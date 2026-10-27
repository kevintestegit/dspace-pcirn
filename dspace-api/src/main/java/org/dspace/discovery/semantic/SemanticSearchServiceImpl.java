/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.discovery.semantic;

import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicLong;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import jakarta.inject.Named;
import org.apache.commons.lang3.StringUtils;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.solr.client.solrj.SolrClient;
import org.apache.solr.client.solrj.SolrQuery;
import org.apache.solr.client.solrj.SolrRequest;
import org.apache.solr.client.solrj.SolrServerException;
import org.apache.solr.client.solrj.impl.HttpSolrClient;
import org.apache.solr.client.solrj.response.QueryResponse;
import org.apache.solr.common.SolrDocument;
import org.apache.solr.common.SolrInputDocument;
import org.dspace.service.impl.HttpConnectionPoolService;
import org.dspace.services.ConfigurationService;
import org.dspace.services.factory.DSpaceServicesFactory;
import org.springframework.beans.factory.annotation.Autowired;

/**
 * Calls an OpenAI-compatible embeddings endpoint and stores the vectors in the dedicated
 * {@code semantic} Solr core.
 *
 * <p>The endpoint is configured with {@code semantic.embedding.url} and is only used when
 * {@code semantic.enabled} is true. Failures are logged and backed off for one minute so a
 * full reindex does not wait for the same timeout on every item.</p>
 */
public class SemanticSearchServiceImpl implements SemanticSearchService {

    private static final Logger log = LogManager.getLogger(SemanticSearchServiceImpl.class);
    private static final ObjectMapper MAPPER = new ObjectMapper();
    private static final long FAILURE_BACKOFF_MILLIS = 60_000L;
    private static final int DEFAULT_MAX_CHARS = 4000;
    private static final int DEFAULT_TIMEOUT_MILLIS = 15_000;

    private final ConfigurationService configurationService;
    private final AtomicLong retryAfter = new AtomicLong();
    private final AtomicBoolean warned = new AtomicBoolean();
    private volatile HttpClient httpClient;
    private volatile SolrClient solr;

    @Autowired(required = false)
    @Named("solrHttpConnectionPoolService")
    private HttpConnectionPoolService httpConnectionPoolService;

    public SemanticSearchServiceImpl() {
        this(DSpaceServicesFactory.getInstance().getConfigurationService());
    }

    SemanticSearchServiceImpl(ConfigurationService configurationService) {
        this.configurationService = configurationService;
    }

    @Override
    public boolean isEnabled() {
        return configurationService.getBooleanProperty("semantic.enabled", false)
            && StringUtils.isNotBlank(configurationService.getProperty("semantic.embedding.url", ""));
    }

    @Override
    public int getMaxChars() {
        return configurationService.getIntProperty("semantic.embedding.max-chars", DEFAULT_MAX_CHARS);
    }

    @Override
    public Optional<float[]> embed(String text) {
        if (!isEnabled() || StringUtils.isBlank(text)) {
            return Optional.empty();
        }
        if (System.currentTimeMillis() < retryAfter.get()) {
            return Optional.empty();
        }

        try {
            String body = MAPPER.writeValueAsString(buildPayload(text));
            HttpRequest.Builder request = HttpRequest.newBuilder(URI.create(getUrl()))
                .timeout(Duration.ofMillis(getTimeoutMillis()))
                .header("Content-Type", "application/json")
                .POST(HttpRequest.BodyPublishers.ofString(body));

            String apiKey = configurationService.getProperty("semantic.embedding.api-key");
            if (StringUtils.isNotBlank(apiKey)) {
                request.header("Authorization", "Bearer " + apiKey);
            }

            HttpResponse<String> response = getHttpClient()
                .send(request.build(), HttpResponse.BodyHandlers.ofString());
            if (response.statusCode() < 200 || response.statusCode() >= 300) {
                throw new IOException("Embedding endpoint returned HTTP " + response.statusCode());
            }

            Optional<float[]> vector = parseVector(response.body());
            if (vector.isEmpty()) {
                throw new IOException("Embedding endpoint returned no vector");
            }
            int expectedDimension = configurationService.getIntProperty("semantic.embedding.dimension", 1024);
            if (vector.get().length != expectedDimension) {
                throw new IOException("Embedding dimension is " + vector.get().length
                    + " but semantic.embedding.dimension is " + expectedDimension);
            }

            retryAfter.set(0);
            warned.set(false);
            return vector;
        } catch (Exception e) {
            recordFailure(e);
            return Optional.empty();
        }
    }

    @Override
    public void index(String uniqueId, float[] vector) throws IOException {
        SolrInputDocument document = new SolrInputDocument();
        document.addField("search.uniqueid", uniqueId);
        List<Float> values = new ArrayList<>(vector.length);
        for (float value : vector) {
            values.add(value);
        }
        document.addField("semantic_vector", values);
        try {
            getSolr().add(document);
        } catch (SolrServerException e) {
            throw new IOException("Could not index semantic vector for " + uniqueId, e);
        }
    }

    @Override
    public void delete(String uniqueId) throws IOException {
        try {
            getSolr().deleteById(uniqueId);
        } catch (SolrServerException e) {
            throw new IOException("Could not delete semantic vector for " + uniqueId, e);
        }
    }

    @Override
    public void deleteAll() throws IOException {
        try {
            getSolr().deleteByQuery("*:*");
        } catch (SolrServerException e) {
            throw new IOException("Could not clear the semantic core", e);
        }
    }

    @Override
    public void commit() throws IOException {
        try {
            getSolr().commit();
        } catch (SolrServerException e) {
            throw new IOException("Could not commit the semantic core", e);
        }
    }

    @Override
    public List<String> search(float[] vector, int topK) {
        SolrQuery query = new SolrQuery();
        query.setQuery("{!knn f=semantic_vector topK=" + topK + "}" + toVectorString(vector));
        query.setFields("search.uniqueid");
        query.setRows(topK);

        try {
            QueryResponse response = getSolr().query(query, SolrRequest.METHOD.POST);
            List<String> identifiers = new ArrayList<>(response.getResults().size());
            for (SolrDocument document : response.getResults()) {
                Object value = document.getFieldValue("search.uniqueid");
                if (value != null) {
                    identifiers.add(value.toString());
                }
            }
            return identifiers;
        } catch (Exception e) {
            log.warn("Semantic vector search failed: {}", e.getMessage());
            return List.of();
        }
    }

    private Map<String, Object> buildPayload(String text) {
        Map<String, Object> payload = new HashMap<>();
        payload.put("input", truncate(text));
        String model = configurationService.getProperty("semantic.embedding.model");
        if (StringUtils.isNotBlank(model)) {
            payload.put("model", model);
        }
        return payload;
    }

    private Optional<float[]> parseVector(String responseBody) throws IOException {
        JsonNode root = MAPPER.readTree(responseBody);
        JsonNode embedding = root.path("data").path(0).path("embedding");
        if (!embedding.isArray()) {
            embedding = root.path("embedding");
        }
        if (!embedding.isArray() || embedding.isEmpty()) {
            return Optional.empty();
        }

        float[] vector = new float[embedding.size()];
        for (int i = 0; i < embedding.size(); i++) {
            vector[i] = (float) embedding.get(i).asDouble();
        }
        return Optional.of(vector);
    }

    private String truncate(String text) {
        int maxChars = getMaxChars();
        if (maxChars > 0 && text.length() > maxChars) {
            return text.substring(0, maxChars);
        }
        return text;
    }

    private String getUrl() {
        return configurationService.getProperty("semantic.embedding.url", "").trim();
    }

    private int getTimeoutMillis() {
        return Math.max(1000, configurationService.getIntProperty(
            "semantic.embedding.timeout-ms", DEFAULT_TIMEOUT_MILLIS));
    }

    private HttpClient getHttpClient() {
        HttpClient client = httpClient;
        if (client == null) {
            synchronized (this) {
                client = httpClient;
                if (client == null) {
                    client = HttpClient.newBuilder()
                        .connectTimeout(Duration.ofMillis(getTimeoutMillis()))
                        .build();
                    httpClient = client;
                }
            }
        }
        return client;
    }

    private SolrClient getSolr() {
        SolrClient client = solr;
        if (client == null) {
            synchronized (this) {
                client = solr;
                if (client == null) {
                    String url = configurationService.getProperty("semantic.solr.server",
                        configurationService.getProperty("solr.server", "") + "/"
                            + configurationService.getProperty("solr.multicorePrefix", "") + "semantic");
                    HttpSolrClient.Builder builder = new HttpSolrClient.Builder(url.trim());
                    if (httpConnectionPoolService != null) {
                        builder.withHttpClient(httpConnectionPoolService.getClient());
                    }
                    client = builder.build();
                    solr = client;
                }
            }
        }
        return client;
    }

    private static String toVectorString(float[] vector) {
        StringBuilder value = new StringBuilder(vector.length * 12).append('[');
        for (int i = 0; i < vector.length; i++) {
            if (i > 0) {
                value.append(',');
            }
            value.append(vector[i]);
        }
        return value.append(']').toString();
    }

    private void recordFailure(Exception e) {
        retryAfter.set(System.currentTimeMillis() + FAILURE_BACKOFF_MILLIS);
        if (warned.compareAndSet(false, true)) {
            log.warn("Semantic embedding request failed; semantic search will fall back to lexical search: {}",
                e.getMessage());
        } else {
            log.debug("Semantic embedding request failed", e);
        }
    }
}

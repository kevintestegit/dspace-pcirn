/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.discovery.semantic;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.io.IOException;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.Optional;
import java.util.concurrent.atomic.AtomicInteger;

import com.sun.net.httpserver.HttpServer;
import org.dspace.services.ConfigurationService;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

public class SemanticSearchServiceImplTest {

    private HttpServer server;
    private String endpoint;
    private final AtomicInteger requests = new AtomicInteger();

    @Before
    public void setUp() throws IOException {
        server = HttpServer.create(new InetSocketAddress(0), 0);
        server.createContext("/v1/embeddings", exchange -> {
            requests.incrementAndGet();
            byte[] body = "{\"data\":[{\"embedding\":[0.1,0.2,0.3]}]}"
                .getBytes(StandardCharsets.UTF_8);
            exchange.sendResponseHeaders(200, body.length);
            exchange.getResponseBody().write(body);
            exchange.close();
        });
        server.start();
        endpoint = "http://localhost:" + server.getAddress().getPort() + "/v1/embeddings";
    }

    @After
    public void tearDown() {
        if (server != null) {
            server.stop(0);
        }
    }

    @Test
    public void embedReturnsConfiguredDimension() {
        Optional<float[]> vector = configuredService(3).embed("texto");

        assertTrue(vector.isPresent());
        assertArrayEquals(new float[] {0.1f, 0.2f, 0.3f}, vector.get(), 0.0001f);
        assertTrue(requests.get() > 0);
    }

    @Test
    public void embedRejectsWrongDimension() {
        assertFalse(configuredService(4).embed("texto").isPresent());
    }

    @Test
    public void embedReturnsEmptyWhenDisabled() {
        ConfigurationService configuration = mock(ConfigurationService.class);
        when(configuration.getBooleanProperty("semantic.enabled", false)).thenReturn(false);

        assertFalse(new SemanticSearchServiceImpl(configuration).embed("texto").isPresent());
        assertFalse(requests.get() > 0);
    }

    private SemanticSearchServiceImpl configuredService(int dimension) {
        ConfigurationService configuration = mock(ConfigurationService.class);
        when(configuration.getBooleanProperty("semantic.enabled", false)).thenReturn(true);
        when(configuration.getProperty("semantic.embedding.url", "")).thenReturn(endpoint);
        when(configuration.getProperty("semantic.embedding.model")).thenReturn("test-model");
        when(configuration.getIntProperty("semantic.embedding.dimension", 1024)).thenReturn(dimension);
        when(configuration.getIntProperty("semantic.embedding.max-chars", 4000)).thenReturn(4000);
        when(configuration.getIntProperty("semantic.embedding.timeout-ms", 15000)).thenReturn(5000);
        return new SemanticSearchServiceImpl(configuration);
    }
}

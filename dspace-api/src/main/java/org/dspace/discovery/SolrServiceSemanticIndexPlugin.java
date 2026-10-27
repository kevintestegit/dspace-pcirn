/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.discovery;

import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.Reader;
import java.nio.charset.StandardCharsets;
import java.util.List;

import org.apache.commons.collections4.CollectionUtils;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.apache.solr.common.SolrInputDocument;
import org.dspace.content.Bitstream;
import org.dspace.content.Bundle;
import org.dspace.content.Item;
import org.dspace.content.MetadataValue;
import org.dspace.content.service.BitstreamService;
import org.dspace.content.service.ItemService;
import org.dspace.core.Context;
import org.dspace.discovery.indexobject.IndexableItem;
import org.dspace.discovery.semantic.SemanticSearchService;
import org.springframework.beans.factory.annotation.Autowired;

/**
 * Adds the item embedding to the semantic Solr core when semantic search is enabled.
 *
 * <p>The text sent to the embedding service is the item title, abstract, subjects and the
 * extracted full text (limited by {@code semantic.embedding.max-chars}).</p>
 */
public class SolrServiceSemanticIndexPlugin implements SolrServiceIndexPlugin {

    private static final Logger log = LogManager.getLogger(SolrServiceSemanticIndexPlugin.class);
    private static final String TEXT_BUNDLE = "TEXT";

    @Autowired
    private SemanticSearchService semanticSearchService;

    @Autowired
    private ItemService itemService;

    @Autowired
    private BitstreamService bitstreamService;

    @Override
    public void additionalIndex(Context context, IndexableObject indexableObject, SolrInputDocument document) {
        if (!(indexableObject instanceof IndexableItem) || !semanticSearchService.isEnabled()) {
            return;
        }

        Item item = ((IndexableItem) indexableObject).getIndexedObject();
        try {
            String text = buildText(context, item, semanticSearchService.getMaxChars());
            semanticSearchService.embed(text).ifPresent(vector -> {
                try {
                    semanticSearchService.index(indexableObject.getUniqueIndexID(), vector);
                } catch (IOException e) {
                    log.warn("Could not store semantic vector for item {}", item.getID(), e);
                }
            });
        } catch (Exception e) {
            log.warn("Could not generate semantic vector for item {}", item.getID(), e);
        }
    }

    private String buildText(Context context, Item item, int maxChars) {
        StringBuilder text = new StringBuilder();
        appendMetadata(text, itemService.getMetadataByMetadataString(item, "dc.title"));
        appendMetadata(text, itemService.getMetadataByMetadataString(item, "dc.description.abstract"));
        appendMetadata(text, itemService.getMetadataByMetadataString(item, "dc.subject"));

        for (Bundle bundle : CollectionUtils.emptyIfNull(item.getBundles())) {
            if (!TEXT_BUNDLE.equals(bundle.getName())) {
                continue;
            }
            for (Bitstream bitstream : CollectionUtils.emptyIfNull(bundle.getBitstreams())) {
                if (text.length() >= maxChars) {
                    break;
                }
                try (InputStream input = bitstreamService.retrieve(context, bitstream)) {
                    readAtMost(input, maxChars - text.length(), text);
                } catch (Exception e) {
                    log.debug("Could not read extracted text from bitstream {}", bitstream.getID(), e);
                }
            }
        }
        return text.toString();
    }

    private void appendMetadata(StringBuilder text, List<MetadataValue> values) {
        for (MetadataValue value : CollectionUtils.emptyIfNull(values)) {
            if (value.getValue() != null) {
                text.append(value.getValue()).append(' ');
            }
        }
    }

    private void readAtMost(InputStream input, int maxChars, StringBuilder text) throws IOException {
        try (Reader reader = new InputStreamReader(input, StandardCharsets.UTF_8)) {
            char[] buffer = new char[4096];
            int remaining = maxChars;
            int read;
            while (remaining > 0 && (read = reader.read(buffer, 0, Math.min(buffer.length, remaining))) != -1) {
                text.append(buffer, 0, read);
                remaining -= read;
            }
        }
    }
}

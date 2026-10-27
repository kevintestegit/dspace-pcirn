/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.discovery.semantic;

import java.io.IOException;
import java.util.List;
import java.util.Optional;

/**
 * Embedding client and vector store used by the semantic search mode.
 */
public interface SemanticSearchService {

    /**
     * @return true when semantic search is enabled and an embedding endpoint is configured.
     */
    boolean isEnabled();

    /**
     * Converts text to a dense vector.
     *
     * @param text text to embed.
     * @return the vector, or empty when semantic search is disabled or the service fails.
     */
    Optional<float[]> embed(String text);

    /**
     * Maximum number of characters sent to the embedding service.
     *
     * @return character limit.
     */
    int getMaxChars();

    /**
     * Stores or replaces an item vector.
     *
     * @param uniqueId DSpace index identifier, e.g. {@code Item-uuid}.
     * @param vector   item embedding.
     */
    void index(String uniqueId, float[] vector) throws IOException;

    /**
     * Removes an item vector.
     *
     * @param uniqueId DSpace index identifier.
     */
    void delete(String uniqueId) throws IOException;

    /**
     * Removes every vector from the semantic core.
     */
    void deleteAll() throws IOException;

    /**
     * Commits pending vector updates.
     */
    void commit() throws IOException;

    /**
     * Finds the closest item identifiers.
     *
     * @param vector query embedding.
     * @param topK   maximum number of neighbours.
     * @return identifiers ordered from most to least similar.
     */
    List<String> search(float[] vector, int topK);
}

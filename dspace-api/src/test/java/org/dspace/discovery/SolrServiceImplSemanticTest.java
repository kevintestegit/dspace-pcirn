/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.discovery;

import static org.junit.Assert.assertEquals;

import java.util.List;

import org.junit.Test;

public class SolrServiceImplSemanticTest {

    @Test
    public void identifiersAreBoostedInSemanticOrder() {
        assertEquals("(search.uniqueid:\"Item-a\"^0.0100 OR search.uniqueid:\"Item-b\"^0.0050"
                + " OR search.uniqueid:\"Item-c\"^0.0033)",
            SolrServiceImpl.buildIdentifierQuery(List.of("Item-a", "Item-b", "Item-c")));
    }

    @Test
    public void semanticQueryKeepsTheLexicalMatches() {
        assertEquals("((crime contra a fauna) OR dc.title:(crime contra a fauna)^2)"
                + " OR (search.uniqueid:\"Item-a\"^0.0100)",
            SolrServiceImpl.buildSemanticQuery("crime contra a fauna", List.of("Item-a")));
    }
}

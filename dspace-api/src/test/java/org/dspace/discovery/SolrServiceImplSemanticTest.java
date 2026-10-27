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
        assertEquals("(search.uniqueid:\"Item-a\"^3 OR search.uniqueid:\"Item-b\"^2"
                + " OR search.uniqueid:\"Item-c\"^1)",
            SolrServiceImpl.buildIdentifierQuery(List.of("Item-a", "Item-b", "Item-c")));
    }
}

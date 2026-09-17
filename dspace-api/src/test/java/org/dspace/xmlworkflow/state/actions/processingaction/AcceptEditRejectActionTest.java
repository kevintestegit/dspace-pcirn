/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.xmlworkflow.state.actions.processingaction;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;

import java.util.List;

import org.junit.Test;

/**
 * Unit tests for the reviewer decisions exposed by {@link AcceptEditRejectAction}.
 */
public class AcceptEditRejectActionTest {

    @Test
    public void testOptionsExposeTheFourReviewerDecisions() {
        List<String> options = new AcceptEditRejectAction().getOptions();

        assertTrue(options.contains("submit_approve"));
        assertTrue(options.contains("submit_reject"));
        assertTrue(options.contains("submit_edit_metadata"));
        assertTrue(options.contains("submit_delete"));
        assertFalse(options.contains("return_to_pool"));
    }
}

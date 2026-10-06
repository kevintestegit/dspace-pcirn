/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.util;

import static org.junit.Assert.assertArrayEquals;
import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import java.io.ByteArrayInputStream;
import java.io.IOException;

import org.junit.Test;

/** Tests that exceeding a byte limit cannot look like a successful truncated read. */
public class LimitedInputStreamTest {
    @Test
    public void readsExactBudgetAndUnlimitedSizedBudget() throws Exception {
        byte[] bytes = {1, 2, 3};
        for (long budget : new long[] {3, Long.MAX_VALUE}) {
            try (LimitedInputStream input = new LimitedInputStream(new ByteArrayInputStream(bytes), budget)) {
                assertArrayEquals(bytes, input.readAllBytes());
            }
        }
    }

    @Test
    public void rejectsOverflowViaBulkReadAndSkip() throws Exception {
        try (LimitedInputStream input = new LimitedInputStream(new ByteArrayInputStream(new byte[4]), 3)) {
            assertThrows(IOException.class, input::readAllBytes);
        }
        try (LimitedInputStream input = new LimitedInputStream(new ByteArrayInputStream(new byte[4]), 3)) {
            assertThrows(IOException.class, () -> input.skip(4));
        }
    }

    @Test
    public void zeroBudgetAllowsOnlyEmptyStream() throws Exception {
        try (LimitedInputStream input = new LimitedInputStream(new ByteArrayInputStream(new byte[0]), 0)) {
            assertEquals(-1, input.read());
        }
        try (LimitedInputStream input = new LimitedInputStream(new ByteArrayInputStream(new byte[1]), 0)) {
            assertThrows(IOException.class, input::read);
        }
    }
}

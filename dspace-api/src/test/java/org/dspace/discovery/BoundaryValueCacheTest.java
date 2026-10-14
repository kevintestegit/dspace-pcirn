/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.discovery;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNull;

import org.junit.Test;

/**
 * Verifies the lifetime rules of the cache that holds the boundaries of the index.
 */
public class BoundaryValueCacheTest {

    private static final long LONG_LIVED = 60_000L;

    @Test
    public void returnsWhatWasPut() {
        BoundaryValueCache<String> cache = new BoundaryValueCache<>(LONG_LIVED);

        cache.put("key", "value");

        assertEquals("value", cache.get("key"));
    }

    @Test
    public void missingKeyReturnsNull() {
        BoundaryValueCache<String> cache = new BoundaryValueCache<>(LONG_LIVED);

        assertNull(cache.get("never put"));
    }

    @Test
    public void expiredValueIsNotReturned() throws Exception {
        BoundaryValueCache<String> cache = new BoundaryValueCache<>(1);
        cache.put("key", "value");

        Thread.sleep(20);

        assertNull("a value that outlived its time to live must not be served", cache.get("key"));
    }

    @Test
    public void invalidateDropsEverything() {
        BoundaryValueCache<String> cache = new BoundaryValueCache<>(LONG_LIVED);
        cache.put("one", "1");
        cache.put("two", "2");

        cache.invalidate();

        assertNull(cache.get("one"));
        assertNull(cache.get("two"));
    }

    @Test
    public void cachedValuesAreNotSharedWithAnotherType() {
        BoundaryValueCache<int[]> cache = new BoundaryValueCache<>(LONG_LIVED);

        cache.put("range", new int[] {1959, 2026});

        assertEquals(1959, cache.get("range")[0]);
        assertEquals(2026, cache.get("range")[1]);
    }

    /**
     * The keys carry the identity of the user, so the cache has to stay bounded even when many different users ask.
     */
    @Test
    public void cacheStaysBounded() {
        BoundaryValueCache<String> cache = new BoundaryValueCache<>(LONG_LIVED);
        int overTheLimit = 1001;

        for (int i = 0; i < overTheLimit; i++) {
            cache.put("key" + i, "value" + i);
        }

        assertNull("the oldest entries must have been dropped", cache.get("key0"));
        assertEquals("value1000", cache.get("key1000"));
    }
}

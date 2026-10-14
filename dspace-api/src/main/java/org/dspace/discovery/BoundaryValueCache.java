/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.discovery;

import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;

/**
 * Short lived, JVM wide cache of the values that only describe the boundaries of a result set: the year span of a
 * date facet and the smallest and largest value of the facets that expose their minimum and maximum.
 * <P>
 * Those values answer the same thing for every search of a user with the same permissions, but they have to be
 * resolved before the main query can be built, so without a cache they are looked up again on every search. They are
 * only valid while the index does not change, so {@link #invalidate()} has to be called by every indexing operation,
 * and, as a safety net for an index changed by another process, they also expire after a short time.
 *
 * @param <V> the type of the cached value.
 */
class BoundaryValueCache<V> {

    /**
     * Upper bound on the number of entries. The keys carry the identity of the user, so a repository with many
     * authenticated users could otherwise grow the cache without limit. Reaching the bound simply drops what was
     * cached so far; resolving the values again is cheap.
     */
    private static final int MAX_ENTRIES = 1000;

    private final long timeToLiveMillis;
    private final Map<String, Entry<V>> values = new ConcurrentHashMap<>();

    BoundaryValueCache(long timeToLiveMillis) {
        this.timeToLiveMillis = timeToLiveMillis;
    }

    /**
     * Returns the value cached for the given key.
     *
     * @param key the key, which must encode everything the value depends on.
     * @return the cached value, or null when nothing is cached for that key or what is cached has expired.
     */
    V get(String key) {
        Entry<V> entry = values.get(key);
        if (entry == null) {
            return null;
        }
        if (System.currentTimeMillis() - entry.createdAt > timeToLiveMillis) {
            values.remove(key, entry);
            return null;
        }
        return entry.value;
    }

    void put(String key, V value) {
        if (values.size() >= MAX_ENTRIES) {
            invalidate();
        }
        values.put(key, new Entry<>(value, System.currentTimeMillis()));
    }

    /**
     * Drops everything that was cached. Has to be called whenever the index changes.
     */
    void invalidate() {
        values.clear();
    }

    private static class Entry<V> {

        private final V value;
        private final long createdAt;

        Entry(V value, long createdAt) {
            this.value = value;
            this.createdAt = createdAt;
        }
    }
}

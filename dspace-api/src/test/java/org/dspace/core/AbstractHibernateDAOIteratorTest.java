/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.core;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.mockito.Mockito.CALLS_REAL_METHODS;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.util.Iterator;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.stream.Stream;

import jakarta.persistence.Query;
import org.junit.Test;

/**
 * JDBC iteration must release resources on the owning thread, without a finalizer.
 */
public class AbstractHibernateDAOIteratorTest {

    private Iterator<Object> iterator(Stream<Object> stream) {
        Query query = mock(Query.class);
        org.hibernate.query.Query hibernate = mock(org.hibernate.query.Query.class);
        when(query.unwrap(org.hibernate.query.Query.class)).thenReturn(hibernate);
        when(hibernate.stream()).thenReturn(stream);
        AbstractHibernateDAO<Object> dao = mock(AbstractHibernateDAO.class, CALLS_REAL_METHODS);
        return dao.iterate(query);
    }

    /** Exhausting a nonempty stream closes it exactly once. */
    @Test
    public void exhaustedIteratorClosesStream() {
        AtomicInteger closed = new AtomicInteger();
        Iterator<Object> iterator = iterator(Stream.<Object>of("value").onClose(closed::incrementAndGet));
        assertEquals("value", iterator.next());
        assertEquals(0, closed.get());
        assertFalse(iterator.hasNext());
        assertFalse(iterator.hasNext());
        assertEquals(1, closed.get());
    }

    /** An empty result closes without creating a finalizer for a JDBC resource. */
    @Test
    public void emptyIteratorClosesWithoutFinalizer() {
        AtomicInteger closed = new AtomicInteger();
        Iterator<Object> iterator = iterator(Stream.empty().onClose(closed::incrementAndGet));
        assertFalse(iterator.hasNext());
        assertEquals(1, closed.get());
        assertThrows(NoSuchMethodException.class, () -> iterator.getClass().getDeclaredMethod("finalize"));
    }
}

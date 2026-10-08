/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.core;

import static org.junit.Assert.assertThrows;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.never;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.sql.SQLException;

import org.hibernate.Session;
import org.hibernate.Transaction;
import org.hibernate.resource.transaction.spi.TransactionStatus;
import org.junit.Test;

/**
 * Commit outcome tests without a database connection.
 */
public class HibernateDBConnectionCommitTest {

    @Test
    public void rollbackOnlyTransactionCannotReportSuccessfulCommit() throws Exception {
        assertCommitRejected(TransactionStatus.MARKED_ROLLBACK);
    }

    @Test
    public void rollingBackTransactionCannotReportSuccessfulCommit() throws Exception {
        assertCommitRejected(TransactionStatus.ROLLING_BACK);
    }

    @Test
    public void inactiveTransactionStillAllowsNoOpCommit() throws Exception {
        HibernateDBConnection connection = spy(new HibernateDBConnection());
        Transaction transaction = mock(Transaction.class);
        doReturn(transaction).when(connection).getTransaction();
        when(transaction.getStatus()).thenReturn(TransactionStatus.NOT_ACTIVE);

        connection.commit();

        verify(transaction, never()).commit();
        verify(connection, never()).getSession();
    }

    @Test
    public void activeTransactionStillFlushesAndCommits() throws Exception {
        HibernateDBConnection connection = spy(new HibernateDBConnection());
        Transaction transaction = mock(Transaction.class);
        Session session = mock(Session.class);
        doReturn(transaction).when(connection).getTransaction();
        doReturn(session).when(connection).getSession();
        when(transaction.isActive()).thenReturn(true);
        when(transaction.getStatus()).thenReturn(TransactionStatus.ACTIVE);

        connection.commit();

        verify(session).flush();
        verify(transaction).commit();
    }

    private void assertCommitRejected(TransactionStatus status) throws Exception {
        HibernateDBConnection connection = spy(new HibernateDBConnection());
        Transaction transaction = mock(Transaction.class);
        doReturn(transaction).when(connection).getTransaction();
        when(transaction.isActive()).thenReturn(status == TransactionStatus.MARKED_ROLLBACK);
        when(transaction.getStatus()).thenReturn(status);

        assertThrows(SQLException.class, connection::commit);

        verify(transaction, never()).commit();
        verify(connection, never()).getSession();
    }
}

/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.storage.rdbms;

import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;

import org.junit.Before;
import org.junit.Test;

/** Tests that profile selection never adopts existing repository data. */
public class PcirnFreshProfileTest {
    private Connection connection;
    private DatabaseMetaData metadata;
    private ResultSet tables;
    private ResultSet rows;

    @Before
    public void setup() throws SQLException {
        connection = mock(Connection.class);
        metadata = mock(DatabaseMetaData.class);
        tables = mock(ResultSet.class);
        rows = mock(ResultSet.class);
        PreparedStatement statement = mock(PreparedStatement.class);
        when(connection.getSchema()).thenReturn("public");
        when(connection.getMetaData()).thenReturn(metadata);
        when(metadata.getTables(null, "public", "schema_version", null)).thenReturn(tables);
        when(connection.prepareStatement(anyString())).thenReturn(statement);
        when(statement.executeQuery()).thenReturn(rows);
    }

    @Test
    public void emptyDatabaseIsAllowed() throws SQLException {
        when(rows.next()).thenReturn(true);
        when(rows.getLong(1)).thenReturn(0L);
        PcirnFreshProfile.validate(connection);
    }

    @Test(expected = SQLException.class)
    public void databaseWithoutHistoryButWithObjectsIsRejected() throws SQLException {
        when(rows.next()).thenReturn(true);
        when(rows.getLong(1)).thenReturn(1L);
        PcirnFreshProfile.validate(connection);
    }

    @Test(expected = SQLException.class)
    public void institutionalHistoryIsRejected() throws SQLException {
        when(tables.next()).thenReturn(true);
        when(rows.next()).thenReturn(true, false);
        when(rows.getString(1)).thenReturn("V9.4_2026.08.15__pcirn_sector_access.sql");
        PcirnFreshProfile.validate(connection);
    }

    @Test
    public void initializedFreshRepositoryIsAllowed() throws SQLException {
        when(tables.next()).thenReturn(true);
        when(rows.next()).thenReturn(true, false);
        when(rows.getString(1)).thenReturn("V9.4_2026.10.13__pcirn_fresh_roles.sql");
        PcirnFreshProfile.validate(connection);
    }

    @Test
    public void genericPcirnUpgradeDoesNotChangeProfile() throws SQLException {
        when(tables.next()).thenReturn(true);
        when(rows.next()).thenReturn(true, true, false);
        when(rows.getString(1)).thenReturn("V9.4_2026.10.13__pcirn_fresh_roles.sql",
            "V9.4_2026.10.14__pcirn_generic_upgrade.sql");
        PcirnFreshProfile.validate(connection);
    }

    @Test(expected = SQLException.class)
    public void partiallyMigratedRepositoryWithContentIsRejected() throws SQLException {
        when(tables.next()).thenReturn(true);
        ResultSet communityTable = mock(ResultSet.class);
        when(metadata.getTables(null, "public", "community", null)).thenReturn(communityTable);
        when(communityTable.next()).thenReturn(true);
        when(rows.next()).thenReturn(false, true);
        when(rows.getLong(1)).thenReturn(1L);
        PcirnFreshProfile.validate(connection);
    }
}

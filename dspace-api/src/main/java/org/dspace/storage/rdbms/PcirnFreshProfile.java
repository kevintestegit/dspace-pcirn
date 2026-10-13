/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.storage.rdbms;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.Set;

/**
 * Prevents selecting the empty-repository migration profile for an institutional database.
 * Historical institutional migrations remain available with their original checksums
 * in the default profile; the fresh profile has its own explicit migration history.
 */
public final class PcirnFreshProfile {
    private static final String FRESH_ROLES = "V9.4_2026.10.13__pcirn_fresh_roles.sql";
    private static final Set<String> INSTITUTIONAL_MIGRATIONS = Set.of(
        "V9.4_2026.08.14__pcirn_mvp_access.sql",
        "V9.4_2026.08.15__pcirn_sector_access.sql",
        "V9.4_2026.08.16__pcirn_sector_membership_reconcile.sql",
        "V9.4_2026.08.17__pcirn_portarias_collections.sql",
        "V9.4_2026.08.18__pcirn_public_portarias.sql",
        "V9.4_2026.08.24__pcirn_sector_submission_and_shared_read.sql",
        "V9.4_2026.09.15__pcirn_public_items.sql",
        "V9.4_2026.09.17__pcirn_access_reconcile.sql",
        "V9.4_2026.09.23__pcirn_memoria_institucional_collection.sql");

    private PcirnFreshProfile() {
    }

    /**
     * Reject a database that already contains an institutional migration history.
     *
     * @param connection the migration connection
     * @throws SQLException if institutional history exists or validation cannot complete
     */
    public static void validate(Connection connection) throws SQLException {
        if (!tableExists(connection, "schema_version")) {
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT count(*) FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace"
                        + " WHERE n.nspname = current_schema() AND c.relkind IN ('r','p','v','m','S','f')");
                 ResultSet rows = statement.executeQuery()) {
                if (!rows.next() || rows.getLong(1) != 0) {
                    throw new SQLException("The fresh profile requires an empty database before initialization");
                }
            }
            return;
        }
        boolean initialized = false;
        try (PreparedStatement statement = connection.prepareStatement(
                "SELECT script FROM schema_version WHERE script LIKE '%pcirn%'");
             ResultSet rows = statement.executeQuery()) {
            while (rows.next()) {
                String script = rows.getString(1);
                if (INSTITUTIONAL_MIGRATIONS.contains(script)) {
                    throw new SQLException("The fresh profile cannot replace institutional migration history");
                }
                initialized |= FRESH_ROLES.equals(script);
            }
        }
        if (!initialized && tableExists(connection, "community")) {
            try (PreparedStatement statement = connection.prepareStatement(
                    "SELECT (SELECT count(*) FROM community) + (SELECT count(*) FROM collection)"
                        + " + (SELECT count(*) FROM item) + (SELECT count(*) FROM eperson)");
                 ResultSet rows = statement.executeQuery()) {
                if (rows.next() && rows.getLong(1) != 0) {
                    throw new SQLException("The fresh profile requires an empty repository");
                }
            }
        }
    }

    private static boolean tableExists(Connection connection, String name) throws SQLException {
        try (ResultSet tables = connection.getMetaData().getTables(null, connection.getSchema(), name, null)) {
            return tables.next();
        }
    }
}

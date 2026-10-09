/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.core;

import static org.junit.Assert.assertNotNull;
import static org.mockito.Mockito.CALLS_REAL_METHODS;
import static org.mockito.Mockito.mockStatic;
import static org.mockito.Mockito.never;

import org.dspace.AbstractIntegrationTestWithDatabase;
import org.dspace.storage.rdbms.DatabaseUtils;
import org.junit.Test;
import org.mockito.MockedStatic;

/**
 * Opening a context must never change the database schema.
 * <P>
 * The schema is brought up to date only by an explicit
 * {@code dspace database migrate}, which is what lets an operator authorize a
 * migration. A deployment that opened a context first used to migrate the
 * database as a side effect, so the authorization could be bypassed.
 */
public class ContextInitializationTest extends AbstractIntegrationTestWithDatabase {

    @Test
    public void initializingAContextDoesNotRunMigrations() throws Exception {
        try (MockedStatic<DatabaseUtils> migrations =
                 mockStatic(DatabaseUtils.class, CALLS_REAL_METHODS)) {
            try (Context context = new Context()) {
                assertNotNull(context.getDBConnection());
            }

            migrations.verify(() -> DatabaseUtils.updateDatabase(), never());
        }
    }
}

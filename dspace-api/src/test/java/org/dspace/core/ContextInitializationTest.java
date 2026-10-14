/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.core;

import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.mockStatic;
import static org.mockito.Mockito.when;

import org.dspace.event.service.EventService;
import org.dspace.services.ConfigurationService;
import org.dspace.services.factory.DSpaceServicesFactory;
import org.dspace.storage.rdbms.DatabaseUtils;
import org.junit.Test;
import org.mockito.MockedStatic;

/**
 * Checks context initialization without a database or Spring application.
 */
public class ContextInitializationTest {

    /**
     * Opening a context must leave schema changes to the explicit database command.
     */
    @Test
    public void initializationDoesNotRunMigrations() {
        DSpaceServicesFactory factory = mock(DSpaceServicesFactory.class);
        when(factory.getConfigurationService()).thenReturn(mock(ConfigurationService.class));
        try (MockedStatic<DSpaceServicesFactory> services = mockStatic(DSpaceServicesFactory.class)) {
            services.when(DSpaceServicesFactory::getInstance).thenReturn(factory);
            try (MockedStatic<DatabaseUtils> migrations = mockStatic(DatabaseUtils.class)) {
                new Context(mock(EventService.class), mock(DBConnection.class));
                migrations.verifyNoInteractions();
            }
        }
    }
}

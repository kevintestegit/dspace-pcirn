/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.service.impl;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;

import org.dspace.services.ConfigurationService;
import org.junit.Test;
import org.springframework.context.annotation.AnnotationConfigApplicationContext;
import org.springframework.test.util.ReflectionTestUtils;

/**
 * Closing a Spring context must not leave a monitor retaining the old service graph.
 */
public class HttpConnectionPoolLifecycleTest {

    /**
     * The service's destruction callback stops the monitor, including repeated closure.
     * @throws InterruptedException if the test thread is interrupted while joining the monitor
     */
    @Test
    public void springShutdownStopsConnectionMonitor() throws InterruptedException {
        ConfigurationService configuration = mock(ConfigurationService.class);
        when(configuration.getIntProperty(anyString(), anyInt())).thenAnswer(call -> call.getArgument(1));
        Thread monitor;
        HttpConnectionPoolService pool;
        try (AnnotationConfigApplicationContext spring = new AnnotationConfigApplicationContext()) {
            spring.registerBean(ConfigurationService.class, () -> configuration);
            spring.registerBean(HttpConnectionPoolService.class, () -> new HttpConnectionPoolService("test"));
            spring.refresh();
            pool = spring.getBean(HttpConnectionPoolService.class);
            monitor = (Thread) ReflectionTestUtils.getField(pool, "connectionMonitor");
            assertTrue(monitor.isAlive());
        }
        monitor.join(2000);
        assertFalse("A destroyed pool must not retain its service graph", monitor.isAlive());
        pool.close();
    }
}

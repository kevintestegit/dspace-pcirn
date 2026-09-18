/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */

package org.dspace.services.email;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;
import static org.junit.Assert.assertNull;

import jakarta.mail.MessagingException;
import jakarta.mail.PasswordAuthentication;
import jakarta.mail.Session;
import org.dspace.services.ConfigurationService;
import org.dspace.services.EmailService;
import org.dspace.test.DSpaceAbstractKernelTest;
import org.junit.Test;

/**
 * @author mwood
 */
public class EmailServiceImplTest
    extends DSpaceAbstractKernelTest {
    private static final String USERNAME = "auser";
    private static final String PASSWORD = "apassword";

    /*
    @BeforeClass
    public static void setUpClass()
            throws Exception
    {
    }

    @AfterClass
    public static void tearDownClass()
            throws Exception
    {
    }

    @Before
    public void setUp()
    {
    }

    @After
    public void tearDown()
    {
    }
    */

    /**
     * Test of getSession method, of class EmailService.
     */
    @Test
    public void testGetSession()
        throws MessagingException {
        System.out.println("getSession");
        Session session;
        EmailService instance = getService(EmailServiceImpl.class);

        // Try to get a Session
        session = instance.getSession();
        assertNotNull(" getSession returned null", session);
        assertNull(" getSession returned authenticated session",
                session.getProperties().getProperty("mail.smtp.auth"));
    }

    private static final String CFG_USERNAME = "mail.server.username";
    private static final String CFG_PASSWORD = "mail.server.password";
    private static final String CFG_SERVER = "mail.server";
    private static final String CFG_SERVER_PORT = "mail.server.port";
    private static final String CFG_EXTRAPROPERTIES = "mail.extraproperties";

    /**
     * Test of testGetSession method, of class EmailServiceImpl when an smtp
     * username is provided.
     */
    @Test
    public void testGetAuthenticatedInstance() {
        System.out.println("getSession");
        ConfigurationService cfg = getKernel().getConfigurationService();

        // Save existing values.
        String oldUsername = cfg.getProperty(CFG_USERNAME);
        String oldPassword = cfg.getProperty(CFG_PASSWORD);

        // Set known values.
        cfg.setProperty(CFG_USERNAME, USERNAME);
        cfg.setProperty(CFG_PASSWORD, PASSWORD);

        EmailServiceImpl instance = (EmailServiceImpl) getService(EmailServiceImpl.class);
        instance.reset();
        assertNotNull(" getSession returned null", instance);
        assertEquals(" authenticated session ", "true",
                instance.getSession().getProperties().getProperty("mail.smtp.auth"));

        // Restore old values, if any.
        cfg.setProperty(CFG_USERNAME, oldUsername);
        cfg.setProperty(CFG_PASSWORD, oldPassword);
        instance.reset();
    }

    /**
     * Test of an authenticated session configured for Resend SMTP with STARTTLS.
     */
    @Test
    public void testGetAuthenticatedStartTlsSession() {
        System.out.println("getAuthenticatedStartTlsSession");
        ConfigurationService cfg = getKernel().getConfigurationService();

        String oldServer = cfg.getProperty(CFG_SERVER);
        String oldServerPort = cfg.getProperty(CFG_SERVER_PORT);
        String oldUsername = cfg.getProperty(CFG_USERNAME);
        String oldPassword = cfg.getProperty(CFG_PASSWORD);
        String oldExtraProperties = cfg.getProperty(CFG_EXTRAPROPERTIES);

        EmailServiceImpl instance = (EmailServiceImpl) getService(EmailServiceImpl.class);
        try {
            cfg.setProperty(CFG_SERVER, "smtp.resend.com");
            cfg.setProperty(CFG_SERVER_PORT, "587");
            cfg.setProperty(CFG_USERNAME, "resend");
            cfg.setProperty(CFG_PASSWORD, "dummy-resend-api-key");
            cfg.setProperty(CFG_EXTRAPROPERTIES,
                    "mail.smtp.starttls.enable=true,mail.smtp.starttls.required=true");

            instance.reset();
            Session session = instance.getSession();
            assertNotNull(" getSession returned null", session);
            assertEquals("smtp.resend.com", session.getProperties().getProperty("mail.host"));
            assertEquals("587", session.getProperties().getProperty("mail.smtp.port"));
            assertEquals("true", session.getProperties().getProperty("mail.smtp.auth"));
            assertEquals("true",
                    session.getProperties().getProperty("mail.smtp.starttls.enable"));
            assertEquals("true",
                    session.getProperties().getProperty("mail.smtp.starttls.required"));
        } finally {
            cfg.setProperty(CFG_SERVER, oldServer);
            cfg.setProperty(CFG_SERVER_PORT, oldServerPort);
            cfg.setProperty(CFG_USERNAME, oldUsername);
            cfg.setProperty(CFG_PASSWORD, oldPassword);
            cfg.setProperty(CFG_EXTRAPROPERTIES, oldExtraProperties);
            instance.reset();
        }
    }

    /**
     * Test of getPasswordAuthentication method, of class EmailServiceImpl.
     */
    @Test
    public void testGetPasswordAuthentication() {
        System.out.println("getPasswordAuthentication");
        ConfigurationService cfg = getKernel().getConfigurationService();

        // Save existing values.
        String oldUsername = cfg.getProperty(CFG_USERNAME);
        String oldPassword = cfg.getProperty(CFG_PASSWORD);

        // Set known values.
        cfg.setProperty(CFG_USERNAME, USERNAME);
        cfg.setProperty(CFG_PASSWORD, PASSWORD);

        EmailServiceImpl instance = (EmailServiceImpl) getService(EmailServiceImpl.class);

        PasswordAuthentication result = instance.getPasswordAuthentication();
        assertNotNull(" null returned", result);
        assertEquals(" username does not match configuration", result.getUserName(), USERNAME);
        assertEquals(" password does not match configuration", result.getPassword(), PASSWORD);

        // Restore old values, if any.
        cfg.setProperty(CFG_USERNAME, oldUsername);
        cfg.setProperty(CFG_PASSWORD, oldPassword);
    }
}

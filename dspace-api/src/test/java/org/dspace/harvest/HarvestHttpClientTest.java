/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.harvest;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;
import static org.mockito.Mockito.CALLS_REAL_METHODS;
import static org.mockito.Mockito.mockStatic;

import java.io.IOException;
import java.io.InputStream;
import java.net.InetAddress;
import java.net.URI;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.TimeUnit;

import okhttp3.mockwebserver.MockResponse;
import okhttp3.mockwebserver.MockWebServer;
import org.junit.Test;
import org.mockito.MockedStatic;
import org.xml.sax.SAXException;

/** Tests for harvesting URL and connection address boundaries. */
public class HarvestHttpClientTest {
    @Test
    public void parsesOaiErrorsAndPaginationButRejectsExternalXmlEntities() throws Exception {
        try (MockWebServer server = new MockWebServer();
             MockedStatic<HarvestHttpClient> policy = mockStatic(HarvestHttpClient.class, CALLS_REAL_METHODS)) {
            server.start(80);
            policy.when(() -> HarvestHttpClient.resolvePublicAddresses("provider.example"))
                .thenReturn(new InetAddress[] {InetAddress.getByName("127.0.0.1")});
            server.enqueue(new MockResponse().setBody("<OAI-PMH xmlns='http://www.openarchives.org/OAI/2.0/'>"
                + "<ListRecords><record><metadata><resumptionToken>ignore</resumptionToken></metadata></record>"
                + "<resumptionToken>next &amp; page</resumptionToken></ListRecords></OAI-PMH>"));
            OaiResponse response = OaiResponse.request("http://provider.example/oai", "ListRecords",
                "metadataPrefix", "oai_dc", "set", "set & value");
            assertEquals("next & page", response.getResumptionToken());
            assertEquals(0, response.getErrors().getLength());
            assertTrue(server.takeRequest().getPath().contains("set=set+%26+value"));
            server.enqueue(new MockResponse().setBody("<OAI-PMH xmlns='http://www.openarchives.org/OAI/2.0/'>"
                + "<error code='noRecordsMatch'>none</error></OAI-PMH>"));
            assertEquals(1, OaiResponse.request("http://provider.example/oai", "ListRecords").getErrors().getLength());
            server.enqueue(new MockResponse().setBody("<!DOCTYPE x [<!ENTITY secret SYSTEM 'file:///etc/passwd'>]>"
                + "<x>&secret;</x>"));
            assertThrows(SAXException.class, () -> OaiResponse.request("http://provider.example/oai", "Identify"));
        }
    }
    @Test(timeout = 10000)
    public void followsPublicRedirectsButRejectsPrivateRedirectsAndOversizedBodies() throws Exception {
        try (MockWebServer server = new MockWebServer();
             MockedStatic<HarvestHttpClient> policy = mockStatic(HarvestHttpClient.class, CALLS_REAL_METHODS)) {
            server.start(80);
            // Only the synthetic public provider is routed to the isolated loopback test server.
            policy.when(() -> HarvestHttpClient.resolvePublicAddresses("provider.example"))
                .thenReturn(new InetAddress[] {InetAddress.getByName("127.0.0.1")});
            server.enqueue(new MockResponse().setResponseCode(302).addHeader("Location", "http://provider.example/next"));
            server.enqueue(new MockResponse().setBody("valid"));
            try (InputStream response = HarvestHttpClient.open(URI.create("http://provider.example/oai"), 10)) {
                assertEquals("valid", new String(response.readAllBytes(), StandardCharsets.UTF_8));
            }
            server.enqueue(new MockResponse().setResponseCode(302).addHeader("Location", "http://127.0.0.1/private"));
            assertThrows(IOException.class, () -> HarvestHttpClient.open(URI.create("http://provider.example/oai"), 10));
            assertEquals(3, server.getRequestCount());
            server.enqueue(new MockResponse().setBody("x".repeat(100000)).throttleBody(1024, 1, TimeUnit.SECONDS));
            try (InputStream response = HarvestHttpClient.open(URI.create("http://provider.example/resource"), 3)) {
                assertThrows(IOException.class, response::readAllBytes);
            }
        }
    }
    @Test
    public void rejectsNonPublicIpv4AndIpv6() throws Exception {
        for (String address : new String[] {"0.0.0.0", "10.1.2.3", "127.0.0.1", "169.254.169.254",
            "172.16.0.1", "192.168.0.1", "100.64.0.1", "192.0.2.1", "198.18.0.1", "224.0.0.1", "240.0.0.1",
            "::", "::1", "::ffff:127.0.0.1", "fc00::1", "fe80::1", "ff02::1", "2001:db8::1", "2002:7f00:1::"}) {
            assertFalse(address, HarvestHttpClient.isPublicAddress(InetAddress.getByName(address)));
        }
    }

    @Test
    public void acceptsPublicAddressesAndStandardPorts() throws Exception {
        for (String address : new String[] {"8.8.8.8", "1.1.1.1", "2606:4700:4700::1111"}) {
            assertTrue(address, HarvestHttpClient.isPublicAddress(InetAddress.getByName(address)));
        }
        HarvestHttpClient.validateUri(URI.create("https://provider.example/oai"));
        HarvestHttpClient.validateUri(URI.create("http://provider.example:80/oai"));
    }

    @Test
    public void rejectsUnsafeSchemesPortsAndCredentials() {
        for (String uri : new String[] {"file:///etc/passwd", "ftp://provider.example/file",
            "http://provider.example:8080/oai", "https://provider.example:80/oai",
            "https://user:password@provider.example/oai", "https://provider.example/oai#fragment"}) {
            assertThrows(uri, IOException.class, () -> HarvestHttpClient.open(URI.create(uri), 10));
        }
    }

    @Test
    public void rejectsPrivateConnectionsBeforeSendingRequest() {
        for (String uri : new String[] {"http://127.0.0.1/", "http://[::1]/", "http://2130706433/"}) {
            assertThrows(IOException.class, () -> HarvestHttpClient.open(URI.create(uri), 10));
        }
    }
}

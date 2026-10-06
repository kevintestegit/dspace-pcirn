/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.harvest;

import java.io.IOException;
import java.io.InputStream;
import java.net.InetAddress;
import java.net.URI;
import java.net.UnknownHostException;

import org.apache.http.HttpException;
import org.apache.http.client.config.RequestConfig;
import org.apache.http.client.methods.CloseableHttpResponse;
import org.apache.http.client.methods.HttpGet;
import org.apache.http.conn.routing.HttpRoute;
import org.apache.http.impl.client.CloseableHttpClient;
import org.apache.http.impl.client.HttpClients;
import org.dspace.app.util.LimitedInputStream;

/**
 * HTTP transport for untrusted harvesting destinations. DNS validation is applied
 * to the addresses used by each connection, including redirect connections.
 */
public final class HarvestHttpClient {
    private HarvestHttpClient() { }

    /**
     * Fetch a public HTTP(S) resource using standard ports and bounded reads.
     * Proxies are deliberately excluded: remote proxy DNS would bypass this policy.
     * @param uri resource URI
     * @param maximumBytes maximum response size after decompression
     * @return stream owning its HTTP response and client
     * @throws IOException if the destination, response or transport is rejected
     */
    public static InputStream open(URI uri, long maximumBytes) throws IOException {
        return open(uri, maximumBytes, 0);
    }

    private static InputStream open(URI uri, long maximumBytes, int redirects) throws IOException {
        validateUri(uri);
        if (redirects > 5) {
            throw new IOException("Too many harvesting redirects");
        }
        CloseableHttpClient client = HttpClients.custom()
            .setDnsResolver(HarvestHttpClient::resolvePublicAddresses)
            .setRoutePlanner((target, request, context) -> {
                try {
                    validateUri(URI.create(target.toURI()));
                } catch (IOException | IllegalArgumentException e) {
                    throw new HttpException("Rejected harvesting destination", e);
                }
                return new HttpRoute(target, null, "https".equalsIgnoreCase(target.getSchemeName()));
            })
            .setDefaultRequestConfig(RequestConfig.custom().setConnectTimeout(10000)
                .setConnectionRequestTimeout(10000).setSocketTimeout(30000).setMaxRedirects(5).build())
            .disableAutomaticRetries()
            .disableRedirectHandling()
            .disableCookieManagement()
            .build();
        HttpGet request = new HttpGet(uri);
        try {
            CloseableHttpResponse response = client.execute(request);
            try {
                int status = response.getStatusLine().getStatusCode();
                if (status == 301 || status == 302 || status == 303 || status == 307 || status == 308) {
                    org.apache.http.Header location = response.getFirstHeader("Location");
                    if (location == null) {
                        throw new IOException("Harvesting redirect has no destination");
                    }
                    URI next = uri.resolve(location.getValue());
                    request.abort();
                    response.close();
                    client.close();
                    return open(next, maximumBytes, redirects + 1);
                }
                if (status < 200 || status >= 300 || response.getEntity() == null) {
                    throw new IOException("Harvesting HTTP response rejected: " + status);
                }
                return new LimitedInputStream(response.getEntity().getContent(), maximumBytes) {
                    @Override
                    public void close() throws IOException {
                        request.abort();
                        try (client; response) {
                            super.close();
                        }
                    }
                };
            } catch (IOException | RuntimeException e) {
                request.abort();
                response.close();
                throw e;
            }
        } catch (IOException | RuntimeException e) {
            request.abort();
            client.close();
            throw e;
        }
    }

    static void validateUri(URI uri) throws IOException {
        String scheme = uri.getScheme();
        int expectedPort = "https".equalsIgnoreCase(scheme) ? 443 : 80;
        if (!("http".equalsIgnoreCase(scheme) || "https".equalsIgnoreCase(scheme))
            || uri.getHost() == null || uri.getUserInfo() != null || uri.getFragment() != null
            || (uri.getPort() != -1 && uri.getPort() != expectedPort)) {
            throw new IOException("Only public HTTP(S) harvesting destinations on standard ports are permitted");
        }
    }

    static InetAddress[] resolvePublicAddresses(String host) throws UnknownHostException {
        InetAddress[] addresses = InetAddress.getAllByName(host);
        for (InetAddress address : addresses) {
            if (!isPublicAddress(address)) {
                throw new UnknownHostException("Non-public harvesting destination rejected");
            }
        }
        return addresses;
    }

    static boolean isPublicAddress(InetAddress address) {
        if (address.isAnyLocalAddress() || address.isLoopbackAddress() || address.isLinkLocalAddress()
            || address.isSiteLocalAddress() || address.isMulticastAddress()) {
            return false;
        }
        byte[] bytes = address.getAddress();
        int first = bytes[0] & 255;
        int second = bytes[1] & 255;
        if (bytes.length == 4) {
            int third = bytes[2] & 255;
            return first != 0 && first != 10 && first != 127 && first < 224
                && !(first == 100 && second >= 64 && second <= 127)
                && !(first == 169 && second == 254)
                && !(first == 172 && second >= 16 && second <= 31)
                && !(first == 192 && (second == 168 || (second == 0 && (third == 0 || third == 2))
                    || (second == 88 && third == 99)))
                && !(first == 198 && (second == 18 || second == 19 || (second == 51 && third == 100)))
                && !(first == 203 && second == 0 && third == 113);
        }
        return (first & 224) == 32
            && !(first == 32 && second == 1 && ((bytes[2] & 254) == 0
                || ((bytes[2] & 255) == 13 && (bytes[3] & 255) == 184)))
            && !(first == 32 && second == 2)
            && !(first == 63 && second == 255 && (bytes[2] & 240) == 0);
    }
}

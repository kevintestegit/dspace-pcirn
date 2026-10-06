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
import java.net.URISyntaxException;
import javax.xml.parsers.ParserConfigurationException;
import javax.xml.xpath.XPathConstants;
import javax.xml.xpath.XPathExpressionException;
import javax.xml.xpath.XPathFactory;

import org.apache.http.client.utils.URIBuilder;
import org.dspace.app.util.XMLUtils;
import org.w3c.dom.Document;
import org.w3c.dom.NodeList;
import org.xml.sax.SAXException;

/**
 * OAI-PMH response fetched through the harvesting transport and secure XML parser.
 */
public final class OaiResponse {
    private static final String OAI_NAMESPACE = "http://www.openarchives.org/OAI/2.0/";
    private final Document document;
    private final String requestUrl;

    private OaiResponse(Document document, String requestUrl) {
        this.document = document;
        this.requestUrl = requestUrl;
    }

    /**
     * Execute an OAI-PMH request.
     * @param source provider base URL
     * @param verb OAI-PMH verb
     * @param parameters alternating parameter names and values; null values are omitted
     * @return parsed response
     * @throws IOException if the destination or response is unsafe or unavailable
     * @throws ParserConfigurationException if XML protection is unavailable
     * @throws SAXException if XML is malformed or contains a DTD
     */
    public static OaiResponse request(String source, String verb, String... parameters)
        throws IOException, ParserConfigurationException, SAXException {
        try {
            URIBuilder uri = new URIBuilder(source);
            uri.setParameter("verb", verb);
            for (int i = 0; i < parameters.length; i += 2) {
                if (parameters[i + 1] != null) {
                    uri.setParameter(parameters[i], parameters[i + 1]);
                }
            }
            try (InputStream input = HarvestHttpClient.open(uri.build(), 16 * 1024 * 1024)) {
                javax.xml.parsers.DocumentBuilderFactory factory = XMLUtils.getDocumentBuilderFactory();
                factory.setNamespaceAware(true);
                javax.xml.parsers.DocumentBuilder builder = factory.newDocumentBuilder();
                return new OaiResponse(builder.parse(input), uri.toString());
            }
        } catch (URISyntaxException | IllegalArgumentException e) {
            throw new IOException("Invalid OAI provider URL", e);
        }
    }

    /** @return parsed OAI document */
    public Document getDocument() {
        return document;
    }

    /** @return OAI protocol errors */
    public NodeList getErrors() {
        return nodes("/*/*[local-name()='error' and namespace-uri()='" + OAI_NAMESPACE + "']");
    }

    /** @return request URL for operational diagnostics */
    public String getRequestURL() {
        return requestUrl;
    }

    /** @return pagination token, or null when the response is complete */
    public String getResumptionToken() {
        NodeList tokens = nodes("/*/*[local-name()='ListRecords' and namespace-uri()='" + OAI_NAMESPACE
            + "']/*[local-name()='resumptionToken' and namespace-uri()='" + OAI_NAMESPACE + "']");
        return tokens.getLength() == 0 ? null : tokens.item(0).getTextContent();
    }

    private NodeList nodes(String expression) {
        try {
            return (NodeList) XPathFactory.newInstance().newXPath().evaluate(expression, document,
                XPathConstants.NODESET);
        } catch (XPathExpressionException e) {
            throw new IllegalStateException("Invalid OAI response query", e);
        }
    }
}

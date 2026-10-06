/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.util;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertThrows;

import java.io.StringReader;

import org.junit.Test;
import org.xml.sax.InputSource;
import org.xml.sax.SAXException;
import org.xml.sax.helpers.DefaultHandler;

/** Tests for streaming XML import protection. */
public class SecureXmlParserTest {
    @Test
    public void rejectsExternalAndInternalEntities() throws Exception {
        for (String entity : new String[] {"SYSTEM 'file:///etc/passwd'", "SYSTEM 'http://127.0.0.1/'", "'expanded'"}) {
            String xml = "<!DOCTYPE PubmedArticle [<!ENTITY x " + entity + ">]>"
                + "<PubmedArticle>&x;</PubmedArticle>";
            assertThrows(SAXException.class, () -> XMLUtils.getSAXParser().parse(
                new InputSource(new StringReader(xml)), new DefaultHandler()));
        }
    }

    @Test
    public void preservesOrdinaryText() throws Exception {
        StringBuilder text = new StringBuilder();
        XMLUtils.getSAXParser().parse(new InputSource(new StringReader(
            "<!DOCTYPE PubmedArticle PUBLIC '-//NLM//DTD PubMed//EN' 'https://127.0.0.1/unreachable.dtd'>"
                + "<PubmedArticle>A &amp; B</PubmedArticle>")),
            new DefaultHandler() {
                @Override
                public void characters(char[] chars, int start, int length) {
                    text.append(chars, start, length);
                }
            });
        assertEquals("A & B", text.toString());
    }
}

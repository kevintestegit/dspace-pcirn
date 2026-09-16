/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.core;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.not;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;

import jakarta.mail.BodyPart;
import jakarta.mail.MessagingException;
import jakarta.mail.Multipart;
import jakarta.mail.internet.MimeMultipart;
import org.dspace.AbstractDSpaceTest;
import org.dspace.services.ConfigurationService;
import org.junit.Before;
import org.junit.Test;

/**
 * Tests for email sender.
 *
 * @author mwood
 */
public class EmailTest
        extends AbstractDSpaceTest {
    private ConfigurationService config;

    @Before
    public void init_test() {
        config = kernelImpl.getConfigurationService();
    }

    @Test
    public void testNullParameter()
            throws MessagingException, IOException {
        // Ensure that no mail goes out
        config.setProperty("mail.server.disabled", "true");

        Email email = new Email();
        email.setContent("null test",
                "Testing: parameter value is /${params[0]}/.");
        email.addArgument(null);
        email.build();
        String message = email.getMessage();
        assertThat("Null message parameter should be transformed to empty",
                message, not(containsString("(null)")));
    }

    @Test
    public void testNotNullParameter()
            throws MessagingException, IOException {
        // Ensure that no mail goes out
        config.setProperty("mail.server.disabled", "true");

        Email email = new Email();
        email.setContent("not-null test",
                "Testing: parameter value is /${params[0]}/.");
        String testParam = "axolotl";
        email.addArgument(testParam);
        email.build();
        String message = email.getMessage();
        assertThat("Null message parameter should be transformed to empty",
                message, containsString(testParam));
    }

    @Test
    public void buildCreatesHtmlAndPlainTextAlternatives()
            throws MessagingException, IOException {
        Email email = new Email();
        email.setContent("pcirn-test",
                "#set($emailTitle = 'Teste')\n"
                        + "#set($emailActionLabel = 'Abrir')\n"
                        + "#set($emailActionUrl = 'https://example.org/task')\n"
                        + "Conteúdo de teste.");
        email.addRecipient("recipient@example.org");
        email.build();

        assertThat("content type: " + email.message.getContentType(),
                email.message.isMimeType("multipart/alternative"), is(true));
        Multipart alternative = (Multipart) email.message.getContent();
        assertThat(alternative.getCount(), is(2));
        assertThat(alternative.getBodyPart(0).isMimeType("text/plain"), is(true));
        assertThat(alternative.getBodyPart(1).isMimeType("multipart/related"), is(true));

        Multipart related = (Multipart) alternative.getBodyPart(1).getContent();
        assertThat(related.getCount(), is(5));
        assertThat(((String) alternative.getBodyPart(0).getContent()),
                containsString("Conteúdo de teste."));
        assertThat(((String) related.getBodyPart(0).getContent()),
                containsString("Teste"));
        assertThat(((String) related.getBodyPart(0).getContent()),
                containsString("https://example.org/task"));
    }

    @Test
    public void buildKeepsUserAttachmentsOutsideRelatedPart()
            throws Exception {
        File attachment = File.createTempFile("pcirn-email", ".txt");
        try {
            Files.writeString(attachment.toPath(), "attachment");

            Email email = new Email();
            email.setContent("pcirn-attachment-test",
                    "#set($emailTitle = 'Teste')\nCorpo.");
            email.addRecipient("recipient@example.org");
            email.addAttachment(attachment, "test.txt");
            email.build();

            assertThat(email.message.isMimeType("multipart/mixed"), is(true));
            Multipart mixed = (Multipart) email.message.getContent();
            assertThat(mixed.getCount(), is(2));
            assertThat(mixed.getBodyPart(0).isMimeType("multipart/alternative"), is(true));
            Multipart alternative = (Multipart) mixed.getBodyPart(0).getContent();
            assertThat(alternative.getBodyPart(1).isMimeType("multipart/related"), is(true));
            assertThat(mixed.getBodyPart(1).getFileName(), equalTo("test.txt"));
            assertThat(((MimeMultipart) alternative.getBodyPart(1).getContent()).getCount(), is(5));
        } finally {
            Files.deleteIfExists(attachment.toPath());
        }
    }

    @Test
    public void buildRendersRealChangePasswordTemplateAsTextAndHtml()
            throws Exception {
        String token = "https://example.org/reset?token=pcirn-test";
        Path template = Paths.get(config.getProperty("dspace.dir"), "config", "emails",
                "change_password");

        Email email = Email.getEmail(template.toString());
        email.addRecipient("recipient@example.org");
        email.addArgument(token);
        email.build();

        Multipart alternative = (Multipart) email.message.getContent();
        assertThat(alternative.getBodyPart(0).isMimeType("text/plain"), is(true));
        assertThat((String) alternative.getBodyPart(0).getContent(), containsString(token));
        assertThat((String) alternative.getBodyPart(0).getContent(),
                containsString("If you need assistance"));

        BodyPart relatedPart = alternative.getBodyPart(1);
        assertThat(relatedPart.isMimeType("multipart/related"), is(true));
        Multipart related = (Multipart) relatedPart.getContent();
        String html = (String) related.getBodyPart(0).getContent();
        assertThat(html, containsString("<!doctype html>"));
        assertThat(html, containsString("cid:pcirn-footer-bg"));
        assertThat(related.getCount(), is(5));
    }
}

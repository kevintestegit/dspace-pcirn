/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.core;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.allOf;
import static org.hamcrest.Matchers.containsInAnyOrder;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.not;
import static org.junit.Assert.fail;

import java.io.IOException;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.Locale;
import java.util.stream.Collectors;

import org.junit.Test;

/**
 * Contract tests for the PCIRN email template renderer.
 */
public final class PcirnEmailTemplateRendererTest {
    private static final Path EMAIL_DIRECTORY = Paths.get(
            System.getProperty("user.dir"), "..", "dspace", "config", "emails")
            .toAbsolutePath().normalize();

    @Test
    public void rendersEscapedBodyAndAction()
            throws IOException {
        PcirnEmailTemplateRenderer renderer = new PcirnEmailTemplateRenderer(
                EMAIL_DIRECTORY);

        PcirnEmailTemplateRenderer.RenderedEmail rendered = renderer.render(
                "Primeiro <parágrafo> & linha\ncom quebra.\n\nSegundo parágrafo.",
                "Título <PCIRN> & público",
                "Abrir <item> & continuar",
                "https://pcirn.example/item?id=1&mode=\"full\"",
                "Prévia <ação> & necessária");

        assertThat(rendered.html(), allOf(
                containsString("<p>Primeiro &lt;parágrafo&gt; &amp; linha<br>com quebra.</p>"),
                containsString("<p>Segundo parágrafo.</p>"),
                containsString("Título &lt;PCIRN&gt; &amp; público"),
                containsString("Abrir &lt;item&gt; &amp; continuar"),
                containsString("Prévia &lt;ação&gt; &amp; necessária"),
                not(containsString("Título <PCIRN> & público")),
                not(containsString("Abrir <item> & continuar")),
                not(containsString("Prévia <ação> & necessária")),
                containsString(
                        "href=\"https://pcirn.example/item?id=1&amp;mode=&quot;full&quot;\""),
                containsString("cid:pcirn-dspace-logo"),
                containsString("cid:pcirn-policiacientifica"),
                containsString("cid:pcirn-estado-rn"),
                containsString("cid:pcirn-footer-bg"),
                not(containsString("Primeiro <parágrafo> & linha"))));
        assertThat(rendered.inlineResources(), hasSize(4));
        assertThat(rendered.inlineResources().stream()
                .map(PcirnEmailTemplateRenderer.InlineResource::contentId)
                .collect(Collectors.toList()), containsInAnyOrder(
                        "pcirn-dspace-logo",
                        "pcirn-policiacientifica",
                        "pcirn-estado-rn",
                        "pcirn-footer-bg"));
    }

    @Test
    public void rejectsNonHttpOrHttpsActionUrl() {
        assertRejectsInvalidActionUrl("javascript:alert(1)");
    }

    @Test
    public void acceptsHttpActionUrl()
            throws IOException {
        PcirnEmailTemplateRenderer.RenderedEmail rendered = renderWithActionUrl(
                "http://example.org/task");

        assertThat(rendered.html(), containsString(
                "href=\"http://example.org/task\""));
    }

    @Test
    public void acceptsHttpsActionUrl()
            throws IOException {
        PcirnEmailTemplateRenderer.RenderedEmail rendered = renderWithActionUrl(
                "https://example.org/task");

        assertThat(rendered.html(), containsString(
                "href=\"https://example.org/task\""));
    }

    @Test
    public void rejectsFtpActionUrl() {
        assertRejectsInvalidActionUrl("ftp://example.org/task");
    }

    @Test
    public void rejectsRelativeActionUrl() {
        assertRejectsInvalidActionUrl("/task");
    }

    @Test
    public void rejectsNetworkPathActionUrl() {
        assertRejectsInvalidActionUrl("//host/path");
    }

    @Test
    public void rejectsRelativeHttpActionUrl() {
        assertRejectsInvalidActionUrl("http:relative");
    }

    @Test
    public void rejectsMalformedActionUrl() {
        assertRejectsInvalidActionUrl("http://[malformed");
    }

    @Test
    public void rejectsEmptyActionUrl() {
        assertRejectsInvalidActionUrl("");
    }

    @Test
    public void rejectsNullActionUrl() {
        assertRejectsInvalidActionUrl(null);
    }

    private void assertRejectsInvalidActionUrl(String actionUrl) {
        try {
            renderWithActionUrl(actionUrl);
            fail("Expected invalid action URL to be rejected: " + actionUrl);
        } catch (IOException exception) {
            String exceptionDetails = exceptionMessages(exception);
            assertThat(exceptionDetails.toLowerCase(Locale.ROOT), containsString("url"));
            if (actionUrl != null && !actionUrl.isEmpty()) {
                assertThat(exceptionDetails, containsString(actionUrl));
            }
        }
    }

    private String exceptionMessages(Throwable exception) {
        StringBuilder messages = new StringBuilder();
        for (Throwable current = exception; current != null; current = current.getCause()) {
            messages.append(' ').append(current.getMessage());
        }
        return messages.toString();
    }

    private PcirnEmailTemplateRenderer.RenderedEmail renderWithActionUrl(
            String actionUrl)
            throws IOException {
        PcirnEmailTemplateRenderer renderer = new PcirnEmailTemplateRenderer(
                EMAIL_DIRECTORY);

        return renderer.render("Corpo", "Título", "Abrir", actionUrl, "Prévia");
    }
}

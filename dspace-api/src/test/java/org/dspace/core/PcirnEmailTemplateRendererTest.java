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
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.hasSize;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.not;
import static org.hamcrest.Matchers.notNullValue;
import static org.junit.Assert.fail;

import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.List;

import org.junit.Test;

/**
 * Contract tests for the PCIRN email template renderer.
 */
public final class PcirnEmailTemplateRendererTest {
    private static final Path EMAIL_DIRECTORY = resolveEmailDirectory();

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
                "Prévia <ação> & necessária", "NOTIFICAÇÃO DO REPOSITÓRIO", "");

        assertThat(rendered.html(), allOf(
                containsString("Primeiro &lt;parágrafo&gt; &amp; linha<br>com quebra.</p>"),
                containsString("Segundo parágrafo.</p>"),
                containsString("Título &lt;PCIRN&gt; &amp; público"),
                containsString("Abrir &lt;item&gt; &amp; continuar"),
                containsString("Prévia &lt;ação&gt; &amp; necessária"),
                not(containsString("Título <PCIRN> & público")),
                not(containsString("Abrir <item> & continuar")),
                not(containsString("Prévia <ação> & necessária")),
                containsString(
                        "href=\"https://pcirn.example/item?id=1&amp;mode=&quot;full&quot;\""),
                containsString(
                        "Se o botão não abrir, acesse: <a href=\"https://pcirn.example/"
                                + "item?id=1&amp;mode=&quot;full&quot;\""),
                containsString(
                        "https://pcirn.example/item?id=1&amp;mode=&quot;full&quot;</a>"),
                containsString("cid:pcirn-dspace-logo"),
                containsString("cid:pcirn-policiacientifica"),
                containsString("cid:pcirn-estado-rn"),
                containsString("alt=\"Brasão da Polícia Científica do Rio Grande do Norte\""),
                containsString("cid:pcirn-footer-building"),
                containsString("Repositório Institucional da PCIRN"),
                containsString("POLÍCIA CIENTÍFICA DO RIO GRANDE DO NORTE"),
                containsString("CIÊNCIA QUE IDENTIFICA.<br>INFORMAÇÃO QUE TRANSFORMA."),
                containsString("NOTIFICAÇÃO DO REPOSITÓRIO"),
                containsString("background-color:#edf4fb"),
                containsString("border-radius:12px"),
                containsString("background-color:#0869e8"),
                containsString("Se você não reconhece esta mensagem"),
                containsString("text-align:center;\">!</div>"),
                containsString("width=\"46\""),
                not(containsString("background-color:#041c34")),
                not(containsString("$email")),
                not(containsString("Primeiro <parágrafo> & linha"))));
        String escapedActionUrl = "https://pcirn.example/item?id=1&amp;mode=&quot;full&quot;";
        assertThat(countOccurrences(rendered.html(), "href=\"" + escapedActionUrl + "\""), is(2));
        assertThat(countOccurrences(rendered.html(), ">" + escapedActionUrl + "</a>"), is(1));
        assertThat(rendered.inlineResources(), hasSize(4));
        assertInlineResource(rendered.inlineResources(), "pcirn-dspace-logo",
                "dspace-logo-white.svg", "image/svg+xml");
        assertInlineResource(rendered.inlineResources(), "pcirn-policiacientifica",
                "brasao-policia-cientifica-rn.png", "image/png");
        assertInlineResource(rendered.inlineResources(), "pcirn-estado-rn",
                "brasao-estado-rn.png", "image/png");
        assertInlineResource(rendered.inlineResources(), "pcirn-footer-building",
                "desenho1.png", "image/png");
    }

    @Test
    public void groupsDetailsWithoutInterpretingHtmlOrLosingFreeText() throws IOException {
        PcirnEmailTemplateRenderer renderer = new PcirnEmailTemplateRenderer(EMAIL_DIRECTORY);
        String html = renderer.render(
                "Descrição.\n\nTítulo: <script> & documento\nColeção: Ciência\n"
                        + "Identificador: https://example.org/item?a=1&b=2\n\n"
                        + "Mensagem do usuário:\nNão é um campo.\n\nhttps://example.org/extra",
                "Título", "Revisar submissão", "https://example.org/task", "Prévia",
                "Submissões <PCIRN>", "Ajuda <equipe>").html();

        assertThat(html, allOf(
                containsString("<dl"), containsString("Título</dt>"),
                containsString("&lt;script&gt; &amp; documento</dd>"),
                containsString("Coleção</dt>"), containsString("Ciência</dd>"),
                containsString("https://example.org/item?a=1&amp;b=2</dd>"),
                containsString("Mensagem do usuário:<br>Não é um campo.</p>"),
                containsString("https://example.org/extra</p>"),
                containsString("Submissões &lt;PCIRN&gt;"),
                containsString("Ajuda &lt;equipe&gt;"),
                not(containsString("<script>"))));
        assertThat(countOccurrences(html, "<dl"), is(1));
        assertThat(html.indexOf("Revisar submissão") < html.indexOf("Ajuda &lt;equipe&gt;"), is(true));
        assertThat(html.indexOf("Ajuda &lt;equipe&gt;")
                < html.indexOf("Se você não reconhece esta mensagem"), is(true));
    }

    @Test
    public void rejectsNonHttpOrHttpsActionUrl()
            throws IOException {
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
    public void rejectsFtpActionUrl()
            throws IOException {
        assertRejectsInvalidActionUrl("ftp://example.org/task");
    }

    @Test
    public void rejectsRelativeActionUrl()
            throws IOException {
        assertRejectsInvalidActionUrl("/task");
    }

    @Test
    public void rejectsNetworkPathActionUrl()
            throws IOException {
        assertRejectsInvalidActionUrl("//host/path");
    }

    @Test
    public void rejectsRelativeHttpActionUrl()
            throws IOException {
        assertRejectsInvalidActionUrl("http:relative");
    }

    @Test
    public void rejectsMalformedActionUrl()
            throws IOException {
        assertRejectsInvalidActionUrl("http://[malformed");
    }

    @Test
    public void omitsActionWhenActionUrlIsNull()
            throws IOException {
        assertActionOmitted("Optional action with null URL", null);
    }

    @Test
    public void omitsActionWhenActionUrlIsEmpty()
            throws IOException {
        assertActionOmitted("Optional action with empty URL", "");
    }

    @Test
    public void omitsActionWhenActionUrlIsWhitespace()
            throws IOException {
        assertActionOmitted("Optional action with whitespace URL", "   ");
    }

    @Test
    public void omitsActionWhenActionLabelIsNull()
            throws IOException {
        assertActionOmitted(null, "https://example.org/optional-null-label");
    }

    @Test
    public void omitsActionWhenActionLabelIsEmpty()
            throws IOException {
        assertActionOmitted("", "https://example.org/optional-empty-label");
    }

    @Test
    public void omitsActionWhenActionLabelIsWhitespace()
            throws IOException {
        assertActionOmitted("   ", "https://example.org/optional-whitespace-label");
    }

    private void assertRejectsInvalidActionUrl(String actionUrl)
            throws IOException {
        PcirnEmailTemplateRenderer.RenderedEmail valid = renderWithActionUrl(
                "https://example.org/known-valid-action");
        assertThat(valid.html(), containsString(
                "href=\"https://example.org/known-valid-action\""));

        try {
            renderWithActionUrl(actionUrl);
            fail("Expected invalid action URL to be rejected: " + actionUrl);
        } catch (IOException expected) {
            // Expected: the valid render above rules out asset/template failures.
        }
    }

    private void assertActionOmitted(String actionLabel, String actionUrl)
            throws IOException {
        PcirnEmailTemplateRenderer.RenderedEmail rendered = render(
                actionLabel, actionUrl);

        if (actionLabel != null && !actionLabel.isBlank()) {
            assertThat(rendered.html(), not(containsString(actionLabel)));
        }
        if (actionUrl != null && !actionUrl.isBlank()) {
            assertThat(rendered.html(), not(containsString(actionUrl)));
        }
        assertThat(rendered.html(), not(containsString("href=\"")));
    }

    private void assertInlineResource(
            List<PcirnEmailTemplateRenderer.InlineResource> resources,
            String contentId, String fileName, String mimeType) {
        PcirnEmailTemplateRenderer.InlineResource resource = resources.stream()
                .filter(candidate -> contentId.equals(candidate.contentId()))
                .findFirst()
                .orElseThrow(() -> new AssertionError(
                        "Missing inline resource: " + contentId));

        File file = resource.file();
        assertThat(file, notNullValue());
        if (file != null) {
            assertThat(file.isFile(), is(true));
            assertThat(file.canRead(), is(true));
            assertThat(file.getName(), equalTo(fileName));
        }
        assertThat(resource.mimeType(), equalTo(mimeType));
    }

    private PcirnEmailTemplateRenderer.RenderedEmail render(
            String actionLabel, String actionUrl)
            throws IOException {
        PcirnEmailTemplateRenderer renderer = new PcirnEmailTemplateRenderer(
                EMAIL_DIRECTORY);

        return renderer.render("Corpo", "Título", actionLabel, actionUrl, "Prévia", "Categoria", "");
    }

    private PcirnEmailTemplateRenderer.RenderedEmail renderWithActionUrl(
            String actionUrl)
            throws IOException {
        return render("Abrir", actionUrl);
    }

    private int countOccurrences(String text, String value) {
        if (text == null || value == null || value.isEmpty()) {
            return 0;
        }
        int count = 0;
        int index = 0;
        while ((index = text.indexOf(value, index)) >= 0) {
            count++;
            index += value.length();
        }
        return count;
    }

    private static Path resolveEmailDirectory() {
        String dspaceDirectory = System.getProperty("dspace.dir");
        Path directory;
        if (dspaceDirectory != null && !dspaceDirectory.isBlank()) {
            directory = Paths.get(dspaceDirectory, "config", "emails");
        } else {
            Path moduleDirectory = Paths.get("..", "dspace", "config", "emails");
            directory = Files.isDirectory(moduleDirectory)
                    ? moduleDirectory
                    : Paths.get("dspace", "config", "emails");
        }
        if (!Files.isDirectory(directory)) {
            throw new AssertionError("Missing DSpace email directory: "
                    + directory.toAbsolutePath());
        }
        return directory.toAbsolutePath().normalize();
    }
}

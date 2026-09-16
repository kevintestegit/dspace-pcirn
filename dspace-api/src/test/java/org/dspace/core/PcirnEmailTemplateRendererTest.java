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

import java.io.IOException;
import java.nio.file.Paths;
import java.util.stream.Collectors;

import org.junit.Test;

/**
 * Contract tests for the PCIRN email template renderer.
 */
public final class PcirnEmailTemplateRendererTest {

    @Test
    public void rendersEscapedBodyAndAction()
            throws IOException {
        PcirnEmailTemplateRenderer renderer = new PcirnEmailTemplateRenderer(
                Paths.get("../dspace/config/emails"));

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

    @Test(expected = IOException.class)
    public void rejectsNonHttpOrHttpsActionUrl()
            throws IOException {
        PcirnEmailTemplateRenderer renderer = new PcirnEmailTemplateRenderer(
                Paths.get("../dspace/config/emails"));

        renderer.render("Corpo", "Título", "Abrir", "javascript:alert(1)",
                "Prévia");
    }
}

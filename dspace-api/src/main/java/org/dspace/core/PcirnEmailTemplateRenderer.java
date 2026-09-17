/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.core;

import java.io.File;
import java.io.IOException;
import java.net.MalformedURLException;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.util.List;
import java.util.regex.Matcher;
import java.util.regex.Pattern;
import java.util.stream.Collectors;

import org.apache.commons.text.StringEscapeUtils;

/**
 * Renders a merged DSpace email body in the shared PCIRN HTML shell.
 */
public final class PcirnEmailTemplateRenderer {

    private static final String LAYOUT_FILE = "pcirn-layout.html";

    private static final String ASSETS_DIRECTORY = "assets";

    private static final String DSPACE_LOGO = "dspace-logo-white.svg";

    private static final String POLICIA_CIENTIFICA = "brasao-policia-cientifica-rn.png";

    private static final String ESTADO_RN = "brasao-estado-rn.png";

    private static final String FOOTER_BACKGROUND = "footer-bg-pcirn.webp";

    private static final String FOOTER_BUILDING = "desenho1.png";

    private static final Pattern HTML_ENTITY = Pattern.compile(
            "&(?:#\\d+|#x[0-9a-fA-F]+|[A-Za-z][A-Za-z0-9]+);");

    /**
     * Describes an image embedded in the rendered email as an inline resource.
     *
     * @param contentId content ID referenced by the HTML
     * @param file asset file
     * @param mimeType asset MIME type
     */
    public record InlineResource(String contentId, File file, String mimeType) {
    }

    /**
     * Contains the rendered HTML and its inline image resources.
     *
     * @param html rendered HTML
     * @param inlineResources resources referenced by content ID
     */
    public record RenderedEmail(String html, List<InlineResource> inlineResources) {
    }

    private final Path emailDirectory;

    /**
     * Creates a renderer rooted at the DSpace email configuration directory.
     *
     * @param emailDirectory email configuration directory
     */
    public PcirnEmailTemplateRenderer(Path emailDirectory) {
        this.emailDirectory = emailDirectory;
    }

    /**
     * Renders the supplied text and presentation metadata in the PCIRN shell.
     *
     * @param bodyText merged plain-text email body
     * @param title email title
     * @param actionLabel optional CTA label
     * @param actionUrl optional CTA URL
     * @param preheader optional email preheader
     * @return rendered HTML and inline resources
     * @throws IOException if the shell or assets cannot be read, or the action
     *         URL is invalid
     */
    public RenderedEmail render(
            String bodyText,
            String title,
            String actionLabel,
            String actionUrl,
            String preheader) throws IOException {
        String layout = Files.readString(
                emailDirectory.resolve(LAYOUT_FILE), StandardCharsets.UTF_8);
        String escapedActionLabel = escape(actionLabel);
        String escapedActionUrl = escapeActionUrl(actionLabel, actionUrl);
        String actionBlock = "";
        if (!isBlank(actionLabel) && !isBlank(actionUrl)) {
            actionBlock = renderActionBlock(escapedActionLabel, escapedActionUrl);
        }

        String html = layout
                .replace("$emailPreheader", escape(preheader))
                .replace("$emailTitle", escape(title))
                .replace("$emailActionBlock", actionBlock)
                .replace("$emailBodyHtml", renderBody(bodyText));

        return new RenderedEmail(html, List.of(
                inlineResource("pcirn-dspace-logo", DSPACE_LOGO, "image/svg+xml"),
                inlineResource("pcirn-policiacientifica", POLICIA_CIENTIFICA, "image/png"),
                inlineResource("pcirn-estado-rn", ESTADO_RN, "image/png"),
                inlineResource("pcirn-footer-bg", FOOTER_BACKGROUND, "image/webp"),
                inlineResource("pcirn-footer-building", FOOTER_BUILDING, "image/png")));
    }

    private String renderBody(String bodyText) {
        String normalized = value(bodyText).replace("\r\n", "\n").replace('\r', '\n');
        return java.util.Arrays.stream(normalized.split("\\n\\s*\\n", -1))
                .map(paragraph -> "<p>" + escape(paragraph).replace("\n", "<br>") + "</p>")
                .collect(Collectors.joining("\n"));
    }

    private String renderActionBlock(String actionLabel, String actionUrl) {
        return "<table role=\"presentation\" width=\"100%\" cellpadding=\"0\" "
                + "cellspacing=\"0\" border=\"0\" style=\"margin:28px auto 0;\">"
                + "<tr><td align=\"center\" style=\"padding:0 0 16px;\">"
                + "<a href=\"" + actionUrl + "\" style=\"display:inline-block; "
                + "padding:16px 34px; background-color:#1d72f3; color:#ffffff; "
                + "font-size:17px; line-height:22px; font-weight:bold; text-decoration:none; "
                + "border-radius:999px;\">"
                + actionLabel + " &nbsp;&#8599;</a></td></tr>"
                + "<tr><td align=\"center\" style=\"font-size:12px; line-height:19px; color:#b9d2ed;\">"
                + "Se o botão não abrir, acesse: <a href=\"" + actionUrl
                + "\" style=\"color:#6db1ff; word-break:break-all;\">"
                + actionUrl + "</a></td></tr></table>";
    }

    private String escapeActionUrl(String actionLabel, String actionUrl) throws IOException {
        if (isBlank(actionLabel) || isBlank(actionUrl)) {
            return "";
        }
        try {
            URL url = new URL(actionUrl);
            String protocol = url.getProtocol();
            if (url.getHost().isBlank()
                    || !("http".equalsIgnoreCase(protocol) || "https".equalsIgnoreCase(protocol))) {
                throw new IOException("Action URL must be an absolute http or https URL");
            }
        } catch (MalformedURLException e) {
            throw new IOException("Action URL must be an absolute http or https URL", e);
        }
        return escape(actionUrl);
    }

    private InlineResource inlineResource(String contentId, String fileName, String mimeType)
            throws IOException {
        File file = emailDirectory.resolve(ASSETS_DIRECTORY).resolve(fileName).toFile();
        if (!file.isFile() || !file.canRead()) {
            throw new IOException("Unable to read PCIRN email asset: " + file);
        }
        return new InlineResource(contentId, file, mimeType);
    }

    private String escape(String value) {
        String escaped = StringEscapeUtils.escapeHtml4(value(value));
        Matcher matcher = HTML_ENTITY.matcher(escaped);
        StringBuilder result = new StringBuilder(escaped.length());
        int position = 0;
        while (matcher.find()) {
            result.append(escaped, position, matcher.start());
            String entity = matcher.group();
            result.append(isStructuralEntity(entity)
                    ? entity : StringEscapeUtils.unescapeHtml4(entity));
            position = matcher.end();
        }
        return result.append(escaped, position, escaped.length()).toString();
    }

    private boolean isStructuralEntity(String entity) {
        return "&amp;".equals(entity) || "&lt;".equals(entity)
                || "&gt;".equals(entity) || "&quot;".equals(entity)
                || "&#39;".equals(entity) || "&apos;".equals(entity);
    }

    private String value(String value) {
        return value == null ? "" : value;
    }

    private boolean isBlank(String value) {
        return value == null || value.isBlank();
    }
}

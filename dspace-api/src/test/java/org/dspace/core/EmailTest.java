/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.core;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.arrayContaining;
import static org.hamcrest.Matchers.containsString;
import static org.hamcrest.Matchers.equalTo;
import static org.hamcrest.Matchers.is;
import static org.hamcrest.Matchers.not;

import java.io.ByteArrayInputStream;
import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.IOException;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.LinkedHashMap;
import java.util.Map;
import java.util.Set;
import java.util.TreeSet;
import java.util.stream.Collectors;

import jakarta.mail.BodyPart;
import jakarta.mail.MessagingException;
import jakarta.mail.Multipart;
import jakarta.mail.Session;
import jakarta.mail.internet.MimeMessage;
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
        assertThat(related.getCount(), is(6));
        assertThat(((String) alternative.getBodyPart(0).getContent()),
                containsString("Conteúdo de teste."));
        assertThat(((String) related.getBodyPart(0).getContent()),
                containsString("Teste"));
        assertThat(((String) related.getBodyPart(0).getContent()),
                containsString("https://example.org/task"));
    }

    @Test
    public void buildAddsPlainTextActionFallback()
            throws Exception {
        Email email = new Email();
        email.setContent("pcirn-action-fallback-test",
                "#set($emailTitle = 'Teste')\n"
                        + "#set($emailActionLabel = 'Abrir')\n"
                        + "#set($emailActionUrl = 'https://example.org/task')\n"
                        + "Conteúdo sem URL visível.");
        email.addRecipient("recipient@example.org");
        email.build();

        Multipart alternative = (Multipart) email.message.getContent();
        String plainText = (String) alternative.getBodyPart(0).getContent();
        Multipart related = (Multipart) alternative.getBodyPart(1).getContent();
        String html = (String) related.getBodyPart(0).getContent();

        assertThat(plainText, containsString("Abrir: https://example.org/task"));
        assertThat(html, containsString(">Abrir &nbsp;&#8599;</a>"));
        assertThat(html, containsString("href=\"https://example.org/task\""));
        assertThat(countOccurrences(html, ">https://example.org/task</a>"), is(1));
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
            assertThat(((MimeMultipart) alternative.getBodyPart(1).getContent()).getCount(), is(6));
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
        String plainText = (String) alternative.getBodyPart(0).getContent();
        assertThat(plainText, containsString(token));
        assertThat(plainText,
                containsString("Se você não solicitou"));

        BodyPart relatedPart = alternative.getBodyPart(1);
        assertThat(relatedPart.isMimeType("multipart/related"), is(true));
        Multipart related = (Multipart) relatedPart.getContent();
        String html = (String) related.getBodyPart(0).getContent();
        assertThat(html, containsString("<!doctype html>"));
        assertThat(html, containsString("Cadastre sua senha"));
        assertThat(html, containsString("Cadastrar minha senha"));
        assertThat(html, containsString("href=\"" + token + "\""));
        assertThat(countOccurrences(html, ">" + token + "</a>"), is(1));
        String htmlWithoutAnchors = html.replaceAll("(?is)<a\\b[^>]*>.*?</a>", "");
        assertThat(htmlWithoutAnchors, not(containsString(token)));
        assertThat(html, containsString("cid:pcirn-footer-bg"));
        assertThat(html, containsString("cid:pcirn-footer-building"));
        assertThat(related.getCount(), is(6));
        assertInlinePart(related.getBodyPart(1), "pcirn-dspace-logo",
                "dspace-logo-white.svg", "image/svg+xml");
        assertInlinePart(related.getBodyPart(2), "pcirn-policiacientifica",
                "brasao-policia-cientifica-rn.png", "image/png");
        assertInlinePart(related.getBodyPart(3), "pcirn-estado-rn",
                "brasao-estado-rn.png", "image/png");
        assertInlinePart(related.getBodyPart(4), "pcirn-footer-bg",
                "footer-bg-pcirn.webp", "image/webp");
        assertInlinePart(related.getBodyPart(5), "pcirn-footer-building",
                "desenho1.png", "image/png");

        ByteArrayOutputStream serialized = new ByteArrayOutputStream();
        email.message.writeTo(serialized);
        MimeMessage reloaded = new MimeMessage((Session) null,
                new ByteArrayInputStream(serialized.toByteArray()));
        Multipart reloadedAlternative = (Multipart) reloaded.getContent();
        Multipart reloadedRelated = (Multipart) reloadedAlternative.getBodyPart(1).getContent();
        assertThat((String) reloadedRelated.getBodyPart(0).getContent(),
                containsString("você"));
    }

    @Test
    public void buildRendersEveryConfiguredEmailTemplate()
            throws Exception {
        config.setProperty("mail.server.disabled", "true");
        Path emailDirectory = Paths.get(config.getProperty("dspace.dir"), "config", "emails");
        Map<String, TemplateFixture> fixtures = templateFixtures();

        Set<String> configuredTemplates;
        try (var paths = Files.list(emailDirectory)) {
            configuredTemplates = paths.filter(Files::isRegularFile)
                    .map(path -> path.getFileName().toString())
                    .filter(name -> !name.equals("pcirn-layout.html"))
                    .collect(Collectors.toCollection(TreeSet::new));
        }
        assertThat(fixtures.keySet(), equalTo(configuredTemplates));

        for (Map.Entry<String, TemplateFixture> entry : fixtures.entrySet()) {
            TemplateFixture fixture = entry.getValue();
            Email email = Email.getEmail(emailDirectory.resolve(entry.getKey()).toString());
            for (Object argument : fixture.arguments()) {
                email.addArgument(argument);
            }
            email.addRecipient("recipient@example.org");
            email.build();

            Multipart alternative = (Multipart) email.message.getContent();
            String plainText = (String) alternative.getBodyPart(0).getContent();
            Multipart related = (Multipart) alternative.getBodyPart(1).getContent();
            String html = (String) related.getBodyPart(0).getContent();

            assertThat(html, containsString("<!doctype html>"));
            assertThat(html, containsString(fixture.title()));
            assertThat(plainText, containsString(fixture.bodyMarker()));
            for (String literal : new String[] {
                "$emailTitle", "$emailActionLabel", "$emailActionUrl", "$emailPreheader", "#set("
            }) {
                assertThat(plainText, not(containsString(literal)));
                assertThat(html, not(containsString(literal)));
            }
        }
    }

    private Map<String, TemplateFixture> templateFixtures() {
        Map<String, TemplateFixture> fixtures = new LinkedHashMap<>();
        fixtures.put("batch_import_error", fixture("Falha na importação em lote",
                "falha no lote", "falha no lote", "https://example.org/feedback"));
        fixtures.put("batch_import_success", fixture("Importação em lote concluída",
                "completed successfully", "/tmp/mapfile"));
        fixtures.put("change_password", fixture("Cadastre sua senha",
                "Recebemos uma solicitação", "https://example.org/reset?token=pcirn-test"));
        fixtures.put("coar_notify_accepted", fixture("Revisão aceita pelo serviço",
                "Item aceito", "Serviço LDN", "Item aceito", "https://example.org/service",
                "https://example.org/item", "Nome do submetente", "2026-09-16"));
        fixtures.put("coar_notify_endorsed", fixture("Item endossado pelo serviço",
                "Item endossado", "Serviço LDN", "Item endossado", "https://example.org/service",
                "https://example.org/item", "Nome do submetente", "2026-09-16"));
        fixtures.put("coar_notify_rejected", fixture("Solicitação de revisão recusada",
                "Item recusado", "Serviço LDN", "Item recusado", "https://example.org/service",
                "https://example.org/item", "Nome do submetente", "2026-09-16"));
        fixtures.put("coar_notify_rejected_resubmission", fixture("Revisões necessárias na submissão",
                "Item com revisão", "Serviço LDN", "Item com revisão", "https://example.org/service",
                "https://example.org/item", "Nome do submetente", "2026-09-16"));
        fixtures.put("coar_notify_relationship", fixture("Novo relacionamento de recurso",
                "Item relacionado", "Serviço LDN", "Item relacionado", "https://example.org/service",
                "https://example.org/item", "Nome do submetente",
                new RelationshipNotification("https://example.org/related"), "Item relacionado"));
        fixtures.put("coar_notify_reviewed", fixture("Item revisado pelo serviço",
                "Item revisado", "Serviço LDN", "Item revisado", "https://example.org/service",
                "https://example.org/item", "Nome do submetente", "2026-09-16"));
        fixtures.put("doi_maintenance_error", fixture("Falha na manutenção do DOI",
                "atualização", "atualização", "2026-09-16", "item", "123", "10.1234/example",
                "falha"));
        fixtures.put("export_error", fixture("Falha na exportação",
                "falha na exportação", "falha na exportação", "https://example.org/feedback"));
        fixtures.put("export_success", fixture("Exportação pronta para download",
                "ready for download", "https://example.org/export", "24"));
        fixtures.put("feedback", fixture("Feedback recebido", "comentário do usuário",
                "2026-09-16", "user@example.org", "usuário", "https://example.org/page",
                "Mozilla", "session", "comentário do usuário"));
        fixtures.put("flowtask_notify", fixture("Relatório de tarefa de curadoria",
                "Título da submissão", "Título da submissão", "Coleção", "Nome do submetente",
                "curadoria", "resultado", "ação"));
        fixtures.put("harvesting_error", fixture("Falha na coleta", "coleção-1",
                "coleção-1", "2026-09-16", "FAILED", "mensagem de erro", "pilha de erro"));
        fixtures.put("healthcheck", fixture("Verificação do repositório concluída",
                "saída do healthcheck", "saída do healthcheck"));
        fixtures.put("internal_error", fixture("Erro interno do repositório",
                "https://example.org/server", "https://example.org/server", "2026-09-16", "sessão",
                "https://example.org/error", "pilha de erro", "usuário", "127.0.0.1"));
        fixtures.put("orcid", fixture("Conclua seu cadastro com ORCID",
                "To complete registration", "https://example.org/orcid"));
        fixtures.put("qaevent_admin_notification", fixture("Nova solicitação administrativa",
                "topic", "topic", "123", "motivo"));
        fixtures.put("register", fixture("Confirme seu cadastro", "To complete registration",
                "https://example.org/register?token=pcirn-test"));
        fixtures.put("registration_notify", fixture("Novo cadastro no repositório",
                "novo usuário", "novo usuário", "https://example.org", "Nome", "user@example.org",
                "2026-09-16"));
        fixtures.put("request_item.admin", fixture("Solicitação de acesso aberto",
                "admin", "admin", "https://example.org/item", "token", "Nome do aprovador",
                "approver@example.org"));
        fixtures.put("request_item.author", fixture("Solicitação de cópia de documento",
                "Dear", "Nome do solicitante", "requester@example.org", "arquivo", "123/abc",
                "Título do documento", "mensagem", "https://example.org/request", "Autor",
                "author@example.org", "Repositório", "help@example.org"));
        fixtures.put("request_item.granted", fixture("Solicitação de cópia aprovada",
                "Dear", "Solicitante", "https://example.org/item", "Título", "Concedente",
                "grantor@example.org", "mensagem adicional"));
        fixtures.put("request_item.granted_token", fixture("Acesso seguro concedido",
                "Dear", "Solicitante", "https://example.org/item", "Título", "Concedente",
                "grantor@example.org", "mensagem adicional", "https://example.org/token",
                "2026-09-30"));
        fixtures.put("request_item.rejected", fixture("Solicitação de cópia recusada",
                "Dear", "Solicitante", "https://example.org/item", "Título", "Concedente",
                "grantor@example.org", "mensagem adicional"));
        fixtures.put("submit_archive", fixture("Submissão aprovada e arquivada",
                "You submitted", "Título da submissão", "Coleção", "123/abc"));
        fixtures.put("submit_reject", fixture("Sua submissão precisa de atenção",
                "You submitted", "Título da submissão", "Coleção", "Revisor", "motivo",
                "https://example.org/my-dspace"));
        fixtures.put("submit_task", fixture("Você tem uma nova tarefa", "A new item has been submitted",
                "Título da submissão", "Coleção", "Nome do submetente", "descrição",
                "https://example.org/my-dspace"));
        fixtures.put("subscriptions_content", fixture("Atualizações das suas inscrições",
                "escolhidas", "escolhidas", "novos itens", "itens modificados"));
        fixtures.put("validation_orcid", fixture("Confirme seu e-mail ORCID",
                "To confirm your email", "https://example.org/validation"));
        fixtures.put("welcome", fixture("Bem-vindo ao repositório",
                "Thank you for registering an account."));
        return fixtures;
    }

    private TemplateFixture fixture(String title, String bodyMarker, Object... arguments) {
        return new TemplateFixture(title, bodyMarker, arguments);
    }

    private record TemplateFixture(String title, String bodyMarker, Object[] arguments) {
    }

    public static final class RelationshipNotification {
        private final RelationshipObject object;

        public RelationshipNotification(String subject) {
            object = new RelationshipObject(subject);
        }

        public RelationshipObject getObject() {
            return object;
        }
    }

    public static final class RelationshipObject {
        private final String subject;

        public RelationshipObject(String subject) {
            this.subject = subject;
        }

        public String getSubject() {
            return subject;
        }
    }

    private void assertInlinePart(BodyPart part, String contentId, String fileName,
                                  String mimeType) throws MessagingException {
        assertThat(part.getFileName(), equalTo(fileName));
        assertThat(part.getHeader("Content-ID"),
                arrayContaining("<" + contentId + ">"));
        assertThat(part.isMimeType(mimeType), is(true));
        assertThat(part.getDisposition(), equalTo(BodyPart.INLINE));
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
}

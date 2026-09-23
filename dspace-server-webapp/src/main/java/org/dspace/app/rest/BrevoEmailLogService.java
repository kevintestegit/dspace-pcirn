/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.rest;

import static org.springframework.http.HttpStatus.BAD_GATEWAY;
import static org.springframework.http.HttpStatus.BAD_REQUEST;
import static org.springframework.http.HttpStatus.NOT_FOUND;
import static org.springframework.http.HttpStatus.SERVICE_UNAVAILABLE;
import java.net.URI;
import java.util.List;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ObjectNode;
import org.apache.commons.lang3.StringUtils;
import org.dspace.services.ConfigurationService;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.boot.web.client.RestTemplateBuilder;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpHeaders;
import org.springframework.http.HttpMethod;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Component;
import org.springframework.web.client.RestClientException;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.server.ResponseStatusException;
import org.springframework.web.util.UriComponentsBuilder;

/**
 * Reads transactional email events and content from Brevo without storing them in DSpace.
 */
@Component
public class BrevoEmailLogService {

    private static final String API_BASE_URL = "https://api.brevo.com/v3/smtp";

    private final ObjectMapper objectMapper = new ObjectMapper();
    private final String apiKey;
    private final String senderEmail;
    private final RestTemplate restTemplate;

    @Autowired
    public BrevoEmailLogService(@Value("${BREVO_API_KEY:}") String apiKey,
                                ConfigurationService configurationService,
                                RestTemplateBuilder restTemplateBuilder) {
        this(apiKey, configurationService.getProperty("mail.from.address"), restTemplateBuilder.build());
    }

    BrevoEmailLogService(String apiKey, RestTemplate restTemplate) {
        this(apiKey, "", restTemplate);
    }

    BrevoEmailLogService(String apiKey, String senderEmail, RestTemplate restTemplate) {
        this.apiKey = apiKey;
        this.senderEmail = senderEmail;
        this.restTemplate = restTemplate;
    }

    /**
     * Retrieves a page of transactional email events from the preceding number of days.
     *
     * @param days number of days to include, from 1 to 90
     * @param limit maximum number of events to return, from 1 to 5000
     * @param offset first event index to return
     * @return Brevo event report
     */
    public JsonNode getEvents(int days, int limit, int offset) {
        if (days < 1 || days > 90 || limit < 1 || limit > 5000 || offset < 0) {
            throw new ResponseStatusException(BAD_REQUEST, "Invalid Brevo email event range or pagination");
        }
        URI uri = UriComponentsBuilder.fromHttpUrl(API_BASE_URL + "/statistics/events")
            .queryParam("days", days)
            .queryParam("limit", limit)
            .queryParam("offset", offset)
            .queryParam("sort", "desc")
            .build()
            .toUri();
        return get(uri);
    }

    /**
     * Retrieves the personalized content and event timeline for a message.
     *
     * @param messageId Brevo message identifier from an event
     * @return Brevo email details
     */
    public JsonNode getEmailContent(String messageId) {
        if (StringUtils.isBlank(messageId)) {
            throw new ResponseStatusException(BAD_REQUEST, "messageId is required");
        }
        URI listUri = UriComponentsBuilder.fromHttpUrl(API_BASE_URL + "/emails")
            .queryParam("messageId", messageId)
            .build()
            .encode()
            .toUri();
        JsonNode emailList = get(listUri);
        JsonNode email = emailList.path("transactionalEmails").path(0);
        String uuid = email.path("uuid").asText();
        if (StringUtils.isBlank(uuid)) {
            throw new ResponseStatusException(NOT_FOUND, "Brevo email not found");
        }
        URI contentUri = UriComponentsBuilder.fromHttpUrl(API_BASE_URL + "/emails/{uuid}")
            .buildAndExpand(uuid)
            .encode()
            .toUri();
        return get(contentUri);
    }

    /**
     * Sends a new email using the rendered content of an existing Brevo message.
     *
     * @param messageId Brevo message identifier from an event
     * @return Brevo send response
     */
    public JsonNode resendEmail(String messageId) {
        JsonNode original = getEmailContent(messageId);
        String recipient = original.path("email").asText();
        String subject = original.path("subject").asText();
        String body = original.path("body").asText();
        if (StringUtils.isBlank(recipient) || StringUtils.isBlank(subject) || StringUtils.isBlank(body)) {
            throw new ResponseStatusException(BAD_REQUEST, "Brevo email content is incomplete and cannot be resent");
        }
        if (original.path("attachmentCount").asInt(0) > 0) {
            throw new ResponseStatusException(BAD_REQUEST, "Brevo email with attachments cannot be resent from this page");
        }
        if (StringUtils.isBlank(senderEmail)) {
            throw new ResponseStatusException(SERVICE_UNAVAILABLE, "DSpace mail.from.address is not configured");
        }

        ObjectNode payload = objectMapper.createObjectNode()
            .put("subject", subject)
            .put("htmlContent", body);
        payload.set("sender", objectMapper.createObjectNode().put("email", senderEmail));
        payload.set("to", objectMapper.createArrayNode().add(objectMapper.createObjectNode().put("email", recipient)));

        return post(URI.create(API_BASE_URL + "/email"), payload);
    }

    private JsonNode get(URI uri) {
        return exchange(uri, HttpMethod.GET, null);
    }

    private JsonNode post(URI uri, JsonNode body) {
        return exchange(uri, HttpMethod.POST, body);
    }

    private JsonNode exchange(URI uri, HttpMethod method, JsonNode body) {
        if (StringUtils.isBlank(apiKey)) {
            throw new ResponseStatusException(SERVICE_UNAVAILABLE, "Brevo API key is not configured");
        }
        HttpHeaders headers = new HttpHeaders();
        headers.set("api-key", apiKey);
        headers.setAccept(List.of(MediaType.APPLICATION_JSON));
        headers.setContentType(MediaType.APPLICATION_JSON);
        try {
            ResponseEntity<JsonNode> response = restTemplate.exchange(
                uri, method, new HttpEntity<>(body, headers), JsonNode.class);
            if (response.getBody() == null) {
                throw new ResponseStatusException(BAD_GATEWAY, "Brevo returned an empty response");
            }
            return response.getBody();
        } catch (RestClientException e) {
            throw new ResponseStatusException(BAD_GATEWAY, "Brevo email operation failed", e);
        }
    }
}

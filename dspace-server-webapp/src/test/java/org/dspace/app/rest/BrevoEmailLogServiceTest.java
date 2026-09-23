/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.rest;

import static org.junit.Assert.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.when;

import java.net.URI;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.junit.Before;
import org.junit.Test;
import org.mockito.Mock;
import org.mockito.MockitoAnnotations;
import org.springframework.http.HttpEntity;
import org.springframework.http.HttpMethod;
import org.springframework.http.ResponseEntity;
import org.springframework.web.client.RestTemplate;

public class BrevoEmailLogServiceTest {

    private final ObjectMapper objectMapper = new ObjectMapper();

    @Mock
    private RestTemplate restTemplate;

    private BrevoEmailLogService service;

    @Before
    public void setUp() {
        MockitoAnnotations.openMocks(this);
        service = new BrevoEmailLogService("test-key", restTemplate);
    }

    @Test
    public void getEventsShouldRequestBrevoEventsWithinConfiguredRange() throws Exception {
        JsonNode expected = objectMapper.readTree("{\"events\":[{\"event\":\"delivered\"}]}");
        when(restTemplate.exchange(any(URI.class), eq(HttpMethod.GET), any(HttpEntity.class), eq(JsonNode.class)))
            .thenReturn(ResponseEntity.ok(expected));

        JsonNode actual = service.getEvents(12, 50, 10);

        assertEquals(expected, actual);
    }

    @Test
    public void getEmailContentShouldResolveMessageIdToUuid() throws Exception {
        JsonNode emailList = objectMapper.readTree("{\"transactionalEmails\":[{\"uuid\":\"email-uuid\"}]}");
        JsonNode expected = objectMapper.readTree("{\"subject\":\"Bem-vindo\",\"body\":\"<p>Olá</p>\"}");
        when(restTemplate.exchange(any(URI.class), eq(HttpMethod.GET), any(HttpEntity.class), eq(JsonNode.class)))
            .thenReturn(ResponseEntity.ok(emailList), ResponseEntity.ok(expected));

        JsonNode actual = service.getEmailContent("<message@example.org>");

        assertEquals(expected, actual);
    }
}

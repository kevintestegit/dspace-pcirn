/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.rest;

import com.fasterxml.jackson.databind.JsonNode;
import org.springframework.http.CacheControl;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

/**
 * Administrative access to transactional email logs held by Brevo.
 */
@RestController
@RequestMapping("/api/admin/email-logs")
public class BrevoEmailLogRestController {

    private final BrevoEmailLogService brevoEmailLogService;

    public BrevoEmailLogRestController(BrevoEmailLogService brevoEmailLogService) {
        this.brevoEmailLogService = brevoEmailLogService;
    }

    /**
     * Retrieves paginated transactional email events.
     *
     * @param days number of days to include, from 1 to 90
     * @param limit maximum number of events to return
     * @param offset first event index to return
     * @return Brevo event report
     */
    @GetMapping("/events")
    @PreAuthorize("hasAuthority('ADMIN')")
    public ResponseEntity<JsonNode> getEvents(@RequestParam(defaultValue = "30") int days,
                                              @RequestParam(defaultValue = "100") int limit,
                                              @RequestParam(defaultValue = "0") int offset) {
        return ResponseEntity.ok()
            .cacheControl(CacheControl.noStore())
            .body(brevoEmailLogService.getEvents(days, limit, offset));
    }

    /**
     * Retrieves the content and event history for one message.
     *
     * @param messageId message identifier returned in an event
     * @return sent email content and its event timeline
     */
    @GetMapping("/content")
    @PreAuthorize("hasAuthority('ADMIN')")
    public ResponseEntity<JsonNode> getEmailContent(@RequestParam String messageId) {
        return ResponseEntity.ok()
            .cacheControl(CacheControl.noStore())
            .body(brevoEmailLogService.getEmailContent(messageId));
    }

    /**
     * Sends a new copy of a message using its rendered content from Brevo.
     *
     * @param messageId message identifier returned in an event
     * @return Brevo send response
     */
    @PostMapping("/resend")
    @PreAuthorize("hasAuthority('ADMIN')")
    public ResponseEntity<JsonNode> resendEmail(@RequestParam String messageId) {
        return ResponseEntity.ok()
            .cacheControl(CacheControl.noStore())
            .body(brevoEmailLogService.resendEmail(messageId));
    }
}

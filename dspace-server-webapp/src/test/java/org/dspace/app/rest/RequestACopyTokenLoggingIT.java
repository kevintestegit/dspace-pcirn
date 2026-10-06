/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.rest;

import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.when;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.io.ByteArrayInputStream;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;

import org.apache.logging.log4j.Level;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.core.Appender;
import org.apache.logging.log4j.core.LogEvent;
import org.apache.logging.log4j.core.Logger;
import org.dspace.app.requestitem.RequestItem;
import org.dspace.app.rest.test.AbstractControllerIntegrationTest;
import org.dspace.builder.BitstreamBuilder;
import org.dspace.builder.CollectionBuilder;
import org.dspace.builder.CommunityBuilder;
import org.dspace.builder.ItemBuilder;
import org.dspace.builder.RequestItemBuilder;
import org.dspace.content.Bitstream;
import org.dspace.content.Collection;
import org.dspace.content.Community;
import org.dspace.content.Item;
import org.dspace.services.ConfigurationService;
import org.junit.Test;
import org.springframework.beans.factory.annotation.Autowired;

/** Verify that a working request-a-copy download never logs its bearer token. */
public class RequestACopyTokenLoggingIT extends AbstractControllerIntegrationTest {
    @Autowired
    private ConfigurationService configurationService;

    @Test
    public void debugDownloadLogsNoToken() throws Exception {
        configurationService.setProperty("request.item.type", "all");
        context.turnOffAuthorisationSystem();
        Community community = CommunityBuilder.createCommunity(context).build();
        Collection collection = CollectionBuilder.createCollection(context, community).build();
        Item item = ItemBuilder.createItem(context, collection).build();
        Bitstream bitstream = BitstreamBuilder.createBitstream(context, item,
            new ByteArrayInputStream(new byte[] {1, 2, 3})).build();
        RequestItem request = RequestItemBuilder.createRequestItem(context, item, bitstream)
            .withAccessToken("log-test-bearer-secret").withAcceptRequest(true)
            .withDecisionDate(Instant.now()).withAccessExpiry(Instant.now().plusSeconds(3600)).build();
        context.restoreAuthSystemState();
        List<String> messages = new ArrayList<>();
        Appender appender = mock(Appender.class);
        when(appender.getName()).thenReturn("TokenLogTest");
        when(appender.isStarted()).thenReturn(true);
        doAnswer(invocation -> {
            messages.add(((LogEvent) invocation.getArgument(0)).getMessage().getFormattedMessage());
            return null;
        }).when(appender).append(any(LogEvent.class));
        Logger logger = (Logger) LogManager.getLogger(BitstreamRestController.class);
        Level level = logger.getLevel();
        logger.addAppender(appender);
        logger.setLevel(Level.DEBUG);
        try {
            getClient().perform(get("/api/core/bitstreams/" + bitstream.getID() + "/content")
                .param("accessToken", request.getAccess_token())).andExpect(status().isOk());
            assertTrue(messages.stream().anyMatch(message -> message.contains("Authorize access")));
            assertFalse(messages.stream().anyMatch(message -> message.contains(request.getAccess_token())));
        } finally {
            logger.removeAppender(appender);
            logger.setLevel(level);
        }
    }
}

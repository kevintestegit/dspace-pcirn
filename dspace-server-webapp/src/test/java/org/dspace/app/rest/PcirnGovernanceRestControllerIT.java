/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.rest;

import static org.hamcrest.MatcherAssert.assertThat;
import static org.hamcrest.Matchers.contains;
import static org.hamcrest.Matchers.is;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.put;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.sql.SQLException;
import java.util.UUID;

import org.apache.commons.io.IOUtils;
import org.dspace.app.rest.test.AbstractControllerIntegrationTest;
import org.dspace.authorize.ResourcePolicy;
import org.dspace.authorize.factory.AuthorizeServiceFactory;
import org.dspace.authorize.service.AuthorizeService;
import org.dspace.authorize.service.ResourcePolicyService;
import org.dspace.builder.BitstreamBuilder;
import org.dspace.builder.CollectionBuilder;
import org.dspace.builder.CommunityBuilder;
import org.dspace.builder.EPersonBuilder;
import org.dspace.builder.GroupBuilder;
import org.dspace.builder.ItemBuilder;
import org.dspace.content.Collection;
import org.dspace.content.Community;
import org.dspace.content.Item;
import org.dspace.core.Constants;
import org.dspace.core.Context;
import org.dspace.eperson.EPerson;
import org.dspace.eperson.Group;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;
import org.springframework.http.MediaType;
import org.springframework.test.web.servlet.ResultActions;

/**
 * Integration tests for the PCIRN governance endpoints.
 */
public class PcirnGovernanceRestControllerIT extends AbstractControllerIntegrationTest {

    private Community community;
    private Collection collection;
    private Item item;
    private Group sectorGroup;
    private Group otherGroup;
    private EPerson sectorMember;

    @Before
    public void setup() throws Exception {
        super.setUp();
        context.turnOffAuthorisationSystem();
        community = CommunityBuilder.createCommunity(context).withName("Instituto de Criminalística").build();
        collection = CollectionBuilder.createCollection(context, community).withName("Portarias").build();
        item = ItemBuilder.createItem(context, collection).withTitle("Portaria 1").build();
        try (InputStream is = IOUtils.toInputStream("conteudo", StandardCharsets.UTF_8)) {
            BitstreamBuilder.createBitstream(context, item, is).withName("doc.txt").build();
        }
        sectorMember = EPersonBuilder.createEPerson(context)
            .withEmail("setor@example.org")
            .withPassword(password)
            .build();
        sectorGroup = GroupBuilder.createGroup(context)
            .withName("PCIRN_Setor_TEST")
            .addMember(sectorMember)
            .build();
        otherGroup = GroupBuilder.createGroup(context)
            .withName("PCIRN_Grupo_Local")
            .build();
        GroupBuilder.createGroup(context)
            .withName("NUGECID")
            .build();
        AuthorizeService authorizeService = AuthorizeServiceFactory.getInstance().getAuthorizeService();
        authorizeService.addPolicy(context, collection, Constants.ADD, sectorGroup);
        context.restoreAuthSystemState();
    }

    @After
    public void destroy() throws Exception {
        community = null;
        collection = null;
        item = null;
        sectorGroup = null;
        otherGroup = null;
        sectorMember = null;
        super.destroy();
    }

    @Test
    public void governanceListsPublicCommunityWithSectorPublisher() throws Exception {
        governanceMatrix()
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.communities[0].name").value("Instituto de Criminalística"))
            .andExpect(jsonPath("$.communities[0].accessMode").value("public"))
            .andExpect(jsonPath("$.communities[0].collections[0].name").value("Portarias"))
            .andExpect(jsonPath("$.communities[0].collections[0].publishGroup.name").value("PCIRN_Setor_TEST"))
            .andExpect(jsonPath("$.curationGroup.name").value("NUGECID"));
    }

    @Test
    public void restrictCommunityReplacesAnonymousReadAndKeepsPublication() throws Exception {
        getClient().perform(put("/api/pcirn/governance/communities/{uuid}/access", community.getID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"mode\":\"restricted\",\"sectorGroup\":\"" + sectorGroup.getID() + "\"}")
                .header("Authorization", getAuthToken(admin.getEmail(), password)))
            .andExpect(status().isOk());

        getClient().perform(get("/api/core/communities/{uuid}", community.getID()))
            .andExpect(status().isUnauthorized());
        getClient().perform(get("/api/core/communities/{uuid}", community.getID())
                .header("Authorization", getAuthToken(sectorMember.getEmail(), password)))
            .andExpect(status().isOk());

        governanceMatrix()
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.communities[0].accessMode").value("restricted"))
            .andExpect(jsonPath("$.communities[0].sectorGroup.name").value("PCIRN_Setor_TEST"))
            .andExpect(jsonPath("$.communities[0].collections[0].publishGroup.name").value("PCIRN_Setor_TEST"));

        assertThat(policyGroupPresent(collection.getID(), Constants.DEFAULT_ITEM_READ, sectorGroup.getID()), is(true));
        assertThat(policyGroupPresent(collection.getID(), Constants.DEFAULT_BITSTREAM_READ, sectorGroup.getID()),
            is(true));
        assertThat(policyGroupPresent(item.getID(), Constants.READ, sectorGroup.getID()), is(true));
    }

    @Test
    public void restorePublicReopensAnonymousRead() throws Exception {
        getClient().perform(put("/api/pcirn/governance/communities/{uuid}/access", community.getID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"mode\":\"restricted\",\"sectorGroup\":\"" + sectorGroup.getID() + "\"}")
                .header("Authorization", getAuthToken(admin.getEmail(), password)))
            .andExpect(status().isOk());

        getClient().perform(put("/api/pcirn/governance/communities/{uuid}/access", community.getID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"mode\":\"public\"}")
                .header("Authorization", getAuthToken(admin.getEmail(), password)))
            .andExpect(status().isOk());

        getClient().perform(get("/api/core/communities/{uuid}", community.getID()))
            .andExpect(status().isOk());

        governanceMatrix()
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.communities[0].accessMode").value("public"));
    }

    @Test
    public void localPoliciesSurviveBothToggles() throws Exception {
        AuthorizeService authorizeService = AuthorizeServiceFactory.getInstance().getAuthorizeService();
        context.turnOffAuthorisationSystem();
        authorizeService.addPolicy(context, item, Constants.READ, otherGroup);
        context.restoreAuthSystemState();

        String adminToken = getAuthToken(admin.getEmail(), password);
        getClient().perform(put("/api/pcirn/governance/communities/{uuid}/access", community.getID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"mode\":\"restricted\",\"sectorGroup\":\"" + sectorGroup.getID() + "\"}")
                .header("Authorization", adminToken))
            .andExpect(status().isOk());
        getClient().perform(put("/api/pcirn/governance/communities/{uuid}/access", community.getID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"mode\":\"public\"}")
                .header("Authorization", adminToken))
            .andExpect(status().isOk());

        assertThat(policyGroupPresent(item.getID(), Constants.READ, otherGroup.getID()), is(true));
    }

    @Test
    public void restrictWithoutValidGroupIsRejected() throws Exception {
        String adminToken = getAuthToken(admin.getEmail(), password);
        getClient().perform(put("/api/pcirn/governance/communities/{uuid}/access", community.getID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"mode\":\"restricted\"}")
                .header("Authorization", adminToken))
            .andExpect(status().isUnprocessableEntity());
        getClient().perform(put("/api/pcirn/governance/communities/{uuid}/access", community.getID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"mode\":\"weird\"}")
                .header("Authorization", adminToken))
            .andExpect(status().isUnprocessableEntity());
    }

    @Test
    public void nonAdminIsForbidden() throws Exception {
        getClient().perform(put("/api/pcirn/governance/communities/{uuid}/access", community.getID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"mode\":\"public\"}")
                .header("Authorization", getAuthToken(sectorMember.getEmail(), password)))
            .andExpect(status().isForbidden());
    }

    @Test
    public void unknownCommunityIsNotFound() throws Exception {
        getClient().perform(put("/api/pcirn/governance/communities/{uuid}/access", UUID.randomUUID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"mode\":\"public\"}")
                .header("Authorization", getAuthToken(admin.getEmail(), password)))
            .andExpect(status().isNotFound());
    }

    @Test
    public void bindCollectionSectorIsIdempotentAndPublishes() throws Exception {
        context.turnOffAuthorisationSystem();
        Collection second = CollectionBuilder.createCollection(context, community).withName("Memorandos").build();
        context.restoreAuthSystemState();

        String adminToken = getAuthToken(admin.getEmail(), password);
        getClient().perform(put("/api/pcirn/governance/collections/{uuid}/sector", second.getID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"sectorGroup\":\"" + sectorGroup.getID() + "\"}")
                .header("Authorization", adminToken))
            .andExpect(status().isOk());
        getClient().perform(put("/api/pcirn/governance/collections/{uuid}/sector", second.getID())
                .contentType(MediaType.APPLICATION_JSON)
                .content("{\"sectorGroup\":\"" + sectorGroup.getID() + "\"}")
                .header("Authorization", adminToken))
            .andExpect(status().isOk());

        assertThat(policyGroupPresent(second.getID(), Constants.ADD, sectorGroup.getID()), is(true));
        getClient().perform(get("/api/pcirn/governance").header("Authorization", adminToken))
            .andExpect(status().isOk())
            .andExpect(jsonPath("$.communities[0].collections[?(@.uuid=='" + second.getID()
                    + "')].publishGroup.name", contains("PCIRN_Setor_TEST")));
    }

    private ResultActions governanceMatrix() throws Exception {
        String token = getAuthToken(admin.getEmail(), password);
        return getClient().perform(get("/api/pcirn/governance").header("Authorization", token));
    }

    private boolean policyGroupPresent(UUID dsoUuid, int action, UUID groupId) throws SQLException {
        ResourcePolicyService resourcePolicyService = AuthorizeServiceFactory.getInstance().getResourcePolicyService();
        Context fresh = new Context();
        try {
            for (ResourcePolicy policy : resourcePolicyService
                .findByResouceUuidAndActionId(fresh, dsoUuid, action, 0, 100)) {
                if (policy.getGroup() != null && policy.getGroup().getID().equals(groupId)) {
                    return true;
                }
            }
            return false;
        } finally {
            fresh.abort();
        }
    }
}

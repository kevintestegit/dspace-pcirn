/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.rest;

import static org.hamcrest.Matchers.endsWith;
import static org.springframework.test.web.servlet.request.MockMvcRequestBuilders.get;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.jsonPath;
import static org.springframework.test.web.servlet.result.MockMvcResultMatchers.status;

import java.util.UUID;

import org.dspace.app.rest.test.AbstractControllerIntegrationTest;
import org.dspace.builder.CommunityBuilder;
import org.junit.Test;

/**
 * Integration test for the {@link RestResourceController}
 *
 * @author Andrea Bollini (andrea.bollini at 4science.it)
 */
public class RestResourceControllerIT extends AbstractControllerIntegrationTest {

    /**
     * Submission, import and version-history routes require authentication even for public resources.
     * @throws Exception if a request cannot be performed
     */
    @Test
    public void privateRoutesRejectAnonymousRequests() throws Exception {
        for (String path : new String[] {"/api/integration/externalsources/orcid",
            "/api/submission/vocabularies/common_types", "/api/versioning/versionhistories/1",
            "/api/statistics/searchevents", "/api/undefined/undefined", "/api/captcha/challenge",
            "/api/statistics/usagereports", "/api/integration/qualityassuranceevents",
            "/api/submission/vocabularyEntryDetails/srsc:SCB110", "/api/system/systemwidealerts/1",
            "/api/eperson/groups/00000000-0000-0000-0000-000000000000"}) {
            getClient().perform(get(path)).andExpect(status().isUnauthorized());
        }
    }

    @Test
    public void undefinedRepository() throws Exception {
        // When we call the root endpoint
        getClient(getAuthToken(eperson.getEmail(), password)).perform(get("/api/undefined/undefined"))
                // The status has to be 404 Not Found
                .andExpect(status().isNotFound());
    }

    @Test
    public void undefinedSubResource() throws Exception {
        // We turn off the authorization system in order to create the structure as defined below
        context.turnOffAuthorisationSystem();

        // ** GIVEN **
        // 1. A community-collection structure with one parent community with sub-community and one collection.
        parentCommunity = CommunityBuilder.createCommunity(context).withName("Parent Community").build();

        context.restoreAuthSystemState();
        // When we call the root endpoint
        getClient().perform(get("/api/core/communities/" + parentCommunity.getID().toString() + "/undefined"))
                // The status has to be 404 Not Found
                .andExpect(status().isNotFound());
    }

    @Test
    public void selfRelIsNotASubResource() throws Exception {
        // We turn off the authorization system in order to create the structure as defined below
        context.turnOffAuthorisationSystem();

        // ** GIVEN **
        // 1. A community-collection structure with one parent community with sub-community and one collection.
        parentCommunity = CommunityBuilder.createCommunity(context).withName("Parent Community").build();

        context.restoreAuthSystemState();
        // When we call the root endpoint
        getClient().perform(get("/api/core/communities/" + parentCommunity.getID().toString() + "/self"))
                // The status has to be 404 Not Found
                .andExpect(status().isNotFound());
    }

    @Test
    public void notExistentResourceValidSubPath() throws Exception {
        // When we call the root endpoint
        getClient().perform(get("/api/core/communities/" + UUID.randomUUID().toString() + "/collections"))
                // The status has to be 404 Not Found
                .andExpect(status().isNotFound());
    }

    @Test
    public void selfLinkContainsRequestParametersWhenProvided() throws Exception {
        // When we call a search endpoint with additional parameters
        getClient().perform(get("/api/core/metadatafields/search/byFieldName?schema=dc&offset=0"))
                   // The self link should contain those same parameters
                   .andExpect(jsonPath("$._links.self.href", endsWith(
                           "/api/core/metadatafields/search/byFieldName?schema=dc&offset=0")));
    }

    @Test
    public void selfLinkDevoidOfRequestParametersWhenNoneProvided() throws Exception {
        // When we call a search endpoint without additional parameters
        getClient().perform(get("/api/core/metadatafields/search/byFieldName"))
                   // The self link should match the initial request exactly
                   .andExpect(jsonPath("$._links.self.href",
                                       endsWith("/api/core/metadatafields/search/byFieldName")));
    }

    @Test
    public void selfLinkContainsRequestParametersAndEmbedsWhenProvided() throws Exception {
        // When we call a search endpoint with additional parameters and an embed parameter
        getClient().perform(get("/api/core/metadatafields/search/byFieldName?schema=dc&offset=0&embed=schema"))
                   // The self link should contain those same parameters
                   .andExpect(jsonPath("$._links.self.href", endsWith(
                           "/api/core/metadatafields/search/byFieldName?schema=dc&offset=0")));

        getClient().perform(get("/api/core/metadatafields/search/byFieldName?schema=dc&offset=0&embed.size=schema=5"))
                   // The self link should contain those same parameters
                   .andExpect(jsonPath("$._links.self.href", endsWith(
                           "/api/core/metadatafields/search/byFieldName?schema=dc&offset=0")));
    }



}

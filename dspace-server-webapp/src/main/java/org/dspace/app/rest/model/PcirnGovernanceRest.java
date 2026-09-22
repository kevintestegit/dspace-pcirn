/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.rest.model;

import java.util.List;
import java.util.UUID;

/**
 * Data transfer objects for the PCIRN governance endpoints.
 *
 * @author PCIRN
 */
public final class PcirnGovernanceRest {

    private PcirnGovernanceRest() {
    }

    /**
     * Summary of a DSpace group with its direct member count.
     *
     * @param uuid        group identifier
     * @param name        group name
     * @param memberCount number of members
     */
    public record GroupSummary(UUID uuid, String name, int memberCount) {
    }

    /**
     * Governance view of one collection.
     *
     * @param uuid         collection identifier
     * @param name         collection name
     * @param handle       collection handle
     * @param publishGroup group allowed to submit into the collection, may be null
     */
    public record CollectionGovernance(UUID uuid, String name, String handle, GroupSummary publishGroup) {
    }

    /**
     * Governance view of one community.
     *
     * @param uuid        community identifier
     * @param name        community name
     * @param handle      community handle
     * @param accessMode  {@code public} or {@code restricted}
     * @param sectorGroup group that reads the community when restricted, may be null
     * @param collections descendant collections
     */
    public record CommunityGovernance(UUID uuid, String name, String handle, String accessMode,
                                      GroupSummary sectorGroup, List<CollectionGovernance> collections) {
    }

    /**
     * Full governance matrix.
     *
     * @param communities   all communities
     * @param curationGroup repository-wide curation group
     */
    public record Governance(List<CommunityGovernance> communities, GroupSummary curationGroup) {
    }

    /**
     * Request payload for changing a community access mode.
     *
     * @param mode        {@code public} or {@code restricted}
     * @param sectorGroup group required when restricting
     */
    public record AccessModeRequest(String mode, UUID sectorGroup) {
    }

    /**
     * Request payload for binding a collection to a sector group.
     *
     * @param sectorGroup group to bind
     */
    public record SectorRequest(UUID sectorGroup) {
    }
}

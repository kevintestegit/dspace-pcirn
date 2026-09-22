/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.rest;

import java.sql.SQLException;
import java.util.ArrayList;
import java.util.Comparator;
import java.util.Iterator;
import java.util.List;
import java.util.UUID;

import org.dspace.app.rest.exception.UnprocessableEntityException;
import org.dspace.app.rest.model.PcirnGovernanceRest.AccessModeRequest;
import org.dspace.app.rest.model.PcirnGovernanceRest.CollectionGovernance;
import org.dspace.app.rest.model.PcirnGovernanceRest.CommunityGovernance;
import org.dspace.app.rest.model.PcirnGovernanceRest.Governance;
import org.dspace.app.rest.model.PcirnGovernanceRest.GroupSummary;
import org.dspace.app.rest.model.PcirnGovernanceRest.SectorRequest;
import org.dspace.app.rest.utils.ContextUtil;
import org.dspace.authorize.AuthorizeException;
import org.dspace.authorize.ResourcePolicy;
import org.dspace.authorize.service.AuthorizeService;
import org.dspace.authorize.service.ResourcePolicyService;
import org.dspace.content.Bitstream;
import org.dspace.content.Collection;
import org.dspace.content.Community;
import org.dspace.content.DSpaceObject;
import org.dspace.content.Item;
import org.dspace.content.service.BitstreamService;
import org.dspace.content.service.CollectionService;
import org.dspace.content.service.CommunityService;
import org.dspace.content.service.ItemService;
import org.dspace.core.Constants;
import org.dspace.core.Context;
import org.dspace.eperson.Group;
import org.dspace.eperson.service.GroupService;
import org.springframework.data.rest.webmvc.ResourceNotFoundException;
import org.springframework.http.ResponseEntity;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PutMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Administrative endpoints for the PCIRN access governance model. The page at
 * {@code /admin/governance} consumes these endpoints. Communities, collections, groups, and
 * resource policies remain the single source of truth; no parallel registry is used.
 *
 * @author PCIRN
 */
@RestController
@RequestMapping("/api/pcirn/governance")
public class PcirnGovernanceRestController {

    private static final String CURATION_GROUP_NAME = "NUGECID";
    private static final String MODE_PUBLIC = "public";
    private static final String MODE_RESTRICTED = "restricted";

    private final CommunityService communityService;
    private final CollectionService collectionService;
    private final ItemService itemService;
    private final BitstreamService bitstreamService;
    private final ResourcePolicyService resourcePolicyService;
    private final GroupService groupService;
    private final AuthorizeService authorizeService;

    public PcirnGovernanceRestController(CommunityService communityService,
                                         CollectionService collectionService,
                                         ItemService itemService,
                                         BitstreamService bitstreamService,
                                         ResourcePolicyService resourcePolicyService,
                                         GroupService groupService,
                                         AuthorizeService authorizeService) {
        this.communityService = communityService;
        this.collectionService = collectionService;
        this.itemService = itemService;
        this.bitstreamService = bitstreamService;
        this.resourcePolicyService = resourcePolicyService;
        this.groupService = groupService;
        this.authorizeService = authorizeService;
    }

    /**
     * Returns the governance matrix: every community with its access mode, sector group, and
     * descendant collections, plus the repository-wide curation group.
     *
     * @return governance matrix
     * @throws SQLException if the database access fails
     */
    @GetMapping
    @PreAuthorize("hasAuthority('ADMIN')")
    public Governance getGovernance() throws SQLException {
        Context context = ContextUtil.obtainCurrentRequestContext();
        Group anonymous = groupService.findByName(context, Group.ANONYMOUS);
        Group administrator = groupService.findByName(context, Group.ADMIN);
        List<CommunityGovernance> communities = new ArrayList<>();
        for (Community community : communityService.findAll(context)) {
            communities.add(toCommunityGovernance(context, community, anonymous, administrator));
        }
        Group curation = groupService.findByName(context, CURATION_GROUP_NAME);
        Governance governance = new Governance(communities, toGroupSummary(context, curation));
        context.complete();
        return governance;
    }

    /**
     * Switches a community between public and restricted access. Restricted replaces the
     * Anonymous READ policies with the sector group on the community, its collections, all
     * items and bitstreams, and the collection read defaults; publication (ADD) is ensured for
     * the sector group. Public reverses the READ rewrite and leaves ADD untouched.
     *
     * @param uuid    community identifier
     * @param request desired mode and, when restricting, the sector group
     * @return 200 when applied
     * @throws SQLException          if the database access fails
     * @throws AuthorizeException    if a policy update is not authorized
     */
    @PutMapping("/communities/{uuid}/access")
    @PreAuthorize("hasAuthority('ADMIN')")
    public ResponseEntity<Void> setCommunityAccess(@PathVariable UUID uuid, @RequestBody AccessModeRequest request)
        throws SQLException, AuthorizeException {
        Context context = ContextUtil.obtainCurrentRequestContext();
        try {
            Community community = communityService.find(context, uuid);
            if (community == null) {
                throw new ResourceNotFoundException("No such community: " + uuid);
            }
            Group anonymous = groupService.findByName(context, Group.ANONYMOUS);
            Group administrator = groupService.findByName(context, Group.ADMIN);
            if (MODE_RESTRICTED.equals(request.mode())) {
                Group sectorGroup = findGroup(context, request.sectorGroup());
                validateSectorGroup(sectorGroup, anonymous, administrator);
                applyCommunityAccess(context, community, anonymous, sectorGroup, true);
            } else if (MODE_PUBLIC.equals(request.mode())) {
                Group sectorGroup = findSectorGroup(context, community, anonymous, administrator);
                applyCommunityAccess(context, community, sectorGroup, anonymous, false);
            } else {
                throw new UnprocessableEntityException("Unsupported access mode: " + request.mode());
            }
            context.complete();
        } catch (SQLException | AuthorizeException | RuntimeException e) {
            context.abort();
            throw e;
        }
        return ResponseEntity.ok().build();
    }

    /**
     * Binds a collection to a sector group: ensures publication (ADD) for the group and
     * reconciles the collection read access with the community access mode.
     *
     * @param uuid    collection identifier
     * @param request sector group to bind
     * @return 200 when applied
     * @throws SQLException          if the database access fails
     * @throws AuthorizeException    if a policy update is not authorized
     */
    @PutMapping("/collections/{uuid}/sector")
    @PreAuthorize("hasAuthority('ADMIN')")
    public ResponseEntity<Void> bindCollectionSector(@PathVariable UUID uuid, @RequestBody SectorRequest request)
        throws SQLException, AuthorizeException {
        Context context = ContextUtil.obtainCurrentRequestContext();
        try {
            Collection collection = collectionService.find(context, uuid);
            if (collection == null) {
                throw new ResourceNotFoundException("No such collection: " + uuid);
            }
            Group anonymous = groupService.findByName(context, Group.ANONYMOUS);
            Group administrator = groupService.findByName(context, Group.ADMIN);
            Group sectorGroup = findGroup(context, request.sectorGroup());
            validateSectorGroup(sectorGroup, anonymous, administrator);
            Group readGroup = resolveCollectionReadGroup(context, collection, sectorGroup, anonymous, administrator);
            Group previousReadGroup = anonymous.getID().equals(readGroup.getID()) ? sectorGroup : anonymous;
            applyCollectionRead(context, collection, previousReadGroup, readGroup);
            ensurePolicy(context, collection, sectorGroup, Constants.ADD);
            context.complete();
        } catch (SQLException | AuthorizeException | RuntimeException e) {
            context.abort();
            throw e;
        }
        return ResponseEntity.ok().build();
    }

    private CommunityGovernance toCommunityGovernance(Context context, Community community, Group anonymous,
                                                      Group administrator) throws SQLException {
        Group sectorGroup = findSectorGroup(context, community, anonymous, administrator);
        boolean anonymousRead = hasAnonymousRead(context, community, anonymous);
        String accessMode = sectorGroup != null && !anonymousRead ? MODE_RESTRICTED : MODE_PUBLIC;
        List<CollectionGovernance> collections = new ArrayList<>();
        for (Collection collection : communityService.getAllCollections(context, community)) {
            collections.add(toCollectionGovernance(context, collection, administrator));
        }
        return new CommunityGovernance(community.getID(), community.getName(), community.getHandle(),
            accessMode, toGroupSummary(context, sectorGroup), collections);
    }

    private CollectionGovernance toCollectionGovernance(Context context, Collection collection, Group administrator)
        throws SQLException {
        Group publishGroup = null;
        List<ResourcePolicy> policies = new ArrayList<>(resourcePolicyService.find(context, collection, Constants.ADD));
        policies.sort(Comparator.comparing(policy -> policy.getGroup() == null ? "" : policy.getGroup().getName()));
        for (ResourcePolicy policy : policies) {
            Group group = policy.getGroup();
            if (group == null || administrator != null && group.getID().equals(administrator.getID())) {
                continue;
            }
            publishGroup = group;
            break;
        }
        return new CollectionGovernance(collection.getID(), collection.getName(), collection.getHandle(),
            toGroupSummary(context, publishGroup));
    }

    private GroupSummary toGroupSummary(Context context, Group group) throws SQLException {
        if (group == null) {
            return null;
        }
        return new GroupSummary(group.getID(), group.getName(), groupService.allMembers(context, group).size());
    }

    private void applyCommunityAccess(Context context, Community community, Group from, Group to, boolean restricted)
        throws SQLException, AuthorizeException {
        replacePolicies(context, community, Constants.READ, from, to);
        for (Collection collection : communityService.getAllCollections(context, community)) {
            if (restricted) {
                ensurePolicy(context, collection, to, Constants.ADD);
            }
            applyCollectionRead(context, collection, from, to);
        }
    }

    private void applyCollectionRead(Context context, Collection collection, Group from, Group to)
        throws SQLException, AuthorizeException {
        replacePolicies(context, collection, Constants.READ, from, to);
        replacePolicies(context, collection, Constants.DEFAULT_ITEM_READ, from, to);
        replacePolicies(context, collection, Constants.DEFAULT_BITSTREAM_READ, from, to);
        Iterator<Item> items = itemService.findAllByCollection(context, collection);
        while (items.hasNext()) {
            replacePolicies(context, items.next(), Constants.READ, from, to);
        }
        Iterator<Bitstream> bitstreams = bitstreamService.getCollectionBitstreams(context, collection);
        while (bitstreams.hasNext()) {
            replacePolicies(context, bitstreams.next(), Constants.READ, from, to);
        }
    }

    private void replacePolicies(Context context, DSpaceObject dso, int action, Group from, Group to)
        throws SQLException, AuthorizeException {
        if (from != null) {
            for (ResourcePolicy policy : resourcePolicyService.find(context, dso, action)) {
                if (policy.getGroup() != null && policy.getGroup().getID().equals(from.getID())) {
                    policy.setGroup(to);
                    resourcePolicyService.update(context, policy);
                }
            }
        }
        ensurePolicy(context, dso, to, action);
    }

    private void ensurePolicy(Context context, DSpaceObject dso, Group group, int action)
        throws SQLException, AuthorizeException {
        if (group == null) {
            return;
        }
        if (authorizeService.findByTypeGroupAction(context, dso, group, action) == null) {
            authorizeService.addPolicy(context, dso, action, group);
        }
    }

    private Group resolveCollectionReadGroup(Context context, Collection collection, Group requested,
                                             Group anonymous, Group administrator) throws SQLException {
        Group restricted = null;
        for (Community community : collection.getCommunities()) {
            Group sectorGroup = findSectorGroup(context, community, anonymous, administrator);
            if (sectorGroup != null && !hasAnonymousRead(context, community, anonymous)) {
                if (!sectorGroup.getID().equals(requested.getID())) {
                    throw new UnprocessableEntityException(
                        "Community " + community.getName() + " is restricted to a different sector group");
                }
                restricted = sectorGroup;
            }
        }
        return restricted == null ? anonymous : restricted;
    }

    private Group findSectorGroup(Context context, Community community, Group anonymous, Group administrator)
        throws SQLException {
        List<ResourcePolicy> policies = new ArrayList<>(resourcePolicyService.find(context, community, Constants.READ));
        policies.sort(Comparator.comparing(policy -> policy.getGroup() == null ? "" : policy.getGroup().getName()));
        Group sectorGroup = null;
        for (ResourcePolicy policy : policies) {
            Group group = policy.getGroup();
            if (group == null || group.getID().equals(anonymous.getID())) {
                continue;
            }
            if (administrator != null && group.getID().equals(administrator.getID())) {
                continue;
            }
            sectorGroup = group;
            break;
        }
        return sectorGroup;
    }

    private boolean hasAnonymousRead(Context context, DSpaceObject dso, Group anonymous) throws SQLException {
        for (ResourcePolicy policy : resourcePolicyService.find(context, dso, Constants.READ)) {
            if (policy.getGroup() != null && policy.getGroup().getID().equals(anonymous.getID())) {
                return true;
            }
        }
        return false;
    }

    private Group findGroup(Context context, UUID uuid) throws SQLException {
        if (uuid == null) {
            return null;
        }
        return groupService.find(context, uuid);
    }

    private void validateSectorGroup(Group group, Group anonymous, Group administrator) {
        if (group == null || group.getID().equals(anonymous.getID())
            || administrator != null && group.getID().equals(administrator.getID())) {
            throw new UnprocessableEntityException("A valid sector group is required");
        }
    }
}

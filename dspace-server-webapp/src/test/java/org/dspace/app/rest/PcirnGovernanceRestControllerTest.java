/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.rest;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertFalse;
import static org.junit.Assert.assertThrows;
import static org.junit.Assert.assertTrue;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.anyInt;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.ArgumentMatchers.isNull;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.mockStatic;
import static org.mockito.Mockito.when;

import java.time.LocalDate;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

import org.dspace.app.rest.exception.UnprocessableEntityException;
import org.dspace.app.rest.model.PcirnGovernanceRest.AccessModeRequest;
import org.dspace.app.rest.model.PcirnGovernanceRest.SectorRequest;
import org.dspace.app.rest.utils.ContextUtil;
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
import org.junit.Before;
import org.junit.Test;
import org.mockito.MockedStatic;

/**
 * Exercises governance policy changes without a database or an HTTP server.
 */
public class PcirnGovernanceRestControllerTest {

    private final Context context = mock(Context.class);
    private final Community community = mock(Community.class);
    private final Collection collection = mock(Collection.class);
    private final Item published = mock(Item.class);
    private final Item withdrawn = mock(Item.class);
    private final Item draft = mock(Item.class);
    private final Bitstream publishedFile = mock(Bitstream.class);
    private final Bitstream withdrawnFile = mock(Bitstream.class);
    private final Bitstream draftFile = mock(Bitstream.class);
    private final Bitstream deletedFile = mock(Bitstream.class);
    private final Group anonymous = group();
    private final Group sector = group();
    private final UUID communityId = UUID.randomUUID();
    private final UUID collectionId = UUID.randomUUID();
    private final Map<DSpaceObject, Map<Integer, List<ResourcePolicy>>> policies = new HashMap<>();
    private PcirnGovernanceRestController controller;
    private CommunityService communities;
    private GroupService groups;

    @Before
    public void setUp() throws Exception {
        communities = mock(CommunityService.class);
        CollectionService collections = mock(CollectionService.class);
        ItemService items = mock(ItemService.class);
        BitstreamService bitstreams = mock(BitstreamService.class);
        groups = mock(GroupService.class);
        ResourcePolicyService resources = mock(ResourcePolicyService.class);
        AuthorizeService authorization = mock(AuthorizeService.class);
        controller = new PcirnGovernanceRestController(communities, collections, items, bitstreams,
            resources, groups, authorization);

        when(communities.find(context, communityId)).thenReturn(community);
        when(communities.getAllCollections(context, community)).thenReturn(List.of(collection));
        when(collections.find(context, collectionId)).thenReturn(collection);
        when(collection.getCommunities()).thenReturn(List.of(community));
        when(communities.getAllParents(context, collection)).thenReturn(List.of(community));
        Community formerCommunity = mock(Community.class);
        addPolicy(formerCommunity, Constants.READ, sector);
        when(communities.findAll(context)).thenReturn(List.of(community, formerCommunity));
        when(groups.findByName(context, Group.ANONYMOUS)).thenReturn(anonymous);
        when(groups.find(context, sector.getID())).thenReturn(sector);
        when(items.findAllByCollection(context, collection))
            .thenAnswer(invocation -> List.of(published, withdrawn, draft).iterator());
        when(published.isArchived()).thenReturn(true);
        when(withdrawn.isArchived()).thenReturn(true);
        when(withdrawn.isWithdrawn()).thenReturn(true);
        when(deletedFile.isDeleted()).thenReturn(true);
        when(bitstreams.getCollectionBitstreams(context, collection))
            .thenAnswer(invocation -> List.of(publishedFile, withdrawnFile, draftFile, deletedFile).iterator());
        when(bitstreams.getItemBitstreams(context, published))
            .thenAnswer(invocation -> List.of(publishedFile, deletedFile).iterator());
        when(bitstreams.getItemBitstreams(context, withdrawn))
            .thenAnswer(invocation -> List.of(withdrawnFile).iterator());
        when(bitstreams.getItemBitstreams(context, draft))
            .thenAnswer(invocation -> List.of(draftFile).iterator());
        when(resources.find(eq(context), any(DSpaceObject.class), anyInt()))
            .thenAnswer(invocation -> policies(invocation.getArgument(1), invocation.getArgument(2)));
        doAnswer(invocation -> {
            ResourcePolicy policy = invocation.getArgument(1);
            policies.values().forEach(actions -> actions.values().forEach(list -> list.remove(policy)));
            return null;
        }).when(resources).delete(eq(context), any(ResourcePolicy.class));
        when(authorization.findByTypeGroupAction(eq(context), any(DSpaceObject.class), any(Group.class), anyInt()))
            .thenAnswer(invocation -> policies(invocation.getArgument(1), invocation.getArgument(3)).stream()
                .filter(policy -> policy.getGroup().equals(invocation.getArgument(2))).findFirst().orElse(null));
        doAnswer(invocation -> {
            addPolicy(invocation.getArgument(1), invocation.getArgument(2), invocation.getArgument(3));
            return null;
        }).when(authorization).addPolicy(eq(context), any(DSpaceObject.class), anyInt(), any(Group.class));
        when(authorization.createResourcePolicy(eq(context), any(DSpaceObject.class), any(Group.class),
            isNull(), anyInt(), isNull())).thenAnswer(invocation ->
                addPolicy(invocation.getArgument(1), invocation.getArgument(4), invocation.getArgument(2)));
        addPolicy(community, Constants.READ, sector);
        addPolicy(withdrawn, Constants.WITHDRAWN_READ, anonymous);
        addPolicy(withdrawnFile, Constants.WITHDRAWN_READ, anonymous);
    }

    @Test
    public void unmarkedLocalAddIsNotSilentlyDeleted() throws Exception {
        Group local = group();
        policies(community, Constants.READ).clear();
        addPolicy(community, Constants.READ, anonymous);
        addPolicy(collection, Constants.ADD, local);
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            assertThrows(UnprocessableEntityException.class,
                () -> controller.bindCollectionSector(collectionId, new SectorRequest(sector.getID())));
        }
        assertTrue(hasPolicy(collection, Constants.ADD, local));
        assertFalse(hasPolicy(collection, Constants.ADD, sector));
    }

    @Test
    public void expiredLocalAddDoesNotReplaceEffectivePublicationPermission() throws Exception {
        ResourcePolicy expired = addPolicy(collection, Constants.ADD, sector);
        when(expired.getEndDate()).thenReturn(LocalDate.now().minusDays(1));
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            controller.bindCollectionSector(collectionId, new SectorRequest(sector.getID()));
        }
        assertEquals(2, policies(collection, Constants.ADD).size());
        assertTrue(policies(collection, Constants.ADD).contains(expired));
        assertTrue(policies(collection, Constants.ADD).stream().anyMatch(policy -> policy.getEndDate() == null));
    }

    @Test
    public void transferReconcilesFormerSectorAndPreservesLocalPolicies() throws Exception {
        Group nextSector = group();
        Group local = group();
        when(groups.find(context, nextSector.getID())).thenReturn(nextSector);
        policies(community, Constants.READ).clear();
        addPolicy(community, Constants.READ, nextSector);
        addPolicy(collection, Constants.ADD, sector);
        addPolicy(collection, Constants.ADD, local).setRpType(ResourcePolicy.TYPE_CUSTOM);
        addPolicy(collection, Constants.ADD, local);
        for (DSpaceObject object : List.of(collection, published, publishedFile)) {
            addPolicy(object, Constants.READ, sector);
            addPolicy(object, Constants.READ, sector).setRpType(ResourcePolicy.TYPE_CUSTOM);
            addPolicy(object, Constants.READ, sector).setRpName("Local access grant");
            ResourcePolicy dated = addPolicy(object, Constants.READ, sector);
            when(dated.getStartDate()).thenReturn(LocalDate.now().plusDays(1));
            addPolicy(object, Constants.READ, local);
        }
        addPolicy(collection, Constants.DEFAULT_ITEM_READ, sector);
        addPolicy(collection, Constants.DEFAULT_BITSTREAM_READ, sector);
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            controller.bindCollectionSector(collectionId, new SectorRequest(nextSector.getID()));
        }
        assertFalse(hasPolicy(collection, Constants.ADD, sector));
        assertTrue(hasPolicy(collection, Constants.ADD, nextSector));
        assertTrue(hasPolicy(collection, Constants.ADD, local));
        assertPublishedObjectsReadableBy(nextSector);
        for (DSpaceObject object : List.of(collection, published, publishedFile)) {
            assertEquals(3, policies(object, Constants.READ).stream()
                .filter(policy -> policy.getGroup().equals(sector)).count());
            assertTrue(hasPolicy(object, Constants.READ, local));
        }
        assertUnpublishedObjectsRemainPrivate();
    }

    @Test
    public void transferToPublicCommunityRemovesFormerSectorRead() throws Exception {
        Group nextSector = group();
        when(groups.find(context, nextSector.getID())).thenReturn(nextSector);
        policies(community, Constants.READ).clear();
        addPolicy(community, Constants.READ, anonymous);
        addPolicy(collection, Constants.ADD, sector);
        addPolicy(publishedFile, Constants.READ, sector);
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            controller.bindCollectionSector(collectionId, new SectorRequest(nextSector.getID()));
        }
        assertFalse(hasPolicy(collection, Constants.ADD, sector));
        assertFalse(hasPolicy(publishedFile, Constants.READ, sector));
        assertPublishedObjectsReadableBy(anonymous);
    }

    @Test
    public void markedAncestorSectorTakesPrecedenceOverUnmarkedLocalRead() throws Exception {
        Community ancestor = mock(Community.class);
        Group local = group();
        when(local.getName()).thenReturn("A local group");
        when(sector.getName()).thenReturn("Z sector group");
        policies(community, Constants.READ).clear();
        addPolicy(community, Constants.READ, anonymous);
        addPolicy(ancestor, Constants.READ, local);
        addPolicy(ancestor, Constants.READ, sector).setRpName("pcirn-governance");
        when(communities.getAllParents(context, collection)).thenReturn(List.of(community, ancestor));
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            controller.bindCollectionSector(collectionId, new SectorRequest(sector.getID()));
        }
        assertPublishedObjectsReadableBy(sector);
        assertTrue(hasPolicy(ancestor, Constants.READ, local));
    }

    @Test
    public void expiredAnonymousPolicyDoesNotMakeRestrictedAncestorPublic() throws Exception {
        Community ancestor = mock(Community.class);
        policies(community, Constants.READ).clear();
        addPolicy(community, Constants.READ, anonymous);
        addPolicy(ancestor, Constants.READ, sector).setRpName("pcirn-governance");
        ResourcePolicy expired = addPolicy(ancestor, Constants.READ, anonymous);
        when(expired.getEndDate()).thenReturn(LocalDate.now().minusDays(1));
        when(communities.getAllParents(context, collection)).thenReturn(List.of(community, ancestor));
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            controller.bindCollectionSector(collectionId, new SectorRequest(sector.getID()));
        }
        assertPublishedObjectsReadableBy(sector);
        assertFalse(hasPolicy(publishedFile, Constants.READ, anonymous));
        assertTrue(policies(ancestor, Constants.READ).contains(expired));
    }

    @Test
    public void markedBindingSupportsRepeatedTransfersBetweenPublicSectors() throws Exception {
        Group nextSector = group();
        when(groups.find(context, nextSector.getID())).thenReturn(nextSector);
        policies(community, Constants.READ).clear();
        addPolicy(community, Constants.READ, anonymous);
        when(communities.findAll(context)).thenReturn(List.of(community));
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            controller.bindCollectionSector(collectionId, new SectorRequest(sector.getID()));
            controller.bindCollectionSector(collectionId, new SectorRequest(nextSector.getID()));
            assertFalse(hasPolicy(collection, Constants.ADD, sector));
            assertTrue(hasPolicy(collection, Constants.ADD, nextSector));
            controller.bindCollectionSector(collectionId, new SectorRequest(sector.getID()));
        }
        assertFalse(hasPolicy(collection, Constants.ADD, nextSector));
        assertTrue(hasPolicy(collection, Constants.ADD, sector));
        assertPublishedObjectsReadableBy(anonymous);
    }

    @Test
    public void restrictedAncestorPreventsIncompatibleSectorBinding() throws Exception {
        Community ancestor = mock(Community.class);
        Group nextSector = group();
        when(groups.find(context, nextSector.getID())).thenReturn(nextSector);
        policies(community, Constants.READ).clear();
        addPolicy(community, Constants.READ, anonymous);
        addPolicy(ancestor, Constants.READ, sector);
        when(communities.getAllParents(context, collection)).thenReturn(List.of(community, ancestor));
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            assertThrows(UnprocessableEntityException.class,
                () -> controller.bindCollectionSector(collectionId, new SectorRequest(nextSector.getID())));
        }
        assertTrue(policies(collection, Constants.ADD).isEmpty());
    }

    @Test
    public void restrictedAncestorDeterminesReadGroup() throws Exception {
        Community ancestor = mock(Community.class);
        policies(community, Constants.READ).clear();
        addPolicy(community, Constants.READ, anonymous);
        addPolicy(ancestor, Constants.READ, sector);
        when(communities.getAllParents(context, collection)).thenReturn(List.of(community, ancestor));
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            controller.bindCollectionSector(collectionId, new SectorRequest(sector.getID()));
        }
        assertPublishedObjectsReadableBy(sector);
        assertFalse(hasPolicy(publishedFile, Constants.READ, anonymous));
    }

    @Test
    public void publishingCommunityDoesNotReopenWithdrawnDocuments() throws Exception {
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            assertEquals(200, controller.setCommunityAccess(communityId, new AccessModeRequest("public", null))
                .getStatusCode().value());
            assertUnpublishedObjectsRemainPrivate();
            assertPublishedObjectsReadableBy(anonymous);
        }
    }

    @Test
    public void bindingCollectionDoesNotReopenWithdrawnDocuments() throws Exception {
        policies(community, Constants.READ).clear();
        addPolicy(community, Constants.READ, anonymous);
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            assertEquals(200, controller.bindCollectionSector(collectionId, new SectorRequest(sector.getID()))
                .getStatusCode().value());
            assertUnpublishedObjectsRemainPrivate();
            assertPublishedObjectsReadableBy(anonymous);
            assertTrue(hasPolicy(collection, Constants.ADD, sector));
        }
    }

    @Test
    public void restrictThenPublishPreservesWithdrawalAndLocalPolicies() throws Exception {
        Group local = group();
        policies(community, Constants.READ).clear();
        addPolicy(community, Constants.READ, anonymous);
        addPolicy(published, Constants.READ, anonymous);
        addPolicy(publishedFile, Constants.READ, anonymous);
        addPolicy(publishedFile, Constants.READ, local);
        try (MockedStatic<ContextUtil> contexts = mockStatic(ContextUtil.class)) {
            contexts.when(ContextUtil::obtainCurrentRequestContext).thenReturn(context);
            controller.setCommunityAccess(communityId, new AccessModeRequest("restricted", sector.getID()));
            assertUnpublishedObjectsRemainPrivate();
            assertPublishedObjectsReadableBy(sector);
            assertFalse(hasPolicy(publishedFile, Constants.READ, anonymous));
            controller.setCommunityAccess(communityId, new AccessModeRequest("public", null));
            assertUnpublishedObjectsRemainPrivate();
            assertPublishedObjectsReadableBy(anonymous);
            assertTrue(hasPolicy(publishedFile, Constants.READ, local));
        }
    }

    private void assertUnpublishedObjectsRemainPrivate() {
        for (DSpaceObject object : List.of(withdrawn, withdrawnFile, draft, draftFile, deletedFile)) {
            assertTrue("Unexpected READ on " + object, policies(object, Constants.READ).isEmpty());
        }
        assertTrue(hasPolicy(withdrawn, Constants.WITHDRAWN_READ, anonymous));
        assertTrue(hasPolicy(withdrawnFile, Constants.WITHDRAWN_READ, anonymous));
    }

    private void assertPublishedObjectsReadableBy(Group group) {
        for (DSpaceObject object : List.of(collection, published, publishedFile)) {
            assertTrue(hasPolicy(object, Constants.READ, group));
        }
        assertTrue(hasPolicy(collection, Constants.DEFAULT_ITEM_READ, group));
        assertTrue(hasPolicy(collection, Constants.DEFAULT_BITSTREAM_READ, group));
    }

    private boolean hasPolicy(DSpaceObject object, int action, Group group) {
        return policies(object, action).stream().anyMatch(policy -> policy.getGroup().equals(group));
    }

    private List<ResourcePolicy> policies(DSpaceObject object, int action) {
        return policies.computeIfAbsent(object, key -> new HashMap<>())
            .computeIfAbsent(action, key -> new ArrayList<>());
    }

    private ResourcePolicy addPolicy(DSpaceObject object, int action, Group group) throws Exception {
        ResourcePolicy policy = mock(ResourcePolicy.class);
        Group[] currentGroup = {group};
        String[] currentType = {null};
        String[] currentName = {null};
        when(policy.getRpName()).thenAnswer(invocation -> currentName[0]);
        doAnswer(invocation -> {
            currentName[0] = invocation.getArgument(0);
            return null;
        }).when(policy).setRpName(any(String.class));
        when(policy.getRpType()).thenAnswer(invocation -> currentType[0]);
        doAnswer(invocation -> {
            currentType[0] = invocation.getArgument(0);
            return null;
        }).when(policy).setRpType(any(String.class));
        when(policy.getGroup()).thenAnswer(invocation -> currentGroup[0]);
        doAnswer(invocation -> {
            currentGroup[0] = invocation.getArgument(0);
            return null;
        }).when(policy).setGroup(any(Group.class));
        policies(object, action).add(policy);
        return policy;
    }

    private static Group group() {
        Group group = mock(Group.class);
        when(group.getID()).thenReturn(UUID.randomUUID());
        when(group.getName()).thenReturn("Test group");
        return group;
    }
}

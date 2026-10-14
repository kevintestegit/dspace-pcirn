/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.authorize;

import static org.junit.Assert.assertEquals;
import static org.junit.Assert.assertNotNull;

import java.util.ArrayList;
import java.util.List;
import java.util.stream.Collectors;

import org.dspace.AbstractUnitTest;
import org.dspace.authorize.factory.AuthorizeServiceFactory;
import org.dspace.authorize.service.ResourcePolicyService;
import org.dspace.builder.AbstractBuilder;
import org.dspace.builder.CollectionBuilder;
import org.dspace.builder.CommunityBuilder;
import org.dspace.builder.ItemBuilder;
import org.dspace.builder.ResourcePolicyBuilder;
import org.dspace.content.Collection;
import org.dspace.content.Community;
import org.dspace.content.DSpaceObject;
import org.dspace.content.Item;
import org.dspace.core.Constants;
import org.dspace.eperson.Group;
import org.dspace.eperson.factory.EPersonServiceFactory;
import org.dspace.eperson.service.GroupService;
import org.junit.After;
import org.junit.Before;
import org.junit.Test;

/**
 * Verifies that the batched policy prefetch answers exactly what the individual lookups answer, so that turning it on
 * cannot change an authorization outcome.
 */
public class ResourcePolicyPrefetchTest extends AbstractUnitTest {

    private final ResourcePolicyService resourcePolicyService =
        AuthorizeServiceFactory.getInstance().getResourcePolicyService();
    private final GroupService groupService = EPersonServiceFactory.getInstance().getGroupService();

    private Community community;
    private Collection collection;
    private Item itemWithPolicy;
    private Item itemWithoutPolicy;
    private Group group;

    @Before
    @Override
    public void init() {
        super.init();
        AbstractBuilder.init(); // AbstractUnitTest doesn't do this for us.
    }

    @After
    @Override
    public void destroy() {
        community = null;
        collection = null;
        itemWithPolicy = null;
        itemWithoutPolicy = null;
        group = null;
        super.destroy();
    }

    @Test
    public void prefetchAnswersTheSameAsTheIndividualLookups() throws Exception {
        context.turnOffAuthorisationSystem();

        community = CommunityBuilder.createCommunity(context)
            .withName("Comunidade de teste")
            .build();
        collection = CollectionBuilder.createCollection(context, community)
            .withName("Colecao de teste")
            .build();
        itemWithPolicy = ItemBuilder.createItem(context, collection)
            .withTitle("Item com politica")
            .build();
        itemWithoutPolicy = ItemBuilder.createItem(context, collection)
            .withTitle("Item sem politica")
            .build();

        group = groupService.create(context);
        ResourcePolicyBuilder.createResourcePolicy(context, null, group)
            .withAction(Constants.WRITE)
            .withDspaceObject(itemWithPolicy)
            .build();

        context.restoreAuthSystemState();

        List<DSpaceObject> objects = List.of(itemWithPolicy, itemWithoutPolicy, collection, community);
        List<Integer> actions = List.of(Constants.WRITE, Constants.ADMIN, Constants.ADD);

        // The answers the database gives, one object and action at a time.
        List<List<Integer>> fromDatabase = new ArrayList<>();
        for (int action : actions) {
            for (DSpaceObject dso : objects) {
                fromDatabase.add(policyIds(resourcePolicyService.find(context, dso, action)));
            }
        }

        // The same questions, now answered from a single batched query per action.
        for (int action : actions) {
            resourcePolicyService.prefetch(context, objects, action);
        }

        int answer = 0;
        for (int action : actions) {
            for (DSpaceObject dso : objects) {
                assertEquals("policies of " + dso.getID() + " for action " + action,
                             fromDatabase.get(answer++),
                             policyIds(resourcePolicyService.find(context, dso, action)));
            }
        }

        // Objects with no policy must be remembered as having none, not as "unknown".
        for (int action : actions) {
            assertNotNull("the collection should have been prefetched for action " + action,
                          context.getPrefetchedPolicies(collection, action));
            assertNotNull("the item without a policy should have been prefetched for action " + action,
                          context.getPrefetchedPolicies(itemWithoutPolicy, action));
        }
    }

    private List<Integer> policyIds(List<ResourcePolicy> policies) {
        return policies.stream().map(ResourcePolicy::getID).sorted().collect(Collectors.toList());
    }
}

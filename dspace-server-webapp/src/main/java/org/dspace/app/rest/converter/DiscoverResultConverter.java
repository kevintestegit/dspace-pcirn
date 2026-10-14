/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.rest.converter;

import java.sql.SQLException;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Map;
import java.util.Set;

import org.apache.commons.collections4.CollectionUtils;
import org.apache.commons.collections4.MapUtils;
import org.apache.logging.log4j.LogManager;
import org.apache.logging.log4j.Logger;
import org.dspace.app.rest.converter.query.SearchQueryConverter;
import org.dspace.app.rest.model.RestAddressableModel;
import org.dspace.app.rest.model.SearchResultEntryRest;
import org.dspace.app.rest.model.SearchResultsRest;
import org.dspace.app.rest.parameter.SearchFilter;
import org.dspace.app.rest.projection.Projection;
import org.dspace.authorize.service.ResourcePolicyService;
import org.dspace.content.Collection;
import org.dspace.content.DSpaceObject;
import org.dspace.content.Item;
import org.dspace.content.service.CommunityService;
import org.dspace.core.Constants;
import org.dspace.core.Context;
import org.dspace.discovery.DiscoverResult;
import org.dspace.discovery.IndexableObject;
import org.dspace.discovery.configuration.DiscoveryConfiguration;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Pageable;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Component;

/**
 * This class' purpose is to create a SearchResultsRest object from the given parameters
 */
@Component
public class DiscoverResultConverter {

    private static final Logger log = LogManager.getLogger();

    @Autowired
    private List<IndexableObjectConverter> converters;

    @Autowired
    protected ConverterService converter;

    @Autowired
    private ResourcePolicyService resourcePolicyService;

    @Autowired
    private CommunityService communityService;

    @Autowired
    private DiscoverFacetsConverter facetConverter;
    @Autowired
    private SearchFilterToAppliedFilterConverter searchFilterToAppliedFilterConverter;

    public SearchResultsRest convert(final Context context, final String query, final List<String> dsoTypes,
                                     final String configurationName, final String scope,
                                     final List<SearchFilter> searchFilters, final Pageable page,
                                     final DiscoverResult searchResult, final DiscoveryConfiguration configuration,
                                     final Projection projection) {

        SearchResultsRest resultsRest = new SearchResultsRest();
        resultsRest.setProjection(projection);

        setRequestInformation(context, query, dsoTypes, configurationName, scope, searchFilters, page, resultsRest);

        prefetchPolicies(context, searchResult);

        addSearchResults(searchResult, resultsRest, projection);

        addFacetValues(context, searchResult, resultsRest, configuration, projection);

        resultsRest.setTotalNumberOfResults(searchResult.getTotalSearchResults());

        return resultsRest;
    }

    private void addFacetValues(Context context, final DiscoverResult searchResult, final SearchResultsRest resultsRest,
            final DiscoveryConfiguration configuration, final Projection projection) {
        facetConverter.addFacetValues(context, searchResult, resultsRest, configuration, projection);
    }

    private void addSearchResults(final DiscoverResult searchResult, final SearchResultsRest resultsRest,
                                  final Projection projection) {
        for (IndexableObject dspaceObject : CollectionUtils.emptyIfNull(searchResult.getIndexableObjects())) {
            SearchResultEntryRest resultEntry = new SearchResultEntryRest();
            resultEntry.setProjection(projection);

            //Convert the DSpace Object to its REST model
            resultEntry.setIndexableObject(convertDSpaceObject(dspaceObject, projection));

            //Add hit highlighting for this DSO if present
            DiscoverResult.IndexableObjectHighlightResult highlightedResults = searchResult
                .getHighlightedResults(dspaceObject);
            if (highlightedResults != null && MapUtils.isNotEmpty(highlightedResults.getHighlightResults())) {
                for (Map.Entry<String, List<String>> metadataHighlight : highlightedResults.getHighlightResults()
                                                                                           .entrySet()) {
                    resultEntry.addHitHighlights(metadataHighlight.getKey(), metadataHighlight.getValue());
                }
            }

            resultsRest.addSearchResult(resultEntry);
        }
    }

    /**
     * Loads, in one query per action, the policies of every object this page is about to convert. Converting an item
     * asks whether the current user may edit it, and that check walks up through its collection and the communities
     * above it; without this, the question is asked once per item and each answer costs database round trips.
     * <P>
     * This only moves the fetch: the policies, and the decisions taken from them, are unchanged. If anything is
     * missing, the individual lookups still happen, so this cannot change an authorization outcome.
     *
     * @param context      the DSpace context that keeps the prefetched policies
     * @param searchResult the page of results that is about to be converted
     */
    private void prefetchPolicies(final Context context, final DiscoverResult searchResult) {
        Set<DSpaceObject> objects = new LinkedHashSet<>();
        Set<Collection> collections = new LinkedHashSet<>();
        for (IndexableObject indexableObject : CollectionUtils.emptyIfNull(searchResult.getIndexableObjects())) {
            if (!(indexableObject.getIndexedObject() instanceof DSpaceObject)) {
                continue;
            }
            DSpaceObject dso = (DSpaceObject) indexableObject.getIndexedObject();
            objects.add(dso);
            if (dso instanceof Item) {
                Collection owningCollection = ((Item) dso).getOwningCollection();
                if (owningCollection != null) {
                    objects.add(owningCollection);
                    collections.add(owningCollection);
                }
            }
        }
        if (objects.isEmpty()) {
            return;
        }

        try {
            // Editing an item also asks whether the user may edit its collection, which walks up to the communities
            // above it. Those communities are collected here so that the walk does not become a query per item.
            for (Collection collection : collections) {
                objects.addAll(communityService.getAllParents(context, collection));
            }

            resourcePolicyService.prefetch(context, objects, Constants.WRITE);
            resourcePolicyService.prefetch(context, objects, Constants.ADMIN);
            resourcePolicyService.prefetch(context, objects, Constants.ADD);
        } catch (SQLException e) {
            // Prefetching is an optimization; the per-object lookups still answer correctly on their own.
            log.warn("Unable to prefetch resource policies for the search results page", e);
        }
    }

    private RestAddressableModel convertDSpaceObject(final IndexableObject indexableObject,
                                                     final Projection projection) {
        return converter.toRest(indexableObject.getIndexedObject(), projection);
    }

    private void setRequestInformation(final Context context, final String query, final List<String> dsoTypes,
                                       final String configurationName, final String scope,
                                       final List<SearchFilter> searchFilters, final Pageable page,
                                       final SearchResultsRest resultsRest) {
        resultsRest.setQuery(query);
        resultsRest.setConfiguration(configurationName);
        resultsRest.setDsoTypes(dsoTypes);

        resultsRest.setScope(scope);

        if (page != null && page.getSort() != null && page.getSort().iterator().hasNext()) {
            Sort.Order order = page.getSort().iterator().next();
            resultsRest.setSort(order.getProperty(), order.getDirection().name());
        }
        SearchQueryConverter searchQueryConverter = new SearchQueryConverter();
        List<SearchFilter> transformedFilters = searchQueryConverter.convert(searchFilters);

        for (SearchFilter searchFilter : CollectionUtils.emptyIfNull(transformedFilters)) {
            resultsRest
                    .addAppliedFilter(searchFilterToAppliedFilterConverter.convertSearchFilter(context, searchFilter));
        }
    }
}

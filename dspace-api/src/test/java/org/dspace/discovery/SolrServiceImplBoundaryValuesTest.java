/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.discovery;

import static org.junit.Assert.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.doReturn;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.spy;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.UUID;

import org.apache.solr.client.solrj.SolrClient;
import org.apache.solr.client.solrj.SolrRequest;
import org.dspace.core.Context;
import org.dspace.discovery.configuration.DiscoverySearchFilterFacet;
import org.dspace.eperson.EPerson;
import org.junit.Before;
import org.junit.Test;

/**
 * Verifies that the queries which only resolve the boundaries of a result set are not repeated for every search.
 * <P>
 * A single search issues the main query plus the queries needed to resolve the span of its date facets and the
 * minimum and maximum of the facets that expose them. Those answers do not depend on the text being searched for, so
 * they are cached for everything a user with the same permissions asks. This test pins both the sharing and its
 * limits: the cache must never mix two users, two filter selections or two different indexes.
 */
public class SolrServiceImplBoundaryValuesTest {

    private static final String VALUE_FIELD = "dateIssued_min";
    private static final String SORT_FIELD = "dateIssued_min_sort";
    private static final String DATE_FACET = "dateIssued";
    private static final String YEAR_FIELD = DATE_FACET + ".year";
    private static final String EXTREME_VALUE = "1959-08-14";
    private static final String YEAR = "1959";

    private SolrServiceImpl solrService;
    private SolrClient solrClient;

    @Before
    public void setUp() throws Exception {
        solrClient = mock(SolrClient.class);

        SolrSearchCore solrSearchCore = mock(SolrSearchCore.class);
        solrSearchCore.REQUEST_METHOD = SolrRequest.METHOD.POST;
        when(solrSearchCore.getSolr()).thenReturn(solrClient);

        solrService = spy(new SolrServiceImpl());
        solrService.solrSearchCore = solrSearchCore;
    }

    /**
     * The same anonymous user asking twice, in two different requests, must only reach Solr the first time.
     */
    @Test
    public void extremeValueIsReusedAcrossRequests() throws Exception {
        givenExtremeValue(EXTREME_VALUE);

        assertEquals(EXTREME_VALUE, solrService.calculateExtremeValue(
            anonymousContext(), VALUE_FIELD, SORT_FIELD, DiscoverQuery.SORT_ORDER.asc));
        assertEquals(EXTREME_VALUE, solrService.calculateExtremeValue(
            anonymousContext(), VALUE_FIELD, SORT_FIELD, DiscoverQuery.SORT_ORDER.asc));

        verify(solrService, times(1)).search(any(Context.class), any(DiscoverQuery.class));
    }

    /**
     * An authenticated user must not be served the boundaries that were resolved for somebody else.
     */
    @Test
    public void extremeValueIsNotSharedBetweenUsers() throws Exception {
        givenExtremeValue(EXTREME_VALUE);

        solrService.calculateExtremeValue(anonymousContext(), VALUE_FIELD, SORT_FIELD, DiscoverQuery.SORT_ORDER.asc);
        solrService.calculateExtremeValue(authenticatedContext(), VALUE_FIELD, SORT_FIELD,
            DiscoverQuery.SORT_ORDER.asc);

        verify(solrService, times(2)).search(any(Context.class), any(DiscoverQuery.class));
    }

    /**
     * The two directions of a boundary are cached apart: asking for the smallest value must not answer the largest.
     */
    @Test
    public void bothDirectionsAreCachedSeparately() throws Exception {
        givenExtremeValue(EXTREME_VALUE);

        solrService.calculateExtremeValue(anonymousContext(), VALUE_FIELD, SORT_FIELD, DiscoverQuery.SORT_ORDER.asc);
        solrService.calculateExtremeValue(anonymousContext(), VALUE_FIELD, SORT_FIELD, DiscoverQuery.SORT_ORDER.desc);

        verify(solrService, times(2)).search(any(Context.class), any(DiscoverQuery.class));
    }

    /**
     * An indexing operation makes what is cached obsolete, so the next search has to resolve it again.
     */
    @Test
    public void indexingInvalidatesTheCachedValues() throws Exception {
        givenExtremeValue(EXTREME_VALUE);

        solrService.calculateExtremeValue(anonymousContext(), VALUE_FIELD, SORT_FIELD, DiscoverQuery.SORT_ORDER.asc);
        solrService.atomicUpdate(anonymousContext(), "123456789/1", "database_status", Map.of("set", "ARCHIVED"));
        solrService.calculateExtremeValue(anonymousContext(), VALUE_FIELD, SORT_FIELD, DiscoverQuery.SORT_ORDER.asc);

        verify(solrService, times(2)).search(any(Context.class), any(DiscoverQuery.class));
    }

    /**
     * The span of a date facet must be reused across requests as well, and must come back with both ends.
     */
    @Test
    public void yearRangeIsReusedAcrossRequests() throws Exception {
        givenYear(YEAR);

        FacetYearRange first = solrService.getFacetYearRange(
            anonymousContext(), null, dateFacet(), List.of(), new DiscoverQuery());
        FacetYearRange second = solrService.getFacetYearRange(
            anonymousContext(), null, dateFacet(), List.of(), new DiscoverQuery());

        assertEquals(1959, first.getOldestYear());
        assertEquals(1959, first.getNewestYear());
        assertEquals("the cached span must be served as is", 1959, second.getOldestYear());
        assertEquals(1959, second.getNewestYear());
        // Both ends of the span come from their own query, so a cold span costs two.
        verify(solrService, times(2)).search(any(Context.class), any(DiscoverQuery.class));
    }

    /**
     * A span resolved for one selection of filters says nothing about another one.
     */
    @Test
    public void yearRangeIsNotSharedBetweenFilterSelections() throws Exception {
        givenYear(YEAR);

        solrService.getFacetYearRange(anonymousContext(), null, dateFacet(), List.of(), new DiscoverQuery());
        solrService.getFacetYearRange(anonymousContext(), null, dateFacet(),
            List.of("author_filter:silva"), new DiscoverQuery());

        verify(solrService, times(4)).search(any(Context.class), any(DiscoverQuery.class));
    }

    private DiscoverySearchFilterFacet dateFacet() {
        DiscoverySearchFilterFacet facet = mock(DiscoverySearchFilterFacet.class);
        when(facet.getIndexFieldName()).thenReturn(DATE_FACET);
        return facet;
    }

    private void givenExtremeValue(String value) throws Exception {
        doReturn(resultWith(VALUE_FIELD, value))
            .when(solrService).search(any(Context.class), any(DiscoverQuery.class));
    }

    private void givenYear(String year) throws Exception {
        doReturn(resultWith(YEAR_FIELD, year))
            .when(solrService).search(any(Context.class), any(DiscoverQuery.class));
    }

    /**
     * Builds the result Solr would have returned for a boundary query, with one document carrying the value.
     */
    private DiscoverResult resultWith(String field, String value) {
        IndexableObject indexableObject = mock(IndexableObject.class);

        DiscoverResult.SearchDocument searchDocument = new DiscoverResult.SearchDocument();
        searchDocument.addSearchField(field, value);

        DiscoverResult result = new DiscoverResult();
        result.addIndexableObject(indexableObject);
        result.addSearchDocument(indexableObject, searchDocument);
        return result;
    }

    /**
     * A Context of a request of a user that is not logged in. Its request cache behaves like the real one, so the
     * memoization of the permission scope actually happens.
     */
    private Context anonymousContext() {
        return contextFor(null, Set.of());
    }

    private Context authenticatedContext() {
        EPerson eperson = mock(EPerson.class);
        when(eperson.getID()).thenReturn(UUID.randomUUID());
        return contextFor(eperson, Set.of());
    }

    private Context contextFor(EPerson currentUser, Set<UUID> specialGroups) {
        Map<String, String> requestCache = new HashMap<>();
        Context context = mock(Context.class);
        when(context.getCurrentUser()).thenReturn(currentUser);
        when(context.getSpecialGroupUuids()).thenReturn(specialGroups);
        when(context.getCachedRequestValue(any(String.class)))
            .thenAnswer(invocation -> requestCache.get(invocation.getArgument(0, String.class)));
        doAnswer(invocation -> {
            requestCache.put(invocation.getArgument(0, String.class), invocation.getArgument(1, String.class));
            return null;
        }).when(context).cacheRequestValue(any(String.class), any(String.class));
        return context;
    }
}

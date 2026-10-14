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
import static org.mockito.ArgumentMatchers.anyString;
import static org.mockito.Mockito.doAnswer;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.times;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.when;

import java.util.HashMap;
import java.util.Map;

import org.apache.solr.client.solrj.SolrClient;
import org.apache.solr.client.solrj.SolrRequest;
import org.apache.solr.client.solrj.response.QueryResponse;
import org.apache.solr.common.SolrDocument;
import org.apache.solr.common.SolrDocumentList;
import org.apache.solr.common.params.SolrParams;
import org.apache.solr.common.util.NamedList;
import org.dspace.core.Context;
import org.dspace.discovery.indexobject.IndexableCollection;
import org.junit.Before;
import org.junit.Test;

/**
 * Verifies that the "location" query of the administrable communities and collections is computed once per Context.
 * <P>
 * A single Discovery search issues several Solr queries (the main one plus the ones needed to resolve the year range
 * and the facet boundaries) and every one of them asks for the same permission filter. Without memoization the same
 * lookup is repeated once per query.
 */
public class SolrServiceImplAdministrableLocationsTest {

    private static final String CLAUSE = "g0";

    private SolrServiceImpl solrService;
    private SolrClient solrClient;
    private Context context;

    private final Map<String, String> requestCache = new HashMap<>();

    @Before
    public void setUp() throws Exception {
        solrClient = mock(SolrClient.class);

        SolrSearchCore solrSearchCore = mock(SolrSearchCore.class);
        solrSearchCore.REQUEST_METHOD = SolrRequest.METHOD.POST;
        when(solrSearchCore.getSolr()).thenReturn(solrClient);

        solrService = new SolrServiceImpl();
        solrService.solrSearchCore = solrSearchCore;

        // A Context whose request cache behaves like the real one, so memoization actually happens.
        context = mock(Context.class);
        when(context.getCachedRequestValue(anyString()))
            .thenAnswer(invocation -> requestCache.get(invocation.getArgument(0, String.class)));
        doAnswer(invocation -> {
            requestCache.put(invocation.getArgument(0, String.class), invocation.getArgument(1, String.class));
            return null;
        }).when(context).cacheRequestValue(anyString(), anyString());
    }

    /**
     * Calling the method twice for the same Context must query Solr only once.
     */
    @Test
    public void locationQueryIsResolvedOnlyOncePerContext() throws Exception {
        givenAdministrableCollection("abc");

        String first = solrService.createLocationQueryForAdministrableDSOs(context, CLAUSE);
        String second = solrService.createLocationQueryForAdministrableDSOs(context, CLAUSE);

        assertEquals("location:(labc)", first);
        assertEquals("the memoized value must be returned as is", first, second);
        verify(solrClient, times(1)).query(any(SolrParams.class), any(SolrRequest.METHOD.class));
    }

    /**
     * Two different users (two different clauses) must not share a cache entry.
     */
    @Test
    public void differentClausesAreResolvedSeparately() throws Exception {
        givenAdministrableCollection("abc");

        solrService.createLocationQueryForAdministrableDSOs(context, "g0");
        solrService.createLocationQueryForAdministrableDSOs(context, "g1");
        solrService.createLocationQueryForAdministrableDSOs(context, "g0");

        verify(solrClient, times(2)).query(any(SolrParams.class), any(SolrRequest.METHOD.class));
    }

    /**
     * A user with no administrable community or collection is memoized as well, so the empty answer is not recomputed
     * for every query of the search.
     */
    @Test
    public void emptyResultIsMemoized() throws Exception {
        givenNoAdministrableCollection();

        assertEquals("", solrService.createLocationQueryForAdministrableDSOs(context, CLAUSE));
        assertEquals("", solrService.createLocationQueryForAdministrableDSOs(context, CLAUSE));

        verify(solrClient, times(1)).query(any(SolrParams.class), any(SolrRequest.METHOD.class));
    }

    private void givenAdministrableCollection(String uniqueId) throws Exception {
        when(solrClient.query(any(SolrParams.class), any(SolrRequest.METHOD.class)))
            .thenReturn(responseWithCollection(uniqueId));
    }

    private void givenNoAdministrableCollection() throws Exception {
        when(solrClient.query(any(SolrParams.class), any(SolrRequest.METHOD.class)))
            .thenReturn(emptyResponse());
    }

    private QueryResponse responseWithCollection(String uniqueId) {
        SolrDocument document = new SolrDocument();
        document.setField(SearchUtils.RESOURCE_ID_FIELD, uniqueId);
        document.setField(SearchUtils.RESOURCE_TYPE_FIELD, IndexableCollection.TYPE);

        SolrDocumentList results = new SolrDocumentList();
        results.setNumFound(1);
        results.add(document);

        return responseWith(results);
    }

    private QueryResponse emptyResponse() {
        SolrDocumentList results = new SolrDocumentList();
        results.setNumFound(0);

        return responseWith(results);
    }

    private QueryResponse responseWith(SolrDocumentList results) {
        NamedList<Object> response = new NamedList<>();
        response.add("response", results);

        QueryResponse queryResponse = new QueryResponse();
        queryResponse.setResponse(response);
        return queryResponse;
    }
}

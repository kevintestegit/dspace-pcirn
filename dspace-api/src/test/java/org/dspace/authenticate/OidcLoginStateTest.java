/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.authenticate;

import static org.junit.Assert.assertEquals;
import static org.mockito.ArgumentMatchers.any;
import static org.mockito.ArgumentMatchers.eq;
import static org.mockito.Mockito.mock;
import static org.mockito.Mockito.verify;
import static org.mockito.Mockito.verifyNoInteractions;
import static org.mockito.Mockito.verifyNoMoreInteractions;
import static org.mockito.Mockito.when;

import java.util.Map;

import org.apache.http.client.utils.URIBuilder;
import org.dspace.authenticate.oidc.OidcClient;
import org.dspace.authenticate.oidc.model.OidcTokenResponseDTO;
import org.dspace.core.Context;
import org.dspace.eperson.EPerson;
import org.dspace.eperson.service.EPersonService;
import org.dspace.services.ConfigurationService;
import org.junit.Before;
import org.junit.Test;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpSession;
import org.springframework.test.util.ReflectionTestUtils;

/** Tests browser binding and atomic, expiring OIDC state consumption. */
public class OidcLoginStateTest {
    private OidcAuthenticationBean authentication;
    private OidcClient client;
    private Context context;

    @Before
    public void setup() {
        authentication = new OidcAuthenticationBean();
        client = mock(OidcClient.class);
        context = mock(Context.class);
        ConfigurationService config = mock(ConfigurationService.class);
        for (String key : new String[] {"authorize-endpoint", "client-id", "client-secret", "redirect-url",
            "token-endpoint", "user-info-endpoint"}) {
            when(config.getProperty("authentication-oidc." + key)).thenReturn("https://provider.example/" + key);
        }
        when(config.getArrayProperty(eq("authentication-oidc.scopes"), any(String[].class)))
            .thenReturn(new String[] {"openid", "email"});
        when(config.getProperty("authentication-oidc.user-info.email", "email")).thenReturn("email");
        ReflectionTestUtils.setField(authentication, "configurationService", config);
        authentication.setOidcClient(client);
    }

    @Test
    public void rejectsCallbackWithoutInitiation() throws Exception {
        MockHttpServletRequest request = callback();
        request.setParameter("state", "attacker-state");
        authentication.authenticate(context, null, null, null, request);
        verifyNoInteractions(client);
    }

    @Test
    public void rejectsMissingMismatchedExpiredAndOtherBrowserState() throws Exception {
        for (String scenario : new String[] {"missing", "mismatch", "expired", "other-browser"}) {
            MockHttpServletRequest request = callback();
            initiate(request);
            if ("missing".equals(scenario)) {
                request.removeParameter("state");
            } else if ("mismatch".equals(scenario)) {
                request.setParameter("state", "attacker-state");
            } else if ("expired".equals(scenario)) {
                request.getSession().setAttribute("oidc.login.expiry", 0L);
            } else {
                request.setSession(new MockHttpSession());
            }
            authentication.authenticate(context, null, null, null, request);
        }
        verifyNoInteractions(client);
    }

    @Test
    public void acceptsValidLoginAndRejectsReplay() throws Exception {
        MockHttpServletRequest request = callback();
        initiate(request);
        OidcTokenResponseDTO token = new OidcTokenResponseDTO();
        token.setAccessToken("access-token");
        when(client.getAccessToken("code")).thenReturn(token);
        when(client.getUserInfo("access-token")).thenReturn(Map.of("email", "user@example.org"));
        EPersonService people = mock(EPersonService.class);
        EPerson person = mock(EPerson.class);
        when(people.findByEmail(context, "user@example.org")).thenReturn(person);
        when(person.canLogIn()).thenReturn(true);
        ReflectionTestUtils.setField(authentication, "ePersonService", people);
        assertEquals(AuthenticationMethod.SUCCESS, authentication.authenticate(context, null, null, null, request));
        verify(context).setCurrentUser(person);
        authentication.authenticate(context, null, null, null, request);
        verify(client).getAccessToken("code");
        verify(client).getUserInfo("access-token");
        verifyNoMoreInteractions(client);
    }

    @Test
    public void consumesStateEvenWhenExchangeFails() throws Exception {
        MockHttpServletRequest request = callback();
        initiate(request);
        authentication.authenticate(context, null, null, null, request);
        authentication.authenticate(context, null, null, null, request);
        verify(client).getAccessToken("code");
        verifyNoMoreInteractions(client);
    }

    private void initiate(MockHttpServletRequest request) throws Exception {
        String url = authentication.startLogin(request);
        String state = new URIBuilder(url).getQueryParams().stream()
            .filter(parameter -> "state".equals(parameter.getName())).findFirst().orElseThrow().getValue();
        request.setParameter("state", state);
    }

    private MockHttpServletRequest callback() {
        MockHttpServletRequest request = new MockHttpServletRequest();
        request.setAttribute(OidcAuthenticationBean.OIDC_AUTH_ATTRIBUTE, "oidc");
        request.setParameter("code", "code");
        return request;
    }
}

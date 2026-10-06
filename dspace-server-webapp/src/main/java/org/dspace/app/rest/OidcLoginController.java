/**
 * The contents of this file are subject to the license and copyright
 * detailed in the LICENSE and NOTICE files at the root of the source
 * tree and available online at
 *
 * http://www.dspace.org/license/
 */
package org.dspace.app.rest;

import java.io.IOException;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import org.dspace.authenticate.OidcAuthenticationBean;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RestController;

/**
 * Browser entry point for an OIDC transaction bound to the initiating session.
 */
@RestController
public class OidcLoginController {
    @Autowired
    private OidcAuthenticationBean oidcAuthentication;

    /**
     * Start login and navigate to the configured provider.
     * @param request browser request
     * @param response redirect response
     * @throws IOException if the redirect cannot be sent
     */
    @GetMapping("/api/authn/oidc/login")
    public void login(HttpServletRequest request, HttpServletResponse response) throws IOException {
        response.setHeader("Cache-Control", "no-store");
        String location = oidcAuthentication.startLogin(request);
        if (location.isEmpty()) {
            response.sendError(HttpServletResponse.SC_SERVICE_UNAVAILABLE);
            return;
        }
        response.sendRedirect(location);
    }
}

package com.taxpilot.gateway.service;

import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.core.io.ByteArrayResource;
import org.springframework.http.*;
import org.springframework.stereotype.Service;
import org.springframework.util.MultiValueMap;
import org.springframework.web.client.RestTemplate;
import org.springframework.web.util.UriComponentsBuilder;

import java.net.URI;
import java.util.Map;

/**
 * Routes requests from the gateway → Python FastAPI engine.
 * Strips the /gateway prefix and forwards with the same method/body.
 *
 * The Python engine trusts requests from the gateway network only —
 * it is NOT exposed on a public port in production.
 */
@Slf4j
@Service
public class ProxyService {

    private final RestTemplate restTemplate;
    private final String       pythonBaseUrl;

    public ProxyService(
            RestTemplate restTemplate,
            @Value("${app.python-engine.base-url}") String pythonBaseUrl) {
        this.restTemplate  = restTemplate;
        this.pythonBaseUrl = pythonBaseUrl;
    }

    /**
     * Forward a request to the Python engine.
     *
     * @param path         Python-engine path  e.g. "/api/v1/transactions/42/categorize"
     * @param method       HTTP method
     * @param queryParams  Query params map (may be null)
     * @param body         Request body (may be null)
     * @param contentType  Content-Type of body
     */
    public ResponseEntity<byte[]> forward(
            String path,
            HttpMethod method,
            Map<String, String> queryParams,
            byte[] body,
            MediaType contentType
    ) {
        UriComponentsBuilder builder = UriComponentsBuilder
                .fromUriString(pythonBaseUrl + path);

        if (queryParams != null) {
            queryParams.forEach(builder::queryParam);
        }
        URI uri = builder.build().encode().toUri();

        HttpHeaders headers = new HttpHeaders();
        if (contentType != null && body != null) {
            headers.setContentType(contentType);
        }

        HttpEntity<byte[]> entity = (body != null && body.length > 0)
                ? new HttpEntity<>(body, headers)
                : new HttpEntity<>(headers);

        log.debug("Proxying {} {}", method, uri);
        try {
            return restTemplate.exchange(uri, method, entity, byte[].class);
        } catch (Exception ex) {
            log.error("Proxy error for {} {}: {}", method, uri, ex.getMessage());
            return ResponseEntity.status(HttpStatus.BAD_GATEWAY)
                    .body(("Python engine error: " + ex.getMessage()).getBytes());
        }
    }
}

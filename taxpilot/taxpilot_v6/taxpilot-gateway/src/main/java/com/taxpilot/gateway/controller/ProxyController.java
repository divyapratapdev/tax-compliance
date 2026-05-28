package com.taxpilot.gateway.controller;

import com.taxpilot.gateway.service.ProxyService;
import com.taxpilot.gateway.service.UsageMeteringService;
import com.taxpilot.gateway.util.JwtUtil;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.http.HttpMethod;
import org.springframework.http.HttpStatus;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * Catch-all proxy: forwards every /api/v1/* request (except /auth, /clients, /usage)
 * to the Python engine after JWT auth + rate-limit check.
 *
 * Path mapping:
 *   Gateway:        /api/v1/engine/**
 *   Python engine:  /api/v1/**
 *
 * Example: GET /api/v1/engine/compliance/42
 *       →  GET http://ingestion-service:8000/api/v1/compliance/42
 */
@Slf4j
@RestController
@RequestMapping("/api/v1/engine")
@RequiredArgsConstructor
public class ProxyController {

    private final ProxyService          proxyService;
    private final UsageMeteringService  meteringService;
    private final JwtUtil               jwtUtil;

    @RequestMapping("/**")
    public ResponseEntity<byte[]> proxy(
            HttpServletRequest req,
            @RequestBody(required = false) byte[] body
    ) throws IOException {

        // 1. Identify firm
        Long   firmId = extractFirmId(req);
        String plan   = extractPlan(req);

        // 2. Rate-limit check
        if (meteringService.isRateLimitExceeded(firmId, plan)) {
            return ResponseEntity.status(HttpStatus.TOO_MANY_REQUESTS)
                    .body("Daily API limit reached for your plan. Upgrade at taxpilot.in".getBytes());
        }

        // 3. Record usage
        meteringService.record(firmId, req.getRequestURI());

        // 4. Build target path: strip /api/v1/engine prefix, keep the rest
        String fullPath    = req.getRequestURI();                         // /api/v1/engine/gst/recon
        String enginePath  = fullPath.replaceFirst("/api/v1/engine", "/api/v1");  // /api/v1/gst/recon

        // 5. Collect query params
        Map<String, String> queryParams = new HashMap<>();
        req.getParameterMap().forEach((k, v) -> {
            if (v != null && v.length > 0) queryParams.put(k, v[0]);
        });

        // 6. Determine Content-Type
        MediaType contentType = null;
        String ct = req.getContentType();
        if (ct != null) {
            try { contentType = MediaType.parseMediaType(ct); }
            catch (Exception ignored) { }
        }

        // 7. Forward
        HttpMethod method = HttpMethod.valueOf(req.getMethod());
        return proxyService.forward(enginePath, method, queryParams, body, contentType);
    }

    private Long extractFirmId(HttpServletRequest req) {
        String header = req.getHeader("Authorization");
        if (StringUtils.hasText(header) && header.startsWith("Bearer ")) {
            return jwtUtil.extractFirmId(header.substring(7));
        }
        throw new IllegalStateException("Missing token");
    }

    private String extractPlan(HttpServletRequest req) {
        String header = req.getHeader("Authorization");
        if (StringUtils.hasText(header) && header.startsWith("Bearer ")) {
            String plan = jwtUtil.extractPlan(header.substring(7));
            return plan != null ? plan : "starter";
        }
        return "starter";
    }
}

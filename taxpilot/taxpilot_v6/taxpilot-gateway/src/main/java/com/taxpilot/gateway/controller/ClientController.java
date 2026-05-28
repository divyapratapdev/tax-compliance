package com.taxpilot.gateway.controller;

import com.taxpilot.gateway.dto.request.CreateClientRequest;
import com.taxpilot.gateway.dto.response.ApiResponse;
import com.taxpilot.gateway.dto.response.ClientResponse;
import com.taxpilot.gateway.service.ClientService;
import com.taxpilot.gateway.util.JwtUtil;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

import java.util.List;

@RestController
@RequestMapping("/api/v1/clients")
@RequiredArgsConstructor
public class ClientController {

    private final ClientService clientService;
    private final JwtUtil       jwtUtil;

    @PostMapping
    public ResponseEntity<ApiResponse<ClientResponse>> create(
            @Valid @RequestBody CreateClientRequest req,
            HttpServletRequest httpReq) {
        Long firmId = extractFirmId(httpReq);
        ClientResponse resp = clientService.createClient(firmId, req);
        return ResponseEntity.status(201).body(ApiResponse.ok("Client created", resp));
    }

    @GetMapping
    public ResponseEntity<ApiResponse<List<ClientResponse>>> list(HttpServletRequest httpReq) {
        Long firmId = extractFirmId(httpReq);
        return ResponseEntity.ok(ApiResponse.ok(clientService.listClients(firmId)));
    }

    @GetMapping("/{clientId}")
    public ResponseEntity<ApiResponse<ClientResponse>> get(
            @PathVariable Long clientId, HttpServletRequest httpReq) {
        Long firmId = extractFirmId(httpReq);
        return ResponseEntity.ok(ApiResponse.ok(clientService.getClient(firmId, clientId)));
    }

    @DeleteMapping("/{clientId}")
    public ResponseEntity<ApiResponse<Void>> deactivate(
            @PathVariable Long clientId, HttpServletRequest httpReq) {
        Long firmId = extractFirmId(httpReq);
        clientService.deactivateClient(firmId, clientId);
        return ResponseEntity.ok(ApiResponse.ok("Client deactivated", null));
    }

    private Long extractFirmId(HttpServletRequest req) {
        String header = req.getHeader("Authorization");
        if (StringUtils.hasText(header) && header.startsWith("Bearer ")) {
            return jwtUtil.extractFirmId(header.substring(7));
        }
        throw new IllegalStateException("No valid token");
    }
}

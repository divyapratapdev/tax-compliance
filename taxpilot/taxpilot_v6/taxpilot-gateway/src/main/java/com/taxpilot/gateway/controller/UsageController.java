package com.taxpilot.gateway.controller;

import com.taxpilot.gateway.dto.response.ApiResponse;
import com.taxpilot.gateway.dto.response.UsageSummaryResponse;
import com.taxpilot.gateway.service.UsageMeteringService;
import com.taxpilot.gateway.util.JwtUtil;
import jakarta.servlet.http.HttpServletRequest;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.util.StringUtils;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/usage")
@RequiredArgsConstructor
public class UsageController {

    private final UsageMeteringService meteringService;
    private final JwtUtil              jwtUtil;

    @GetMapping("/summary")
    public ResponseEntity<ApiResponse<UsageSummaryResponse>> summary(
            HttpServletRequest req) {
        Long firmId = extractFirmId(req);
        return ResponseEntity.ok(ApiResponse.ok(meteringService.getSummary(firmId)));
    }

    private Long extractFirmId(HttpServletRequest req) {
        String header = req.getHeader("Authorization");
        if (StringUtils.hasText(header) && header.startsWith("Bearer ")) {
            return jwtUtil.extractFirmId(header.substring(7));
        }
        throw new IllegalStateException("No valid token");
    }
}

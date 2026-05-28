package com.taxpilot.gateway.controller;

import com.taxpilot.gateway.dto.request.LoginRequest;
import com.taxpilot.gateway.dto.request.SignupRequest;
import com.taxpilot.gateway.dto.response.ApiResponse;
import com.taxpilot.gateway.dto.response.AuthResponse;
import com.taxpilot.gateway.service.AuthService;
import jakarta.validation.Valid;
import lombok.RequiredArgsConstructor;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/v1/auth")
@RequiredArgsConstructor
public class AuthController {

    private final AuthService authService;

    @PostMapping("/signup")
    public ResponseEntity<ApiResponse<AuthResponse>> signup(
            @Valid @RequestBody SignupRequest req) {
        AuthResponse resp = authService.signup(req);
        return ResponseEntity.status(201)
                .body(ApiResponse.ok("CA firm registered successfully", resp));
    }

    @PostMapping("/login")
    public ResponseEntity<ApiResponse<AuthResponse>> login(
            @Valid @RequestBody LoginRequest req) {
        AuthResponse resp = authService.login(req);
        return ResponseEntity.ok(ApiResponse.ok("Login successful", resp));
    }
}

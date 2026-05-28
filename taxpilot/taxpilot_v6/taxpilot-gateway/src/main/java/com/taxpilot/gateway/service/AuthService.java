package com.taxpilot.gateway.service;

import com.taxpilot.gateway.dto.request.LoginRequest;
import com.taxpilot.gateway.dto.request.SignupRequest;
import com.taxpilot.gateway.dto.response.AuthResponse;
import com.taxpilot.gateway.entity.CAFirm;
import com.taxpilot.gateway.repository.CAFirmRepository;
import com.taxpilot.gateway.util.JwtUtil;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.security.authentication.AuthenticationManager;
import org.springframework.security.authentication.UsernamePasswordAuthenticationToken;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

@Slf4j
@Service
@RequiredArgsConstructor
public class AuthService {

    private final CAFirmRepository caFirmRepository;
    private final PasswordEncoder  passwordEncoder;
    private final JwtUtil          jwtUtil;
    private final AuthenticationManager authManager;

    @Transactional
    public AuthResponse signup(SignupRequest req) {
        if (caFirmRepository.existsByEmail(req.getEmail())) {
            throw new IllegalArgumentException("Email already registered");
        }
        if (caFirmRepository.existsByRegistrationNumber(req.getRegistrationNumber())) {
            throw new IllegalArgumentException("Registration number already in use");
        }

        CAFirm firm = CAFirm.builder()
                .name(req.getName())
                .registrationNumber(req.getRegistrationNumber())
                .email(req.getEmail())
                .passwordHash(passwordEncoder.encode(req.getPassword()))
                .phone(req.getPhone())
                .plan(req.getPlan() != null ? req.getPlan() : "starter")
                .isActive(true)
                .build();

        firm = caFirmRepository.save(firm);
        log.info("New CA firm registered: {} ({})", firm.getName(), firm.getEmail());
        return buildAuthResponse(firm);
    }

    public AuthResponse login(LoginRequest req) {
        authManager.authenticate(
            new UsernamePasswordAuthenticationToken(req.getEmail(), req.getPassword())
        );
        CAFirm firm = caFirmRepository.findByEmail(req.getEmail())
                .orElseThrow(() -> new IllegalArgumentException("Firm not found"));
        return buildAuthResponse(firm);
    }

    private AuthResponse buildAuthResponse(CAFirm firm) {
        String access  = jwtUtil.generateAccessToken(firm.getId(), firm.getEmail(), firm.getPlan());
        String refresh = jwtUtil.generateRefreshToken(firm.getId(), firm.getEmail());
        return AuthResponse.builder()
                .accessToken(access)
                .refreshToken(refresh)
                .tokenType("Bearer")
                .expiresIn(jwtUtil.getExpirationMs() / 1000)
                .firmId(firm.getId())
                .firmName(firm.getName())
                .email(firm.getEmail())
                .plan(firm.getPlan())
                .build();
    }
}

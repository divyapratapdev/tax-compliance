package com.taxpilot.gateway.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;
import java.time.LocalDateTime;

@Entity
@Table(name = "ca_firms")
@Data @NoArgsConstructor @AllArgsConstructor @Builder
public class CAFirm {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(nullable = false)
    private String name;

    @Column(name = "registration_number", unique = true, nullable = false, length = 50)
    private String registrationNumber;

    @Column(unique = true, nullable = false)
    private String email;

    /** BCrypt-hashed password */
    @Column(name = "password_hash", nullable = false)
    private String passwordHash;

    /** Plan: starter | growth | scale | enterprise */
    @Column(nullable = false)
    @Builder.Default
    private String plan = "starter";

    /** Phone number for WhatsApp alerts */
    @Column(length = 20)
    private String phone;

    @Column(name = "is_active")
    @Builder.Default
    private Boolean isActive = true;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @Column(name = "updated_at")
    private LocalDateTime updatedAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
        updatedAt = LocalDateTime.now();
    }

    @PreUpdate
    protected void onUpdate() {
        updatedAt = LocalDateTime.now();
    }
}

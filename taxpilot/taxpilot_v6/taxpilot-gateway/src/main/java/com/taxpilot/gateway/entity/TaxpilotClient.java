package com.taxpilot.gateway.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;
import java.time.LocalDateTime;

/**
 * A client company managed by a CA firm.
 * id here MUST match the client_id used in the Python engine.
 */
@Entity
@Table(name = "clients")
@Data @NoArgsConstructor @AllArgsConstructor @Builder
public class TaxpilotClient {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "ca_firm_id", nullable = false)
    private Long caFirmId;

    @Column(name = "company_name", nullable = false)
    private String companyName;

    @Column(length = 15, unique = true)
    private String gstin;

    @Column(length = 10, unique = true)
    private String pan;

    /** small | medium | large */
    @Column(name = "turnover_category", length = 50)
    private String turnoverCategory;

    /** regular | composition */
    @Column(name = "registration_type", length = 50)
    private String registrationType;

    /** Email for compliance alerts */
    private String email;

    /** Phone for WhatsApp alerts */
    @Column(length = 20)
    private String phone;

    @Column(name = "is_active")
    @Builder.Default
    private Boolean isActive = true;

    @Column(name = "created_at", updatable = false)
    private LocalDateTime createdAt;

    @PrePersist
    protected void onCreate() {
        createdAt = LocalDateTime.now();
    }
}

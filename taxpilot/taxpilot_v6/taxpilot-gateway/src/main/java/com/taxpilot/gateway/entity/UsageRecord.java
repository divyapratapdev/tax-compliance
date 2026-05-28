package com.taxpilot.gateway.entity;

import jakarta.persistence.*;
import lombok.Data;
import lombok.NoArgsConstructor;
import lombok.AllArgsConstructor;
import lombok.Builder;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * Hourly flush of per-CA-firm API call counts from Redis → MySQL.
 * One row per (ca_firm_id, date, endpoint_group).
 */
@Entity
@Table(
    name = "usage_records",
    uniqueConstraints = @UniqueConstraint(
        columnNames = {"ca_firm_id", "usage_date", "endpoint_group"}
    )
)
@Data @NoArgsConstructor @AllArgsConstructor @Builder
public class UsageRecord {

    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;

    @Column(name = "ca_firm_id", nullable = false)
    private Long caFirmId;

    @Column(name = "usage_date", nullable = false)
    private LocalDate usageDate;

    /** Coarse grouping: ingestion | gst | tds | compliance | returns */
    @Column(name = "endpoint_group", nullable = false, length = 50)
    private String endpointGroup;

    @Column(name = "call_count", nullable = false)
    @Builder.Default
    private Long callCount = 0L;

    @Column(name = "last_flushed_at")
    private LocalDateTime lastFlushedAt;
}

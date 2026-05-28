package com.taxpilot.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.util.Map;

@Data @Builder @NoArgsConstructor @AllArgsConstructor
public class UsageSummaryResponse {
    private Long caFirmId;
    private String plan;
    private int dailyLimit;           // -1 = unlimited
    private long callsToday;
    private long callsThisMonth;
    private Map<String, Long> byEndpointGroup;   // ingestion→120, gst→45 …
    private boolean limitReached;
}

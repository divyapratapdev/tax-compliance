package com.taxpilot.gateway.service;

import com.taxpilot.gateway.dto.response.UsageSummaryResponse;
import com.taxpilot.gateway.entity.CAFirm;
import com.taxpilot.gateway.entity.UsageRecord;
import com.taxpilot.gateway.repository.CAFirmRepository;
import com.taxpilot.gateway.repository.UsageRecordRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.data.redis.core.StringRedisTemplate;
import org.springframework.scheduling.annotation.Scheduled;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.util.*;
import java.util.concurrent.TimeUnit;

/**
 * Usage metering:
 *   - Each API call → increment Redis key  usage:{firmId}:{date}:{group}
 *   - @Scheduled hourly job flushes Redis counts → MySQL usage_records
 *   - RateLimit check reads from Redis (fast) with MySQL fallback
 */
@Slf4j
@Service
@RequiredArgsConstructor
public class UsageMeteringService {

    private static final Map<String, Integer> PLAN_LIMITS = Map.of(
        "starter",    500,
        "growth",     2000,
        "scale",      10000,
        "enterprise", -1
    );

    private static final List<String> ENDPOINT_GROUPS = List.of(
        "ingestion", "gst", "tds", "compliance", "returns"
    );

    private final StringRedisTemplate       redis;
    private final UsageRecordRepository     usageRepo;
    private final CAFirmRepository          firmRepo;

    @Value("${app.metering.redis-key-prefix:usage:}")
    private String keyPrefix;

    // ── Record a call ─────────────────────────────────────────────────────

    public void record(Long caFirmId, String requestPath) {
        String group = pathToGroup(requestPath);
        String key   = redisKey(caFirmId, LocalDate.now(), group);
        redis.opsForValue().increment(key);
        // Set TTL of 48h so orphan keys don't pile up
        redis.expire(key, 48, TimeUnit.HOURS);
    }

    // ── Rate limit check ──────────────────────────────────────────────────

    public boolean isRateLimitExceeded(Long caFirmId, String plan) {
        int limit = PLAN_LIMITS.getOrDefault(plan, 500);
        if (limit == -1) return false;   // enterprise = unlimited

        long today = callsToday(caFirmId);
        return today >= limit;
    }

    public long callsToday(Long caFirmId) {
        LocalDate today = LocalDate.now();
        long total = 0;
        for (String group : ENDPOINT_GROUPS) {
            String val = redis.opsForValue().get(redisKey(caFirmId, today, group));
            if (val != null) total += Long.parseLong(val);
        }
        return total;
    }

    // ── Summary for dashboard ─────────────────────────────────────────────

    public UsageSummaryResponse getSummary(Long caFirmId) {
        CAFirm firm = firmRepo.findById(caFirmId)
                .orElseThrow(() -> new IllegalArgumentException("Firm not found"));

        LocalDate today     = LocalDate.now();
        LocalDate monthStart = today.withDayOfMonth(1);

        long todayCalls  = callsToday(caFirmId);
        Long monthCalls  = usageRepo.sumCallCountByFirmAndDate(caFirmId, today);
        // add today's Redis count (not yet flushed)
        long thisMonth   = (monthCalls == null ? 0 : monthCalls) + todayCalls;

        Map<String, Long> byGroup = new LinkedHashMap<>();
        for (String group : ENDPOINT_GROUPS) {
            String val = redis.opsForValue().get(redisKey(caFirmId, today, group));
            byGroup.put(group, val == null ? 0L : Long.parseLong(val));
        }

        int limit = PLAN_LIMITS.getOrDefault(firm.getPlan(), 500);

        return UsageSummaryResponse.builder()
                .caFirmId(caFirmId)
                .plan(firm.getPlan())
                .dailyLimit(limit)
                .callsToday(todayCalls)
                .callsThisMonth(thisMonth)
                .byEndpointGroup(byGroup)
                .limitReached(limit != -1 && todayCalls >= limit)
                .build();
    }

    // ── Hourly flush: Redis → MySQL ───────────────────────────────────────

    @Scheduled(fixedDelayString = "${app.metering.flush-interval-seconds:3600}000")
    @Transactional
    public void flushToDatabase() {
        log.info("Usage metering flush started");
        LocalDate today = LocalDate.now();

        List<CAFirm> firms = firmRepo.findAll();
        int flushed = 0;

        for (CAFirm firm : firms) {
            for (String group : ENDPOINT_GROUPS) {
                String key = redisKey(firm.getId(), today, group);
                String val = redis.opsForValue().get(key);
                if (val == null || Long.parseLong(val) == 0) continue;

                long count = Long.parseLong(val);
                Optional<UsageRecord> existing = usageRepo
                    .findByCaFirmIdAndUsageDateAndEndpointGroup(firm.getId(), today, group);

                if (existing.isPresent()) {
                    UsageRecord rec = existing.get();
                    rec.setCallCount(rec.getCallCount() + count);
                    rec.setLastFlushedAt(LocalDateTime.now());
                    usageRepo.save(rec);
                } else {
                    usageRepo.save(UsageRecord.builder()
                        .caFirmId(firm.getId())
                        .usageDate(today)
                        .endpointGroup(group)
                        .callCount(count)
                        .lastFlushedAt(LocalDateTime.now())
                        .build());
                }
                // Reset Redis counter after flush
                redis.opsForValue().set(key, "0");
                flushed++;
            }
        }
        log.info("Usage metering flush complete: {} records written", flushed);
    }

    // ── Helpers ───────────────────────────────────────────────────────────

    private String redisKey(Long firmId, LocalDate date, String group) {
        return keyPrefix + firmId + ":" + date + ":" + group;
    }

    static String pathToGroup(String path) {
        if (path == null) return "other";
        if (path.contains("/documents") || path.contains("/bank-statement") ||
            path.contains("/invoice"))         return "ingestion";
        if (path.contains("/gst"))              return "gst";
        if (path.contains("/tds"))              return "tds";
        if (path.contains("/compliance"))       return "compliance";
        if (path.contains("/returns"))          return "returns";
        return "other";
    }
}

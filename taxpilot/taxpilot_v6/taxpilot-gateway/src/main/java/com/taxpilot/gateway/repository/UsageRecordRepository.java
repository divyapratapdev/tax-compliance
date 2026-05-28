package com.taxpilot.gateway.repository;

import com.taxpilot.gateway.entity.UsageRecord;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.stereotype.Repository;
import java.time.LocalDate;
import java.util.List;
import java.util.Optional;

@Repository
public interface UsageRecordRepository extends JpaRepository<UsageRecord, Long> {

    Optional<UsageRecord> findByCaFirmIdAndUsageDateAndEndpointGroup(
        Long caFirmId, LocalDate date, String endpointGroup);

    @Query("SELECT SUM(u.callCount) FROM UsageRecord u " +
           "WHERE u.caFirmId = :caFirmId AND u.usageDate = :date")
    Long sumCallCountByFirmAndDate(Long caFirmId, LocalDate date);

    List<UsageRecord> findByCaFirmIdAndUsageDateBetween(
        Long caFirmId, LocalDate from, LocalDate to);
}

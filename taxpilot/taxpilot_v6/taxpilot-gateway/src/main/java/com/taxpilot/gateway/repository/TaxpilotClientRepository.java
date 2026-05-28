package com.taxpilot.gateway.repository;

import com.taxpilot.gateway.entity.TaxpilotClient;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.List;
import java.util.Optional;

@Repository
public interface TaxpilotClientRepository extends JpaRepository<TaxpilotClient, Long> {
    List<TaxpilotClient> findByCaFirmIdAndIsActiveTrue(Long caFirmId);
    Optional<TaxpilotClient> findByIdAndCaFirmId(Long id, Long caFirmId);
    boolean existsByGstin(String gstin);
    boolean existsByPan(String pan);
}

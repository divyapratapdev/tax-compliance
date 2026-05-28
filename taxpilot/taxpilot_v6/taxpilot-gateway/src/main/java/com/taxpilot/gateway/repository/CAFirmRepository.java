package com.taxpilot.gateway.repository;

import com.taxpilot.gateway.entity.CAFirm;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.stereotype.Repository;
import java.util.Optional;

@Repository
public interface CAFirmRepository extends JpaRepository<CAFirm, Long> {
    Optional<CAFirm> findByEmail(String email);
    boolean existsByEmail(String email);
    boolean existsByRegistrationNumber(String registrationNumber);
}

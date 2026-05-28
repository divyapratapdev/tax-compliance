package com.taxpilot.gateway.service;

import com.taxpilot.gateway.dto.request.CreateClientRequest;
import com.taxpilot.gateway.dto.response.ClientResponse;
import com.taxpilot.gateway.entity.TaxpilotClient;
import com.taxpilot.gateway.repository.TaxpilotClientRepository;
import lombok.RequiredArgsConstructor;
import lombok.extern.slf4j.Slf4j;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;

import java.util.List;
import java.util.stream.Collectors;

@Slf4j
@Service
@RequiredArgsConstructor
public class ClientService {

    private final TaxpilotClientRepository clientRepo;

    @Transactional
    public ClientResponse createClient(Long caFirmId, CreateClientRequest req) {
        if (req.getGstin() != null && clientRepo.existsByGstin(req.getGstin())) {
            throw new IllegalArgumentException("GSTIN already registered");
        }
        if (req.getPan() != null && clientRepo.existsByPan(req.getPan())) {
            throw new IllegalArgumentException("PAN already registered");
        }

        TaxpilotClient client = TaxpilotClient.builder()
                .caFirmId(caFirmId)
                .companyName(req.getCompanyName())
                .gstin(req.getGstin())
                .pan(req.getPan())
                .email(req.getEmail())
                .phone(req.getPhone())
                .turnoverCategory(req.getTurnoverCategory())
                .registrationType(req.getRegistrationType())
                .isActive(true)
                .build();

        client = clientRepo.save(client);
        log.info("Client created: {} for firm {}", client.getCompanyName(), caFirmId);
        return toResponse(client);
    }

    public List<ClientResponse> listClients(Long caFirmId) {
        return clientRepo.findByCaFirmIdAndIsActiveTrue(caFirmId)
                .stream().map(this::toResponse).collect(Collectors.toList());
    }

    public ClientResponse getClient(Long caFirmId, Long clientId) {
        return clientRepo.findByIdAndCaFirmId(clientId, caFirmId)
                .map(this::toResponse)
                .orElseThrow(() -> new IllegalArgumentException("Client not found"));
    }

    @Transactional
    public void deactivateClient(Long caFirmId, Long clientId) {
        TaxpilotClient client = clientRepo.findByIdAndCaFirmId(clientId, caFirmId)
                .orElseThrow(() -> new IllegalArgumentException("Client not found"));
        client.setIsActive(false);
        clientRepo.save(client);
    }

    private ClientResponse toResponse(TaxpilotClient c) {
        return ClientResponse.builder()
                .id(c.getId())
                .companyName(c.getCompanyName())
                .gstin(c.getGstin())
                .pan(c.getPan())
                .email(c.getEmail())
                .phone(c.getPhone())
                .turnoverCategory(c.getTurnoverCategory())
                .registrationType(c.getRegistrationType())
                .isActive(c.getIsActive())
                .createdAt(c.getCreatedAt())
                .build();
    }
}

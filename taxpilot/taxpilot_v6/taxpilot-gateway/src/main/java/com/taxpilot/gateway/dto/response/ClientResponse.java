package com.taxpilot.gateway.dto.response;

import lombok.AllArgsConstructor;
import lombok.Builder;
import lombok.Data;
import lombok.NoArgsConstructor;
import java.time.LocalDateTime;

@Data @Builder @NoArgsConstructor @AllArgsConstructor
public class ClientResponse {
    private Long id;
    private String companyName;
    private String gstin;
    private String pan;
    private String email;
    private String phone;
    private String turnoverCategory;
    private String registrationType;
    private Boolean isActive;
    private LocalDateTime createdAt;
}

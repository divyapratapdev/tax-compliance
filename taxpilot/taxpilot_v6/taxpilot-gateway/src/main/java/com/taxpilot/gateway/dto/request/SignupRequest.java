package com.taxpilot.gateway.dto.request;

import jakarta.validation.constraints.Email;
import jakarta.validation.constraints.NotBlank;
import jakarta.validation.constraints.Size;
import lombok.Data;

@Data
public class SignupRequest {

    @NotBlank(message = "Firm name is required")
    private String name;

    @NotBlank(message = "Registration number is required")
    private String registrationNumber;

    @Email(message = "Valid email required")
    @NotBlank
    private String email;

    @NotBlank
    @Size(min = 8, message = "Password must be at least 8 characters")
    private String password;

    private String phone;

    /** starter | growth | scale | enterprise */
    private String plan = "starter";
}

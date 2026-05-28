package com.taxpilot.gateway;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.scheduling.annotation.EnableScheduling;

@SpringBootApplication
@EnableScheduling
public class TaxPilotGatewayApplication {
    public static void main(String[] args) {
        SpringApplication.run(TaxPilotGatewayApplication.class, args);
    }
}

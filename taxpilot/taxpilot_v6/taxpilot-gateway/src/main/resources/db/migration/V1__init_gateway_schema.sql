-- TaxPilot Gateway Schema
-- Runs in taxpilot_gateway database (separate from Python engine's taxpilot DB)

CREATE TABLE IF NOT EXISTS ca_firms (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    name                VARCHAR(255)    NOT NULL,
    registration_number VARCHAR(50)     NOT NULL UNIQUE,
    email               VARCHAR(255)    NOT NULL UNIQUE,
    password_hash       VARCHAR(255)    NOT NULL,
    plan                VARCHAR(50)     NOT NULL DEFAULT 'starter',
    phone               VARCHAR(20),
    is_active           TINYINT(1)      NOT NULL DEFAULT 1,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS clients (
    id                  BIGINT AUTO_INCREMENT PRIMARY KEY,
    ca_firm_id          BIGINT          NOT NULL,
    company_name        VARCHAR(255)    NOT NULL,
    gstin               VARCHAR(15)     UNIQUE,
    pan                 VARCHAR(10)     UNIQUE,
    turnover_category   VARCHAR(50),
    registration_type   VARCHAR(50)     DEFAULT 'regular',
    email               VARCHAR(255),
    phone               VARCHAR(20),
    is_active           TINYINT(1)      NOT NULL DEFAULT 1,
    created_at          DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_clients_firm (ca_firm_id),
    CONSTRAINT fk_clients_firm FOREIGN KEY (ca_firm_id) REFERENCES ca_firms(id)
);

CREATE TABLE IF NOT EXISTS usage_records (
    id              BIGINT AUTO_INCREMENT PRIMARY KEY,
    ca_firm_id      BIGINT          NOT NULL,
    usage_date      DATE            NOT NULL,
    endpoint_group  VARCHAR(50)     NOT NULL,
    call_count      BIGINT          NOT NULL DEFAULT 0,
    last_flushed_at DATETIME,
    UNIQUE KEY uq_usage (ca_firm_id, usage_date, endpoint_group),
    INDEX idx_usage_firm_date (ca_firm_id, usage_date),
    CONSTRAINT fk_usage_firm FOREIGN KEY (ca_firm_id) REFERENCES ca_firms(id)
);

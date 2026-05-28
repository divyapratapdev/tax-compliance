-- Creates both databases on first container start
CREATE DATABASE IF NOT EXISTS taxpilot CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE DATABASE IF NOT EXISTS taxpilot_gateway CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'taxpilot'@'%' IDENTIFIED BY 'taxpilot123';
GRANT ALL PRIVILEGES ON taxpilot.*         TO 'taxpilot'@'%';
GRANT ALL PRIVILEGES ON taxpilot_gateway.* TO 'taxpilot'@'%';
FLUSH PRIVILEGES;

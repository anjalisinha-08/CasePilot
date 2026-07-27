-- =============================================================================
-- CASEPILOT — Module 1: Foundation
-- Script: 03_schemas.sql
-- Purpose: Create all schemas within CASEPILOT_DB
-- Author: CasePilot Team
-- =============================================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE CASEPILOT_WH;
USE DATABASE CASEPILOT_DB;

-- =============================================================================
-- SCHEMA: RAW
-- Landing zone for all raw/simulated transactional data.
-- Contains: CUSTOMER, ACCOUNT, MERCHANT, DEVICE, TRANSACTION
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS RAW
    COMMENT = 'Raw transactional data - customers, accounts, merchants, devices, transactions';

-- =============================================================================
-- SCHEMA: CORE
-- Curated and cleansed data layer for analytical consumption.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS CORE
    COMMENT = 'Curated core data layer for analytics and processing';

-- =============================================================================
-- SCHEMA: ALERTS
-- Alert generation and management.
-- Contains: ALERT table populated by alert rules engine.
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS ALERTS
    COMMENT = 'Alert generation and management schema';

-- =============================================================================
-- SCHEMA: INVESTIGATION
-- Investigation case management.
-- Contains: INVESTIGATION_CASE, CASE_ENRICHMENT
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS INVESTIGATION
    COMMENT = 'Investigation case management and enrichment';

-- =============================================================================
-- SCHEMA: ANALYTICS
-- Intelligence, scoring, and summary data.
-- Contains: CASE_INTELLIGENCE
-- =============================================================================
CREATE SCHEMA IF NOT EXISTS ANALYTICS
    COMMENT = 'Case intelligence, scoring, and analytics';

-- Verify creation
SHOW SCHEMAS IN DATABASE CASEPILOT_DB;

-- =============================================================================
-- CASEPILOT — Module 1: Foundation
-- Script: 01_warehouse.sql
-- Purpose: Create the compute warehouse for CasePilot workloads
-- Author: CasePilot Team
-- =============================================================================

-- Use ACCOUNTADMIN to create infrastructure
USE ROLE ACCOUNTADMIN;

-- =============================================================================
-- WAREHOUSE: CASEPILOT_WH
-- X-Small warehouse suitable for development and moderate workloads.
-- Auto-suspends after 60 seconds of inactivity to minimize credit usage.
-- Auto-resumes on any query submission.
-- =============================================================================
CREATE WAREHOUSE IF NOT EXISTS CASEPILOT_WH
    WITH
    WAREHOUSE_SIZE      = 'X-SMALL'
    AUTO_SUSPEND        = 60
    AUTO_RESUME         = TRUE
    INITIALLY_SUSPENDED = TRUE
    MIN_CLUSTER_COUNT   = 1
    MAX_CLUSTER_COUNT   = 1
    COMMENT             = 'CasePilot - AI-Powered Financial Investigation Copilot warehouse';

-- Verify creation
SHOW WAREHOUSES LIKE 'CASEPILOT_WH';

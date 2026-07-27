-- =============================================================================
-- CASEPILOT — Module 1: Foundation
-- Script: 02_database.sql
-- Purpose: Create the primary database for CasePilot
-- Author: CasePilot Team
-- =============================================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE CASEPILOT_WH;

-- =============================================================================
-- DATABASE: CASEPILOT_DB
-- Central database housing all schemas for the investigation platform.
-- =============================================================================
CREATE DATABASE IF NOT EXISTS CASEPILOT_DB
    COMMENT = 'CasePilot - AI-Powered Financial Investigation Copilot database';

-- Verify creation
SHOW DATABASES LIKE 'CASEPILOT_DB';

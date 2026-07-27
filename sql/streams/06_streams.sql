-- =============================================================================
-- CASEPILOT — Module 4: Streams
-- Script: 06_streams.sql
-- Purpose: Create Snowflake Streams for change data capture
-- Author: CasePilot Team
-- =============================================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE CASEPILOT_WH;
USE DATABASE CASEPILOT_DB;

-- =============================================================================
-- STREAM: TRANSACTION_STREAM
-- Captures INSERT operations on RAW.TRANSACTION table.
-- Used by ALERT_CREATION_TASK to detect new transactions and evaluate
-- them against alert rules.
-- =============================================================================
CREATE OR REPLACE STREAM RAW.TRANSACTION_STREAM
    ON TABLE RAW.TRANSACTION
    APPEND_ONLY = TRUE
    COMMENT = 'Captures new transactions for real-time alert evaluation';

-- =============================================================================
-- STREAM: ALERT_STREAM
-- Captures INSERT operations on ALERTS.ALERT table.
-- Used by CASE_CREATION_TASK to automatically create investigation cases.
-- =============================================================================
CREATE OR REPLACE STREAM ALERTS.ALERT_STREAM
    ON TABLE ALERTS.ALERT
    APPEND_ONLY = TRUE
    COMMENT = 'Captures new alerts for automatic case creation';

-- Verify streams
SHOW STREAMS IN DATABASE CASEPILOT_DB;

-- Check stream status
SELECT SYSTEM$STREAM_HAS_DATA('RAW.TRANSACTION_STREAM') AS TXN_STREAM_HAS_DATA;
SELECT SYSTEM$STREAM_HAS_DATA('ALERTS.ALERT_STREAM') AS ALERT_STREAM_HAS_DATA;

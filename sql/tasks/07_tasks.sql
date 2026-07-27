-- =============================================================================
-- CASEPILOT — Module 4: Tasks
-- Script: 07_tasks.sql
-- Purpose: Create Snowflake Tasks for event-driven processing
-- Author: CasePilot Team
-- =============================================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE CASEPILOT_WH;
USE DATABASE CASEPILOT_DB;

-- =============================================================================
-- TASK: ALERT_CREATION_TASK
-- Runs every 1 minute. When TRANSACTION_STREAM has data, evaluates new
-- transactions against alert rules and inserts matching alerts.
--
-- Alert Rules implemented in SQL:
--   1. HIGH_VALUE_TXN:    amount > 25000
--   2. ODD_HOUR_ACTIVITY: hour between 0 and 3
--   3. FOREIGN_ACTIVITY:  IS_INTERNATIONAL = TRUE
-- =============================================================================
CREATE OR REPLACE TASK RAW.ALERT_CREATION_TASK
    WAREHOUSE = CASEPILOT_WH
    SCHEDULE  = '1 MINUTE'
    COMMENT   = 'Evaluates new transactions from stream and creates alerts'
    WHEN SYSTEM$STREAM_HAS_DATA('RAW.TRANSACTION_STREAM')
AS
BEGIN
    -- Rule 1: HIGH_VALUE_TXN (Amount > 25000)
    INSERT INTO ALERTS.ALERT (
        ALERT_ID, TXN_ID, ACCOUNT_ID, CUSTOMER_ID, ALERT_TYPE,
        ALERT_DESCRIPTION, SEVERITY, RULE_VERSION,
        TRIGGERED_AMOUNT, TRIGGERED_THRESHOLD, STATUS,
        CREATED_AT, UPDATED_AT
    )
    SELECT
        UUID_STRING(),
        TXN_ID,
        ACCOUNT_ID,
        CUSTOMER_ID,
        'HIGH_VALUE_TXN',
        'High-value transaction of ₹' || TO_VARCHAR(AMOUNT, '999,999,999.99') ||
            ' detected. Threshold: ₹25,000. Channel: ' || CHANNEL || '.',
        CASE
            WHEN AMOUNT >= 100000 THEN 'CRITICAL'
            WHEN AMOUNT >= 50000  THEN 'HIGH'
            ELSE 'MEDIUM'
        END,
        '1.0',
        AMOUNT,
        25000,
        'NEW',
        CURRENT_TIMESTAMP(),
        CURRENT_TIMESTAMP()
    FROM RAW.TRANSACTION_STREAM
    WHERE AMOUNT > 25000
      AND STATUS = 'COMPLETED';

    -- Rule 2: ODD_HOUR_ACTIVITY (00:00 - 04:00)
    INSERT INTO ALERTS.ALERT (
        ALERT_ID, TXN_ID, ACCOUNT_ID, CUSTOMER_ID, ALERT_TYPE,
        ALERT_DESCRIPTION, SEVERITY, RULE_VERSION,
        TRIGGERED_AMOUNT, TRIGGERED_THRESHOLD, STATUS,
        CREATED_AT, UPDATED_AT
    )
    SELECT
        UUID_STRING(),
        TXN_ID,
        ACCOUNT_ID,
        CUSTOMER_ID,
        'ODD_HOUR_ACTIVITY',
        'Transaction at ' || TO_VARCHAR(TXN_TIMESTAMP, 'HH24:MI:SS') ||
            ' (odd hours: 00:00–04:00). Amount: ₹' ||
            TO_VARCHAR(AMOUNT, '999,999,999.99') || '. Channel: ' || CHANNEL || '.',
        'MEDIUM',
        '1.0',
        AMOUNT,
        NULL,
        'NEW',
        CURRENT_TIMESTAMP(),
        CURRENT_TIMESTAMP()
    FROM RAW.TRANSACTION_STREAM
    WHERE HOUR(TXN_TIMESTAMP) >= 0
      AND HOUR(TXN_TIMESTAMP) < 4
      AND STATUS = 'COMPLETED';

    -- Rule 3: FOREIGN_ACTIVITY (international transactions)
    INSERT INTO ALERTS.ALERT (
        ALERT_ID, TXN_ID, ACCOUNT_ID, CUSTOMER_ID, ALERT_TYPE,
        ALERT_DESCRIPTION, SEVERITY, RULE_VERSION,
        TRIGGERED_AMOUNT, TRIGGERED_THRESHOLD, STATUS,
        CREATED_AT, UPDATED_AT
    )
    SELECT
        UUID_STRING(),
        TXN_ID,
        ACCOUNT_ID,
        CUSTOMER_ID,
        'FOREIGN_ACTIVITY',
        'Foreign transaction detected in ' || COALESCE(MERCHANT_CITY, 'Unknown') ||
            ', ' || COALESCE(MERCHANT_COUNTRY, 'Unknown') ||
            '. Amount: ₹' || TO_VARCHAR(AMOUNT, '999,999,999.99') ||
            '. Channel: ' || CHANNEL || '.',
        'HIGH',
        '1.0',
        AMOUNT,
        NULL,
        'NEW',
        CURRENT_TIMESTAMP(),
        CURRENT_TIMESTAMP()
    FROM RAW.TRANSACTION_STREAM
    WHERE IS_INTERNATIONAL = TRUE
      AND STATUS = 'COMPLETED';
END;


-- =============================================================================
-- TASK: CASE_CREATION_TASK
-- Child task that runs after ALERT_CREATION_TASK completes.
-- Creates investigation cases for each new alert.
-- =============================================================================
CREATE OR REPLACE TASK INVESTIGATION.CASE_CREATION_TASK
    WAREHOUSE = CASEPILOT_WH
    COMMENT   = 'Creates investigation cases from new alerts'
    AFTER RAW.ALERT_CREATION_TASK
    WHEN SYSTEM$STREAM_HAS_DATA('ALERTS.ALERT_STREAM')
AS
BEGIN
    INSERT INTO INVESTIGATION.INVESTIGATION_CASE (
        CASE_ID, ALERT_ID, CUSTOMER_ID, ACCOUNT_ID,
        CASE_NUMBER, CASE_STATUS, ASSIGNED_TO, ASSIGNED_TEAM,
        PRIORITY, CREATED_AT, UPDATED_AT
    )
    SELECT
        UUID_STRING(),
        ALERT_ID,
        CUSTOMER_ID,
        ACCOUNT_ID,
        'CP-' || TO_VARCHAR(CURRENT_DATE(), 'YYYYMMDD') || '-' ||
            SUBSTR(UUID_STRING(), 1, 5),
        'OPEN',
        NULL,
        CASE
            WHEN ALERT_TYPE IN ('HIGH_VALUE_TXN') THEN 'TEAM_ALPHA'
            WHEN ALERT_TYPE IN ('NEW_DEVICE_USED', 'RAPID_TXN_BURST') THEN 'TEAM_BETA'
            WHEN ALERT_TYPE IN ('FOREIGN_ACTIVITY') THEN 'TEAM_GAMMA'
            ELSE 'TEAM_ALPHA'
        END,
        SEVERITY,
        CURRENT_TIMESTAMP(),
        CURRENT_TIMESTAMP()
    FROM ALERTS.ALERT_STREAM;
END;


-- =============================================================================
-- Enable tasks (start from the leaf task, then root)
-- =============================================================================
ALTER TASK INVESTIGATION.CASE_CREATION_TASK RESUME;
ALTER TASK RAW.ALERT_CREATION_TASK RESUME;

-- Verify tasks
SHOW TASKS IN DATABASE CASEPILOT_DB;

-- Check task history (run after some time)
-- SELECT * FROM TABLE(INFORMATION_SCHEMA.TASK_HISTORY())
--     WHERE NAME IN ('ALERT_CREATION_TASK', 'CASE_CREATION_TASK')
--     ORDER BY SCHEDULED_TIME DESC LIMIT 20;

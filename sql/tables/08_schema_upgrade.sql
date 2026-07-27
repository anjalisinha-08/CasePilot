-- =============================================================================
-- CASEPILOT 2.0 — Schema Upgrade
-- Script: 08_schema_upgrade.sql
-- Purpose: Add fraud labeling, behavioral profiles, model metrics, notifications
-- =============================================================================

USE ROLE ACCOUNTADMIN;
USE WAREHOUSE CASEPILOT_WH;
USE DATABASE CASEPILOT_DB;

-- =============================================================================
-- 1. ADD FRAUD COLUMNS TO RAW.TRANSACTION
-- =============================================================================
ALTER TABLE RAW.TRANSACTION ADD COLUMN IF NOT EXISTS IS_FRAUD BOOLEAN DEFAULT FALSE;
ALTER TABLE RAW.TRANSACTION ADD COLUMN IF NOT EXISTS FRAUD_TYPE VARCHAR(50);
ALTER TABLE RAW.TRANSACTION ADD COLUMN IF NOT EXISTS FRAUD_REASON VARCHAR(500);
ALTER TABLE RAW.TRANSACTION ADD COLUMN IF NOT EXISTS FRAUD_CONFIDENCE NUMBER(5,4) DEFAULT 0.0;

-- =============================================================================
-- 2. CUSTOMER BEHAVIORAL PROFILES
-- =============================================================================
CREATE TABLE IF NOT EXISTS ANALYTICS.CUSTOMER_BEHAVIOR_PROFILE (
    PROFILE_ID          VARCHAR(36)     NOT NULL PRIMARY KEY,
    CUSTOMER_ID         VARCHAR(36)     NOT NULL,
    AVG_TXN_AMOUNT      NUMBER(15,2),
    MAX_TXN_AMOUNT      NUMBER(15,2),
    STD_DEV_AMOUNT      NUMBER(15,2),
    AVG_DAILY_SPEND     NUMBER(15,2),
    AVG_MONTHLY_SPEND   NUMBER(15,2),
    TXN_FREQUENCY_DAILY NUMBER(10,4),
    PREFERRED_CHANNELS  VARIANT,
    PREFERRED_DEVICES   VARIANT,
    TYPICAL_LOCATIONS   VARIANT,
    MERCHANT_PREFERENCES VARIANT,
    TOTAL_TRANSACTIONS  NUMBER(10),
    PROFILE_PERIOD_DAYS NUMBER(5),
    COMPUTED_AT         TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    CONSTRAINT FK_PROFILE_CUSTOMER FOREIGN KEY (CUSTOMER_ID)
        REFERENCES RAW.CUSTOMER(CUSTOMER_ID)
);

-- =============================================================================
-- 3. MODEL EVALUATION METRICS
-- =============================================================================
CREATE TABLE IF NOT EXISTS ANALYTICS.MODEL_METRICS (
    METRIC_ID           VARCHAR(36)     NOT NULL PRIMARY KEY,
    RUN_ID              VARCHAR(36)     NOT NULL,
    MODEL_VERSION       VARCHAR(20)     NOT NULL DEFAULT '2.0',
    TOTAL_PREDICTIONS   NUMBER(10),
    TRUE_POSITIVES      NUMBER(10),
    TRUE_NEGATIVES      NUMBER(10),
    FALSE_POSITIVES     NUMBER(10),
    FALSE_NEGATIVES     NUMBER(10),
    ACCURACY            NUMBER(8,6),
    PRECISION_SCORE     NUMBER(8,6),
    RECALL              NUMBER(8,6),
    F1_SCORE            NUMBER(8,6),
    FALSE_POSITIVE_RATE NUMBER(8,6),
    FALSE_NEGATIVE_RATE NUMBER(8,6),
    EVALUATION_DETAILS  VARIANT,
    EVALUATED_AT        TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP()
);

-- =============================================================================
-- 4. CUSTOMER NOTIFICATION LOG
-- =============================================================================
CREATE TABLE IF NOT EXISTS INVESTIGATION.NOTIFICATION_LOG (
    NOTIFICATION_ID     VARCHAR(36)     NOT NULL PRIMARY KEY,
    CUSTOMER_ID         VARCHAR(36)     NOT NULL,
    ALERT_ID            VARCHAR(36)     NOT NULL,
    CASE_ID             VARCHAR(36),
    MESSAGE             VARCHAR(1000)   NOT NULL,
    CHANNEL             VARCHAR(20)     NOT NULL,
    STATUS              VARCHAR(20)     NOT NULL DEFAULT 'SENT',
    CUSTOMER_RESPONSE   VARCHAR(20),
    SENT_AT             TIMESTAMP_NTZ   NOT NULL DEFAULT CURRENT_TIMESTAMP(),
    RESPONDED_AT        TIMESTAMP_NTZ,
    RESPONSE_ACTION     VARCHAR(100),
    CONSTRAINT FK_NOTIF_CUSTOMER FOREIGN KEY (CUSTOMER_ID)
        REFERENCES RAW.CUSTOMER(CUSTOMER_ID),
    CONSTRAINT FK_NOTIF_ALERT FOREIGN KEY (ALERT_ID)
        REFERENCES ALERTS.ALERT(ALERT_ID)
);

-- =============================================================================
-- VERIFY
-- =============================================================================
SHOW COLUMNS IN TABLE RAW.TRANSACTION LIKE 'IS_FRAUD';
SHOW TABLES IN SCHEMA ANALYTICS;
SHOW TABLES IN SCHEMA INVESTIGATION;

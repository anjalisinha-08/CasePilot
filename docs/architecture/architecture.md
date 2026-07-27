# CasePilot — System Architecture

## Overview

CasePilot is an **AI-Powered Financial Investigation Copilot** that automates post-alert investigation workflows. It does NOT detect fraud — it starts **after** an alert is generated and creates investigation-ready cases with enrichment, intelligence, and priority scoring.

## Architecture Diagram

```mermaid
graph TB
    subgraph "Data Generation Layer"
        CG[Customer Generator<br/>100 Customers] --> SF_RAW[(RAW Schema)]
        AG[Account Generator<br/>150 Accounts] --> SF_RAW
        MG[Merchant Generator<br/>50 Merchants] --> SF_RAW
        DG[Device Generator<br/>300 Devices] --> SF_RAW
        TG[Transaction Generator<br/>10,000 Txns] --> SF_RAW
    end

    subgraph "Event Processing Layer"
        SF_RAW --> TS{TRANSACTION_STREAM}
        TS --> ACT[ALERT_CREATION_TASK]
        ACT --> SF_ALERTS[(ALERTS Schema)]
        SF_ALERTS --> AS{ALERT_STREAM}
        AS --> CCT[CASE_CREATION_TASK]
    end

    subgraph "Investigation Engine"
        CCT --> IC[(INVESTIGATION Schema)]
        IC --> CE[Case Enrichment]
        CE --> IC
    end

    subgraph "Intelligence Layer"
        IC --> PS[Priority Scoring<br/>0-100 Score]
        PS --> CS[Case Summary<br/>AI Narratives]
        CS --> SF_ANALYTICS[(ANALYTICS Schema)]
    end

    subgraph "Presentation Layer"
        SF_ANALYTICS --> D1[Executive Dashboard]
        IC --> D2[Investigation Queue]
        IC --> D3[Customer 360]
        SF_ANALYTICS --> D4[Case Intelligence]
        SF_ANALYTICS --> D5[Risk Analytics]
    end

    style SF_RAW fill:#1E293B,stroke:#3B82F6,color:#F1F5F9
    style SF_ALERTS fill:#1E293B,stroke:#EF4444,color:#F1F5F9
    style IC fill:#1E293B,stroke:#F59E0B,color:#F1F5F9
    style SF_ANALYTICS fill:#1E293B,stroke:#10B981,color:#F1F5F9
```

## Data Flow

```mermaid
sequenceDiagram
    participant SIM as Simulator
    participant RAW as RAW Schema
    participant STREAM as Transaction Stream
    participant TASK as Alert Task
    participant ALERT as ALERTS Schema
    participant INV as Investigation Engine
    participant INTEL as Intelligence Layer
    participant UI as Streamlit Dashboard

    SIM->>RAW: Generate Customers, Accounts, Merchants, Devices
    SIM->>RAW: Generate 10,000 Transactions
    RAW->>STREAM: CDC captures new transactions
    STREAM->>TASK: Alert Creation Task triggered
    TASK->>ALERT: Evaluate rules → Create Alerts
    ALERT->>INV: Create Investigation Cases
    INV->>INV: Enrich with Customer 360 context
    INV->>INTEL: Calculate Priority Score (0-100)
    INTEL->>INTEL: Generate Summary + Recommendations
    UI->>ALERT: Query alerts
    UI->>INV: Query cases + enrichment
    UI->>INTEL: Query intelligence
```

## Snowflake Schema Design

| Schema | Purpose | Tables |
|--------|---------|--------|
| **RAW** | Landing zone for transactional data | CUSTOMER, ACCOUNT, MERCHANT, DEVICE, TRANSACTION |
| **CORE** | Curated analytical layer | (Reserved for views) |
| **ALERTS** | Alert generation & management | ALERT |
| **INVESTIGATION** | Case management & enrichment | INVESTIGATION_CASE, CASE_ENRICHMENT |
| **ANALYTICS** | Intelligence & scoring | CASE_INTELLIGENCE |

## Priority Scoring Algorithm

```mermaid
pie title Scoring Weight Distribution
    "Alert Severity" : 25
    "Amount Deviation" : 20
    "Customer Risk" : 15
    "Previous Alerts" : 15
    "Device Trust" : 10
    "Time Anomaly" : 10
    "Geographic Anomaly" : 5
```

| Risk Band | Score Range | Action |
|-----------|------------|--------|
| LOW | 0–25 | Routine review |
| MEDIUM | 26–50 | 48-hour investigation |
| HIGH | 51–75 | Same-day priority |
| CRITICAL | 76–100 | Immediate escalation |

## Alert Rules

| Rule | Trigger Condition | Default Severity |
|------|------------------|-----------------|
| HIGH_VALUE_TXN | Amount > ₹25,000 | MEDIUM–CRITICAL |
| ODD_HOUR_ACTIVITY | 00:00–04:00 hours | MEDIUM |
| NEW_DEVICE_USED | Untrusted device | HIGH |
| RAPID_TXN_BURST | 5+ txns in 10 min | HIGH |
| FOREIGN_ACTIVITY | Outside India | HIGH |

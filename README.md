# 🛡️ CasePilot — AI-Powered Financial Investigation Copilot

> **CasePilot starts where fraud detection ends.** It automatically creates investigation-ready cases from alerts, enriches them with customer context, generates intelligence summaries, and calculates priority scores — all powered by Snowflake.

[![Snowflake](https://img.shields.io/badge/Snowflake-Powered-29B5E8?logo=snowflake)](https://snowflake.com)
[![Python](https://img.shields.io/badge/Python-3.9+-3776AB?logo=python)](https://python.org)
[![Streamlit](https://img.shields.io/badge/Streamlit-Dashboard-FF4B4B?logo=streamlit)](https://streamlit.io)

---

## 📋 Table of Contents

- [Overview](#overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Setup Instructions](#setup-instructions)
- [Running the Project](#running-the-project)
- [Modules](#modules)
- [Testing](#testing)
- [Dashboard](#dashboard)

---

## Overview

CasePilot is a **post-alert investigation automation platform**. Existing fraud systems generate alerts — CasePilot takes those alerts and:

1. **Creates investigation cases** automatically
2. **Enriches cases** with customer, account, transaction, merchant, and device context
3. **Scores priority** using a weighted multi-factor algorithm (0–100)
4. **Generates intelligence** — summaries, recommendations, timelines, key findings
5. **Displays everything** through a professional Streamlit dashboard

### Tech Stack

| Component | Technology |
|-----------|-----------|
| Database | Snowflake |
| Processing | Snowpark, Streams, Tasks |
| Language | Python 3.9+ |
| Dashboard | Streamlit + Plotly |
| Data Gen | Faker |

---

## Architecture

```
Simulator → RAW Schema → Stream → Alert Task → ALERTS Schema
                                                     ↓
                              Investigation Engine → Cases + Enrichment
                                                     ↓
                              Intelligence Layer → Priority Score + Summary
                                                     ↓
                              Streamlit Dashboard → 5 Pages
```

See [docs/architecture/architecture.md](docs/architecture/architecture.md) for detailed diagrams.

---

## Project Structure

```
casepilot/
├── docs/architecture/           # Architecture documentation
├── sql/
│   ├── schemas/                 # Warehouse, DB, schema, role SQL
│   ├── tables/                  # Table DDL
│   ├── streams/                 # Snowflake Streams
│   └── tasks/                   # Snowflake Tasks
├── src/
│   ├── config/                  # Snowflake connection + settings
│   ├── simulator/               # Data generators (5 files)
│   ├── alerts/                  # Alert engine (5 rules)
│   ├── investigation/           # Case generator + enrichment
│   ├── intelligence/            # Priority scoring + summaries
│   ├── dashboard/               # Streamlit app (5 pages)
│   │   ├── app.py               # Main entry point
│   │   ├── pages/               # Individual page modules
│   │   └── services/            # Query service layer
│   └── utils/                   # Helper functions
├── tests/                       # Unit tests
├── .env.example                 # Environment template
├── requirements.txt             # Python dependencies
└── README.md
```

---

## Setup Instructions

### Prerequisites

- Python 3.9+
- Snowflake Trial Account ([signup](https://signup.snowflake.com/))
- Git

### Step 1: Clone Repository

```bash
git clone https://github.com/your-username/CasePilot.git
cd CasePilot
```

### Step 2: Create Virtual Environment

```bash
python -m venv venv
source venv/bin/activate  # macOS/Linux
# venv\Scripts\activate   # Windows
```

### Step 3: Install Dependencies

```bash
pip install -r requirements.txt
```

### Step 4: Configure Environment

```bash
cp .env.example .env
```

Edit `.env` with your Snowflake credentials:
```
SNOWFLAKE_ACCOUNT=your_account_identifier
SNOWFLAKE_USER=your_username
SNOWFLAKE_PASSWORD=your_password
```

### Step 5: Run Snowflake SQL Scripts

Execute these scripts **in order** in Snowflake Worksheets:

1. `sql/schemas/01_warehouse.sql`
2. `sql/schemas/02_database.sql`
3. `sql/schemas/03_schemas.sql`
4. `sql/tables/04_tables.sql`
5. `sql/schemas/05_roles_and_grants.sql`
6. `sql/streams/06_streams.sql`
7. `sql/tasks/07_tasks.sql`

---

## Running the Project

### Step 1: Generate Data

```bash
python -c "
from src.simulator.customer_generator import generate_customers, insert_customers_to_snowflake
from src.simulator.account_generator import generate_accounts, insert_accounts_to_snowflake
from src.simulator.merchant_generator import generate_merchants, insert_merchants_to_snowflake
from src.simulator.device_generator import generate_devices, insert_devices_to_snowflake
from src.simulator.transaction_generator import generate_transactions, insert_transactions_to_snowflake
from src.config.snowflake_connection import SnowflakeConnection

conn = SnowflakeConnection()
conn.connect()

customers = generate_customers()
insert_customers_to_snowflake(customers, conn)

accounts = generate_accounts(customers)
insert_accounts_to_snowflake(accounts, conn)

merchants = generate_merchants()
insert_merchants_to_snowflake(merchants, conn)

devices = generate_devices(customers)
insert_devices_to_snowflake(devices, conn)

transactions = generate_transactions(customers, accounts, merchants, devices)
insert_transactions_to_snowflake(transactions, conn)
print('Data generation complete!')
conn.disconnect()
"
```

### Step 2: Generate Alerts

```bash
python -c "
from src.alerts.alert_engine import run_alert_engine, insert_alerts_to_snowflake
from src.simulator.transaction_generator import generate_transactions
from src.simulator.customer_generator import generate_customers
from src.simulator.account_generator import generate_accounts
from src.simulator.merchant_generator import generate_merchants
from src.simulator.device_generator import generate_devices
from src.config.snowflake_connection import SnowflakeConnection

customers = generate_customers()
accounts = generate_accounts(customers)
merchants = generate_merchants()
devices = generate_devices(customers)
transactions = generate_transactions(customers, accounts, merchants, devices)

alerts = run_alert_engine(transactions, devices)

conn = SnowflakeConnection()
conn.connect()
insert_alerts_to_snowflake(alerts, conn)
conn.disconnect()
print(f'Generated {len(alerts)} alerts!')
"
```

### Step 3: Create Cases & Intelligence

```bash
python -c "
from src.investigation.case_generator import generate_cases, insert_cases_to_snowflake
from src.investigation.case_enrichment import enrich_cases, insert_enrichments_to_snowflake
from src.intelligence.priority_scoring import score_all_cases
from src.intelligence.case_summary import generate_intelligence, insert_intelligence_to_snowflake
from src.alerts.alert_engine import run_alert_engine
from src.simulator.customer_generator import generate_customers
from src.simulator.account_generator import generate_accounts
from src.simulator.merchant_generator import generate_merchants
from src.simulator.device_generator import generate_devices
from src.simulator.transaction_generator import generate_transactions
from src.config.snowflake_connection import SnowflakeConnection

customers = generate_customers()
accounts = generate_accounts(customers)
merchants = generate_merchants()
devices = generate_devices(customers)
transactions = generate_transactions(customers, accounts, merchants, devices)
alerts = run_alert_engine(transactions, devices)
cases = generate_cases(alerts)
enrichments = enrich_cases(cases, alerts, customers, accounts, transactions, merchants, devices)
scores = score_all_cases(cases, alerts, enrichments)
intelligence = generate_intelligence(cases, alerts, enrichments, scores)

conn = SnowflakeConnection()
conn.connect()
insert_cases_to_snowflake(cases, conn)
insert_enrichments_to_snowflake(enrichments, conn)
insert_intelligence_to_snowflake(intelligence, conn)
conn.disconnect()
print('Pipeline complete!')
"
```

### Step 4: Launch Dashboard

```bash
streamlit run src/dashboard/app.py
```

Open `http://localhost:8501` in your browser.

---

## Modules

| Module | Description |
|--------|------------|
| **Foundation** | Snowflake infrastructure (warehouse, DB, schemas, tables, roles) |
| **Simulator** | Generates 100 customers, 150 accounts, 50 merchants, 300 devices, 10K transactions |
| **Alert Engine** | 5 rules: HIGH_VALUE_TXN, ODD_HOUR, NEW_DEVICE, RAPID_BURST, FOREIGN |
| **Streams & Tasks** | Event-driven processing via Snowflake Streams and Tasks |
| **Investigation** | Auto case creation + 360° enrichment |
| **Intelligence** | Priority scoring (0–100) + AI summaries + recommendations |
| **Dashboard** | 5-page Streamlit app: Executive, Queue, Customer 360, Intelligence, Analytics |

---

## Testing

```bash
# Run all tests
python -m pytest tests/ -v

# Run specific test file
python -m pytest tests/test_generators.py -v
python -m pytest tests/test_alert_engine.py -v
python -m pytest tests/test_priority_scoring.py -v
```

---

## Dashboard Pages

| Page | Features |
|------|----------|
| **Executive Dashboard** | KPI cards, risk pie chart, priority histogram, severity bar, recent queue |
| **Investigation Queue** | Filterable/searchable case table with detail expander |
| **Customer 360** | Full enrichment: profile, accounts, txns, merchants, devices, alerts, stats |
| **Case Intelligence** | Score card, summary, recommendations, timeline, key findings |
| **Risk Analytics** | 6 charts + top entities (customers, merchants, devices) |

---

## License

This project is for educational and demonstration purposes.

---

Built with ❄️ Snowflake + 🐍 Python + 🎯 Streamlit




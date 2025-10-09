# Treasury Auction Systems

A containerized data pipeline and analytics platform for U.S. Treasury auction data, providing automated collection, storage, and visualization of historical and real-time auction results.

## Overview

The Treasury Auction System automatically fetches data from the TreasuryDirect API, stores it in a PostgreSQL database, and provides an interactive dashboard for analysis.  
The system includes over **10,000 historical auction records** spanning from 1979 to 2025.

### Key Features

- **Automated daily data collection** from TreasuryDirect API
- **PostgreSQL database** with normalized schema
- **Interactive Streamlit dashboard** with real-time visualizations
- **Fully containerized with Docker**
- **Scheduled updates** for continuous data freshness
- **Data export capabilities** to CSV

---

## Quick Start

### Prerequisites

- Docker and Docker Compose installed
- 2GB+ available disk space
- Ports 8501 and 5432 available

### Installation

1. **Clone the repository**

```bash
git clone <repository-url>
cd treasury-auction-system
```

2. **Start the system**

```bash
docker-compose up -d --build
```

3. **Monitor initial data load (takes ~5 minutes)**

```bash
docker-compose logs -f app

```

4. **Access the dashboard**
   http://localhost:8501

5. **Run Validation Checks**

We provide a `validation.sql` script to check database integrity and auction consistency.

 Have the latest version
```bash
git pull origin main
```

copy script into the Postgres container
```bash
docker cp validation.sql treasury_postgres:/validation.sql
```
run it inside Postgres
```bash
docker exec -it treasury_postgres psql -U treasury_user -d treasury_db -c "\i /validation.sql"
```

## Project Structure

```bash

treasury-auction-system/
├── app/
│   ├── Dockerfile
│   ├── requirements.txt
│   ├── models.py
│   ├── treasury_data_pipeline_v2.py
│   ├── scheduler.py
│   ├── streamlit_dashboard.py
│   └── analytics.py
├── data/
│   └── treasury_cache.json
├── docker-compose.yml
├── init/
│   └── 01-create-extensions.sql
└── .env
```

## Database Schema

### securities (Dimension Table)

| Column        | Type         | Description                                  |
| ------------- | ------------ | -------------------------------------------- |
| cusip         | VARCHAR(9)   | Primary key - unique security identifier     |
| security_type | VARCHAR(20)  | Bill, Note, or Bond                          |
| security_term | VARCHAR(20)  | Duration (e.g., "10-Year")                   |
| series        | VARCHAR(100) | Security series name                         |
| tips          | BOOLEAN      | Treasury Inflation-Protected Securities flag |
| callable      | BOOLEAN      | Whether security can be called early         |

### auctions (FACT Table)

| Column             | Type          | Description                 |
| ------------------ | ------------- | --------------------------- |
| auction_id         | INTEGER       | Primary key                 |
| cusip              | VARCHAR(9)    | Foreign key to `securities` |
| auction_date       | DATE          | When auction occurred       |
| issue_date         | DATE          | When security is issued     |
| maturity_date      | DATE          | When security matures       |
| offering_amount    | DECIMAL(20,2) | Amount offered (dollars)    |
| total_accepted     | DECIMAL(20,2) | Total amount accepted       |
| bid_to_cover_ratio | DECIMAL(10,4) | Demand indicator            |
| high_yield         | DECIMAL(10,4) | Highest accepted yield      |
| price_per_100      | DECIMAL(10,4) | Price per \$100 face value  |

### bidder_details (Supplementary Table)

| Column                     | Type         | Description               |
| -------------------------- | ------------ | ------------------------- |
| detail_id                  | INTEGER      | Primary key               |
| auction_id                 | INTEGER      | Foreign key to `auctions` |
| primary_dealer_percentage  | DECIMAL(5,2) | % from primary dealers    |
| direct_bidder_percentage   | DECIMAL(5,2) | % from direct bidders     |
| indirect_bidder_percentage | DECIMAL(5,2) | % from indirect bidders   |

### data_updates (Audit Table)

| Column           | Type        | Description                 |
| ---------------- | ----------- | --------------------------- |
| update_id        | INTEGER     | Primary key                 |
| update_timestamp | TIMESTAMP   | When update ran             |
| records_fetched  | INTEGER     | Number of records retrieved |
| records_inserted | INTEGER     | New records added           |
| status           | VARCHAR(20) | SUCCESS, RUNNING, or FAILED |

## Dashboard Features

### Visualizations

- Bid-to-Cover Ratio Trends: Time series analysis with moving averages

- Security Type Distribution: Pie charts showing auction breakdown

- Yield Analysis: Scatter plots of yields over time

- Dealer Participation: Analysis of bidder types

### Filters

- Date range selection

- Security type filtering (Bills, Notes, Bonds)

- Export filtered data to CSV

### Key Metrics

- Total auctions count

- Average bid-to-cover ratio

- Total offering amounts

- Latest yield rates

## Data Pipeline

### Initial Load Process

1. Fetches all available records from TreasuryDirect API

2. Caches data to /data/treasury_cache.json

3. Processes and validates data

4. Inserts into PostgreSQL database

5. Updates audit table with statistics

### Daily Updates

- Scheduled at 18:00 daily

- Fetches only new/updated records

- Incremental database updates

- Automatic error recovery

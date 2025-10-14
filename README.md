# Treasury Auction & Fiscal Policy Analytics

[![Live Demo](https://img.shields.io/badge/Live%20Demo-treasury--analytics.duckdns.org-blue?style=for-the-badge&logo=streamlit)](https://treasury-analytics.duckdns.org/)
[![Status](https://img.shields.io/badge/Status-Live-success?style=for-the-badge)](https://treasury-analytics.duckdns.org/)

> **Live Application:** [https://treasury-analytics.duckdns.org](https://treasury-analytics.duckdns.org/)

An advanced analytics platform for analyzing U.S. Treasury auction data and its correlation with fiscal policy sentiment derived from news articles. Built with Python, PostgreSQL, and Streamlit.

---

## Features

### **Treasury Auction Analytics**

- **Real-time auction data** from U.S. Treasury API
- **10,000+ historical auction records** dating back to 2020
- Comprehensive metrics:
  - Bid-to-Cover Ratios
  - Yield curves (2Y, 5Y, 10Y, 30Y)
  - Primary Dealer participation
  - FIMA (Foreign & International Monetary Authorities) participation
  - SOMA (Federal Reserve) participation
  - Competitive vs Non-competitive bids

### **Interactive Comparisons**

- Multi-select comparison tool for fiscal indices vs treasury metrics
- Compare any combination of:
  - **Fiscal Indices:** Fiscal Policy, Tariff, Non-Tariff
  - **Treasury Metrics:** Bid-to-Cover, Dealer Shares, Yields, FIMA/SOMA participation
- Dual-axis time series charts
- Correlation scatter plots with trendlines
- Interactive heatmaps
- Statistical summary tables
- CSV data export

### **Fiscal Policy Index**

- Sentiment analysis from news articles
- Daily tracking of fiscal policy discussions
- Separate indices for:
  - Overall fiscal policy
  - Tariff-related policy
  - Non-tariff fiscal policy
- Top phrases and trending topics

### **Market Stress Indicators**

- Yield spread analysis
- Bid-to-Cover trend monitoring
- Competitive vs Non-competitive bid composition
- Early warning signals based on Brookings Institution framework

### **Federal Reserve Participation**

- FIMA participation tracking (foreign central banks)
- SOMA participation tracking (Fed's own portfolio)
- Historical trends by security type
- Combined Fed impact analysis

### **Advanced Analytics**

- Rolling volatility analysis
- Statistical summaries by security type
- Rate spread analysis
- Correlation matrices

---

## Architecture

### **Tech Stack**

```
Frontend:  Streamlit (Python)
Backend:   Python 3.11
Database:  PostgreSQL 15
Container: Docker + Docker Compose
Hosting:   AWS EC2 (Ubuntu)
Domain:    DuckDNS (free subdomain)
SSL:       Let's Encrypt (Certbot)
Proxy:     Nginx
```

### **Data Pipeline**

```
┌─────────────────────────────────────────────────────────────┐
│                     Data Sources                            │
├─────────────────────────────────────────────────────────────┤
│  Treasury API          │  News APIs (Fiscal Analysis)       │
│  (treasurydirect.gov)  │  (Article scraping & NLP)          │
└────────┬───────────────┴────────────────┬───────────────────┘
         │                                │
         ▼                                ▼
┌─────────────────────┐        ┌─────────────────────┐
│ Treasury Pipeline   │        │ Fiscal Data Loader  │
│ - Fetch auctions    │        │ - Scrape articles   │
│ - Parse data        │        │ - Calculate indices │
│ - Validate          │        │ - Extract phrases   │
└─────────┬───────────┘        └──────────┬──────────┘
          │                               │
          └───────────┬───────────────────┘
                      ▼
          ┌───────────────────────┐
          │   PostgreSQL Database │
          │   - securities        │
          │   - auctions          │
          │   - bidder_details    │
          │   - fiscal_indices    │
          │   - top_phrases       │
          └───────────┬───────────┘
                      │
                      ▼
          ┌───────────────────────┐
          │  Streamlit Dashboard  │
          │  - Interactive UI     │
          │  - Real-time queries  │
          │  - Visualizations     │
          └───────────────────────┘
```

---

## 🗄️ Database Schema

### **Core Tables**

```sql
-- Parent: Securities
securities (
    cusip PK,
    security_type,
    security_term,
    interest_rate,
    maturity_date,
    issue_date
)

-- Child: Auctions
auctions (
    auction_id PK,
    cusip FK → securities,
    auction_date,
    bid_to_cover_ratio,
    high_yield,
    low_yield,
    offering_amount,
    total_accepted,
    total_tendered
)

-- Child: Bidder Details
bidder_details (
    bidder_detail_id PK,
    auction_id FK → auctions,
    primary_dealer_percentage,
    fima_percentage,
    soma_percentage,
    competitive_accepted,
    noncompetitive_accepted
)

-- Independent: Fiscal Data
fiscal_policy_indices (
    date PK,
    fiscal_policy_index,
    tariff_fiscal_index,
    non_tariff_fiscal_index,
    total_articles,
    fiscal_articles
)

top_phrases (
    phrase_id PK,
    phrase,
    count
)
```

**Relationships:**

- `Securities (1) → (Many) Auctions` via `cusip`
- `Auctions (1) → (1) BidderDetails` via `auction_id`
- `Auctions ⟷ FiscalPolicyIndices` via `date` (temporal join)

---

## 🚀 Quick Start

### **Prerequisites**

- Docker & Docker Compose
- Git
- 2GB+ RAM
- Internet connection (for data fetching)

### **Local Development**

```bash
# Clone repository
git clone https://github.com/yourusername/treasury-analytics.git
cd treasury-analytics

# Create .env file
cat > .env << EOF
POSTGRES_DB=treasury_db
POSTGRES_USER=treasury_user
POSTGRES_PASSWORD=your_secure_password
POSTGRES_PORT=5432
STREAMLIT_PORT=8501
EOF

# Start services
docker-compose up -d

# Check logs
docker logs -f treasury_app

# Access dashboard
open http://localhost:8501
```

### **Initial Data Load**

On first startup, the system automatically:

1. Creates database schema
2. Fetches ~10,000 historical auction records
3. Processes and indexes data
4. Starts daily update scheduler

**Expected logs:**

```
INFO:__main__:Database is empty, running initial load...
INFO:treasury_data_pipeline_v2:Loaded 10671 records from cache
INFO:treasury_data_pipeline_v2:Pipeline completed: {'status': 'success', 'fetched': 10671, 'inserted': 10671}
INFO:__main__:Scheduler started. Daily updates scheduled at 18:00
```

---

## 📦 Project Structure

```
treasury-analytics/
├── app/
│   ├── streamlit_dashboard.py      # Main dashboard UI
│   ├── treasury_data_pipeline_v2.py # Treasury data fetcher
│   ├── fiscal_data_loader.py       # Fiscal policy analyzer
│   ├── models.py                   # SQLAlchemy models
│   ├── scheduler.py                # Daily update scheduler
│   ├── analytics.py                # Analysis utilities
│   ├── validation.sql              # Validation testing queries                
│   ├── requirements.txt            # Python dependencies
│   └── Dockerfile                  # App container config
├── init/
│   └── init.sql                    # Database initialization
├── data/                           # Cached data files
├── docker-compose.yml              # Multi-container orchestration
├── .env                            # Environment variables
└── README.md
```

---

## Configuration

### **Environment Variables**

```bash
# Database
POSTGRES_DB=treasury_db
POSTGRES_USER=treasury_user
POSTGRES_PASSWORD=treasury_secure_pass_2025
POSTGRES_PORT=5432

# Application
STREAMLIT_PORT=8501
MAX_RECORDS=15000
UPDATE_SCHEDULE_HOUR=18
UPDATE_SCHEDULE_MINUTE=0
```

### **Data Update Schedule**

- **Frequency:** Daily at 18:00 UTC
- **Source:** U.S. Treasury API
- **Records:** Incremental updates (new auctions only)
- **Cache:** Local backup for faster restarts

---

## 📊 Dashboard Pages

### 1. ** Overview**

- Key metrics summary
- Bid-to-Cover trends
- Auction distribution by type
- Recent auction data

### 2. **Interactive Comparisons** ⭐ NEW

- Multi-select fiscal indices and treasury metrics
- Time series comparisons (dual-axis)
- Correlation scatter plots
- Heatmap visualizations
- Statistical summary tables
- CSV export

### 3. **Market Stress Indicators**

- Yield spread analysis
- Bid-to-Cover trends
- Bid composition changes
- Stress signal detection

### 4. **Fed Participation (FIMA/SOMA)**

- FIMA participation trends
- SOMA participation analysis
- Combined Fed impact
- Security type breakdown

### 5. **Advanced Analytics**

- Rolling volatility
- Statistical summaries
- Rate spread analysis
- Correlation matrices

### 6. **Fiscal Policy Index**

- Daily fiscal policy sentiment
- Tariff vs Non-tariff indices
- Article volume tracking
- Trend visualization

### 7. **Top Phrases**

- Most frequent phrases in fiscal articles
- Word cloud visualization
- Phrase frequency treemap

### 8. **Fiscal-Auction Correlation**

- Correlation analysis
- Dual-axis time series
- Scatter plots
- Full correlation matrix

---

## 🔌 API Reference

### **Treasury Data API**

```python
# Endpoint
https://www.treasurydirect.gov/TA_WS/securities/jqsearch

# Example request
{
    "startDate": "2020-01-01",
    "endDate": "2025-10-13",
    "pageSize": 250
}
```

### **Database Connection**

```python
from sqlalchemy import create_engine

DATABASE_URL = "postgresql://treasury_user:password@postgres:5432/treasury_db"
engine = create_engine(DATABASE_URL)

# Query example
query = "SELECT * FROM auctions WHERE auction_date >= '2024-01-01'"
df = pd.read_sql(query, engine)
```

---

## 🚢 Deployment

### **AWS EC2 Deployment**

The application is deployed on AWS EC2 with the following setup:

```bash
# Instance: t3.micro (Ubuntu 24.04)
# Domain: treasury-analytics.duckdns.org
# SSL: Let's Encrypt
# Proxy: Nginx

# Architecture
User → DuckDNS → AWS EC2 → Nginx (443/80) → Streamlit (8501)
                                ↓
                           PostgreSQL (5432)
```

**Deployment steps:**

1. SSH into EC2 instance
2. Clone repository
3. Configure environment variables
4. Run `docker-compose up -d`
5. Configure Nginx reverse proxy
6. Set up SSL with Certbot
7. Configure DuckDNS for dynamic DNS

### **Manual Deployment**

```bash
# On local machine
cd ~/capstone-project-11
tar -czf treasury-app.tar.gz \
  --exclude='*.pyc' \
  --exclude='__pycache__' \
  --exclude='.git' \
  app/ docker-compose.yml .env init/

# Upload to EC2
scp treasury-app.tar.gz ubuntu@13.211.222.86:~/

# On EC2
ssh ubuntu@13.211.222.86
tar -xzf treasury-app.tar.gz -C capstone-project-11/
cd capstone-project-11
docker-compose build
docker-compose up -d
```

---

## 🛠️ Development

### **Adding New Features**

1. **New Data Source**

   ```python
   # Create new loader in app/
   class NewDataLoader:
       def fetch_data(self):
           # Fetch logic
           pass

       def process_data(self, raw_data):
           # Transform logic
           pass
   ```

2. **New Database Table**

   ```sql
   -- Add to init/init.sql
   CREATE TABLE new_table (
       id SERIAL PRIMARY KEY,
       ...
   );
   ```

3. **New Dashboard Page**
   ```python
   # In streamlit_dashboard.py
   elif page == "🆕 New Feature":
       st.header("New Feature")
       # Your code here
   ```

### **Running Tests**

```bash
# Unit tests
docker exec -it treasury_app python -m pytest tests/

# Database connection test
docker exec -it treasury_postgres psql -U treasury_user -d treasury_db -c "SELECT COUNT(*) FROM auctions;"

# Manual data refresh
docker exec -it treasury_app python -c "
from treasury_data_pipeline_v2 import TreasuryDataPipeline
pipeline = TreasuryDataPipeline()
result = pipeline.run()
print(result)
"
```

---

## 🐛 Troubleshooting

### **Database Connection Issues**

```bash
# Check database is running
docker ps | grep postgres

# Check connection
docker exec -it treasury_postgres psql -U treasury_user -d treasury_db

# Reset database
docker-compose down -v
docker-compose up -d
```

### **Data Not Loading**

```bash
# Check logs
docker logs treasury_app --tail 100

# Manually trigger data load
docker exec -it treasury_app python scheduler.py

# Check data count
docker exec -it treasury_postgres psql -U treasury_user -d treasury_db -c "SELECT COUNT(*) FROM auctions;"
```

### **Dashboard Not Accessible**

```bash
# Check container status
docker-compose ps

# Restart services
docker-compose restart app

# Check Nginx (if deployed)
sudo systemctl status nginx
sudo nginx -t
```

[⬆ Back to top](#-treasury-auction--fiscal-policy-analytics)

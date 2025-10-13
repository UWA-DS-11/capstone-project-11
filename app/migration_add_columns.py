"""
Database Migration Script
Adds new columns for enhanced Treasury auction analysis

Run this BEFORE running the updated ingest.py
"""

import os
from sqlalchemy import create_engine, text
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def run_migration():
    database_url = os.getenv(
        'DATABASE_URL',
        os.getenv('DATABASE_URL', 'postgresql://treasury_user:treasury_secure_pass_2025@postgres:5432/treasury_db')
    )
    
    engine = create_engine(database_url)
    
    migrations = [
        # Security table additions
        """
        ALTER TABLE securities 
        ADD COLUMN IF NOT EXISTS interest_rate NUMERIC(10, 6);
        """,
        
        # Auction table additions
        """
        ALTER TABLE auctions 
        ADD COLUMN IF NOT EXISTS auction_date_year VARCHAR(4),
        ADD COLUMN IF NOT EXISTS maturing_date DATE,
        ADD COLUMN IF NOT EXISTS allocation_percentage NUMERIC(5, 2),
        ADD COLUMN IF NOT EXISTS interest_rate NUMERIC(10, 6),
        ADD COLUMN IF NOT EXISTS high_discount_rate NUMERIC(10, 4),
        ADD COLUMN IF NOT EXISTS low_discount_rate NUMERIC(10, 4),
        ADD COLUMN IF NOT EXISTS high_investment_rate NUMERIC(10, 4),
        ADD COLUMN IF NOT EXISTS low_investment_rate NUMERIC(10, 4);
        """,
        
        # BidderDetail table additions
        """
        ALTER TABLE bidder_details 
        ADD COLUMN IF NOT EXISTS fima_accepted NUMERIC(20, 2),
        ADD COLUMN IF NOT EXISTS fima_percentage NUMERIC(5, 2),
        ADD COLUMN IF NOT EXISTS soma_accepted NUMERIC(20, 2),
        ADD COLUMN IF NOT EXISTS soma_percentage NUMERIC(5, 2),
        ADD COLUMN IF NOT EXISTS competitive_accepted NUMERIC(20, 2),
        ADD COLUMN IF NOT EXISTS noncompetitive_accepted NUMERIC(20, 2),
        ADD COLUMN IF NOT EXISTS treasury_retail_accepted NUMERIC(20, 2);
        """
    ]
    
    logger.info("Starting database migration...")
    
    with engine.connect() as conn:
        for i, migration in enumerate(migrations, 1):
            try:
                logger.info(f"Running migration {i}/{len(migrations)}...")
                conn.execute(text(migration))
                conn.commit()
                logger.info(f"✓ Migration {i} completed successfully")
            except Exception as e:
                logger.error(f"✗ Migration {i} failed: {e}")
                conn.rollback()
                raise
    
    logger.info("✅ All migrations completed successfully!")
    logger.info("\nNext steps:")
    logger.info("1. Update your models.py with the new version")
    logger.info("2. Update your ingest.py with the new version")
    logger.info("3. Run the ingestion pipeline to populate new columns")

if __name__ == "__main__":
    run_migration()
#!/usr/bin/env python3
import os
import time
import schedule
import logging
from sqlalchemy import text
from treasury_data_pipeline_v2 import TreasuryDataPipeline

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def run_update():
    logger.info("Starting scheduled treasury data update...")
    try:
        pipeline = TreasuryDataPipeline()
        result = pipeline.run_pipeline()
        logger.info(f"Update completed: {result}")
    except Exception as e:
        logger.error(f"Update failed: {e}")

def initial_load():
    logger.info("Checking if initial data load is needed...")
    try:
        pipeline = TreasuryDataPipeline()
        engine = pipeline.engine
        
        with engine.connect() as conn:
            result = conn.execute(text("SELECT COUNT(*) FROM auctions"))
            count = result.scalar()
            
            if count == 0:
                logger.info("Database is empty, running initial load...")
                run_update()
            else:
                logger.info(f"Database has {count} records, skipping initial load")
    except Exception as e:
        if "relation" in str(e).lower() and "does not exist" in str(e).lower():
            logger.info("Tables don't exist yet, running initial load...")
            run_update()
        else:
            logger.error(f"Initial load check failed: {e}")

initial_load()

update_hour = os.getenv('UPDATE_SCHEDULE_HOUR', '18')
update_minute = os.getenv('UPDATE_SCHEDULE_MINUTE', '00')
schedule_time = f"{update_hour.zfill(2)}:{update_minute.zfill(2)}"

schedule.every().day.at(schedule_time).do(run_update)
logger.info(f"Scheduler started. Daily updates scheduled at {schedule_time}")

while True:
    schedule.run_pending()
    time.sleep(60)
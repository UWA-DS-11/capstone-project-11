import os
import json
import logging
import requests
from datetime import datetime
from decimal import Decimal
from typing import Dict, Any, Optional

import pandas as pd
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.dialects.postgresql import insert

from models import Base, Security, Auction, BidderDetail, DataUpdate

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TreasuryDataPipeline:
    def __init__(self, database_url: str = None):
        self.database_url = database_url or os.getenv(
            'DATABASE_URL', 
            'postgresql://treasury_user:treasury_pass@localhost:5432/treasury_db'
        )
        self.engine = create_engine(self.database_url, echo=False, pool_pre_ping=True)
        self.SessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.api_base = os.getenv('TREASURY_API_BASE', 'https://www.treasurydirect.gov/TA_WS/securities/jqsearch')
    
    def parse_value(self, value: Any, value_type: str = 'decimal') -> Optional[Any]:
        if value is None or value == '':
            return None
        
        try:
            if value_type == 'decimal':
                return Decimal(str(value))
            elif value_type == 'date':
                return pd.to_datetime(value).date() if value else None
            elif value_type == 'datetime':
                return pd.to_datetime(value) if value else None
            elif value_type == 'boolean':
                return str(value).lower() in ['yes', 'true', '1']
            elif value_type == 'integer':
                return int(value)
            else:
                return str(value) if value else None
        except (ValueError, TypeError):
            return None
    
    def fetch_treasury_data(self, max_records: int = 15000) -> list:
        """Fetch all available Treasury auction data from API"""
        cache_file = '/data/treasury_cache.json'
        
        # Try to load from cache first
        if os.path.exists(cache_file):
            try:
                with open(cache_file, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} records from cache")
                    return data
            except Exception as e:
                logger.warning(f"Cache load failed: {e}")
        
        all_records = []
        page_size = 100
        page_num = 0
        
        logger.info("Fetching data from Treasury API...")
        
        while len(all_records) < max_records:
            params = {
                'format': 'json',
                'pagesize': page_size,
                'pagenum': page_num,
                'recordstartindex': page_num * page_size,
                'recordendindex': (page_num + 1) * page_size
            }
            
            try:
                response = requests.get(self.api_base, params=params, timeout=30)
                response.raise_for_status()
                data = response.json()
                
                if 'securityList' in data and data['securityList']:
                    all_records.extend(data['securityList'])
                    logger.info(f"Fetched page {page_num + 1}: {len(all_records)} total records")
                    
                    if 'totalResultsCount' in data and len(all_records) >= data['totalResultsCount']:
                        break
                    
                    page_num += 1
                else:
                    break
                    
            except Exception as e:
                logger.error(f"Error fetching page {page_num}: {e}")
                break
        
        # Cache the results
        if all_records:
            os.makedirs('/data', exist_ok=True)
            with open(cache_file, 'w') as f:
                json.dump(all_records, f)
            logger.info(f"Cached {len(all_records)} records")
        
        return all_records
    
    def process_records(self, records: list) -> Dict[str, int]:
        """Process fetched records and store in database"""
        session = self.SessionLocal()
        stats = {'inserted': 0, 'updated': 0, 'errors': 0}
        
        try:
            for record in records:
                try:
                    # Process security first
                    security_data = {
                        'cusip': record.get('cusip'),
                        'security_type': record.get('securityType'),
                        'security_term': record.get('securityTerm'),
                        'series': record.get('series'),
                        'tips': self.parse_value(record.get('tips'), 'boolean'),
                        'callable': self.parse_value(record.get('callable'), 'boolean'),
                    }
                    
                    stmt = insert(Security).values(**security_data)
                    stmt = stmt.on_conflict_do_update(
                        index_elements=['cusip'],
                        set_={k: v for k, v in security_data.items() if k != 'cusip'}
                    )
                    session.execute(stmt)
                    
                    # Process auction
                    auction_date = self.parse_value(record.get('auctionDate'), 'date')
                    if not auction_date:
                        continue
                    
                    existing_auction = session.query(Auction).filter_by(
                        cusip=record.get('cusip'),
                        auction_date=auction_date
                    ).first()
                    
                    auction_data = {
                        'cusip': record.get('cusip'),
                        'auction_date': auction_date,
                        'announcement_date': self.parse_value(record.get('announcementDate'), 'date'),
                        'issue_date': self.parse_value(record.get('issueDate'), 'date'),
                        'maturity_date': self.parse_value(record.get('maturityDate'), 'date'),
                        'auction_format': record.get('auctionFormat'),
                        'offering_amount': self.parse_value(record.get('offeringAmount'), 'decimal'),
                        'total_tendered': self.parse_value(record.get('totalTendered'), 'decimal'),
                        'total_accepted': self.parse_value(record.get('totalAccepted'), 'decimal'),
                        'bid_to_cover_ratio': self.parse_value(record.get('bidToCoverRatio'), 'decimal'),
                        'high_yield': self.parse_value(record.get('highYield'), 'decimal'),
                        'low_yield': self.parse_value(record.get('lowYield'), 'decimal'),
                        'average_median_yield': self.parse_value(record.get('averageMedianYield'), 'decimal'),
                        'high_price': self.parse_value(record.get('highPrice'), 'decimal'),
                        'low_price': self.parse_value(record.get('lowPrice'), 'decimal'),
                        'price_per_100': self.parse_value(record.get('pricePer100'), 'decimal'),
                    }
                    
                    if existing_auction:
                        for key, value in auction_data.items():
                            setattr(existing_auction, key, value)
                        auction = existing_auction
                        stats['updated'] += 1
                    else:
                        auction = Auction(**auction_data)
                        session.add(auction)
                        stats['inserted'] += 1
                    
                    session.flush()
                    
                    # Process bidder details if available
                    total_accepted = self.parse_value(record.get('totalAccepted'), 'decimal')
                    if total_accepted and total_accepted > 0:
                        primary_accepted = self.parse_value(record.get('primaryDealerAccepted'), 'decimal')
                        direct_accepted = self.parse_value(record.get('directBidderAccepted'), 'decimal')
                        indirect_accepted = self.parse_value(record.get('indirectBidderAccepted'), 'decimal')
                        
                        bidder_data = {
                            'auction_id': auction.auction_id,
                            'primary_dealer_accepted': primary_accepted,
                            'primary_dealer_percentage': (primary_accepted / total_accepted * 100) if primary_accepted else None,
                            'direct_bidder_accepted': direct_accepted,
                            'direct_bidder_percentage': (direct_accepted / total_accepted * 100) if direct_accepted else None,
                            'indirect_bidder_accepted': indirect_accepted,
                            'indirect_bidder_percentage': (indirect_accepted / total_accepted * 100) if indirect_accepted else None,
                        }
                        
                        existing_bidder = session.query(BidderDetail).filter_by(
                            auction_id=auction.auction_id
                        ).first()
                        
                        if existing_bidder:
                            for key, value in bidder_data.items():
                                if key != 'auction_id':
                                    setattr(existing_bidder, key, value)
                        else:
                            bidder = BidderDetail(**bidder_data)
                            session.add(bidder)
                    
                except Exception as e:
                    logger.error(f"Error processing record: {e}")
                    stats['errors'] += 1
                    continue
            
            session.commit()
            
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {e}")
            raise
        finally:
            session.close()
        
        return stats
    
    def run_pipeline(self) -> Dict[str, Any]:
        """Main pipeline execution"""
        session = self.SessionLocal()
        
        # Create update record
        update_record = DataUpdate(
            run_type='FULL',
            status='RUNNING'
        )
        session.add(update_record)
        session.commit()
        
        try:
            # Fetch data
            records = self.fetch_treasury_data()
            update_record.records_fetched = len(records)
            
            # Process records
            stats = self.process_records(records)
            
            # Update tracking record
            update_record.records_inserted = stats['inserted']
            update_record.records_updated = stats['updated']
            update_record.status = 'SUCCESS'
            
            # Get last auction date
            last_auction = session.query(Auction).order_by(
                Auction.auction_date.desc()
            ).first()
            if last_auction:
                update_record.last_auction_date = last_auction.auction_date
            
            session.commit()
            
            result = {
                'status': 'success',
                'fetched': len(records),
                'inserted': stats['inserted'],
                'updated': stats['updated'],
                'errors': stats['errors']
            }
            logger.info(f"Pipeline completed: {result}")
            return result
            
        except Exception as e:
            update_record.status = 'FAILED'
            update_record.error_message = str(e)
            session.commit()
            logger.error(f"Pipeline failed: {e}")
            return {'status': 'failed', 'error': str(e)}
        finally:
            session.close()

if __name__ == "__main__":
    pipeline = TreasuryDataPipeline()
    result = pipeline.run_pipeline()
    print(f"Pipeline result: {result}")
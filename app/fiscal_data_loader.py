#!/usr/bin/env python3
"""
Fiscal Policy Data Loader
Loads CSV data into the new fiscal policy tables
"""
import os
import sys
import pandas as pd
import logging
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from decimal import Decimal
from datetime import datetime

# Add app directory to path to import models
sys.path.insert(0, '/app')
from models import Base, FiscalArticle, FiscalPolicyIndex, TopPhrase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class FiscalDataLoader:
    def __init__(self, database_url=None, csv_directory='/data'):
        """
        Initialize the data loader
        
        Args:
            database_url: PostgreSQL connection string
            csv_directory: Directory containing CSV files
        """
        self.database_url = database_url or os.getenv(
            'DATABASE_URL',
            'postgresql://treasury_user:treasury_secure_pass_2025@localhost:5432/treasury_db'
        )
        self.csv_directory = csv_directory
        self.engine = create_engine(self.database_url, echo=False)
        self.SessionLocal = sessionmaker(bind=self.engine)
        
    def create_tables(self):
        """Create all new fiscal policy tables"""
        logger.info("Creating fiscal policy tables...")
        Base.metadata.create_all(bind=self.engine)
        logger.info("✓ Tables created successfully")
    
    def load_fiscal_articles(self, filename='wsj_articles.csv'):
        """Load individual article data"""
        filepath = os.path.join(self.csv_directory, filename)
        logger.info(f"Loading fiscal articles from {filepath}...")
        
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return 0
        
        # Read CSV
        df = pd.read_csv(filepath)
        logger.info(f"Found {len(df)} articles in CSV")
        
        session = self.SessionLocal()
        inserted = 0
        updated = 0
        skipped = 0
        
        try:
            for _, row in df.iterrows():
                # Parse date and validate
                try:
                    article_date = pd.to_datetime(row['date'])
                    if pd.isna(article_date):
                        skipped += 1
                        continue
                    article_date = article_date.date()
                except (ValueError, TypeError):
                    skipped += 1
                    continue
                
                # Check if article exists
                existing = session.query(FiscalArticle).filter_by(
                    article_id=str(row['article_id'])
                ).first()
                
                if existing:
                    # Update existing
                    existing.date = article_date
                    existing.is_fiscal_article = bool(row['is_fiscal_article'])
                    existing.has_tariff = bool(row.get('has_tariff', False))
                    updated += 1
                else:
                    # Insert new
                    article = FiscalArticle(
                        article_id=str(row['article_id']),
                        date=article_date,
                        is_fiscal_article=bool(row['is_fiscal_article']),
                        has_tariff=bool(row.get('has_tariff', False))
                    )
                    session.add(article)
                    inserted += 1
                
                # Commit in batches
                if (inserted + updated) % 100 == 0:
                    session.commit()
                    logger.info(f"Progress: {inserted + updated} articles processed...")
            
            session.commit()
            if skipped > 0:
                logger.warning(f"⚠ Skipped {skipped} articles with invalid dates")
            logger.info(f"✓ Fiscal articles loaded: {inserted} inserted, {updated} updated")
            return inserted + updated
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error loading fiscal articles: {e}")
            raise
        finally:
            session.close()
    
    def load_policy_indices(self, filename='wsj_articles_scores.csv'):
        """Load daily policy index scores"""
        filepath = os.path.join(self.csv_directory, filename)
        logger.info(f"Loading policy indices from {filepath}...")
        
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return 0
        
        # Read CSV
        df = pd.read_csv(filepath)
        logger.info(f"Found {len(df)} daily records in CSV")
        
        # Need to add date column - let's derive it from fiscal_articles
        session = self.SessionLocal()
        
        try:
            # Get unique dates from fiscal_articles to match with scores
            articles_df = pd.read_csv(os.path.join(self.csv_directory, 'wsj_articles.csv'))
            articles_df['date'] = pd.to_datetime(articles_df['date'])
            # Filter out NaT values
            articles_df = articles_df[articles_df['date'].notna()]
            unique_dates = sorted(articles_df['date'].unique())
            
            if len(unique_dates) != len(df):
                logger.warning(f"Date mismatch: {len(unique_dates)} dates vs {len(df)} score rows")
                # Match them by order (assuming scores are in chronological order)
                logger.info("Matching scores to dates by chronological order...")
            
            inserted = 0
            updated = 0
            skipped = 0
            
            for idx, row in df.iterrows():
                # Get corresponding date
                if idx < len(unique_dates):
                    # Validate date
                    try:
                        temp_date = unique_dates[idx]
                        if pd.isna(temp_date):
                            skipped += 1
                            continue
                        index_date = temp_date.date()
                    except (ValueError, TypeError, AttributeError):
                        skipped += 1
                        continue
                else:
                    logger.warning(f"No date for row {idx}, skipping...")
                    skipped += 1
                    continue
                
                # Check if record exists
                existing = session.query(FiscalPolicyIndex).filter_by(date=index_date).first()
                
                data = {
                    'total_articles': int(row['total_articles']),
                    'fiscal_articles': int(row['fiscal_articles']),
                    'tariff_fiscal_articles': int(row['tariff_fiscal_articles']),
                    'non_tariff_fiscal_articles': int(row['non_tariff_fiscal_articles']),
                    'rate': Decimal(str(row['rate'])) if pd.notna(row['rate']) else None,
                    'tariff_rate': Decimal(str(row['tariff_rate'])) if pd.notna(row['tariff_rate']) else None,
                    'non_tariff_rate': Decimal(str(row['non_tariff_rate'])) if pd.notna(row['non_tariff_rate']) else None,
                    'fiscal_policy_index': Decimal(str(row['fiscal_policy_index'])) if pd.notna(row['fiscal_policy_index']) else None,
                    'tariff_fiscal_index': Decimal(str(row['tariff_fiscal_index'])) if pd.notna(row['tariff_fiscal_index']) else None,
                    'non_tariff_fiscal_index': Decimal(str(row['non_tariff_fiscal_index'])) if pd.notna(row['non_tariff_fiscal_index']) else None,
                }
                
                if existing:
                    # Update
                    for key, value in data.items():
                        setattr(existing, key, value)
                    updated += 1
                else:
                    # Insert
                    index_record = FiscalPolicyIndex(date=index_date, **data)
                    session.add(index_record)
                    inserted += 1
                
                # Commit in batches
                if (inserted + updated) % 50 == 0:
                    session.commit()
                    logger.info(f"Progress: {inserted + updated} indices processed...")
            
            session.commit()
            if skipped > 0:
                logger.warning(f"⚠ Skipped {skipped} indices with invalid dates")
            logger.info(f"✓ Policy indices loaded: {inserted} inserted, {updated} updated")
            return inserted + updated
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error loading policy indices: {e}")
            raise
        finally:
            session.close()
    
    def load_top_phrases(self, filename='top_phrases.csv'):
        """Load top phrases from articles"""
        filepath = os.path.join(self.csv_directory, filename)
        logger.info(f"Loading top phrases from {filepath}...")
        
        if not os.path.exists(filepath):
            logger.error(f"File not found: {filepath}")
            return 0
        
        # Read CSV
        df = pd.read_csv(filepath)
        logger.info(f"Found {len(df)} phrases in CSV")
        
        session = self.SessionLocal()
        inserted = 0
        updated = 0
        
        try:
            for _, row in df.iterrows():
                phrase_text = str(row['phrase']).strip()
                phrase_count = int(row['count'])
                
                # Check if phrase exists
                existing = session.query(TopPhrase).filter_by(phrase=phrase_text).first()
                
                if existing:
                    # Update count
                    existing.count = phrase_count
                    updated += 1
                else:
                    # Insert new
                    phrase = TopPhrase(
                        phrase=phrase_text,
                        count=phrase_count
                    )
                    session.add(phrase)
                    inserted += 1
                
                # Commit in batches
                if (inserted + updated) % 100 == 0:
                    session.commit()
            
            session.commit()
            logger.info(f"✓ Top phrases loaded: {inserted} inserted, {updated} updated")
            return inserted + updated
            
        except Exception as e:
            session.rollback()
            logger.error(f"Error loading top phrases: {e}")
            raise
        finally:
            session.close()
    
    def verify_data(self):
        """Verify loaded data"""
        logger.info("\n" + "="*50)
        logger.info("DATA VERIFICATION")
        logger.info("="*50)
        
        session = self.SessionLocal()
        
        try:
            # Count records
            article_count = session.query(FiscalArticle).count()
            index_count = session.query(FiscalPolicyIndex).count()
            phrase_count = session.query(TopPhrase).count()
            
            logger.info(f"✓ FiscalArticle records: {article_count}")
            logger.info(f"✓ FiscalPolicyIndex records: {index_count}")
            logger.info(f"✓ TopPhrase records: {phrase_count}")
            
            # Sample data
            if article_count > 0:
                sample_article = session.query(FiscalArticle).first()
                logger.info(f"\nSample Article:")
                logger.info(f"  ID: {sample_article.article_id}")
                logger.info(f"  Date: {sample_article.date}")
                logger.info(f"  Is Fiscal: {sample_article.is_fiscal_article}")
                logger.info(f"  Has Tariff: {sample_article.has_tariff}")
            
            if index_count > 0:
                sample_index = session.query(FiscalPolicyIndex).first()
                logger.info(f"\nSample Policy Index:")
                logger.info(f"  Date: {sample_index.date}")
                logger.info(f"  Fiscal Articles: {sample_index.fiscal_articles}/{sample_index.total_articles}")
                logger.info(f"  Fiscal Policy Index: {sample_index.fiscal_policy_index}")
            
            if phrase_count > 0:
                top_phrase = session.query(TopPhrase).order_by(TopPhrase.count.desc()).first()
                logger.info(f"\nTop Phrase:")
                logger.info(f"  Phrase: '{top_phrase.phrase}'")
                logger.info(f"  Count: {top_phrase.count}")
            
            logger.info("\n" + "="*50)
            
        finally:
            session.close()
    
    def run_full_load(self):
        """Run complete data loading process"""
        logger.info("="*50)
        logger.info("FISCAL POLICY DATA LOADER")
        logger.info("="*50 + "\n")
        
        try:
            # Step 1: Create tables
            self.create_tables()
            
            # Step 2: Load data
            self.load_fiscal_articles()
            self.load_policy_indices()
            self.load_top_phrases()
            
            # Step 3: Verify
            self.verify_data()
            
            logger.info("\n✅ All data loaded successfully!")
            return True
            
        except Exception as e:
            logger.error(f"\n❌ Data loading failed: {e}")
            return False

if __name__ == "__main__":
    loader = FiscalDataLoader()
    success = loader.run_full_load()
    sys.exit(0 if success else 1)
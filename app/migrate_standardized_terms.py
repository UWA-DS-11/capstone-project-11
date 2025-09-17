import sys
import os
sys.path.append('/app')

from sqlalchemy import create_engine, text
from treasury_data_pipeline_v2 import TreasuryDataPipeline
import pandas as pd

def migrate_standardized_terms():
    
    database_url = os.getenv('DATABASE_URL', 
                            'postgresql://treasury_user:treasury_pass@localhost:5432/treasury_db')
    engine = create_engine(database_url)
    pipeline = TreasuryDataPipeline()
    
    with engine.connect() as conn:
        conn.execute(text("""
            ALTER TABLE securities 
            ADD COLUMN IF NOT EXISTS standardized_term VARCHAR(20)
        """))
        conn.commit()
        
        securities = pd.read_sql(
            "SELECT cusip, security_term FROM securities", 
            engine
        )
        
        for _, row in securities.iterrows():
            standardized = pipeline.standardize_maturity(row['security_term'])
            conn.execute(text("""
                UPDATE securities 
                SET standardized_term = :std_term 
                WHERE cusip = :cusip
            """), {'std_term': standardized, 'cusip': row['cusip']})
        
        conn.commit()
        
        conn.execute(text("""
            CREATE INDEX IF NOT EXISTS idx_standardized_term 
            ON securities(standardized_term)
        """))
        conn.commit()
        
    print(f"Migration complete! Updated {len(securities)} securities with standardized terms")

if __name__ == "__main__":
    migrate_standardized_terms()
import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import os

class TreasuryAnalytics:
    def __init__(self, database_url=None):
        self.database_url = database_url or os.getenv('DATABASE_URL')
        self.engine = create_engine(self.database_url)
    
    def calculate_volatility(self, security_type=None, window=30):
        query = """
        SELECT 
            auction_date,
            security_type,
            bid_to_cover_ratio
        FROM auctions a
        JOIN securities s ON a.cusip = s.cusip
        WHERE bid_to_cover_ratio IS NOT NULL
        """
        if security_type:
            query += f" AND s.security_type = '{security_type}'"
        query += " ORDER BY auction_date"
        
        df = pd.read_sql(query, self.engine)
        df['auction_date'] = pd.to_datetime(df['auction_date'])
        
        volatility_data = []
        for sec_type in df['security_type'].unique():
            sec_data = df[df['security_type'] == sec_type].copy()
            sec_data = sec_data.sort_values('auction_date')
            
            sec_data['btc_returns'] = sec_data['bid_to_cover_ratio'].pct_change()
            
            sec_data['volatility'] = sec_data['btc_returns'].rolling(
                window=window, min_periods=10
            ).std() * np.sqrt(252)
            
            volatility_data.append(sec_data)
        
        return pd.concat(volatility_data, ignore_index=True)
    
    def calculate_correlations(self):
        query = """
        SELECT 
            a.auction_date,
            s.security_type,
            a.bid_to_cover_ratio,
            a.high_yield,
            a.offering_amount,
            bd.primary_dealer_percentage,
            bd.indirect_bidder_percentage
        FROM auctions a
        JOIN securities s ON a.cusip = s.cusip
        LEFT JOIN bidder_details bd ON a.auction_id = bd.auction_id
        WHERE a.auction_date >= '2015-01-01'
        ORDER BY a.auction_date
        """
        
        df = pd.read_sql(query, self.engine)
        df['auction_date'] = pd.to_datetime(df['auction_date'])
        
        correlations = {}
        
        for sec_type in df['security_type'].unique():
            sec_data = df[df['security_type'] == sec_type]
            
            if len(sec_data) > 30:
                corr_matrix = sec_data[['bid_to_cover_ratio', 'high_yield', 
                                       'primary_dealer_percentage', 
                                       'indirect_bidder_percentage']].corr()
                correlations[sec_type] = corr_matrix
        
        return correlations
    
    def detect_anomalies(self, z_threshold=3):
        query = """
        SELECT 
            a.*,
            s.security_type
        FROM auctions a
        JOIN securities s ON a.cusip = s.cusip
        WHERE a.bid_to_cover_ratio IS NOT NULL
        """
        
        df = pd.read_sql(query, self.engine)
        anomalies = []
        
        for sec_type in df['security_type'].unique():
            sec_data = df[df['security_type'] == sec_type].copy()
            
            mean_btc = sec_data['bid_to_cover_ratio'].mean()
            std_btc = sec_data['bid_to_cover_ratio'].std()
            
            sec_data['z_score'] = np.abs((sec_data['bid_to_cover_ratio'] - mean_btc) / std_btc)
            
            anomalous = sec_data[sec_data['z_score'] > z_threshold]
            if not anomalous.empty:
                anomalies.append(anomalous)
        
        return pd.concat(anomalies, ignore_index=True) if anomalies else pd.DataFrame()
    
    def calculate_market_stress_index(self):
        query = """
        SELECT 
            DATE_TRUNC('week', auction_date) as week,
            AVG(bid_to_cover_ratio) as avg_btc,
            STDDEV(bid_to_cover_ratio) as std_btc,
            AVG(high_yield) as avg_yield,
            COUNT(*) as auction_count
        FROM auctions a
        JOIN securities s ON a.cusip = s.cusip
        WHERE auction_date >= CURRENT_DATE - INTERVAL '2 years'
        GROUP BY DATE_TRUNC('week', auction_date)
        ORDER BY week
        """
        
        df = pd.read_sql(query, self.engine)
        
        df['btc_zscore'] = (df['avg_btc'] - df['avg_btc'].mean()) / df['avg_btc'].std()
        df['yield_zscore'] = (df['avg_yield'] - df['avg_yield'].mean()) / df['avg_yield'].std()
        df['volatility_zscore'] = (df['std_btc'] - df['std_btc'].mean()) / df['std_btc'].std()
        
        df['stress_index'] = (
            -df['btc_zscore'] +
            df['yield_zscore'] +
            df['volatility_zscore']
        ) / 3
        
        return df
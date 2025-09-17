import pandas as pd
import numpy as np
from sqlalchemy import create_engine
import os

class TreasuryAnalytics:
    def __init__(self, database_url=None):
        self.database_url = database_url or os.getenv('DATABASE_URL', 
                                                      'postgresql://treasury_user:treasury_pass@localhost:5432/treasury_db')
        self.engine = create_engine(self.database_url)
    
    def calculate_volatility(self, security_type=None, use_standardized=True, window=30):
        """Calculate rolling volatility of bid-to-cover ratios"""
        term_col = 'standardized_term' if use_standardized else 'security_term'
        
        query = f"""
        SELECT 
            auction_date,
            s.security_type,
            s.{term_col} as term,
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
        
        return pd.concat(volatility_data, ignore_index=True) if volatility_data else pd.DataFrame()
    
    def calculate_correlations(self, use_standardized=True):
        
        term_col = 'standardized_term' if use_standardized else 'security_term'
        
        query = f"""
        SELECT 
            a.auction_date,
            s.security_type,
            s.security_term,
            s.{term_col} as term,
            a.bid_to_cover_ratio,
            a.high_yield,
            a.offering_amount,
            bd.primary_dealer_percentage,
            bd.direct_bidder_percentage,
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
                numeric_cols = ['bid_to_cover_ratio', 'high_yield', 
                              'primary_dealer_percentage', 'direct_bidder_percentage',
                              'indirect_bidder_percentage']
                
                available_cols = [col for col in numeric_cols if col in sec_data.columns]
                corr_matrix = sec_data[available_cols].corr()
                correlations[sec_type] = corr_matrix
        
        term_correlations = {}
        for term in df['term'].unique():
            term_data = df[df['term'] == term]
            
            if len(term_data) > 30:
                numeric_cols = ['bid_to_cover_ratio', 'high_yield', 'offering_amount']
                available_cols = [col for col in numeric_cols if col in term_data.columns]
                if len(available_cols) > 1:
                    corr_matrix = term_data[available_cols].corr()
                    term_correlations[term] = corr_matrix
        
        return {'by_type': correlations, 'by_term': term_correlations}
    
    def detect_anomalies(self, z_threshold=3, use_standardized=True):
        """Detect anomalous auctions using statistical methods"""
        term_col = 'standardized_term' if use_standardized else 'security_term'
        
        query = f"""
        SELECT 
            a.*,
            s.security_type,
            s.{term_col} as term
        FROM auctions a
        JOIN securities s ON a.cusip = s.cusip
        WHERE a.bid_to_cover_ratio IS NOT NULL
        """
        
        df = pd.read_sql(query, self.engine)
        anomalies = []
        
        # anomalies by security type
        for sec_type in df['security_type'].unique():
            sec_data = df[df['security_type'] == sec_type].copy()
            
            if len(sec_data) > 10:
                mean_btc = sec_data['bid_to_cover_ratio'].mean()
                std_btc = sec_data['bid_to_cover_ratio'].std()
                
                if std_btc > 0:
                    sec_data['z_score'] = np.abs((sec_data['bid_to_cover_ratio'] - mean_btc) / std_btc)
                    
                    anomalous = sec_data[sec_data['z_score'] > z_threshold]
                    if not anomalous.empty:
                        anomalies.append(anomalous)
        
        return pd.concat(anomalies, ignore_index=True) if anomalies else pd.DataFrame()
    
    def calculate_market_stress_index(self):
        """Create a composite market stress index"""
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
            AND bid_to_cover_ratio IS NOT NULL
        GROUP BY DATE_TRUNC('week', auction_date)
        ORDER BY week
        """
        
        df = pd.read_sql(query, self.engine)
        
        if df.empty:
            return pd.DataFrame()
        
        # Calculate z-scores for normalization
        df['btc_zscore'] = (df['avg_btc'] - df['avg_btc'].mean()) / df['avg_btc'].std()
        df['yield_zscore'] = (df['avg_yield'] - df['avg_yield'].mean()) / df['avg_yield'].std()
        df['volatility_zscore'] = (df['std_btc'] - df['std_btc'].mean()) / df['std_btc'].std()
        
        # Composite stress index
        df['stress_index'] = (
            -df['btc_zscore'] +  # Lower bid-to-cover = more stress
            df['yield_zscore'] +  # Higher yields = more stress
            df['volatility_zscore']  # Higher volatility = more stress
        ) / 3
        
        return df
    
    def analyze_term_transitions(self):
        """Analyze how standardization affects term classifications"""
        query = """
        SELECT 
            security_term as original_term,
            standardized_term,
            security_type,
            COUNT(*) as count
        FROM securities
        WHERE security_term IS NOT NULL
        GROUP BY security_term, standardized_term, security_type
        ORDER BY security_type, security_term
        """
        
        df = pd.read_sql(query, self.engine)
        
        transitions = df.pivot_table(
            index='original_term',
            columns='standardized_term',
            values='count',
            aggfunc='sum',
            fill_value=0
        )
        
        return transitions
    
    def get_summary_statistics(self, use_standardized=True):
        """Generate comprehensive summary statistics"""
        term_col = 'standardized_term' if use_standardized else 'security_term'
        
        query = f"""
        SELECT 
            s.security_type,
            s.{term_col} as term,
            COUNT(*) as auction_count,
            AVG(a.bid_to_cover_ratio) as avg_btc,
            STDDEV(a.bid_to_cover_ratio) as std_btc,
            AVG(a.high_yield) as avg_yield,
            SUM(a.offering_amount) / 1e9 as total_offered_billions,
            AVG(bd.primary_dealer_percentage) as avg_primary_dealer_pct,
            AVG(bd.indirect_bidder_percentage) as avg_indirect_bidder_pct
        FROM auctions a
        JOIN securities s ON a.cusip = s.cusip
        LEFT JOIN bidder_details bd ON a.auction_id = bd.auction_id
        WHERE a.auction_date >= CURRENT_DATE - INTERVAL '5 years'
        GROUP BY s.security_type, s.{term_col}
        ORDER BY s.security_type, s.{term_col}
        """
        
        df = pd.read_sql(query, self.engine)
        
        return df
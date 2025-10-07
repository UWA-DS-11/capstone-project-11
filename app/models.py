from sqlalchemy import create_engine, Column, String, DateTime, Date, Numeric, Integer, Boolean, Text, ForeignKey, UniqueConstraint, Index
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

Base = declarative_base()

class Security(Base):
    __tablename__ = 'securities'
    
    cusip = Column(String(9), primary_key=True)
    security_type = Column(String(20), nullable=False)
    security_term = Column(String(20))
    original_security_term = Column(String(20))
    series = Column(String(100))
    corpus_cusip = Column(String(9))
    tips = Column(Boolean, default=False)
    floating_rate = Column(Boolean, default=False)
    callable = Column(Boolean, default=False)
    call_date = Column(Date)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    auctions = relationship("Auction", back_populates="security")
    
    __table_args__ = (
        Index('idx_security_type', 'security_type'),
    )

class Auction(Base):
    __tablename__ = 'auctions'
    
    auction_id = Column(Integer, primary_key=True, autoincrement=True)
    cusip = Column(String(9), ForeignKey('securities.cusip'), nullable=False)
    
    # Key dates
    announcement_date = Column(Date)
    auction_date = Column(Date, nullable=False)
    issue_date = Column(Date)
    maturity_date = Column(Date)
    dated_date = Column(Date)
    
    # Auction details
    auction_format = Column(String(30))
    closing_time_competitive = Column(String(10))
    closing_time_noncompetitive = Column(String(10))
    offering_amount = Column(Numeric(20, 2))
    
    # Results
    total_tendered = Column(Numeric(20, 2))
    total_accepted = Column(Numeric(20, 2))
    bid_to_cover_ratio = Column(Numeric(10, 4))
    
    # Yields/Rates
    high_yield = Column(Numeric(10, 4))
    low_yield = Column(Numeric(10, 4))
    average_median_yield = Column(Numeric(10, 4))
    
    # Prices
    high_price = Column(Numeric(10, 4))
    low_price = Column(Numeric(10, 4))
    price_per_100 = Column(Numeric(10, 4))
    
    # Metadata
    updated_timestamp = Column(DateTime)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    security = relationship("Security", back_populates="auctions")
    bidder_details = relationship("BidderDetail", back_populates="auction", uselist=False, cascade="all, delete-orphan")
    
    __table_args__ = (
        UniqueConstraint('cusip', 'auction_date', name='unique_auction'),
        Index('idx_auction_date', 'auction_date'),
        Index('idx_cusip_date', 'cusip', 'auction_date'),
    )

class BidderDetail(Base):
    __tablename__ = 'bidder_details'
    
    detail_id = Column(Integer, primary_key=True, autoincrement=True)
    auction_id = Column(Integer, ForeignKey('auctions.auction_id'), nullable=False, unique=True)
    
    primary_dealer_accepted = Column(Numeric(20, 2))
    primary_dealer_percentage = Column(Numeric(5, 2))
    direct_bidder_accepted = Column(Numeric(20, 2))
    direct_bidder_percentage = Column(Numeric(5, 2))
    indirect_bidder_accepted = Column(Numeric(20, 2))
    indirect_bidder_percentage = Column(Numeric(5, 2))
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    auction = relationship("Auction", back_populates="bidder_details")

class DataUpdate(Base):
    __tablename__ = 'data_updates'
    
    update_id = Column(Integer, primary_key=True, autoincrement=True)
    update_timestamp = Column(DateTime, server_default=func.now())
    records_fetched = Column(Integer)
    records_inserted = Column(Integer)
    records_updated = Column(Integer)
    last_auction_date = Column(Date)
    status = Column(String(20))
    error_message = Column(Text)
    run_type = Column(String(20))

# NEW MODELS FOR FISCAL POLICY DATA

class FiscalArticle(Base):
    __tablename__ = 'fiscal_articles'
    
    article_id = Column(String(20), primary_key=True)
    date = Column(Date, nullable=False)
    is_fiscal_article = Column(Boolean, default=False)
    has_tariff = Column(Boolean, default=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_article_date', 'date'),
        Index('idx_fiscal_flag', 'is_fiscal_article'),
    )

class FiscalPolicyIndex(Base):
    __tablename__ = 'fiscal_policy_indices'
    
    index_id = Column(Integer, primary_key=True, autoincrement=True)
    date = Column(Date, nullable=False, unique=True)
    
    # Article counts
    total_articles = Column(Integer)
    fiscal_articles = Column(Integer)
    tariff_fiscal_articles = Column(Integer)
    non_tariff_fiscal_articles = Column(Integer)
    
    # Rates
    rate = Column(Numeric(10, 6))
    tariff_rate = Column(Numeric(10, 6))
    non_tariff_rate = Column(Numeric(10, 6))
    
    # Policy indices
    fiscal_policy_index = Column(Numeric(10, 4))
    tariff_fiscal_index = Column(Numeric(10, 4))
    non_tariff_fiscal_index = Column(Numeric(10, 4))
    
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_policy_date', 'date'),
    )

class TopPhrase(Base):
    __tablename__ = 'top_phrases'
    
    phrase_id = Column(Integer, primary_key=True, autoincrement=True)
    phrase = Column(String(100), nullable=False, unique=True)
    count = Column(Integer, nullable=False)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    
    __table_args__ = (
        Index('idx_phrase_count', 'count'),
    )
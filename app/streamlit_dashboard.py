import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
from datetime import datetime, timedelta
import os

st.set_page_config(
    page_title="Treasury Auction Analytics",
    page_icon="🏛️",
    layout="wide"
)

@st.cache_resource
def get_db_connection():
    database_url = os.getenv('DATABASE_URL', 'postgresql://treasury_user:treasury_pass@localhost:5432/treasury_db')
    return create_engine(database_url)

@st.cache_data(ttl=600)
def load_auction_data():
    engine = get_db_connection()
    query = """
    SELECT 
        a.auction_date,
        s.security_type,
        s.security_term,
        a.bid_to_cover_ratio,
        a.high_yield,
        a.offering_amount,
        bd.primary_dealer_percentage,
        bd.indirect_bidder_percentage
    FROM auctions a
    JOIN securities s ON a.cusip = s.cusip
    LEFT JOIN bidder_details bd ON a.auction_id = bd.auction_id
    WHERE a.auction_date >= '2020-01-01'
    ORDER BY a.auction_date DESC
    """
    df = pd.read_sql(query, engine, parse_dates=['auction_date'])
    return df

st.title("🏛️ Treasury Auction Analytics Dashboard")

page = st.sidebar.radio(
    "Select Analysis",
    ["Overview", "Advanced Analytics", "Correlations"]
)

df = load_auction_data()

st.sidebar.markdown("---")
st.sidebar.header("Filters")

min_date = df['auction_date'].min()
max_date = df['auction_date'].max()

date_range = st.sidebar.date_input(
    "Date Range",
    value=(max_date - timedelta(days=365), max_date),
    min_value=min_date.date(),
    max_value=max_date.date()
)

if isinstance(date_range, tuple) and len(date_range) == 2:
    start_datetime = pd.Timestamp(date_range[0])
    end_datetime = pd.Timestamp(date_range[1]) + timedelta(days=1)
    filtered_df = df[(df['auction_date'] >= start_datetime) & (df['auction_date'] < end_datetime)].copy()
else:
    filtered_df = df.copy()

if page == "Overview":
    col1, col2, col3, col4 = st.columns(4)
    
    thirty_days_ago = pd.Timestamp.now() - timedelta(days=30)
    recent_data = filtered_df[filtered_df['auction_date'] >= thirty_days_ago]
    
    with col1:
        total_auctions = len(filtered_df)
        delta = len(recent_data)
        st.metric("Total Auctions", f"{total_auctions:,}", f"{delta} last 30 days")
    
    with col2:
        avg_btc = filtered_df['bid_to_cover_ratio'].mean()
        st.metric("Avg Bid-to-Cover", f"{avg_btc:.2f}" if pd.notna(avg_btc) else "N/A")
    
    with col3:
        total_offered = filtered_df['offering_amount'].sum() / 1e9
        st.metric("Total Offered", f"${total_offered:.1f}B")
    
    with col4:
        recent_yields = filtered_df[filtered_df['high_yield'].notna()]
        if not recent_yields.empty:
            latest_yield = recent_yields.iloc[0]['high_yield']
            st.metric("Latest Yield", f"{latest_yield:.2f}%")
        else:
            st.metric("Latest Yield", "N/A")
    
    st.markdown("---")
    
    st.subheader("Bid-to-Cover Ratio Trends")
    
    btc_data = filtered_df[filtered_df['bid_to_cover_ratio'].notna()].copy()
    btc_data = btc_data.sort_values('auction_date')
    
    for sec_type in btc_data['security_type'].unique():
        mask = btc_data['security_type'] == sec_type
        btc_data.loc[mask, 'ma_30'] = btc_data.loc[mask, 'bid_to_cover_ratio'].rolling(30, min_periods=1).mean()
    
    fig = px.scatter(
        btc_data,
        x='auction_date',
        y='bid_to_cover_ratio',
        color='security_type',
        title='Bid-to-Cover Ratios with Trend',
        opacity=0.6
    )
    
    for sec_type in btc_data['security_type'].unique():
        sec_data = btc_data[btc_data['security_type'] == sec_type]
        fig.add_trace(go.Scatter(
            x=sec_data['auction_date'],
            y=sec_data['ma_30'],
            mode='lines',
            name=f'{sec_type} Trend',
            line=dict(width=2)
        ))
    
    st.plotly_chart(fig, use_container_width=True)
    
    col1, col2 = st.columns(2)
    
    with col1:
        type_counts = filtered_df['security_type'].value_counts()
        fig2 = px.pie(
            values=type_counts.values,
            names=type_counts.index,
            title='Auction Distribution by Type'
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    with col2:
        dealer_data = filtered_df[['primary_dealer_percentage', 'indirect_bidder_percentage']].dropna()
        if not dealer_data.empty:
            avg_dealers = dealer_data.mean()
            fig3 = px.bar(
                x=avg_dealers.index,
                y=avg_dealers.values,
                title='Average Dealer Participation',
                labels={'x': 'Bidder Type', 'y': 'Percentage'}
            )
            st.plotly_chart(fig3, use_container_width=True)

elif page == "Advanced Analytics":
    st.header("Advanced Analytics")
    
    st.subheader("Volatility Analysis")
    
    vol_window = st.slider("Rolling Window (days)", 10, 60, 30)
    
    vol_data = filtered_df.copy()
    vol_data = vol_data.sort_values('auction_date')
    
    for sec_type in vol_data['security_type'].unique():
        mask = vol_data['security_type'] == sec_type
        if mask.any():
            vol_data.loc[mask, 'volatility'] = (
                vol_data.loc[mask, 'bid_to_cover_ratio']
                .rolling(vol_window, min_periods=5)
                .std()
            )
    
    fig = px.line(
        vol_data[vol_data['volatility'].notna()],
        x='auction_date',
        y='volatility',
        color='security_type',
        title=f'{vol_window}-Day Rolling Volatility'
    )
    st.plotly_chart(fig, use_container_width=True)
    
    st.subheader("Statistical Summary")
    
    stats = filtered_df.groupby('security_type')['bid_to_cover_ratio'].agg([
        'count', 'mean', 'std', 'min', 'max'
    ]).round(3)
    
    st.dataframe(stats)

elif page == "Correlations":
    st.header("Correlation Analysis")
    
    corr_columns = ['bid_to_cover_ratio', 'high_yield', 'offering_amount', 
                   'primary_dealer_percentage', 'indirect_bidder_percentage']
    
    available_cols = [col for col in corr_columns if col in filtered_df.columns]
    
    if len(available_cols) > 1:
        for sec_type in filtered_df['security_type'].unique():
            sec_data = filtered_df[filtered_df['security_type'] == sec_type][available_cols].dropna()
            
            if len(sec_data) > 10:
                st.subheader(f"{sec_type} Correlations")
                
                corr_matrix = sec_data.corr()
                
                fig = px.imshow(
                    corr_matrix,
                    text_auto='.2f',
                    aspect="auto",
                    color_continuous_scale='RdBu',
                    range_color=[-1, 1]
                )
                st.plotly_chart(fig, use_container_width=True)
    else:
        st.info("Insufficient data for correlation analysis")

st.markdown("---")
st.caption(f"Data from {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')} | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
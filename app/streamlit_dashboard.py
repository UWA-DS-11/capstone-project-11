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
        a.cusip,
        s.security_type,
        s.security_term,
        COALESCE(s.standardized_term, s.security_term) as standardized_term,
        a.bid_to_cover_ratio,
        a.high_yield,
        a.offering_amount,
        a.total_accepted,
        bd.primary_dealer_percentage,
        bd.direct_bidder_percentage,
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

# Navigation
page = st.sidebar.radio(
    "Select Analysis",
    ["Overview", "Advanced Analytics", "Correlations", "Data Export"]
)

# Load data
df = load_auction_data()

if df.empty:
    st.error("No data available. Please check the database connection.")
    st.stop()

# Filters
st.sidebar.markdown("---")
st.sidebar.header("Filters")

# Term display preference
use_standardized = st.sidebar.checkbox("Use Standardized Terms", value=True, 
                                      help="Match TreasuryDirect official classifications")

# Select which term column to use
term_column = 'standardized_term' if use_standardized else 'security_term'

# Date range filter
min_date = df['auction_date'].min()
max_date = df['auction_date'].max()

date_range = st.sidebar.date_input(
    "Date Range",
    value=(max_date - timedelta(days=365), max_date),
    min_value=min_date.date(),
    max_value=max_date.date()
)

# Security type filter
security_types = st.sidebar.multiselect(
    "Security Types",
    options=sorted(df['security_type'].unique()),
    default=sorted(df['security_type'].unique())
)

# Apply filters
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_datetime = pd.Timestamp(date_range[0])
    end_datetime = pd.Timestamp(date_range[1]) + timedelta(days=1)
    filtered_df = df[(df['auction_date'] >= start_datetime) & 
                     (df['auction_date'] < end_datetime) &
                     (df['security_type'].isin(security_types))].copy()
else:
    filtered_df = df[df['security_type'].isin(security_types)].copy()

# Page: Overview
if page == "Overview":
    # Metrics
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
    
    # Bid-to-Cover Trends
    st.subheader("Bid-to-Cover Ratio Trends")
    
    btc_data = filtered_df[filtered_df['bid_to_cover_ratio'].notna()].copy()
    btc_data = btc_data.sort_values('auction_date')
    
    # Calculate moving averages by security type
    for sec_type in btc_data['security_type'].unique():
        mask = btc_data['security_type'] == sec_type
        btc_data.loc[mask, 'ma_30'] = btc_data.loc[mask, 'bid_to_cover_ratio'].rolling(30, min_periods=1).mean()
    
    fig = px.scatter(
        btc_data,
        x='auction_date',
        y='bid_to_cover_ratio',
        color='security_type',
        title='Bid-to-Cover Ratios with 30-Day Moving Average',
        opacity=0.6,
        hover_data=[term_column]
    )
    
    # Add trend lines
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
    
    # Distribution charts
    col1, col2 = st.columns(2)
    
    with col1:
        type_counts = filtered_df['security_type'].value_counts()
        fig2 = px.pie(
            values=type_counts.values,
            names=type_counts.index,
            title='Auction Distribution by Type',
            hole=0.3
        )
        st.plotly_chart(fig2, use_container_width=True)
    
    with col2:
        # Dealer participation
        dealer_cols = ['primary_dealer_percentage', 'direct_bidder_percentage', 'indirect_bidder_percentage']
        dealer_data = filtered_df[dealer_cols].dropna()
        if not dealer_data.empty:
            avg_dealers = dealer_data.mean()
            fig3 = px.bar(
                x=['Primary Dealers', 'Direct Bidders', 'Indirect Bidders'],
                y=avg_dealers.values,
                title='Average Dealer Participation (%)',
                color=avg_dealers.index,
                color_discrete_sequence=['#1f77b4', '#ff7f0e', '#2ca02c']
            )
            fig3.update_layout(showlegend=False)
            st.plotly_chart(fig3, use_container_width=True)
        else:
            st.info("No dealer participation data available")
    
    # Term analysis with standardization
    if use_standardized:
        st.markdown("---")
        st.subheader("Security Terms Analysis (Standardized)")
        
        term_counts = filtered_df.groupby(['security_type', term_column]).size().reset_index(name='count')
        
        fig4 = px.treemap(
            term_counts,
            path=['security_type', term_column],
            values='count',
            title='Securities by Type and Standardized Term'
        )
        st.plotly_chart(fig4, use_container_width=True)

# Page: Advanced Analytics
elif page == "Advanced Analytics":
    st.header("Advanced Analytics")
    
    # Volatility Analysis
    st.subheader("📊 Volatility Analysis")
    
    vol_window = st.slider("Rolling Window (days)", 10, 60, 30)
    
    vol_data = filtered_df.copy()
    vol_data = vol_data.sort_values('auction_date')
    
    # Calculate volatility by security type
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
        title=f'{vol_window}-Day Rolling Volatility of Bid-to-Cover Ratios'
    )
    
    # Add mean line
    mean_vol = vol_data['volatility'].mean()
    fig.add_hline(y=mean_vol, line_dash="dash", 
                  annotation_text=f"Mean: {mean_vol:.3f}")
    
    st.plotly_chart(fig, use_container_width=True)
    
    # Statistical Summary
    st.subheader("📈 Statistical Summary")
    
    # Group by standardized or original term based on user selection
    stats = filtered_df.groupby(['security_type', term_column])['bid_to_cover_ratio'].agg([
        'count', 'mean', 'std', 'min', 'max'
    ]).round(3)
    
    # Reset index for better display
    stats = stats.reset_index()
    stats.columns = ['Security Type', 'Term', 'Count', 'Mean', 'Std Dev', 'Min', 'Max']
    
    st.dataframe(stats, use_container_width=True, hide_index=True)
    
    # Yield curve analysis
    if not filtered_df[filtered_df['high_yield'].notna()].empty:
        st.subheader("📉 Yield Analysis")
        
        yield_data = filtered_df[filtered_df['high_yield'].notna()].copy()
        
        # Create yield curve
        latest_date = yield_data['auction_date'].max()
        recent_yields = yield_data[yield_data['auction_date'] >= latest_date - timedelta(days=30)]
        
        if not recent_yields.empty:
            avg_yields = recent_yields.groupby(term_column)['high_yield'].mean().reset_index()
            
            fig_yield = px.line(
                avg_yields,
                x=term_column,
                y='high_yield',
                title='Current Yield Curve (30-day average)',
                markers=True
            )
            fig_yield.update_layout(xaxis_title="Security Term", yaxis_title="Yield (%)")
            st.plotly_chart(fig_yield, use_container_width=True)

# Page: Correlations
elif page == "Correlations":
    st.header("Correlation Analysis")
    
    # Select columns for correlation
    corr_columns = ['bid_to_cover_ratio', 'high_yield', 'offering_amount', 
                   'primary_dealer_percentage', 'direct_bidder_percentage', 
                   'indirect_bidder_percentage']
    
    available_cols = [col for col in corr_columns if col in filtered_df.columns]
    
    if len(available_cols) > 1:
        # Overall correlations
        st.subheader("Overall Market Correlations")
        
        overall_corr = filtered_df[available_cols].corr()
        
        fig_overall = px.imshow(
            overall_corr,
            text_auto='.2f',
            aspect="auto",
            color_continuous_scale='RdBu',
            range_color=[-1, 1],
            title="All Securities Correlation Matrix"
        )
        st.plotly_chart(fig_overall, use_container_width=True)
        
        # Correlations by security type
        st.subheader("Correlations by Security Type")
        
        tabs = st.tabs(filtered_df['security_type'].unique().tolist())
        
        for i, sec_type in enumerate(filtered_df['security_type'].unique()):
            with tabs[i]:
                sec_data = filtered_df[filtered_df['security_type'] == sec_type][available_cols].dropna()
                
                if len(sec_data) > 10:
                    corr_matrix = sec_data.corr()
                    
                    fig = px.imshow(
                        corr_matrix,
                        text_auto='.2f',
                        aspect="auto",
                        color_continuous_scale='RdBu',
                        range_color=[-1, 1],
                        title=f"{sec_type} Correlations"
                    )
                    st.plotly_chart(fig, use_container_width=True)
                    
                    # Key insights
                    st.markdown("**Key Observations:**")
                    
                    # Find strongest correlations (excluding diagonal)
                    corr_values = corr_matrix.values
                    np.fill_diagonal(corr_values, 0)
                    
                    max_corr_idx = np.unravel_index(np.argmax(np.abs(corr_values)), corr_values.shape)
                    max_corr_value = corr_values[max_corr_idx]
                    
                    if abs(max_corr_value) > 0.3:
                        col1 = corr_matrix.columns[max_corr_idx[0]]
                        col2 = corr_matrix.columns[max_corr_idx[1]]
                        st.write(f"- Strongest correlation: {col1} vs {col2} ({max_corr_value:.3f})")
                else:
                    st.info(f"Insufficient data for {sec_type} correlation analysis")
    else:
        st.warning("Not enough data columns available for correlation analysis")

# Page: Data Export
elif page == "Data Export":
    st.header("📥 Data Export")
    
    st.markdown("Export filtered data or generate reports")
    
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Export Filtered Data")
        
        # Prepare export data
        export_df = filtered_df.copy()
        
        # Add term preference
        if use_standardized:
            export_df['display_term'] = export_df['standardized_term']
        else:
            export_df['display_term'] = export_df['security_term']
        
        # Select columns for export
        export_columns = ['auction_date', 'cusip', 'security_type', 'display_term',
                         'bid_to_cover_ratio', 'high_yield', 'offering_amount',
                         'primary_dealer_percentage', 'direct_bidder_percentage']
        
        export_df = export_df[export_columns]
        
        # CSV export
        csv = export_df.to_csv(index=False)
        st.download_button(
            label="📄 Download as CSV",
            data=csv,
            file_name=f'treasury_auctions_{datetime.now().strftime("%Y%m%d")}.csv',
            mime='text/csv'
        )
        
        st.info(f"Dataset contains {len(export_df):,} records")
    
    with col2:
        st.subheader("Summary Statistics")
        
        summary_stats = {
            'Total Auctions': len(filtered_df),
            'Date Range': f"{filtered_df['auction_date'].min().date()} to {filtered_df['auction_date'].max().date()}",
            'Security Types': ', '.join(filtered_df['security_type'].unique()),
            'Average Bid-to-Cover': f"{filtered_df['bid_to_cover_ratio'].mean():.3f}",
            'Average Yield': f"{filtered_df['high_yield'].mean():.3f}%",
            'Total Volume': f"${filtered_df['offering_amount'].sum()/1e12:.2f}T"
        }
        
        for key, value in summary_stats.items():
            st.metric(key, value)

# Footer
st.markdown("---")
st.caption(f"""
Data from {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')} | 
Terms: {'Standardized' if use_standardized else 'Original'} | 
Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}
""")
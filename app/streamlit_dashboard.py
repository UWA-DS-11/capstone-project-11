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
    """Load enhanced auction data with new fields"""
    engine = get_db_connection()
    query = """
    SELECT 
        a.auction_date,
        a.auction_date_year,
        s.security_type,
        s.security_term,
        s.interest_rate as security_interest_rate,
        a.bid_to_cover_ratio,
        a.high_yield,
        a.low_yield,
        a.offering_amount,
        a.total_accepted,
        a.total_tendered,
        a.high_discount_rate,
        a.low_discount_rate,
        a.high_investment_rate,
        a.low_investment_rate,
        bd.primary_dealer_percentage,
        bd.indirect_bidder_percentage,
        bd.fima_accepted,
        bd.fima_percentage,
        bd.soma_accepted,
        bd.soma_percentage,
        bd.competitive_accepted,
        bd.noncompetitive_accepted,
        bd.treasury_retail_accepted
    FROM auctions a
    JOIN securities s ON a.cusip = s.cusip
    LEFT JOIN bidder_details bd ON a.auction_id = bd.auction_id
    WHERE a.auction_date >= '2020-01-01'
    ORDER BY a.auction_date DESC
    """
    df = pd.read_sql(query, engine, parse_dates=['auction_date'])
    return df

@st.cache_data(ttl=600)
def load_fiscal_policy_data():
    """Load fiscal policy indices"""
    engine = get_db_connection()
    query = """
    SELECT 
        date,
        total_articles,
        fiscal_articles,
        tariff_fiscal_articles,
        non_tariff_fiscal_articles,
        rate,
        tariff_rate,
        non_tariff_rate,
        fiscal_policy_index,
        tariff_fiscal_index,
        non_tariff_fiscal_index
    FROM fiscal_policy_indices
    ORDER BY date DESC
    """
    df = pd.read_sql(query, engine, parse_dates=['date'])
    return df

@st.cache_data(ttl=600)
def load_top_phrases(limit=50):
    """Load top phrases"""
    engine = get_db_connection()
    query = f"""
    SELECT phrase, count
    FROM top_phrases
    ORDER BY count DESC
    LIMIT {limit}
    """
    df = pd.read_sql(query, engine)
    return df

@st.cache_data(ttl=600)
def load_correlation_data():
    """Load combined data for correlation analysis"""
    engine = get_db_connection()
    query = """
    SELECT 
        a.auction_date as date,
        AVG(a.bid_to_cover_ratio) as avg_btc,
        AVG(a.high_yield) as avg_yield,
        AVG(a.offering_amount) as avg_offering,
        AVG(bd.fima_percentage) as avg_fima_pct,
        AVG(bd.soma_percentage) as avg_soma_pct,
        COUNT(*) as auction_count
    FROM auctions a
    LEFT JOIN bidder_details bd ON a.auction_id = bd.auction_id
    WHERE a.auction_date >= '2020-01-01'
    GROUP BY a.auction_date
    ORDER BY a.auction_date
    """
    auctions_df = pd.read_sql(query, engine, parse_dates=['date'])
    
    fiscal_df = load_fiscal_policy_data()
    
    # Merge on date
    merged_df = pd.merge(
        auctions_df, 
        fiscal_df, 
        on='date', 
        how='inner'
    )
    return merged_df

st.title("🏛️ Treasury Auction & Fiscal Policy Analytics")

# Sidebar navigation
page = st.sidebar.radio(
    "Select Analysis",
    [
        "📊 Overview", 
        "🚨 Market Stress Indicators",
        "🏦 Fed Participation (FIMA/SOMA)",
        "📈 Advanced Analytics", 
        "🔗 Correlations",
        "📰 Fiscal Policy Index",
        "💬 Top Phrases",
        "🔄 Fiscal-Auction Correlation"
    ]
)

# Load data
df = load_auction_data()

# Date filter in sidebar
st.sidebar.markdown("---")
st.sidebar.header("Filters")

min_date = df['auction_date'].min()
max_date = df['auction_date'].max()

date_range = st.sidebar.date_input(
    "Date Range",
    value=(max_date - timedelta(days=365), max_date)
)

# Ensure start_datetime and end_datetime are always defined
if isinstance(date_range, tuple) and len(date_range) == 2:
    start_datetime = pd.Timestamp(date_range[0])
    end_datetime = pd.Timestamp(date_range[1]) + timedelta(days=1)
    filtered_df = df[(df['auction_date'] >= start_datetime) & (df['auction_date'] < end_datetime)].copy()
else:
    # Default to showing all data if date range not properly selected
    start_datetime = min_date
    end_datetime = max_date + timedelta(days=1)
    filtered_df = df.copy()

# ==================== PAGES ====================

if page == "📊 Overview":
    st.header("Treasury Auction Overview")
    
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
    
    # NEW: Second row of metrics for Fed participation
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        avg_fima = filtered_df['fima_percentage'].mean()
        st.metric("Avg FIMA %", f"{avg_fima:.1f}%" if pd.notna(avg_fima) else "N/A")
    
    with col2:
        avg_soma = filtered_df['soma_percentage'].mean()
        st.metric("Avg SOMA %", f"{avg_soma:.1f}%" if pd.notna(avg_soma) else "N/A")
    
    with col3:
        total_competitive = filtered_df['competitive_accepted'].sum() / 1e9
        st.metric("Competitive Bids", f"${total_competitive:.1f}B")
    
    with col4:
        total_noncomp = filtered_df['noncompetitive_accepted'].sum() / 1e9
        st.metric("Non-Competitive Bids", f"${total_noncomp:.1f}B")
    
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

elif page == "🚨 Market Stress Indicators":
    st.header("Market Stress Indicators")
    st.caption("Based on Brookings Institution framework for detecting Treasury market stress")
    
    # Calculate yield spread (high - low)
    spread_data = filtered_df[
        (filtered_df['high_yield'].notna()) & 
        (filtered_df['low_yield'].notna())
    ].copy()
    spread_data['yield_spread'] = spread_data['high_yield'] - spread_data['low_yield']
    
    # Key stress indicators
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        recent_btc = filtered_df.tail(20)['bid_to_cover_ratio'].mean()
        historical_btc = filtered_df['bid_to_cover_ratio'].mean()
        btc_change = ((recent_btc / historical_btc) - 1) * 100
        st.metric(
            "Recent Bid-to-Cover",
            f"{recent_btc:.2f}",
            f"{btc_change:+.1f}% vs avg",
            help="Lower bid-to-cover may indicate weaker demand"
        )
    
    with col2:
        avg_spread = spread_data.tail(20)['yield_spread'].mean()
        st.metric(
            "Avg Yield Spread",
            f"{avg_spread:.3f}%",
            help="Higher spread indicates greater pricing uncertainty"
        )
    
    with col3:
        recent_fima = filtered_df.tail(20)['fima_percentage'].mean()
        st.metric(
            "Recent FIMA %",
            f"{recent_fima:.1f}%" if pd.notna(recent_fima) else "N/A",
            help="Foreign central bank participation"
        )
    
    with col4:
        recent_soma = filtered_df.tail(20)['soma_percentage'].mean()
        st.metric(
            "Recent SOMA %",
            f"{recent_soma:.1f}%" if pd.notna(recent_soma) else "N/A",
            help="Federal Reserve participation"
        )
    
    st.markdown("---")
    
    # Yield Spread Over Time
    st.subheader("1. Yield Spread Analysis")
    st.caption("Wide spreads suggest bidder uncertainty and potential stress")
    
    if not spread_data.empty:
        fig1 = px.line(
            spread_data.sort_values('auction_date'),
            x='auction_date',
            y='yield_spread',
            color='security_type',
            title='Yield Spread (High - Low) by Security Type'
        )
        st.plotly_chart(fig1, use_container_width=True)
    
    # Bid-to-Cover Trends
    st.subheader("2. Bid-to-Cover Trend")
    st.caption("Declining bid-to-cover ratios indicate weakening demand")
    
    btc_trend = filtered_df[filtered_df['bid_to_cover_ratio'].notna()].copy()
    btc_trend = btc_trend.sort_values('auction_date')
    btc_trend['btc_ma_30'] = btc_trend['bid_to_cover_ratio'].rolling(30, min_periods=1).mean()
    
    fig2 = go.Figure()
    fig2.add_trace(go.Scatter(
        x=btc_trend['auction_date'],
        y=btc_trend['bid_to_cover_ratio'],
        mode='markers',
        name='Actual',
        opacity=0.4
    ))
    fig2.add_trace(go.Scatter(
        x=btc_trend['auction_date'],
        y=btc_trend['btc_ma_30'],
        mode='lines',
        name='30-Day Avg',
        line=dict(color='red', width=3)
    ))
    fig2.update_layout(title='Bid-to-Cover Ratio Trend')
    st.plotly_chart(fig2, use_container_width=True)
    
    # Competitive vs Non-Competitive
    st.subheader("3. Bid Composition")
    st.caption("Changes in competitive/non-competitive mix reveal demand dynamics")
    
    bid_comp = filtered_df[
        (filtered_df['competitive_accepted'].notna()) & 
        (filtered_df['noncompetitive_accepted'].notna())
    ].copy()
    
    if not bid_comp.empty:
        bid_comp['total_bids'] = bid_comp['competitive_accepted'] + bid_comp['noncompetitive_accepted']
        bid_comp['comp_pct'] = (bid_comp['competitive_accepted'] / bid_comp['total_bids'] * 100)
        bid_comp['noncomp_pct'] = (bid_comp['noncompetitive_accepted'] / bid_comp['total_bids'] * 100)
        
        fig3 = go.Figure()
        fig3.add_trace(go.Scatter(
            x=bid_comp['auction_date'],
            y=bid_comp['comp_pct'],
            name='Competitive %',
            stackgroup='one',
            fillcolor='lightblue'
        ))
        fig3.add_trace(go.Scatter(
            x=bid_comp['auction_date'],
            y=bid_comp['noncomp_pct'],
            name='Non-Competitive %',
            stackgroup='one',
            fillcolor='lightcoral'
        ))
        fig3.update_layout(
            title='Competitive vs Non-Competitive Bid Distribution',
            yaxis_title='Percentage'
        )
        st.plotly_chart(fig3, use_container_width=True)

elif page == "🏦 Fed Participation (FIMA/SOMA)":
    st.header("Federal Reserve Participation Analysis")
    
    fed_data = filtered_df[
        (filtered_df['fima_percentage'].notna()) | 
        (filtered_df['soma_percentage'].notna())
    ].copy()
    
    if fed_data.empty:
        st.warning("No FIMA/SOMA data available for selected date range")
    else:
        # Summary metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            avg_fima_pct = fed_data['fima_percentage'].mean()
            st.metric("Avg FIMA %", f"{avg_fima_pct:.1f}%")
        
        with col2:
            total_fima = fed_data['fima_accepted'].sum() / 1e9
            st.metric("Total FIMA", f"${total_fima:.1f}B")
        
        with col3:
            avg_soma_pct = fed_data['soma_percentage'].mean()
            st.metric("Avg SOMA %", f"{avg_soma_pct:.1f}%")
        
        with col4:
            total_soma = fed_data['soma_accepted'].sum() / 1e9
            st.metric("Total SOMA", f"${total_soma:.1f}B")
        
        st.markdown("---")
        
        # FIMA Trends
        st.subheader("FIMA Participation Over Time")
        st.caption("Foreign and International Monetary Authorities - tracks foreign central bank demand")
        
        fima_trend = fed_data[fed_data['fima_percentage'].notna()].sort_values('auction_date')
        
        fig1 = px.scatter(
            fima_trend,
            x='auction_date',
            y='fima_percentage',
            color='security_type',
            size='fima_accepted',
            title='FIMA Participation by Security Type',
            labels={'fima_percentage': 'FIMA %', 'fima_accepted': 'FIMA Amount'}
        )
        st.plotly_chart(fig1, use_container_width=True)
        
        # SOMA Trends
        st.subheader("SOMA Participation Over Time")
        st.caption("System Open Market Account - Federal Reserve's own portfolio operations")
        
        soma_trend = fed_data[fed_data['soma_percentage'].notna()].sort_values('auction_date')
        
        if not soma_trend.empty:
            fig2 = px.scatter(
                soma_trend,
                x='auction_date',
                y='soma_percentage',
                color='security_type',
                size='soma_accepted',
                title='SOMA Participation by Security Type',
                labels={'soma_percentage': 'SOMA %', 'soma_accepted': 'SOMA Amount'}
            )
            st.plotly_chart(fig2, use_container_width=True)
        else:
            st.info("No SOMA participation data available")
        
        # Combined Fed Participation
        st.subheader("Combined Federal Reserve Impact")
        
        fed_combined = fed_data.copy()
        fed_combined['fed_total_pct'] = (
            fed_combined['fima_percentage'].fillna(0) + 
            fed_combined['soma_percentage'].fillna(0)
        )
        
        fig3 = px.line(
            fed_combined.sort_values('auction_date'),
            x='auction_date',
            y='fed_total_pct',
            color='security_type',
            title='Total Fed Participation (FIMA + SOMA)',
            labels={'fed_total_pct': 'Total Fed %'}
        )
        st.plotly_chart(fig3, use_container_width=True)
        
        # By security type breakdown
        st.subheader("Fed Participation by Security Type")
        
        fed_by_type = fed_data.groupby('security_type').agg({
            'fima_percentage': 'mean',
            'soma_percentage': 'mean',
            'fima_accepted': 'sum',
            'soma_accepted': 'sum'
        }).reset_index()
        
        col1, col2 = st.columns(2)
        
        with col1:
            fig4 = px.bar(
                fed_by_type,
                x='security_type',
                y=['fima_percentage', 'soma_percentage'],
                title='Average Fed Participation % by Security Type',
                barmode='group'
            )
            st.plotly_chart(fig4, use_container_width=True)
        
        with col2:
            fed_by_type['fima_accepted_b'] = fed_by_type['fima_accepted'] / 1e9
            fed_by_type['soma_accepted_b'] = fed_by_type['soma_accepted'] / 1e9
            
            fig5 = px.bar(
                fed_by_type,
                x='security_type',
                y=['fima_accepted_b', 'soma_accepted_b'],
                title='Total Fed Participation ($ Billions) by Security Type',
                barmode='group',
                labels={'value': 'Billions USD'}
            )
            st.plotly_chart(fig5, use_container_width=True)

elif page == "📈 Advanced Analytics":
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
    
    st.dataframe(stats, use_container_width=True)
    
    # NEW: Discount/Investment Rate Analysis
    st.subheader("Rate Spread Analysis")
    
    rate_data = filtered_df[
        (filtered_df['high_discount_rate'].notna()) & 
        (filtered_df['low_discount_rate'].notna())
    ].copy()
    
    if not rate_data.empty:
        rate_data['discount_spread'] = rate_data['high_discount_rate'] - rate_data['low_discount_rate']
        
        fig_spread = px.scatter(
            rate_data,
            x='auction_date',
            y='discount_spread',
            color='security_type',
            title='Discount Rate Spread (High - Low)',
            labels={'discount_spread': 'Spread (%)'}
        )
        st.plotly_chart(fig_spread, use_container_width=True)

elif page == "🔗 Correlations":
    st.header("Correlation Analysis")
    
    # NEW: Include new fields in correlation
    corr_columns = [
        'bid_to_cover_ratio', 'high_yield', 'offering_amount', 
        'primary_dealer_percentage', 'indirect_bidder_percentage',
        'fima_percentage', 'soma_percentage'
    ]
    
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

elif page == "📰 Fiscal Policy Index":
    st.header("Fiscal Policy Index Analysis")
    
    fiscal_df = load_fiscal_policy_data()
    
    if fiscal_df.empty:
        st.warning("No fiscal policy data available")
    else:
        # Apply date filter
        fiscal_filtered = fiscal_df[
            (fiscal_df['date'] >= start_datetime) & 
            (fiscal_df['date'] < end_datetime)
        ].copy()
        
        # Key Metrics
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            total_articles = fiscal_filtered['total_articles'].sum()
            st.metric("Total Articles", f"{total_articles:,}")
        
        with col2:
            avg_fiscal_rate = fiscal_filtered['rate'].mean() * 100
            st.metric("Avg Fiscal Rate", f"{avg_fiscal_rate:.1f}%")
        
        with col3:
            latest_index = fiscal_filtered.iloc[0]['fiscal_policy_index'] if len(fiscal_filtered) > 0 else 0
            st.metric("Latest Policy Index", f"{latest_index:.2f}")
        
        with col4:
            avg_tariff_rate = fiscal_filtered['tariff_rate'].mean() * 100
            st.metric("Avg Tariff Rate", f"{avg_tariff_rate:.1f}%")
        
        st.markdown("---")
        
        # Fiscal Policy Index Over Time
        st.subheader("Fiscal Policy Index Trends")
        
        # Add rolling average selector
        col_smooth1, col_smooth2 = st.columns([3, 1])
        with col_smooth2:
            rolling_window = st.selectbox(
                "Smoothing",
                options=['Daily (Raw)', '7-Day Avg', '30-Day Avg', '90-Day Avg'],
                index=2  # Default to 30-Day
            )
        
        # Calculate rolling averages based on selection
        plot_df = fiscal_filtered.copy().sort_values('date')
        
        if rolling_window != 'Daily (Raw)':
            window_size = int(rolling_window.split('-')[0])
            plot_df['fiscal_policy_index_smooth'] = plot_df['fiscal_policy_index'].rolling(
                window=window_size, min_periods=1
            ).mean()
            plot_df['tariff_fiscal_index_smooth'] = plot_df['tariff_fiscal_index'].rolling(
                window=window_size, min_periods=1
            ).mean()
            plot_df['non_tariff_fiscal_index_smooth'] = plot_df['non_tariff_fiscal_index'].rolling(
                window=window_size, min_periods=1
            ).mean()
            
            # Use smoothed columns
            fiscal_col = 'fiscal_policy_index_smooth'
            tariff_col = 'tariff_fiscal_index_smooth'
            non_tariff_col = 'non_tariff_fiscal_index_smooth'
            title_suffix = f' ({rolling_window})'
        else:
            # Use raw columns
            fiscal_col = 'fiscal_policy_index'
            tariff_col = 'tariff_fiscal_index'
            non_tariff_col = 'non_tariff_fiscal_index'
            title_suffix = ' (Daily)'
        
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=plot_df['date'],
            y=plot_df[fiscal_col],
            mode='lines',
            name='Overall Fiscal Index',
            line=dict(width=3, color='blue')
        ))
        
        fig.add_trace(go.Scatter(
            x=plot_df['date'],
            y=plot_df[tariff_col],
            mode='lines',
            name='Tariff Fiscal Index',
            line=dict(width=2, color='red', dash='dash')
        ))
        
        fig.add_trace(go.Scatter(
            x=plot_df['date'],
            y=plot_df[non_tariff_col],
            mode='lines',
            name='Non-Tariff Fiscal Index',
            line=dict(width=2, color='green', dash='dash')
        ))
        
        fig.update_layout(
            title=f'Fiscal Policy Indices Over Time{title_suffix}',
            xaxis_title='Date',
            yaxis_title='Index Value',
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Article Composition
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Fiscal Article Rate Over Time")
            fig2 = px.line(
                fiscal_filtered,
                x='date',
                y='rate',
                title='Proportion of Fiscal Articles'
            )
            fig2.update_yaxes(tickformat='.1%')
            st.plotly_chart(fig2, use_container_width=True)
        
        with col2:
            st.subheader("Tariff vs Non-Tariff Articles")
            
            avg_data = pd.DataFrame({
                'Type': ['Tariff', 'Non-Tariff'],
                'Average Articles': [
                    fiscal_filtered['tariff_fiscal_articles'].mean(),
                    fiscal_filtered['non_tariff_fiscal_articles'].mean()
                ]
            })
            
            fig3 = px.bar(
                avg_data,
                x='Type',
                y='Average Articles',
                title='Average Daily Fiscal Articles by Type',
                color='Type'
            )
            st.plotly_chart(fig3, use_container_width=True)
        
        # Recent Data Table
        st.subheader("Recent Fiscal Policy Data")
        display_cols = ['date', 'total_articles', 'fiscal_articles', 
                       'tariff_fiscal_articles', 'fiscal_policy_index']
        st.dataframe(
            fiscal_filtered[display_cols].head(20),
            use_container_width=True
        )

elif page == "💬 Top Phrases":
    st.header("Top Phrases from Fiscal Articles")
    
    phrases_df = load_top_phrases(limit=100)
    
    if phrases_df.empty:
        st.warning("No phrase data available")
    else:
        col1, col2 = st.columns([2, 1])
        
        with col1:
            st.subheader("Top 30 Phrases")
            top_30 = phrases_df.head(30)
            
            fig = px.bar(
                top_30.sort_values('count', ascending=True),
                y='phrase',
                x='count',
                orientation='h',
                title='Most Frequent Phrases in Fiscal Policy Articles',
                labels={'count': 'Frequency', 'phrase': 'Phrase'}
            )
            fig.update_layout(height=800)
            st.plotly_chart(fig, use_container_width=True)
        
        with col2:
            st.subheader("Key Statistics")
            st.metric("Total Unique Phrases", len(phrases_df))
            st.metric("Top Phrase", phrases_df.iloc[0]['phrase'])
            st.metric("Top Phrase Count", f"{phrases_df.iloc[0]['count']:,}")
            
            st.markdown("---")
            st.subheader("Top 10 Phrases")
            for idx, row in phrases_df.head(10).iterrows():
                st.write(f"**{idx+1}. {row['phrase']}** - {row['count']:,}")
        
        # Word cloud simulation using bar chart
        st.subheader("Phrase Cloud (Top 50)")
        top_50 = phrases_df.head(50)
        
        fig2 = px.treemap(
            top_50,
            path=['phrase'],
            values='count',
            title='Phrase Frequency Treemap'
        )
        st.plotly_chart(fig2, use_container_width=True)

elif page == "🔄 Fiscal-Auction Correlation":
    st.header("Fiscal Policy & Treasury Auction Correlation")
    
    corr_df = load_correlation_data()
    
    if corr_df.empty:
        st.warning("Insufficient data for correlation analysis")
    else:
        # Apply date filter
        corr_filtered = corr_df[
            (corr_df['date'] >= start_datetime) & 
            (corr_df['date'] < end_datetime)
        ].copy()
        
        st.subheader("How does fiscal policy sentiment affect Treasury auctions?")
        
        # Add rolling average selector
        col_corr1, col_corr2 = st.columns([3, 1])
        with col_corr2:
            rolling_window_corr = st.selectbox(
                "Smoothing",
                options=['Daily (Raw)', '7-Day Avg', '30-Day Avg', '90-Day Avg'],
                index=2,  # Default to 30-Day
                key='correlation_rolling'
            )
        
        # Calculate rolling averages
        corr_plot_df = corr_filtered.copy().sort_values('date')
        
        if rolling_window_corr != 'Daily (Raw)':
            window_size = int(rolling_window_corr.split('-')[0])
            corr_plot_df['fiscal_policy_index_smooth'] = corr_plot_df['fiscal_policy_index'].rolling(
                window=window_size, min_periods=1
            ).mean()
            corr_plot_df['avg_btc_smooth'] = corr_plot_df['avg_btc'].rolling(
                window=window_size, min_periods=1
            ).mean()
            
            fiscal_col_corr = 'fiscal_policy_index_smooth'
            btc_col = 'avg_btc_smooth'
            title_suffix_corr = f' ({rolling_window_corr})'
        else:
            fiscal_col_corr = 'fiscal_policy_index'
            btc_col = 'avg_btc'
            title_suffix_corr = ' (Daily)'
        
        # Dual-axis chart: Fiscal Index vs Bid-to-Cover
        fig = go.Figure()
        
        fig.add_trace(go.Scatter(
            x=corr_plot_df['date'],
            y=corr_plot_df[fiscal_col_corr],
            mode='lines',
            name='Fiscal Policy Index',
            line=dict(color='blue', width=2),
            yaxis='y'
        ))
        
        fig.add_trace(go.Scatter(
            x=corr_plot_df['date'],
            y=corr_plot_df[btc_col],
            mode='lines',
            name='Avg Bid-to-Cover',
            line=dict(color='red', width=2),
            yaxis='y2'
        ))
        
        fig.update_layout(
            title=f'Fiscal Policy Index vs Treasury Bid-to-Cover Ratio{title_suffix_corr}',
            xaxis=dict(title='Date'),
            yaxis=dict(
                title='Fiscal Policy Index',
                side='left'
            ),
            yaxis2=dict(
                title='Avg Bid-to-Cover Ratio',
                overlaying='y',
                side='right'
            ),
            hovermode='x unified'
        )
        
        st.plotly_chart(fig, use_container_width=True)
        
        # Correlation metrics - NEW: Include FIMA/SOMA
        st.subheader("Correlation Analysis")
        
        col1, col2, col3, col4 = st.columns(4)
        
        # Calculate correlations
        corr_btc = corr_filtered[['fiscal_policy_index', 'avg_btc']].corr().iloc[0, 1]
        corr_yield = corr_filtered[['fiscal_policy_index', 'avg_yield']].corr().iloc[0, 1]
        corr_tariff_btc = corr_filtered[['tariff_fiscal_index', 'avg_btc']].corr().iloc[0, 1]
        
        # NEW: FIMA correlation with fiscal index
        fima_data = corr_filtered[['fiscal_policy_index', 'avg_fima_pct']].dropna()
        corr_fima = fima_data.corr().iloc[0, 1] if len(fima_data) > 10 else None
        
        with col1:
            st.metric(
                "Fiscal Index ↔ Bid-to-Cover",
                f"{corr_btc:.3f}",
                help="Correlation between fiscal policy index and bid-to-cover ratio"
            )
        
        with col2:
            st.metric(
                "Fiscal Index ↔ Yield",
                f"{corr_yield:.3f}",
                help="Correlation between fiscal policy index and treasury yields"
            )
        
        with col3:
            st.metric(
                "Tariff Index ↔ Bid-to-Cover",
                f"{corr_tariff_btc:.3f}",
                help="Correlation between tariff-related fiscal index and bid-to-cover ratio"
            )
        
        with col4:
            if corr_fima is not None:
                st.metric(
                    "Fiscal Index ↔ FIMA %",
                    f"{corr_fima:.3f}",
                    help="Correlation between fiscal policy and foreign central bank participation"
                )
            else:
                st.metric("Fiscal Index ↔ FIMA %", "N/A")
        
        st.markdown("---")
        
        # Scatter plot: Fiscal Index vs Yield
        col1, col2 = st.columns(2)
        
        with col1:
            st.subheader("Fiscal Index vs Bid-to-Cover")
            fig3 = px.scatter(
                corr_filtered,
                x='fiscal_policy_index',
                y='avg_btc',
                title='Relationship: Fiscal Policy Index & Bid-to-Cover',
                labels={
                    'fiscal_policy_index': 'Fiscal Policy Index',
                    'avg_btc': 'Avg Bid-to-Cover Ratio'
                }
            )
            st.plotly_chart(fig3, use_container_width=True)
        
        with col2:
            st.subheader("Fiscal Index vs Treasury Yield")
            fig4 = px.scatter(
                corr_filtered,
                x='fiscal_policy_index',
                y='avg_yield',
                title='Relationship: Fiscal Policy Index & Yields',
                labels={
                    'fiscal_policy_index': 'Fiscal Policy Index',
                    'avg_yield': 'Avg Treasury Yield (%)'
                }
            )
            st.plotly_chart(fig4, use_container_width=True)
        
        # Correlation heatmap - NEW: Include Fed participation
        st.subheader("Full Correlation Matrix")
        
        corr_cols = ['fiscal_policy_index', 'tariff_fiscal_index', 
                    'non_tariff_fiscal_index', 'avg_btc', 'avg_yield',
                    'avg_fima_pct', 'avg_soma_pct']
        
        # Only include columns that exist in the data
        available_corr_cols = [col for col in corr_cols if col in corr_filtered.columns]
        corr_matrix = corr_filtered[available_corr_cols].corr()
        
        fig5 = px.imshow(
            corr_matrix,
            text_auto='.3f',
            aspect='auto',
            color_continuous_scale='RdBu',
            range_color=[-1, 1],
            labels=dict(color="Correlation")
        )
        fig5.update_layout(
            title='Correlation Matrix: Fiscal Policy vs Treasury Auctions & Fed Participation'
        )
        st.plotly_chart(fig5, use_container_width=True)
        
        # Interpretation
        st.info("""
        **📊 Interpretation Guide:**
        - **Positive correlation (>0.5)**: When fiscal policy index increases, the metric tends to increase
        - **Negative correlation (<-0.5)**: When fiscal policy index increases, the metric tends to decrease
        - **Weak correlation (-0.3 to 0.3)**: Little to no linear relationship
        
        **💡 Key Insights:**
        - High fiscal policy index may indicate increased uncertainty or policy changes
        - Tariff-related fiscal news may have different market impact than general fiscal policy
        - FIMA participation reflects foreign central bank confidence in US Treasuries
        - SOMA participation shows Federal Reserve market support levels
        - Monitor these correlations to anticipate auction performance during fiscal policy events
        """)

# Footer
st.markdown("---")
st.caption(f"Data from {min_date.strftime('%Y-%m-%d')} to {max_date.strftime('%Y-%m-%d')} | Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M')}")
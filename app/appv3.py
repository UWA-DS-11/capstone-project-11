# streamlit_app.py
import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from sqlalchemy import create_engine
from datetime import datetime, timedelta
import os

st.set_page_config(
    page_title="Treasury Auction Analytics",
    layout="wide"
)

# -----------------------
# Database / Data loaders
# -----------------------
@st.cache_resource
def get_db_connection():
    database_url = os.getenv('DATABASE_URL', 'postgresql://treasury_user:treasury_secure_pass_2025@localhost:5432/treasury_db')
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
        bd.indirect_bidder_percentage,
        bd.fima_percentage,
        bd.soma_percentage
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
    engine = get_db_connection()
    query = """
    SELECT 
        a.auction_date as date,
        AVG(a.bid_to_cover_ratio) as avg_btc,
        AVG(a.high_yield) as avg_yield,
        AVG(a.offering_amount) as avg_offering,
        COUNT(*) as auction_count
    FROM auctions a
    WHERE a.auction_date >= '2020-01-01'
    GROUP BY a.auction_date
    ORDER BY a.auction_date
    """
    auctions_df = pd.read_sql(query, engine, parse_dates=['date'])
    fiscal_df = load_fiscal_policy_data()
    merged_df = pd.merge(auctions_df, fiscal_df, on='date', how='inner')
    return merged_df

# -----------------------
# Load data
# -----------------------
df = load_auction_data()
fiscal_df_all = load_fiscal_policy_data()
phrases_df_all = load_top_phrases(limit=500)
corr_df_all = load_correlation_data()

# Protect against empty dataset
if df.empty:
    st.warning("Auction dataset is empty — check your DB or DATABASE_URL environment variable.")
    st.stop()

min_date = df['auction_date'].min()
max_date = df['auction_date'].max()

# -----------------------
# Sidebar / Global filters
# -----------------------
st.sidebar.header("Global Filters")

default_start = (max_date - timedelta(days=365)).date()
default_end = max_date.date()
date_range = st.sidebar.date_input(
    "Date Range",
    value=(default_start, default_end),
    min_value=min_date.date(),
    max_value=max_date.date()
)

security_options = ["All"] + sorted(df['security_type'].dropna().unique().tolist())
security_selected = st.sidebar.selectbox("Security Type", options=security_options, index=0)

#global_rolling = st.sidebar.selectbox("Rolling smoothing (global)", options=["Daily (Raw)", "7-Day", "30-Day"], index=2)

# -----------------------
# Helper: apply global filters
# -----------------------
def apply_filters(auctions_df):
    if isinstance(date_range, tuple) and len(date_range) == 2:
        start_dt = pd.Timestamp(date_range[0])
        end_dt = pd.Timestamp(date_range[1]) + timedelta(days=1)
    else:
        start_dt = pd.Timestamp(date_range[0])
        end_dt = pd.Timestamp(date_range) + timedelta(days=1)
    out = auctions_df[(auctions_df['auction_date'] >= start_dt) & (auctions_df['auction_date'] < end_dt)].copy()
    if security_selected != "All":
        out = out[out['security_type'] == security_selected].copy()
    return out, start_dt, end_dt

filtered_df, filter_start, filter_end = apply_filters(df)

# -----------------------
# Page structure: top-level tabs
# -----------------------
st.title("Treasury Auction & Fiscal Policy Analytics")
main_tabs = st.tabs(["Treasury Dashboard", "Fiscal Dashboard"])  # Removed Correlation Explorer

# -----------------------
# Treasury Dashboard Tab
# -----------------------
with main_tabs[0]:
    treasury_subtabs = st.tabs(["Overview", "Advanced Analytics", "Auction Correlations"])
    
    # ---------- Overview ----------
    with treasury_subtabs[0]:
        st.header("Treasury Overview")
        col_a, col_b = st.columns([3, 2])
        with col_a:
            st.subheader("Summary Metrics")
            metric_cols = st.columns(4)
            total_auctions = len(filtered_df)
            recent_30 = filtered_df[filtered_df['auction_date'] >= (pd.Timestamp.now() - timedelta(days=30))]
            recent_7 = filtered_df[filtered_df['auction_date'] >= (pd.Timestamp.now() - timedelta(days=7))]
            metric_cols[0].metric("Total Auctions", f"{total_auctions:,}", delta=f"{len(recent_30)} in 30d")
            avg_btc = filtered_df['bid_to_cover_ratio'].mean()
            metric_cols[1].metric("Avg Bid-to-Cover", f"{avg_btc:.2f}" if pd.notna(avg_btc) else "N/A",
                                  delta=f"{len(recent_7)} in 7d")
            total_offered = filtered_df['offering_amount'].sum() / 1e9
            metric_cols[2].metric("Total Offered (B)", f"${total_offered:.1f}B")
            latest_yield_row = filtered_df[filtered_df['high_yield'].notna()].sort_values('auction_date', ascending=False).head(1)
            latest_yield = latest_yield_row.iloc[0]['high_yield'] if not latest_yield_row.empty else None
            metric_cols[3].metric("Latest Yield", f"{latest_yield:.2f}%" if latest_yield is not None else "N/A")
        
        with col_b:
            st.subheader("Quick selectors")
            overview_roll = st.selectbox("Overview smoothing", options=["Daily (Raw)", "7-Day", "30-Day"], index=1)
            st.caption("Recent auctions (top 5)")
            st.dataframe(filtered_df.sort_values('auction_date', ascending=False).head(5)[
                ['auction_date', 'security_type', 'offering_amount', 'bid_to_cover_ratio']
            ], use_container_width=True)
        
        st.markdown("---")
        st.subheader("Bid-to-Cover Trend")
        btc_plot_df = filtered_df[['auction_date', 'security_type', 'bid_to_cover_ratio']].dropna().sort_values('auction_date')
        if btc_plot_df.empty:
            st.info("No bid-to-cover data for the selected filters")
        else:
            roll_map = {"Daily (Raw)": 1, "7-Day": 7, "30-Day": 30}
            win = roll_map.get(overview_roll, 30)
            btc_plot_df = btc_plot_df.groupby('security_type', group_keys=False).apply(
                lambda d: d.assign(rolling= d['bid_to_cover_ratio'].rolling(win, min_periods=1).mean())
            ).reset_index(drop=True)
            fig = px.line(btc_plot_df, x='auction_date', y='bid_to_cover_ratio', color='security_type',
                          title=f"Bid-to-Cover (raw) and {win}-day rolling")
            for sec in btc_plot_df['security_type'].unique():
                sec_data = btc_plot_df[btc_plot_df['security_type'] == sec]
                fig.add_trace(go.Scatter(x=sec_data['auction_date'], y=sec_data['rolling'],
                                         mode='lines', name=f"{sec} {win}-day avg", line=dict(width=2, dash='dash')))
            st.plotly_chart(fig, use_container_width=True)
        
        st.markdown("### Auction Mix & Dealer Participation")
        col1, col2 = st.columns(2)
        with col1:
            type_counts = filtered_df['security_type'].value_counts()
            fig1 = px.pie(values=type_counts.values, names=type_counts.index, title='Auction Distribution by Type')
            st.plotly_chart(fig1, use_container_width=True)
        with col2:
            dealer_data = filtered_df[['primary_dealer_percentage', 'indirect_bidder_percentage']].dropna()
            if not dealer_data.empty:
                avg_dealers = dealer_data.mean()
                fig2 = px.bar(x=avg_dealers.index, y=avg_dealers.values, labels={'x': 'Bidder Type', 'y': 'Percentage'},
                              title='Average Dealer Participation')
                st.plotly_chart(fig2, use_container_width=True)

        # ---------- FIMA vs SOMA Trend ----------
        st.markdown("### FIMA vs SOMA Trend")
        fima_soma_ts = filtered_df[['auction_date', 'fima_percentage', 'soma_percentage']].dropna()
        if not fima_soma_ts.empty:
            roll_map = {"Daily (Raw)": 1, "7-Day": 7, "30-Day": 30}
            win_fs = roll_map.get(overview_roll, 30)
            fima_soma_ts_sorted = fima_soma_ts.sort_values('auction_date')
            
            # Apply rolling average for smoother lines
            fima_soma_ts_sorted['fima_smooth'] = fima_soma_ts_sorted['fima_percentage'].rolling(win_fs, min_periods=1).mean()
            fima_soma_ts_sorted['soma_smooth'] = fima_soma_ts_sorted['soma_percentage'].rolling(win_fs, min_periods=1).mean()
            
            fig_fs = go.Figure()
            fig_fs.add_trace(go.Scatter(x=fima_soma_ts_sorted['auction_date'], y=fima_soma_ts_sorted['fima_percentage'],
                                        mode='lines+markers', name='FIMA (Raw)', line=dict(color='blue')))
            fig_fs.add_trace(go.Scatter(x=fima_soma_ts_sorted['auction_date'], y=fima_soma_ts_sorted['fima_smooth'],
                                        mode='lines', name=f'FIMA {win_fs}-Day Avg', line=dict(color='blue', dash='dash')))
            
            fig_fs.add_trace(go.Scatter(x=fima_soma_ts_sorted['auction_date'], y=fima_soma_ts_sorted['soma_percentage'],
                                        mode='lines+markers', name='SOMA (Raw)', line=dict(color='green')))
            fig_fs.add_trace(go.Scatter(x=fima_soma_ts_sorted['auction_date'], y=fima_soma_ts_sorted['soma_smooth'],
                                        mode='lines', name=f'SOMA {win_fs}-Day Avg', line=dict(color='green', dash='dash')))
            
            fig_fs.update_layout(
                title=f"FIMA vs SOMA Share Trend ({overview_roll})",
                xaxis_title='Auction Date',
                yaxis_title='Percentage (%)',
                hovermode='x unified'
            )
            st.plotly_chart(fig_fs, use_container_width=True)
        else:
            st.info("No FIMA/SOMA data available for the selected filters")

    # ---------- Advanced Analytics ----------
    with treasury_subtabs[1]:
        st.header("Advanced Analytics")
        vol_window = st.slider("Volatility rolling window (days)", min_value=7, max_value=180, value=30, step=1)
        vol_df = filtered_df.sort_values('auction_date').copy()
        if vol_df.empty:
            st.info("No data to calculate volatility")
        else:
            vol_df = vol_df.groupby('security_type', group_keys=False).apply(
                lambda d: d.assign(volatility=d['bid_to_cover_ratio'].rolling(vol_window, min_periods=5).std())
            ).reset_index(drop=True)
            fig = px.line(vol_df[vol_df['volatility'].notna()], x='auction_date', y='volatility', color='security_type',
                          title=f'{vol_window}-Day Rolling Volatility')
            st.plotly_chart(fig, use_container_width=True)

        st.subheader("Statistical Summary by Security")
        stats = filtered_df.groupby('security_type')['bid_to_cover_ratio'].agg(['count', 'mean', 'std', 'min', 'max']).round(3)
        st.dataframe(stats, use_container_width=True)

    # ---------- Auction Correlations ----------
    with treasury_subtabs[2]:
        st.header("Auction Correlations")
        corr_columns = ['bid_to_cover_ratio', 'high_yield', 'offering_amount', 'primary_dealer_percentage', 'indirect_bidder_percentage']
        available_cols = [col for col in corr_columns if col in filtered_df.columns]
        if len(available_cols) > 1:
            for sec_type in filtered_df['security_type'].unique():
                sec_data = filtered_df[filtered_df['security_type'] == sec_type][available_cols].dropna()
                if len(sec_data) > 10:
                    st.subheader(f"{sec_type} Correlations")
                    corr_matrix = sec_data.corr()
                    fig = px.imshow(corr_matrix, text_auto='.2f', aspect="auto",
                                    color_continuous_scale='RdBu', range_color=[-1, 1])
                    st.plotly_chart(fig, use_container_width=True)
        else:
            st.info("Insufficient data for correlation analysis")

# -----------------------
# Fiscal Dashboard Tab
# -----------------------
with main_tabs[1]:
    fiscal_subtabs = st.tabs(["Fiscal Policy Index", "Top Phrases", "Fiscal-Auction Correlation"])
    
    with fiscal_subtabs[0]:
        st.header("Fiscal Policy Index")
        if fiscal_df_all.empty:
            st.warning("No fiscal policy data available")
        else:
            fiscal_filtered = fiscal_df_all[(fiscal_df_all['date'] >= filter_start) & (fiscal_df_all['date'] < filter_end)].copy().sort_values('date')
            col1, col2, col3, col4 = st.columns(4)
            with col1:
                st.metric("Total Articles", f"{int(fiscal_filtered['total_articles'].sum()):,}")
            with col2:
                st.metric("Average Fiscal Rate", f"{(fiscal_filtered['rate'].mean()*100):.1f}%")
            with col3:
                latest_index = fiscal_filtered.iloc[-1]['fiscal_policy_index'] if not fiscal_filtered.empty else float('nan')
                st.metric("Latest Policy Index", f"{latest_index:.2f}")
            with col4:
                st.metric("Avg Tariff Rate", f"{(fiscal_filtered['tariff_rate'].mean()*100):.1f}%")
            
            st.markdown("---")
            smooth_choice = st.selectbox("Smoothing", options=["Daily (Raw)", "7-Day", "30-Day", "90-Day"], index=2)
            roll_map = {"Daily (Raw)": 1, "7-Day": 7, "30-Day": 30, "90-Day": 90}
            window = roll_map.get(smooth_choice, 30)
            plot_df = fiscal_filtered.copy()
            if window > 1:
                plot_df['fiscal_policy_index_smooth'] = plot_df['fiscal_policy_index'].rolling(window, min_periods=1).mean()
                plot_df['tariff_fiscal_index_smooth'] = plot_df['tariff_fiscal_index'].rolling(window, min_periods=1).mean()
                plot_df['non_tariff_fiscal_index_smooth'] = plot_df['non_tariff_fiscal_index'].rolling(window, min_periods=1).mean()
                fiscal_col = 'fiscal_policy_index_smooth'
                tariff_col = 'tariff_fiscal_index_smooth'
                non_tariff_col = 'non_tariff_fiscal_index_smooth'
            else:
                fiscal_col = 'fiscal_policy_index'
                tariff_col = 'tariff_fiscal_index'
                non_tariff_col = 'non_tariff_fiscal_index'

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df[fiscal_col], mode='lines', name='Fiscal Policy Index'))
            fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df[tariff_col], mode='lines', name='Tariff Index'))
            fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df[non_tariff_col], mode='lines', name='Non-Tariff Index'))
            fig.update_layout(title=f"Fiscal Policy Indices ({smooth_choice})", xaxis_title='Date', yaxis_title='Index')
            st.plotly_chart(fig, use_container_width=True)

            st.markdown("### Article Composition")
            c1, c2 = st.columns(2)
            with c1:
                fig_rate = px.line(plot_df, x='date', y='rate', title='Proportion of Fiscal Articles')
                fig_rate.update_yaxes(tickformat='.1%')
                st.plotly_chart(fig_rate, use_container_width=True)
            with c2:
                avg_data = pd.DataFrame({
                    'Type': ['Tariff', 'Non-Tariff'],
                    'Average Articles': [
                        fiscal_filtered['tariff_fiscal_articles'].mean(),
                        fiscal_filtered['non_tariff_fiscal_articles'].mean()
                    ]
                })
                fig3 = px.bar(avg_data, x='Type', y='Average Articles', title='Average Daily Fiscal Articles by Type')
                st.plotly_chart(fig3, use_container_width=True)
            
            st.markdown("Recent fiscal policy data")
            st.dataframe(fiscal_filtered[['date', 'total_articles', 'fiscal_articles', 'tariff_fiscal_articles', 'fiscal_policy_index']].tail(50),
                         use_container_width=True)

    with fiscal_subtabs[1]:
        st.header("Top Phrases from Fiscal Articles")
        if phrases_df_all.empty:
            st.warning("No phrase data available")
        else:
            top_n = st.slider("Number of phrases to show", min_value=10, max_value=200, value=50, step=10)
            top_phrases = phrases_df_all.head(top_n)
            c1, c2 = st.columns([3,1])
            with c1:
                fig = px.bar(top_phrases.sort_values('count', ascending=True), y='phrase', x='count', orientation='h',
                             title=f"Top {top_n} phrases")
                st.plotly_chart(fig, use_container_width=True)
            with c2:
                st.subheader("Key stats")
                st.metric("Unique Phrases", f"{len(phrases_df_all):,}")
                top_phrase = phrases_df_all.iloc[0]['phrase'] if not phrases_df_all.empty else "N/A"
                top_count = int(phrases_df_all.iloc[0]['count']) if not phrases_df_all.empty else 0
                st.metric("Top Phrase", top_phrase)
                st.metric("Top Phrase Count", f"{top_count:,}")
            st.markdown("Phrase frequency treemap")
            fig2 = px.treemap(top_phrases.head(200), path=['phrase'], values='count', title='Phrase Frequency Treemap')
            st.plotly_chart(fig2, use_container_width=True)

        # ----- Fiscal-Auction Correlation Tab (Combined) -----
    with fiscal_subtabs[2]:
        st.header("Fiscal Policy vs Avg Bid-to-Cover & Tariff/Non-Tariff")
        if corr_df_all.empty:
            st.warning("Insufficient data for correlation analysis")
        else:
            corr_filtered = corr_df_all[(corr_df_all['date'] >= filter_start) & (corr_df_all['date'] < filter_end)].copy().sort_values('date')
            smoothing = st.selectbox("Smoothing for combined chart", options=["Daily (Raw)", "7-Day", "30-Day", "90-Day"], index=2)
            window_map = {"Daily (Raw)": 1, "7-Day": 7, "30-Day": 30, "90-Day": 90}
            w = window_map.get(smoothing, 30)

            plot_df = corr_filtered.copy()
            if w > 1:
                plot_df['fiscal_policy_index_smooth'] = plot_df['fiscal_policy_index'].rolling(w, min_periods=1).mean()
                plot_df['tariff_fiscal_index_smooth'] = plot_df['tariff_fiscal_index'].rolling(w, min_periods=1).mean()
                plot_df['non_tariff_fiscal_index_smooth'] = plot_df['non_tariff_fiscal_index'].rolling(w, min_periods=1).mean()
                plot_df['avg_btc_smooth'] = plot_df['avg_btc'].rolling(w, min_periods=1).mean()
                fiscal_col = 'fiscal_policy_index_smooth'
                tariff_col = 'tariff_fiscal_index_smooth'
                non_tariff_col = 'non_tariff_fiscal_index_smooth'
                btc_col = 'avg_btc_smooth'
            else:
                fiscal_col = 'fiscal_policy_index'
                tariff_col = 'tariff_fiscal_index'
                non_tariff_col = 'non_tariff_fiscal_index'
                btc_col = 'avg_btc'

            fig = go.Figure()
            fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df[fiscal_col], mode='lines', name='Fiscal Policy Index', yaxis='y'))
            fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df[tariff_col], mode='lines', name='Tariff Index', yaxis='y'))
            fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df[non_tariff_col], mode='lines', name='Non-Tariff Index', yaxis='y'))
            fig.add_trace(go.Scatter(x=plot_df['date'], y=plot_df[btc_col], mode='lines', name='Avg Bid-to-Cover', yaxis='y2'))

            fig.update_layout(
                title=f"Fiscal Policy Indices vs Avg Bid-to-Cover ({smoothing})",
                xaxis=dict(title='Date'),
                yaxis=dict(title='Policy Index'),
                yaxis2=dict(title='Avg Bid-to-Cover Ratio', overlaying='y', side='right'),
                hovermode='x unified'
            )
            st.plotly_chart(fig, use_container_width=True)

            # Correlation metrics
            st.subheader("Correlation metrics")
            try:
                corr_fiscal_btc = plot_df[[fiscal_col, btc_col]].dropna().corr().iloc[0, 1]
            except:
                corr_fiscal_btc = float('nan')
            try:
                corr_tariff_btc = plot_df[[tariff_col, btc_col]].dropna().corr().iloc[0, 1]
            except:
                corr_tariff_btc = float('nan')
            try:
                corr_non_tariff_btc = plot_df[[non_tariff_col, btc_col]].dropna().corr().iloc[0, 1]
            except:
                corr_non_tariff_btc = float('nan')

            c1, c2, c3 = st.columns(3)
            c1.metric("Fiscal Index ↔ BTC", f"{corr_fiscal_btc:.3f}" if pd.notna(corr_fiscal_btc) else "N/A")
            c2.metric("Tariff Index ↔ BTC", f"{corr_tariff_btc:.3f}" if pd.notna(corr_tariff_btc) else "N/A")
            c3.metric("Non-Tariff Index ↔ BTC", f"{corr_non_tariff_btc:.3f}" if pd.notna(corr_non_tariff_btc) else "N/A")


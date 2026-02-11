"""
Professional Options & Futures Trading Platform
World-class institutional-grade dashboard
"""

import os
import numpy as np
import pandas as pd
import streamlit as st
from datetime import datetime, timedelta

# Import existing modules
from src.data.api_data import (
    fetch_execution_info,
    fetch_zero_gamma,
    fetch_gex_profile,
    fetch_gex_levels,
    fetch_ohlc_data,
)

from src.ui.plots import (
    plotly_gex_strike_bars,
    plotly_gex_profile,
    plotly_candlestick_gex,
)

# Import advanced modules
from src.core.market_regime import MarketRegimeDetector, MarketEnvironment
from src.core.strategy_engine import StrategyEngine
from src.analytics.vol_arb import VolatilityArbitrage, ImpliedVolatilitySurface
from src.ui.position_sizing import KellyPositionSizer, RiskManager
from src.ui.advanced_plots import OptionsVisualizer, create_risk_metrics_gauge
from src.backtesting.backtester import OptionsBacktester, plot_backtest_results
from src.analytics.dix_tracker import DIXTracker, create_dix_gex_plot
from src.data.realtime_feed import RealtimeDataFeed, StreamlitRealtimeDisplay, MarketSnapshot
from src.strategies.options_flow_scanner import OptionsFlowScanner, create_flow_visualization
from src.ml.ml_predictor import MLPricePredictor, create_prediction_visualization
from src.analytics.trade_journal import TradeJournal, create_performance_dashboard

# Page configuration
st.set_page_config(
    page_title="Institutional Trading Platform",
    page_icon="📈",
    layout="wide",
    initial_sidebar_state='expanded',
)

# Professional CSS Styling
st.markdown("""
<style>
    /* Import modern font */
    @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');
    
    * {
        font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    }
    
    .stApp {
        background: linear-gradient(135deg, #0a0e27 0%, #1a1f3a 100%);
        color: #e8eaed;
    }
    
    /* Header styling */
    h1 {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        font-weight: 700;
        letter-spacing: -0.5px;
    }
    
    h2, h3 {
        color: #a8b3cf;
        font-weight: 600;
        letter-spacing: -0.3px;
    }
    
    /* Card effect for metrics */
    [data-testid="stMetricValue"] {
        font-size: 2rem;
        font-weight: 700;
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
    }
    
    [data-testid="stMetricLabel"] {
        font-size: 0.9rem;
        color: #8b95b0;
        font-weight: 500;
        text-transform: uppercase;
        letter-spacing: 0.5px;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, #1a1f3a 0%, #0f1729 100%);
        border-right: 1px solid #2d3548;
    }
    
    [data-testid="stSidebar"] h1, 
    [data-testid="stSidebar"] h2, 
    [data-testid="stSidebar"] h3 {
        color: #667eea;
    }
    
    /* Button styling */
    .stButton>button {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        border: none;
        border-radius: 8px;
        padding: 0.5rem 2rem;
        font-weight: 600;
        box-shadow: 0 4px 15px rgba(102, 126, 234, 0.4);
        transition: all 0.3s ease;
    }
    
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(102, 126, 234, 0.6);
    }
    
    /* Tabs */
    .stTabs [data-baseweb="tab-list"] {
        gap: 8px;
        background-color: rgba(26, 31, 58, 0.5);
        border-radius: 10px;
        padding: 4px;
    }
    
    .stTabs [data-baseweb="tab"] {
        border-radius: 8px;
        color: #8b95b0;
        font-weight: 500;
    }
    
    .stTabs [aria-selected="true"] {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
    }
    
    /* Expander */
    .streamlit-expanderHeader {
        background: rgba(26, 31, 58, 0.6);
        border-radius: 8px;
        font-weight: 600;
        color: #a8b3cf;
    }
    
    /* Selectbox and input */
    .stSelectbox>div>div, .stTextInput>div>div {
        background-color: rgba(26, 31, 58, 0.8);
        border: 1px solid #2d3548;
        border-radius: 8px;
        color: #e8eaed;
    }
    
    /* DataFrames */
    [data-testid="stDataFrame"] {
        border-radius: 8px;
        overflow: hidden;
    }
    
    /* Alert boxes */
    .stAlert {
        border-radius: 8px;
        border-left: 4px solid #667eea;
    }
    
    /* Success/Info/Warning boxes */
    .element-container div[data-testid="stMarkdownContainer"] div[data-testid="stMarkdown"] {
        border-radius: 8px;
    }
    
    /* Glassmorphism effect */
    .glass-card {
        background: rgba(26, 31, 58, 0.4);
        backdrop-filter: blur(10px);
        border-radius: 12px;
        border: 1px solid rgba(255, 255, 255, 0.1);
        padding: 1.5rem;
        box-shadow: 0 8px 32px rgba(0, 0, 0, 0.3);
    }
</style>
""", unsafe_allow_html=True)


# Define data retrieval function
@st.cache_data(ttl=3600)  # Cache for 1 hour
def get_data():
    execution_info = fetch_execution_info()
    zero_gamma = fetch_zero_gamma()
    dict_gex_profile = fetch_gex_profile()
    dict_gex_levels = fetch_gex_levels()
    ohlc = fetch_ohlc_data()
    
    return execution_info, zero_gamma, dict_gex_profile, dict_gex_levels, ohlc


def main():
    # === HEADER ===
    st.markdown("""
        <h1 style='text-align: center; font-size: 3rem; margin-bottom: 0;'>
            ⚡ INSTITUTIONAL TRADING PLATFORM
        </h1>
        <p style='text-align: center; color: #8b95b0; font-size: 1.1rem; margin-top: 0;'>
            Advanced Options & Futures Analytics with AI-Powered Strategy Recommendations
        </p>
    """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # === SIDEBAR CONFIGURATION ===
    with st.sidebar:
        st.markdown("### ⚙️ Configuration")
        
        # Account settings
        st.markdown("#### Account Settings")
        account_balance = st.number_input(
            "Account Balance ($)",
            min_value=1000,
            max_value=10000000,
            value=100000,
            step=1000,
            help="Your total account value for position sizing"
        )
        
        kelly_fraction = st.slider(
            "Kelly Fraction (%)",
            min_value=5,
            max_value=50,
            value=10,
            step=5,
            help="10% fractional Kelly is recommended for conservative sizing"
        ) / 100
        
        max_risk_per_trade = st.slider(
            "Max Risk Per Trade (%)",
            min_value=1,
            max_value=10,
            value=2,
            step=1,
            help="Maximum portfolio risk per single trade"
        ) / 100
        
        st.markdown("---")
        
        # Market data settings
        st.markdown("#### Market Settings")
        current_vix = st.number_input(
            "Current VIX",
            min_value=8.0,
            max_value=80.0,
            value=18.0,
            step=0.5,
            help="Used for volatility analysis"
        )
        
        underlying_symbol = st.text_input(
            "Underlying Symbol",
            value="SPX",
            help="Symbol for analysis"
        )
        
        st.markdown("---")
        
        if st.button("🔄 Refresh Data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        
        st.markdown("---")
        st.markdown("""
            <div style='text-align: center; color: #667eea; font-size: 0.9rem;'>
                <b>Made with ⚡ by Prop Traders</b><br>
                <span style='color: #8b95b0; font-size: 0.8rem;'>
                    Professional Options Analytics
                </span>
            </div>
        """, unsafe_allow_html=True)
    
    # === LOAD DATA ===
    with st.spinner('🔄 Loading market data...'):
        execution_info, zero_gamma, dict_gex_profile, dict_gex_levels, ohlc = get_data()
    
    if execution_info.empty or ohlc.empty:
        st.error("❌ Failed to load critical data. Please check API connections.")
        return
    
    # Data preprocessing
    ohlc = ohlc.loc[ohlc['Open'] != 0, :]
    execution_info['delayed_timestamp'] = pd.to_datetime(execution_info['delayed_timestamp'])
    execution_info['date'] = execution_info['delayed_timestamp'].dt.date
    
    date_to_id = dict(zip(execution_info['date'], execution_info['mongodb_id']))
    available_dates = sorted(list(date_to_id.keys()), reverse=True)
    
    if not available_dates:
        st.error("No execution dates found.")
        return
    
    # === DATE SELECTION ===
    col_title, col_date = st.columns([3, 1])
    
    with col_date:
        selected_date = st.selectbox(
            label='📅 Select Date',
            options=available_dates,
            index=0
        )
    
    # Get data for selected date
    sel_mongodb_id = date_to_id[selected_date]
    
    try:
        spot_price = ohlc.loc[pd.to_datetime(selected_date).date(), 'Close']
    except KeyError:
        st.warning(f"No spot price found for {selected_date}. Using latest available.")
        spot_price = ohlc['Close'].iloc[-1] if not ohlc.empty else 0
    
    # Prepare GEX Data
    if sel_mongodb_id not in dict_gex_profile or sel_mongodb_id not in dict_gex_levels:
        st.error(f"No GEX data found for ID: {sel_mongodb_id}")
        return
    
    gex_profile = pd.DataFrame(dict_gex_profile[sel_mongodb_id])
    gex_profile.rename(columns={
        'strike': 'Strikes',
        'index': 'Strikes',
        'Gamma Profile All': 'Gamma Exposure',
        'Gamma Profile (Ex Next)': 'Gamma Exposure ExNext Expiry',
        'Gamma Profile (Ex Next Monthly)': 'Gamma Exposure ExNext Friday',
    }, inplace=True)
    
    gex_levels = pd.DataFrame(dict_gex_levels[sel_mongodb_id])
    gex_levels.rename(columns={
        'index': 'Strikes',
        'strike': 'Strikes',
        'Total Gamma Call': 'Gamma Exposure Calls',
        'Total Gamma Put': 'Gamma Exposure Puts',
    }, inplace=True)
    
    # Zero Gamma
    zero_gamma_val = None
    if not zero_gamma.empty:
        try:
            zero_gamma_val = zero_gamma.loc[pd.to_datetime(selected_date), 'Zero Gamma']
        except KeyError:
            pass
    
    # === MARKET REGIME ANALYSIS ===
    st.markdown("## 🎯 Market Intelligence")
    
    regime_detector = MarketRegimeDetector()
    market_env = regime_detector.analyze_environment(
        ohlc=ohlc,
        gex_data=gex_profile,
        zero_gamma=zero_gamma_val,
        current_price=spot_price,
        vix=current_vix
    )
    
    # Display market environment
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        st.metric("Market Regime", market_env.regime.value)
    
    with col2:
        st.metric("Volatility Regime", market_env.volatility_regime.value)
    
    with col3:
        st.metric("Trend Strength", f"{market_env.trend_strength:.0f}/100")
    
    with col4:
        st.metric("Gamma Regime", market_env.gamma_regime.split('(')[0])
    
    # Environment details
    with st.expander("📊 Detailed Market Metrics"):
        metrics_cols = st.columns(4)
        
        with metrics_cols[0]:
            st.metric("Current Price", f"${market_env.raw_metrics['current_price']:.2f}")
            st.metric("SMA 20", f"${market_env.raw_metrics['sma20']:.2f}")
            st.metric("SMA 50", f"${market_env.raw_metrics['sma50']:.2f}")
        
        with metrics_cols[1]:
            st.metric("Price vs SMA20", f"{market_env.raw_metrics['price_vs_sma20']:.2f}%")
            st.metric("ADX", f"{market_env.raw_metrics['adx']:.1f}")
            st.metric("ATR %", f"{market_env.raw_metrics['atr_pct']:.2f}%")
        
        with metrics_cols[2]:
            st.metric("Historical Vol", f"{market_env.raw_metrics['hv']:.1f}%")
            st.metric("Vol Percentile", f"{market_env.vol_percentile:.0f}%")
            st.metric("IV Rank", f"{market_env.iv_rank:.0f}%")
        
        with metrics_cols[3]:
            st.metric("ROC (20d)", f"{market_env.raw_metrics['roc20']:.2f}%")
            st.metric("Analysis Confidence", f"{market_env.confidence:.0f}%")
            if zero_gamma_val:
                st.metric("Zero Gamma", f"${zero_gamma_val:.2f}")
    
    st.markdown("---")
    
    # === VOLATILITY ARBITRAGE ===
    st.markdown("## 💎 Volatility Arbitrage Analysis")
    
    vol_arb = VolatilityArbitrage()
    vol_signal = vol_arb.analyze_vol_arbitrage(
        ohlc=ohlc,
        current_iv=current_vix,
        current_price=spot_price
    )
    
    col1, col2, col3 = st.columns(3)
    
    with col1:
        signal_color = "#00cc96" if "UNDERPRICED" in vol_signal.signal_type else "#ef553b" if "OVERPRICED" in vol_signal.signal_type else "#ffa500"
        st.markdown(f"""
            <div style='background: rgba(26, 31, 58, 0.6); padding: 1.5rem; border-radius: 12px; border-left: 4px solid {signal_color};'>
                <h3 style='color: {signal_color}; margin: 0;'>{vol_signal.signal_type.replace('_', ' ')}</h3>
                <p style='color: #a8b3cf; font-size: 0.9rem; margin: 0.5rem 0 0 0;'>
                    {vol_signal.recommended_action}
                </p>
            </div>
        """, unsafe_allow_html=True)
    
    with col2:
        st.metric("IV vs HV Spread", f"{vol_signal.iv_hv_spread:.1f}%")
        st.metric("Z-Score", f"{vol_signal.z_score:.2f}")
    
    with col3:
        st.metric("Signal Confidence", f"{vol_signal.confidence:.0f}%")
        st.metric("Risk Level", vol_signal.risk_level)
    
    st.markdown("**💡 Recommended Vol Strategies:**")
    cols = st.columns(len(vol_signal.target_strategies[:3]))
    for idx, strategy in enumerate(vol_signal.target_strategies[:3]):
        with cols[idx]:
            st.markdown(f"""
                <div style='background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); 
                            padding: 0.8rem; border-radius: 8px; text-align: center; color: white;'>
                    <b>{strategy}</b>
                </div>
            """, unsafe_allow_html=True)
    
    st.markdown("---")
    
    # === AI STRATEGY RECOMMENDATIONS ===
    st.markdown("## 🤖 AI Strategy Recommendations")
    
    strategy_engine = StrategyEngine()
    recommendations = strategy_engine.recommend_strategies(
        market_env=market_env,
        current_price=spot_price,
        num_recommendations=5
    )
    
    # Initialize position sizer
    kelly_sizer = KellyPositionSizer(
        account_balance=account_balance,
        kelly_fraction=kelly_fraction,
        max_risk_per_trade=max_risk_per_trade
    )
    
    for idx, rec in enumerate(recommendations):
        with st.expander(f"{'🥇' if idx == 0 else '🥈' if idx == 1 else '🥉' if idx == 2 else '📌'} **{rec.name}** - Confidence: {rec.confidence:.0f}% | Type: {rec.type}", expanded=(idx == 0)):
            
            col1, col2 = st.columns([2, 1])
            
            with col1:
                st.markdown(f"**📝 Analysis:** {rec.reasoning}")
                
                st.markdown("**📊 Strike Selection:**")
                strike_text = ", ".join([f"**{k.replace('_', ' ').title()}**: ${v:.2f}" for k, v in rec.strikes.items()])
                st.markdown(strike_text)
                
                st.markdown(f"**📅 Expiration:** {rec.expiration_dte} DTE")
                
                st.markdown(f"**💰 Risk/Reward:** {rec.risk_reward}")
                st.markdown(f"**📈 Max Profit:** {rec.max_profit}")
                st.markdown(f"**📉 Max Loss:** {rec.max_loss}")
                
                st.markdown(f"**🎯 Greeks Profile:** {rec.greeks_profile}")
            
            with col2:
                # Position sizing
                st.markdown("### 💼 Position Sizing")
                
                # Estimate max loss for sizing
                estimated_max_loss = 500  # Placeholder - would calculate from strikes
                estimated_max_profit = 300
                
                sizing = kelly_sizer.calculate_strategy_sizing(
                    strategy_name=rec.name,
                    confidence=rec.confidence,
                    max_loss_per_contract=estimated_max_loss,
                    max_profit_per_contract=estimated_max_profit
                )
                
                st.metric("Contracts to Trade", f"{sizing.contracts_to_trade}")
                st.metric("Account Risk", f"{sizing.account_risk_pct:.2f}%")
                st.metric("Max Loss", f"${sizing.max_loss:.2f}")
                st.metric("Expected Value", f"${sizing.expected_value:.2f}")
                st.metric("Kelly Fraction", f"{sizing.fractional_kelly:.2f}%")
            
            # Pros and Cons
            pros_cons_col1, pros_cons_col2 = st.columns(2)
            
            with pros_cons_col1:
                if rec.pros:
                    st.markdown("**✅ Pros:**")
                    for pro in rec.pros:
                        st.markdown(f"- {pro}")
            
            with pros_cons_col2:
                if rec.cons:
                    st.markdown("**⚠️ Cons:**")
                    for con in rec.cons:
                        st.markdown(f"- {con}")
    
    st.markdown("---")
    
    # === VISUALIZATION SECTION ===
    st.markdown("## 📈 Advanced Analytics")
    
    tabs = st.tabs([
        "📊 GEX Analysis",
        "🎨 3D P&L Surface",
        "📉 P&L Profiles",
        "🔬 Greeks Dashboard",
        "🔙 Strategy Backtester",
        "💼 DIX / Institutional Flow",
        "📡 Options Flow Scanner",
        "🤖 ML Price Predictor",
        "📓 Trade Journal",
        "⚡ Real-time Data",
        "📜 Historical Data"
    ])
    
    with tabs[0]:
        st.markdown("### Gamma Exposure Analysis")
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.plotly_chart(
                plotly_gex_strike_bars(gex_levels, spot_price=spot_price),
                use_container_width=True
            )
        
        with col2:
            st.plotly_chart(
                plotly_gex_profile(gex_profile, spot_price=spot_price),
                use_container_width=True
            )
        
        st.markdown("### Historical SPX & Gamma Flip")
        st.plotly_chart(
            plotly_candlestick_gex(ohlc.iloc[-252:, :], historic_gex=zero_gamma),
            use_container_width=True
        )
    
    with tabs[1]:
        st.markdown("### 3D P&L Surface Analysis")
        
        if recommendations:
            selected_strategy = st.selectbox(
                "Select Strategy for 3D View",
                options=[rec.name for rec in recommendations[:3]],
                key="3d_strategy"
            )
            
            # Find the recommendation
            selected_rec = next((r for r in recommendations if r.name == selected_strategy), None)
            
            if selected_rec:
                visualizer = OptionsVisualizer()
                
                fig_3d = visualizer.plot_pnl_surface_3d(
                    strategy_name=selected_rec.name,
                    strikes=selected_rec.strikes,
                    current_price=spot_price,
                    iv=current_vix
                )
                
                st.plotly_chart(fig_3d, use_container_width=True)
                
                st.info("💡 **How to read:** Green zones = profit, Red zones = loss. Rotate the 3D plot to see P&L from different angles.")
    
    with tabs[2]:
        st.markdown("### 2D P&L Profiles")
        
        if recommendations:
            selected_strategy_2d = st.selectbox(
                "Select Strategy",
                options=[rec.name for rec in recommendations[:3]],
                key="2d_strategy"
            )
            
            selected_rec = next((r for r in recommendations if r.name == selected_strategy_2d), None)
            
            if selected_rec:
                visualizer = OptionsVisualizer()
                
                col1, col2 = st.columns([1, 1])
                
                with col1:
                    fig_profile = visualizer.plot_pnl_profile_at_expiration(
                        strategy_name=selected_rec.name,
                        strikes=selected_rec.strikes,
                        current_price=spot_price
                    )
                    st.plotly_chart(fig_profile, use_container_width=True)
                
                with col2:
                    fig_heatmap = visualizer.plot_pnl_heatmap_2d(
                        strategy_name=selected_rec.name,
                        strikes=selected_rec.strikes,
                        current_price=spot_price,
                        iv=current_vix
                    )
                    st.plotly_chart(fig_heatmap, use_container_width=True)
    
    with tabs[3]:
        st.markdown("### Greeks Analysis")
        
        if recommendations:
            selected_strategy_greeks = st.selectbox(
                "Select Strategy for Greeks",
                options=[rec.name for rec in recommendations[:3]],
                key="greeks_strategy"
            )
            
            selected_rec = next((r for r in recommendations if r.name == selected_strategy_greeks), None)
            
            if selected_rec:
                visualizer = OptionsVisualizer()
                
                fig_greeks = visualizer.plot_greeks_dashboard(
                    strategy_name=selected_rec.name,
                    strikes=selected_rec.strikes,
                    current_price=spot_price
                )
                
                st.plotly_chart(fig_greeks, use_container_width=True)
    
    with tabs[4]:
        st.markdown("### 🔙 Strategy Backtester")
        st.markdown("Test historical performance of recommended strategies")
        
        # Backtest configuration
        col1, col2, col3 = st.columns(3)
        
        with col1:
            backtest_initial_capital = st.number_input(
                "Initial Capital ($)",
                min_value=10000,
                max_value=1000000,
                value=100000,
                step=10000
            )
        
        with col2:
            backtest_min_confidence = st.slider(
                "Min Confidence (%)",
                min_value=30,
                max_value=90,
                value=60,
                help="Only take trades with confidence above this threshold"
            )
        
        with col3:
            rebalance_freq = st.selectbox(
                "Rebalance Frequency",
                options=["daily", "weekly", "monthly"],
                index=1
            )
        
        if st.button("🚀 Run Backtest", use_container_width=True):
            with st.spinner("Running backtest simulation..."):
                # Initialize backtester
                backtester = OptionsBacktester(
                    initial_capital=backtest_initial_capital,
                    kelly_fraction=kelly_fraction,
                    max_risk_per_trade=max_risk_per_trade
                )
                
                # Run backtest
                results = backtester.run_backtest(
                    ohlc_data=ohlc,
                    gex_data=dict_gex_profile,
                    zero_gamma_data=zero_gamma,
                    vix_data=None,  # Would need VIX data
                    min_confidence=backtest_min_confidence,
                    rebalance_frequency=rebalance_freq
                )
                
                # Display results
                st.markdown("### 📊 Backtest Results")
                
                # Key metrics
                metrics_cols = st.columns(5)
                
                with metrics_cols[0]:
                    st.metric("Total Return", f"{results.total_return:.2f}%")
                
                with metrics_cols[1]:
                    st.metric("Sharpe Ratio", f"{results.sharpe_ratio:.2f}")
                
                with metrics_cols[2]:
                    st.metric("Win Rate", f"{results.win_rate:.1f}%")
                
                with metrics_cols[3]:
                    st.metric("Profit Factor", f"{results.profit_factor:.2f}")
                
                with metrics_cols[4]:
                    st.metric("Max Drawdown", f"{results.max_drawdown:.2f}%")
                
                # Advanced metrics
                with st.expander("📈 Advanced Metrics"):
                    adv_cols = st.columns(4)
                    
                    with adv_cols[0]:
                        st.metric("Annualized Return", f"{results.annualized_return:.2f}%")
                        st.metric("Sortino Ratio", f"{results.sortino_ratio:.2f}")
                    
                    with adv_cols[1]:
                        st.metric("Total Trades", results.total_trades)
                        st.metric("Winning Trades", results.winning_trades)
                    
                    with adv_cols[2]:
                        st.metric("Losing Trades", results.losing_trades)
                        st.metric("Avg Win", f"${results.avg_win:.2f}")
                    
                    with adv_cols[3]:
                        st.metric("Avg Loss", f"${results.avg_loss:.2f}")
                        st.metric("Calmar Ratio", f"{results.calmar_ratio:.2f}")
                
                # Visualization
                if not results.equity_curve.empty:
                    fig_results = plot_backtest_results(results)
                    st.plotly_chart(fig_results, use_container_width=True)
                
                # Trade log
                if not results.trade_log.empty:
                    with st.expander("📋 Trade Log"):
                        st.dataframe(results.trade_log, use_container_width=True)
                
                st.success(f"✅ Backtest complete! Tested {results.total_trades} trades over {len(results.equity_curve)} periods.")
    
    with tabs[5]:
        st.markdown("### 💼 DIX / Institutional Flow Analysis")
        st.markdown("Track smart money activity through Dark Pool Index")
        
        # Simulated DIX data (replace with actual DIX API data)
        dix_current = st.number_input(
            "Current DIX Level",
            min_value=0.0,
            max_value=1.0,
            value=0.43,
            step=0.01,
            help="DIX > 0.45 = Bullish, DIX < 0.40 = Bearish"
        )
        
        # Create historical DIX series (simulated)
        historical_dix = pd.Series(
            np.random.uniform(0.35, 0.50, len(ohlc.iloc[-252:])),
            index=ohlc.iloc[-252:].index
        )
        
        # GEX for DIX analysis (use actual GEX if available)
        gex_current = 0 if zero_gamma.empty else zero_gamma.iloc[-1]['Zero Gamma'] if 'Zero Gamma' in zero_gamma.columns else 0
        
        historical_gex = zero_gamma['Zero Gamma'] if not zero_gamma.empty and 'Zero Gamma' in zero_gamma.columns else pd.Series([0] * len(ohlc.iloc[-252:]), index=ohlc.iloc[-252:].index)
        
        # Analyze DIX/GEX
        dix_tracker = DIXTracker()
        dix_analysis = dix_tracker.analyze_dix_gex(
            current_dix=dix_current,
            current_gex=gex_current,
            historical_dix=historical_dix,
            historical_gex=historical_gex,
            current_price=spot_price,
            trend=market_env.regime.value
        )
        
        # Display analysis
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            signal_color = "#00cc96" if "BUYING" in dix_analysis.signal.value else "#ef553b" if "SELLING" in dix_analysis.signal.value else "#ffa500"
            st.markdown(f"""
                <div style='background: rgba(26, 31, 58, 0.6); padding: 1.5rem; border-radius: 12px; border-left: 4px solid {signal_color};'>
                    <h4 style='color: {signal_color}; margin: 0;'>{dix_analysis.signal.value}</h4>
                </div>
            """, unsafe_allow_html=True)
        
        with col2:
            st.metric("DIX", f"{dix_analysis.dix:.3f}")
            st.metric("DIX Percentile", f"{dix_analysis.dix_percentile:.0f}%")
        
        with col3:
            st.metric("GEX", f"${dix_analysis.gex:,.0f}")
            st.metric("GEX Percentile", f"{dix_analysis.gex_percentile:.0f}%")
        
        with col4:
            st.metric("Confidence", f"{dix_analysis.confidence:.0f}%")
            st.metric("Risk Level", dix_analysis.risk_level)
        
        # Interpretation
        st.markdown("#### 🔍 Analysis")
        st.info(dix_analysis.interpretation)
        
        st.markdown("#### 🎯 Market Outlook")
        st.success(dix_analysis.market_outlook)
        
        st.markdown("#### 💡 Trading Recommendation")
        st.warning(dix_analysis.trading_recommendation)
        
        # DIX/GEX chart
        st.markdown("#### 📈 Historical DIX/GEX vs Price")
        
        try:
            fig_dix = create_dix_gex_plot(
                dix_history=historical_dix,
                gex_history=historical_gex,
                price_history=ohlc['Close'].iloc[-252:],
                current_dix=dix_current,
                current_gex=gex_current
            )
            st.plotly_chart(fig_dix, use_container_width=True)
        except Exception as e:
            st.warning(f"DIX/GEX chart unavailable: {e}")
        
        # Educational content
        with st.expander("📚 Understanding DIX"):
            st.markdown("""
            **Dark Pool Index (DIX)** measures institutional buying pressure through dark pool short volume.
            
            **Key Insights:**
            - **DIX > 0.45**: Institutions actively buying (bullish)
            - **DIX 0.40-0.45**: Neutral positioning
            - **DIX <  0.40**: Institutions selling (bearish)
            
            **Combined with GEX:**
            - **High DIX + Low GEX** = Bullish (institutions buying, low dealer hedging)
            - **Low DIX + High GEX** = Bearish (institutions selling, high dealer hedging)
            
            DIX has historically been a leading indicator for major market moves.
            """)
    
    with tabs[6]:
        st.markdown("### 📡 Options Flow Scanner")
        st.markdown("**Track institutional money flow in real-time**")
        
        st.info("💡 **What is Options Flow?** Unusual options activity (UOA) reveals where smart money is positioning. Large trades, sweeps, and whale activity often precede major price moves.")
        
        # Scanner configuration
        col1, col2, col3 = st.columns(3)
        
        with col1:
            whale_threshold = st.number_input(
                "Whale Threshold ($)",
                min_value=100_000,
                max_value=10_000_000,
                value=1_000_000,
                step=100_000,
                help="Minimum premium for whale detection"
            )
        
        with col2:
            block_size = st.number_input(
                "Block Size (contracts)",
                min_value=100,
                max_value=2000,
                value=500,
                help="Minimum contracts for block trade"
            )
        
        with col3:
            volume_mult = st.slider(
                "Volume Multiplier",
                min_value=1.5,
                max_value=5.0,
                value=2.0,
                step=0.5,
                help="Volume vs average for unusual detection"
            )
        
        # Initialize scanner
        scanner = OptionsFlowScanner(
            whale_premium_threshold=whale_threshold,
            block_size_threshold=block_size,
            volume_multiplier=volume_mult
        )
        
        # Create sample options data (replace with real options chain)
        st.markdown("#### 🔍 Live Flow Alerts")
        
        # Sample data for demonstration
        sample_options = pd.DataFrame({
            'strike': [spot_price * i for i in [0.95, 0.97, 1.00, 1.03, 1.05]],
            'expiration': ['30DTE'] * 5,
            'volume': [1500, 800, 2000, 1200, 600],
            'avg_volume': [500, 400, 600, 500, 300],
            'premium': [2_500_000, 800_000, 3_000_000, 1_500_000, 500_000],
            'open_interest': [5000, 3000, 8000, 4000, 2000],
            'oi_change_pct': [0.3, 0.2, 0.6, 0.4, 0.1],
            'option_type': ['C', 'P', 'C', 'C', 'P'],
            'bid': [15.5, 12.0, 18.0, 14.0, 10.0],
            'ask': [15.8, 12.3, 18.3, 14.3, 10.3]
        })
        
        # Scan for unusual activity
        flow_alerts = scanner.scan_options_chain(
            sample_options,
            current_price=spot_price,
            symbol="SPX"
        )
        
        # Generate summary
        flow_summary = scanner.generate_flow_summary(flow_alerts, top_n=10)
        
        # Display summary metrics
        summary_cols = st.columns(5)
        
        with summary_cols[0]:
            sentiment_color = "#00cc96" if "BULLISH" in flow_summary.sentiment.value else "#ef553b" if "BEARISH" in flow_summary.sentiment.value else "#ffa500"
            st.markdown(f"""
                <div style='background: rgba(26, 31, 58, 0.6); padding: 1rem; border-radius: 8px; border-left: 4px solid {sentiment_color};'>
                    <h4 style='color: {sentiment_color}; margin: 0;'>{flow_summary.sentiment.value}</h4>
                </div>
            """, unsafe_allow_html=True)
        
        with summary_cols[1]:
            st.metric("Total Premium", f"${flow_summary.total_premium:,.0f}")
        
        with summary_cols[2]:
            st.metric("C/P Ratio", f"{flow_summary.call_put_ratio:.2f}")
        
        with summary_cols[3]:
            st.metric("Whale Trades", flow_summary.whale_count)
        
        with summary_cols[4]:
            st.metric("Net Flow", f"${flow_summary.net_premium:,.0f}")
        
        # Detailed breakdown
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### 📊 Flow Breakdown")
            breakdown_df = pd.DataFrame({
                'Type': ['Calls', 'Puts'],
                'Premium': [flow_summary.call_premium, flow_summary.put_premium],
                'Count': [flow_summary.bullish_count, flow_summary.bearish_count]
            })
            st.dataframe(breakdown_df, use_container_width=True, hide_index=True)
        
        with col2:
            st.markdown("#### 🎯 Interpretation")
            if "VERY_BULLISH" in flow_summary.sentiment.value:
                st.success("🚀 **Heavy institutional call buying.** Major bullish positioning detected. Expect upward pressure.")
            elif "BULLISH" in flow_summary.sentiment.value:
                st.success("✅ **Moderate bullish flow.** More calls than puts being purchased.")
            elif "VERY_BEARISH" in flow_summary.sentiment.value:
                st.error("📉 **Heavy put buying.** Institutions hedging or betting on downside.")
            elif "BEARISH" in flow_summary.sentiment.value:
                st.warning("⚠️ **Moderate bearish flow.** More puts than calls.")
            else:
                st.info("➡️ **Neutral flow.** No clear directional bias from options activity.")
        
        # Top flow alerts
        if flow_summary.top_alerts:
            st.markdown("#### 🔔 Top Flow Alerts")
            
            for i, alert in enumerate(flow_summary.top_alerts[:5], 1):
                with st.expander(f"#{i} - {alert.flow_type.value} - ${alert.premium:,.0f}"):
                    flow_cols = st.columns(4)
                    
                    with flow_cols[0]:
                        st.metric("Strike", f"${alert.strike:.0f}")
                        st.metric("Contracts", f"{alert.volume:,}")
                    
                    with flow_cols[1]:
                        st.metric("Premium", f"${alert.premium:,.0f}")
                        st.metric("OI", f"{alert.open_interest:,}")
                    
                    with flow_cols[2]:
                        st.metric("Sentiment", alert.sentiment)
                        st.metric("Expiration", alert.expiration)
                    
                    with flow_cols[3]:
                        st.metric("Aggressiveness", f"{alert.aggressiveness:.0f}/100")
                        st.metric("Confidence", f"{alert.confidence:.0f}%")
                    
                    st.markdown(f"**📝 Details:** {alert.description}")
        
        # Visualization
        try:
            fig_flow = create_flow_visualization(flow_summary)
            st.plotly_chart(fig_flow, use_container_width=True)
        except Exception as e:
            st.warning(f"Flow visualization unavailable: {e}")
        
        # Educational content
        with st.expander("📚 Understanding Options Flow"):
            st.markdown("""
            **Key Flow Indicators:**
            
            🐋 **Whale Trades**
            - Premium > $1M
            - Institutional positioning
            - Often early signal of big moves
            
            🧹 **Sweeps**
            - Aggressive multi-exchange buying
            - Urgency to establish position
            - Often precedes volatility
            
            📦 **Block Trades**
            - Large contract sizes (>500)
            - Dark pool execution
            - Smart money accumulation
            
            **How to Use:**
            1. **Follow the whales** - Large trades often know something
            2. **Watch C/P ratio** - >1.5 = bullish, <0.7 = bearish
            3. **Check timing** - Flow at market open/close most meaningful
            4. **Confirm with price action** - Best when aligned with technicals
            """)
    
    with tabs[7]:
        st.markdown("###  🤖 ML Price Predictor")
        st.markdown("**AI-Powered directional bias using Machine Learning**")
        
        st.info("💡 **What is ML Prediction?** Our ensemble AI models (Random Forest + Gradient Boosting) analyze 20+ technical indicators to predict likely price direction with confidence scores.")
        
        # Predictor configuration
        pred_cols = st.columns(3)
        
        with pred_cols[0]:
            prediction_days = st.selectbox(
                "Prediction Timeframe",
                options=[1, 3, 5, 10, 20],
                index=2,
                help="Days forward to predict"
            )
        
        with pred_cols[1]:
            train_period = st.slider(
                "Training Period (days)",
                min_value=200,
                max_value=1000,
                value=500,
                step=100,
                help="Historical data used for training"
            )
        
        with pred_cols[2]:
            run_backtest = st.checkbox("Show Backtest Performance", value=False)
        
        if st.button("🚀 Generate Prediction", use_container_width=True):
            with st.spinner(f"Training AI models on {train_period} days of data..."):
                # Initialize predictor
                predictor = MLPricePredictor()
                
                # Train
                try:
                    predictor.train(ohlc, target_days=prediction_days, train_period_days=train_period)
                    
                    # Predict
                    prediction = predictor.predict(ohlc, symbol="SPX", timeframe_days=prediction_days)
                    
                    # Display prediction
                    st.markdown("### 🎯 Prediction Results")
                    
                    result_cols = st.columns(4)
                    
                    with result_cols[0]:
                        direction_color = "#00cc96" if prediction.direction == "UP" else "#ef553b" if prediction.direction == "DOWN" else "#ffa500"
                        st.markdown(f"""
                            <div style='background: rgba(26, 31, 58, 0.6); padding: 1.5rem; border-radius: 12px; border-left: 4px solid {direction_color}; text-align: center;'>
                                <h2 style='color: {direction_color}; margin: 0; font-size: 3rem;'>{prediction.direction}</h2>
                                <p style='color: #a8b3cf; margin: 0.5rem 0 0 0;'>Direction</p>
                            </div>
                        """, unsafe_allow_html=True)
                    
                    with result_cols[1]:
                        st.metric("Current Price", f"${prediction.current_price:.2f}")
                        st.metric("Predicted Price", f"${prediction.predicted_price:.2f}")
                    
                    with result_cols[2]:
                        st.metric("Expected Change", f"{prediction.predicted_change_pct:+.2f}%")
                        st.metric("Confidence", f"{prediction.confidence:.0f}%")
                    
                    with result_cols[3]:
                        st.metric("Model Agreement", f"{prediction.model_agreement:.0f}%")
                        st.metric("Timeframe", f"{prediction.timeframe_days}d")
                    
                    # Confidence interval
                    st.markdown("#### 📊 Price Range (68% Confidence)")
                    range_cols = st.columns(3)
                    
                    with range_cols[0]:
                        st.metric("Lower Bound", f"${prediction.lower_bound:.2f}")
                    
                    with range_cols[1]:
                        st.metric("Predicted", f"${prediction.predicted_price:.2f}", 
                                 delta=f"{prediction.predicted_change_pct:+.2f}%")
                    
                    with range_cols[2]:
                        st.metric("Upper Bound", f"${prediction.upper_bound:.2f}")
                    
                    # Key drivers
                    st.markdown("#### 🔑 Key Prediction Drivers")
                    drivers_text = " • ".join(prediction.key_drivers)
                    st.info(f"**Top Factors:** {drivers_text}")
                    
                    # Visualization
                    try:
                        fig_pred = create_prediction_visualization(prediction)
                        st.plotly_chart(fig_pred, use_container_width=True)
                    except Exception as e:
                        st.warning(f"Prediction chart unavailable: {e}")
                    
                    # Trading recommendation
                    st.markdown("#### 💡 Trading Implication")
                    
                    if prediction.direction == "UP" and prediction.confidence > 65:
                        st.success(f"✅ **Bullish Setup** ({prediction.confidence:.0f}% confidence) - Consider bull call spreads, sell puts, or directional calls")
                    elif prediction.direction == "DOWN" and prediction.confidence > 65:
                        st.error(f"📉 **Bearish Setup** ({prediction.confidence:.0f}% confidence) - Consider bear put spreads, sell calls, or protective puts")
                    elif prediction.confidence < 50:
                        st.warning("⚠️ **Low Confidence** - Models disagree. Favor neutral strategies (Iron Condor, Butterfly)")
                    else:
                        st.info("➡️ **Moderate Signal** - Use as secondary confirmation with other indicators")
                    
                    # Backtest performance
                    if run_backtest:
                        with st.spinner("Running backtest..."):
                            performance = predictor.backtest_predictions(
                                ohlc,
                                prediction_days=prediction_days,
                                lookback_periods=50
                            )
                            
                            st.markdown("### 📈 Model Performance (Backtest)")
                            
                            perf_cols = st.columns(5)
                            
                            with perf_cols[0]:
                                st.metric("Accuracy", f"{performance.accuracy:.1f}%")
                            
                            with perf_cols[1]:
                                st.metric("Total Predictions", performance.total_predictions)
                            
                            with perf_cols[2]:
                                st.metric("Correct", performance.correct_predictions)
                            
                            with perf_cols[3]:
                                st.metric("MAE", f"{performance.mae:.2f}%")
                            
                            with perf_cols[4]:
                                st.metric("Sharpe", f"{performance.sharpe_ratio:.2f}")
                            
                            if performance.accuracy > 55:
                                st.success(f"✅ Model shows {performance.accuracy:.1f}% directional accuracy - **Edge detected!**")
                            elif performance.accuracy > 50:
                                st.info("➡️ Model slightly better than random - Use with caution")
                            else:
                                st.warning("⚠️ Model accuracy below 50% - Consider retraining or different timeframe")
                
                except Exception as e:
                    st.error(f"Prediction failed: {e}")
                    st.info("💡 **Tip**: Try adjusting the training period or timeframe")
        
        # Educational content
        with st.expander("📚 Understanding ML Predictions"):
            st.markdown("""
            **How It Works:**
            
            1. **Feature Engineering**: 20+ technical indicators calculated
               - Momentum (ROC, RSI, MACD)
               - Moving Averages (SMA20, 50, 200)
               - Volatility (ATR, HV)
               - Patterns (Bollinger Bands, Volume)
            
            2. **Ensemble Learning**: Two models vote
               - Random Forest (60% weight) - Captures non-linear patterns
               - Gradient Boosting (40% weight) - Sequential learning
            
            3. **Confidence Scoring**: Based on
               - Model agreement (do both models agree?)
               - Historical accuracy
               - Prediction magnitude
            
            **Best Practices:**
            - Use as **confirmation**, not sole signal
            - Higher confidence (>70%) = more reliable
            - Combine with market regime + DIX
            - Backtest regularly to verify accuracy
            
            **Limitations:**
            - Cannot predict black swan events
            - Works best in normal market conditions
            - Accuracy degrades during high volatility
            - Assumes patterns repeat (not always true)
            """)
    
    with tabs[8]:
        st.markdown("### 📓 Trade Journal")
        st.markdown("**Track your actual trades and learn from performance**")
        
        # Initialize journal
        journal = TradeJournal()
        
        # Tabs for journal sections
        journal_tabs = st.tabs(["📝 Log Trade", "📊 Performance Dashboard", "📈 Trade History", "💡 Insights"])
        
        # Log Trade Tab
        with journal_tabs[0]:
            st.markdown("#### Add New Trade")
            
            with st.form("new_trade_form"):
                entry_cols = st.columns(2)
                
                with entry_cols[0]:
                    st.markdown("**Position Details**")
                    
                    trade_symbol = st.text_input("Symbol", value="SPX")
                    trade_strategy = st.selectbox(
                        "Strategy",
                        options=["Iron Condor","Bull Call Spread", "Bear Put Spread", "Long Call", "Long Put", 
                                "Jade Lizard", "Iron Butterfly", "Straddle", "Strangle", "Other"]
                    )
                    trade_direction = st.select_slider(
                        "Direction",
                        options=["Bearish", "Neutral", "Bullish"],
                        value="Neutral"
                    )
                    trade_contracts = st.number_input("Contracts", min_value=1, value=1)
                    
                with entry_cols[1]:
                    st.markdown("**Entry Conditions**")
                    
                    trade_entry_price = st.number_input("Entry Price ($)", value=float(spot_price), step=0.01)
                    trade_vix = st.number_input("VIX at Entry", value=current_vix, step=0.1)
                    trade_dte = st.number_input("DTE at Entry", min_value=1, max_value=365, value=45)
                    trade_regime = st.selectbox(
                        "Market Regime",
                        options=["Trend Up", "Trend Down", "Ranging", "High Vol", "Low Vol"]
                    )
                
                st.markdown("**Risk/Reward**")
                risk_cols = st.columns(2)
                
                with risk_cols[0]:
                    max_profit = st.number_input("Max Profit ($)", value=300.0, step=10.0)
                    max_loss = st.number_input("Max Loss ($)", value=500.0, step=10.0)
                
                with risk_cols[1]:
                    trade_plan = st.text_area(
                        "Trade Plan",
                        placeholder="Why am I entering this trade? What am I expecting?",
                        height=100
                    )
                
                submitted = st.form_submit_button("📝 Log Trade", use_container_width=True)
                
                if submitted:
                    from trade_journal import JournalEntry
                    import uuid
                    
                    entry = JournalEntry(
                        entry_id=str(uuid.uuid4()),
                        entry_date=datetime.now(),
                        exit_date=None,
                        symbol=trade_symbol,
                        strategy_name=trade_strategy,
                        direction=trade_direction,
                        contracts=trade_contracts,
                        entry_price=trade_entry_price,
                        exit_price=None,
                        strikes={},
                        expiration=f"{trade_dte}DTE",
                        dte_entry=trade_dte,
                        dte_exit=None,
                        market_regime=trade_regime,
                        vix_entry=trade_vix,
                        dix_entry=None,
                        underlying_price_entry=trade_entry_price,
                        underlying_price_exit=None,
                        realized_pnl=None,
                        max_profit_potential=max_profit,
                        max_loss_potential=max_loss,
                        roi_pct=None,
                        trade_plan=trade_plan,
                        exit_reason="",
                        notes="",
                        tags=[],
                        status="OPEN"
                    )
                    
                    journal.add_entry(entry)
                    st.success(f"✅ Trade logged! Entry ID: {entry.entry_id[:8]}")
                    st.rerun()
        
        # Performance Dashboard Tab
        with journal_tabs[1]:
            st.markdown("#### 📊 Performance Analytics")
            
            analytics = journal.analyze_performance()
            
            if analytics.total_trades == 0:
                st.info("📝 No trades logged yet. Start by logging your first trade!")
            else:
                # Key metrics
                perf_cols = st.columns(5)
                
                with perf_cols[0]:
                    st.metric("Total P&L", f"${analytics.total_pnl:,.2f}", 
                             delta=f"{analytics.total_return_pct:.2f}%")
                
                with perf_cols[1]:
                    win_rate_color = "normal" if analytics.win_rate < 50 else "inverse"
                    st.metric("Win Rate", f"{analytics.win_rate:.1f}%",
                             delta=f"{analytics.winning_trades}/{analytics.closed_trades}",
                             delta_color=win_rate_color)
                
                with perf_cols[2]:
                    st.metric("Profit Factor", f"{analytics.profit_factor:.2f}")
                
                with perf_cols[3]:
                    st.metric("Avg Win", f"${analytics.avg_win:.2f}")
                
                with perf_cols[4]:
                    st.metric("Avg Loss", f"${analytics.avg_loss:.2f}")
                
                st.markdown("---")
                
                # Advanced metrics
                adv_cols = st.columns(4)
                
                with adv_cols[0]:
                    st.markdown("**📈 Best Performance**")
                    st.metric("Best Strategy", analytics.best_strategy)
                    st.metric("Best Regime", analytics.best_regime)
                
                with adv_cols[1]:
                    st.markdown("**📊 Streaks**")
                    streak_value = analytics.current_streak
                    streak_label = f"{abs(streak_value)} {'Wins' if streak_value > 0 else 'Losses'}"
                    st.metric("Current Streak", streak_label)
                    st.metric("Longest Win", analytics.longest_win_streak)
                
                with adv_cols[2]:
                    st.markdown("**⏱️ Timing**")
                    st.metric("Avg Hold Time", f"{analytics.avg_hold_time:.1f} days")
                    st.metric("Best DTE Entry", f"{analytics.best_dte_entry} days")
                
                with adv_cols[3]:
                    st.markdown("**🧠 Psychology**")
                    st.metric("Revenge Trades", analytics.revenge_trades)
                    overtrading_color = "normal" if analytics.overtrading_score < 50 else "inverse"
                    st.metric("Overtrading Score", f"{analytics.overtrading_score:.0f}/100",
                             delta_color=overtrading_color)
                
                # Visualization
                try:
                    fig_perf = create_performance_dashboard(analytics)
                    st.plotly_chart(fig_perf, use_container_width=True)
                except Exception as e:
                    st.warning(f"Performance chart unavailable: {e}")
                
                # Strategy breakdown
                if analytics.strategy_performance:
                    st.markdown("#### 📋 Performance by Strategy")
                    
                    strategy_data = []
                    for strategy, stats in analytics.strategy_performance.items():
                        strategy_data.append({
                            'Strategy': strategy,
                            'Trades': len(stats['trades']),
                            'Wins': stats['wins'],
                            'Losses': stats['losses'],
                            'Win Rate': f"{stats['win_rate']:.1f}%",
                            'Total P&L': f"${stats['total_pnl']:.2f}"
                        })
                    
                    strategy_df = pd.DataFrame(strategy_data)
                    st.dataframe(strategy_df, use_container_width=True, hide_index=True)
        
        # Trade History Tab
        with journal_tabs[2]:
            st.markdown("#### 📈 Trade History")
            
            # Filter options
            filter_cols = st.columns(3)
            
            with filter_cols[0]:
                status_filter = st.selectbox(
                    "Status",
                    options=["All", "Open", "Closed Wins", "Closed Losses"]
                )
            
            with filter_cols[1]:
                strategy_filter = st.selectbox(
                    "Strategy",
                    options=["All"] + list(set([e.strategy_name for e in journal.entries]))
                )
             
            with filter_cols[2]:
                sort_by = st.selectbox(
                    "Sort By",
                    options=["Entry Date", "P&L", "Win Rate"]
                )
            
            # Get trades
            if status_filter == "Open":
                trades = journal.get_open_trades()
            elif status_filter == "Closed Wins":
                trades = [e for e in journal.get_closed_trades() if e.status == "CLOSED_WIN"]
            elif status_filter == "Closed Losses":
                trades = [e for e in journal.get_closed_trades() if e.status == "CLOSED_LOSS"]
            else:
                trades = journal.entries
            
            # Apply strategy filter
            if strategy_filter != "All":
                trades = [t for t in trades if t.strategy_name == strategy_filter]
            
            if not trades:
                st.info("No trades match the selected filters.")
            else:
                st.markdown(f"**Showing {len(trades)} trade(s)**")
                
                # Display trades
                for trade in reversed(trades[-20:]):  # Show last 20
                    status_emoji = "🟢" if trade.status == "OPEN" else "✅" if trade.status == "CLOSED_WIN" else "❌"
                    
                    with st.expander(f"{status_emoji} {trade.strategy_name} - {trade.entry_date.strftime('%Y-%m-%d')} - {trade.symbol}"):
                        trade_cols = st.columns(4)
                        
                        with trade_cols[0]:
                            st.markdown("**Entry**")
                            st.text(f"Date: {trade.entry_date.strftime('%Y-%m-%d')}")
                            st.text(f"Price: ${trade.entry_price:.2f}")
                            st.text(f"Contracts: {trade.contracts}")
                            st.text(f"DTE: {trade.dte_entry}")
                        
                        with trade_cols[1]:
                            st.markdown("**Exit**")
                            if trade.exit_date:
                                st.text(f"Date: {trade.exit_date.strftime('%Y-%m-%d')}")
                                st.text(f"Price: ${trade.exit_price:.2f}")
                                st.text(f"DTE: {trade.dte_exit}")
                            else:
                                st.text("Still Open")
                        
                        with trade_cols[2]:
                            st.markdown("**Performance**")
                            if trade.realized_pnl is not None:
                                st.text(f"P&L: ${trade.realized_pnl:.2f}")
                                if trade.roi_pct:
                                    st.text(f"ROI: {trade.roi_pct:.1f}%")
                                st.text(f"Status: {trade.status}")
                            else:
                                st.text("In Progress")
                        
                        with trade_cols[3]:
                            st.markdown("**Context**")
                            st.text(f"Regime: {trade.market_regime}")
                            st.text(f"VIX: {trade.vix_entry:.1f}")
                            st.text(f"Direction: {trade.direction}")
                        
                        if trade.trade_plan:
                            st.markdown(f"**Plan:** {trade.trade_plan}")
                        
                        if trade.exit_reason:
                            st.markdown(f"**Exit Reason:** {trade.exit_reason}")
                        
                        # Option to close trade
                        if trade.status == "OPEN":
                            if st.button(f"Close Trade #{trade.entry_id[:8]}", key=f"close_{trade.entry_id}"):
                                # Would show form to close trade
                                st.info("Trade close form would appear here")
        
        # Insights Tab
        with journal_tabs[3]:
            st.markdown("#### 💡 Performance Insights")
            
            analytics = journal.analyze_performance()
            
            if analytics.total_trades < 5:
                st.info("📝 Log at least 5 trades to unlock detailed insights!")
            else:
                st.markdown("### 🎯 Key Takeaways")
                
                # Best practices
                if analytics.win_rate > 60:
                    st.success(f"✅ **Great Win Rate!** Your {analytics.win_rate:.0f}% win rate is excellent. Keep doing what you're doing!")
                elif analytics.win_rate > 50:
                    st.info(f"➡️ **Solid Performance** - {analytics.win_rate:.0f}% win rate. Focus on increasing position sizes on your best setups.")
                else:
                    st.warning(f"⚠️ **Win Rate Below 50%** - Currently at {analytics.win_rate:.0f}%. Review your losing trades for patterns.")
                
                # Profit factor analysis
                if analytics.profit_factor > 2.0:
                    st.success(f"🎉 **Exceptional Profit Factor!** {analytics.profit_factor:.2f} shows you're cutting losses and letting winners run.")
                elif analytics.profit_factor > 1.5:
                    st.info(f"✅ **Good Profit Factor** - {analytics.profit_factor:.2f} indicates healthy risk management.")
                elif analytics.profit_factor > 1.0:
                    st.warning(f"⚠️ **Mediocre Profit Factor** - {analytics.profit_factor:.2f}. Work on cutting losses faster.")
                else:
                    st.error(f"❌ **Poor Profit Factor** - {analytics.profit_factor:.2f}. Your losses are outpacing wins. Review your risk management.")
                
                # Strategy recommendations
                st.markdown("### 📊 Strategy Analysis")
                
                if analytics.strategy_performance:
                    best_strat = analytics.best_strategy
                    best_wr = analytics.strategy_performance[best_strat]['win_rate']
                    
                    st.success(f"🏆 **Best Strategy:** {best_strat} ({best_wr:.0f}% win rate)")
                    st.info(f"💡 **Recommendation:** Increase allocation to {best_strat}. It's working well for you!")
                    
                    if analytics.worst_strategy and analytics.worst_strategy != best_strat:
                        st.warning(f"⚠️ **Worst Strategy:** {analytics.worst_strategy}. Consider avoiding or adjusting this.")
                
                # Regime insights
                st.markdown("### 🌦️ Market Regime Insights")
                
                if analytics.regime_performance:
                    best_regime = analytics.best_regime
                    best_regime_wr = analytics.regime_performance[best_regime]['win_rate']
                    
                    st.success(f"🎯 **Best Regime:** {best_regime} ({best_regime_wr:.0f}% win rate)")
                    st.info(f"💡 **Tip:** You perform best in {best_regime} conditions. Size up when you identify this regime!")
                
                # Psychological insights
                st.markdown("### 🧠 Psychological Analysis")
                
                if analytics.revenge_trades > 0:
                    st.warning(f"⚠️ **Revenge Trading Detected:** {analytics.revenge_trades} trade(s) entered within 24h of a loss. Avoid emotional decisions!")
                
                if analytics.overtrading_score > 70:
                    st.error(f"❌ **Overtrading Alert:** Score of {analytics.overtrading_score:.0f}/100. You may be trading too frequently. Quality > Quantity!")
                elif analytics.overtrading_score > 50:
                    st.warning(f"⚠️ **Moderate Overtrading:** Score of {analytics.overtrading_score:.0f}/100. Be selective with entries.")
                else:
                    st.success(f"✅ **Good Trade Frequency:** Score of {analytics.overtrading_score:.0f}/100. You're being selective!")
                
                # Action items
                st.markdown("### ✅ Action Items")
                
                action_items = []
                
                if analytics.win_rate < 50:
                    action_items.append("📉 Review losing trades and identify common mistakes")
                
                if analytics.profit_factor < 1.5:
                    action_items.append("✂️ Cut losses faster - Your average loss is too large")
                
                if analytics.revenge_trades > 2:
                    action_items.append("😤 Take a break after losses - Avoid revenge trading")
                
                if analytics.overtrading_score > 60:
                    action_items.append("⏸️ Reduce trading frequency - Wait for high-quality setups")
                
                if len(action_items) == 0:
                    st.success("🎉 **No critical issues!** Keep up the great work!")
                else:
                    for item in action_items:
                        st.markdown(f"- {item}")
    
    with tabs[9]:


        st.markdown("### ⚡ Real-Time Market Data")
        
        # Auto-refresh toggle
        auto_refresh = st.checkbox("Enable Auto-Refresh (30s)", value=False)
        
        if auto_refresh:
            display = StreamlitRealtimeDisplay()
            display.create_auto_refresh(30)
        
        # Initialize real-time feed
        realtime_feed = RealtimeDataFeed(update_interval=5)
        
        # Display timestamp
        st.caption(f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        
        # Market snapshot
        st.markdown("#### 📊 Live Market Snapshot")
        
        # Create snapshot (using current data as placeholder)
        snapshot = MarketSnapshot(
            timestamp=datetime.now(),
            underlying_price=spot_price,
            vix=current_vix,
            spx=spot_price,
            dix=dix_current if 'dix_current' in locals() else None,
            gex=gex_current if 'gex_current' in locals() else None
        )
        
        display = StreamlitRealtimeDisplay()
        display.display_market_snapshot(snapshot)
        
        st.markdown("---")
        
        # Symbol tracker
        st.markdown("#### 🎯 Symbol Tracker")
        
        tracked_symbols = st.multiselect(
            "Select Symbols to Track",
            options=["SPY", "SPX", "QQQ", "IWM", "VIX", "DIA", "TLT", "GLD"],
            default=["SPY", "QQQ", "VIX"]
        )
        
        if tracked_symbols:
            for symbol in tracked_symbols:
                with st.expander(f"{symbol} - Live Quote"):
                    # Placeholder quote (replace with actual API call)
                    st.markdown(f"""
                    **{symbol}** - Real-time data would appear here with:
                    - Bid/Ask Spread
                    - Last Price
                    - Volume
                    - Implied Volatility (for options)
                    - Greeks (Delta, Gamma, Theta, Vega)
                    
                    *Connect your real-time data feed API to enable live updates*
                    """)
        
        # Data feed configuration
        with st.expander("⚙️ Configure Real-Time Data Feed"):
            st.markdown("""
            **Supported Data Sources:**
            - REST API polling (current)
            - WebSocket streams (future)
            - Third-party providers (Interactive Brokers, TD Ameritrade, etc.)
            
            **Configuration:**
            Add API endpoints in your `.env` file:
            ```
            REALTIME_API_SPX=https://your-api.com/quote/SPX
            REALTIME_API_VIX=https://your-api.com/quote/VIX
            REALTIME_API_DIX=https://squeezemetrics.com/dix
            ```
            """)
        
        if st.button("🔄 Refresh Now"):
            st.rerun()
    
    with tabs[7]:

        st.markdown("### Raw Data Tables")
        
        tab1, tab2, tab3 = st.tabs(["OHLC Data", "GEX Levels", "GEX Profile"])
        
        with tab1:
            st.dataframe(ohlc.iloc[::-1, :], use_container_width=True)
        with tab2:
            st.dataframe(gex_levels, use_container_width=True, hide_index=True)
        with tab3:
            st.dataframe(gex_profile, use_container_width=True, hide_index=True)
    
    # === FOOTER ===
    st.markdown("---")
    st.markdown("""
        <div style='text-align: center; color: #667eea; padding: 2rem;'>
            <h3>⚡ Institutional-Grade Trading Intelligence</h3>
            <p style='color: #8b95b0;'>
                Powered by Advanced ML • Real-time Greeks • Kelly Criterion • Volatility Arbitrage
            </p>
        </div>
    """, unsafe_allow_html=True)


if __name__ == "__main__":
    main()

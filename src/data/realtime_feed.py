"""
Real-Time Data Streaming Module
WebSocket and REST API integration for live market data
"""

import asyncio
import json
import time
import requests
import pandas as pd
from typing import Dict, List, Optional, Callable
from datetime import datetime
from dataclasses import dataclass
from threading import Thread
import streamlit as st


@dataclass
class RealtimeQuote:
    """Real-time quote data"""
    symbol: str
    timestamp: datetime
    bid: float
    ask: float
    last: float
    volume: int
    open_interest: Optional[int] = None
    delta: Optional[float] = None
    gamma: Optional[float] = None
    theta: Optional[float] = None
    vega: Optional[float] = None
    iv: Optional[float] = None


@dataclass
class MarketSnapshot:
    """Complete market snapshot"""
    timestamp: datetime
    underlying_price: float
    vix: float
    spx: float
    dix: Optional[float] = None
    gex: Optional[float] = None
    net_gamma: Optional[float] = None
    call_put_ratio: Optional[float] = None
    advance_decline: Optional[float] = None


class RealtimeDataFeed:
    """
    Real-time data streaming manager
    
    Supports multiple data sources:
    - REST API polling
    - WebSocket streams (future)
    - Third-party data providers
    """
    
    def __init__(
        self,
        update_interval: int = 5,  # seconds
        enable_caching: bool = True
    ):
        """
        Initialize real-time data feed
        
        Args:
            update_interval: Seconds between updates (REST polling)
            enable_caching: Cache recent data to reduce API calls
        """
        self.update_interval = update_interval
        self.enable_caching = enable_caching
        
        # Data cache
        self.cache: Dict[str, RealtimeQuote] = {}
        self.last_update: Optional[datetime] = None
        
        # Callbacks for data updates
        self.callbacks: List[Callable] = []
    
    def fetch_realtime_quote(
        self,
        symbol: str,
        api_url: Optional[str] = None
    ) -> Optional[RealtimeQuote]:
        """
        Fetch real-time quote for a symbol
        
        Args:
            symbol: Ticker symbol (e.g., "SPY", "AAPL")
            api_url: Optional API endpoint override
            
        Returns:
            RealtimeQuote or None if fetch fails
        """
        
        # Check cache first
        if self.enable_caching and symbol in self.cache:
            cached_quote = self.cache[symbol]
            age = (datetime.now() - cached_quote.timestamp).total_seconds()
            
            if age < self.update_interval:
                return cached_quote
        
        try:
            # Fetch from API
            # This is a template - replace with actual API endpoint
            if api_url is None:
                # Example: Using a free API (replace with your actual endpoint)
                api_url = f"https://api.example.com/quote/{symbol}"
            
            response = requests.get(
                api_url,
                headers={'User-Agent': 'TradingPlatform/1.0'},
                timeout=5
            )
            
            if response.status_code == 200:
                data = response.json()
                
                # Parse response (adjust based on your API structure)
                quote = RealtimeQuote(
                    symbol=symbol,
                    timestamp=datetime.now(),
                    bid=data.get('bid', 0.0),
                    ask=data.get('ask', 0.0),
                    last=data.get('last', 0.0),
                    volume=data.get('volume', 0),
                    iv=data.get('implied_volatility', None)
                )
                
                # Cache the quote
                self.cache[symbol] = quote
                
                return quote
            
        except Exception as e:
            st.warning(f"Failed to fetch real-time data for {symbol}: {e}")
            return None
        
        return None
    
    def fetch_market_snapshot(
        self,
        api_endpoints: Dict[str, str]
    ) -> MarketSnapshot:
        """
        Fetch complete market snapshot
        
        Args:
            api_endpoints: Dictionary of API endpoints
                - 'spx': SPX price endpoint
                - 'vix': VIX endpoint  
                - 'dix': DIX endpoint (optional)
                - 'gex': GEX endpoint (optional)
                
        Returns:
            MarketSnapshot with current market state
        """
        
        snapshot_data = {
            'timestamp': datetime.now(),
            'underlying_price': 0.0,
            'vix': 0.0,
            'spx': 0.0,
        }
        
        # Fetch SPX
        if 'spx' in api_endpoints:
            spx_quote = self.fetch_realtime_quote('SPX', api_endpoints['spx'])
            if spx_quote:
                snapshot_data['spx'] = spx_quote.last
                snapshot_data['underlying_price'] = spx_quote.last
        
        # Fetch VIX
        if 'vix' in api_endpoints:
            vix_quote = self.fetch_realtime_quote('VIX', api_endpoints['vix'])
            if vix_quote:
                snapshot_data['vix'] = vix_quote.last
        
        # Fetch DIX (if available)
        if 'dix' in api_endpoints:
            try:
                response = requests.get(api_endpoints['dix'], timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    snapshot_data['dix'] = data.get('dix', None)
            except:
                pass
        
        # Fetch GEX (if available)
        if 'gex' in api_endpoints:
            try:
                response = requests.get(api_endpoints['gex'], timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    snapshot_data['gex'] = data.get('gex', None)
                    snapshot_data['net_gamma'] = data.get('net_gamma', None)
            except:
                pass
        
        return MarketSnapshot(**snapshot_data)
    
    def stream_data(
        self,
        symbols: List[str],
        callback: Callable[[Dict[str, RealtimeQuote]], None],
        duration_seconds: Optional[int] = None
    ):
        """
        Stream data for multiple symbols
        
        Args:
            symbols: List of symbols to stream
            callback: Function to call with updated data
            duration_seconds: How long to stream (None = indefinite)
        """
        
        start_time = time.time()
        
        while True:
            # Check duration
            if duration_seconds and (time.time() - start_time) > duration_seconds:
                break
            
            # Fetch quotes for all symbols
            quotes = {}
            for symbol in symbols:
                quote = self.fetch_realtime_quote(symbol)
                if quote:
                    quotes[symbol] = quote
            
            # Call callback with updated data
            if quotes:
                callback(quotes)
            
            # Wait for next update
            time.sleep(self.update_interval)
    
    def add_update_callback(self, callback: Callable):
        """Add a callback function to be called on data updates"""
        self.callbacks.append(callback)
    
    def notify_callbacks(self, data: Dict):
        """Notify all registered callbacks with new data"""
        for callback in self.callbacks:
            try:
                callback(data)
            except Exception as e:
                print(f"Callback error: {e}")


class StreamlitRealtimeDisplay:
    """
    Streamlit-specific real-time display components
    """
    
    @staticmethod
    def display_realtime_ticker(
        symbol: str,
        quote: RealtimeQuote,
        key: str = "ticker"
    ):
        """Display a real-time ticker widget"""
        
        # Calculate change
        change = 0.0
        change_pct = 0.0
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric(
                label=f"{symbol}",
                value=f"${quote.last:.2f}",
                delta=f"{change_pct:+.2f}%"
            )
        
        with col2:
            st.metric("Bid", f"${quote.bid:.2f}")
        
        with col3:
            st.metric("Ask", f"${quote.ask:.2f}")
        
        with col4:
            st.metric("Volume", f"{quote.volume:,}")
        
        # IV if available
        if quote.iv:
            st.metric("Implied Vol", f"{quote.iv:.1f}%")
    
    @staticmethod
    def display_market_snapshot(snapshot: MarketSnapshot):
        """Display market snapshot dashboard"""
        
        st.markdown("### 📊 Live Market Snapshot")
        
        col1, col2, col3, col4 = st.columns(4)
        
        with col1:
            st.metric("SPX", f"${snapshot.spx:.2f}")
        
        with col2:
            st.metric("VIX", f"{snapshot.vix:.2f}")
        
        with col3:
            if snapshot.dix:
                st.metric("DIX", f"{snapshot.dix:.3f}")
            else:
                st.metric("DIX", "N/A")
        
        with col4:
            if snapshot.gex:
                st.metric("GEX", f"${snapshot.gex:,.0f}M")
            else:
                st.metric("GEX", "N/A")
        
        # Timestamp
        st.caption(f"Last updated: {snapshot.timestamp.strftime('%Y-%m-%d %H:%M:%S')}")
    
    @staticmethod
    def create_auto_refresh(interval_seconds: int = 30):
        """
        Create auto-refresh for Streamlit app
        
        Args:
            interval_seconds: Refresh interval in seconds
        """
        
        st.markdown(f"""
        <script>
            setTimeout(function() {{
                window.location.reload();
            }}, {interval_seconds * 1000});
        </script>
        """, unsafe_allow_html=True)


class DataStreamManager:
    """
    Manage multiple data streams efficiently
    """
    
    def __init__(self):
        self.active_streams: Dict[str, Thread] = {}
        self.data_buffer: Dict[str, pd.DataFrame] = {}
    
    def start_stream(
        self,
        stream_id: str,
        symbols: List[str],
        feed: RealtimeDataFeed,
        buffer_size: int = 1000
    ):
        """Start a new data stream"""
        
        def stream_worker():
            """Worker thread for streaming"""
            data_points = []
            
            def on_update(quotes: Dict[str, RealtimeQuote]):
                """Handle data updates"""
                for symbol, quote in quotes.items():
                    data_points.append({
                        'timestamp': quote.timestamp,
                        'symbol': symbol,
                        'price': quote.last,
                        'bid': quote.bid,
                        'ask': quote.ask,
                        'volume': quote.volume,
                    })
                
                # Maintain buffer size
                if len(data_points) > buffer_size:
                    data_points.pop(0)
                
                # Update buffer
                self.data_buffer[stream_id] = pd.DataFrame(data_points)
            
            feed.stream_data(symbols, on_update)
        
        # Start thread
        thread = Thread(target=stream_worker, daemon=True)
        thread.start()
        
        self.active_streams[stream_id] = thread
    
    def get_stream_data(self, stream_id: str) -> Optional[pd.DataFrame]:
        """Get buffered data from a stream"""
        return self.data_buffer.get(stream_id)
    
    def stop_stream(self, stream_id: str):
        """Stop a data stream"""
        if stream_id in self.active_streams:
            # Thread will stop naturally since it's a daemon
            del self.active_streams[stream_id]
            
            if stream_id in self.data_buffer:
                del self.data_buffer[stream_id]


# Example usage functions

def example_realtime_integration():
    """
    Example of how to integrate real-time data into Streamlit app
    """
    
    st.title("Real-Time Market Data")
    
    # Initialize feed
    feed = RealtimeDataFeed(update_interval=5)
    
    # API endpoints (replace with actual endpoints)
    api_endpoints = {
        'spx': 'https://api.example.com/quote/SPX',
        'vix': 'https://api.example.com/quote/VIX',
        'dix': 'https://api.squeezemetrics.com/dix',  # Example
        'gex': 'https://api.example.com/gex',
    }
    
    # Fetch snapshot
    snapshot = feed.fetch_market_snapshot(api_endpoints)
    
    # Display
    display = StreamlitRealtimeDisplay()
    display.display_market_snapshot(snapshot)
    
    # Auto-refresh every 30 seconds
    display.create_auto_refresh(30)
    
    # Individual quotes
    st.markdown("---")
    st.markdown("### Symbol Quotes")
    
    symbols = ['SPY', 'QQQ', 'IWM', 'VIX']
    
    for symbol in symbols:
        quote = feed.fetch_realtime_quote(symbol)
        if quote:
            with st.expander(f"{symbol} - ${quote.last:.2f}"):
                display.display_realtime_ticker(symbol, quote)

"""
Polygon.io API Client
REST client for quotes, options chains, OHLCV aggregates.
WebSocket support for real-time streaming.
"""

import os
import json
import time
import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, List, Callable
from dataclasses import dataclass
import threading

import requests
import pandas as pd
import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class PolygonConfig:
    """Polygon.io connection configuration"""
    api_key: str = ""
    base_url: str = "https://api.polygon.io"
    ws_url: str = "wss://socket.polygon.io"
    max_retries: int = 3
    timeout: int = 10
    rate_limit_per_minute: int = 5  # Free tier


class PolygonClient:
    """
    REST client for Polygon.io market data.

    Supports:
    - Stock/ETF quotes and snapshots
    - Options chain data
    - OHLCV aggregates (bars)
    - Reference data (tickers, exchanges)
    """

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("POLYGON_API_KEY", "")
        self.base_url = "https://api.polygon.io"
        self.session = requests.Session()
        self.session.params = {"apiKey": self.api_key}
        self._last_request_time = 0
        self._min_interval = 12.0  # seconds between requests (free tier: 5/min)

    @classmethod
    def from_config(cls, config) -> "PolygonClient":
        """Create from unified Config object."""
        return cls(api_key=config.polygon_api_key)

    def _rate_limit(self):
        """Enforce rate limiting."""
        elapsed = time.time() - self._last_request_time
        if elapsed < self._min_interval:
            time.sleep(self._min_interval - elapsed)
        self._last_request_time = time.time()

    def _get(self, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """Make rate-limited GET request."""
        self._rate_limit()
        url = f"{self.base_url}{endpoint}"
        try:
            resp = self.session.get(url, params=params or {}, timeout=10)
            resp.raise_for_status()
            return resp.json()
        except requests.RequestException as e:
            logger.error(f"Polygon API error: {e}")
            return None

    # =========================================================================
    # Quotes & Snapshots
    # =========================================================================

    def get_snapshot(self, symbol: str) -> Optional[Dict]:
        """Get current snapshot for a ticker (price, volume, etc.)."""
        data = self._get(f"/v2/snapshot/locale/us/markets/stocks/tickers/{symbol}")
        if data and data.get("status") == "OK":
            return data.get("ticker", {})
        return None

    def get_last_quote(self, symbol: str) -> Optional[Dict]:
        """Get the most recent NBBO quote."""
        data = self._get(f"/v3/quotes/{symbol}", {"limit": 1, "order": "desc"})
        if data and data.get("results"):
            return data["results"][0]
        return None

    def get_last_trade(self, symbol: str) -> Optional[Dict]:
        """Get the most recent trade."""
        data = self._get(f"/v3/trades/{symbol}", {"limit": 1, "order": "desc"})
        if data and data.get("results"):
            return data["results"][0]
        return None

    # =========================================================================
    # OHLCV Aggregates
    # =========================================================================

    def get_aggregates(
        self,
        symbol: str,
        multiplier: int = 1,
        timespan: str = "day",
        from_date: Optional[str] = None,
        to_date: Optional[str] = None,
        limit: int = 120,
    ) -> Optional[pd.DataFrame]:
        """
        Get OHLCV aggregate bars.

        Args:
            symbol: Ticker symbol
            multiplier: Size of the timespan multiplier
            timespan: day, hour, minute, week, month, quarter, year
            from_date: Start date (YYYY-MM-DD)
            to_date: End date (YYYY-MM-DD)
            limit: Max number of results

        Returns:
            DataFrame with columns: [timestamp, open, high, low, close, volume, vwap]
        """
        if not from_date:
            from_date = (date.today() - timedelta(days=180)).isoformat()
        if not to_date:
            to_date = date.today().isoformat()

        data = self._get(
            f"/v2/aggs/ticker/{symbol}/range/{multiplier}/{timespan}/{from_date}/{to_date}",
            {"limit": limit, "adjusted": "true", "sort": "asc"},
        )

        if not data or not data.get("results"):
            return None

        df = pd.DataFrame(data["results"])
        df = df.rename(columns={
            "t": "timestamp", "o": "open", "h": "high", "l": "low",
            "c": "close", "v": "volume", "vw": "vwap", "n": "transactions",
        })
        df["timestamp"] = pd.to_datetime(df["timestamp"], unit="ms")
        df = df.set_index("timestamp")
        return df

    # =========================================================================
    # Options
    # =========================================================================

    def get_options_chain(
        self,
        underlying: str,
        expiration_date: Optional[str] = None,
        contract_type: Optional[str] = None,
        strike_price_gte: Optional[float] = None,
        strike_price_lte: Optional[float] = None,
        limit: int = 250,
    ) -> Optional[pd.DataFrame]:
        """
        Get options contracts snapshot.

        Args:
            underlying: Underlying ticker (e.g., "SPY")
            expiration_date: Filter by expiration (YYYY-MM-DD)
            contract_type: "call" or "put"
            strike_price_gte: Min strike price
            strike_price_lte: Max strike price

        Returns:
            DataFrame with options chain data
        """
        params = {
            "underlying_ticker": underlying,
            "limit": limit,
            "order": "asc",
            "sort": "strike_price",
        }
        if expiration_date:
            params["expiration_date"] = expiration_date
        if contract_type:
            params["contract_type"] = contract_type
        if strike_price_gte is not None:
            params["strike_price.gte"] = strike_price_gte
        if strike_price_lte is not None:
            params["strike_price.lte"] = strike_price_lte

        data = self._get("/v3/snapshot/options/" + underlying, params)
        if not data or not data.get("results"):
            return None

        records = []
        for item in data["results"]:
            details = item.get("details", {})
            greeks = item.get("greeks", {})
            day = item.get("day", {})

            records.append({
                "symbol": details.get("ticker", ""),
                "strike": details.get("strike_price", 0),
                "expiration": details.get("expiration_date", ""),
                "contract_type": details.get("contract_type", ""),
                "volume": day.get("volume", 0),
                "openInterest": item.get("open_interest", 0),
                "lastPrice": day.get("close", 0),
                "impliedVolatility": item.get("implied_volatility", 0),
                "delta": greeks.get("delta", 0),
                "gamma": greeks.get("gamma", 0),
                "theta": greeks.get("theta", 0),
                "vega": greeks.get("vega", 0),
                "underlying_price": item.get("underlying_asset", {}).get("price", 0),
            })

        return pd.DataFrame(records)

    def get_options_chain_split(
        self,
        underlying: str,
        expiration_date: Optional[str] = None,
    ) -> tuple:
        """
        Get calls and puts DataFrames separately (compatible with other calculators).

        Returns:
            (calls_df, puts_df) tuple
        """
        chain = self.get_options_chain(underlying, expiration_date=expiration_date)
        if chain is None or chain.empty:
            return None, None

        calls = chain[chain["contract_type"] == "call"].copy()
        puts = chain[chain["contract_type"] == "put"].copy()
        return calls, puts


class PolygonWebSocket:
    """
    WebSocket client for real-time Polygon.io streaming.

    Streams:
    - T.* — Trades
    - Q.* — Quotes
    - A.* — Second aggregates
    - AM.* — Minute aggregates
    """

    def __init__(self, api_key: Optional[str] = None, cluster: str = "stocks"):
        self.api_key = api_key or os.getenv("POLYGON_API_KEY", "")
        self.cluster = cluster
        self.ws_url = f"wss://socket.polygon.io/{cluster}"
        self._ws = None
        self._thread = None
        self._running = False
        self._callbacks: Dict[str, List[Callable]] = {}

    def subscribe(self, channels: List[str], callback: Callable):
        """
        Subscribe to channels with a callback.

        Args:
            channels: List of channels like ["T.SPY", "Q.SPY", "AM.SPY"]
            callback: Function called with (channel, data) for each message
        """
        for ch in channels:
            if ch not in self._callbacks:
                self._callbacks[ch] = []
            self._callbacks[ch].append(callback)

    def start(self):
        """Start the WebSocket connection in a background thread."""
        try:
            import websocket
        except ImportError:
            logger.error("websocket-client not installed. Run: pip install websocket-client")
            return

        self._running = True

        def _on_message(ws, message):
            data = json.loads(message)
            if isinstance(data, list):
                for msg in data:
                    ev = msg.get("ev", "")
                    sym = msg.get("sym", "")
                    channel = f"{ev}.{sym}"
                    for cb in self._callbacks.get(channel, []):
                        try:
                            cb(channel, msg)
                        except Exception as e:
                            logger.error(f"Callback error: {e}")

        def _on_open(ws):
            # Authenticate
            ws.send(json.dumps({"action": "auth", "params": self.api_key}))
            # Subscribe to channels
            all_channels = list(self._callbacks.keys())
            if all_channels:
                ws.send(json.dumps({
                    "action": "subscribe",
                    "params": ",".join(all_channels),
                }))
            logger.info(f"Polygon WebSocket connected, subscribed to {len(all_channels)} channels")

        def _on_error(ws, error):
            logger.error(f"Polygon WebSocket error: {error}")

        def _on_close(ws, close_status_code, close_msg):
            logger.info("Polygon WebSocket closed")
            self._running = False

        def _run():
            import websocket
            self._ws = websocket.WebSocketApp(
                self.ws_url,
                on_message=_on_message,
                on_open=_on_open,
                on_error=_on_error,
                on_close=_on_close,
            )
            self._ws.run_forever()

        self._thread = threading.Thread(target=_run, daemon=True)
        self._thread.start()

    def stop(self):
        """Stop the WebSocket connection."""
        self._running = False
        if self._ws:
            self._ws.close()

"""
DataManager — Unified data access with fallback chain.
Schwab → Polygon → yfinance

Provides a single interface for all market data needs.
"""

import logging
from typing import Optional, Dict, Tuple
from datetime import date, timedelta

import pandas as pd

logger = logging.getLogger(__name__)


class DataManager:
    """
    Unified data facade with automatic failover.

    Priority:
    1. Schwab (if configured + authenticated)
    2. Polygon.io (if API key configured)
    3. yfinance (always available, free)
    """

    def __init__(self, config=None):
        if config is None:
            from src.config.config import get_config
            config = self._config = get_config()
        else:
            self._config = config

        self._schwab = None
        self._polygon = None

        # Initialize Schwab if configured
        if config.schwab_app_key:
            try:
                from src.data.schwab_connector import SchwabDataConnector
                self._schwab = SchwabDataConnector.from_config(config)
                logger.info("Schwab connector initialized")
            except Exception as e:
                logger.warning(f"Schwab connector unavailable: {e}")

        # Initialize Polygon if configured
        if config.polygon_api_key:
            try:
                from src.data.polygon_client import PolygonClient
                self._polygon = PolygonClient.from_config(config)
                logger.info("Polygon client initialized")
            except Exception as e:
                logger.warning(f"Polygon client unavailable: {e}")

    def get_quote(self, symbol: str) -> Optional[Dict]:
        """Get current quote with fallback chain."""
        # Try Schwab
        if self._schwab:
            try:
                result = self._schwab.get_quote(symbol)
                if result:
                    return {"price": result.get("lastPrice"), "source": "schwab", **result}
            except Exception as e:
                logger.debug(f"Schwab quote failed for {symbol}: {e}")

        # Try Polygon
        if self._polygon:
            try:
                snap = self._polygon.get_snapshot(symbol)
                if snap:
                    day = snap.get("day", {})
                    return {
                        "price": day.get("c") or snap.get("lastTrade", {}).get("p"),
                        "volume": day.get("v"),
                        "source": "polygon",
                    }
            except Exception as e:
                logger.debug(f"Polygon quote failed for {symbol}: {e}")

        # Fallback to yfinance
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            info = ticker.fast_info
            price = getattr(info, "last_price", None)
            if price is None:
                hist = ticker.history(period="1d")
                if not hist.empty:
                    price = float(hist["Close"].iloc[-1])
            prev_close = getattr(info, "previous_close", None)
            return {
                "price": price,
                "previous_close": prev_close,
                "change": (price - prev_close) if (price and prev_close) else None,
                "source": "yfinance",
            }
        except Exception as e:
            logger.error(f"All data sources failed for {symbol}: {e}")
            return None

    def get_options_chain(
        self, symbol: str, expiration: Optional[str] = None
    ) -> Tuple[Optional[pd.DataFrame], Optional[pd.DataFrame]]:
        """Get options chain (calls_df, puts_df) with fallback chain."""
        # Try Schwab
        if self._schwab:
            try:
                chain = self._schwab.get_option_chain(symbol)
                if chain:
                    calls = pd.DataFrame(chain.get("calls", []))
                    puts = pd.DataFrame(chain.get("puts", []))
                    if not calls.empty:
                        return calls, puts
            except Exception as e:
                logger.debug(f"Schwab chain failed for {symbol}: {e}")

        # Try Polygon
        if self._polygon:
            try:
                calls, puts = self._polygon.get_options_chain_split(
                    symbol, expiration_date=expiration
                )
                if calls is not None and not calls.empty:
                    return calls, puts
            except Exception as e:
                logger.debug(f"Polygon chain failed for {symbol}: {e}")

        # Fallback to yfinance
        try:
            import yfinance as yf
            ticker = yf.Ticker(symbol)
            expirations = ticker.options
            if not expirations:
                return None, None
            exp = expiration or expirations[0]
            chain = ticker.option_chain(exp)
            calls = chain.calls.copy()
            puts = chain.puts.copy()
            calls["expiration"] = exp
            puts["expiration"] = exp
            return calls, puts
        except Exception as e:
            logger.error(f"All options sources failed for {symbol}: {e}")
            return None, None

    def get_ohlcv(
        self,
        symbol: str,
        days: int = 120,
        interval: str = "day",
    ) -> Optional[pd.DataFrame]:
        """Get OHLCV data with fallback chain."""
        from_date = (date.today() - timedelta(days=days)).isoformat()
        to_date = date.today().isoformat()

        # Try Polygon
        if self._polygon:
            try:
                df = self._polygon.get_aggregates(
                    symbol, timespan=interval, from_date=from_date, to_date=to_date, limit=days
                )
                if df is not None and not df.empty:
                    return df
            except Exception as e:
                logger.debug(f"Polygon OHLCV failed for {symbol}: {e}")

        # Fallback to yfinance
        try:
            import yfinance as yf
            period_map = {30: "1mo", 90: "3mo", 120: "6mo", 365: "1y"}
            period = "6mo"
            for threshold, p in sorted(period_map.items()):
                if days <= threshold:
                    period = p
                    break
            ticker = yf.Ticker(symbol)
            df = ticker.history(period=period)
            if not df.empty:
                df.columns = [c.lower() for c in df.columns]
                return df
        except Exception as e:
            logger.error(f"All OHLCV sources failed for {symbol}: {e}")

        return None

    @property
    def available_sources(self) -> list:
        """List currently available data sources."""
        sources = ["yfinance"]
        if self._schwab:
            sources.insert(0, "schwab")
        if self._polygon:
            sources.insert(-1, "polygon")
        return sources

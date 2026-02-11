"""
Quote endpoints — real-time stock/ETF/index quotes.
Refactored from Trading_Terminal's backend.
"""

from flask import Blueprint, jsonify
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
quotes_bp = Blueprint("quotes", __name__)

# Ticker mapping: frontend ticker -> yfinance ticker
TICKER_MAP = {
    "SPY": "SPY",
    "SPX": "^GSPC",
    "QQQ": "QQQ",
    "IWM": "IWM",
    "VIX": "^VIX",
    "ES": "ES=F",
    "NQ": "NQ=F",
    "RTY": "RTY=F",
    "GLD": "GLD",
    "DIA": "DIA",
}


def _get_yf_ticker(ticker: str) -> str:
    return TICKER_MAP.get(ticker.upper(), ticker.upper())


@quotes_bp.route("/api/quote/<ticker>")
def quote(ticker):
    """Get real-time quote for a ticker."""
    try:
        import yfinance as yf

        yf_ticker = _get_yf_ticker(ticker)
        t = yf.Ticker(yf_ticker)
        info = t.fast_info

        price = getattr(info, "last_price", None)
        if price is None:
            hist = t.history(period="1d")
            if not hist.empty:
                price = float(hist["Close"].iloc[-1])

        prev_close = getattr(info, "previous_close", None)
        change = None
        change_pct = None
        if price and prev_close:
            change = price - prev_close
            change_pct = (change / prev_close) * 100

        return jsonify({
            "ticker": ticker,
            "price": price,
            "previous_close": prev_close,
            "change": change,
            "change_pct": change_pct,
            "market_cap": getattr(info, "market_cap", None),
            "timestamp": datetime.now().isoformat(),
            "source": "yfinance",
        })
    except Exception as e:
        logger.error(f"Quote error for {ticker}: {e}")
        return jsonify({"error": str(e), "ticker": ticker}), 500


@quotes_bp.route("/api/health")
def health():
    return jsonify({
        "status": "ok",
        "timestamp": datetime.now().isoformat(),
        "version": "1.0.0",
    })

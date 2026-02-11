"""
Options endpoints — chains, IV surface, term structure.
Refactored from Trading_Terminal's backend.
"""

from flask import Blueprint, jsonify
from datetime import datetime
import math
import logging

logger = logging.getLogger(__name__)
options_bp = Blueprint("options", __name__)

TICKER_MAP = {
    "SPY": "SPY", "SPX": "^GSPC", "QQQ": "QQQ", "IWM": "IWM",
    "VIX": "^VIX", "ES": "ES=F", "GLD": "GLD", "DIA": "DIA",
}


def _get_yf_ticker(ticker: str) -> str:
    return TICKER_MAP.get(ticker.upper(), ticker.upper())


def _safe_float(val, default=0):
    try:
        return default if (val is None or math.isnan(val)) else float(val)
    except (TypeError, ValueError):
        return default


def _safe_int(val, default=0):
    try:
        return default if (val is None or math.isnan(val)) else int(val)
    except (TypeError, ValueError):
        return default


@options_bp.route("/api/options/<ticker>")
def options_chain(ticker):
    """Get full options chain for a ticker."""
    try:
        import yfinance as yf

        yf_ticker = _get_yf_ticker(ticker)
        t = yf.Ticker(yf_ticker)
        expirations = t.options

        if not expirations:
            return jsonify({"ticker": ticker, "error": "No options data", "expirations": []})

        chains = []
        for exp_date in expirations[:4]:
            try:
                chain = t.option_chain(exp_date)
                calls_data = [
                    {
                        "strike": float(row["strike"]),
                        "lastPrice": _safe_float(row["lastPrice"]),
                        "bid": _safe_float(row["bid"]),
                        "ask": _safe_float(row["ask"]),
                        "volume": _safe_int(row["volume"]),
                        "openInterest": _safe_int(row["openInterest"]),
                        "impliedVolatility": _safe_float(row["impliedVolatility"]),
                    }
                    for _, row in chain.calls.iterrows()
                ]
                puts_data = [
                    {
                        "strike": float(row["strike"]),
                        "lastPrice": _safe_float(row["lastPrice"]),
                        "bid": _safe_float(row["bid"]),
                        "ask": _safe_float(row["ask"]),
                        "volume": _safe_int(row["volume"]),
                        "openInterest": _safe_int(row["openInterest"]),
                        "impliedVolatility": _safe_float(row["impliedVolatility"]),
                    }
                    for _, row in chain.puts.iterrows()
                ]
                chains.append({
                    "expiration": exp_date,
                    "dte": (datetime.strptime(exp_date, "%Y-%m-%d") - datetime.now()).days,
                    "calls": calls_data,
                    "puts": puts_data,
                })
            except Exception:
                continue

        return jsonify({
            "ticker": ticker,
            "expirations": expirations[:8],
            "chains": chains,
            "timestamp": datetime.now().isoformat(),
            "source": "yfinance",
        })
    except Exception as e:
        logger.error(f"Options error for {ticker}: {e}")
        return jsonify({"error": str(e), "ticker": ticker}), 500


@options_bp.route("/api/iv-surface/<ticker>")
def iv_surface(ticker):
    """Get IV surface data from real options chains."""
    try:
        import yfinance as yf

        yf_ticker = _get_yf_ticker(ticker)
        t = yf.Ticker(yf_ticker)
        expirations = t.options
        if not expirations:
            return jsonify({"ticker": ticker, "error": "No options data", "surface": []})

        price = getattr(t.fast_info, "last_price", None)
        if not price:
            hist = t.history(period="1d")
            price = float(hist["Close"].iloc[-1]) if not hist.empty else None
        if not price:
            return jsonify({"ticker": ticker, "error": "Cannot determine spot price", "surface": []})

        surface = []
        for exp_date in expirations[:6]:
            try:
                dte = (datetime.strptime(exp_date, "%Y-%m-%d") - datetime.now()).days
                if dte <= 0:
                    continue
                chain = t.option_chain(exp_date)
                for _, row in chain.calls.iterrows():
                    strike = float(row["strike"])
                    iv = _safe_float(row["impliedVolatility"])
                    moneyness = strike / price
                    if 0.8 <= moneyness <= 1.2 and iv > 0:
                        surface.append({"strike": strike, "moneyness": round(moneyness, 4), "dte": dte, "iv": round(iv, 4), "type": "call"})
                for _, row in chain.puts.iterrows():
                    strike = float(row["strike"])
                    iv = _safe_float(row["impliedVolatility"])
                    moneyness = strike / price
                    if 0.8 <= moneyness <= 1.2 and iv > 0:
                        surface.append({"strike": strike, "moneyness": round(moneyness, 4), "dte": dte, "iv": round(iv, 4), "type": "put"})
            except Exception:
                continue

        return jsonify({"ticker": ticker, "spot": price, "surface": surface, "timestamp": datetime.now().isoformat(), "source": "yfinance"})
    except Exception as e:
        logger.error(f"IV surface error for {ticker}: {e}")
        return jsonify({"error": str(e), "ticker": ticker}), 500


@options_bp.route("/api/term-structure/<ticker>")
def term_structure(ticker):
    """Get ATM IV across expirations (term structure)."""
    try:
        import yfinance as yf

        yf_ticker = _get_yf_ticker(ticker)
        t = yf.Ticker(yf_ticker)
        expirations = t.options
        if not expirations:
            return jsonify({"ticker": ticker, "error": "No options data", "term_structure": {}})

        price = getattr(t.fast_info, "last_price", None)
        if not price:
            hist = t.history(period="1d")
            price = float(hist["Close"].iloc[-1]) if not hist.empty else None
        if not price:
            return jsonify({"ticker": ticker, "error": "Cannot determine spot price", "term_structure": {}})

        raw_term = []
        for exp_date in expirations[:8]:
            try:
                dte = (datetime.strptime(exp_date, "%Y-%m-%d") - datetime.now()).days
                if dte <= 0:
                    continue
                chain = t.option_chain(exp_date)
                calls = chain.calls
                calls_valid = calls[calls["impliedVolatility"].notna() & (calls["impliedVolatility"] > 0)]
                if calls_valid.empty:
                    continue
                atm_idx = (calls_valid["strike"] - price).abs().idxmin()
                atm_iv = float(calls_valid.loc[atm_idx, "impliedVolatility"])
                raw_term.append({"expiration": exp_date, "dte": dte, "atm_iv": round(atm_iv, 4), "atm_strike": float(calls_valid.loc[atm_idx, "strike"])})
            except Exception:
                continue

        term_map = {}
        for entry in raw_term:
            dte = entry["dte"]
            if dte <= 10 and "1W" not in term_map:
                term_map["1W"] = entry["atm_iv"]
            elif 10 < dte <= 20 and "2W" not in term_map:
                term_map["2W"] = entry["atm_iv"]
            elif 20 < dte <= 45 and "1M" not in term_map:
                term_map["1M"] = entry["atm_iv"]
            elif 45 < dte <= 75 and "2M" not in term_map:
                term_map["2M"] = entry["atm_iv"]
            elif 75 < dte <= 120 and "3M" not in term_map:
                term_map["3M"] = entry["atm_iv"]
            elif dte > 120 and "6M" not in term_map:
                term_map["6M"] = entry["atm_iv"]

        return jsonify({"ticker": ticker, "spot": price, "term_structure": term_map, "raw": raw_term, "timestamp": datetime.now().isoformat(), "source": "yfinance"})
    except Exception as e:
        logger.error(f"Term structure error for {ticker}: {e}")
        return jsonify({"error": str(e), "ticker": ticker}), 500

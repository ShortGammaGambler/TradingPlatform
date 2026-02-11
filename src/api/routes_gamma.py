"""
Gamma exposure endpoints — GEX data, data source status.
Refactored from Gamma_Backtest's unified_api.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
gamma_bp = Blueprint("gamma", __name__)


@gamma_bp.route("/api/gamma/<symbol>")
def gamma_exposure(symbol):
    """Get gamma exposure data for a symbol."""
    try:
        from src.calculators.gex_calculator import GEXCalculator

        calculator = GEXCalculator()

        # Try to get options chain data
        try:
            from src.data.data_manager import DataManager
            dm = DataManager()
            calls, puts = dm.get_options_chain(symbol)
            quote = dm.get_quote(symbol)
            spot_price = quote.get("price", 0) if quote else 0
        except Exception:
            # Return demo data if no live data available
            return jsonify({
                "symbol": symbol,
                "mode": "demo",
                "message": "Configure data sources in .env for live data",
                "timestamp": datetime.now().isoformat(),
            })

        if calls is None or puts is None:
            return jsonify({"symbol": symbol, "error": "No options data available"}), 404

        # Calculate GEX
        result = calculator.calculate_gex(calls, puts, spot_price)

        return jsonify({
            "symbol": symbol,
            "spot_price": spot_price,
            "total_gex": result.get("total_gex", 0),
            "call_gex": result.get("call_gex", 0),
            "put_gex": result.get("put_gex", 0),
            "gamma_flip": result.get("gamma_flip", 0),
            "strikes": result.get("strikes", []),
            "timestamp": datetime.now().isoformat(),
            "source": "calculated",
        })
    except Exception as e:
        logger.error(f"Gamma exposure error for {symbol}: {e}")
        return jsonify({"error": str(e), "symbol": symbol}), 500


@gamma_bp.route("/api/data/status")
def data_status():
    """Check which data sources are configured and available."""
    from src.config.config import get_config
    config = get_config()

    sources = {
        "schwab": {
            "configured": bool(config.schwab_app_key),
            "status": "ready" if config.schwab_app_key else "not_configured",
        },
        "polygon": {
            "configured": bool(config.polygon_api_key),
            "status": "ready" if config.polygon_api_key else "not_configured",
        },
        "spotgamma": {
            "configured": bool(config.spotgamma_api_key),
            "status": "ready" if config.spotgamma_api_key else "not_configured",
        },
        "yfinance": {
            "configured": True,
            "status": "ready",
        },
    }

    return jsonify({
        "sources": sources,
        "timestamp": datetime.now().isoformat(),
    })

"""
Backtest endpoints — run backtests, list strategies, retrieve results.
Refactored from Gamma_Backtest's unified_api.
"""

from flask import Blueprint, jsonify, request
from datetime import datetime, timedelta
import logging
import uuid

logger = logging.getLogger(__name__)
backtest_bp = Blueprint("backtest", __name__)

# In-memory results store (swap for DB in production)
_backtest_results = {}


@backtest_bp.route("/api/backtest/strategies")
def list_strategies():
    """List available backtest strategies."""
    try:
        from src.strategies.gamma_strategies import STRATEGY_DESCRIPTIONS
        return jsonify({
            "strategies": STRATEGY_DESCRIPTIONS,
            "timestamp": datetime.now().isoformat(),
        })
    except ImportError:
        return jsonify({
            "strategies": {
                "gamma_flip_breakout": "Trade breakouts through the gamma flip level",
                "deep_negative_gamma_reversion": "Mean reversion in deep negative gamma regimes",
                "positive_gamma_range_fade": "Fade moves in positive gamma (mean-reverting) environments",
                "gex_momentum": "Follow GEX momentum when regime is strong",
            },
            "timestamp": datetime.now().isoformat(),
        })


@backtest_bp.route("/api/backtest/run", methods=["POST"])
def run_backtest():
    """Execute a backtest with given parameters."""
    try:
        from src.backtesting.backtest_engine import BacktestEngine, GammaRegime, MarketState

        params = request.get_json() or {}
        strategy_name = params.get("strategy", "gamma_flip_breakout")
        symbol = params.get("symbol", "SPY")
        days = params.get("days", 60)
        initial_capital = params.get("initial_capital", 100000)

        # Create backtest engine
        engine = BacktestEngine(initial_capital=initial_capital)

        # Get strategy function
        from src.strategies.gamma_strategies import (
            gamma_flip_breakout,
            deep_negative_gamma_reversion,
            positive_gamma_range_fade,
            gex_momentum,
        )
        strategy_map = {
            "gamma_flip_breakout": gamma_flip_breakout,
            "deep_negative_gamma_reversion": deep_negative_gamma_reversion,
            "positive_gamma_range_fade": positive_gamma_range_fade,
            "gex_momentum": gex_momentum,
        }
        strategy_fn = strategy_map.get(strategy_name)
        if not strategy_fn:
            return jsonify({"error": f"Unknown strategy: {strategy_name}"}), 400

        # Run backtest
        results = engine.run(strategy_fn, days=days)

        # Store results
        result_id = str(uuid.uuid4())[:8]
        _backtest_results[result_id] = {
            "id": result_id,
            "strategy": strategy_name,
            "symbol": symbol,
            "days": days,
            "initial_capital": initial_capital,
            "results": results,
            "timestamp": datetime.now().isoformat(),
        }

        return jsonify({
            "id": result_id,
            "strategy": strategy_name,
            "status": "completed",
            "results": results,
            "timestamp": datetime.now().isoformat(),
        })
    except Exception as e:
        logger.error(f"Backtest error: {e}")
        return jsonify({"error": str(e)}), 500


@backtest_bp.route("/api/backtest/results/<result_id>")
def get_results(result_id):
    """Retrieve stored backtest results."""
    result = _backtest_results.get(result_id)
    if not result:
        return jsonify({"error": "Result not found"}), 404
    return jsonify(result)

"""
Unified Gamma Trading Platform API
Combines dashboard gamma data with backtesting capabilities.

Endpoints:
    /api/data/status          - Data source status
    /api/data/configure       - Configure Schwab credentials
    /api/gamma/<symbol>       - Gamma exposure data
    /api/backtest/strategies  - List available strategies
    /api/backtest/run         - Execute backtest
    /api/backtest/results/<id> - Get backtest results
    /api/risk/assess          - Assess portfolio risk

Usage:
    python unified_api.py
    # API runs at http://localhost:5000
"""

from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional
import json
import logging
import random
import math

from flask import Flask, jsonify, request
from flask_cors import CORS

from src.backtesting.backtest_engine import BacktestEngine, GammaRegime, MarketState, Trade
from src.analytics.risk_manager import RiskManager, PositionGreeks, RiskLevel
from src.strategies.gamma_strategies import (
    gamma_flip_breakout,
    deep_negative_gamma_reversion,
    positive_gamma_range_fade,
    gex_momentum,
    STRATEGY_DESCRIPTIONS
)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# =============================================================================
# GLOBAL STATE
# =============================================================================

data_loader = TOSDataLoader()
backtest_results_cache: Dict[str, Dict] = {}
data_source_mode = "simulated"  # "simulated" or "live"


# =============================================================================
# SIMULATED DATA GENERATOR
# =============================================================================

class GammaDataSimulator:
    """Generate realistic simulated gamma data for testing."""

    def __init__(self, base_price: float = 5100.0):
        self.base_price = base_price
        self.gamma_flip = base_price * 0.998
        self.tick = 0

    def get_current_gex(self, symbol: str = "SPX") -> Dict:
        """Generate simulated gamma exposure data."""
        self.tick += 1

        # Price oscillates around base
        price_offset = math.sin(self.tick * 0.1) * 50 + random.uniform(-10, 10)
        spot_price = self.base_price + price_offset

        # Gamma flip moves slowly
        self.gamma_flip += random.uniform(-2, 2)

        # Distance determines regime
        distance = (spot_price - self.gamma_flip) / self.gamma_flip

        if distance > 0.008:
            environment = "deep_positive"
        elif distance > 0.003:
            environment = "positive"
        elif distance > -0.003:
            environment = "neutral"
        elif distance > -0.008:
            environment = "negative"
        else:
            environment = "deep_negative"

        # GEX based on distance
        total_gex = random.uniform(-2, 8) + distance * 500
        call_gex = max(0, total_gex * 0.7 + random.uniform(-1, 1))
        put_gex = total_gex - call_gex

        # IV rank cycles
        iv_rank = 50 + 30 * math.sin(self.tick * 0.05) + random.uniform(-5, 5)
        iv_rank = max(0, min(100, iv_rank))

        return {
            "symbol": symbol,
            "timestamp": datetime.now().isoformat(),
            "spot_price": round(spot_price, 2),
            "gamma_flip": round(self.gamma_flip, 2),
            "total_gex": round(total_gex, 2),
            "call_gex": round(call_gex, 2),
            "put_gex": round(put_gex, 2),
            "environment": environment,
            "distance_to_flip": round(distance * 100, 3),
            "iv_rank": round(iv_rank, 1),
            "implied_vol": round(18 + iv_rank * 0.1, 1),
            "realized_vol": round(16 + random.uniform(-2, 2), 1),
            "call_wall": round(self.gamma_flip + 100, 0),
            "put_wall": round(self.gamma_flip - 100, 0),
        }


gamma_sim = GammaDataSimulator()


# =============================================================================
# DATA SOURCE ENDPOINTS
# =============================================================================

@app.route('/api/data/status', methods=['GET'])
def get_data_status():
    """Get current data source status."""
    schwab_configured = hasattr(data_loader, 'schwab') and data_loader.schwab is not None
    schwab_authenticated = False

    if schwab_configured:
        schwab_authenticated = data_loader.schwab.auth.is_authenticated

    return jsonify({
        "success": True,
        "data": {
            "mode": data_source_mode,
            "schwab_configured": schwab_configured,
            "schwab_authenticated": schwab_authenticated,
            "available_modes": ["simulated", "live"]
        }
    })


@app.route('/api/data/configure', methods=['POST'])
def configure_data_source():
    """Configure data source (Schwab API or simulated)."""
    global data_source_mode

    body = request.json or {}
    mode = body.get('mode', 'simulated')

    if mode == 'live':
        client_id = body.get('client_id')
        client_secret = body.get('client_secret')

        if not client_id or not client_secret:
            return jsonify({
                "success": False,
                "error": "client_id and client_secret required for live mode"
            }), 400

        try:
            data_loader.setup_schwab_api(client_id, client_secret)
            data_source_mode = "live"
            logger.info("Switched to live data mode")
        except Exception as e:
            logger.error(f"Failed to configure Schwab API: {e}")
            return jsonify({
                "success": False,
                "error": str(e)
            }), 500
    else:
        data_source_mode = "simulated"
        logger.info("Switched to simulated data mode")

    return jsonify({
        "success": True,
        "data": {"mode": data_source_mode}
    })


# =============================================================================
# GAMMA DATA ENDPOINTS
# =============================================================================

@app.route('/api/gamma/<symbol>', methods=['GET'])
def get_gamma_data(symbol: str):
    """
    Get gamma exposure data for a symbol.

    Uses live Schwab data if configured, otherwise simulated data.
    """
    try:
        if data_source_mode == "live" and hasattr(data_loader, 'schwab'):
            # Use live Schwab data
            gamma_data = data_loader.fetch_live_gamma_data(symbol.upper())

            data = {
                "symbol": symbol.upper(),
                "timestamp": gamma_data['timestamp'].isoformat(),
                "spot_price": gamma_data['spot_price'],
                "gamma_flip": gamma_data['gamma_flip'],
                "total_gex": gamma_data['total_gex'],
                "call_gex": gamma_data['call_gex'],
                "put_gex": gamma_data['put_gex'],
                "environment": _classify_environment(gamma_data),
                "distance_to_flip": (gamma_data['spot_price'] - gamma_data['gamma_flip']) / gamma_data['gamma_flip'] * 100,
                "iv_rank": gamma_data.get('iv_rank', 50),
                "implied_vol": gamma_data.get('implied_vol', 20),
                "realized_vol": gamma_data.get('realized_vol', 18),
            }
        else:
            # Use simulator
            data = gamma_sim.get_current_gex(symbol.upper())

        return jsonify({"success": True, "data": data})

    except Exception as e:
        logger.error(f"Error fetching gamma data: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


def _classify_environment(gamma_data: Dict) -> str:
    """Classify gamma environment from raw data."""
    distance = (gamma_data['spot_price'] - gamma_data['gamma_flip']) / gamma_data['gamma_flip']

    if distance > 0.008:
        return "deep_positive"
    elif distance > 0.003:
        return "positive"
    elif distance > -0.003:
        return "neutral"
    elif distance > -0.008:
        return "negative"
    else:
        return "deep_negative"


# =============================================================================
# BACKTEST ENDPOINTS
# =============================================================================

@app.route('/api/backtest/strategies', methods=['GET'])
def list_strategies():
    """List available backtesting strategies with descriptions."""
    return jsonify({
        "success": True,
        "data": STRATEGY_DESCRIPTIONS
    })


@app.route('/api/backtest/run', methods=['POST'])
def run_backtest():
    """
    Run a backtest with specified parameters.

    Request body:
    {
        "strategies": ["breakout", "reversion"],  // or ["all"]
        "start_date": "2024-01-01",
        "end_date": "2024-12-31",
        "initial_capital": 100000,
        "symbol": "SPY",
        "risk_settings": {
            "max_risk_per_trade": 0.02,
            "max_portfolio_risk": 0.20,
            "enable_risk_checks": true
        }
    }
    """
    try:
        body = request.json or {}

        strategies_requested = body.get('strategies', ['all'])
        start_date = body.get('start_date', '2024-01-01')
        end_date = body.get('end_date', '2024-12-31')
        initial_capital = body.get('initial_capital', 100000)
        symbol = body.get('symbol', 'SPY')
        risk_settings = body.get('risk_settings', {})

        # Map strategy names to functions
        strategy_map = {
            'breakout': gamma_flip_breakout,
            'reversion': deep_negative_gamma_reversion,
            'fade': positive_gamma_range_fade,
            'momentum': gex_momentum,
        }

        if 'all' in strategies_requested:
            strategies = list(strategy_map.values())
            strategy_names = list(strategy_map.keys())
        else:
            strategies = [strategy_map[s] for s in strategies_requested if s in strategy_map]
            strategy_names = [s for s in strategies_requested if s in strategy_map]

        if not strategies:
            return jsonify({
                "success": False,
                "error": f"No valid strategies specified. Available: {list(strategy_map.keys())}"
            }), 400

        # Generate sample data (live data would require Schwab API + historical gamma)
        price_data, gamma_data = generate_sample_data(start_date, end_date)

        # Configure risk manager
        risk_manager = RiskManager(
            account_value=initial_capital,
            max_risk_per_trade=risk_settings.get('max_risk_per_trade', 0.02),
            max_portfolio_risk=risk_settings.get('max_portfolio_risk', 0.20)
        )

        # Create and run engine
        engine = BacktestEngine(
            initial_capital=initial_capital,
            risk_manager=risk_manager,
            enable_risk_checks=risk_settings.get('enable_risk_checks', True),
            slippage_bps=risk_settings.get('slippage_bps', 5.0),
            commission_per_contract=risk_settings.get('commission_per_contract', 0.65)
        )
        engine.load_data(price_data, gamma_data)

        for strategy in strategies:
            engine.add_strategy(strategy)

        results = engine.run()

        # Prepare response
        backtest_id = f"bt_{datetime.now().strftime('%Y%m%d_%H%M%S')}"

        response_data = {
            "backtest_id": backtest_id,
            "parameters": {
                "strategies": strategy_names,
                "start_date": start_date,
                "end_date": end_date,
                "initial_capital": initial_capital,
                "symbol": symbol,
                "risk_settings": risk_settings
            },
            "metrics": results,
            "equity_curve": engine.equity_curve,
            "trades": [
                {
                    "entry_time": t.entry_time.isoformat() if t.entry_time else None,
                    "exit_time": t.exit_time.isoformat() if t.exit_time else None,
                    "instrument": t.instrument,
                    "direction": t.direction,
                    "size": t.size,
                    "entry_price": round(t.entry_price, 2),
                    "exit_price": round(t.exit_price, 2) if t.exit_price else None,
                    "pnl": round(t.pnl, 2) if t.pnl else None,
                    "strategy": t.strategy,
                    "exit_reason": t.exit_reason
                }
                for t in engine.portfolio.closed_trades
            ]
        }

        # Cache results
        backtest_results_cache[backtest_id] = response_data

        logger.info(f"Backtest {backtest_id} completed: {results['total_return_pct']:.1f}% return, "
                   f"{results['total_trades']} trades")

        return jsonify({
            "success": True,
            "data": response_data
        })

    except Exception as e:
        logger.error(f"Backtest error: {e}", exc_info=True)
        return jsonify({
            "success": False,
            "error": str(e)
        }), 500


@app.route('/api/backtest/results/<backtest_id>', methods=['GET'])
def get_backtest_results(backtest_id: str):
    """Get results from a previous backtest."""
    if backtest_id not in backtest_results_cache:
        return jsonify({
            "success": False,
            "error": "Backtest not found"
        }), 404

    return jsonify({
        "success": True,
        "data": backtest_results_cache[backtest_id]
    })


@app.route('/api/backtest/history', methods=['GET'])
def get_backtest_history():
    """Get list of recent backtests."""
    history = [
        {
            "backtest_id": bt_id,
            "strategies": data["parameters"]["strategies"],
            "total_return": data["metrics"]["total_return_pct"],
            "net_return": data["metrics"]["net_return_pct"],
            "sharpe": data["metrics"]["sharpe_ratio"],
            "trades": data["metrics"]["total_trades"]
        }
        for bt_id, data in backtest_results_cache.items()
    ]

    return jsonify({
        "success": True,
        "data": history
    })


# =============================================================================
# RISK ENDPOINTS
# =============================================================================

@app.route('/api/risk/assess', methods=['POST'])
def assess_risk():
    """
    Assess risk for a proposed portfolio.

    Request body:
    {
        "positions": [
            {"symbol": "SPY_C_500", "delta": 50, "gamma": 0.05, ...}
        ],
        "account_value": 100000
    }
    """
    try:
        body = request.json or {}
        positions = body.get('positions', [])
        account_value = body.get('account_value', 100000)

        rm = RiskManager(account_value=account_value)

        for pos in positions:
            rm.add_position(PositionGreeks(
                symbol=pos.get('symbol', 'UNKNOWN'),
                delta=pos.get('delta', 0),
                gamma=pos.get('gamma', 0),
                theta=pos.get('theta', 0),
                vega=pos.get('vega', 0),
                notional=pos.get('notional', 0),
                contracts=pos.get('contracts', 0)
            ))

        risk = rm.assess_portfolio_risk()
        suggestions = rm.suggest_hedges(risk)

        return jsonify({
            "success": True,
            "data": {
                "risk_level": risk.risk_level.value,
                "net_delta": risk.net_delta,
                "net_gamma": risk.net_gamma,
                "net_theta": risk.net_theta,
                "net_vega": risk.net_vega,
                "largest_position_pct": risk.largest_position_pct,
                "warnings": risk.warnings,
                "hedge_suggestions": suggestions
            }
        })

    except Exception as e:
        logger.error(f"Risk assessment error: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


# =============================================================================
# HEALTH CHECK
# =============================================================================

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.now().isoformat(),
        "data_mode": data_source_mode
    })


# =============================================================================
# MAIN
# =============================================================================

if __name__ == '__main__':
    print("=" * 60)
    print("Gamma Trading Platform - Unified API")
    print("=" * 60)
    print("\nEndpoints:")
    print("  GET  /api/health              - Health check")
    print("  GET  /api/data/status         - Data source status")
    print("  POST /api/data/configure      - Configure data source")
    print("  GET  /api/gamma/<symbol>      - Gamma exposure data")
    print("  GET  /api/backtest/strategies - List strategies")
    print("  POST /api/backtest/run        - Run backtest")
    print("  GET  /api/backtest/results/<id> - Get results")
    print("  GET  /api/backtest/history    - Recent backtests")
    print("  POST /api/risk/assess         - Assess portfolio risk")
    print("\nStarting server on http://localhost:5000")
    print("=" * 60)

    app.run(debug=True, host='0.0.0.0', port=5000)

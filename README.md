# Unified Trading Platform

Institutional-grade options and futures trading platform with real-time data, Greeks analytics, gamma exposure analysis, ML-powered predictions, and automated strategy execution.

Consolidated from 235 files across 5 codebases into one unified Python project.

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Configure API keys
cp .env.example .env   # Edit with your keys

# Launch the Streamlit dashboard
python run_ui.py

# Or launch the Flask API server
python run_api.py
```

## Features

**Options Analytics**
- Full Black-Scholes Greeks (delta, gamma, vega, theta, rho, vanna, charm, volga)
- Gamma exposure (GEX) calculation and visualization
- Vanna/Charm flow analysis
- VIX term structure (contango/backwardation detection)
- 3D implied volatility surface

**Market Intelligence**
- Options flow scanner (sweep, block, and unusual volume detection)
- Market regime classification
- Dealer positioning and dark pool (DIX) tracking
- SEC 13F/SC 13D filing parser
- Earnings calendar integration

**Trading Strategies**
- 4 gamma-based strategies (flip breakout, mean reversion, range fade, ensemble)
- 15+ strategy recommendations with confidence scoring
- Kelly criterion position sizing
- Volatility arbitrage (IV vs HV)
- Automatic hedging

**ML & Backtesting**
- ML price predictor with feature engineering
- Multi-factor regime classifier
- Gamma backtest engine
- Options strategy backtester with full portfolio tracking

**Data Sources**
- Schwab API (OAuth2 with circuit breaker and rate limiting)
- Polygon.io (REST + WebSocket)
- yfinance (free fallback)
- CBOE data scraper
- SpotGamma GEX API
- Unified DataManager with automatic failover: Schwab -> Polygon -> yfinance

**Alerts & Notifications**
- 4-channel alert system: desktop, email (SMTP), SMS (Twilio), Discord webhook
- Configurable alert priorities and thresholds

## Architecture

```
src/
├── config/         Configuration (dataclass-based, .env support)
├── core/           Alert system, position sizer (Kelly), market regime, strategy engine
├── calculators/    Black-Scholes Greeks, Vanna/Charm, VIX analyzer, gamma exposure
├── data/           Schwab connector, Polygon.io client, yfinance, CBOE, realtime feed
├── analytics/      Risk manager, volatility arbitrage, DIX tracker, trade journal
├── strategies/     Gamma strategies, options flow scanner
├── ml/             ML price predictor, regime classifier
├── backtesting/    Gamma backtest engine, options backtester
├── institutional/  Dealer positioning, SEC filings, alt data, sovereign wealth funds
├── hedging/        Auto-hedger
├── api/            Flask REST API (quotes, options, gamma, backtest endpoints)
└── ui/             Streamlit dashboard, Plotly charts, 3D IV surface
frontend/           HTML/JS trading terminals (Chart.js, Three.js)
thinkscript/        ThinkOrSwim studies, scans, and watchlist columns
```

## API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/api/health` | Health check |
| GET | `/api/quote/<ticker>` | Real-time quote |
| GET | `/api/options/<ticker>` | Options chain |
| GET | `/api/iv-surface/<ticker>` | Implied volatility surface |
| GET | `/api/term-structure/<ticker>` | Term structure |
| GET | `/api/gamma/<symbol>` | Gamma exposure |
| POST | `/api/backtest/run` | Run backtest |
| GET | `/api/backtest/strategies` | List strategies |
| GET | `/api/backtest/results/<id>` | Backtest results |

## API Keys

| Service | Required | Notes |
|---------|----------|-------|
| Schwab | Optional | Live trading data (OAuth2) |
| Polygon.io | Optional | Real-time and historical data |
| SpotGamma | Optional | GEX data |
| FRED | Optional | Macro/economic data |
| yfinance | Built-in | Always available (free) |

The platform works out of the box with yfinance. Add additional API keys for premium data sources.

## Tests

```bash
pytest tests/ -v
```

## Requirements

- Python 3.10+
- See `requirements.txt` for full dependency list

## Documentation

See [MASTER_INDEX.md](MASTER_INDEX.md) for the complete file-by-file source mapping and migration details.

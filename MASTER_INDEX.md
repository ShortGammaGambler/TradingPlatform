# Unified Trading Platform — Master Index

Institutional-grade options & futures trading platform.
Consolidated from 235 files across 5 codebases into one unified project.

## Quick Start

```bash
pip install -r requirements.txt
cp .env.example .env  # Fill in API keys
python run_ui.py      # Streamlit dashboard
python run_api.py     # Flask API server
```

## Architecture

```
src/
├── config/         Central configuration (dataclass-based, .env support)
├── core/           Alert system (4-channel), position sizer (Kelly), market regime, strategy engine
├── calculators/    Black-Scholes Greeks, Vanna/Charm, VIX analyzer, gamma exposure
├── data/           Schwab OAuth connector, Polygon.io client, yfinance, CBOE, realtime feed
├── analytics/      Risk manager, volatility arbitrage, DIX tracker, trade journal, portfolio tracker
├── strategies/     Gamma strategies (flip breakout, reversion, range fade), options flow scanner
├── ml/             ML price predictor, regime classifier
├── backtesting/    Gamma backtest engine, options backtester
├── institutional/  Dealer positioning, SEC filing parser, alt data, sovereign wealth fund monitor
├── hedging/        Auto-hedger
├── api/            Flask app with Blueprint routes (quotes, options, gamma, backtest)
└── ui/             Streamlit dashboard (1,683-line trading platform), plots, advanced plots
```

## Source Mapping

### src/config/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| config.py | Trading_Platform | 228 | Config dataclasses + singleton + Schwab OAuth fields |

### src/core/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| alert_system.py | Trading_Platform | 569 | 4-channel alerts (desktop/email/SMS/Discord), AlertLevel alias added |
| position_sizer.py | Trading_Platform | ~400 | Kelly criterion + from_config() factory |
| market_regime.py | GEX_Dashboard | ~340 | MarketRegimeDetector, MarketEnvironment |
| strategy_engine.py | GEX_Dashboard | ~520 | 15+ strategy recommendations with confidence scoring |

### src/calculators/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| greeks.py | Old_Trading_ML | 130 | Full Black-Scholes: delta, gamma, vega, theta, rho, vanna, charm, volga |
| vanna_charm.py | Old_Trading_ML | 177 | Vanna/Charm/Volga exposure by strike |
| vix_analyzer.py | Old_Trading_ML | 102 | VIX term structure, contango/backwardation |
| gamma_exposure.py | Old_Trading_ML | ~150 | GEX from options chain data |
| gex_calculator.py | Gamma_Backtest | ~400 | Production GEX calculator |

### src/data/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| schwab_connector.py | Gamma_Backtest | ~1100 | Circuit breaker, rate limiting, OAuth, from_config() |
| polygon_client.py | NEW | ~280 | REST + WebSocket client for Polygon.io |
| data_manager.py | NEW | ~170 | Unified facade: Schwab → Polygon → yfinance fallback |
| yahoo_options.py | Old_Trading_ML | ~80 | yfinance options fetcher |
| cboe_scraper.py | Old_Trading_ML | ~90 | CBOE data scraper |
| realtime_feed.py | GEX_Dashboard | ~360 | Real-time data feed framework |
| api_data.py | GEX_Dashboard | ~100 | SpotGamma API data fetcher |

### src/analytics/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| risk_manager.py | Gamma_Backtest | ~500 | Portfolio risk, Greeks tracking |
| vol_arb.py | GEX_Dashboard | ~290 | IV vs HV volatility arbitrage |
| dix_tracker.py | GEX_Dashboard | ~440 | Dark Index tracking |
| trade_journal.py | GEX_Dashboard | ~480 | Trade tracking and journaling |
| portfolio_tracker.py | GEX_Dashboard | ~400 | Portfolio monitoring |
| earnings_calendar.py | GEX_Dashboard | ~390 | Earnings event tracking |

### src/strategies/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| gamma_strategies.py | Gamma_Backtest | ~470 | 4 gamma-based strategies + ensemble |
| options_flow_scanner.py | NEW (was 0 bytes) | ~300 | Sweep/block/V-OI detection + Plotly visualization |

### src/ml/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| ml_predictor.py | GEX_Dashboard | ~470 | ML-based price prediction |
| regime_classifier.py | Trading_Platform | ~490 | Multi-factor regime classification |

### src/backtesting/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| backtest_engine.py | Gamma_Backtest | ~660 | Core engine with MarketState/Trade/Portfolio models |
| backtester.py | GEX_Dashboard | ~580 | Options strategy backtester |

### src/institutional/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| dealer_positioning.py | Trading_Platform | ~560 | Dealer flow monitoring |
| sec_filing_parser.py | Trading_Platform | ~500 | SEC 13F/SC 13D parsing |
| alt_data.py | Trading_Platform | ~420 | Alternative data integration |
| swf_monitor.py | Trading_Platform | ~390 | Sovereign wealth fund tracking |

### src/hedging/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| auto_hedger.py | GEX_Dashboard | ~440 | Automatic hedging strategies |

### src/api/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| app.py | NEW | 30 | Flask factory with Blueprint registration |
| routes_quotes.py | Trading_Terminal | ~70 | GET /api/quote, /api/health |
| routes_options.py | Trading_Terminal | ~160 | GET /api/options, /api/iv-surface, /api/term-structure |
| routes_gamma.py | Gamma_Backtest | ~70 | GET /api/gamma, /api/data/status |
| routes_backtest.py | Gamma_Backtest | ~100 | POST /api/backtest/run, GET strategies & results |

### src/ui/
| File | Source | Lines | Notes |
|------|--------|-------|-------|
| trading_platform.py | GEX_Dashboard | 1,683 | Core Streamlit UI — 13 imports rewritten |
| plots.py | GEX_Dashboard | ~190 | Plotly GEX charts |
| advanced_plots.py | GEX_Dashboard | ~480 | 3D IV surface, risk metrics |
| position_sizing.py | GEX_Dashboard | ~320 | Kelly UI integration |

### frontend/
| File | Source | Notes |
|------|--------|-------|
| index.html | Trading_Terminal | Full trading terminal (Chart.js, Three.js 3D IV surface) |
| trading-terminal.html | Trading_Terminal | Alternative terminal layout |
| professional_trading_terminal.html | Trading_Terminal | Professional version |

### thinkscript/
| File | Notes |
|------|-------|
| studies/Confluence_Dashboard.ts | Multi-factor confluence indicator |
| studies/GammaRegimeIndicator.ts | Gamma regime classification |
| studies/MTFMomentumDashboard.ts | Multi-timeframe momentum |
| scans/Equity_EventVol_Scanner.ts | Event volatility scanner |
| scans/ETF_GammaFlow_Scanner.ts | ETF gamma flow scanner |
| scans/Index_VRP_Scanner.ts | Variance risk premium scanner |
| columns/WatchlistColumnsPackage.ts | Custom watchlist columns |

## Resolved Duplicates

| File | Copies Found | Canonical Source |
|------|-------------|-----------------|
| schwab_connector.py | 3 (Gamma_Backtest, Python_Scripts, Strategy_Docs) | Gamma_Backtest (45.5KB, most complete) |
| gex_calculator.py | 3 (Gamma_Backtest, Python_Scripts, Trading_Monitor) | Gamma_Backtest (analytics/) |
| enhanced-spy-analysis.py | 3 (Python_Scripts, SPY_Dashboard, Strategy_Docs) | Archived (not migrated) |
| GrandPappy_Trading_Platform.txt | 2 (Strategy_Docs, Trading_Monitor) | docs/ (single copy) |
| Old_Trading_ML/NewCode/gex_dashboard/ | Full duplicate of GEX_Dashboard/ | GEX_Dashboard/ (canonical) |

## Interface Aliases

| Alias | Points To | Reason |
|-------|----------|--------|
| `AlertManager` | `AlertSystem` | Gamma_Backtest used AlertManager |
| `AlertLevel` | `AlertPriority` | Gamma_Backtest used AlertLevel |
| `KellyPositionSizer` | `PositionSizer` | GEX_Dashboard used KellyPositionSizer |

## API Keys Required

| Service | Env Var | Required? |
|---------|---------|-----------|
| Schwab | SCHWAB_APP_KEY + SCHWAB_APP_SECRET | For live trading data |
| Polygon.io | POLYGON_API_KEY | For real-time/historical data |
| SpotGamma | SPOTGAMMA_API_KEY | For GEX data API |
| FRED | FRED_API_KEY | For macro/economic data |
| yfinance | None | Always available (free) |

# 🤖 AGENTS.md — AI Collaboration Guide for TradingPlatform

This file documents how AI agents and tools are used in this project.
If you are an AI agent working in this repo, read this first.

---

## 🧠 How We Use AI Here

TradingPlatform is the core infrastructure layer for the QuantumEdge Alpha trading stack. AI is used throughout — from writing data connectors to optimizing signal logic.

### Primary AI Tools
| Tool | Role |
|---|---|
| **Claude (Anthropic)** | Code generation, architecture, debugging, strategy research |
| **Claude in Chrome** | Automation, research, GitHub workflow |
| **Cowork Mode** | File orchestration, multi-step task execution |

---

## 📐 Agent Guidelines

### Code Style
- Python 3.10+, type hints everywhere, docstrings on all public functions
- Use `pandas` for tabular data, `numpy` for math, `scipy` for stats
- All market data operations must handle missing data and exchange holidays gracefully
- Logging over print statements — use the `logging` module

### Commit Convention
```
feat:   new feature or capability
fix:    bug fix
data:   data pipeline changes
perf:   performance improvement
test:   adding or fixing tests
docs:   documentation only
refactor: code restructure, no behavior change
```

### What AI Is Trusted To Do
- ✅ Build and refactor data pipeline modules
- ✅ Write signal generation logic from specifications
- ✅ Create unit tests and test fixtures
- ✅ Generate documentation and type stubs
- ✅ Optimize pandas/numpy performance

### What Requires Human Review
- ⚠️ Order routing and execution logic
- ⚠️ Position sizing and risk limits
- ⚠️ Any broker API integration changes
- ⚠️ Schema changes to live data stores

---

## 🏃 Architecture Context

```
TradingPlatform/
├── ingestion/     # Real-time + historical data feeds
├── signals/       # Alpha signal generation & scoring
├── execution/     # Order management, broker connectors
├── backtest/      # Strategy backtesting engine
├── storage/       # Time-series DB, caching layer
├── monitoring/    # P&L tracking, alerts, dashboards
└── tests/         # Unit, integration, and simulation tests
```

---

## 🎯 Context for AI Agents

This platform feeds data and signals into QuantumEdgeAlpha strategies. Reliability and correctness are more important than cleverness. When in doubt, write boring, readable code that does exactly what it says.

The end users of this platform are retail investors who deserve the same infrastructure quality as a hedge fund. Build it that way.

---

*Built with Claude · Powered by curiosity · For the average Joe*

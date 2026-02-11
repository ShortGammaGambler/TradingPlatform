"""Launch the Flask API server."""

from src.api.app import create_app


def main():
    app = create_app()
    print("=" * 60)
    print("  Trading Platform API v1.0")
    print("  Endpoints:")
    print("    GET  /api/health")
    print("    GET  /api/quote/<ticker>")
    print("    GET  /api/options/<ticker>")
    print("    GET  /api/iv-surface/<ticker>")
    print("    GET  /api/term-structure/<ticker>")
    print("    GET  /api/gamma/<symbol>")
    print("    GET  /api/data/status")
    print("    GET  /api/backtest/strategies")
    print("    POST /api/backtest/run")
    print("    GET  /api/backtest/results/<id>")
    print("=" * 60)
    app.run(host="0.0.0.0", port=5000, debug=True)


if __name__ == "__main__":
    main()

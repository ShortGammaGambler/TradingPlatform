"""
Unified Trading Platform — Flask Application Factory
Registers all Blueprint routes from quotes, options, gamma, and backtest modules.
"""

import logging
from flask import Flask
from flask_cors import CORS


def create_app() -> Flask:
    """Create and configure the Flask application."""
    app = Flask(__name__)
    CORS(app)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )

    # Register Blueprints
    from src.api.routes_quotes import quotes_bp
    from src.api.routes_options import options_bp
    from src.api.routes_gamma import gamma_bp
    from src.api.routes_backtest import backtest_bp

    app.register_blueprint(quotes_bp)
    app.register_blueprint(options_bp)
    app.register_blueprint(gamma_bp)
    app.register_blueprint(backtest_bp)

    return app

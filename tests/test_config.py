"""Tests for centralized configuration."""

import os
import pytest
from src.config.config import Config, RiskConfig, get_config, reload_config


class TestConfigDefaults:
    def test_default_risk_values(self):
        config = Config()
        assert config.risk.max_position_size_pct == 5.0
        assert config.risk.kelly_fraction == 0.5
        assert config.risk.max_daily_loss_pct == 3.0

    def test_default_regime_thresholds(self):
        config = Config()
        assert config.regime.vix_low == 15.0
        assert config.regime.vix_high == 25.0
        assert config.regime.gamma_positive == 1.0

    def test_default_watchlist(self):
        config = Config()
        assert "SPY" in config.trading.default_watchlist
        assert "QQQ" in config.trading.default_watchlist

    def test_default_data_provider(self):
        config = Config()
        assert config.data.default_data_provider == "yfinance"

    def test_schwab_fields_exist(self):
        config = Config()
        assert hasattr(config, "schwab_app_key")
        assert hasattr(config, "schwab_app_secret")
        assert hasattr(config, "schwab_redirect_uri")
        assert hasattr(config, "schwab_token_path")


class TestConfigFromEnv:
    def test_loads_env_vars(self, monkeypatch):
        monkeypatch.setenv("POLYGON_API_KEY", "test_polygon_key")
        monkeypatch.setenv("FRED_API_KEY", "test_fred_key")
        config = Config()
        assert config.polygon_api_key == "test_polygon_key"
        assert config.fred_api_key == "test_fred_key"

    def test_schwab_env_vars(self, monkeypatch):
        monkeypatch.setenv("SCHWAB_APP_KEY", "schwab_test")
        monkeypatch.setenv("SCHWAB_APP_SECRET", "schwab_secret")
        config = Config()
        assert config.schwab_app_key == "schwab_test"
        assert config.schwab_app_secret == "schwab_secret"


class TestConfigSingleton:
    def test_get_config_returns_same_instance(self):
        reload_config()  # Reset
        c1 = get_config()
        c2 = get_config()
        assert c1 is c2

    def test_reload_creates_new_instance(self):
        c1 = get_config()
        c2 = reload_config()
        assert c1 is not c2

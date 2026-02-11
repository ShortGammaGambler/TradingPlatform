"""
MASTER CONFIGURATION
Central configuration for the trading platform
Built for: Travis @ Trav's Trader Lounge
"""

import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from pathlib import Path


@dataclass
class RiskConfig:
    """Risk management configuration"""
    # Position sizing
    max_position_size_pct: float = 5.0          # Max single position as % of portfolio
    max_portfolio_heat_pct: float = 20.0        # Max total risk at any time
    kelly_fraction: float = 0.5                  # Half-Kelly for safety
    max_correlation_exposure: float = 0.7        # Max correlation penalty threshold

    # 0DTE specific
    max_0dte_allocation_pct: float = 10.0       # Max allocation to same-day expiry
    max_0dte_single_trade_pct: float = 2.0      # Max single 0DTE trade

    # Daily limits
    max_daily_loss_pct: float = 3.0             # Stop trading for day
    max_weekly_loss_pct: float = 7.0            # Reduce size 50%
    max_monthly_loss_pct: float = 15.0          # Major review

    # Regime adjustments
    high_vol_size_multiplier: float = 0.5       # Reduce size in high vol
    negative_gamma_size_multiplier: float = 0.75


@dataclass
class AlertConfig:
    """Alert system configuration"""
    # Channels
    enable_desktop: bool = True
    enable_email: bool = True
    enable_sms: bool = False                    # Requires Twilio
    enable_discord: bool = True

    # Email settings
    smtp_server: str = ""
    smtp_port: int = 587
    email_from: str = ""
    email_to: str = ""

    # Twilio settings
    twilio_sid: str = ""
    twilio_token: str = ""
    twilio_from: str = ""
    sms_to: str = ""

    # Discord settings
    discord_webhook: str = ""

    # Alert thresholds
    pnl_alert_threshold: float = 500            # Alert on P&L changes > this
    position_alert_pct: float = 2.0             # Alert on position moves > this %


@dataclass
class RegimeConfig:
    """Market regime thresholds"""
    # VIX thresholds
    vix_very_low: float = 12.0
    vix_low: float = 15.0
    vix_normal_high: float = 20.0
    vix_high: float = 25.0
    vix_extreme: float = 35.0

    # Gamma thresholds (in billions)
    gamma_deep_positive: float = 5.0
    gamma_positive: float = 1.0
    gamma_negative: float = -1.0
    gamma_deep_negative: float = -5.0


@dataclass
class DataConfig:
    """Data source configuration"""
    # Primary data
    default_data_provider: str = "yfinance"     # yfinance, polygon, alpaca

    # Cache settings
    cache_ttl_seconds: int = 300                # 5 minute cache
    options_chain_cache_ttl: int = 60           # 1 minute for options

    # Database
    db_path: str = "./data/trading.db"
    journal_db_path: str = "./data/trade_journal.db"


@dataclass
class TradingConfig:
    """Trading parameters"""
    # Default symbols
    default_watchlist: List[str] = field(default_factory=lambda: [
        "SPY", "QQQ", "IWM", "DIA",              # Index ETFs
        "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", # Mega caps
        "META", "TSLA", "AMD", "NFLX"            # Tech
    ])

    # Futures mapping
    futures_map: Dict[str, str] = field(default_factory=lambda: {
        "SPY": "ES", "SPX": "ES",
        "QQQ": "NQ",
        "IWM": "RTY",
        "DIA": "YM",
        "GLD": "GC",
        "USO": "CL"
    })

    # Trading hours (CT)
    pre_market_start: str = "07:00"
    market_open: str = "08:30"
    market_close: str = "15:00"
    post_market_end: str = "16:00"


@dataclass
class Config:
    """Master configuration container"""
    risk: RiskConfig = field(default_factory=RiskConfig)
    alerts: AlertConfig = field(default_factory=AlertConfig)
    regime: RegimeConfig = field(default_factory=RegimeConfig)
    data: DataConfig = field(default_factory=DataConfig)
    trading: TradingConfig = field(default_factory=TradingConfig)

    # API Keys (load from environment)
    schwab_app_key: str = ""
    schwab_app_secret: str = ""
    schwab_redirect_uri: str = "https://127.0.0.1"
    schwab_token_path: str = "./schwab_tokens.json"
    fred_api_key: str = ""
    polygon_api_key: str = ""
    spotgamma_api_key: str = ""
    alpha_vantage_api_key: str = ""

    def __post_init__(self):
        """Load API keys from environment"""
        self.schwab_app_key = os.getenv("SCHWAB_APP_KEY", "")
        self.schwab_app_secret = os.getenv("SCHWAB_APP_SECRET", "")
        self.schwab_redirect_uri = os.getenv("SCHWAB_REDIRECT_URI", "https://127.0.0.1")
        self.schwab_token_path = os.getenv("SCHWAB_TOKEN_PATH", "./schwab_tokens.json")
        self.fred_api_key = os.getenv("FRED_API_KEY", "")
        self.polygon_api_key = os.getenv("POLYGON_API_KEY", "")
        self.spotgamma_api_key = os.getenv("SPOTGAMMA_API_KEY", "")
        self.alpha_vantage_api_key = os.getenv("ALPHA_VANTAGE_API_KEY", "")

    @classmethod
    def load(cls, env_file: Optional[str] = None) -> "Config":
        """Load configuration, optionally from .env file"""
        if env_file:
            from dotenv import load_dotenv
            load_dotenv(env_file)

        return cls()


# Singleton config instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get or create config singleton"""
    global _config
    if _config is None:
        _config = Config.load()
    return _config


def reload_config(env_file: Optional[str] = None) -> Config:
    """Reload configuration"""
    global _config
    _config = Config.load(env_file)
    return _config


# =============================================================================
# CONVENIENCE ACCESSORS
# =============================================================================

def get_risk_config() -> RiskConfig:
    return get_config().risk


def get_alert_config() -> AlertConfig:
    return get_config().alerts


def get_regime_thresholds() -> RegimeConfig:
    return get_config().regime


def get_watchlist() -> List[str]:
    return get_config().trading.default_watchlist


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    config = get_config()

    print("=" * 60)
    print("TRADING PLATFORM CONFIGURATION")
    print("=" * 60)

    print("\nRisk Settings:")
    print(f"  Max Position Size: {config.risk.max_position_size_pct}%")
    print(f"  Max Portfolio Heat: {config.risk.max_portfolio_heat_pct}%")
    print(f"  Kelly Fraction: {config.risk.kelly_fraction}")
    print(f"  Max Daily Loss: {config.risk.max_daily_loss_pct}%")

    print("\nRegime Thresholds:")
    print(f"  VIX Low: < {config.regime.vix_low}")
    print(f"  VIX High: > {config.regime.vix_high}")
    print(f"  Gamma Positive: > {config.regime.gamma_positive}B")
    print(f"  Gamma Negative: < {config.regime.gamma_negative}B")

    print("\nWatchlist:")
    print(f"  {', '.join(config.trading.default_watchlist)}")

    print("\nAPI Keys Configured:")
    print(f"  TD Ameritrade: {'Yes' if config.td_ameritrade_api_key else 'No'}")
    print(f"  FRED: {'Yes' if config.fred_api_key else 'No'}")
    print(f"  Polygon: {'Yes' if config.polygon_api_key else 'No'}")
    print(f"  SpotGamma: {'Yes' if config.spotgamma_api_key else 'No'}")

"""Shared pytest fixtures and configuration."""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

# Add project root to path so `from src.xxx import` works
project_root = str(Path(__file__).parent.parent)
if project_root not in sys.path:
    sys.path.insert(0, project_root)


# ---------------------------------------------------------------------------
# OHLC price data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_ohlc():
    """250-day synthetic OHLC DataFrame suitable for regime / indicator tests."""
    rng = np.random.default_rng(seed=42)
    n = 250
    # Slight upward drift with realistic daily noise
    returns = rng.normal(loc=0.0003, scale=0.01, size=n)
    close = 400.0 * np.cumprod(1 + returns)
    high = close * (1 + np.abs(rng.normal(0, 0.005, n)))
    low = close * (1 - np.abs(rng.normal(0, 0.005, n)))
    open_ = close * (1 + rng.normal(0, 0.003, n))
    return pd.DataFrame({"Open": open_, "High": high, "Low": low, "Close": close})


# ---------------------------------------------------------------------------
# Options chain data
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_calls():
    """Sample call option chain."""
    return pd.DataFrame([
        {"strike": 390, "volume": 5000, "openInterest": 500,
         "lastPrice": 12.00, "impliedVolatility": 0.22, "expiration": "2027-03-20"},
        {"strike": 400, "volume": 300, "openInterest": 1000,
         "lastPrice": 5.00,  "impliedVolatility": 0.25, "expiration": "2027-03-20"},
        {"strike": 410, "volume": 100, "openInterest": 800,
         "lastPrice": 1.50,  "impliedVolatility": 0.28, "expiration": "2027-03-20"},
    ])


@pytest.fixture
def sample_puts():
    """Sample put option chain."""
    return pd.DataFrame([
        {"strike": 390, "volume": 8000, "openInterest": 600,
         "lastPrice": 3.00,  "impliedVolatility": 0.26, "expiration": "2027-03-20"},
        {"strike": 400, "volume": 200, "openInterest": 900,
         "lastPrice": 7.00,  "impliedVolatility": 0.24, "expiration": "2027-03-20"},
        {"strike": 410, "volume": 50,  "openInterest": 400,
         "lastPrice": 14.00, "impliedVolatility": 0.27, "expiration": "2027-03-20"},
    ])

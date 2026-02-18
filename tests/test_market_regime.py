"""Tests for the market regime detector."""

import pytest
import numpy as np
import pandas as pd
from src.core.market_regime import (
    MarketRegime, MarketRegimeDetector, VolatilityRegime,
)


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def detector():
    return MarketRegimeDetector()


@pytest.fixture
def base_metrics():
    """Neutral starting metrics that produce RANGING_NEUTRAL by default."""
    return {
        "current_price": 100.0,
        "sma20": 100.0,
        "sma50": 100.0,
        "sma200": 100.0,
        "price_vs_sma20": 0.0,
        "price_vs_sma50": 0.0,
        "price_vs_sma200": 0.0,
        "adx": 15.0,
        "atr20": 1.0,
        "atr_pct": 1.0,
        "hv": 15.0,
        "vol_percentile": 50.0,
        "iv_rank": 50.0,
        "roc20": 0.0,
        "ma_alignment": 0,
        "ma_bear_alignment": 0,
        "trend_strength": 20.0,
        "vix": 18.0,
    }


# ---------------------------------------------------------------------------
# _classify_market_regime
# ---------------------------------------------------------------------------

class TestClassifyMarketRegime:
    def test_strong_trend_up(self, detector, base_metrics):
        """adx > 40, price > SMA20 by >3%, bullish MA alignment."""
        base_metrics.update(adx=45, price_vs_sma20=4.0, ma_alignment=3)
        assert detector._classify_market_regime(base_metrics) == MarketRegime.STRONG_TREND_UP

    def test_strong_trend_down(self, detector, base_metrics):
        """adx > 40, price < SMA20 by >3%, bearish MA alignment."""
        base_metrics.update(adx=45, price_vs_sma20=-4.0, ma_bear_alignment=3, ma_alignment=0)
        assert detector._classify_market_regime(base_metrics) == MarketRegime.STRONG_TREND_DOWN

    def test_trend_up(self, detector, base_metrics):
        """adx > 25, moderate positive deviation, at least one bullish MA cross."""
        base_metrics.update(adx=30, price_vs_sma20=2.0, ma_alignment=2, ma_bear_alignment=0)
        assert detector._classify_market_regime(base_metrics) == MarketRegime.TREND_UP

    def test_trend_down(self, detector, base_metrics):
        """adx > 25, moderate negative deviation, at least one bearish MA cross."""
        base_metrics.update(adx=30, price_vs_sma20=-2.0, ma_alignment=0, ma_bear_alignment=2)
        assert detector._classify_market_regime(base_metrics) == MarketRegime.TREND_DOWN

    def test_high_volatility(self, detector, base_metrics):
        """High vol percentile with low ADX signals choppy / high-vol environment."""
        base_metrics.update(adx=15, vol_percentile=80, price_vs_sma20=0.0)
        assert detector._classify_market_regime(base_metrics) == MarketRegime.HIGH_VOLATILITY

    def test_low_volatility(self, detector, base_metrics):
        """Low vol percentile with very low ADX signals tight consolidation."""
        base_metrics.update(adx=10, vol_percentile=20, price_vs_sma20=0.0)
        assert detector._classify_market_regime(base_metrics) == MarketRegime.LOW_VOLATILITY

    def test_ranging_bullish(self, detector, base_metrics):
        """Low ADX, near-SMA price, but positive 20-day momentum → ranging bullish."""
        base_metrics.update(adx=15, price_vs_sma20=1.0, vol_percentile=50, roc20=3.0)
        assert detector._classify_market_regime(base_metrics) == MarketRegime.RANGING_BULLISH

    def test_ranging_bearish(self, detector, base_metrics):
        """Low ADX, near-SMA price, negative 20-day momentum → ranging bearish."""
        base_metrics.update(adx=15, price_vs_sma20=1.0, vol_percentile=50, roc20=-3.0)
        assert detector._classify_market_regime(base_metrics) == MarketRegime.RANGING_BEARISH

    def test_ranging_neutral(self, detector, base_metrics):
        """Low ADX, near-SMA price, flat momentum → ranging neutral."""
        base_metrics.update(adx=15, price_vs_sma20=0.5, vol_percentile=50, roc20=0.0)
        assert detector._classify_market_regime(base_metrics) == MarketRegime.RANGING_NEUTRAL


# ---------------------------------------------------------------------------
# _classify_volatility_regime
# ---------------------------------------------------------------------------

class TestClassifyVolatilityRegime:
    @pytest.mark.parametrize("vix,expected", [
        (10,  VolatilityRegime.EXTREME_LOW),
        (14,  VolatilityRegime.LOW),
        (18,  VolatilityRegime.NORMAL),
        (25,  VolatilityRegime.ELEVATED),
        (35,  VolatilityRegime.HIGH),
        (45,  VolatilityRegime.EXTREME),
    ])
    def test_vix_band_classification(self, detector, base_metrics, vix, expected):
        result = detector._classify_volatility_regime(base_metrics, vix=vix)
        assert result == expected

    def test_uses_metrics_vix_when_none_passed(self, detector, base_metrics):
        """When vix=None is passed, the value from the metrics dict is used."""
        base_metrics["vix"] = 25
        result = detector._classify_volatility_regime(base_metrics, vix=None)
        assert result == VolatilityRegime.ELEVATED


# ---------------------------------------------------------------------------
# _classify_gamma_regime
# ---------------------------------------------------------------------------

class TestClassifyGammaRegime:
    def test_above_zero_gamma_positive(self, detector):
        result = detector._classify_gamma_regime(current_price=405, zero_gamma=400)
        assert "Positive" in result

    def test_below_zero_gamma_negative(self, detector):
        result = detector._classify_gamma_regime(current_price=395, zero_gamma=400)
        assert "Negative" in result

    def test_none_zero_gamma_unknown(self, detector):
        result = detector._classify_gamma_regime(current_price=400, zero_gamma=None)
        assert result == "Unknown"


# ---------------------------------------------------------------------------
# _calculate_confidence
# ---------------------------------------------------------------------------

class TestCalculateConfidence:
    def test_minimum_confidence_clamped_at_20(self, detector, base_metrics):
        """All-zero inputs should still yield confidence >= 20."""
        base_metrics.update(adx=0, ma_alignment=0, ma_bear_alignment=0, price_vs_sma20=0)
        confidence = detector._calculate_confidence(base_metrics)
        assert confidence >= 20

    def test_maximum_confidence_clamped_at_100(self, detector, base_metrics):
        """Extreme inputs should still yield confidence <= 100."""
        base_metrics.update(adx=50, ma_alignment=3, ma_bear_alignment=3, price_vs_sma20=100)
        confidence = detector._calculate_confidence(base_metrics)
        assert confidence <= 100

    def test_confidence_increases_with_strong_trend(self, detector, base_metrics):
        """Strong ADX + aligned MAs + large price deviation → higher confidence."""
        base_metrics.update(adx=10, ma_alignment=0, ma_bear_alignment=0, price_vs_sma20=0)
        low_confidence = detector._calculate_confidence(base_metrics)
        base_metrics.update(adx=40, ma_alignment=3, price_vs_sma20=5)
        high_confidence = detector._calculate_confidence(base_metrics)
        assert high_confidence > low_confidence


# ---------------------------------------------------------------------------
# Integration — analyze_environment
# ---------------------------------------------------------------------------

class TestAnalyzeEnvironment:
    def test_returns_market_environment(self, detector, sample_ohlc):
        from src.core.market_regime import MarketEnvironment
        env = detector.analyze_environment(sample_ohlc)
        assert isinstance(env, MarketEnvironment)

    def test_regime_is_valid_enum(self, detector, sample_ohlc):
        env = detector.analyze_environment(sample_ohlc)
        assert isinstance(env.regime, MarketRegime)

    def test_volatility_regime_is_valid_enum(self, detector, sample_ohlc):
        env = detector.analyze_environment(sample_ohlc)
        assert isinstance(env.volatility_regime, VolatilityRegime)

    def test_confidence_in_valid_range(self, detector, sample_ohlc):
        env = detector.analyze_environment(sample_ohlc)
        assert 0 <= env.confidence <= 100

    def test_trend_strength_in_valid_range(self, detector, sample_ohlc):
        env = detector.analyze_environment(sample_ohlc)
        assert 0 <= env.trend_strength <= 100

    def test_key_levels_populated(self, detector, sample_ohlc):
        env = detector.analyze_environment(sample_ohlc)
        assert "current_price" in env.key_levels
        assert "recent_high" in env.key_levels
        assert "recent_low" in env.key_levels

    def test_gamma_regime_with_zero_gamma_level(self, detector, sample_ohlc):
        """Passing a zero_gamma level should classify the gamma regime."""
        current_price = sample_ohlc["Close"].iloc[-1]
        env = detector.analyze_environment(sample_ohlc, zero_gamma=current_price - 10)
        assert env.gamma_regime != "Unknown"

    def test_vix_accepted_as_parameter(self, detector, sample_ohlc):
        """Providing vix should influence the volatility regime."""
        env_low_vix = detector.analyze_environment(sample_ohlc, vix=10)
        env_high_vix = detector.analyze_environment(sample_ohlc, vix=50)
        assert env_low_vix.volatility_regime != env_high_vix.volatility_regime

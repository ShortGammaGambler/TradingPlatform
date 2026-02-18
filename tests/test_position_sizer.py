"""Tests for the Kelly Criterion position sizer."""

import pytest
from src.core.position_sizer import PositionSizer


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sizer():
    return PositionSizer(
        portfolio_value=100_000,
        max_position_pct=5.0,
        max_heat_pct=20.0,
        kelly_fraction=0.5,
    )


# Inputs chosen so that NO regime leaves the result capped at max_position_pct,
# making it easy to verify the exact multiplier chain.
_UNCAPPED_INPUTS = dict(win_rate=0.51, reward_risk_ratio=1.1)


# ---------------------------------------------------------------------------
# Kelly formula
# ---------------------------------------------------------------------------

class TestKellyCalculation:
    def test_formula_positive_edge(self, sizer):
        """W=0.6, R=2 → Kelly = W - (1-W)/R = 0.6 - 0.2 = 0.4"""
        kelly = sizer.calculate_kelly(win_rate=0.60, reward_risk_ratio=2.0)
        assert kelly == pytest.approx(0.40, abs=1e-6)

    def test_formula_breakeven_edge(self, sizer):
        """W=0.5, R=1 → Kelly = 0 (exactly on the edge)"""
        kelly = sizer.calculate_kelly(win_rate=0.50, reward_risk_ratio=1.0)
        assert kelly == pytest.approx(0.0, abs=1e-6)

    def test_negative_edge_returns_negative(self, sizer):
        """Below-breakeven inputs produce a negative Kelly fraction."""
        kelly = sizer.calculate_kelly(win_rate=0.30, reward_risk_ratio=1.0)
        assert kelly < 0

    def test_zero_rr_guard(self, sizer):
        """Zero reward/risk ratio is guarded and returns 0."""
        kelly = sizer.calculate_kelly(win_rate=0.60, reward_risk_ratio=0)
        assert kelly == 0


# ---------------------------------------------------------------------------
# IV adjustments
# ---------------------------------------------------------------------------

class TestIVAdjustments:
    def test_high_iv_reduces_size(self, sizer):
        """IV > 80 applies 0.6x multiplier — vol_adjusted should be lower than normal."""
        size_high = sizer.calculate_position_size("SPY", iv_percentile=85, **_UNCAPPED_INPUTS)
        size_norm = sizer.calculate_position_size("SPY", iv_percentile=50, **_UNCAPPED_INPUTS)
        assert size_high.vol_adjusted < size_norm.vol_adjusted

    def test_elevated_iv_reduces_size(self, sizer):
        """IV 60–80 applies 0.8x multiplier."""
        size_elev = sizer.calculate_position_size("SPY", iv_percentile=70, **_UNCAPPED_INPUTS)
        size_norm = sizer.calculate_position_size("SPY", iv_percentile=50, **_UNCAPPED_INPUTS)
        assert size_elev.vol_adjusted < size_norm.vol_adjusted

    def test_low_iv_boosts_size(self, sizer):
        """IV < 20 applies 1.1x multiplier — vol_adjusted should exceed normal."""
        size_low = sizer.calculate_position_size("SPY", iv_percentile=15, **_UNCAPPED_INPUTS)
        size_norm = sizer.calculate_position_size("SPY", iv_percentile=50, **_UNCAPPED_INPUTS)
        assert size_low.vol_adjusted > size_norm.vol_adjusted

    def test_high_iv_multiplier_value(self, sizer):
        """Verify the 0.6x multiplier is applied exactly for IV > 80."""
        size_high = sizer.calculate_position_size("SPY", iv_percentile=85, **_UNCAPPED_INPUTS)
        size_norm = sizer.calculate_position_size("SPY", iv_percentile=50, **_UNCAPPED_INPUTS)
        assert size_high.vol_adjusted == pytest.approx(size_norm.vol_adjusted * 0.6, rel=1e-6)

    def test_elevated_iv_multiplier_value(self, sizer):
        """Verify the 0.8x multiplier is applied exactly for IV 60–80."""
        size_elev = sizer.calculate_position_size("SPY", iv_percentile=70, **_UNCAPPED_INPUTS)
        size_norm = sizer.calculate_position_size("SPY", iv_percentile=50, **_UNCAPPED_INPUTS)
        assert size_elev.vol_adjusted == pytest.approx(size_norm.vol_adjusted * 0.8, rel=1e-6)

    def test_low_iv_multiplier_value(self, sizer):
        """Verify the 1.1x multiplier is applied exactly for IV < 20."""
        size_low = sizer.calculate_position_size("SPY", iv_percentile=15, **_UNCAPPED_INPUTS)
        size_norm = sizer.calculate_position_size("SPY", iv_percentile=50, **_UNCAPPED_INPUTS)
        assert size_low.vol_adjusted == pytest.approx(size_norm.vol_adjusted * 1.1, rel=1e-6)


# ---------------------------------------------------------------------------
# Correlation penalty
# ---------------------------------------------------------------------------

class TestCorrelationPenalty:
    def test_high_correlation_reduces_size(self, sizer):
        """Correlation > 0.5 triggers a penalty, shrinking correlation_adjusted."""
        size_high = sizer.calculate_position_size("SPY", correlation=0.8, **_UNCAPPED_INPUTS)
        size_none = sizer.calculate_position_size("SPY", correlation=0.0, **_UNCAPPED_INPUTS)
        assert size_high.correlation_adjusted < size_none.correlation_adjusted

    def test_low_correlation_no_penalty(self, sizer):
        """Correlation ≤ 0.5 leaves the size unchanged."""
        size_low = sizer.calculate_position_size("SPY", correlation=0.3, **_UNCAPPED_INPUTS)
        size_none = sizer.calculate_position_size("SPY", correlation=0.0, **_UNCAPPED_INPUTS)
        assert size_low.correlation_adjusted == pytest.approx(size_none.correlation_adjusted, rel=1e-6)

    def test_correlation_floor_at_50pct(self, sizer):
        """Even at correlation=0.99, the multiplier is floored at 0.5×vol_adjusted."""
        size = sizer.calculate_position_size("SPY", correlation=0.99, **_UNCAPPED_INPUTS)
        assert size.correlation_adjusted >= size.vol_adjusted * 0.5 - 1e-9


# ---------------------------------------------------------------------------
# Regime multipliers
# ---------------------------------------------------------------------------

class TestRegimeMultipliers:
    @pytest.mark.parametrize("regime,expected_mult", [
        ("POSITIVE_GAMMA", 1.0),
        ("DEEP_POSITIVE", 1.0),
        ("NORMAL",         1.0),
        ("NEUTRAL",        0.9),
        ("NEGATIVE_GAMMA", 0.75),
        ("DEEP_NEGATIVE",  0.5),
        ("HIGH_VOL",       0.6),
        ("EXTREME_VOL",    0.3),
    ])
    def test_regime_multiplier(self, sizer, regime, expected_mult):
        """Each named regime applies the documented multiplier to correlation_adjusted."""
        base = sizer.calculate_position_size("SPY", regime="NORMAL", **_UNCAPPED_INPUTS)
        sized = sizer.calculate_position_size("SPY", regime=regime, **_UNCAPPED_INPUTS)
        # NORMAL multiplier is 1.0, so base.regime_adjusted == base.correlation_adjusted.
        # For any other regime: sized.regime_adjusted = base.correlation_adjusted * expected_mult.
        if base.regime_adjusted > 0:
            ratio = sized.regime_adjusted / base.regime_adjusted
            assert ratio == pytest.approx(expected_mult, rel=1e-3)

    def test_unknown_regime_falls_back(self, sizer):
        """An unrecognised regime string defaults to 0.9× (the NEUTRAL bucket)."""
        base = sizer.calculate_position_size("SPY", regime="NORMAL", **_UNCAPPED_INPUTS)
        sized = sizer.calculate_position_size("SPY", regime="MADE_UP_REGIME", **_UNCAPPED_INPUTS)
        if base.regime_adjusted > 0:
            ratio = sized.regime_adjusted / base.regime_adjusted
            assert ratio == pytest.approx(0.9, rel=1e-3)


# ---------------------------------------------------------------------------
# Position cap
# ---------------------------------------------------------------------------

class TestPositionCap:
    def test_large_kelly_capped_at_max_position_pct(self, sizer):
        """An implausibly large edge (99% win rate, 10:1 R/R) is capped at max_position_pct."""
        size = sizer.calculate_position_size("SPY", win_rate=0.99, reward_risk_ratio=10.0)
        assert size.capped_size_pct <= sizer.max_position_pct

    def test_position_dollars_respects_cap(self, sizer):
        """Dollar amount should never exceed max_position_pct % of portfolio."""
        size = sizer.calculate_position_size("SPY", win_rate=0.99, reward_risk_ratio=10.0)
        max_dollars = sizer.portfolio_value * sizer.max_position_pct / 100
        assert size.position_size_dollars <= max_dollars + 1e-6


# ---------------------------------------------------------------------------
# Negative edge — zero position path
# ---------------------------------------------------------------------------

class TestNegativeEdge:
    def test_negative_edge_returns_zero_dollars(self, sizer):
        """Negative Kelly edge (win_rate < breakeven) must produce a zero-dollar position."""
        size = sizer.calculate_position_size("SPY", win_rate=0.30, reward_risk_ratio=1.0)
        assert size.position_size_dollars == 0

    def test_negative_edge_warns(self, sizer):
        """A warning must be attached explaining the negative-edge result."""
        size = sizer.calculate_position_size("SPY", win_rate=0.30, reward_risk_ratio=1.0)
        assert len(size.warnings) > 0

    def test_negative_edge_all_zeroes(self, sizer):
        """All sizing fields should be 0 on a negative-edge trade."""
        size = sizer.calculate_position_size("SPY", win_rate=0.30, reward_risk_ratio=1.0)
        assert size.capped_size_pct == 0
        assert size.contracts_at_price == 0
        assert size.shares_at_price == 0


# ---------------------------------------------------------------------------
# Contract / share arithmetic
# ---------------------------------------------------------------------------

class TestContractShareCalculation:
    def test_contracts_match_formula(self, sizer):
        """contracts_at_price == floor(position_dollars / (price × multiplier))."""
        size = sizer.calculate_position_size(
            "SPY", win_rate=0.6, reward_risk_ratio=2.0,
            entry_price=5.0, contract_multiplier=100,
        )
        expected = int(size.position_size_dollars / (5.0 * 100))
        assert size.contracts_at_price == expected

    def test_shares_match_formula(self, sizer):
        """shares_at_price == floor(position_dollars / price)."""
        size = sizer.calculate_position_size(
            "SPY", win_rate=0.6, reward_risk_ratio=2.0, entry_price=500.0,
        )
        expected = int(size.position_size_dollars / 500.0)
        assert size.shares_at_price == expected

    def test_no_entry_price_means_zero_contracts(self, sizer):
        """Without an entry price, contracts and shares should remain 0."""
        size = sizer.calculate_position_size("SPY", win_rate=0.6, reward_risk_ratio=2.0)
        assert size.contracts_at_price == 0
        assert size.shares_at_price == 0


# ---------------------------------------------------------------------------
# Portfolio heat tracking
# ---------------------------------------------------------------------------

class TestPortfolioHeatTracking:
    def test_add_position_increases_heat(self, sizer):
        sizer.add_position("SPY", 5_000)
        heat = sizer.get_portfolio_heat()
        assert heat.total_heat_pct == pytest.approx(5.0)
        assert "SPY" in heat.positions

    def test_remove_position_decreases_heat(self, sizer):
        sizer.add_position("SPY", 5_000)
        sizer.remove_position("SPY")
        heat = sizer.get_portfolio_heat()
        assert heat.total_heat_pct == pytest.approx(0.0)
        assert "SPY" not in heat.positions

    def test_at_limit_flag_set_when_full(self):
        sizer = PositionSizer(portfolio_value=100_000, max_heat_pct=10.0)
        sizer.add_position("SPY", 10_000)   # exactly 10%
        heat = sizer.get_portfolio_heat()
        assert heat.at_limit is True

    def test_at_limit_flag_clear_when_under(self, sizer):
        sizer.add_position("SPY", 5_000)
        heat = sizer.get_portfolio_heat()
        assert heat.at_limit is False


class TestPortfolioHeatConstrainsNewPosition:
    def test_full_heat_blocks_new_position(self):
        """Sizer already at max heat should return a zero-size position."""
        sizer = PositionSizer(
            portfolio_value=100_000,
            max_position_pct=5.0,
            max_heat_pct=10.0,
        )
        sizer.add_position("SPY", 10_000)   # 10% risk = at limit
        size = sizer.calculate_position_size("QQQ", win_rate=0.7, reward_risk_ratio=3.0)
        assert size.capped_size_pct == 0.0

    def test_partial_heat_reduces_position(self):
        """Partial heat leaves some room; new position must fit within remaining capacity."""
        sizer = PositionSizer(
            portfolio_value=100_000,
            max_position_pct=5.0,
            max_heat_pct=20.0,
        )
        sizer.add_position("SPY", 15_000)   # 15% heat, 5% remaining
        size = sizer.calculate_position_size("QQQ", win_rate=0.7, reward_risk_ratio=3.0)
        assert 0 < size.capped_size_pct <= 5.0

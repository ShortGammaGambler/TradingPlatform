"""Tests for the portfolio risk manager."""

import numpy as np
import pytest
from src.analytics.risk_manager import PositionGreeks, RiskLevel, RiskManager


# ---------------------------------------------------------------------------
# Shared fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def rm():
    """Risk manager backed by a $100 000 account."""
    return RiskManager(account_value=100_000)


@pytest.fixture
def known_returns():
    """Reproducible 100-element return series (seed fixed)."""
    rng = np.random.default_rng(seed=0)
    return rng.normal(loc=0.0, scale=0.01, size=100)


def make_position(symbol, *, delta=0.0, gamma=0.0, theta=0.0, vega=0.0, notional=0.0):
    return PositionGreeks(
        symbol=symbol, delta=delta, gamma=gamma,
        theta=theta, vega=vega, notional=notional,
    )


# ---------------------------------------------------------------------------
# Fixed-fractional position sizing
# ---------------------------------------------------------------------------

class TestFixedFractional:
    def test_basic_sizing(self, rm):
        """dollar_risk / risk_per_share gives the expected share count when the
        result stays within max_position_size (here $4,000 < $10,000 cap)."""
        # dollar_risk = 100_000 * 0.02 = 2_000; risk_per_share = |100 - 50| = 50
        # shares = int(2_000 / 50) = 40; value = 40 * 100 = $4,000 < $10,000 cap
        shares = rm.calculate_position_size_fixed_fractional(entry_price=100, stop_loss=50)
        assert shares == 40

    def test_entry_equals_stop_returns_zero(self, rm):
        """When entry == stop, risk per share is 0; must return 0 shares."""
        shares = rm.calculate_position_size_fixed_fractional(entry_price=100, stop_loss=100)
        assert shares == 0

    def test_max_position_cap(self, rm):
        """Position value must not exceed max_position_size × account_value."""
        # Tiny stop makes dollar-risk formula suggest millions of shares
        shares = rm.calculate_position_size_fixed_fractional(entry_price=500, stop_loss=499.99)
        max_value = rm.account_value * rm.max_position_size
        assert shares * 500 <= max_value


# ---------------------------------------------------------------------------
# Kelly position sizing
# ---------------------------------------------------------------------------

class TestKellyPositionSizing:
    def test_basic_kelly(self, rm):
        """Positive edge with half-Kelly should produce a non-zero share count."""
        shares = rm.calculate_position_size_kelly(
            win_rate=0.55, avg_win=200, avg_loss=100, entry_price=500
        )
        assert shares > 0

    def test_zero_avg_loss_returns_zero(self, rm):
        """avg_loss == 0 is a degenerate case and must return 0."""
        shares = rm.calculate_position_size_kelly(
            win_rate=0.55, avg_win=200, avg_loss=0, entry_price=500
        )
        assert shares == 0

    def test_win_rate_zero_returns_zero(self, rm):
        """win_rate = 0 means no edge; must return 0."""
        shares = rm.calculate_position_size_kelly(
            win_rate=0.0, avg_win=200, avg_loss=100, entry_price=500
        )
        assert shares == 0

    def test_win_rate_one_returns_zero(self, rm):
        """win_rate = 1 is guarded against (boundary) and must return 0."""
        shares = rm.calculate_position_size_kelly(
            win_rate=1.0, avg_win=200, avg_loss=100, entry_price=500
        )
        assert shares == 0

    def test_negative_edge_returns_zero(self, rm):
        """When full Kelly is negative there is no edge; must return 0."""
        # b = 0.5, p = 0.3, q = 0.7 → Kelly = (0.5*0.3 - 0.7)/0.5 < 0
        shares = rm.calculate_position_size_kelly(
            win_rate=0.30, avg_win=50, avg_loss=100, entry_price=500
        )
        assert shares == 0

    def test_max_position_size_cap(self, rm):
        """Allocation fraction must not exceed max_position_size."""
        shares = rm.calculate_position_size_kelly(
            win_rate=0.90, avg_win=1000, avg_loss=10, entry_price=100
        )
        assert shares * 100 <= rm.account_value * rm.max_position_size + 1


# ---------------------------------------------------------------------------
# Portfolio Greeks aggregation
# ---------------------------------------------------------------------------

class TestPortfolioGreeks:
    def test_empty_portfolio_all_zeros(self, rm):
        greeks = rm.calculate_portfolio_greeks()
        assert greeks["net_delta"] == 0.0
        assert greeks["net_gamma"] == 0.0
        assert greeks["net_theta"] == 0.0
        assert greeks["net_vega"] == 0.0

    def test_single_position_passes_through(self, rm):
        rm.add_position(make_position("SPY", delta=50, gamma=0.05, theta=-10, vega=100))
        greeks = rm.calculate_portfolio_greeks()
        assert greeks["net_delta"] == pytest.approx(50)
        assert greeks["net_gamma"] == pytest.approx(0.05)
        assert greeks["net_theta"] == pytest.approx(-10)
        assert greeks["net_vega"] == pytest.approx(100)

    def test_hedge_reduces_net_delta(self, rm):
        """Adding an opposing position should reduce net delta toward zero."""
        rm.add_position(make_position("SPY_C", delta=50))
        rm.add_position(make_position("SPY_H", delta=-30))
        greeks = rm.calculate_portfolio_greeks()
        assert greeks["net_delta"] == pytest.approx(20)

    def test_delta_dollars_field(self, rm):
        rm.add_position(make_position("SPY", delta=50))
        greeks = rm.calculate_portfolio_greeks()
        assert greeks["delta_dollars"] == pytest.approx(50 * 100)

    def test_multiple_positions_summed(self, rm):
        rm.add_position(make_position("SPY", delta=40, vega=200))
        rm.add_position(make_position("QQQ", delta=-10, vega=50))
        greeks = rm.calculate_portfolio_greeks()
        assert greeks["net_delta"] == pytest.approx(30)
        assert greeks["net_vega"] == pytest.approx(250)


# ---------------------------------------------------------------------------
# VaR and CVaR
# ---------------------------------------------------------------------------

class TestVaR:
    def test_var_matches_formula(self, rm, known_returns):
        """VaR should equal -percentile(returns, 5%) × account_value."""
        var = rm.calculate_var(known_returns, confidence=0.95)
        expected = -np.percentile(known_returns, 5) * rm.account_value
        assert var == pytest.approx(expected, rel=1e-6)

    def test_var_99_greater_than_var_95(self, rm, known_returns):
        """99% VaR must be at least as large as 95% VaR."""
        var95 = rm.calculate_var(known_returns, confidence=0.95)
        var99 = rm.calculate_var(known_returns, confidence=0.99)
        assert var99 >= var95

    def test_var_insufficient_data_returns_zero(self, rm):
        """Fewer than 30 observations is insufficient; must return 0."""
        short_returns = np.array([-0.01, 0.02, -0.03])
        var = rm.calculate_var(short_returns)
        assert var == 0

    def test_cvar_matches_formula(self, rm, known_returns):
        """CVaR should equal -mean(tail_returns) × account_value."""
        cvar = rm.calculate_cvar(known_returns, confidence=0.95)
        threshold = np.percentile(known_returns, 5)
        tail = known_returns[known_returns <= threshold]
        expected = -np.mean(tail) * rm.account_value
        assert cvar == pytest.approx(expected, rel=1e-6)

    def test_cvar_exceeds_var(self, rm, known_returns):
        """CVaR (expected shortfall) must be >= VaR at the same confidence level."""
        var = rm.calculate_var(known_returns, confidence=0.95)
        cvar = rm.calculate_cvar(known_returns, confidence=0.95)
        assert cvar >= var


# ---------------------------------------------------------------------------
# Portfolio risk assessment
# ---------------------------------------------------------------------------

class TestAssessPortfolioRisk:
    def test_empty_portfolio_is_low_risk(self, rm):
        risk = rm.assess_portfolio_risk()
        assert risk.risk_level == RiskLevel.LOW
        assert len(risk.warnings) == 0

    def test_delta_breach_generates_warning(self, rm):
        # max_delta = 100_000 * 0.50 = 50_000; add delta > 50_000
        rm.add_position(make_position("SPY", delta=60_000))
        risk = rm.assess_portfolio_risk()
        assert any("Delta" in w or "delta" in w for w in risk.warnings)

    def test_vega_breach_generates_warning(self, rm):
        # max_vega = 100_000 * 0.05 = 5_000
        rm.add_position(make_position("SPY", vega=6_000))
        risk = rm.assess_portfolio_risk()
        assert any("Vega" in w or "vega" in w for w in risk.warnings)

    def test_theta_breach_generates_warning(self, rm):
        # max_theta = -500; theta bleed worse than that triggers warning
        rm.add_position(make_position("SPY", theta=-600))
        risk = rm.assess_portfolio_risk()
        assert any("Theta" in w or "theta" in w for w in risk.warnings)

    def test_concentration_warning_above_25pct(self, rm):
        """A single position > 25% of total notional should generate a warning."""
        rm.add_position(make_position("SPY", notional=80_000))
        rm.add_position(make_position("QQQ", notional=20_000))
        risk = rm.assess_portfolio_risk()
        assert any("position" in w.lower() for w in risk.warnings)

    def test_risk_level_moderate_with_one_warning(self, rm):
        rm.add_position(make_position("SPY", delta=60_000))
        risk = rm.assess_portfolio_risk()
        assert risk.risk_level == RiskLevel.MODERATE

    def test_risk_level_elevated_with_three_warnings(self, rm):
        # Trigger three warnings simultaneously
        rm.add_position(make_position(
            "SPY",
            delta=60_000,   # delta breach
            vega=6_000,     # vega breach
            theta=-600,     # theta breach
        ))
        risk = rm.assess_portfolio_risk()
        assert risk.risk_level in (RiskLevel.ELEVATED, RiskLevel.HIGH)


# ---------------------------------------------------------------------------
# Stop-loss / take-profit calculation
# ---------------------------------------------------------------------------

class TestStopLevels:
    def test_atr_method(self, rm):
        stop, target = rm.calculate_stop_levels(
            entry_price=100, method="atr", atr=2.0, risk_reward=2.0
        )
        assert stop == pytest.approx(96.0)    # 100 - 2*2 = 96
        assert target == pytest.approx(108.0)  # 100 + 4*2 = 108

    def test_percent_method(self, rm):
        stop, target = rm.calculate_stop_levels(
            entry_price=100, method="percent", risk_reward=3.0
        )
        assert stop == pytest.approx(98.0)     # 100 * 0.98
        assert target == pytest.approx(106.0)  # 100 * (1 + 0.02*3)

    def test_default_method(self, rm):
        stop, target = rm.calculate_stop_levels(entry_price=100)
        assert stop == pytest.approx(98.0)
        assert target == pytest.approx(104.0)

    def test_stop_below_entry_target_above(self, rm):
        stop, target = rm.calculate_stop_levels(entry_price=200, method="atr", atr=5.0)
        assert stop < 200
        assert target > 200


# ---------------------------------------------------------------------------
# Hedge suggestions
# ---------------------------------------------------------------------------

class TestSuggestHedges:
    def test_high_positive_delta_suggests_short(self, rm):
        rm.add_position(make_position("SPY", delta=45_000))  # > 0.8 × max_delta
        risk = rm.assess_portfolio_risk()
        suggestions = rm.suggest_hedges(risk)
        assert any("short" in s.lower() or "short" in s for s in suggestions)

    def test_high_negative_delta_suggests_buy(self, rm):
        rm.add_position(make_position("SPY", delta=-45_000))
        risk = rm.assess_portfolio_risk()
        suggestions = rm.suggest_hedges(risk)
        assert any("buy" in s.lower() for s in suggestions)

    def test_high_short_vega_suggests_vix_calls(self, rm):
        # max_vega = 5_000; -0.8 * 5_000 = -4_000 threshold
        rm.add_position(make_position("SPY", vega=-4_500))
        risk = rm.assess_portfolio_risk()
        suggestions = rm.suggest_hedges(risk)
        assert any("VIX" in s or "vix" in s.lower() for s in suggestions)

    def test_no_breach_no_suggestions(self, rm):
        rm.add_position(make_position("SPY", delta=100, vega=50, theta=-10))
        risk = rm.assess_portfolio_risk()
        suggestions = rm.suggest_hedges(risk)
        assert suggestions == []

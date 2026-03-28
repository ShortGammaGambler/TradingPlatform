"""Tests for the Gamma Exposure calculator."""

import pandas as pd
import pytest
from src.calculators.gamma_exposure import GammaExposureCalculator


# ---------------------------------------------------------------------------
# Shared fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def calc():
    return GammaExposureCalculator(risk_free_rate=0.05)


# Future expiry so that T > 0 in all calculations
_EXPIRY = "2027-12-31"


def _call_row(strike, oi, iv=0.20):
    return {"strike": strike, "openInterest": oi,
            "impliedVolatility": iv, "expiration": _EXPIRY}


def _put_row(strike, oi, iv=0.20):
    return {"strike": strike, "openInterest": oi,
            "impliedVolatility": iv, "expiration": _EXPIRY}


# ---------------------------------------------------------------------------
# calculate_gamma_exposure — sign conventions
# ---------------------------------------------------------------------------

class TestGammaExposureSigns:
    def test_calls_contribute_positive_gex(self, calc):
        """A calls-only chain must produce positive total GEX."""
        calls = pd.DataFrame([_call_row(400, oi=1000)])
        puts = pd.DataFrame(columns=["strike", "openInterest", "impliedVolatility", "expiration"])
        _, total_gamma, _ = calc.calculate_gamma_exposure(calls, puts, current_price=400)
        assert total_gamma > 0

    def test_puts_contribute_negative_gex(self, calc):
        """A puts-only chain must produce negative total GEX."""
        calls = pd.DataFrame(columns=["strike", "openInterest", "impliedVolatility", "expiration"])
        puts = pd.DataFrame([_put_row(400, oi=1000)])
        _, total_gamma, _ = calc.calculate_gamma_exposure(calls, puts, current_price=400)
        assert total_gamma < 0

    def test_balanced_chain_near_zero(self, calc):
        """Equal call/put OI at the same strike should nearly cancel out."""
        calls = pd.DataFrame([_call_row(400, oi=500)])
        puts = pd.DataFrame([_put_row(400, oi=500)])
        _, total_gamma, _ = calc.calculate_gamma_exposure(calls, puts, current_price=400)
        assert abs(total_gamma) < 1e6   # Close to zero relative to one-sided magnitude

    def test_dominant_puts_give_negative_total(self, calc):
        """More put OI than call OI should yield negative total GEX."""
        calls = pd.DataFrame([_call_row(400, oi=100)])
        puts = pd.DataFrame([_put_row(400, oi=1000)])
        _, total_gamma, _ = calc.calculate_gamma_exposure(calls, puts, current_price=400)
        assert total_gamma < 0

    def test_dominant_calls_give_positive_total(self, calc):
        """More call OI than put OI should yield positive total GEX."""
        calls = pd.DataFrame([_call_row(400, oi=1000)])
        puts = pd.DataFrame([_put_row(400, oi=100)])
        _, total_gamma, _ = calc.calculate_gamma_exposure(calls, puts, current_price=400)
        assert total_gamma > 0


# ---------------------------------------------------------------------------
# calculate_gamma_exposure — none / empty guards
# ---------------------------------------------------------------------------

class TestGammaExposureEdgeCases:
    def test_none_inputs_return_none_triple(self, calc):
        result = calc.calculate_gamma_exposure(None, None, current_price=400)
        assert result == (None, None, None)

    def test_zero_oi_rows_skipped(self, calc):
        """Rows with openInterest=0 should produce no gamma contribution."""
        calls = pd.DataFrame([_call_row(400, oi=0)])
        puts = pd.DataFrame([_put_row(400, oi=0)])
        result = calc.calculate_gamma_exposure(calls, puts, current_price=400)
        # All rows filtered → no strikes accumulated → returns (None, None, None)
        assert result == (None, None, None)

    def test_gamma_df_has_expected_columns(self, calc):
        calls = pd.DataFrame([_call_row(400, oi=200)])
        puts = pd.DataFrame([_put_row(390, oi=200)])
        gamma_df, _, _ = calc.calculate_gamma_exposure(calls, puts, current_price=400)
        assert "strike" in gamma_df.columns
        assert "gamma_exposure" in gamma_df.columns


# ---------------------------------------------------------------------------
# _find_gamma_flip_zone
# ---------------------------------------------------------------------------

class TestGammaFlipZone:
    def test_flip_zone_found_when_cumulative_goes_negative(self, calc):
        """The flip zone should be the first strike where cumulative GEX < 0."""
        gamma_df = pd.DataFrame({
            "strike": [390, 400, 410],
            "gamma_exposure": [100, -800, 200],   # cumulative: 100 → -700 → -500
        })
        flip = calc._find_gamma_flip_zone(gamma_df, current_price=405)
        assert flip == 400   # strike where cumulative first goes negative

    def test_flip_zone_none_when_always_positive(self, calc):
        """When cumulative GEX never goes negative the flip zone falls back to
        the highest strike below current_price."""
        gamma_df = pd.DataFrame({
            "strike": [390, 400, 410],
            "gamma_exposure": [100, 200, 300],    # always positive
        })
        flip = calc._find_gamma_flip_zone(gamma_df, current_price=405)
        # Fallback: highest strike < 405
        assert flip == 400


# ---------------------------------------------------------------------------
# calculate_max_pain
# ---------------------------------------------------------------------------

class TestMaxPain:
    def test_max_pain_minimises_total_pain(self, calc):
        """Max pain is the strike that minimises total option holder pain."""
        # Calls at 410 (OI=100); Puts at 395 (OI=100); Large cluster at 400 (OI=1000 each)
        # Pain at strike 395: puts_itm(>395)=[400 OI=1000] → (400-395)*1000=5000; calls_itm=0
        # Pain at strike 400: calls_itm(<400)=none; puts_itm(>400)=none → total=0  ← minimum
        # Pain at strike 410: calls_itm(<410)=[400 OI=1000] → (410-400)*1000=10000
        calls = pd.DataFrame([
            {"strike": 400, "openInterest": 1000},
            {"strike": 410, "openInterest": 100},
        ])
        puts = pd.DataFrame([
            {"strike": 395, "openInterest": 100},
            {"strike": 400, "openInterest": 1000},
        ])
        max_pain = calc.calculate_max_pain(calls, puts)
        assert max_pain == 400

    def test_max_pain_returns_none_for_none_inputs(self, calc):
        assert calc.calculate_max_pain(None, None) is None

    def test_max_pain_returns_a_numeric_value(self, calc, sample_calls, sample_puts):
        import numbers
        result = calc.calculate_max_pain(sample_calls, sample_puts)
        assert isinstance(result, numbers.Number)


# ---------------------------------------------------------------------------
# find_support_resistance
# ---------------------------------------------------------------------------

class TestSupportResistance:
    def test_below_spot_becomes_support(self, calc):
        calls = pd.DataFrame([
            {"strike": 380, "openInterest": 500},
            {"strike": 410, "openInterest": 100},
        ])
        puts = pd.DataFrame([
            {"strike": 385, "openInterest": 400},
            {"strike": 420, "openInterest": 50},
        ])
        support, resistance = calc.find_support_resistance(calls, puts, current_price=400)
        assert all(s < 400 for s in support)

    def test_above_spot_becomes_resistance(self, calc):
        calls = pd.DataFrame([
            {"strike": 380, "openInterest": 100},
            {"strike": 415, "openInterest": 600},
        ])
        puts = pd.DataFrame([
            {"strike": 395, "openInterest": 50},
            {"strike": 420, "openInterest": 700},
        ])
        support, resistance = calc.find_support_resistance(calls, puts, current_price=400)
        assert all(r > 400 for r in resistance)

    def test_num_levels_respected(self, calc, sample_calls, sample_puts):
        support, resistance = calc.find_support_resistance(
            sample_calls, sample_puts, current_price=400, num_levels=2
        )
        assert len(support) <= 2
        assert len(resistance) <= 2

    def test_none_inputs_return_empty_lists(self, calc):
        support, resistance = calc.find_support_resistance(None, None, current_price=400)
        assert support == []
        assert resistance == []


# ---------------------------------------------------------------------------
# calculate_net_gamma_position
# ---------------------------------------------------------------------------

class TestNetGammaPosition:
    def test_positive_gamma_string(self, calc):
        gamma_df = pd.DataFrame({"strike": [400], "gamma_exposure": [500]})
        result = calc.calculate_net_gamma_position(gamma_df, current_price=400)
        assert "Positive" in result

    def test_negative_gamma_string(self, calc):
        gamma_df = pd.DataFrame({"strike": [400], "gamma_exposure": [-500]})
        result = calc.calculate_net_gamma_position(gamma_df, current_price=400)
        assert "Negative" in result

    def test_none_input_returns_unknown(self, calc):
        result = calc.calculate_net_gamma_position(None, current_price=400)
        assert result == "Unknown"

    def test_empty_df_returns_unknown(self, calc):
        result = calc.calculate_net_gamma_position(pd.DataFrame(), current_price=400)
        assert result == "Unknown"

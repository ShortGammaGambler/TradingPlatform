"""Tests for Black-Scholes Greeks calculator."""

import pytest
import math
from src.calculators.greeks import GreeksCalculator


@pytest.fixture
def calc():
    return GreeksCalculator(risk_free_rate=0.05)


class TestDelta:
    def test_atm_call_delta_near_05(self, calc):
        """ATM call delta should be approximately 0.5."""
        delta = calc.delta(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="call")
        assert 0.45 < delta < 0.65

    def test_atm_put_delta_near_neg05(self, calc):
        """ATM put delta should be approximately -0.5 (drift shifts it slightly)."""
        delta = calc.delta(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="put")
        assert -0.65 < delta < -0.35

    def test_deep_itm_call(self, calc):
        """Deep ITM call delta should approach 1."""
        delta = calc.delta(S=150, K=100, T=0.25, r=0.05, sigma=0.2, option_type="call")
        assert delta > 0.95

    def test_deep_otm_call(self, calc):
        """Deep OTM call delta should approach 0."""
        delta = calc.delta(S=50, K=100, T=0.25, r=0.05, sigma=0.2, option_type="call")
        assert delta < 0.05

    def test_expired_option(self, calc):
        """At expiration, delta should be 0 or 1."""
        delta_itm = calc.delta(S=110, K=100, T=0, r=0.05, sigma=0.2, option_type="call")
        assert delta_itm == 1.0
        delta_otm = calc.delta(S=90, K=100, T=0, r=0.05, sigma=0.2, option_type="call")
        assert delta_otm == 0.0


class TestGamma:
    def test_gamma_positive(self, calc):
        """Gamma should always be positive."""
        gamma = calc.gamma(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        assert gamma > 0

    def test_gamma_highest_atm(self, calc):
        """Gamma should be highest at-the-money."""
        gamma_atm = calc.gamma(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        gamma_otm = calc.gamma(S=100, K=120, T=0.25, r=0.05, sigma=0.2)
        gamma_itm = calc.gamma(S=100, K=80, T=0.25, r=0.05, sigma=0.2)
        assert gamma_atm > gamma_otm
        assert gamma_atm > gamma_itm

    def test_gamma_zero_at_expiry(self, calc):
        """Gamma should be 0 at expiration."""
        gamma = calc.gamma(S=100, K=100, T=0, r=0.05, sigma=0.2)
        assert gamma == 0


class TestVega:
    def test_vega_positive(self, calc):
        """Vega should always be positive."""
        vega = calc.vega(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        assert vega > 0

    def test_vega_highest_atm(self, calc):
        """Vega should be highest ATM."""
        vega_atm = calc.vega(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        vega_otm = calc.vega(S=100, K=130, T=0.25, r=0.05, sigma=0.2)
        assert vega_atm > vega_otm


class TestTheta:
    def test_theta_negative_for_long(self, calc):
        """Theta should be negative (time decay hurts long positions)."""
        theta = calc.theta(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="call")
        assert theta < 0


class TestAllGreeks:
    def test_returns_all_greeks(self, calc):
        """calculate_all_greeks should return all 8 Greeks."""
        greeks = calc.calculate_all_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        expected_keys = {"delta", "gamma", "vega", "theta", "rho", "vanna", "charm", "volga"}
        assert set(greeks.keys()) == expected_keys

    def test_put_call_delta_parity(self, calc):
        """Call delta - Put delta should approximately equal 1 (adjusted for rates)."""
        greeks_call = calc.calculate_all_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="call")
        greeks_put = calc.calculate_all_greeks(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="put")
        diff = greeks_call["delta"] - greeks_put["delta"]
        assert 0.95 < diff < 1.05


class TestRho:
    def test_call_rho_positive(self, calc):
        """Call rho is positive: higher rates increase call value."""
        rho = calc.rho(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="call")
        assert rho > 0

    def test_put_rho_negative(self, calc):
        """Put rho is negative: higher rates decrease put value."""
        rho = calc.rho(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="put")
        assert rho < 0

    def test_rho_zero_at_expiry(self, calc):
        """At expiration (T=0) rho must be 0."""
        assert calc.rho(S=100, K=100, T=0, r=0.05, sigma=0.2, option_type="call") == 0
        assert calc.rho(S=100, K=100, T=0, r=0.05, sigma=0.2, option_type="put") == 0

    def test_call_rho_increases_with_time(self, calc):
        """Longer time to expiry amplifies the rate sensitivity."""
        rho_short = calc.rho(S=100, K=100, T=0.25, r=0.05, sigma=0.2, option_type="call")
        rho_long = calc.rho(S=100, K=100, T=1.00, r=0.05, sigma=0.2, option_type="call")
        assert rho_long > rho_short


class TestVannaCharmVolga:
    def test_vanna_zero_at_expiry(self, calc):
        """Vanna (∂delta/∂vol) must be 0 when T=0."""
        assert calc.vanna(S=100, K=100, T=0, r=0.05, sigma=0.2) == 0

    def test_vanna_zero_when_sigma_zero(self, calc):
        """Vanna must be 0 when sigma=0 (guarded by sigma <= 0 check)."""
        assert calc.vanna(S=100, K=100, T=0.25, r=0.05, sigma=0) == 0

    def test_vanna_returns_float(self, calc):
        """Vanna should return a finite float for standard inputs."""
        vanna = calc.vanna(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        assert isinstance(vanna, float)
        assert math.isfinite(vanna)

    def test_charm_zero_at_expiry(self, calc):
        """Charm (∂delta/∂time) must be 0 when T=0."""
        assert calc.charm(S=100, K=100, T=0, r=0.05, sigma=0.2) == 0

    def test_charm_returns_finite_float(self, calc):
        charm = calc.charm(S=100, K=100, T=0.25, r=0.05, sigma=0.2)
        assert isinstance(charm, float)
        assert math.isfinite(charm)

    def test_volga_zero_at_expiry(self, calc):
        """Volga (∂vega/∂vol) must be 0 when T=0."""
        assert calc.volga(S=100, K=100, T=0, r=0.05, sigma=0.2) == 0

    def test_volga_positive_otm(self, calc):
        """For OTM options d1 and d2 are both positive → volga > 0."""
        # S=80 vs K=100 is deep OTM; both d1 and d2 tend to be large and positive
        volga = calc.volga(S=80, K=100, T=1.0, r=0.05, sigma=0.3)
        assert volga > 0


class TestExpiryHelpers:
    def test_days_to_expiry_past_date_is_zero(self, calc):
        """A date already in the past should yield 0 days."""
        assert calc.days_to_expiry("2020-01-01") == 0

    def test_days_to_expiry_future_date_positive(self, calc):
        """A date well in the future should yield a positive number of days."""
        assert calc.days_to_expiry("2030-01-01") > 0

    def test_years_to_expiry_past_date_is_zero(self, calc):
        assert calc.years_to_expiry("2020-01-01") == 0.0

    def test_years_to_expiry_future_date_positive(self, calc):
        years = calc.years_to_expiry("2030-01-01")
        assert years > 0

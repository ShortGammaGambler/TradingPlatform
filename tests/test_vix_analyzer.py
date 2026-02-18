"""Tests for the VIX term structure analyzer."""

import pandas as pd
import pytest
from src.calculators.vix_analyzer import VIXAnalyzer


@pytest.fixture
def analyzer():
    return VIXAnalyzer()


def _make_term_structure(*settle_values):
    """Helper: build a minimal VIX futures DataFrame ordered by contract month."""
    contracts = [f"VX{i+1}" for i in range(len(settle_values))]
    return pd.DataFrame({"contract": contracts, "settle": list(settle_values)})


# ---------------------------------------------------------------------------
# analyze_term_structure
# ---------------------------------------------------------------------------

class TestAnalyzeTermStructure:
    def test_contango_detected(self, analyzer):
        """Front month < back month → contango."""
        df = _make_term_structure(15.0, 17.0)
        result = analyzer.analyze_term_structure(df)
        assert result["structure"] == "Contango"
        assert result["contango"] is True
        assert result["backwardation"] is False

    def test_backwardation_detected(self, analyzer):
        """Front month > back month → backwardation."""
        df = _make_term_structure(22.0, 18.0)
        result = analyzer.analyze_term_structure(df)
        assert result["structure"] == "Backwardation"
        assert result["backwardation"] is True
        assert result["contango"] is False

    def test_flat_detected(self, analyzer):
        """Front month == back month → flat."""
        df = _make_term_structure(20.0, 20.0)
        result = analyzer.analyze_term_structure(df)
        assert result["structure"] == "Flat"
        assert result["contango"] is False
        assert result["backwardation"] is False

    def test_slope_value(self, analyzer):
        """Slope should equal second_month − first_month."""
        df = _make_term_structure(15.0, 18.5)
        result = analyzer.analyze_term_structure(df)
        assert result["slope"] == pytest.approx(3.5)

    def test_front_and_second_month_stored(self, analyzer):
        df = _make_term_structure(14.0, 16.0)
        result = analyzer.analyze_term_structure(df)
        assert result["front_month"] == pytest.approx(14.0)
        assert result["second_month"] == pytest.approx(16.0)

    def test_insufficient_data_returns_no_slope(self, analyzer):
        """A single-row DataFrame cannot form a slope."""
        df = _make_term_structure(15.0)
        result = analyzer.analyze_term_structure(df)
        assert result["slope"] is None
        assert "Insufficient" in result["structure"]

    def test_none_input_returns_none(self, analyzer):
        assert analyzer.analyze_term_structure(None) is None

    def test_empty_df_returns_none(self, analyzer):
        assert analyzer.analyze_term_structure(pd.DataFrame()) is None


# ---------------------------------------------------------------------------
# calculate_vix_slope_2d
# ---------------------------------------------------------------------------

class TestVIXSlope2D:
    def test_returns_dataframe(self, analyzer):
        df = _make_term_structure(15.0, 17.0, 18.5)
        result = analyzer.calculate_vix_slope_2d(df)
        assert isinstance(result, pd.DataFrame)

    def test_row_count_is_n_minus_one(self, analyzer):
        """With n contracts, there are n-1 slopes."""
        df = _make_term_structure(15.0, 16.5, 17.5, 18.0)
        result = analyzer.calculate_vix_slope_2d(df)
        assert len(result) == 3

    def test_slope_values_correct(self, analyzer):
        df = _make_term_structure(15.0, 17.0)
        result = analyzer.calculate_vix_slope_2d(df)
        assert result.iloc[0]["slope"] == pytest.approx(2.0)

    def test_none_returns_none(self, analyzer):
        assert analyzer.calculate_vix_slope_2d(None) is None


# ---------------------------------------------------------------------------
# get_vix_percentile
# ---------------------------------------------------------------------------

class TestVIXPercentile:
    @pytest.mark.parametrize("vix,expected_label", [
        (8,   "Very Low"),
        (13,  "Low"),
        (18,  "Normal"),
        (25,  "Elevated"),
        (35,  "High"),
        (50,  "Very High"),
    ])
    def test_vix_bucket_classification(self, analyzer, vix, expected_label):
        result = analyzer.get_vix_percentile(vix)
        assert expected_label in result

    def test_none_vix_returns_none(self, analyzer):
        assert analyzer.get_vix_percentile(None) is None

"""Tests for Options Flow Scanner."""

import pytest
import pandas as pd
from src.strategies.options_flow_scanner import (
    OptionsFlowScanner, FlowType, FlowSentiment, create_flow_visualization,
)


@pytest.fixture
def scanner():
    return OptionsFlowScanner(
        vol_oi_threshold=3.0,
        min_premium_alert=10_000,
        min_volume_alert=100,
    )


@pytest.fixture
def sample_calls():
    return pd.DataFrame([
        {"strike": 590, "volume": 5000, "openInterest": 500, "lastPrice": 3.50, "impliedVolatility": 0.22, "expiration": "2026-03-20"},
        {"strike": 600, "volume": 50, "openInterest": 1000, "lastPrice": 1.00, "impliedVolatility": 0.25, "expiration": "2026-03-20"},
        {"strike": 610, "volume": 300, "openInterest": 200, "lastPrice": 0.50, "impliedVolatility": 0.30, "expiration": "2026-03-20"},
    ])


@pytest.fixture
def sample_puts():
    return pd.DataFrame([
        {"strike": 580, "volume": 8000, "openInterest": 600, "lastPrice": 2.00, "impliedVolatility": 0.28, "expiration": "2026-03-20"},
        {"strike": 590, "volume": 20, "openInterest": 5000, "lastPrice": 4.00, "impliedVolatility": 0.26, "expiration": "2026-03-20"},
    ])


class TestFlowDetection:
    def test_detects_unusual_volume(self, scanner, sample_calls, sample_puts):
        """Should detect high V/OI ratio as unusual volume."""
        summary = scanner.scan_chain("SPY", sample_calls, sample_puts, spot_price=595)
        # 590 call: V/OI = 5000/500 = 10x, should be detected
        flow_types = [f.flow_type for f in summary.top_flows]
        assert FlowType.UNUSUAL_VOLUME in flow_types

    def test_calculates_premium(self, scanner, sample_calls, sample_puts):
        """Should correctly calculate total premium."""
        summary = scanner.scan_chain("SPY", sample_calls, sample_puts, spot_price=595)
        assert summary.total_call_premium > 0
        assert summary.total_put_premium > 0

    def test_net_sentiment_range(self, scanner, sample_calls, sample_puts):
        """Net sentiment should be between -1 and 1."""
        summary = scanner.scan_chain("SPY", sample_calls, sample_puts, spot_price=595)
        assert -1 <= summary.net_sentiment <= 1

    def test_empty_chain_handled(self, scanner):
        """Should handle empty DataFrames gracefully."""
        empty_df = pd.DataFrame()
        summary = scanner.scan_chain("SPY", empty_df, empty_df, spot_price=595)
        assert summary.total_call_premium == 0
        assert summary.total_put_premium == 0
        assert len(summary.top_flows) == 0

    def test_none_chain_handled(self, scanner):
        """Should handle None DataFrames gracefully."""
        summary = scanner.scan_chain("SPY", None, None, spot_price=595)
        assert len(summary.top_flows) == 0


class TestFlowDataFrame:
    def test_get_flow_dataframe(self, scanner, sample_calls, sample_puts):
        scanner.scan_chain("SPY", sample_calls, sample_puts, spot_price=595)
        df = scanner.get_flow_dataframe()
        if not df.empty:
            assert "Symbol" in df.columns
            assert "Score" in df.columns
            assert "V/OI" in df.columns


class TestVisualization:
    def test_create_visualization_returns_figures(self, scanner, sample_calls, sample_puts):
        summary = scanner.scan_chain("SPY", sample_calls, sample_puts, spot_price=595)
        figs = create_flow_visualization(summary)
        assert "premium_chart" in figs
        assert "sentiment_gauge" in figs

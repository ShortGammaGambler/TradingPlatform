"""
Options Flow Scanner
Detects unusual options activity: volume spikes, sweeps, blocks, and V/OI anomalies.

Expected interface (referenced by trading_platform.py):
    - OptionsFlowScanner class
    - create_flow_visualization function
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class FlowType(Enum):
    """Classification of options flow"""
    SWEEP = "sweep"          # Aggressive, hits multiple exchanges
    BLOCK = "block"          # Large single-exchange fill
    SPLIT = "split"          # Split across time
    UNUSUAL_VOLUME = "unusual_volume"  # Volume >> open interest
    OPENING = "opening"      # New position
    CLOSING = "closing"      # Closing existing position


class FlowSentiment(Enum):
    """Inferred sentiment from flow"""
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


@dataclass
class OptionsFlow:
    """Single detected flow event"""
    symbol: str
    timestamp: datetime
    flow_type: FlowType
    sentiment: FlowSentiment
    option_type: str          # "call" or "put"
    strike: float
    expiration: str
    volume: int
    open_interest: int
    premium: float            # Total premium in $
    implied_vol: float
    spot_price: float
    score: float = 0.0        # Significance score 0-100
    details: str = ""


@dataclass
class FlowSummary:
    """Aggregate flow statistics"""
    total_call_premium: float = 0.0
    total_put_premium: float = 0.0
    total_call_volume: int = 0
    total_put_volume: int = 0
    sweep_count: int = 0
    block_count: int = 0
    unusual_count: int = 0
    net_sentiment: float = 0.0   # -1 to +1
    top_flows: List[OptionsFlow] = field(default_factory=list)


class OptionsFlowScanner:
    """
    Scans options chains for unusual activity patterns.

    Detection methods:
    1. Volume/OI ratio — flags when V/OI > threshold
    2. Sweep detection — large orders split across exchanges
    3. Block detection — single large fills
    4. Premium analysis — unusually large dollar premium
    """

    def __init__(
        self,
        vol_oi_threshold: float = 3.0,
        min_premium_alert: float = 50_000,
        min_volume_alert: int = 500,
        sweep_min_size: int = 100,
        block_min_size: int = 200,
    ):
        self.vol_oi_threshold = vol_oi_threshold
        self.min_premium_alert = min_premium_alert
        self.min_volume_alert = min_volume_alert
        self.sweep_min_size = sweep_min_size
        self.block_min_size = block_min_size
        self.detected_flows: List[OptionsFlow] = []

    def scan_chain(
        self,
        symbol: str,
        calls_df: pd.DataFrame,
        puts_df: pd.DataFrame,
        spot_price: float,
    ) -> FlowSummary:
        """
        Scan an options chain for unusual activity.

        Args:
            symbol: Underlying ticker
            calls_df: DataFrame with columns [strike, volume, openInterest, lastPrice, impliedVolatility, expiration]
            puts_df: Same structure for puts
            spot_price: Current underlying price

        Returns:
            FlowSummary with detected flows and aggregate stats
        """
        self.detected_flows = []

        if calls_df is not None and not calls_df.empty:
            self._scan_side(symbol, calls_df, "call", spot_price)

        if puts_df is not None and not puts_df.empty:
            self._scan_side(symbol, puts_df, "put", spot_price)

        # Sort by score descending
        self.detected_flows.sort(key=lambda f: f.score, reverse=True)

        # Build summary
        summary = self._build_summary()
        return summary

    def _scan_side(
        self,
        symbol: str,
        df: pd.DataFrame,
        option_type: str,
        spot_price: float,
    ):
        """Scan one side (calls or puts) for unusual activity."""
        for _, row in df.iterrows():
            strike = row.get("strike", 0)
            volume = int(row.get("volume", 0) or 0)
            oi = int(row.get("openInterest", 0) or 0)
            last_price = float(row.get("lastPrice", 0) or 0)
            iv = float(row.get("impliedVolatility", 0) or 0)
            expiry = str(row.get("expiration", ""))

            if volume < 10:
                continue

            premium = volume * last_price * 100  # contract multiplier
            vol_oi_ratio = volume / max(oi, 1)

            # Detect unusual volume/OI
            if vol_oi_ratio >= self.vol_oi_threshold and volume >= self.min_volume_alert:
                flow = self._create_flow(
                    symbol, option_type, strike, expiry, volume, oi,
                    premium, iv, spot_price, FlowType.UNUSUAL_VOLUME,
                    f"V/OI ratio: {vol_oi_ratio:.1f}x"
                )
                self.detected_flows.append(flow)

            # Detect blocks (large single fills)
            elif volume >= self.block_min_size and premium >= self.min_premium_alert:
                flow = self._create_flow(
                    symbol, option_type, strike, expiry, volume, oi,
                    premium, iv, spot_price, FlowType.BLOCK,
                    f"Block: {volume} contracts, ${premium:,.0f} premium"
                )
                self.detected_flows.append(flow)

            # Detect sweeps (aggressive fills, inferred from high volume + ATM proximity)
            elif volume >= self.sweep_min_size and premium >= self.min_premium_alert * 0.5:
                moneyness = abs(strike - spot_price) / spot_price
                if moneyness < 0.05:  # Near ATM
                    flow = self._create_flow(
                        symbol, option_type, strike, expiry, volume, oi,
                        premium, iv, spot_price, FlowType.SWEEP,
                        f"Sweep: {volume} contracts near ATM"
                    )
                    self.detected_flows.append(flow)

    def _create_flow(
        self,
        symbol: str,
        option_type: str,
        strike: float,
        expiry: str,
        volume: int,
        oi: int,
        premium: float,
        iv: float,
        spot_price: float,
        flow_type: FlowType,
        details: str,
    ) -> OptionsFlow:
        """Create a flow event with a significance score."""
        # Calculate score (0-100)
        score = 0.0

        # Volume/OI contribution (up to 30 points)
        vol_oi = volume / max(oi, 1)
        score += min(vol_oi * 10, 30)

        # Premium contribution (up to 30 points)
        score += min(premium / 100_000 * 10, 30)

        # Flow type contribution
        type_scores = {
            FlowType.SWEEP: 20,
            FlowType.BLOCK: 15,
            FlowType.UNUSUAL_VOLUME: 15,
            FlowType.SPLIT: 10,
            FlowType.OPENING: 10,
            FlowType.CLOSING: 5,
        }
        score += type_scores.get(flow_type, 0)

        # Proximity to ATM (up to 10 points)
        moneyness = abs(strike - spot_price) / spot_price
        score += max(0, 10 - moneyness * 100)

        score = min(score, 100)

        # Infer sentiment
        if option_type == "call":
            sentiment = FlowSentiment.BULLISH
        else:
            sentiment = FlowSentiment.BEARISH

        return OptionsFlow(
            symbol=symbol,
            timestamp=datetime.now(),
            flow_type=flow_type,
            sentiment=sentiment,
            option_type=option_type,
            strike=strike,
            expiration=expiry,
            volume=volume,
            open_interest=oi,
            premium=premium,
            implied_vol=iv,
            spot_price=spot_price,
            score=score,
            details=details,
        )

    def _build_summary(self) -> FlowSummary:
        """Build aggregate summary from detected flows."""
        summary = FlowSummary()

        for flow in self.detected_flows:
            if flow.option_type == "call":
                summary.total_call_premium += flow.premium
                summary.total_call_volume += flow.volume
            else:
                summary.total_put_premium += flow.premium
                summary.total_put_volume += flow.volume

            if flow.flow_type == FlowType.SWEEP:
                summary.sweep_count += 1
            elif flow.flow_type == FlowType.BLOCK:
                summary.block_count += 1
            elif flow.flow_type == FlowType.UNUSUAL_VOLUME:
                summary.unusual_count += 1

        # Net sentiment: ratio of call vs put premium
        total_premium = summary.total_call_premium + summary.total_put_premium
        if total_premium > 0:
            summary.net_sentiment = (
                (summary.total_call_premium - summary.total_put_premium) / total_premium
            )

        summary.top_flows = self.detected_flows[:20]
        return summary

    def get_flow_dataframe(self) -> pd.DataFrame:
        """Return detected flows as a DataFrame for display."""
        if not self.detected_flows:
            return pd.DataFrame()

        records = []
        for f in self.detected_flows:
            records.append({
                "Symbol": f.symbol,
                "Type": f.flow_type.value,
                "Sentiment": f.sentiment.value,
                "Side": f.option_type.upper(),
                "Strike": f.strike,
                "Expiry": f.expiration,
                "Volume": f.volume,
                "OI": f.open_interest,
                "V/OI": round(f.volume / max(f.open_interest, 1), 1),
                "Premium": f"${f.premium:,.0f}",
                "IV": f"{f.implied_vol:.1%}",
                "Score": round(f.score, 1),
                "Details": f.details,
            })
        return pd.DataFrame(records)


def create_flow_visualization(summary: FlowSummary) -> dict:
    """
    Create Plotly figures for flow analysis display.

    Returns dict with keys: 'premium_chart', 'flow_table', 'sentiment_gauge'
    """
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    figures = {}

    # 1. Premium comparison bar chart
    fig_premium = go.Figure()
    fig_premium.add_trace(go.Bar(
        x=["Calls", "Puts"],
        y=[summary.total_call_premium, summary.total_put_premium],
        marker_color=["#00C853", "#FF1744"],
        text=[f"${summary.total_call_premium:,.0f}", f"${summary.total_put_premium:,.0f}"],
        textposition="auto",
    ))
    fig_premium.update_layout(
        title="Options Flow Premium",
        yaxis_title="Total Premium ($)",
        template="plotly_dark",
        height=300,
    )
    figures["premium_chart"] = fig_premium

    # 2. Sentiment gauge
    fig_gauge = go.Figure(go.Indicator(
        mode="gauge+number",
        value=summary.net_sentiment * 100,
        title={"text": "Flow Sentiment"},
        gauge={
            "axis": {"range": [-100, 100]},
            "bar": {"color": "#667eea"},
            "steps": [
                {"range": [-100, -30], "color": "#FF1744"},
                {"range": [-30, 30], "color": "#455A64"},
                {"range": [30, 100], "color": "#00C853"},
            ],
        },
        number={"suffix": "%"},
    ))
    fig_gauge.update_layout(template="plotly_dark", height=250)
    figures["sentiment_gauge"] = fig_gauge

    # 3. Flow type breakdown
    labels = ["Sweeps", "Blocks", "Unusual Volume"]
    values = [summary.sweep_count, summary.block_count, summary.unusual_count]
    if any(v > 0 for v in values):
        fig_types = go.Figure(go.Pie(
            labels=labels,
            values=values,
            marker_colors=["#667eea", "#764ba2", "#f093fb"],
            hole=0.4,
        ))
        fig_types.update_layout(
            title="Flow Type Distribution",
            template="plotly_dark",
            height=300,
        )
        figures["flow_types"] = fig_types

    return figures

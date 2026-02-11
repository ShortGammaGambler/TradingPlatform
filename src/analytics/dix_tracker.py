"""
Dark Pool Index (DIX) and Institutional Flow Tracker
Monitors smart money activity through dark pool indicators
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum


class InstitutionalSignal(Enum):
    """Smart money signals"""
    HEAVY_BUYING = "Heavy Institutional Buying"
    MODERATE_BUYING = "Moderate Buying"
    NEUTRAL = "Neutral Flow"
    MODERATE_SELLING = "Moderate Selling"
    HEAVY_SELLING = "Heavy Institutional Selling"


@dataclass
class DIXAnalysis:
    """DIX and GEX analysis results"""
    dix: float  # Dark Pool Index (0-1, higher = more buying)
    gex: float  # Gamma Exposure
    dix_percentile: float  # DIX percentile over lookback
    gex_percentile: float  # GEX percentile
    signal: InstitutionalSignal
    confidence: float  # 0-100
    interpretation: str
    market_outlook: str
    trading_recommendation: str
    risk_level: str


@dataclass
class DarkPoolMetrics:
    """Dark pool trading metrics"""
    dark_pool_volume: float
    total_volume: float
    dark_pool_percentage: float
    short_volume: float
    short_percentage: float
    institutional_buying_pressure: float  # Derived metric
    smart_money_confidence: float  # 0-100


class DIXTracker:
    """
    Track Dark Pool Index and institutional order flow
    
    DIX measures institutional buying in dark pools:
    - High DIX (>0.45): Institutions buying, bullish
    - Low DIX (<0.40): Institutions selling, bearish
    
    Combined with GEX:
    - High DIX + Low GEX = Bullish setup (institutions buying, low dealer hedging)
    - Low DIX + High GEX = Bearish setup (institutions selling, high dealer hedging)
    """
    
    def __init__(self, lookback_period: int = 252):
        self.lookback_period = lookback_period
    
    def analyze_dix_gex(
        self,
        current_dix: float,
        current_gex: float,
        historical_dix: pd.Series,
        historical_gex: pd.Series,
        current_price: float,
        trend: str = "NEUTRAL"
    ) -> DIXAnalysis:
        """
        Comprehensive DIX/GEX analysis
        
        Args:
            current_dix: Current DIX level (0-1)
            current_gex: Current GEX level
            historical_dix: Historical DIX series
            historical_gex: Historical GEX series
            current_price: Current underlying price
            trend: Current market trend
            
        Returns:
            DIXAnalysis with complete interpretation
        """
        
        # Calculate percentiles
        dix_percentile = self._calculate_percentile(current_dix, historical_dix)
        gex_percentile = self._calculate_percentile(current_gex, historical_gex)
        
        # Determine signal
        signal, confidence = self._determine_signal(
            current_dix, 
            current_gex,
            dix_percentile,
            gex_percentile
        )
        
        # Generate interpretation
        interpretation = self._interpret_signal(
            current_dix,
            current_gex,
            dix_percentile,
            gex_percentile,
            signal
        )
        
        # Market outlook
        outlook = self._generate_outlook(signal, current_dix, current_gex, trend)
        
        # Trading recommendation
        recommendation = self._generate_recommendation(signal, current_dix, current_gex)
        
        # Risk assessment
        risk_level = self._assess_risk(current_dix, current_gex, dix_percentile, gex_percentile)
        
        return DIXAnalysis(
            dix=current_dix,
            gex=current_gex,
            dix_percentile=dix_percentile,
            gex_percentile=gex_percentile,
            signal=signal,
            confidence=confidence,
            interpretation=interpretation,
            market_outlook=outlook,
            trading_recommendation=recommendation,
            risk_level=risk_level
        )
    
    def calculate_dix(
        self,
        dark_pool_short_volume: float,
        total_dark_pool_volume: float,
        total_volume: float
    ) -> float:
        """
        Calculate DIX (simplified version)
        
        Real DIX formula is proprietary to SqueezeMetrics
        This is an approximation based on public information
        
        Args:
            dark_pool_short_volume: Short volume in dark pools
            total_dark_pool_volume: Total dark pool volume
            total_volume: Total market volume
            
        Returns:
            DIX estimate (0-1)
        """
        
        # Dark pool percentage
        dp_pct = total_dark_pool_volume / total_volume if total_volume > 0 else 0
        
        # Short percentage in dark pools
        short_pct = dark_pool_short_volume / total_dark_pool_volume if total_dark_pool_volume > 0 else 0
        
        # DIX approximation
        # High short volume in dark pools = institutions buying (they short to hedge)
        dix = short_pct * dp_pct
        
        # Normalize to 0-1 range
        dix = np.clip(dix, 0, 1)
        
        return dix
    
    def track_dark_pool_activity(
        self,
        volume_data: pd.DataFrame
    ) -> DarkPoolMetrics:
        """
        Track dark pool trading activity
        
        Args:
            volume_data: DataFrame with dark pool and exchange volume data
            Expected columns: 'dark_volume', 'total_volume', 'short_volume'
            
        Returns:
            DarkPoolMetrics with analysis
        """
        
        dark_volume = volume_data['dark_volume'].iloc[-1] if 'dark_volume' in volume_data.columns else 0
        total_volume = volume_data['total_volume'].iloc[-1] if 'total_volume' in volume_data.columns else 1
        short_volume = volume_data['short_volume'].iloc[-1] if 'short_volume' in volume_data.columns else 0
        
        dark_pct = (dark_volume / total_volume * 100) if total_volume > 0 else 0
        short_pct = (short_volume / total_volume * 100) if total_volume > 0 else 0
        
        # Calculate institutional buying pressure
        # High short volume often indicates institutional buying (they short to hedge long positions)
        buying_pressure = short_pct * (dark_pct / 100)
        
        # Confidence score
        # Higher dark pool activity = more institutional involvement
        confidence = min(100, dark_pct * 2)
        
        return DarkPoolMetrics(
            dark_pool_volume=dark_volume,
            total_volume=total_volume,
            dark_pool_percentage=dark_pct,
            short_volume=short_volume,
            short_percentage=short_pct,
            institutional_buying_pressure=buying_pressure,
            smart_money_confidence=confidence
        )
    
    def _calculate_percentile(
        self,
        current_value: float,
        historical_series: pd.Series
    ) -> float:
        """Calculate percentile of current value vs historical"""
        
        if historical_series.empty or len(historical_series) == 0:
            return 50.0
        
        # Use last N periods
        recent_history = historical_series.iloc[-self.lookback_period:] if len(historical_series) > self.lookback_period else historical_series
        
        percentile = (current_value > recent_history).sum() / len(recent_history) * 100
        
        return percentile
    
    def _determine_signal(
        self,
        dix: float,
        gex: float,
        dix_percentile: float,
        gex_percentile: float
    ) -> Tuple[InstitutionalSignal, float]:
        """Determine institutional signal and confidence"""
        
        confidence = 50.0
        
        # High DIX scenarios
        if dix > 0.45 and dix_percentile > 70:
            if gex_percentile < 30:
                # Strong bullish: High DIX + Low GEX
                signal = InstitutionalSignal.HEAVY_BUYING
                confidence = min(95, 70 + (dix_percentile - 70) / 3)
            else:
                signal = InstitutionalSignal.MODERATE_BUYING
                confidence = 65
        
        # Low DIX scenarios
        elif dix < 0.40 and dix_percentile < 30:
            if gex_percentile > 70:
                # Strong bearish: Low DIX + High GEX
                signal = InstitutionalSignal.HEAVY_SELLING
                confidence = min(95, 70 + (70 - dix_percentile) / 3)
            else:
                signal = InstitutionalSignal.MODERATE_SELLING
                confidence = 65
        
        # Moderate scenarios
        elif dix > 0.43:
            signal = InstitutionalSignal.MODERATE_BUYING
            confidence = 55
        elif dix < 0.42:
            signal = InstitutionalSignal.MODERATE_SELLING
            confidence = 55
        else:
            signal = InstitutionalSignal.NEUTRAL
            confidence = 40
        
        return signal, confidence
    
    def _interpret_signal(
        self,
        dix: float,
        gex: float,
        dix_percentile: float,
        gex_percentile: float,
        signal: InstitutionalSignal
    ) -> str:
        """Generate human-readable interpretation"""
        
        interpretation = f"DIX at {dix:.3f} ({dix_percentile:.0f}th percentile) indicates "
        
        if signal == InstitutionalSignal.HEAVY_BUYING:
            interpretation += "strong institutional buying. Dark pool activity shows smart money accumulating positions. "
            interpretation += f"GEX at {gex_percentile:.0f}th percentile suggests low dealer hedging pressure, allowing for upside."
        
        elif signal == InstitutionalSignal.MODERATE_BUYING:
            interpretation += "moderate institutional buying. Institutions are positioning for potential upside. "
            interpretation += "Monitor for continuation of this trend."
        
        elif signal == InstitutionalSignal.HEAVY_SELLING:
            interpretation += "strong institutional selling. Smart money appears to be reducing exposure. "
            interpretation += f"GEX at {gex_percentile:.0f}th percentile suggests high dealer hedging, creating downside pressure."
        
        elif signal == InstitutionalSignal.MODERATE_SELLING:
            interpretation += "moderate institutional selling. Some profit-taking or de-risking occurring. "
            interpretation += "Watch for potential reversal signals."
        
        else:
            interpretation += "neutral institutional positioning. No clear directional bias from smart money. "
            interpretation += "Wait for clearer signals before taking large directional bets."
        
        return interpretation
    
    def _generate_outlook(
        self,
        signal: InstitutionalSignal,
        dix: float,
        gex: float,
        trend: str
    ) -> str:
        """Generate market outlook"""
        
        if signal == InstitutionalSignal.HEAVY_BUYING:
            if trend == "TREND_UP":
                return "Bullish: Institutions buying into uptrend. Expect continuation with potential acceleration."
            else:
                return "Accumulation Phase: Institutions building positions. Potential reversal forming."
        
        elif signal == InstitutionalSignal.MODERATE_BUYING:
            return "Cautiously Bullish: Institutions showing interest. Look for confirmation before aggressive positioning."
        
        elif signal == InstitutionalSignal.HEAVY_SELLING:
            if trend == "TREND_DOWN":
                return "Bearish: Institutions selling into downtrend. Expect continuation with increased volatility."
            else:
                return "Distribution Phase: Institutions reducing exposure. Potential reversal or correction ahead."
        
        elif signal == InstitutionalSignal.MODERATE_SELLING:
            return "Cautiously Bearish: Some institutional profit-taking. Monitor for further weakness."
        
        else:
            return "Neutral: No strong institutional bias. Range-bound action likely. Favor theta strategies."
    
    def _generate_recommendation(
        self,
        signal: InstitutionalSignal,
        dix: float,
        gex: float
    ) -> str:
        """Generate trading recommendation"""
        
        if signal == InstitutionalSignal.HEAVY_BUYING:
            return "STRATEGY: Buy dips, use bull call spreads, sell puts. Favor bullish directional plays."
        
        elif signal == InstitutionalSignal.MODERATE_BUYING:
            return "STRATEGY: Slight bullish bias. Consider bull put spreads or calendar spreads at support."
        
        elif signal == InstitutionalSignal.HEAVY_SELLING:
            return "STRATEGY: Sell rallies, use bear put spreads, sell calls. Favor bearish directional plays."
        
        elif signal == InstitutionalSignal.MODERATE_SELLING:
            return "STRATEGY: Slight bearish bias. Consider bear call spreads or protective puts."
        
        else:
            return "STRATEGY: Stay neutral. Iron condors, butterflies, and other range-bound strategies preferred."
    
    def _assess_risk(
        self,
        dix: float,
        gex: float,
        dix_percentile: float,
        gex_percentile: float
    ) -> str:
        """Assess current risk level"""
        
        # Extreme levels indicate higher risk
        if dix_percentile > 85 or dix_percentile < 15:
            if gex_percentile > 85 or gex_percentile < 15:
                return "High Risk (Extreme Levels)"
            return "Medium Risk (Elevated Levels)"
        
        if gex_percentile > 90 or gex_percentile < 10:
            return "Medium Risk (Elevated GEX)"
        
        # Neutral levels = lower risk
        if 40 < dix_percentile < 60 and 40 < gex_percentile < 60:
            return "Low Risk (Normal Conditions)"
        
        return "Medium Risk"


def create_dix_gex_plot(
    dix_history: pd.Series,
    gex_history: pd.Series,
    price_history: pd.Series,
    current_dix: float,
    current_gex: float
):
    """
    Create visualization of DIX/GEX vs price
    """
    import plotly.graph_objs as go
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=3, cols=1,
        shared_xaxes=True,
        subplot_titles=('Price Action', 'DIX (Dark Pool Index)', 'GEX (Gamma Exposure)'),
        vertical_spacing=0.08,
        row_heights=[0.4, 0.3, 0.3]
    )
    
    # Price
    fig.add_trace(
        go.Scatter(
            x=price_history.index,
            y=price_history.values,
            name='Price',
            line=dict(color='#00cc96', width=2)
        ),
        row=1, col=1
    )
    
    # DIX
    fig.add_trace(
        go.Scatter(
            x=dix_history.index,
            y=dix_history.values,
            name='DIX',
            line=dict(color='#ab63fa', width=2),
            fill='tozeroy',
            fillcolor='rgba(171, 99, 250, 0.2)'
        ),
        row=2, col=1
    )
    
    # DIX thresholds
    fig.add_hline(y=0.45, line_dash="dash", line_color="green", row=2, col=1, 
                  annotation_text="Bullish (0.45)")
    fig.add_hline(y=0.40, line_dash="dash", line_color="red", row=2, col=1,
                  annotation_text="Bearish (0.40)")
    
    # GEX
    fig.add_trace(
        go.Scatter(
            x=gex_history.index,
            y=gex_history.values,
            name='GEX',
            line=dict(color='#ffa500', width=2),
            fill='tozeroy',
            fillcolor='rgba(255, 165, 0, 0.2)'
        ),
        row=3, col=1
    )
    
    # Zero GEX line
    fig.add_hline(y=0, line_dash="solid", line_color="gray", row=3, col=1)
    
    fig.update_layout(
        title='DIX/GEX Institutional Flow Analysis',
        height=800,
        template='plotly_dark',
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117',
        showlegend=True,
        hovermode='x unified'
    )
    
    fig.update_yaxes(title_text="Price ($)", row=1, col=1)
    fig.update_yaxes(title_text="DIX", row=2, col=1)
    fig.update_yaxes(title_text="GEX", row=3, col=1)
    fig.update_xaxes(title_text="Date", row=3, col=1)
    
    return fig

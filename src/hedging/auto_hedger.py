"""
Greeks-Based Auto-Hedging Engine
Automatically suggests hedges to maintain portfolio Greeks targets
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum


class HedgeType(Enum):
    """Type of hedge recommendation"""
    DELTA_HEDGE = "Delta Hedge"
    GAMMA_HEDGE = "Gamma Hedge"
    VEGA_HEDGE = "Vega Hedge"
    THETA_OPTIMIZATION = "Theta Optimization"
    COMBINED_HEDGE = "Combined Hedge"


@dataclass
class HedgeRecommendation:
    """Single hedge recommendation"""
    hedge_type: HedgeType
    action: str  # "BUY" or "SELL"
    instrument: str  # "SPY", "VIX", "SPX Call", etc.
    quantity: int
    strike: Optional[float] = None
    expiration: Optional[str] = None
    
    # Impact
    delta_change: float = 0.0
    gamma_change: float = 0.0
    theta_change: float = 0.0
    vega_change: float = 0.0
    
    # Cost
    estimated_cost: float = 0.0
    
    # Rationale
    reason: str = ""
    priority: int = 1  # 1=Critical, 2=Important, 3=Optional
    
    def __str__(self):
        return f"{self.action} {self.quantity} {self.instrument} @ ${self.estimated_cost:,.0f}"


class AutoHedger:
    """
    Automatic hedging engine based on portfolio Greeks
    
    Maintains portfolio Greeks within target ranges:
    - Delta: -200 to +200 (directional neutrality)
    - Gamma: -500 to +500 (gamma risk)
    - Vega: -10,000 to +10,000 (vol risk)
    - Theta: Maximize positive theta
    """
    
    def __init__(
        self,
        delta_target: Tuple[float, float] = (-200, 200),
        gamma_target: Tuple[float, float] = (-500, 500),
        vega_target: Tuple[float, float] = (-10000, 10000),
        theta_min: float = -500,  # Max theta decay willing to accept
    ):
        """
        Initialize auto-hedger with target ranges
        
        Args:
            delta_target: (min, max) acceptable delta range
            gamma_target: (min, max) acceptable gamma range
            vega_target: (min, max) acceptable vega range
            theta_min: minimum acceptable theta (negative = decay)
        """
        self.delta_target = delta_target
        self.gamma_target = gamma_target
        self.vega_target = vega_target
        self.theta_min = theta_min
    
    def analyze_portfolio_greeks(
        self,
        net_delta: float,
        net_gamma: float,
        net_theta: float,
        net_vega: float
    ) -> Dict[str, bool]:
        """
        Check which Greeks are out of range
        
        Returns:
            Dict of {greek: is_out_of_range}
        """
        
        out_of_range = {
            'delta': not (self.delta_target[0] <= net_delta <= self.delta_target[1]),
            'gamma': not (self.gamma_target[0] <= net_gamma <= self.gamma_target[1]),
            'vega': not (self.vega_target[0] <= net_vega <= self.vega_target[1]),
            'theta': net_theta < self.theta_min
        }
        
        return out_of_range
    
    def generate_hedge_recommendations(
        self,
        net_delta: float,
        net_gamma: float,
        net_theta: float,
        net_vega: float,
        current_price: float,
        current_iv: float = 20.0
    ) -> List[HedgeRecommendation]:
        """
        Generate hedge recommendations to bring Greeks back in range
        
        Args:
            net_delta: Current portfolio delta
            net_gamma: Current portfolio gamma
            net_theta: Current portfolio theta
            net_vega: Current portfolio vega
            current_price: Current underlying price
            current_iv: Current implied vol
            
        Returns:
            List of HedgeRecommendation objects, sorted by priority
        """
        
        recommendations = []
        
        # Check what's out of range
        issues = self.analyze_portfolio_greeks(net_delta, net_gamma, net_theta, net_vega)
        
        # 1. DELTA HEDGE (Most Critical)
        if issues['delta']:
            delta_recs = self._hedge_delta(net_delta, current_price)
            recommendations.extend(delta_recs)
        
        # 2. GAMMA HEDGE (Important for large moves)
        if issues['gamma']:
            gamma_recs = self._hedge_gamma(net_gamma, current_price, current_iv)
            recommendations.extend(gamma_recs)
        
        # 3. VEGA HEDGE (Vol risk)
        if issues['vega']:
            vega_recs = self._hedge_vega(net_vega, current_price, current_iv)
            recommendations.extend(vega_recs)
        
        # 4. THETA OPTIMIZATION (If theta too negative)
        if issues['theta']:
            theta_recs = self._optimize_theta(net_theta, current_price)
            recommendations.extend(theta_recs)
        
        # Sort by priority
        recommendations.sort(key=lambda x: x.priority)
        
        return recommendations
    
    def _hedge_delta(
        self,
        net_delta: float,
        current_price: float
    ) -> List[HedgeRecommendation]:
        """Generate delta hedge recommendations"""
        
        recommendations = []
        
        # Calculate how much delta to hedge
        target_delta = 0  # Aim for delta neutral
        delta_to_hedge = net_delta - target_delta
        
        if abs(delta_to_hedge) < 50:
            # Not worth hedging if delta is small
            return recommendations
        
        # Method 1: Hedge with underlying (SPY/SPX)
        # Delta of 1 share = 1, so shares needed = delta_to_hedge
        shares_needed = -delta_to_hedge  # Negative to offset
        
        action = "SELL" if shares_needed < 0 else "BUY"
        qty = abs(int(shares_needed))
        
        cost = qty * current_price
        
        rec = HedgeRecommendation(
            hedge_type=HedgeType.DELTA_HEDGE,
            action=action,
            instrument="SPY",
            quantity=qty,
            delta_change=-delta_to_hedge,
            estimated_cost=cost,
            reason=f"Portfolio delta {net_delta:.0f} is outside target range {self.delta_target}. "
                   f"Hedge with {action} {qty} shares to achieve delta neutrality.",
            priority=1  # Critical
        )
        
        recommendations.append(rec)
        
        # Method 2: Hedge with ATM options (alternative)
        # ATM call has ~0.50 delta, ATM put has ~-0.50 delta
        contracts_needed = int(delta_to_hedge / 50)  # 50 delta per contract (0.50 * 100)
        
        if abs(contracts_needed) > 0:
            if delta_to_hedge > 0:
                # Too much positive delta, sell calls or buy puts
                rec_option = HedgeRecommendation(
                    hedge_type=HedgeType.DELTA_HEDGE,
                    action="SELL",
                    instrument="SPX Call",
                    quantity=abs(contracts_needed),
                    strike=current_price,  # ATM
                    expiration="30 DTE",
                    delta_change=-contracts_needed * 50,
                    estimated_cost=contracts_needed * 500,  # ~$5 premium
                    reason=f"Alternative: Sell {abs(contracts_needed)} ATM calls to reduce positive delta",
                    priority=2
                )
            else:
                # Too much negative delta, buy calls or sell puts
                rec_option = HedgeRecommendation(
                    hedge_type=HedgeType.DELTA_HEDGE,
                    action="BUY",
                    instrument="SPX Call",
                    quantity=abs(contracts_needed),
                    strike=current_price,
                    expiration="30 DTE",
                    delta_change=-contracts_needed * 50,
                    estimated_cost=abs(contracts_needed) * 500,
                    reason=f"Alternative: Buy {abs(contracts_needed)} ATM calls to increase delta",
                    priority=2
                )
            
            recommendations.append(rec_option)
        
        return recommendations
    
    def _hedge_gamma(
        self,
        net_gamma: float,
        current_price: float,
        current_iv: float
    ) -> List[HedgeRecommendation]:
        """Generate gamma hedge recommendations"""
        
        recommendations = []
        
        if abs(net_gamma) < 100:
            return recommendations
        
        # Gamma hedging typically done with options
        # Short gamma positions need long options to hedge (and vice versa)
        
        if net_gamma > self.gamma_target[1]:
            # Too much positive gamma - sell options to reduce
            action = "SELL"
            reason = f"Portfolio gamma {net_gamma:.0f} too high. Sell straddles to reduce."
        else:
            # Too much negative gamma - buy options to hedge
            action = "BUY"
            reason = f"Portfolio gamma {net_gamma:.0f} too negative. Buy straddles to hedge."
        
        # Estimate contracts needed
        # ATM straddle has ~0.05 gamma per contract
        gamma_per_straddle = 5  # Simplified
        contracts = int(abs(net_gamma) / gamma_per_straddle)
        
        rec = HedgeRecommendation(
            hedge_type=HedgeType.GAMMA_HEDGE,
            action=action,
            instrument="SPX Straddle",
            quantity=contracts,
            strike=current_price,
            expiration="30 DTE",
            gamma_change=-net_gamma if action == "SELL" else abs(net_gamma),
            estimated_cost=contracts * 1000,  # ~$10 straddle
            reason=reason,
            priority=2
        )
        
        recommendations.append(rec)
        
        return recommendations
    
    def _hedge_vega(
        self,
        net_vega: float,
        current_price: float,
        current_iv: float
    ) -> List[HedgeRecommendation]:
        """Generate vega hedge recommendations"""
        
        recommendations = []
        
        if abs(net_vega) < 1000:
            return recommendations
        
        # Vega hedging done with longer-dated options
        # Vega is exposure to volatility changes
        
        if net_vega > self.vega_target[1]:
            # Too much positive vega (benefit from rising IV)
            # Hedge by selling options
            action = "SELL"
            reason = f"Portfolio vega {net_vega:.0f} too high. Sell long-dated options to reduce vol exposure."
        else:
            # Too much negative vega (hurt by rising IV)
            # Hedge by buying options
            action = "BUY"
            reason = f"Portfolio vega {net_vega:.0f} too negative. Buy long-dated options to hedge vol risk."
        
        # Longer-dated options have more vega
        # ~100 vega per ATM 90-day straddle
        vega_per_contract = 100
        contracts = int(abs(net_vega) / vega_per_contract)
        
        rec = HedgeRecommendation(
            hedge_type=HedgeType.VEGA_HEDGE,
            action=action,
            instrument="SPX Straddle",
            quantity=contracts,
            strike=current_price,
            expiration="90 DTE",
            vega_change=-net_vega if action == "SELL" else abs(net_vega),
            estimated_cost=contracts * 1500,  # Longer-dated = more expensive
            reason=reason,
            priority=3
        )
        
        recommendations.append(rec)
        
        # Alternative: VIX options/futures
        vix_contracts = int(abs(net_vega) / 500)
        
        if vix_contracts > 0:
            rec_vix = HedgeRecommendation(
                hedge_type=HedgeType.VEGA_HEDGE,
                action="BUY" if net_vega < 0 else "SELL",
                instrument="VIX Futures",
                quantity=vix_contracts,
                vega_change=-net_vega,
                estimated_cost=vix_contracts * current_iv * 1000,
                reason=f"Alternative: Use VIX futures to hedge volatility exposure",
                priority=3
            )
            recommendations.append(rec_vix)
        
        return recommendations
    
    def _optimize_theta(
        self,
        net_theta: float,
        current_price: float
    ) -> List[HedgeRecommendation]:
        """Generate theta optimization recommendations"""
        
        recommendations = []
        
        if net_theta > self.theta_min:
            return recommendations  # Theta is acceptable
        
        # Theta too negative means losing too much to time decay
        # Fix: Close negative theta positions or add positive theta
        
        reason = f"Portfolio theta {net_theta:.0f} below minimum {self.theta_min:.0f}. " \
                 f"Consider closing losing positions or selling premium."
        
        rec = HedgeRecommendation(
            hedge_type=HedgeType.THETA_OPTIMIZATION,
            action="SELL",
            instrument="SPX Iron Condor",
            quantity=1,
            theta_change=-net_theta,  # Add positive theta
            estimated_cost=-300,  # Credit received
            reason=reason,
            priority=3
        )
        
        recommendations.append(rec)
        
        return recommendations
    
    def calculate_hedge_impact(
        self,
        recommendation: HedgeRecommendation,
        current_greeks: Dict[str, float]
    ) -> Dict[str, float]:
        """
        Calculate what Greeks would be after applying hedge
        
        Returns:
            Dict of new Greeks after hedge
        """
        
        new_greeks = current_greeks.copy()
        
        new_greeks['delta'] += recommendation.delta_change
        new_greeks['gamma'] += recommendation.gamma_change
        new_greeks['theta'] += recommendation.theta_change
        new_greeks['vega'] += recommendation.vega_change
        
        return new_greeks
    
    def simulate_hedge_cascade(
        self,
        recommendations: List[HedgeRecommendation],
        current_greeks: Dict[str, float]
    ) -> List[Dict]:
        """
        Simulate applying hedges sequentially
        
        Returns:
            List of Greeks after each hedge step
        """
        
        results = [current_greeks.copy()]
        
        working_greeks = current_greeks.copy()
        
        for rec in recommendations:
            working_greeks = self.calculate_hedge_impact(rec, working_greeks)
            results.append(working_greeks.copy())
        
        return results


def create_hedge_visualization(
    current_greeks: Dict[str, float],
    target_ranges: Dict[str, Tuple[float, float]],
    recommendations: List[HedgeRecommendation]
):
    """Visualize hedging recommendations"""
    import plotly.graph_objs as go
    from plotly.subplots import make_subplots
    
    fig = make_subplots(
        rows=2, cols=2,
        subplot_titles=('Delta Status', 'Gamma Status', 'Vega Status', 'Theta Status')
    )
    
    greeks = ['delta', 'gamma', 'vega', 'theta']
    positions = [(1,1), (1,2), (2,1), (2,2)]
    
    for greek, (row, col) in zip(greeks, positions):
        current = current_greeks.get(greek, 0)
        
        if greek in target_ranges:
            target_min, target_max = target_ranges[greek]
        else:
            target_min, target_max = -1000, 1000
        
        # Gauge chart
        fig.add_trace(
            go.Indicator(
                mode="gauge+number",
                value=current,
                title={'text': greek.upper()},
                gauge={
                    'axis': {'range': [target_min * 2, target_max * 2]},
                    'bar': {'color': "#00cc96" if target_min <= current <= target_max else "#ef553b"},
                    'steps': [
                        {'range': [target_min *  2, target_min], 'color': '#ef553b'},
                        {'range': [target_min, target_max], 'color': '#00cc96'},
                        {'range': [target_max, target_max * 2], 'color': '#ef553b'}
                    ],
                    'threshold': {
                        'line': {'color': "white", 'width': 4},
                        'thickness': 0.75,
                        'value': 0
                    }
                }
            ),
            row=row, col=col
        )
    
    fig.update_layout(
        title="Portfolio Greeks Status",
        height=600,
        template='plotly_dark',
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117'
    )
    
    return fig

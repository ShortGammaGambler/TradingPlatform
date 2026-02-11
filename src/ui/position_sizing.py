"""
Position Sizing using Kelly Criterion
Implements fractional Kelly for optimal risk-adjusted position sizing
"""

import numpy as np
import pandas as pd
from typing import Dict, Optional
from dataclasses import dataclass


@dataclass
class PositionSize:
    """Position sizing recommendation"""
    kelly_fraction: float  # Full Kelly percentage
    fractional_kelly: float  # Conservative Kelly (e.g., 10%)
    recommended_size: float  # Dollar amount to risk
    contracts_to_trade: int  # Number of contracts
    risk_per_contract: float  # Risk per contract
    max_loss: float  # Maximum loss on position
    expected_value: float  # Expected value of trade
    win_rate: float  # Required/estimated win rate
    reward_risk_ratio: float  # Reward to risk ratio
    account_risk_pct: float  # Percentage of account at risk


class KellyPositionSizer:
    """
    Kelly Criterion position sizing for options strategies
    
    Kelly Formula: f* = (p * b - q) / b
    where:
        f* = fraction of capital to bet
        p = probability of winning
        q = probability of losing (1-p)
        b = ratio of win to loss (reward/risk)
    
    For options, we use fractional Kelly (typically 10-25% of full Kelly)
    to account for estimation errors and reduce volatility
    """
    
    def __init__(
        self,
        account_balance: float,
        kelly_fraction: float = 0.10,  # 10% fractional Kelly (conservative)
        max_risk_per_trade: float = 0.02,  # Max 2% account risk per trade
    ):
        """
        Initialize Kelly sizer
        
        Args:
            account_balance: Total account value
            kelly_fraction: Fraction of full Kelly to use (0.10 = 10%)
            max_risk_per_trade: Maximum portfolio risk per trade (0.02 = 2%)
        """
        self.account_balance = account_balance
        self.kelly_fraction = kelly_fraction
        self.max_risk_per_trade = max_risk_per_trade
    
    def calculate_position_size(
        self,
        win_probability: float,
        reward_risk_ratio: float,
        risk_per_contract: float,
        confidence: float = 70,
    ) -> PositionSize:
        """
        Calculate optimal position size using fractional Kelly
        
        Args:
            win_probability: Probability of profitable trade (0-1)
            reward_risk_ratio: Ratio of potential profit to risk
            risk_per_contract: Maximum risk per contract ($)
            confidence: Confidence in estimates (0-100), adjusts Kelly fraction
            
        Returns:
            PositionSize with recommendations
        """
        
        # Kelly Criterion calculation
        # f* = (p * b - q) / b
        p = win_probability
        q = 1 - p
        b = reward_risk_ratio
        
        # Calculate full Kelly
        if b > 0:
            full_kelly = (p * b - q) / b
        else:
            full_kelly = 0
        
        # Ensure Kelly is positive (only bet if edge exists)
        full_kelly = max(0, full_kelly)
        
        # Apply fractional Kelly with confidence adjustment
        confidence_factor = confidence / 100
        adjusted_kelly_fraction = self.kelly_fraction * confidence_factor
        
        kelly_pct = full_kelly * adjusted_kelly_fraction
        
        # Calculate dollar amounts
        kelly_dollars = self.account_balance * kelly_pct
        
        # Apply maximum risk constraint
        max_risk_dollars = self.account_balance * self.max_risk_per_trade
        recommended_risk = min(kelly_dollars, max_risk_dollars)
        
        # Calculate number of contracts
        if risk_per_contract > 0:
            contracts = int(recommended_risk / risk_per_contract)
        else:
            contracts = 0
        
        # Ensure at least 1 contract if Kelly suggests position
        if kelly_pct > 0 and contracts == 0 and risk_per_contract < max_risk_dollars:
            contracts = 1
        
        # Calculate actual position metrics
        actual_risk = contracts * risk_per_contract
        account_risk_pct = (actual_risk / self.account_balance) * 100
        
        # Expected value
        expected_value = (p * (risk_per_contract * b) - q * risk_per_contract) * contracts
        
        return PositionSize(
            kelly_fraction=full_kelly * 100,
            fractional_kelly=kelly_pct * 100,
            recommended_size=recommended_risk,
            contracts_to_trade=contracts,
            risk_per_contract=risk_per_contract,
            max_loss=actual_risk,
            expected_value=expected_value,
            win_rate=p * 100,
            reward_risk_ratio=b,
            account_risk_pct=account_risk_pct
        )
    
    def calculate_strategy_sizing(
        self,
        strategy_name: str,
        confidence: float,
        max_loss_per_contract: float,
        max_profit_per_contract: float,
        current_market_conditions: str = "NORMAL"
    ) -> PositionSize:
        """
        Calculate position size for a specific options strategy
        
        Args:
            strategy_name: Name of the strategy
            confidence: Strategy confidence score (0-100)
            max_loss_per_contract: Maximum loss per spread/strategy
            max_profit_per_contract: Maximum profit per spread/strategy
            current_market_conditions: Market environment
            
        Returns:
            PositionSize recommendation
        """
        
        # Estimate win probability based on strategy and confidence
        win_prob = self._estimate_win_probability(
            strategy_name,
            confidence,
            current_market_conditions
        )
        
        # Calculate reward/risk ratio
        if max_loss_per_contract > 0:
            rr_ratio = max_profit_per_contract / max_loss_per_contract
        else:
            rr_ratio = 1.0
        
        return self.calculate_position_size(
            win_probability=win_prob,
            reward_risk_ratio=rr_ratio,
            risk_per_contract=max_loss_per_contract,
            confidence=confidence
        )
    
    def _estimate_win_probability(
        self,
        strategy_name: str,
        confidence: float,
        market_conditions: str
    ) -> float:
        """
        Estimate win probability based on strategy type and conditions
        
        This is a simplified model - in production, use backtested data
        """
        
        # Base probabilities for different strategy types
        base_probs = {
            'iron_condor': 0.70,
            'iron_butterfly': 0.65,
            'short_strangle': 0.68,
            'credit_spread': 0.60,
            'debit_spread': 0.50,
            'long_call': 0.35,
            'long_put': 0.35,
            'straddle': 0.40,
            'calendar': 0.55,
            'jade_lizard': 0.65,
            'butterfly': 0.45,
            'ratio_spread': 0.50,
        }
        
        # Find matching base probability
        base_prob = 0.50  # Default
        for key, prob in base_probs.items():
            if key in strategy_name.lower().replace('_', ' '):
                base_prob = prob
                break
        
        # Adjust based on confidence (higher confidence = higher win rate)
        confidence_adjustment = (confidence - 50) / 100 * 0.15  # Max ±15%
        
        # Adjust based on market conditions
        condition_adjustment = 0
        if market_conditions == "FAVORABLE":
            condition_adjustment = 0.05
        elif market_conditions == "UNFAVORABLE":
            condition_adjustment = -0.05
        
        # Calculate final probability
        win_prob = base_prob + confidence_adjustment + condition_adjustment
        
        # Clamp between 0.20 and 0.85
        win_prob = max(0.20, min(0.85, win_prob))
        
        return win_prob
    
    def adjust_for_portfolio(
        self,
        existing_positions: list,
        new_position_delta: float
    ) -> float:
        """
        Adjust position size based on existing portfolio delta
        Prevents over-concentration
        """
        
        # Calculate total portfolio delta
        total_delta = sum([pos.get('delta', 0) for pos in existing_positions])
        
        # Add proposed position delta
        new_total_delta = total_delta + new_position_delta
        
        # If portfolio delta would exceed threshold, reduce size
        max_portfolio_delta = self.account_balance * 0.30  # Max 30% delta exposure
        
        if abs(new_total_delta) > max_portfolio_delta:
            reduction_factor = max_portfolio_delta / abs(new_total_delta)
            return reduction_factor
        
        return 1.0  # No adjustment needed


class RiskManager:
    """
    Comprehensive risk management for options portfolio
    """
    
    def __init__(self, account_balance: float):
        self.account_balance = account_balance
        self.max_portfolio_delta = 0.30  # Max 30% delta
        self.max_portfolio_vega = 0.10  # Max 10% vega
        self.max_portfolio_theta = 0.05  # Max 5% theta (daily)
        self.max_single_position = 0.10  # Max 10% in single position
    
    def validate_position(
        self,
        position_greeks: Dict[str, float],
        portfolio_greeks: Dict[str, float],
        position_size: float
    ) -> Dict[str, any]:
        """
        Validate if new position meets risk parameters
        
        Returns dict with 'approved': bool and 'violations': list
        """
        
        violations = []
        
        # Check position size
        if position_size > self.account_balance * self.max_single_position:
            violations.append(f"Position size exceeds {self.max_single_position*100}% limit")
        
        # Check delta
        new_delta = portfolio_greeks.get('delta', 0) + position_greeks.get('delta', 0)
        if abs(new_delta) > self.account_balance * self.max_portfolio_delta:
            violations.append(f"Portfolio delta would exceed {self.max_portfolio_delta*100}% limit")
        
        # Check vega
        new_vega = portfolio_greeks.get('vega', 0) + position_greeks.get('vega', 0)
        if abs(new_vega) > self.account_balance * self.max_portfolio_vega:
            violations.append(f"Portfolio vega would exceed {self.max_portfolio_vega*100}% limit")
        
        # Check theta
        new_theta = portfolio_greeks.get('theta', 0) + position_greeks.get('theta', 0)
        if abs(new_theta) > self.account_balance * self.max_portfolio_theta:
            violations.append(f"Portfolio theta would exceed {self.max_portfolio_theta*100}% limit")
        
        return {
            'approved': len(violations) == 0,
            'violations': violations,
            'new_portfolio_greeks': {
                'delta': new_delta,
                'vega': new_vega,
                'theta': new_theta,
            }
        }
    
    def calculate_var(
        self,
        portfolio_value: float,
        portfolio_delta: float,
        underlying_volatility: float,
        confidence_level: float = 0.95,
        time_horizon_days: int = 1
    ) -> float:
        """
        Calculate Value at Risk (VaR) for the portfolio
        
        Returns maximum expected loss at given confidence level
        """
        
        from scipy import stats
        
        # Z-score for confidence level
        z_score = stats.norm.ppf(confidence_level)
        
        # Daily volatility of underlying
        daily_vol = underlying_volatility / 100 / np.sqrt(252)
        
        # Expected portfolio move
        portfolio_std = abs(portfolio_delta) * daily_vol * np.sqrt(time_horizon_days)
        
        # VaR
        var = z_score * portfolio_std
        
        return var

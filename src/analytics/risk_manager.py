"""
Risk Management Module
Portfolio-level risk controls, position sizing, and Greeks management.
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from enum import Enum
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskLevel(Enum):
    """Risk level classification."""
    LOW = "low"
    MODERATE = "moderate"
    ELEVATED = "elevated"
    HIGH = "high"
    EXTREME = "extreme"


@dataclass
class PositionGreeks:
    """Greeks for a single position."""
    symbol: str
    delta: float = 0.0
    gamma: float = 0.0
    theta: float = 0.0
    vega: float = 0.0
    rho: float = 0.0

    # Second order
    vanna: float = 0.0  # d(delta)/d(vol)
    charm: float = 0.0  # d(delta)/d(time)
    vomma: float = 0.0  # d(vega)/d(vol)

    notional: float = 0.0
    contracts: int = 0


@dataclass
class PortfolioRisk:
    """Aggregated portfolio risk metrics."""
    # Net Greeks
    net_delta: float = 0.0
    net_gamma: float = 0.0
    net_theta: float = 0.0
    net_vega: float = 0.0

    # Delta-adjusted exposure
    beta_weighted_delta: float = 0.0

    # Risk metrics
    var_95: float = 0.0      # 1-day 95% VaR
    var_99: float = 0.0      # 1-day 99% VaR
    expected_shortfall: float = 0.0  # CVaR / Expected Tail Loss

    # Concentration
    largest_position_pct: float = 0.0
    top_3_concentration_pct: float = 0.0

    # Margin
    estimated_margin: float = 0.0
    margin_utilization_pct: float = 0.0

    # Overall assessment
    risk_level: RiskLevel = RiskLevel.LOW
    warnings: List[str] = field(default_factory=list)


class RiskManager:
    """
    Comprehensive risk management for options portfolios.

    Handles:
    - Position sizing (Kelly, fixed fractional, volatility-adjusted)
    - Portfolio Greeks aggregation
    - VaR/CVaR calculations
    - Concentration limits
    - Stop-loss management
    - Correlation risk
    """

    def __init__(self, account_value: float, max_risk_per_trade: float = 0.02,
                 max_portfolio_risk: float = 0.20, max_position_size: float = 0.10):
        """
        Initialize risk manager.

        Args:
            account_value: Total account value
            max_risk_per_trade: Maximum risk per trade as fraction (default 2%)
            max_portfolio_risk: Maximum total portfolio risk (default 20%)
            max_position_size: Maximum single position size (default 10%)
        """
        self.account_value = account_value
        self.max_risk_per_trade = max_risk_per_trade
        self.max_portfolio_risk = max_portfolio_risk
        self.max_position_size = max_position_size

        self.positions: Dict[str, PositionGreeks] = {}

        # Risk limits
        self.max_delta = account_value * 0.50  # 50% of account in delta terms
        self.max_gamma = account_value * 0.10  # 10% gamma exposure
        self.max_vega = account_value * 0.05   # 5% vega exposure
        self.max_theta = -account_value * 0.005  # Max -0.5%/day theta bleed

        logger.info(f"Risk Manager initialized. Account: ${account_value:,.2f}")

    # =========================================================================
    # POSITION SIZING
    # =========================================================================

    def calculate_position_size_fixed_fractional(self, entry_price: float,
                                                  stop_loss: float) -> int:
        """
        Fixed fractional position sizing.

        Risk a fixed percentage of account on each trade.

        Args:
            entry_price: Entry price per share/contract
            stop_loss: Stop loss price

        Returns:
            Number of shares/contracts
        """
        risk_per_share = abs(entry_price - stop_loss)
        if risk_per_share == 0:
            return 0

        dollar_risk = self.account_value * self.max_risk_per_trade
        shares = int(dollar_risk / risk_per_share)

        # Check against max position size
        position_value = shares * entry_price
        if position_value > self.account_value * self.max_position_size:
            shares = int((self.account_value * self.max_position_size) / entry_price)

        return max(0, shares)

    def calculate_position_size_kelly(self, win_rate: float,
                                       avg_win: float, avg_loss: float,
                                       entry_price: float,
                                       kelly_fraction: float = 0.5) -> int:
        """
        Kelly Criterion position sizing.

        Optimal bet size for maximizing long-term growth.
        Using fractional Kelly (typically 0.25-0.5) to reduce volatility.

        Args:
            win_rate: Historical win rate (0-1)
            avg_win: Average winning trade profit
            avg_loss: Average losing trade loss (positive number)
            entry_price: Entry price per share
            kelly_fraction: Fraction of full Kelly to use (default 0.5)

        Returns:
            Number of shares/contracts
        """
        if avg_loss == 0 or win_rate <= 0 or win_rate >= 1:
            return 0

        # Kelly formula: f* = (bp - q) / b
        # where b = avg_win/avg_loss, p = win_rate, q = 1-win_rate
        b = avg_win / avg_loss
        p = win_rate
        q = 1 - p

        full_kelly = (b * p - q) / b

        if full_kelly <= 0:
            logger.warning("Kelly suggests no position (negative edge)")
            return 0

        # Apply fractional Kelly
        fraction = full_kelly * kelly_fraction

        # Don't exceed max position size
        fraction = min(fraction, self.max_position_size)

        position_value = self.account_value * fraction
        shares = int(position_value / entry_price)

        logger.info(f"Kelly sizing: {win_rate:.1%} WR, {avg_win/avg_loss:.2f} W/L ratio -> "
                   f"{fraction:.1%} allocation ({shares} shares)")

        return shares

    def calculate_position_size_volatility_adjusted(self, entry_price: float,
                                                     atr: float,
                                                     atr_multiplier: float = 2.0) -> int:
        """
        Volatility-adjusted position sizing using ATR.

        Position size inversely proportional to volatility.

        Args:
            entry_price: Entry price
            atr: Average True Range
            atr_multiplier: Multiplier for ATR-based stop (default 2x)

        Returns:
            Number of shares
        """
        # Risk is ATR * multiplier
        risk_per_share = atr * atr_multiplier
        dollar_risk = self.account_value * self.max_risk_per_trade
        shares = int(dollar_risk / risk_per_share)

        # Check max position
        max_shares = int((self.account_value * self.max_position_size) / entry_price)
        return min(shares, max_shares)

    # =========================================================================
    # PORTFOLIO GREEKS
    # =========================================================================

    def add_position(self, position: PositionGreeks):
        """Add or update a position."""
        self.positions[position.symbol] = position
        logger.info(f"Added position: {position.symbol} "
                   f"(Delta: {position.delta:.2f}, Gamma: {position.gamma:.4f})")

    def remove_position(self, symbol: str):
        """Remove a position."""
        if symbol in self.positions:
            del self.positions[symbol]
            logger.info(f"Removed position: {symbol}")

    def calculate_portfolio_greeks(self) -> Dict[str, float]:
        """
        Aggregate Greeks across all positions.

        Returns:
            Dict with net portfolio Greeks
        """
        net_delta = sum(p.delta for p in self.positions.values())
        net_gamma = sum(p.gamma for p in self.positions.values())
        net_theta = sum(p.theta for p in self.positions.values())
        net_vega = sum(p.vega for p in self.positions.values())
        net_rho = sum(p.rho for p in self.positions.values())

        return {
            'net_delta': net_delta,
            'net_gamma': net_gamma,
            'net_theta': net_theta,
            'net_vega': net_vega,
            'net_rho': net_rho,
            'delta_dollars': net_delta * 100,  # Assuming $100 notional per delta point
        }

    # =========================================================================
    # VAR / RISK METRICS
    # =========================================================================

    def calculate_var(self, returns: np.ndarray, confidence: float = 0.95) -> float:
        """
        Calculate Value at Risk using historical simulation.

        Args:
            returns: Array of historical returns
            confidence: Confidence level (default 95%)

        Returns:
            VaR as positive number (potential loss)
        """
        if len(returns) < 30:
            logger.warning("Insufficient data for reliable VaR calculation")
            return 0

        # Historical VaR
        var = -np.percentile(returns, (1 - confidence) * 100)
        return var * self.account_value

    def calculate_cvar(self, returns: np.ndarray, confidence: float = 0.95) -> float:
        """
        Calculate Conditional VaR (Expected Shortfall).

        Average loss in the worst (1-confidence)% of cases.

        Args:
            returns: Array of historical returns
            confidence: Confidence level

        Returns:
            CVaR as positive number
        """
        if len(returns) < 30:
            return 0

        var_threshold = np.percentile(returns, (1 - confidence) * 100)
        tail_returns = returns[returns <= var_threshold]

        if len(tail_returns) == 0:
            return self.calculate_var(returns, confidence)

        cvar = -np.mean(tail_returns)
        return cvar * self.account_value

    def calculate_portfolio_var(self, position_returns: Dict[str, np.ndarray],
                                correlations: Optional[pd.DataFrame] = None) -> float:
        """
        Calculate portfolio VaR considering correlations.

        Args:
            position_returns: Dict mapping symbols to return arrays
            correlations: Correlation matrix (uses empirical if not provided)

        Returns:
            Portfolio VaR
        """
        if not position_returns:
            return 0

        # Calculate individual VaRs
        individual_vars = {}
        for symbol, returns in position_returns.items():
            individual_vars[symbol] = self.calculate_var(returns)

        # Simple sum (worst case - perfect correlation)
        undiversified_var = sum(individual_vars.values())

        # If we have correlations, calculate diversified VaR
        if correlations is not None:
            # ... implement correlation-adjusted VaR
            pass

        return undiversified_var

    # =========================================================================
    # RISK ASSESSMENT
    # =========================================================================

    def assess_portfolio_risk(self) -> PortfolioRisk:
        """
        Comprehensive portfolio risk assessment.

        Returns:
            PortfolioRisk object with all metrics and warnings
        """
        risk = PortfolioRisk()
        warnings = []

        # Calculate net Greeks
        greeks = self.calculate_portfolio_greeks()
        risk.net_delta = greeks['net_delta']
        risk.net_gamma = greeks['net_gamma']
        risk.net_theta = greeks['net_theta']
        risk.net_vega = greeks['net_vega']

        # Check Greeks limits
        if abs(risk.net_delta) > self.max_delta:
            warnings.append(f"Delta exposure ({risk.net_delta:.0f}) exceeds limit ({self.max_delta:.0f})")

        if abs(risk.net_gamma) > self.max_gamma:
            warnings.append(f"Gamma exposure exceeds limit")

        if abs(risk.net_vega) > self.max_vega:
            warnings.append(f"Vega exposure exceeds limit")

        if risk.net_theta < self.max_theta:
            warnings.append(f"Theta bleed ({risk.net_theta:.2f}/day) exceeds limit")

        # Concentration analysis
        if self.positions:
            notionals = {sym: p.notional for sym, p in self.positions.items()}
            total_notional = sum(notionals.values())

            if total_notional > 0:
                sorted_positions = sorted(notionals.items(), key=lambda x: x[1], reverse=True)
                risk.largest_position_pct = sorted_positions[0][1] / total_notional * 100

                if len(sorted_positions) >= 3:
                    top_3 = sum(p[1] for p in sorted_positions[:3])
                    risk.top_3_concentration_pct = top_3 / total_notional * 100

                if risk.largest_position_pct > 25:
                    warnings.append(f"Largest position is {risk.largest_position_pct:.1f}% of portfolio")

        # Determine overall risk level
        if len(warnings) == 0:
            risk.risk_level = RiskLevel.LOW
        elif len(warnings) <= 2:
            risk.risk_level = RiskLevel.MODERATE
        elif len(warnings) <= 4:
            risk.risk_level = RiskLevel.ELEVATED
        else:
            risk.risk_level = RiskLevel.HIGH

        risk.warnings = warnings
        return risk

    def suggest_hedges(self, risk: PortfolioRisk) -> List[str]:
        """
        Suggest hedging actions based on current risk profile.

        Args:
            risk: Current PortfolioRisk assessment

        Returns:
            List of suggested hedging actions
        """
        suggestions = []

        # Delta hedge suggestions
        if risk.net_delta > self.max_delta * 0.8:
            shares_to_short = int(risk.net_delta / 100)  # Approximate
            suggestions.append(f"Consider shorting ~{shares_to_short} SPY shares to reduce delta")
        elif risk.net_delta < -self.max_delta * 0.8:
            shares_to_buy = int(abs(risk.net_delta) / 100)
            suggestions.append(f"Consider buying ~{shares_to_buy} SPY shares to reduce negative delta")

        # Gamma suggestions
        if risk.net_gamma < -self.max_gamma * 0.5:
            suggestions.append("High negative gamma - consider buying straddles/strangles for protection")

        # Vega suggestions
        if risk.net_vega > self.max_vega * 0.8:
            suggestions.append("High vega exposure - consider selling premium or buying put spreads")
        elif risk.net_vega < -self.max_vega * 0.8:
            suggestions.append("High short vega - vulnerable to vol spike, consider buying VIX calls")

        # Theta suggestions
        if risk.net_theta < self.max_theta * 0.8:
            suggestions.append(f"Theta bleed is ${abs(risk.net_theta):.0f}/day - review short premium positions")

        return suggestions

    # =========================================================================
    # STOP LOSS MANAGEMENT
    # =========================================================================

    def calculate_stop_levels(self, entry_price: float,
                              method: str = "atr",
                              atr: float = None,
                              risk_reward: float = 2.0) -> Tuple[float, float]:
        """
        Calculate stop loss and take profit levels.

        Args:
            entry_price: Entry price
            method: 'atr', 'percent', 'gamma_flip'
            atr: ATR value (required for 'atr' method)
            risk_reward: Target risk/reward ratio

        Returns:
            Tuple of (stop_loss, take_profit)
        """
        if method == "atr" and atr:
            stop_distance = atr * 2
            stop_loss = entry_price - stop_distance
            take_profit = entry_price + (stop_distance * risk_reward)

        elif method == "percent":
            stop_pct = 0.02  # 2% stop
            stop_loss = entry_price * (1 - stop_pct)
            take_profit = entry_price * (1 + stop_pct * risk_reward)

        else:
            # Default: 2% stop, 4% target
            stop_loss = entry_price * 0.98
            take_profit = entry_price * 1.04

        return (round(stop_loss, 2), round(take_profit, 2))

    def print_risk_report(self):
        """Print formatted risk report to console."""
        risk = self.assess_portfolio_risk()

        print("\n" + "=" * 60)
        print("PORTFOLIO RISK REPORT")
        print("=" * 60)

        print(f"\nAccount Value: ${self.account_value:,.2f}")
        print(f"Risk Level: {risk.risk_level.value.upper()}")

        print("\n--- Portfolio Greeks ---")
        print(f"Net Delta:  {risk.net_delta:>10.2f}")
        print(f"Net Gamma:  {risk.net_gamma:>10.4f}")
        print(f"Net Theta:  {risk.net_theta:>10.2f} /day")
        print(f"Net Vega:   {risk.net_vega:>10.2f}")

        print("\n--- Concentration ---")
        print(f"Largest Position: {risk.largest_position_pct:.1f}%")
        print(f"Top 3 Positions:  {risk.top_3_concentration_pct:.1f}%")

        if risk.warnings:
            print("\n--- WARNINGS ---")
            for w in risk.warnings:
                print(f"  [!] {w}")

        suggestions = self.suggest_hedges(risk)
        if suggestions:
            print("\n--- Suggested Actions ---")
            for s in suggestions:
                print(f"  -> {s}")

        print("\n" + "=" * 60)


if __name__ == "__main__":
    # Demo
    rm = RiskManager(account_value=100000)

    # Add some positions
    rm.add_position(PositionGreeks(
        symbol="SPY_C_500",
        delta=50,
        gamma=0.05,
        theta=-25,
        vega=100,
        notional=5000,
        contracts=10
    ))

    rm.add_position(PositionGreeks(
        symbol="SPY_P_480",
        delta=-30,
        gamma=0.03,
        theta=-15,
        vega=60,
        notional=3000,
        contracts=5
    ))

    rm.print_risk_report()

    # Position sizing example
    shares = rm.calculate_position_size_fixed_fractional(
        entry_price=500,
        stop_loss=490
    )
    print(f"\nPosition size (fixed fractional): {shares} shares")

    shares_kelly = rm.calculate_position_size_kelly(
        win_rate=0.55,
        avg_win=200,
        avg_loss=100,
        entry_price=500
    )
    print(f"Position size (half-Kelly): {shares_kelly} shares")

"""
POSITION SIZING SYSTEM
Kelly Criterion with Multiple Adjustments
Built for: Travis @ Trav's Trader Lounge

This module implements institutional-grade position sizing:
1. Kelly Criterion base calculation
2. Half-Kelly for safety
3. Volatility adjustment
4. Correlation penalty
5. Regime adjustment
6. Portfolio heat cap

The goal: Optimal sizing that maximizes growth while managing drawdown.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import math

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class PositionSize:
    """Calculated position size with all adjustments"""
    symbol: str
    timestamp: datetime

    # Inputs
    portfolio_value: float
    win_rate: float
    reward_risk_ratio: float
    current_iv_percentile: float
    correlation_to_portfolio: float
    regime: str

    # Calculations
    raw_kelly: float
    half_kelly: float
    vol_adjusted: float
    correlation_adjusted: float
    regime_adjusted: float
    capped_size_pct: float

    # Output
    position_size_dollars: float
    risk_amount_dollars: float
    contracts_at_price: int = 0
    shares_at_price: int = 0

    # Metadata
    adjustments_applied: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)


@dataclass
class PortfolioHeat:
    """Current portfolio risk exposure"""
    timestamp: datetime
    total_heat_pct: float
    positions: Dict[str, float]  # symbol -> heat %
    remaining_capacity_pct: float
    at_limit: bool
    warnings: List[str] = field(default_factory=list)


class PositionSizer:
    """
    Position sizing using modified Kelly Criterion.

    Kelly Formula: f* = W - (1-W)/R
    Where:
    - f* = fraction of portfolio to bet
    - W = win rate (probability of winning)
    - R = reward/risk ratio

    We apply multiple dampening factors:
    1. Half-Kelly (0.5x) - Reduces volatility of equity curve
    2. IV adjustment - Reduce size when IV is elevated
    3. Correlation penalty - Reduce for correlated positions
    4. Regime adjustment - Reduce in high-risk regimes
    5. Hard cap - Never exceed max position size
    """

    def __init__(
        self,
        portfolio_value: float,
        max_position_pct: float = 5.0,
        max_heat_pct: float = 20.0,
        kelly_fraction: float = 0.5,
        enable_correlation_penalty: bool = True
    ):
        self.portfolio_value = portfolio_value
        self.max_position_pct = max_position_pct
        self.max_heat_pct = max_heat_pct
        self.kelly_fraction = kelly_fraction
        self.enable_correlation_penalty = enable_correlation_penalty

        # Current positions for heat tracking
        self._positions: Dict[str, float] = {}  # symbol -> risk amount

        logger.info(f"Position Sizer initialized: ${portfolio_value:,.0f} portfolio")

    @classmethod
    def from_config(cls, config, portfolio_value: float = 100_000) -> "PositionSizer":
        """Create PositionSizer from unified Config object."""
        return cls(
            portfolio_value=portfolio_value,
            max_position_pct=config.risk.max_position_size_pct,
            max_heat_pct=config.risk.max_portfolio_heat_pct,
            kelly_fraction=config.risk.kelly_fraction,
        )

    def update_portfolio_value(self, value: float):
        """Update portfolio value"""
        self.portfolio_value = value
        logger.info(f"Portfolio value updated: ${value:,.0f}")

    def calculate_kelly(
        self,
        win_rate: float,
        reward_risk_ratio: float
    ) -> float:
        """
        Calculate raw Kelly fraction.

        Args:
            win_rate: Historical win rate (0-1)
            reward_risk_ratio: Average win / Average loss

        Returns:
            Kelly fraction (can be negative if edge is negative)
        """
        if reward_risk_ratio <= 0:
            return 0

        # Kelly: W - (1-W)/R
        kelly = win_rate - (1 - win_rate) / reward_risk_ratio

        return kelly

    def calculate_position_size(
        self,
        symbol: str,
        win_rate: float,
        reward_risk_ratio: float,
        iv_percentile: float = 50.0,
        correlation: float = 0.0,
        regime: str = "NORMAL",
        entry_price: Optional[float] = None,
        contract_multiplier: int = 100
    ) -> PositionSize:
        """
        Calculate optimal position size with all adjustments.

        Args:
            symbol: Trading symbol
            win_rate: Historical win rate (0-1)
            reward_risk_ratio: Average win / Average loss
            iv_percentile: Current IV percentile (0-100)
            correlation: Correlation to existing portfolio (-1 to 1)
            regime: Market regime (POSITIVE_GAMMA, NEGATIVE_GAMMA, HIGH_VOL, etc.)
            entry_price: Entry price for contract/share calculation
            contract_multiplier: Multiplier for options (usually 100)

        Returns:
            PositionSize with all calculations and adjustments
        """
        adjustments = []
        warnings = []

        # 1. Raw Kelly
        raw_kelly = self.calculate_kelly(win_rate, reward_risk_ratio)

        if raw_kelly <= 0:
            warnings.append("Negative edge - no position recommended")
            return self._zero_position(symbol, win_rate, reward_risk_ratio, warnings)

        # 2. Half Kelly (or configured fraction)
        half_kelly = raw_kelly * self.kelly_fraction
        adjustments.append(f"Kelly fraction: {self.kelly_fraction}")

        # 3. IV Adjustment
        # High IV = reduce size (more expensive, higher risk)
        if iv_percentile > 80:
            iv_multiplier = 0.6
            adjustments.append(f"High IV ({iv_percentile:.0f}%ile): 0.6x")
        elif iv_percentile > 60:
            iv_multiplier = 0.8
            adjustments.append(f"Elevated IV ({iv_percentile:.0f}%ile): 0.8x")
        elif iv_percentile < 20:
            iv_multiplier = 1.1  # Slight boost in low IV
            adjustments.append(f"Low IV ({iv_percentile:.0f}%ile): 1.1x")
        else:
            iv_multiplier = 1.0

        vol_adjusted = half_kelly * iv_multiplier

        # 4. Correlation Penalty
        if self.enable_correlation_penalty and abs(correlation) > 0.5:
            corr_multiplier = 1 - (abs(correlation) - 0.5)
            corr_multiplier = max(0.5, corr_multiplier)  # Floor at 50%
            adjustments.append(f"Correlation ({correlation:.2f}): {corr_multiplier:.2f}x")
        else:
            corr_multiplier = 1.0

        correlation_adjusted = vol_adjusted * corr_multiplier

        # 5. Regime Adjustment
        regime_multipliers = {
            "DEEP_POSITIVE": 1.0,       # Full size
            "POSITIVE_GAMMA": 1.0,      # Full size
            "NEUTRAL": 0.9,             # Slight reduction
            "NEGATIVE_GAMMA": 0.75,     # Reduced
            "DEEP_NEGATIVE": 0.5,       # Half size
            "HIGH_VOL": 0.6,            # Reduced
            "EXTREME_VOL": 0.3,         # Minimal
            "NORMAL": 1.0               # Default
        }

        regime_mult = regime_multipliers.get(regime.upper(), 0.9)
        if regime_mult < 1.0:
            adjustments.append(f"Regime ({regime}): {regime_mult}x")

        regime_adjusted = correlation_adjusted * regime_mult

        # 6. Cap to maximum
        capped = min(regime_adjusted * 100, self.max_position_pct)

        if capped < regime_adjusted * 100:
            adjustments.append(f"Capped to max: {self.max_position_pct}%")

        # 7. Check portfolio heat
        current_heat = self.get_portfolio_heat()
        remaining = self.max_heat_pct - current_heat.total_heat_pct

        if capped > remaining:
            capped = max(0, remaining)
            warnings.append(f"Reduced due to portfolio heat: {current_heat.total_heat_pct:.1f}%")

        # Calculate dollar amounts
        position_dollars = self.portfolio_value * (capped / 100)

        # Risk amount (assuming max loss = position size for simplicity)
        # In practice, this would be calculated based on stop loss
        risk_dollars = position_dollars * 0.05  # Assume 5% stop

        # Calculate contracts/shares if entry price provided
        contracts = 0
        shares = 0

        if entry_price and entry_price > 0:
            contracts = int(position_dollars / (entry_price * contract_multiplier))
            shares = int(position_dollars / entry_price)

        return PositionSize(
            symbol=symbol,
            timestamp=datetime.now(),
            portfolio_value=self.portfolio_value,
            win_rate=win_rate,
            reward_risk_ratio=reward_risk_ratio,
            current_iv_percentile=iv_percentile,
            correlation_to_portfolio=correlation,
            regime=regime,
            raw_kelly=raw_kelly * 100,
            half_kelly=half_kelly * 100,
            vol_adjusted=vol_adjusted * 100,
            correlation_adjusted=correlation_adjusted * 100,
            regime_adjusted=regime_adjusted * 100,
            capped_size_pct=capped,
            position_size_dollars=position_dollars,
            risk_amount_dollars=risk_dollars,
            contracts_at_price=contracts,
            shares_at_price=shares,
            adjustments_applied=adjustments,
            warnings=warnings
        )

    def _zero_position(
        self,
        symbol: str,
        win_rate: float,
        rr_ratio: float,
        warnings: List[str]
    ) -> PositionSize:
        """Return zero position when no trade recommended"""
        return PositionSize(
            symbol=symbol,
            timestamp=datetime.now(),
            portfolio_value=self.portfolio_value,
            win_rate=win_rate,
            reward_risk_ratio=rr_ratio,
            current_iv_percentile=50,
            correlation_to_portfolio=0,
            regime="NORMAL",
            raw_kelly=0,
            half_kelly=0,
            vol_adjusted=0,
            correlation_adjusted=0,
            regime_adjusted=0,
            capped_size_pct=0,
            position_size_dollars=0,
            risk_amount_dollars=0,
            adjustments_applied=[],
            warnings=warnings
        )

    def add_position(self, symbol: str, risk_amount: float):
        """Add position to heat tracking"""
        self._positions[symbol] = risk_amount
        logger.info(f"Added position: {symbol} = ${risk_amount:,.0f} risk")

    def remove_position(self, symbol: str):
        """Remove position from heat tracking"""
        if symbol in self._positions:
            del self._positions[symbol]
            logger.info(f"Removed position: {symbol}")

    def get_portfolio_heat(self) -> PortfolioHeat:
        """Get current portfolio heat (total risk exposure)"""
        total_risk = sum(self._positions.values())
        heat_pct = (total_risk / self.portfolio_value * 100) if self.portfolio_value else 0

        remaining = self.max_heat_pct - heat_pct
        at_limit = heat_pct >= self.max_heat_pct

        warnings = []
        if heat_pct > self.max_heat_pct * 0.8:
            warnings.append(f"Approaching heat limit: {heat_pct:.1f}%")
        if at_limit:
            warnings.append("At heat limit - no new positions")

        position_pcts = {
            sym: (risk / self.portfolio_value * 100)
            for sym, risk in self._positions.items()
        }

        return PortfolioHeat(
            timestamp=datetime.now(),
            total_heat_pct=heat_pct,
            positions=position_pcts,
            remaining_capacity_pct=max(0, remaining),
            at_limit=at_limit,
            warnings=warnings
        )

    def generate_sizing_report(self, size: PositionSize) -> str:
        """Generate formatted sizing report"""
        lines = []
        lines.append("=" * 50)
        lines.append(f"POSITION SIZING: {size.symbol}")
        lines.append("=" * 50)
        lines.append("")

        lines.append("INPUTS:")
        lines.append(f"  Portfolio Value:  ${size.portfolio_value:>12,.0f}")
        lines.append(f"  Win Rate:         {size.win_rate*100:>12.1f}%")
        lines.append(f"  Reward/Risk:      {size.reward_risk_ratio:>12.2f}")
        lines.append(f"  IV Percentile:    {size.current_iv_percentile:>12.0f}%")
        lines.append(f"  Correlation:      {size.correlation_to_portfolio:>12.2f}")
        lines.append(f"  Regime:           {size.regime:>12}")
        lines.append("")

        lines.append("KELLY CALCULATION:")
        lines.append(f"  Raw Kelly:        {size.raw_kelly:>12.2f}%")
        lines.append(f"  Half Kelly:       {size.half_kelly:>12.2f}%")
        lines.append(f"  IV Adjusted:      {size.vol_adjusted:>12.2f}%")
        lines.append(f"  Corr Adjusted:    {size.correlation_adjusted:>12.2f}%")
        lines.append(f"  Regime Adjusted:  {size.regime_adjusted:>12.2f}%")
        lines.append(f"  Final (Capped):   {size.capped_size_pct:>12.2f}%")
        lines.append("")

        lines.append("POSITION SIZE:")
        lines.append(f"  Dollar Amount:    ${size.position_size_dollars:>12,.0f}")
        lines.append(f"  Risk Amount:      ${size.risk_amount_dollars:>12,.0f}")

        if size.contracts_at_price > 0:
            lines.append(f"  Contracts:        {size.contracts_at_price:>12}")

        if size.shares_at_price > 0:
            lines.append(f"  Shares:           {size.shares_at_price:>12}")
        lines.append("")

        if size.adjustments_applied:
            lines.append("ADJUSTMENTS APPLIED:")
            for adj in size.adjustments_applied:
                lines.append(f"  - {adj}")
            lines.append("")

        if size.warnings:
            lines.append("WARNINGS:")
            for warn in size.warnings:
                lines.append(f"  ! {warn}")
            lines.append("")

        lines.append("=" * 50)
        return "\n".join(lines)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("POSITION SIZING SYSTEM")
    print("=" * 60)

    # Initialize with $100k portfolio
    sizer = PositionSizer(
        portfolio_value=100_000,
        max_position_pct=5.0,
        max_heat_pct=20.0,
        kelly_fraction=0.5
    )

    # Calculate size for a trade
    size = sizer.calculate_position_size(
        symbol="SPY",
        win_rate=0.55,           # 55% win rate
        reward_risk_ratio=1.5,   # 1.5:1 R/R
        iv_percentile=65,        # Elevated IV
        correlation=0.3,         # Moderate correlation
        regime="POSITIVE_GAMMA",
        entry_price=3.50,        # Option at $3.50
        contract_multiplier=100
    )

    print(sizer.generate_sizing_report(size))

    # Add some positions and check heat
    sizer.add_position("SPY", 2500)
    sizer.add_position("QQQ", 2000)
    sizer.add_position("NVDA", 1500)

    heat = sizer.get_portfolio_heat()

    print("\nPORTFOLIO HEAT:")
    print(f"  Total Heat: {heat.total_heat_pct:.1f}%")
    print(f"  Remaining Capacity: {heat.remaining_capacity_pct:.1f}%")
    print(f"  At Limit: {heat.at_limit}")

    for sym, pct in heat.positions.items():
        print(f"    {sym}: {pct:.1f}%")

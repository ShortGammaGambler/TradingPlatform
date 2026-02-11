"""
Gamma Exposure (GEX) Calculator
===============================

Proper GEX calculation with configurable methodology.

GEX Formula:
    GEX per strike = Gamma × Open Interest × Multiplier × Spot² / 100

    Note: The Spot² term normalizes gamma (which is per $1 move) to percentage terms.
    Some sources simplify to Gamma × OI × Spot × 100.

Sign Convention (Dealer Perspective):
    - Dealers are NET SHORT options (retail buys, dealers sell)
    - Short Call = Short Gamma (negative GEX contribution)
    - Short Put = Long Gamma (positive GEX contribution)

    Therefore:
    - Call GEX: NEGATIVE (dealers short gamma on calls)
    - Put GEX: POSITIVE (dealers long gamma on puts)

    Total Dealer GEX = Put_GEX - Call_GEX (flipped from market OI perspective)

Author: Production GEX calculation for live trading
"""

import pandas as pd
import numpy as np
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple
from datetime import datetime, date
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


@dataclass
class GEXConfig:
    """Configuration for GEX calculation methodology."""

    # Strike range
    strike_range_pct: float = 10.0  # ±10% from spot

    # Open interest thresholds
    min_oi_threshold: int = 100  # Ignore strikes with OI < 100
    min_volume_threshold: int = 0  # Optional: ignore low volume

    # Expiration weighting
    weight_by_expiration: bool = True
    dte_weights: Dict[int, float] = field(default_factory=lambda: {
        0: 10.0,   # 0DTE: 10x weight (highest gamma impact)
        1: 5.0,    # 1DTE: 5x weight
        2: 3.0,    # 2DTE: 3x weight
        7: 2.0,    # Weekly: 2x weight
        30: 1.0,   # Monthly: 1x weight (baseline)
        60: 0.5,   # 2-month: 0.5x weight
        90: 0.25,  # Quarterly: 0.25x weight
    })

    # Calculation method
    use_dealer_perspective: bool = True  # True = dealer gamma, False = market gamma
    contract_multiplier: int = 100  # Standard equity options

    # Output
    output_in_billions: bool = True


@dataclass
class GEXResult:
    """Results from GEX calculation."""
    timestamp: datetime
    spot_price: float

    # Core metrics
    total_gex: float  # Net gamma exposure
    call_gex: float   # Call contribution
    put_gex: float    # Put contribution

    # Derived levels
    gamma_flip: float      # Price where GEX crosses zero
    max_gamma_strike: float  # Strike with highest gamma
    call_wall: float       # Strike with highest call OI
    put_wall: float        # Strike with highest put OI

    # Distribution
    gex_by_strike: Dict[float, float] = field(default_factory=dict)

    # Metadata
    strikes_used: int = 0
    expirations_used: int = 0
    total_oi_processed: int = 0


class GEXCalculator:
    """
    Production-grade Gamma Exposure calculator.

    Methodology decisions are explicit and configurable.
    """

    def __init__(self, config: GEXConfig = None):
        """
        Initialize calculator with configuration.

        Args:
            config: GEXConfig object defining methodology
        """
        self.config = config or GEXConfig()
        logger.info(f"GEX Calculator initialized")
        logger.info(f"  Strike range: ±{self.config.strike_range_pct}%")
        logger.info(f"  Min OI threshold: {self.config.min_oi_threshold}")
        logger.info(f"  Dealer perspective: {self.config.use_dealer_perspective}")
        logger.info(f"  Expiration weighting: {self.config.weight_by_expiration}")

    def calculate(self,
                  options_chain: pd.DataFrame,
                  spot_price: float,
                  current_date: date = None) -> GEXResult:
        """
        Calculate GEX from options chain data.

        Args:
            options_chain: DataFrame with columns:
                - strike: Strike price
                - type: 'call' or 'put'
                - gamma: Option gamma
                - open_interest: Open interest
                - expiration: Expiration date (str or datetime)
                - volume: (optional) Trading volume
            spot_price: Current underlying price
            current_date: Date for DTE calculation (default: today)

        Returns:
            GEXResult object with all metrics
        """
        if options_chain.empty:
            logger.warning("Empty options chain provided")
            return self._empty_result(spot_price)

        current_date = current_date or date.today()
        df = options_chain.copy()

        # Standardize column names
        df.columns = df.columns.str.lower()

        # Validate required columns
        required = ['strike', 'type', 'gamma', 'open_interest']
        missing = [c for c in required if c not in df.columns]
        if missing:
            raise ValueError(f"Missing required columns: {missing}")

        # Filter by strike range
        min_strike = spot_price * (1 - self.config.strike_range_pct / 100)
        max_strike = spot_price * (1 + self.config.strike_range_pct / 100)
        df = df[(df['strike'] >= min_strike) & (df['strike'] <= max_strike)]

        # Filter by OI threshold
        df = df[df['open_interest'] >= self.config.min_oi_threshold]

        # Filter by volume if configured
        if self.config.min_volume_threshold > 0 and 'volume' in df.columns:
            df = df[df['volume'] >= self.config.min_volume_threshold]

        if df.empty:
            logger.warning("No options passed filters")
            return self._empty_result(spot_price)

        # Calculate DTE and weights
        if 'expiration' in df.columns and self.config.weight_by_expiration:
            df['dte'] = df['expiration'].apply(
                lambda x: self._calculate_dte(x, current_date)
            )
            df['dte_weight'] = df['dte'].apply(self._get_dte_weight)
        else:
            df['dte_weight'] = 1.0

        # Calculate GEX per contract
        # Formula: Gamma × OI × Multiplier × Spot² / 100
        # The division by 100 converts gamma (per $1) to more meaningful units
        df['gex'] = (
            df['gamma'] *
            df['open_interest'] *
            self.config.contract_multiplier *
            spot_price * spot_price / 100
        )

        # Apply expiration weighting
        df['weighted_gex'] = df['gex'] * df['dte_weight']

        # Apply sign convention
        if self.config.use_dealer_perspective:
            # Dealers: Short calls (negative gamma), Long puts (positive gamma)
            # When dealers are short calls, they have negative gamma exposure
            # When dealers are short puts, they have positive gamma exposure
            df['signed_gex'] = df.apply(
                lambda row: -row['weighted_gex'] if row['type'].lower() == 'call'
                           else row['weighted_gex'],
                axis=1
            )
        else:
            # Market perspective (total OI gamma, no sign flip)
            df['signed_gex'] = df['weighted_gex']

        # Aggregate by strike
        gex_by_strike = df.groupby('strike')['signed_gex'].sum()

        # Calculate totals
        calls = df[df['type'].str.lower() == 'call']
        puts = df[df['type'].str.lower() == 'put']

        call_gex = calls['weighted_gex'].sum()  # Raw call gamma
        put_gex = puts['weighted_gex'].sum()    # Raw put gamma
        total_gex = gex_by_strike.sum()         # Net signed GEX

        # Find gamma flip level
        gamma_flip = self._find_gamma_flip(gex_by_strike, spot_price)

        # Find max gamma strike
        max_gamma_strike = gex_by_strike.abs().idxmax() if len(gex_by_strike) > 0 else spot_price

        # Find call/put walls (highest OI strikes)
        call_wall = calls.loc[calls['open_interest'].idxmax(), 'strike'] if len(calls) > 0 else spot_price
        put_wall = puts.loc[puts['open_interest'].idxmax(), 'strike'] if len(puts) > 0 else spot_price

        # Convert to billions if configured
        divisor = 1e9 if self.config.output_in_billions else 1

        result = GEXResult(
            timestamp=datetime.now(),
            spot_price=spot_price,
            total_gex=total_gex / divisor,
            call_gex=call_gex / divisor,
            put_gex=put_gex / divisor,
            gamma_flip=gamma_flip,
            max_gamma_strike=max_gamma_strike,
            call_wall=call_wall,
            put_wall=put_wall,
            gex_by_strike={k: v / divisor for k, v in gex_by_strike.items()},
            strikes_used=len(gex_by_strike),
            expirations_used=df['expiration'].nunique() if 'expiration' in df.columns else 0,
            total_oi_processed=int(df['open_interest'].sum())
        )

        logger.info(f"GEX calculated: {result.total_gex:.2f}B, "
                   f"flip={result.gamma_flip:.2f}, "
                   f"{result.strikes_used} strikes, "
                   f"{result.total_oi_processed:,} OI")

        return result

    def _calculate_dte(self, expiration, current_date: date) -> int:
        """Calculate days to expiration."""
        if isinstance(expiration, str):
            # Try common date formats
            for fmt in ['%Y-%m-%d', '%m/%d/%Y', '%Y%m%d']:
                try:
                    exp_date = datetime.strptime(expiration.split(':')[0], fmt).date()
                    break
                except ValueError:
                    continue
            else:
                return 30  # Default if parsing fails
        elif isinstance(expiration, datetime):
            exp_date = expiration.date()
        elif isinstance(expiration, date):
            exp_date = expiration
        else:
            return 30

        return max(0, (exp_date - current_date).days)

    def _get_dte_weight(self, dte: int) -> float:
        """Get weight for a given DTE."""
        # Find closest configured DTE
        configured_dtes = sorted(self.config.dte_weights.keys())

        if dte in self.config.dte_weights:
            return self.config.dte_weights[dte]

        # Interpolate between nearest configured values
        lower_dte = max([d for d in configured_dtes if d <= dte], default=0)
        upper_dte = min([d for d in configured_dtes if d >= dte], default=90)

        if lower_dte == upper_dte:
            return self.config.dte_weights.get(lower_dte, 1.0)

        # Linear interpolation
        lower_weight = self.config.dte_weights.get(lower_dte, 1.0)
        upper_weight = self.config.dte_weights.get(upper_dte, 1.0)

        ratio = (dte - lower_dte) / (upper_dte - lower_dte)
        return lower_weight + ratio * (upper_weight - lower_weight)

    def _find_gamma_flip(self, gex_by_strike: pd.Series, spot_price: float) -> float:
        """
        Find the gamma flip level (where cumulative GEX crosses zero).

        The gamma flip is the price level where dealer gamma exposure
        transitions from positive (stabilizing) to negative (amplifying).
        """
        if len(gex_by_strike) == 0:
            return spot_price

        # Sort by strike
        sorted_gex = gex_by_strike.sort_index()

        # Calculate cumulative GEX from lowest strike
        cumulative = sorted_gex.cumsum()

        # Find where cumulative crosses zero
        for i in range(len(cumulative) - 1):
            if cumulative.iloc[i] * cumulative.iloc[i + 1] < 0:
                # Linear interpolation
                strike1 = cumulative.index[i]
                strike2 = cumulative.index[i + 1]
                gex1 = cumulative.iloc[i]
                gex2 = cumulative.iloc[i + 1]

                # Zero crossing point
                flip = strike1 + (strike2 - strike1) * abs(gex1) / (abs(gex1) + abs(gex2))
                return flip

        # No crossing found - use strike with minimum absolute cumulative
        return cumulative.abs().idxmin()

    def _empty_result(self, spot_price: float) -> GEXResult:
        """Return empty result when no data available."""
        return GEXResult(
            timestamp=datetime.now(),
            spot_price=spot_price,
            total_gex=0.0,
            call_gex=0.0,
            put_gex=0.0,
            gamma_flip=spot_price,
            max_gamma_strike=spot_price,
            call_wall=spot_price,
            put_wall=spot_price
        )

    def explain_methodology(self) -> str:
        """Return human-readable explanation of current methodology."""
        return f"""
GEX CALCULATION METHODOLOGY
===========================

Formula:
    GEX per contract = Gamma × OI × {self.config.contract_multiplier} × Spot² / 100

Sign Convention:
    {'Dealer Perspective' if self.config.use_dealer_perspective else 'Market Perspective'}
    {'- Calls: NEGATIVE (dealers short gamma)' if self.config.use_dealer_perspective else '- Calls: POSITIVE'}
    {'- Puts: POSITIVE (dealers long gamma)' if self.config.use_dealer_perspective else '- Puts: POSITIVE'}

Filters:
    Strike Range: ±{self.config.strike_range_pct}% from spot
    Min OI: {self.config.min_oi_threshold} contracts
    Min Volume: {self.config.min_volume_threshold} contracts

Expiration Weighting: {'ENABLED' if self.config.weight_by_expiration else 'DISABLED'}
{self._format_dte_weights() if self.config.weight_by_expiration else ''}

Output: {'Billions ($B)' if self.config.output_in_billions else 'Dollars ($)'}
        """

    def _format_dte_weights(self) -> str:
        """Format DTE weights for display."""
        lines = []
        for dte, weight in sorted(self.config.dte_weights.items()):
            label = {0: '0DTE', 1: '1DTE', 2: '2DTE', 7: 'Weekly',
                    30: 'Monthly', 60: '2-Month', 90: 'Quarterly'}.get(dte, f'{dte}DTE')
            lines.append(f"    {label}: {weight}x")
        return '\n'.join(lines)


# =============================================================================
# EXAMPLE USAGE
# =============================================================================

if __name__ == "__main__":
    print("=" * 60)
    print("GEX CALCULATOR - Methodology Demo")
    print("=" * 60)

    # Create calculator with default config
    config = GEXConfig(
        strike_range_pct=10.0,
        min_oi_threshold=100,
        weight_by_expiration=True,
        use_dealer_perspective=True
    )
    calculator = GEXCalculator(config)

    # Print methodology
    print(calculator.explain_methodology())

    # Create sample data
    print("\nSample Calculation:")
    print("-" * 40)

    sample_data = pd.DataFrame({
        'strike': [495, 500, 505, 510, 495, 500, 505, 510],
        'type': ['call', 'call', 'call', 'call', 'put', 'put', 'put', 'put'],
        'gamma': [0.03, 0.05, 0.04, 0.02, 0.03, 0.05, 0.04, 0.02],
        'open_interest': [5000, 10000, 8000, 3000, 4000, 12000, 6000, 2000],
        'expiration': ['2024-01-19'] * 8
    })

    result = calculator.calculate(sample_data, spot_price=502.50)

    print(f"\nSpot Price: ${result.spot_price:.2f}")
    print(f"Total GEX: {result.total_gex:.4f}B")
    print(f"Call GEX: {result.call_gex:.4f}B")
    print(f"Put GEX: {result.put_gex:.4f}B")
    print(f"Gamma Flip: ${result.gamma_flip:.2f}")
    print(f"Call Wall: ${result.call_wall:.0f}")
    print(f"Put Wall: ${result.put_wall:.0f}")
    print(f"Strikes Used: {result.strikes_used}")
    print(f"Total OI: {result.total_oi_processed:,}")

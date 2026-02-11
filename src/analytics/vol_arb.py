"""
Volatility Arbitrage Engine
Identifies mispricing between implied and realized volatility
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple
from dataclasses import dataclass
from scipy import stats


@dataclass
class VolArbitrageSignal:
    """Volatility arbitrage opportunity"""
    signal_type: str  # "IV_OVERPRICED", "IV_UNDERPRICED", "NEUTRAL"
    iv: float  # Implied volatility
    hv: float  # Historical volatility
    iv_hv_spread: float  # IV - HV
    iv_percentile: float  # IV percentile (0-100)
    hv_percentile: float  # HV percentile (0-100)
    z_score: float  # Z-score of IV-HV spread
    confidence: float  # 0-100
    recommended_action: str
    target_strategies: List[str]
    risk_level: str


class VolatilityArbitrage:
    """
    Analyzes volatility relationships to identify arbitrage opportunities
    """
    
    def __init__(self, lookback_period: int = 252):
        self.lookback_period = lookback_period
    
    def analyze_vol_arbitrage(
        self,
        ohlc: pd.DataFrame,
        current_iv: float,
        current_price: float,
        options_data: pd.DataFrame = None
    ) -> VolArbitrageSignal:
        """
        Analyze volatility arbitrage opportunities
        
        Args:
            ohlc: Historical OHLC data
            current_iv: Current implied volatility (annualized %)
            current_price: Current underlying price
            options_data: Optional full options chain data
            
        Returns:
            VolArbitrageSignal with opportunity assessment
        """
        
        # Calculate historical volatility
        hv_metrics = self._calculate_historical_volatility(ohlc)
        
        # Calculate IV metrics
        iv_metrics = self._calculate_iv_metrics(current_iv, ohlc)
        
        # Detect arbitrage opportunity
        signal = self._detect_arbitrage(
            current_iv,
            hv_metrics,
            iv_metrics
        )
        
        return signal
    
    def _calculate_historical_volatility(
        self,
        ohlc: pd.DataFrame
    ) -> Dict[str, float]:
        """Calculate various historical volatility measures"""
        
        returns = ohlc['Close'].pct_change().dropna()
        
        # Multiple HV windows
        hv_10 = returns.iloc[-10:].std() * np.sqrt(252) * 100
        hv_20 = returns.iloc[-20:].std() * np.sqrt(252) * 100
        hv_30 = returns.iloc[-30:].std() * np.sqrt(252) * 100
        hv_60 = returns.iloc[-60:].std() * np.sqrt(252) * 100
        hv_90 = returns.iloc[-90:].std() * np.sqrt(252) * 100
        
        # Parkinson volatility (high-low)
        high = ohlc['High']
        low = ohlc['Low']
        
        parkinson_vol = np.sqrt(
            (1 / (4 * len(high) * np.log(2))) * 
            np.sum(np.log(high / low) ** 2)
        ) * np.sqrt(252) * 100
        
        # Garman-Klass volatility (more efficient)
        close = ohlc['Close']
        open_price = ohlc['Open']
        
        gk_vol = np.sqrt(
            0.5 * np.mean(np.log(high / low) ** 2) - 
            (2 * np.log(2) - 1) * np.mean(np.log(close / open_price) ** 2)
        ) * np.sqrt(252) * 100
        
        # HV percentile over lookback
        hv_series = returns.rolling(20).std() * np.sqrt(252) * 100
        current_hv = hv_20
        
        if len(hv_series) >= self.lookback_period:
            hv_percentile = (hv_series.iloc[-1] > hv_series.iloc[-self.lookback_period:]).sum() / self.lookback_period * 100
        else:
            hv_percentile = 50
        
        return {
            'hv_10': hv_10,
            'hv_20': hv_20,
            'hv_30': hv_30,
            'hv_60': hv_60,
            'hv_90': hv_90,
            'hv_current': current_hv,
            'parkinson': parkinson_vol,
            'garman_klass': gk_vol,
            'hv_percentile': hv_percentile,
        }
    
    def _calculate_iv_metrics(
        self,
        current_iv: float,
        ohlc: pd.DataFrame
    ) -> Dict[str, float]:
        """Calculate IV-related metrics"""
        
        # In a real implementation, we'd have historical IV data
        # For now, we'll use VIX as a proxy or estimate based on current IV
        
        # Simulate IV history (in production, use actual IV term structure)
        # This is a placeholder
        iv_percentile = 50  # Would calculate from historical IV data
        
        return {
            'current_iv': current_iv,
            'iv_percentile': iv_percentile,
        }
    
    def _detect_arbitrage(
        self,
        current_iv: float,
        hv_metrics: Dict[str, float],
        iv_metrics: Dict[str, float]
    ) -> VolArbitrageSignal:
        """Detect volatility arbitrage opportunities"""
        
        hv = hv_metrics['hv_20']  # Use 20-day HV as primary
        iv = current_iv
        
        # Calculate spread
        iv_hv_spread = iv - hv
        
        # Calculate Z-score of the spread
        # In production, use historical IV-HV spreads
        # For now, use a simplified approach
        z_score = iv_hv_spread / (hv * 0.3)  # Normalized by HV volatility
        
        # Determine signal
        if z_score > 1.5:
            signal_type = "IV_OVERPRICED"
            recommended_action = "SELL VOLATILITY (Sell Options)"
            target_strategies = [
                "Short Strangle",
                "Iron Condor",
                "Jade Lizard",
                "Covered Call",
                "Cash-Secured Put"
            ]
            confidence = min(95, 50 + abs(z_score) * 15)
            risk_level = "Medium" if z_score < 2.5 else "Low"
            
        elif z_score < -1.5:
            signal_type = "IV_UNDERPRICED"
            recommended_action = "BUY VOLATILITY (Buy Options)"
            target_strategies = [
                "Long Straddle",
                "Long Strangle",
                "Calendar Spread",
                "Diagonal Spread",
                "Ratio Back Spread"
            ]
            confidence = min(95, 50 + abs(z_score) * 15)
            risk_level = "Medium" if z_score > -2.5 else "Low"
            
        else:
            signal_type = "NEUTRAL"
            recommended_action = "NO CLEAR EDGE - Consider Directional Strategies"
            target_strategies = [
                "Vertical Spreads",
                "Butterfly Spreads",
                "Directional Plays"
            ]
            confidence = 30
            risk_level = "High"
        
        return VolArbitrageSignal(
            signal_type=signal_type,
            iv=iv,
            hv=hv,
            iv_hv_spread=iv_hv_spread,
            iv_percentile=iv_metrics['iv_percentile'],
            hv_percentile=hv_metrics['hv_percentile'],
            z_score=z_score,
            confidence=confidence,
            recommended_action=recommended_action,
            target_strategies=target_strategies,
            risk_level=risk_level
        )
    
    def calculate_vol_risk_premium(
        self,
        iv: float,
        hv: float
    ) -> float:
        """
        Calculate the volatility risk premium
        
        VRP = IV - Realized Vol
        Positive VRP suggests selling vol is profitable over time
        """
        return iv - hv
    
    def estimate_expected_move(
        self,
        current_price: float,
        iv: float,
        days_to_expiration: int
    ) -> Dict[str, float]:
        """
        Calculate expected move based on IV
        
        Returns 1 standard deviation move (68% probability range)
        """
        # Annual IV to daily
        daily_vol = iv / 100 / np.sqrt(252)
        
        # Expected move for the time period
        expected_move_pct = daily_vol * np.sqrt(days_to_expiration)
        expected_move_dollars = current_price * expected_move_pct
        
        return {
            'expected_move_pct': expected_move_pct * 100,
            'expected_move_dollars': expected_move_dollars,
            'upper_bound_1sd': current_price + expected_move_dollars,
            'lower_bound_1sd': current_price - expected_move_dollars,
            'upper_bound_2sd': current_price + (expected_move_dollars * 2),
            'lower_bound_2sd': current_price - (expected_move_dollars * 2),
        }


class ImpliedVolatilitySurface:
    """
    Build and analyze the IV surface across strikes and expirations
    """
    
    def __init__(self):
        pass
    
    def build_iv_surface(
        self,
        options_chain: pd.DataFrame
    ) -> pd.DataFrame:
        """
        Build IV surface from options chain
        
        Expected columns: strike, expiration, iv, option_type
        """
        
        # Pivot to create surface
        # Rows = Strikes, Columns = Expirations
        
        surface = options_chain.pivot_table(
            values='iv',
            index='strike',
            columns='expiration',
            aggfunc='mean'
        )
        
        return surface
    
    def calculate_skew(
        self,
        options_chain: pd.DataFrame,
        expiration: str
    ) -> Dict[str, float]:
        """
        Calculate volatility skew for a specific expiration
        
        Skew = IV(OTM Puts) - IV(ATM) or Put IV - Call IV
        """
        
        exp_data = options_chain[options_chain['expiration'] == expiration]
        
        # Find ATM
        atm_strike = exp_data['strike'].median()
        
        # Get IVs
        atm_iv = exp_data[exp_data['strike'] == atm_strike]['iv'].mean()
        
        # OTM put IV (strikes below ATM)
        otm_puts = exp_data[exp_data['strike'] < atm_strike * 0.95]
        otm_put_iv = otm_puts['iv'].mean() if len(otm_puts) > 0 else atm_iv
        
        # OTM call IV (strikes above ATM)
        otm_calls = exp_data[exp_data['strike'] > atm_strike * 1.05]
        otm_call_iv = otm_calls['iv'].mean() if len(otm_calls) > 0 else atm_iv
        
        skew = otm_put_iv - atm_iv
        
        return {
            'atm_iv': atm_iv,
            'otm_put_iv': otm_put_iv,
            'otm_call_iv': otm_call_iv,
            'skew': skew,
            'call_skew': otm_call_iv - atm_iv,
        }
    
    def calculate_term_structure(
        self,
        options_chain: pd.DataFrame,
        strike: float
    ) -> pd.DataFrame:
        """
        Calculate IV term structure for a specific strike
        Shows how IV changes across expirations
        """
        
        term_structure = options_chain[
            options_chain['strike'] == strike
        ].groupby('expiration')['iv'].mean().reset_index()
        
        term_structure.columns = ['expiration', 'iv']
        
        return term_structure

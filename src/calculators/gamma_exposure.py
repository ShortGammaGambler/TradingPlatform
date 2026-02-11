import pandas as pd
import numpy as np
from src.calculators.greeks import GreeksCalculator

class GammaExposureCalculator:
    def __init__(self, risk_free_rate=0.05):
        self.greeks_calc = GreeksCalculator(risk_free_rate)
        self.spot_gamma_multiplier = 100
    
    def calculate_gamma_exposure(self, calls_df, puts_df, current_price):
        if calls_df is None or puts_df is None:
            return None, None, None
        
        all_strikes = []
        gamma_exposure = []
        
        calls_df = calls_df.copy()
        puts_df = puts_df.copy()
        
        for _, row in calls_df.iterrows():
            strike = row['strike']
            oi = row.get('openInterest', 0)
            iv = row.get('impliedVolatility', 0.2)
            expiry = row.get('expiration', '2024-12-31')
            
            T = self.greeks_calc.years_to_expiry(expiry)
            
            if T > 0 and oi > 0:
                gamma = self.greeks_calc.gamma(current_price, strike, T, 
                                               self.greeks_calc.risk_free_rate, iv)
                
                gamma_exp = oi * gamma * self.spot_gamma_multiplier * current_price * current_price / 100
                
                all_strikes.append(strike)
                gamma_exposure.append(gamma_exp)
        
        for _, row in puts_df.iterrows():
            strike = row['strike']
            oi = row.get('openInterest', 0)
            iv = row.get('impliedVolatility', 0.2)
            expiry = row.get('expiration', '2024-12-31')
            
            T = self.greeks_calc.years_to_expiry(expiry)
            
            if T > 0 and oi > 0:
                gamma = self.greeks_calc.gamma(current_price, strike, T, 
                                               self.greeks_calc.risk_free_rate, iv)
                
                gamma_exp = -oi * gamma * self.spot_gamma_multiplier * current_price * current_price / 100
                
                all_strikes.append(strike)
                gamma_exposure.append(gamma_exp)
        
        if not all_strikes:
            return None, None, None
        
        gamma_df = pd.DataFrame({
            'strike': all_strikes,
            'gamma_exposure': gamma_exposure
        })
        
        gamma_by_strike = gamma_df.groupby('strike')['gamma_exposure'].sum().reset_index()
        gamma_by_strike = gamma_by_strike.sort_values('strike')
        
        total_gamma = gamma_by_strike['gamma_exposure'].sum()
        
        gamma_flip_zone = self._find_gamma_flip_zone(gamma_by_strike, current_price)
        
        return gamma_by_strike, total_gamma, gamma_flip_zone
    
    def _find_gamma_flip_zone(self, gamma_df, current_price):
        gamma_df = gamma_df.sort_values('strike')
        
        cumulative_gamma = 0
        flip_zone = None
        
        for _, row in gamma_df.iterrows():
            cumulative_gamma += row['gamma_exposure']
            
            if flip_zone is None and cumulative_gamma < 0:
                flip_zone = row['strike']
                break
        
        if flip_zone is None:
            below_spot = gamma_df[gamma_df['strike'] < current_price]
            if not below_spot.empty:
                flip_zone = below_spot.iloc[-1]['strike']
        
        return flip_zone
    
    def calculate_max_pain(self, calls_df, puts_df):
        if calls_df is None or puts_df is None:
            return None
        
        all_strikes = set(calls_df['strike'].unique()) | set(puts_df['strike'].unique())
        all_strikes = sorted(list(all_strikes))
        
        max_pain_values = []
        
        for strike in all_strikes:
            call_pain = 0
            put_pain = 0
            
            calls_itm = calls_df[calls_df['strike'] < strike]
            call_pain = ((strike - calls_itm['strike']) * calls_itm['openInterest']).sum()
            
            puts_itm = puts_df[puts_df['strike'] > strike]
            put_pain = ((puts_itm['strike'] - strike) * puts_itm['openInterest']).sum()
            
            total_pain = call_pain + put_pain
            max_pain_values.append({'strike': strike, 'pain': total_pain})
        
        if not max_pain_values:
            return None
        
        max_pain_df = pd.DataFrame(max_pain_values)
        max_pain_strike = max_pain_df.loc[max_pain_df['pain'].idxmin(), 'strike']
        
        return max_pain_strike
    
    def find_support_resistance(self, calls_df, puts_df, current_price, num_levels=5):
        if calls_df is None or puts_df is None:
            return [], []
        
        combined = pd.concat([calls_df, puts_df])
        
        oi_by_strike = combined.groupby('strike')['openInterest'].sum().reset_index()
        oi_by_strike = oi_by_strike.sort_values('openInterest', ascending=False)
        
        support_levels = []
        resistance_levels = []
        
        for _, row in oi_by_strike.head(num_levels * 2).iterrows():
            strike = row['strike']
            if strike < current_price:
                support_levels.append(strike)
            else:
                resistance_levels.append(strike)
        
        support_levels = sorted(support_levels, reverse=True)[:num_levels]
        resistance_levels = sorted(resistance_levels)[:num_levels]
        
        return support_levels, resistance_levels
    
    def calculate_net_gamma_position(self, gamma_by_strike, current_price):
        if gamma_by_strike is None or gamma_by_strike.empty:
            return "Unknown"
        
        total_gamma = gamma_by_strike['gamma_exposure'].sum()
        
        if total_gamma > 0:
            return "Positive Gamma (Dealers Short Gamma - Stabilizing)"
        else:
            return "Negative Gamma (Dealers Long Gamma - Volatility Amplifying)"

import pandas as pd
import numpy as np
from src.calculators.greeks import GreeksCalculator

class VannaCharmCalculator:
    def __init__(self, risk_free_rate=0.05):
        self.greeks_calc = GreeksCalculator(risk_free_rate)
        self.contract_multiplier = 100
    
    def calculate_vanna_exposure(self, calls_df, puts_df, current_price):
        if calls_df is None or puts_df is None:
            return None, None
        
        all_strikes = []
        vanna_exposure = []
        
        for _, row in calls_df.iterrows():
            strike = row['strike']
            oi = row.get('openInterest', 0)
            iv = row.get('impliedVolatility', 0.2)
            expiry = row.get('expiration', '2024-12-31')
            
            T = self.greeks_calc.years_to_expiry(expiry)
            
            if T > 0 and oi > 0:
                vanna = self.greeks_calc.vanna(current_price, strike, T, 
                                               self.greeks_calc.risk_free_rate, iv)
                
                vanna_exp = oi * vanna * self.contract_multiplier
                
                all_strikes.append(strike)
                vanna_exposure.append(vanna_exp)
        
        for _, row in puts_df.iterrows():
            strike = row['strike']
            oi = row.get('openInterest', 0)
            iv = row.get('impliedVolatility', 0.2)
            expiry = row.get('expiration', '2024-12-31')
            
            T = self.greeks_calc.years_to_expiry(expiry)
            
            if T > 0 and oi > 0:
                vanna = self.greeks_calc.vanna(current_price, strike, T, 
                                               self.greeks_calc.risk_free_rate, iv)
                
                vanna_exp = -oi * vanna * self.contract_multiplier
                
                all_strikes.append(strike)
                vanna_exposure.append(vanna_exp)
        
        if not all_strikes:
            return None, None
        
        vanna_df = pd.DataFrame({
            'strike': all_strikes,
            'vanna_exposure': vanna_exposure
        })
        
        vanna_by_strike = vanna_df.groupby('strike')['vanna_exposure'].sum().reset_index()
        vanna_by_strike = vanna_by_strike.sort_values('strike')
        
        total_vanna = vanna_by_strike['vanna_exposure'].sum()
        
        return vanna_by_strike, total_vanna
    
    def calculate_charm_exposure(self, calls_df, puts_df, current_price):
        if calls_df is None or puts_df is None:
            return None, None
        
        all_strikes = []
        charm_exposure = []
        
        for _, row in calls_df.iterrows():
            strike = row['strike']
            oi = row.get('openInterest', 0)
            iv = row.get('impliedVolatility', 0.2)
            expiry = row.get('expiration', '2024-12-31')
            
            T = self.greeks_calc.years_to_expiry(expiry)
            
            if T > 0 and oi > 0:
                charm = self.greeks_calc.charm(current_price, strike, T, 
                                               self.greeks_calc.risk_free_rate, iv, 'call')
                
                charm_exp = oi * charm * self.contract_multiplier
                
                all_strikes.append(strike)
                charm_exposure.append(charm_exp)
        
        for _, row in puts_df.iterrows():
            strike = row['strike']
            oi = row.get('openInterest', 0)
            iv = row.get('impliedVolatility', 0.2)
            expiry = row.get('expiration', '2024-12-31')
            
            T = self.greeks_calc.years_to_expiry(expiry)
            
            if T > 0 and oi > 0:
                charm = self.greeks_calc.charm(current_price, strike, T, 
                                               self.greeks_calc.risk_free_rate, iv, 'put')
                
                charm_exp = -oi * charm * self.contract_multiplier
                
                all_strikes.append(strike)
                charm_exposure.append(charm_exp)
        
        if not all_strikes:
            return None, None
        
        charm_df = pd.DataFrame({
            'strike': all_strikes,
            'charm_exposure': charm_exposure
        })
        
        charm_by_strike = charm_df.groupby('strike')['charm_exposure'].sum().reset_index()
        charm_by_strike = charm_by_strike.sort_values('strike')
        
        total_charm = charm_by_strike['charm_exposure'].sum()
        
        return charm_by_strike, total_charm
    
    def calculate_volga_exposure(self, calls_df, puts_df, current_price):
        if calls_df is None or puts_df is None:
            return None, None
        
        all_strikes = []
        volga_exposure = []
        
        for _, row in calls_df.iterrows():
            strike = row['strike']
            oi = row.get('openInterest', 0)
            iv = row.get('impliedVolatility', 0.2)
            expiry = row.get('expiration', '2024-12-31')
            
            T = self.greeks_calc.years_to_expiry(expiry)
            
            if T > 0 and oi > 0:
                volga = self.greeks_calc.volga(current_price, strike, T, 
                                               self.greeks_calc.risk_free_rate, iv)
                
                volga_exp = oi * volga * self.contract_multiplier
                
                all_strikes.append(strike)
                volga_exposure.append(volga_exp)
        
        for _, row in puts_df.iterrows():
            strike = row['strike']
            oi = row.get('openInterest', 0)
            iv = row.get('impliedVolatility', 0.2)
            expiry = row.get('expiration', '2024-12-31')
            
            T = self.greeks_calc.years_to_expiry(expiry)
            
            if T > 0 and oi > 0:
                volga = self.greeks_calc.volga(current_price, strike, T, 
                                               self.greeks_calc.risk_free_rate, iv)
                
                volga_exp = -oi * volga * self.contract_multiplier
                
                all_strikes.append(strike)
                volga_exposure.append(volga_exp)
        
        if not all_strikes:
            return None, None
        
        volga_df = pd.DataFrame({
            'strike': all_strikes,
            'volga_exposure': volga_exposure
        })
        
        volga_by_strike = volga_df.groupby('strike')['volga_exposure'].sum().reset_index()
        volga_by_strike = volga_by_strike.sort_values('strike')
        
        total_volga = volga_by_strike['volga_exposure'].sum()
        
        return volga_by_strike, total_volga

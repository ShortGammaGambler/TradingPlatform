import numpy as np
from scipy.stats import norm
from datetime import datetime

class GreeksCalculator:
    def __init__(self, risk_free_rate=0.05):
        self.risk_free_rate = risk_free_rate
    
    def _d1(self, S, K, T, r, sigma):
        if T <= 0 or sigma <= 0:
            return 0
        return (np.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * np.sqrt(T))
    
    def _d2(self, S, K, T, r, sigma):
        if T <= 0 or sigma <= 0:
            return 0
        return self._d1(S, K, T, r, sigma) - sigma * np.sqrt(T)
    
    def delta(self, S, K, T, r, sigma, option_type='call'):
        if T <= 0:
            return 1.0 if S > K else 0.0
        
        d1 = self._d1(S, K, T, r, sigma)
        
        if option_type == 'call':
            return norm.cdf(d1)
        else:
            return norm.cdf(d1) - 1
    
    def gamma(self, S, K, T, r, sigma):
        if T <= 0 or sigma <= 0 or S <= 0:
            return 0
        
        d1 = self._d1(S, K, T, r, sigma)
        return norm.pdf(d1) / (S * sigma * np.sqrt(T))
    
    def vega(self, S, K, T, r, sigma):
        if T <= 0 or S <= 0:
            return 0
        
        d1 = self._d1(S, K, T, r, sigma)
        return S * norm.pdf(d1) * np.sqrt(T) / 100
    
    def theta(self, S, K, T, r, sigma, option_type='call'):
        if T <= 0:
            return 0
        
        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(S, K, T, r, sigma)
        
        term1 = -(S * norm.pdf(d1) * sigma) / (2 * np.sqrt(T))
        
        if option_type == 'call':
            term2 = -r * K * np.exp(-r * T) * norm.cdf(d2)
            return (term1 + term2) / 365
        else:
            term2 = r * K * np.exp(-r * T) * norm.cdf(-d2)
            return (term1 + term2) / 365
    
    def vanna(self, S, K, T, r, sigma):
        if T <= 0 or sigma <= 0 or S <= 0:
            return 0
        
        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(S, K, T, r, sigma)
        
        return -norm.pdf(d1) * d2 / sigma / 100
    
    def charm(self, S, K, T, r, sigma, option_type='call'):
        if T <= 0 or sigma <= 0 or S <= 0:
            return 0
        
        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(S, K, T, r, sigma)
        
        term1 = norm.pdf(d1) * (2 * r * T - d2 * sigma * np.sqrt(T))
        term2 = 2 * T * sigma * np.sqrt(T)
        
        if option_type == 'call':
            return -term1 / term2 / 365
        else:
            return -term1 / term2 / 365
    
    def volga(self, S, K, T, r, sigma):
        if T <= 0 or sigma <= 0 or S <= 0:
            return 0
        
        d1 = self._d1(S, K, T, r, sigma)
        d2 = self._d2(S, K, T, r, sigma)
        
        vega_val = self.vega(S, K, T, r, sigma)
        return vega_val * d1 * d2 / sigma
    
    def rho(self, S, K, T, r, sigma, option_type='call'):
        if T <= 0:
            return 0
        
        d2 = self._d2(S, K, T, r, sigma)
        
        if option_type == 'call':
            return K * T * np.exp(-r * T) * norm.cdf(d2) / 100
        else:
            return -K * T * np.exp(-r * T) * norm.cdf(-d2) / 100
    
    def calculate_all_greeks(self, S, K, T, r, sigma, option_type='call'):
        return {
            'delta': self.delta(S, K, T, r, sigma, option_type),
            'gamma': self.gamma(S, K, T, r, sigma),
            'vega': self.vega(S, K, T, r, sigma),
            'theta': self.theta(S, K, T, r, sigma, option_type),
            'rho': self.rho(S, K, T, r, sigma, option_type),
            'vanna': self.vanna(S, K, T, r, sigma),
            'charm': self.charm(S, K, T, r, sigma, option_type),
            'volga': self.volga(S, K, T, r, sigma)
        }
    
    def days_to_expiry(self, expiration_date):
        if isinstance(expiration_date, str):
            exp_date = datetime.strptime(expiration_date, '%Y-%m-%d')
        else:
            exp_date = expiration_date
        
        today = datetime.now()
        days = (exp_date - today).days
        return max(days, 0)
    
    def years_to_expiry(self, expiration_date):
        days = self.days_to_expiry(expiration_date)
        return days / 365.0

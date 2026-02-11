import yfinance as yf
import pandas as pd
from datetime import datetime
import numpy as np

class YahooOptionsFetcher:
    def __init__(self):
        self.supported_tickers = {
            'SPX': '^SPX',
            'SPY': 'SPY',
            'NDX': '^NDX',
            'QQQ': 'QQQ',
            'ES': 'ES=F',
            'NQ': 'NQ=F'
        }
    
    def get_options_chain(self, symbol):
        try:
            ticker_symbol = self.supported_tickers.get(symbol, symbol)
            ticker = yf.Ticker(ticker_symbol)
            
            current_price = self.get_current_price(symbol)
            
            expirations = ticker.options
            if not expirations:
                print(f"No options data available for {symbol}")
                return None, None, current_price
            
            nearest_expiry = expirations[0]
            
            opt_chain = ticker.option_chain(nearest_expiry)
            calls = opt_chain.calls
            puts = opt_chain.puts
            
            calls['type'] = 'call'
            puts['type'] = 'put'
            
            calls['expiration'] = nearest_expiry
            puts['expiration'] = nearest_expiry
            
            return calls, puts, current_price
            
        except Exception as e:
            print(f"Error fetching options for {symbol}: {e}")
            return None, None, None
    
    def get_current_price(self, symbol):
        try:
            ticker_symbol = self.supported_tickers.get(symbol, symbol)
            ticker = yf.Ticker(ticker_symbol)
            
            hist = ticker.history(period='1d')
            if not hist.empty:
                return hist['Close'].iloc[-1]
            
            info = ticker.info
            if 'regularMarketPrice' in info:
                return info['regularMarketPrice']
            elif 'currentPrice' in info:
                return info['currentPrice']
            
            return None
        except Exception as e:
            print(f"Error fetching price for {symbol}: {e}")
            return None
    
    def get_all_expirations(self, symbol):
        try:
            ticker_symbol = self.supported_tickers.get(symbol, symbol)
            ticker = yf.Ticker(ticker_symbol)
            return ticker.options
        except Exception as e:
            print(f"Error fetching expirations for {symbol}: {e}")
            return []
    
    def get_options_for_expiration(self, symbol, expiration):
        try:
            ticker_symbol = self.supported_tickers.get(symbol, symbol)
            ticker = yf.Ticker(ticker_symbol)
            
            opt_chain = ticker.option_chain(expiration)
            calls = opt_chain.calls
            puts = opt_chain.puts
            
            calls['type'] = 'call'
            puts['type'] = 'put'
            calls['expiration'] = expiration
            puts['expiration'] = expiration
            
            return calls, puts
        except Exception as e:
            print(f"Error fetching options for {symbol} expiration {expiration}: {e}")
            return None, None

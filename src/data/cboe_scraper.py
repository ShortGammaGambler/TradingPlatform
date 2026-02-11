import requests
from bs4 import BeautifulSoup
import pandas as pd
from datetime import datetime
import re

class CBOEScraper:
    def __init__(self):
        self.base_url = "https://www.cboe.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    
    def get_vix_term_structure(self):
        try:
            url = f"{self.base_url}/us/futures/market_statistics/historical_data/"
            response = self.session.get(url, timeout=10)
            
            if response.status_code != 200:
                return self._get_vix_from_alternative()
            
            soup = BeautifulSoup(response.content, 'html.parser')
            
            vix_data = []
            tables = soup.find_all('table')
            
            for table in tables:
                rows = table.find_all('tr')
                for row in rows[1:]:
                    cols = row.find_all('td')
                    if len(cols) >= 4:
                        try:
                            contract = cols[0].text.strip()
                            settle = float(cols[3].text.strip())
                            vix_data.append({
                                'contract': contract,
                                'settle': settle
                            })
                        except:
                            continue
            
            if vix_data:
                return pd.DataFrame(vix_data)
            else:
                return self._get_vix_from_alternative()
                
        except Exception as e:
            print(f"Error fetching VIX term structure: {e}")
            return self._get_vix_from_alternative()
    
    def _get_vix_from_alternative(self):
        try:
            import yfinance as yf
            vix_futures = []
            
            months = ['F', 'G', 'H', 'J', 'K', 'M', 'N', 'Q', 'U', 'V', 'X', 'Z']
            year = datetime.now().year % 100
            
            for i, month in enumerate(months[:8]):
                ticker = f"VX{month}{year}"
                try:
                    data = yf.Ticker(ticker)
                    hist = data.history(period='1d')
                    if not hist.empty:
                        vix_futures.append({
                            'contract': ticker,
                            'settle': hist['Close'].iloc[-1]
                        })
                except:
                    continue
            
            return pd.DataFrame(vix_futures) if vix_futures else pd.DataFrame()
        except:
            return pd.DataFrame()
    
    def get_vix_spot(self):
        try:
            import yfinance as yf
            vix = yf.Ticker("^VIX")
            hist = vix.history(period='1d')
            if not hist.empty:
                return hist['Close'].iloc[-1]
            return None
        except Exception as e:
            print(f"Error fetching VIX spot: {e}")
            return None
    
    def get_skew_data(self, symbol='SPX'):
        try:
            url = f"{self.base_url}/tradable_products/vix/skew_data/"
            response = self.session.get(url, timeout=10)
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                return soup
            return None
        except Exception as e:
            print(f"Error fetching SKEW data: {e}")
            return None

import pandas as pd
import numpy as np
from datetime import datetime

class VIXAnalyzer:
    def __init__(self):
        pass
    
    def analyze_term_structure(self, vix_df):
        if vix_df is None or vix_df.empty:
            return None
        
        vix_df = vix_df.copy()
        vix_df = vix_df.sort_values('contract')
        
        if len(vix_df) < 2:
            return {
                'structure': 'Insufficient data',
                'slope': None,
                'contango': None,
                'backwardation': None
            }
        
        first_month = vix_df.iloc[0]['settle']
        second_month = vix_df.iloc[1]['settle']
        
        slope = second_month - first_month
        
        if slope > 0:
            structure = 'Contango'
            contango = True
            backwardation = False
        elif slope < 0:
            structure = 'Backwardation'
            contango = False
            backwardation = True
        else:
            structure = 'Flat'
            contango = False
            backwardation = False
        
        return {
            'structure': structure,
            'slope': slope,
            'contango': contango,
            'backwardation': backwardation,
            'front_month': first_month,
            'second_month': second_month,
            'data': vix_df
        }
    
    def calculate_vix_slope_2d(self, vix_df):
        if vix_df is None or vix_df.empty or len(vix_df) < 2:
            return None
        
        vix_df = vix_df.sort_values('contract')
        
        slopes = []
        for i in range(len(vix_df) - 1):
            slope = vix_df.iloc[i + 1]['settle'] - vix_df.iloc[i]['settle']
            slopes.append({
                'from': vix_df.iloc[i]['contract'],
                'to': vix_df.iloc[i + 1]['contract'],
                'slope': slope
            })
        
        return pd.DataFrame(slopes)
    
    def calculate_vix_slope_3d(self, vix_df, vix_spot):
        if vix_df is None or vix_df.empty:
            return None
        
        vix_df = vix_df.copy()
        vix_df = vix_df.sort_values('contract')
        
        if vix_spot:
            spot_row = pd.DataFrame([{'contract': 'VIX_SPOT', 'settle': vix_spot}])
            vix_df = pd.concat([spot_row, vix_df], ignore_index=True)
        
        vix_df['days_out'] = range(len(vix_df))
        
        return vix_df
    
    def get_vix_percentile(self, current_vix, historical_range=(10, 80)):
        if current_vix is None:
            return None
        
        low, high = historical_range
        
        if current_vix < low:
            return "Very Low (Complacent)"
        elif current_vix < 15:
            return "Low (Calm)"
        elif current_vix < 20:
            return "Normal"
        elif current_vix < 30:
            return "Elevated (Cautious)"
        elif current_vix < 40:
            return "High (Fear)"
        else:
            return "Very High (Panic)"

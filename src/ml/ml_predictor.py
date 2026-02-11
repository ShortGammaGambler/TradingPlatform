"""
Machine Learning Price Predictor
AI-powered directional bias and price forecasting
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from sklearn.ensemble import RandomForestRegressor, GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
import warnings
warnings.filterwarnings('ignore')


@dataclass
class PricePrediction:
    """Price prediction result"""
    symbol: str
    current_price: float
    predicted_price: float
    predicted_change_pct: float
    direction: str  # "UP", "DOWN", "NEUTRAL"
    confidence: float  # 0-100
    timeframe_days: int
    prediction_date: datetime
    lower_bound: float  # 68% confidence interval
    upper_bound: float  # 68% confidence interval
    key_drivers: List[str]
    model_agreement: float  # % of models agreeing on direction


@dataclass
class ModelPerformance:
    """Historical model performance metrics"""
    accuracy: float  # % correct direction
    mae: float  # Mean Absolute Error
    rmse: float  # Root Mean Square Error
    sharpe_ratio: float  # If traded on predictions
    total_predictions: int
    correct_predictions: int


class MLPricePredictor:
    """
    Machine Learning Price Predictor using ensemble methods
    
    Models:
    - Random Forest (captures non-linear patterns)
    - Gradient Boosting (sequential learning)
    - Feature engineering from technical indicators
    
    Features used:
    - Price momentum (ROC)
    - Volatility (ATR, HV)
    - Moving averages (SMA, EMA)
    - Volume indicators
    - Market regime indicators
    - Seasonal patterns
    """
    
    def __init__(self):
        # Models
        self.rf_model = RandomForestRegressor(
            n_estimators=100,
            max_depth=10,
            random_state=42
        )
        
        self.gb_model = GradientBoostingRegressor(
            n_estimators=100,
            max_depth=5,
            random_state=42
        )
        
        self.scaler = StandardScaler()
        self.is_trained = False
        
        # Performance tracking
        self.performance_history = []
    
    def train(
        self,
        ohlc_data: pd.DataFrame,
        target_days: int = 5,
        train_period_days: int = 500
    ):
        """
        Train the ML models on historical data
        
        Args:
            ohlc_data: Historical OHLC data
            target_days: Days forward to predict
            train_period_days: How much history to use for training
        """
        
        # Engineer features
        features_df = self._engineer_features(ohlc_data)
        
        # Create target variable (future returns)
        features_df['target'] = features_df['close'].pct_change(target_days).shift(-target_days)
        
        # Drop NaN values
        features_df = features_df.dropna()
        
        if len(features_df) < 100:
            raise ValueError("Insufficient data for training")
        
        # Use most recent data for training
        train_data = features_df.iloc[-train_period_days:] if len(features_df) > train_period_days else features_df
        
        # Separate features and target
        feature_cols = [col for col in train_data.columns if col not in ['target', 'close', 'date']]
        
        X = train_data[feature_cols]
        y = train_data['target']
        
        # Scale features
        X_scaled = self.scaler.fit_transform(X)
        
        # Train models
        self.rf_model.fit(X_scaled, y)
        self.gb_model.fit(X_scaled, y)
        
        self.is_trained = True
        self.feature_names = feature_cols
    
    def predict(
        self,
        ohlc_data: pd.DataFrame,
        symbol: str = "SPX",
        timeframe_days: int = 5
    ) -> PricePrediction:
        """
        Predict future price movement
        
        Args:
            ohlc_data: Historical OHLC data
            symbol: Symbol being predicted
            timeframe_days: Days forward to predict
            
        Returns:
            PricePrediction with forecast details
        """
        
        if not self.is_trained:
            # Auto-train if not trained
            self.train(ohlc_data, target_days=timeframe_days)
        
        # Engineer features for latest data
        features_df = self._engineer_features(ohlc_data)
        
        # Get most recent features
        latest_features = features_df[self.feature_names].iloc[-1:].values
        
        # Scale
        latest_features_scaled = self.scaler.transform(latest_features)
        
        # Predict with both models
        rf_prediction = self.rf_model.predict(latest_features_scaled)[0]
        gb_prediction = self.gb_model.predict(latest_features_scaled)[0]
        
        # Ensemble prediction (weighted average)
        ensemble_prediction = (rf_prediction * 0.6 + gb_prediction * 0.4)
        
        # Current price
        current_price = ohlc_data['Close'].iloc[-1]
        
        # Predicted price
        predicted_price = current_price * (1 + ensemble_prediction)
        
        # Direction
        if ensemble_prediction > 0.005:  # >0.5% up
            direction = "UP"
        elif ensemble_prediction < -0.005:  # >0.5% down
            direction = "DOWN"
        else:
            direction = "NEUTRAL"
        
        # Confidence calculation
        # Based on model agreement and historical accuracy
        model_agreement = self._calculate_model_agreement(rf_prediction, gb_prediction)
        
        # Base confidence from agreement
        confidence = 50 + (model_agreement * 30)
        
        # Adjust for magnitude
        magnitude_confidence = min(20, abs(ensemble_prediction) * 1000)
        confidence += magnitude_confidence
        
        confidence = min(95, max(30, confidence))
        
        # Confidence intervals (68% - 1 standard deviation)
        prediction_std = abs(rf_prediction - gb_prediction) / 2
        lower_bound = current_price * (1 + ensemble_prediction - prediction_std)
        upper_bound = current_price * (1 + ensemble_prediction + prediction_std)
        
        # Key drivers (feature importance)
        key_drivers = self._get_key_drivers()
        
        return PricePrediction(
            symbol=symbol,
            current_price=current_price,
            predicted_price=predicted_price,
            predicted_change_pct=ensemble_prediction * 100,
            direction=direction,
            confidence=confidence,
            timeframe_days=timeframe_days,
            prediction_date=datetime.now() + timedelta(days=timeframe_days),
            lower_bound=lower_bound,
            upper_bound=upper_bound,
            key_drivers=key_drivers,
            model_agreement=model_agreement * 100
        )
    
    def _engineer_features(self, ohlc_data: pd.DataFrame) -> pd.DataFrame:
        """
        Create features from OHLC data
        
        Features:
        - Price momentum (ROC 5, 10, 20 days)
        - Moving averages (SMA 20, 50, 200)
        - Volatility (ATR, Historical Vol)
        - Volume patterns
        - RSI
        - MACD
        - Bollinger Band position
        """
        
        df = ohlc_data.copy()
        df = df.reset_index()
        
        close = df['Close']
        high = df['High']
        low = df['Low']
        volume = df['Volume'] if 'Volume' in df.columns else pd.Series([0] * len(df))
        
        features = pd.DataFrame()
        
        # Price features
        features['close'] = close
        
        # Momentum indicators
        features['roc_5'] = close.pct_change(5)
        features['roc_10'] = close.pct_change(10)
        features['roc_20'] = close.pct_change(20)
        
        # Moving averages
        features['sma_20'] = close.rolling(20).mean()
        features['sma_50'] = close.rolling(50).mean()
        features['sma_200'] = close.rolling(200).mean()
        
        # Price vs MAs
        features['price_vs_sma20'] = (close / features['sma_20'] - 1)
        features['price_vs_sma50'] = (close / features['sma_50'] - 1)
        
        # Volatility
        features['atr_14'] = self._calculate_atr(df, 14)
        features['hv_20'] = close.pct_change().rolling(20).std() * np.sqrt(252)
        
        # RSI
        features['rsi_14'] = self._calculate_rsi(close, 14)
        
        # MACD
        ema_12 = close.ewm(span=12).mean()
        ema_26 = close.ewm(span=26).mean()
        features['macd'] = ema_12 - ema_26
        features['macd_signal'] = features['macd'].ewm(span=9).mean()
        
        # Bollinger Bands
        bb_middle = close.rolling(20).mean()
        bb_std = close.rolling(20).std()
        features['bb_position'] = (close - bb_middle) / (2 * bb_std)
        
        # Volume (if available)
        if volume.sum() > 0:
            features['volume_sma'] = volume.rolling(20).mean()
            features['volume_ratio'] = volume / features['volume_sma']
        else:
            features['volume_ratio'] = 1.0
        
        # Day of week (seasonal pattern)
        if 'Date' in df.columns or df.index.name == 'Date':
            try:
                dates = pd.to_datetime(df.index if 'Date' not in df.columns else df['Date'])
                features['day_of_week'] = dates.dayofweek
                features['day_of_month'] = dates.day
            except:
                features['day_of_week'] = 0
                features['day_of_month'] = 1
        else:
            features['day_of_week'] = 0
            features['day_of_month'] = 1
        
        return features
    
    def _calculate_atr(self, df: pd.DataFrame, period: int = 14) -> pd.Series:
        """Calculate Average True Range"""
        high = df['High']
        low = df['Low']
        close = df['Close']
        
        tr1 = high - low
        tr2 = abs(high - close.shift())
        tr3 = abs(low - close.shift())
        
        tr = pd.concat([tr1, tr2, tr3], axis=1).max(axis=1)
        atr = tr.rolling(period).mean()
        
        return atr
    
    def _calculate_rsi(self, close: pd.Series, period: int = 14) -> pd.Series:
        """Calculate Relative Strength Index"""
        delta = close.diff()
        
        gain = (delta.where(delta > 0, 0)).rolling(window=period).mean()
        loss = (-delta.where(delta < 0, 0)).rolling(window=period).mean()
        
        rs = gain / loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def _calculate_model_agreement(
        self,
        rf_pred: float,
        gb_pred: float
    ) -> float:
        """
        Calculate how much models agree
        
        Returns 0-1, where 1 is perfect agreement
        """
        
        # Check if same direction
        same_direction = (rf_pred > 0 and gb_pred > 0) or (rf_pred < 0 and gb_pred < 0)
        
        if not same_direction:
            return 0.3  # Low agreement
        
        # Calculate similarity
        avg_pred = (abs(rf_pred) + abs(gb_pred)) / 2
        diff = abs(rf_pred - gb_pred)
        
        if avg_pred == 0:
            return 0.5
        
        similarity = 1 - (diff / (avg_pred * 2))
        similarity = max(0.3, min(1.0, similarity))
        
        return similarity
    
    def _get_key_drivers(self) -> List[str]:
        """Get top features driving the prediction"""
        
        if not self.is_trained:
            return []
        
        # Get feature importances from Random Forest
        importances = self.rf_model.feature_importances_
        
        # Get top 5 features
        top_indices = np.argsort(importances)[-5:][::-1]
        
        feature_map = {
            'roc_20': 'Price Momentum (20d)',
            'roc_10': 'Price Momentum (10d)',
            'rsi_14': 'RSI Indicator',
            'price_vs_sma20': 'Price vs SMA20',
            'macd': 'MACD',
            'hv_20': 'Historical Volatility',
            'bb_position': 'Bollinger Band Position',
            'volume_ratio': 'Volume Pattern'
        }
        
        drivers = []
        for idx in top_indices:
            feature_name = self.feature_names[idx]
            readable_name = feature_map.get(feature_name, feature_name)
            drivers.append(readable_name)
        
        return drivers
    
    def backtest_predictions(
        self,
        ohlc_data: pd.DataFrame,
        prediction_days: int = 5,
        lookback_periods: int = 50
    ) -> ModelPerformance:
        """
        Backtest model performance
        
        Args:
            ohlc_data: Historical data
            prediction_days: Days forward to predict
            lookback_periods: Number of periods to test
            
        Returns:
            ModelPerformance metrics
        """
        
        predictions = []
        actuals = []
        
        # Walk forward through history
        for i in range(lookback_periods):
            # Use data up to current point
            train_end = -(lookback_periods - i + prediction_days)
            if train_end == 0:
                train_data = ohlc_data
            else:
                train_data = ohlc_data.iloc[:train_end]
            
            if len(train_data) < 100:
                continue
            
            # Train and predict
            try:
                self.train(train_data, target_days=prediction_days)
                prediction = self.predict(train_data, timeframe_days=prediction_days)
                
                # Get actual future price
                actual_idx = len(train_data) + prediction_days
                if actual_idx < len(ohlc_data):
                    actual_price = ohlc_data['Close'].iloc[actual_idx]
                    actual_change = (actual_price / prediction.current_price - 1) * 100
                    
                    predictions.append(prediction.predicted_change_pct)
                    actuals.append(actual_change)
            except:
                continue
        
        if len(predictions) == 0:
            return ModelPerformance(
                accuracy=0, mae=0, rmse=0, sharpe_ratio=0,
                total_predictions=0, correct_predictions=0
            )
        
        # Calculate metrics
        predictions = np.array(predictions)
        actuals = np.array(actuals)
        
        # Direction accuracy
        pred_direction = np.sign(predictions)
        actual_direction = np.sign(actuals)
        correct = (pred_direction == actual_direction).sum()
        accuracy = correct / len(predictions) * 100
        
        # MAE and RMSE
        mae = np.mean(np.abs(predictions - actuals))
        rmse = np.sqrt(np.mean((predictions - actuals) ** 2))
        
        # Sharpe (if traded on predictions)
        returns = np.where(predictions > 0, actuals, -actuals) / 100
        sharpe = returns.mean() / returns.std() * np.sqrt(252) if returns.std() > 0 else 0
        
        return ModelPerformance(
            accuracy=accuracy,
            mae=mae,
            rmse=rmse,
            sharpe_ratio=sharpe,
            total_predictions=len(predictions),
            correct_predictions=int(correct)
        )


def create_prediction_visualization(prediction: PricePrediction):
    """Create visualization of price prediction"""
    import plotly.graph_objs as go
    
    fig = go.Figure()
    
    # Current price
    fig.add_trace(go.Scatter(
        x=[0],
        y=[prediction.current_price],
        mode='markers',
        name='Current',
        marker=dict(size=15, color='white', symbol='star')
    ))
    
    # Predicted price
    color = '#00cc96' if prediction.direction == 'UP' else '#ef553b' if prediction.direction == 'DOWN' else '#ffa500'
    
    fig.add_trace(go.Scatter(
        x=[prediction.timeframe_days],
        y=[prediction.predicted_price],
        mode='markers',
        name=f'{prediction.direction} Prediction',
        marker=dict(size=20, color=color, symbol='diamond')
    ))
    
    # Confidence interval
    fig.add_trace(go.Scatter(
        x=[prediction.timeframe_days, prediction.timeframe_days],
        y=[prediction.lower_bound, prediction.upper_bound],
        mode='lines',
        name='68% Confidence',
        line=dict(color=color, width=3),
        fill='tonexty',
        fillcolor=f'rgba({"0,204,150" if prediction.direction == "UP" else "239,85,59"}, 0.2)'
    ))
    
    # Connecting line
    fig.add_trace(go.Scatter(
        x=[0, prediction.timeframe_days],
        y=[prediction.current_price, prediction.predicted_price],
        mode='lines',
        line=dict(color=color, width=2, dash='dash'),
        showlegend=False
    ))
    
    fig.update_layout(
        title=f'{prediction.symbol} Price Prediction ({prediction.timeframe_days}d) - {prediction.confidence:.0f}% Confidence',
        xaxis_title='Days Forward',
        yaxis_title='Price ($)',
        template='plotly_dark',
        paper_bgcolor='#0e1117',
        plot_bgcolor='#0e1117',
        height=500
    )
    
    return fig

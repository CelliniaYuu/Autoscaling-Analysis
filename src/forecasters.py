"""
Time series forecasting models for load prediction
Implements: ExponentialSmoothing, ExponentialTrend, LSTM, XGBoost, Prophet, RandomForest
"""
import numpy as np
import pandas as pd
import warnings
from abc import ABC, abstractmethod
import logging

# Suppress warnings
warnings.filterwarnings('ignore')
logger = logging.getLogger(__name__)

try:
    from fbprophet import Prophet
except ImportError:
    try:
        from prophet import Prophet
    except ImportError:
        logger.warning("Prophet not available")

try:
    from sklearn.preprocessing import MinMaxScaler
    from sklearn.metrics import mean_squared_error, mean_absolute_error
    from sklearn.ensemble import RandomForestRegressor
except ImportError:
    logger.warning("sklearn not available")

try:
    import xgboost as xgb
except ImportError:
    logger.warning("XGBoost not available")

try:
    from tensorflow.keras.models import Sequential
    from tensorflow.keras.layers import LSTM, Dense, Dropout
    from tensorflow.keras.optimizers import Adam
except ImportError:
    logger.warning("TensorFlow/Keras not available")


class BaseForecaster(ABC):
    """Base class for all forecasters"""
    
    def __init__(self, name):
        self.name = name
        self.model = None
        self.history = {}
    
    @abstractmethod
    def fit(self, train_data):
        """Fit model on training data"""
        pass
    
    @abstractmethod
    def predict(self, steps):
        """Generate predictions for next 'steps' periods"""
        pass
    
    def evaluate(self, y_true, y_pred):
        """
        Calculate comprehensive evaluation metrics
        
        Returns:
            dict with metrics:
            - MSE: Mean Squared Error
            - RMSE: Root Mean Squared Error
            - MAE: Mean Absolute Error
            - MAPE: Mean Absolute Percentage Error
            - SMAPE: Symmetric MAPE
            - R2: R-squared score
            - Theil_U: Theil's U statistic (0=perfect, 1=baseline, >1=worse)
            - MASE: Mean Absolute Scaled Error
        """
        mse = mean_squared_error(y_true, y_pred)
        rmse = np.sqrt(mse)
        mae = mean_absolute_error(y_true, y_pred)
        
        # MAPE: Mean Absolute Percentage Error
        mape = np.mean(np.abs((y_true - y_pred) / (y_true + 1e-8))) * 100
        
        # SMAPE: Symmetric MAPE (0-200%)
        numerator = 2.0 * np.abs(y_true - y_pred)
        denominator = np.abs(y_true) + np.abs(y_pred)
        smape = np.mean(numerator / (denominator + 1e-8)) * 100
        
        # R² Score: Coefficient of determination (-∞ to 1, 1 is perfect)
        ss_res = np.sum((y_true - y_pred) ** 2)
        ss_tot = np.sum((y_true - np.mean(y_true)) ** 2)
        r2 = 1 - (ss_res / (ss_tot + 1e-8)) if ss_tot > 0 else 0
        
        # Theil's U: (0=perfect, 1=baseline, >1=worse)
        # U < 1 means model is better than naive forecast
        numerator_u = np.sum((y_true - y_pred) ** 2)
        denominator_u = np.sum((y_true[1:] - y_true[:-1]) ** 2) if len(y_true) > 1 else 1
        theil_u = np.sqrt(numerator_u / (denominator_u + 1e-8)) if denominator_u > 0 else np.inf
        
        # MASE: Mean Absolute Scaled Error
        # Scale by mean absolute forecast error of naive method (persistence)
        if len(y_true) > 1:
            denominator_mase = np.mean(np.abs(y_true[1:] - y_true[:-1]))
            mase = mae / (denominator_mase + 1e-8) if denominator_mase > 0 else 0
        else:
            mase = 0
        
        return {
            'mse': float(mse),
            'rmse': float(rmse),
            'mae': float(mae),
            'mape': float(mape),
            'smape': float(smape),
            'r2': float(r2),
            'theil_u': float(theil_u),
            'mase': float(mase)
        }


class ExponentialSmoothingForecaster(BaseForecaster):
    """Exponential smoothing for time series (replaces ARIMA)"""
    
    def __init__(self, alpha=0.3):
        super().__init__("ExponentialSmoothing")
        self.alpha = alpha
        self.last_value = None
        self.smoothed_values = []
    
    def fit(self, train_data):
        """
        Fit exponential smoothing model
        Args:
            train_data: pandas Series with time index
        """
        try:
            values = train_data.values
            self.smoothed_values = [values[0]]
            
            # Apply exponential smoothing
            for i in range(1, len(values)):
                smoothed = self.alpha * values[i] + (1 - self.alpha) * self.smoothed_values[-1]
                self.smoothed_values.append(smoothed)
            
            self.last_value = self.smoothed_values[-1]
            self.mean = np.mean(values)
            self.std = np.std(values)
            logger.info("ExponentialSmoothing fitted successfully")
            return True
        except Exception as e:
            logger.error(f"Error fitting ExponentialSmoothing: {e}")
            return False
    
    def predict(self, steps=24):
        """Predict next 'steps' periods with trend"""
        try:
            predictions = []
            current_value = self.last_value
            
            # Use weighted combination of last value and mean
            trend = (self.smoothed_values[-1] - self.smoothed_values[-min(24, len(self.smoothed_values))]) / min(24, len(self.smoothed_values))
            
            for i in range(steps):
                # Add trend with damping factor
                damping = 0.98 ** (i + 1)
                pred = current_value + trend * damping
                predictions.append(pred)
                current_value = pred
            
            return np.array(predictions)
        except Exception as e:
            logger.error(f"Error predicting with ExponentialSmoothing: {e}")
            return None


class SeasonalForecaster(BaseForecaster):
    """Seasonal decomposition forecaster (replaces SARIMA)"""
    
    def __init__(self, season_length=24):
        super().__init__("SeasonalForecaster")
        self.season_length = season_length
        self.seasonal_pattern = None
        self.trend_values = None
        self.mean_value = None
    
    def fit(self, train_data):
        """Fit seasonal forecaster"""
        try:
            values = train_data.values
            self.mean_value = np.mean(values)
            
            # Calculate seasonal pattern (average for each season position)
            n_seasons = len(values) // self.season_length
            seasonal_sum = np.zeros(self.season_length)
            
            for i in range(n_seasons):
                seasonal_sum += values[i*self.season_length:(i+1)*self.season_length]
            
            self.seasonal_pattern = seasonal_sum / n_seasons
            
            # Normalize seasonal pattern to mean 0
            self.seasonal_pattern = self.seasonal_pattern - np.mean(self.seasonal_pattern)
            
            # Calculate trend
            self.trend_values = np.convolve(values, np.ones(self.season_length)/self.season_length, mode='valid')
            
            logger.info(f"SeasonalForecaster fitted successfully (season_length={self.season_length})")
            return True
        except Exception as e:
            logger.error(f"Error fitting SeasonalForecaster: {e}")
            return False
    
    def predict(self, steps=24):
        """Predict next 'steps' periods"""
        try:
            predictions = []
            trend = self.trend_values[-1] if len(self.trend_values) > 0 else self.mean_value
            
            # Use trend from last values
            recent_trend = (self.trend_values[-1] - self.trend_values[max(0, len(self.trend_values)-self.season_length)]) / max(1, len(self.trend_values)-self.season_length)
            
            for i in range(steps):
                season_idx = i % self.season_length
                pred = trend + self.seasonal_pattern[season_idx]
                predictions.append(pred)
                trend += recent_trend * 0.1  # Small trend adjustment
            
            return np.array(predictions)
        except Exception as e:
            logger.error(f"Error predicting with SeasonalForecaster: {e}")
            return None


class ProphetForecaster(BaseForecaster):
    """Facebook Prophet for robust forecasting"""
    
    def __init__(self, yearly_seasonality=False, daily_seasonality=True):
        super().__init__("Prophet")
        self.yearly_seasonality = yearly_seasonality
        self.daily_seasonality = daily_seasonality
    
    def fit(self, train_data):
        """
        Fit Prophet model
        Args:
            train_data: pandas Series with datetime index
        """
        try:
            # Prepare data for Prophet
            df = pd.DataFrame({
                'ds': train_data.index,
                'y': train_data.values
            })
            
            self.model = Prophet(
                yearly_seasonality=self.yearly_seasonality,
                daily_seasonality=self.daily_seasonality,
                interval_width=0.95
            )
            self.model.fit(df)
            logger.info("Prophet model fitted successfully")
            return True
        except Exception as e:
            logger.error(f"Error fitting Prophet: {e}")
            return False
    
    def predict(self, steps=24):
        """Predict next 'steps' periods"""
        try:
            future = self.model.make_future_dataframe(periods=steps, freq='min')
            forecast = self.model.predict(future)
            return forecast['yhat'].iloc[-steps:].values
        except Exception as e:
            logger.error(f"Error predicting with Prophet: {e}")
            return None


class XGBoostForecaster(BaseForecaster):
    """XGBoost for time series regression"""
    
    def __init__(self, n_lags=24, params=None):
        super().__init__("XGBoost")
        self.n_lags = n_lags
        self.params = params or {
            'objective': 'reg:squarederror',
            'max_depth': 5,
            'learning_rate': 0.1,
            'n_estimators': 100
        }
    
    def create_features(self, data):
        """Create lagged features"""
        X = []
        y = []
        for i in range(len(data) - self.n_lags):
            X.append(data[i:i+self.n_lags])
            y.append(data[i+self.n_lags])
        return np.array(X), np.array(y)
    
    def fit(self, train_data):
        """Fit XGBoost model"""
        try:
            X, y = self.create_features(train_data.values)
            self.model = xgb.XGBRegressor(**self.params)
            self.model.fit(X, y)
            self.last_sequence = train_data.values[-self.n_lags:]
            logger.info("XGBoost model fitted successfully")
            return True
        except Exception as e:
            logger.error(f"Error fitting XGBoost: {e}")
            return False
    
    def predict(self, steps=24):
        """Predict next 'steps' periods"""
        try:
            predictions = []
            sequence = self.last_sequence.copy()
            
            for _ in range(steps):
                pred = self.model.predict(sequence.reshape(1, -1))[0]
                predictions.append(pred)
                sequence = np.append(sequence[1:], pred)
            
            return np.array(predictions)
        except Exception as e:
            logger.error(f"Error predicting with XGBoost: {e}")
            return None


class RandomForestForecaster(BaseForecaster):
    """Random Forest for time series regression (replaces LightGBM)"""
    
    def __init__(self, n_lags=24, n_estimators=100, max_depth=10):
        super().__init__("RandomForest")
        self.n_lags = n_lags
        self.params = {
            'n_estimators': n_estimators,
            'max_depth': max_depth,
            'random_state': 42
        }
    
    def create_features(self, data):
        """Create lagged features"""
        X = []
        y = []
        for i in range(len(data) - self.n_lags):
            X.append(data[i:i+self.n_lags])
            y.append(data[i+self.n_lags])
        return np.array(X), np.array(y)
    
    def fit(self, train_data):
        """Fit Random Forest model"""
        try:
            X, y = self.create_features(train_data.values)
            self.model = RandomForestRegressor(**self.params)
            self.model.fit(X, y)
            self.last_sequence = train_data.values[-self.n_lags:]
            logger.info("RandomForest model fitted successfully")
            return True
        except Exception as e:
            logger.error(f"Error fitting RandomForest: {e}")
            return False
    
    def predict(self, steps=24):
        """Predict next 'steps' periods"""
        try:
            predictions = []
            sequence = self.last_sequence.copy()
            
            for _ in range(steps):
                pred = self.model.predict(sequence.reshape(1, -1))[0]
                predictions.append(pred)
                sequence = np.append(sequence[1:], pred)
            
            return np.array(predictions)
        except Exception as e:
            logger.error(f"Error predicting with RandomForest: {e}")
            return None


class LSTMForecaster(BaseForecaster):
    """LSTM model for deep learning time series"""
    
    def __init__(self, n_lags=24, units=50, epochs=50):
        super().__init__("LSTM")
        self.n_lags = n_lags
        self.units = units
        self.epochs = epochs
        self.scaler = MinMaxScaler()
    
    def create_features(self, data):
        """Create lagged features"""
        X = []
        y = []
        for i in range(len(data) - self.n_lags):
            X.append(data[i:i+self.n_lags])
            y.append(data[i+self.n_lags])
        return np.array(X), np.array(y)
    
    def fit(self, train_data):
        """Fit LSTM model"""
        try:
            # Normalize data
            data_scaled = self.scaler.fit_transform(train_data.values.reshape(-1, 1))
            X, y = self.create_features(data_scaled.flatten())
            
            # Reshape for LSTM
            X = X.reshape((X.shape[0], X.shape[1], 1))
            
            # Build model
            self.model = Sequential([
                LSTM(self.units, activation='relu', input_shape=(self.n_lags, 1)),
                Dropout(0.2),
                Dense(25, activation='relu'),
                Dense(1)
            ])
            
            self.model.compile(optimizer=Adam(learning_rate=0.001), loss='mse')
            
            # Add early stopping and reduce batch size for faster training
            from tensorflow.keras.callbacks import EarlyStopping
            early_stop = EarlyStopping(monitor='loss', patience=3, restore_best_weights=True)
            
            self.model.fit(
                X, y, 
                epochs=self.epochs, 
                verbose=0,
                batch_size=32,
                callbacks=[early_stop]
            )
            
            self.last_sequence = data_scaled[-self.n_lags:]
            logger.info("LSTM model fitted successfully")
            return True
        except Exception as e:
            logger.error(f"Error fitting LSTM: {e}")
            return False
    
    def predict(self, steps=24):
        """Predict next 'steps' periods"""
        try:
            predictions = []
            sequence = self.last_sequence.copy().flatten()
            
            for _ in range(steps):
                pred_scaled = self.model.predict(sequence.reshape(1, -1, 1), verbose=0)[0]
                predictions.append(pred_scaled[0])
                sequence = np.append(sequence[1:], pred_scaled[0])
            
            # Inverse transform
            predictions = np.array(predictions).reshape(-1, 1)
            predictions = self.scaler.inverse_transform(predictions)
            return predictions.flatten()
        except Exception as e:
            logger.error(f"Error predicting with LSTM: {e}")
            return None


class EnsembleForecaster:
    """Ensemble of multiple forecasters"""
    
    def __init__(self, forecasters, weights=None):
        self.forecasters = forecasters
        self.weights = weights or np.ones(len(forecasters)) / len(forecasters)
    
    def fit(self, train_data):
        """Fit all forecasters"""
        for fc in self.forecasters:
            fc.fit(train_data)
    
    def predict(self, steps=24):
        """Ensemble prediction (weighted average)"""
        predictions = []
        for fc in self.forecasters:
            pred = fc.predict(steps)
            if pred is not None:
                predictions.append(pred)
        
        if not predictions:
            return None
        
        predictions = np.array(predictions)
        ensemble_pred = np.average(predictions, axis=0, weights=self.weights[:len(predictions)])
        return ensemble_pred


def create_forecaster(model_name, **kwargs):
    """Factory function to create forecasters"""
    model_map = {
        'arima': ExponentialSmoothingForecaster,
        'sarima': SeasonalForecaster,
        'exponentialsmoothing': ExponentialSmoothingForecaster,
        'seasonal': SeasonalForecaster,
        'prophet': ProphetForecaster,
        'xgboost': XGBoostForecaster,
        'randomforest': RandomForestForecaster,
        'lightgbm': RandomForestForecaster,  # Backward compatibility
        'lstm': LSTMForecaster,
    }
    
    if model_name.lower() not in model_map:
        raise ValueError(f"Unknown model: {model_name}")
    
    return model_map[model_name.lower()](**kwargs)


if __name__ == "__main__":
    # Test forecasters
    logging.basicConfig(level=logging.INFO)
    
    # Generate synthetic data
    np.random.seed(42)
    t = np.arange(1000)
    y = 100 + 20 * np.sin(2 * np.pi * t / 24) + np.random.normal(0, 5, 1000)
    train_data = pd.Series(y[:800], index=pd.date_range('2025-01-01', periods=800, freq='min'))
    test_data = pd.Series(y[800:], index=pd.date_range('2025-01-01 13:20', periods=200, freq='min'))
    
    print("Training forecasters...")
    forecasters = [
        create_forecaster('xgboost'),
        create_forecaster('lightgbm'),
    ]
    
    for fc in forecasters:
        if fc.fit(train_data):
            pred = fc.predict(steps=24)
            if pred is not None:
                print(f"{fc.name} predictions: {pred[:5]}")

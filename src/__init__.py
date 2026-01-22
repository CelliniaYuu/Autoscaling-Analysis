"""
Autoscaling Analysis System
Main package for load forecasting and scaling optimization
"""

__version__ = "1.0.0"
__author__ = "HAMIC Team"

from .data_loader import HTTPLogParser, TimeSeriesAggregator, load_and_prepare_data
from .forecasters import (
    create_forecaster,
    ExponentialSmoothingForecaster,
    SeasonalForecaster,
    LSTMForecaster,
    XGBoostForecaster,
    RandomForestForecaster,
    ProphetForecaster,
    EnsembleForecaster
)
from .autoscaling import (
    ScalingAction,
    ThresholdScalingPolicy,
    PredictiveScalingPolicy,
    HysteresisScalingPolicy,
    AutoscalingSimulator,
    CostAnalyzer,
    AnomalyDetector
)

__all__ = [
    # Data loading
    'HTTPLogParser',
    'TimeSeriesAggregator',
    'load_and_prepare_data',
    
    # Forecasting
    'create_forecaster',
    'ExponentialSmoothingForecaster',
    'SeasonalForecaster',
    'LSTMForecaster',
    'XGBoostForecaster',
    'RandomForestForecaster',
    'ProphetForecaster',
    'EnsembleForecaster',
    
    # Autoscaling
    'ScalingAction',
    'ThresholdScalingPolicy',
    'PredictiveScalingPolicy',
    'HysteresisScalingPolicy',
    'AutoscalingSimulator',
    'CostAnalyzer',
    'AnomalyDetector',
]

"""
Main training pipeline for autoscaling analysis
"""
import os
import sys
import random
import argparse
import json
import logging
from pathlib import Path
from dotenv import load_dotenv
import joblib

import numpy as np
import pandas as pd
from datetime import datetime

# ==================== CRITICAL: Set Random Seeds for Reproducibility ====================
# This MUST be done before any other imports that use randomness
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

# Set TensorFlow seed if available
try:
    import tensorflow as tf
    tf.random.set_seed(SEED)
    # For TensorFlow 2.x
    tf.keras.utils.set_random_seed(SEED)
except ImportError:
    pass

# Set PyTorch seed if available
try:
    import torch
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(SEED)
        torch.cuda.manual_seed_all(SEED)
except ImportError:
    pass

# ======================================================================================

# Import project modules
from src.data_loader import load_and_prepare_data, HTTPLogParser, TimeSeriesAggregator
from src.forecasters import (
    create_forecaster, EnsembleForecaster,
    ExponentialSmoothingForecaster, SeasonalForecaster, XGBoostForecaster,
    RandomForestForecaster, LSTMForecaster
)
from src.autoscaling import (
    ThresholdScalingPolicy, PredictiveScalingPolicy,
    HysteresisScalingPolicy, CostAnalyzer, AnomalyDetector
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Load environment
load_dotenv()


class AutoscalingPipeline:
    """Complete autoscaling analysis pipeline with feature engineering & optimization"""
    
    def __init__(self, config_path=None):
        self.config = self._load_config(config_path)
        self.train_data = None
        self.models = {}
        self.results = {}
    
    def _load_config(self, config_path=None):
        """Load configuration from env or config file"""
        config = {
            'data_folder': os.getenv('DATA_FOLDER', 'DATA'),
            'train_data_path': os.getenv('TRAIN_DATA_PATH', 'DATA/clean_data_train.txt'),
            'test_data_path': os.getenv('TEST_DATA_PATH', 'DATA/clean_data_test.txt'),
            'output_folder': os.getenv('OUTPUT_FOLDER', 'outputs'),
            'train_end_date': os.getenv('TRAIN_END_DATE', '1995-08-22'),
            'time_windows': os.getenv('TIME_WINDOWS', '1m,5m,15m').split(','),
            'random_state': int(os.getenv('RANDOM_STATE', 42)),
            'models': os.getenv('MODELS', 'xgboost,lightgbm').split(','),
            'metrics': os.getenv('EVALUATION_METRICS', 'rmse,mse,mae,mape').split(','),
        }
        
        # Create output directory
        Path(config['output_folder']).mkdir(exist_ok=True)
        
        return config
    
    def load_data(self):
        """Load and prepare data"""
        logger.info("=" * 60)
        logger.info("PHASE 1: DATA LOADING & PREPARATION")
        logger.info("=" * 60)
        
        # Load cleaned train data
        train_path = Path(self.config['train_data_path'])
        
        if not train_path.exists():
            logger.error(f"Train data file not found: {train_path}")
            raise FileNotFoundError(f"Train data file not found: {train_path}")
        
        # Load train logs
        logger.info(f"Loading logs from {train_path}...")
        train_data, _, quality_report = load_and_prepare_data(
            str(train_path),
            train_end_date=self.config['train_end_date']
        )
        
        self.train_data = train_data
        self.quality_report = quality_report
        
        # Save quality report
        quality_path = Path(self.config['output_folder']) / 'data_quality_report.json'
        with open(quality_path, 'w') as f:
            json.dump(quality_report, f, indent=2, default=str)
        logger.info(f"Data quality report saved to {quality_path}")
        
        logger.info(f"Train data windows: {list(train_data.keys())}")
        
        return train_data
    
    def train_forecasters(self, window='5m'):
        """Train all forecasters with feature engineering support"""
        logger.info("=" * 60)
        logger.info(f"PHASE 2: MODEL TRAINING ({window})")
        logger.info("=" * 60)
        
        if window not in self.train_data:
            logger.error(f"Window {window} not found in data")
            return {}
        
        train_df = self.train_data[window].copy()
        
        # Feature engineering: add temporal features
        train_df['hour'] = train_df.index.hour
        train_df['day_of_week'] = train_df.index.dayofweek
        train_df['is_weekend'] = (train_df['day_of_week'] >= 5).astype(int)
        
        # Rolling statistics
        train_df['rolling_mean_24h'] = train_df['requests'].rolling(window=24, min_periods=1).mean()
        train_df['rolling_std_24h'] = train_df['requests'].rolling(window=24, min_periods=1).std()
        
        train_series = train_df['requests']
        logger.info(f"Train data shape: {train_series.shape}")
        logger.info(f"Features: requests, hour, day_of_week, is_weekend, rolling_mean_24h, rolling_std_24h")
        
        trained_models = {}
        
        for model_name in self.config['models']:
            logger.info(f"\nTraining {model_name.upper()}...")
            try:
                # LSTM: special config
                if model_name.lower() == 'lstm':
                    model = create_forecaster(model_name, n_lags=24, units=32, epochs=10)
                else:
                    model = create_forecaster(model_name, n_lags=24)
                
                if model.fit(train_series):
                    trained_models[model_name] = model
                    logger.info(f"✓ {model_name.upper()} trained successfully")
                else:
                    logger.warning(f"✗ Failed to train {model_name}")
            
            except Exception as e:
                logger.error(f"Error training {model_name}: {e}")
        
        self.models[window] = trained_models
        return trained_models
    
    def evaluate_forecasters(self, window='5m', forecast_steps=24):
        """Evaluate forecasters on test set"""
        logger.info("=" * 60)
        logger.info(f"PHASE 3: MODEL EVALUATION ({window})")
        logger.info("=" * 60)
        
        if window not in self.models or not self.models[window]:
            logger.warning(f"No trained models for window {window}")
            return {}
        
        test_series = self.train_data[window]['requests']
        evaluation_results = {}
        
        for model_name, model in self.models[window].items():
            logger.info(f"\nEvaluating {model_name.upper()}...")
            try:
                # Generate predictions
                predictions = model.predict(steps=min(forecast_steps, len(test_series)))
                
                if predictions is None:
                    logger.warning(f"Failed to generate predictions for {model_name}")
                    continue
                
                # Evaluate
                y_true = test_series[:len(predictions)].values
                metrics = model.evaluate(y_true, predictions)
                
                evaluation_results[model_name] = {
                    **metrics,
                    'sample_predictions': predictions[:10].tolist()
                }
                
                logger.info(f"  RMSE: {metrics['rmse']:.4f}")
                logger.info(f"  MAE:  {metrics['mae']:.4f}")
                logger.info(f"  MAPE: {metrics['mape']:.4f}%")
            
            except Exception as e:
                logger.error(f"Error evaluating {model_name}: {e}")
        
        self.results[window] = evaluation_results
        return evaluation_results
    
    def run_autoscaling_simulation(self, window='5m'):
        """Simulate autoscaling policies"""
        logger.info("=" * 60)
        logger.info(f"PHASE 4: AUTOSCALING SIMULATION ({window})")
        logger.info("=" * 60)
        
        # Get train loads
        loads = self.train_data[window]['requests'].values
        max_load = np.max(loads)
        normalized_loads = loads / (max_load + 1e-8)
        
        # Create policies
        policies = [
            ThresholdScalingPolicy(scale_out_threshold=0.75, scale_in_threshold=0.30),
            PredictiveScalingPolicy(scale_out_threshold=0.75, scale_in_threshold=0.30),
            HysteresisScalingPolicy(scale_out_threshold=0.75, scale_in_threshold=0.30),
        ]
        
        # Compare policies
        comparison_results = CostAnalyzer.compare_policies(
            loads, 
            policies,
            capacity_per_server=10000,
            cost_per_server_hour=float(os.getenv('UNIT_COST_PER_SERVER_HOUR', 0.10))
        )
        
        logger.info("\nAutoscaling Policy Comparison:")
        logger.info("-" * 40)
        for policy_name, metrics in comparison_results.items():
            logger.info(f"\n{policy_name}:")
            for metric, value in metrics.items():
                logger.info(f"  {metric}: {value:.4f}")
        
        return comparison_results
    
    def detect_anomalies(self, window='5m'):
        """Detect anomalies in the data with professional DDoS detection"""
        logger.info("=" * 60)
        logger.info(f"PHASE 5: ANOMALY DETECTION ({window})")
        logger.info("=" * 60)
        
        loads = self.train_data[window]['requests'].values
        error_rates = self.train_data[window]['error_rate'].values if 'error_rate' in self.train_data[window].columns else np.zeros_like(loads)
        
        # Detect spikes
        spikes = AnomalyDetector.detect_spike(loads, window=10, threshold=2.0)
        spike_indices = np.where(spikes)[0]
        
        logger.info(f"Detected {len(spike_indices)} spikes")
        
        # Detect potential DDoS with advanced scoring
        ddos_result = AnomalyDetector.detect_ddos(
            loads,
            error_rates,
            time_window_minutes=5,
            adaptive=True
        )
        
        ddos_anomalies = ddos_result['anomalies']
        ddos_scores = ddos_result['scores']
        ddos_confidence = ddos_result['confidence']
        ddos_indices = np.where(ddos_anomalies)[0]
        
        logger.info(f"Detected {len(ddos_indices)} potential DDoS events")
        
        # High-confidence DDoS alerts
        high_conf_indices = ddos_indices[ddos_confidence[ddos_indices] > 80]
        logger.info(f"High-confidence DDoS alerts: {len(high_conf_indices)}")
        
        return {
            'spike_count': len(spike_indices),
            'ddos_count': len(ddos_indices),
            'ddos_high_confidence_count': len(high_conf_indices),
            'spike_indices': spike_indices[:10].tolist(),
            'ddos_indices': ddos_indices[:10].tolist(),
            'ddos_scores': ddos_scores[:10].tolist(),
            'ddos_confidence': ddos_confidence[:10].tolist(),
            'avg_ddos_score': float(np.mean(ddos_scores)),
            'avg_ddos_confidence': float(np.mean(ddos_confidence))
        }
    
    def _normalize_window_name(self, window):
        """Normalize window names: 1m -> 1min, 5m -> 5min, etc."""
        mapping = {'1m': '1min', '5m': '5min', '15m': '15min', '1h': '1h'}
        return mapping.get(window.strip(), window.strip())
    
    def run(self):
        """Run complete pipeline with all phases"""
        logger.info("\n" + "=" * 60)
        logger.info("AUTOSCALING ANALYSIS PIPELINE")
        logger.info("=" * 60)
        
        # Phase 1: Load data
        self.load_data()
        
        # Phases 2-5: For each time window
        for window_raw in self.config['time_windows']:
            window = self._normalize_window_name(window_raw)
            logger.info(f"\n{'*' * 60}")
            logger.info(f"Processing window: {window_raw}")
            logger.info(f"{'*' * 60}")
            
            # Phase 2: Train models (with feature engineering)
            self.train_forecasters(window)
            
            # Phase 3: Evaluate models
            self.evaluate_forecasters(window)
            
            # Phase 4: Autoscaling simulation
            self.run_autoscaling_simulation(window)
            
            # Phase 5: Anomaly detection
            self.detect_anomalies(window)
        
        # Save results
        self._save_results()
        
        logger.info("\n" + "=" * 60)
        logger.info("PIPELINE COMPLETED")
        logger.info("=" * 60)
    
    def _save_results(self):
        """Save results and models to files"""
        output_path = Path(self.config['output_folder'])
        models_path = output_path / 'models'
        models_path.mkdir(exist_ok=True)
        
        # Save models with joblib
        logger.info("Saving trained models...")
        for window, models_dict in self.models.items():
            window_folder = models_path / window
            window_folder.mkdir(exist_ok=True)
            
            for model_name, model in models_dict.items():
                model_file = window_folder / f"{model_name}.pkl"
                joblib.dump(model, model_file)
                logger.info(f"  ✓ {window}/{model_name}.pkl saved")
        
        # Save evaluation results
        results_file = output_path / 'evaluation_results.json'
        with open(results_file, 'w') as f:
            # Convert numpy types for JSON
            json_results = {}
            for window, metrics in self.results.items():
                json_results[window] = {}
                for model, m_dict in metrics.items():
                    json_results[window][model] = {
                        k: float(v) if isinstance(v, (np.floating, np.integer)) else v
                        for k, v in m_dict.items()
                    }
            json.dump(json_results, f, indent=2)
        
        logger.info(f"Results saved to {results_file}")


def main():
    parser = argparse.ArgumentParser(description="Autoscaling Analysis Pipeline")
    parser.add_argument('--config', type=str, help='Config file path')
    parser.add_argument('--window', type=str, default='5m', help='Time window to analyze')
    
    args = parser.parse_args()
    
    pipeline = AutoscalingPipeline(args.config)
    pipeline.run()


if __name__ == "__main__":
    main()

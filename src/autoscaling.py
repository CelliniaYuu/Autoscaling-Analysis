"""
Autoscaling optimization and policy engine
"""
import numpy as np
import pandas as pd
from enum import Enum
import logging

logger = logging.getLogger(__name__)


class ScalingAction(Enum):
    """Scaling actions"""
    SCALE_OUT = 1
    SCALE_IN = -1
    NO_ACTION = 0


class ScalingPolicy:
    """Base scaling policy"""
    
    def __init__(self, name):
        self.name = name
    
    def recommend_action(self, current_load, predictions):
        """Recommend scaling action based on load and predictions"""
        raise NotImplementedError


class ThresholdScalingPolicy(ScalingPolicy):
    """Simple threshold-based scaling"""
    
    def __init__(self, scale_out_threshold=0.75, scale_in_threshold=0.30):
        super().__init__("ThresholdScaling")
        self.scale_out_threshold = scale_out_threshold
        self.scale_in_threshold = scale_in_threshold
    
    def recommend_action(self, current_load, predictions=None):
        """
        Recommend action based on current load
        Load normalized to [0, 1]
        """
        if current_load > self.scale_out_threshold:
            return ScalingAction.SCALE_OUT
        elif current_load < self.scale_in_threshold:
            return ScalingAction.SCALE_IN
        else:
            return ScalingAction.NO_ACTION


class PredictiveScalingPolicy(ScalingPolicy):
    """Predictive scaling based on forecasts"""
    
    def __init__(self, scale_out_threshold=0.75, scale_in_threshold=0.30,
                 consecutive_steps=5):
        super().__init__("PredictiveScaling")
        self.scale_out_threshold = scale_out_threshold
        self.scale_in_threshold = scale_in_threshold
        self.consecutive_steps = consecutive_steps
    
    def recommend_action(self, current_load, predictions):
        """
        Recommend action based on predictions
        Scale-out if predictions exceed threshold for consecutive steps
        """
        if predictions is None or len(predictions) == 0:
            return ScalingAction.NO_ACTION
        
        # Check if load exceeds scale-out threshold
        high_load_count = np.sum(predictions > self.scale_out_threshold)
        if high_load_count >= self.consecutive_steps:
            return ScalingAction.SCALE_OUT
        
        # Check if load stays below scale-in threshold
        low_load_count = np.sum(predictions < self.scale_in_threshold)
        if low_load_count >= self.consecutive_steps:
            return ScalingAction.SCALE_IN
        
        return ScalingAction.NO_ACTION


class HysteresisScalingPolicy(ScalingPolicy):
    """Scaling with hysteresis to prevent flapping"""
    
    def __init__(self, scale_out_threshold=0.75, scale_in_threshold=0.30,
                 cooldown_steps=10):
        super().__init__("HysteresisScaling")
        self.scale_out_threshold = scale_out_threshold
        self.scale_in_threshold = scale_in_threshold
        self.cooldown_steps = cooldown_steps
        self.last_action = ScalingAction.NO_ACTION
        self.cooldown_counter = 0
    
    def recommend_action(self, current_load, predictions=None):
        """
        Recommend action with cooldown to prevent rapid scaling
        """
        # Decrease cooldown counter
        if self.cooldown_counter > 0:
            self.cooldown_counter -= 1
            return ScalingAction.NO_ACTION
        
        # Determine desired action
        if current_load > self.scale_out_threshold:
            action = ScalingAction.SCALE_OUT
        elif current_load < self.scale_in_threshold:
            action = ScalingAction.SCALE_IN
        else:
            action = ScalingAction.NO_ACTION
        
        # Apply action with cooldown
        if action != ScalingAction.NO_ACTION:
            self.last_action = action
            self.cooldown_counter = self.cooldown_steps
            return action
        
        return ScalingAction.NO_ACTION


class AutoscalingSimulator:
    """Simulate autoscaling and calculate costs"""
    
    def __init__(self, initial_servers=2, cost_per_server_hour=0.10,
                 scale_out_increment=1, scale_in_decrement=1,
                 max_servers=10, min_servers=1):
        self.initial_servers = initial_servers
        self.current_servers = initial_servers
        self.cost_per_server_hour = cost_per_server_hour
        self.scale_out_increment = scale_out_increment
        self.scale_in_decrement = scale_in_decrement
        self.max_servers = max_servers
        self.min_servers = min_servers
        
        self.history = []
        self.total_cost = 0
        self.scaling_events = []
    
    def get_required_servers(self, load, capacity_per_server=1000):
        """Calculate required servers for given load"""
        return max(self.min_servers, int(np.ceil(load / capacity_per_server)))
    
    def apply_action(self, action, timestamp=None):
        """Apply scaling action and update cost"""
        if action == ScalingAction.SCALE_OUT:
            new_servers = min(self.current_servers + self.scale_out_increment, 
                            self.max_servers)
            if new_servers > self.current_servers:
                self.current_servers = new_servers
                self.scaling_events.append({
                    'timestamp': timestamp,
                    'action': 'scale_out',
                    'servers': new_servers
                })
                logger.info(f"[{timestamp}] Scale OUT to {new_servers} servers")
        
        elif action == ScalingAction.SCALE_IN:
            new_servers = max(self.current_servers - self.scale_in_decrement, 
                            self.min_servers)
            if new_servers < self.current_servers:
                self.current_servers = new_servers
                self.scaling_events.append({
                    'timestamp': timestamp,
                    'action': 'scale_in',
                    'servers': new_servers
                })
                logger.info(f"[{timestamp}] Scale IN to {new_servers} servers")
        
        # Calculate cost for this period (hourly cost prorated)
        period_cost = self.current_servers * self.cost_per_server_hour / 60  # per minute
        self.total_cost += period_cost
        
        return self.current_servers
    
    def reset(self):
        """Reset simulator"""
        self.current_servers = self.initial_servers
        self.total_cost = 0
        self.history = []
        self.scaling_events = []


class CostAnalyzer:
    """Analyze and compare costs for different policies"""
    
    @staticmethod
    def calculate_sla_penalty(response_times, sla_threshold_ms=200):
        """Calculate penalty for SLA violations"""
        violations = np.sum(response_times > sla_threshold_ms)
        return violations
    
    @staticmethod
    def compare_policies(loads, policies, capacity_per_server=1000,
                        cost_per_server_hour=0.10):
        """
        Compare multiple policies
        
        Args:
            loads: array of load values
            policies: list of ScalingPolicy instances
            capacity_per_server: requests per server per minute
            cost_per_server_hour: cost per server per hour
        
        Returns:
            dict with comparison results
        """
        results = {}
        
        for policy in policies:
            simulator = AutoscalingSimulator(
                cost_per_server_hour=cost_per_server_hour
            )
            
            # Normalize loads to [0, 1]
            max_load = np.max(loads)
            normalized_loads = loads / (max_load + 1e-8)
            
            for i, load in enumerate(normalized_loads):
                # For predictive policies, use future loads as predictions
                window_size = 5
                if i + window_size < len(normalized_loads):
                    predictions = normalized_loads[i+1:i+window_size]
                else:
                    predictions = normalized_loads[max(0, i-window_size):i]
                
                # Call recommend_action with predictions for all policies
                action = policy.recommend_action(load, predictions=predictions)
                simulator.apply_action(action, timestamp=i)
            
            # Calculate metrics
            avg_servers = np.mean([ev['servers'] for ev in simulator.scaling_events]) \
                         if simulator.scaling_events else simulator.initial_servers
            scaling_count = len(simulator.scaling_events)
            
            results[policy.name] = {
                'total_cost': simulator.total_cost,
                'avg_servers': avg_servers,
                'scaling_events': scaling_count,
                'final_servers': simulator.current_servers,
                'cost_per_hour': simulator.total_cost / (len(loads) / 60)
            }
        
        return results


class AnomalyDetector:
    """Advanced anomaly detection with professional DDoS/spike analysis"""
    
    # DDoS scoring thresholds (0-100 scale)
    DDOS_SCORE_THRESHOLD = 70
    SPIKE_SCORE_THRESHOLD = 60
    
    @staticmethod
    def detect_spike(loads, window=10, threshold=2.0):
        """
        Detect load spikes using moving average with adaptive thresholding
        
        Args:
            loads: array of load values
            window: moving average window size
            threshold: std dev multiplier for spike threshold
        
        Returns:
            array of boolean indicating anomalies
        """
        if len(loads) < window:
            return np.zeros(len(loads), dtype=bool)
        
        # Calculate moving average and std dev
        ma = pd.Series(loads).rolling(window=window).mean().values
        mstd = pd.Series(loads).rolling(window=window).std().values
        
        # Detect spikes
        anomalies = np.abs(loads - ma) > (threshold * (mstd + 1e-8))
        
        return anomalies
    
    @staticmethod
    def _calculate_rate_of_change(loads, window=5):
        """Calculate rate of change in load"""
        if len(loads) < window:
            return np.zeros(len(loads))
        
        roc = np.zeros(len(loads))
        for i in range(window, len(loads)):
            if loads[i-window] != 0:
                roc[i] = (loads[i] - loads[i-window]) / loads[i-window]
        return roc
    
    @staticmethod
    def _detect_request_rate_anomaly(loads, window=10, threshold_std=3.0):
        """Detect anomalies in request rate (requests per unit time)"""
        if len(loads) < window:
            return np.zeros(len(loads), dtype=bool)
        
        # Calculate rate of change
        roc = AnomalyDetector._calculate_rate_of_change(loads, window)
        roc_mean = np.mean(roc[~np.isnan(roc)])
        roc_std = np.std(roc[~np.isnan(roc)])
        
        # Flag rapid increases
        anomalies = np.abs(roc - roc_mean) > (threshold_std * (roc_std + 1e-8))
        
        return anomalies
    
    @staticmethod
    def _calculate_error_rate_severity_array(error_rates, baseline_percentile=75):
        """
        Calculate error rate severity score array (0-100)
        Higher error rate = higher severity
        """
        if len(error_rates) == 0:
            return np.zeros(0)
        
        baseline = np.percentile(error_rates, baseline_percentile)
        max_error = np.max(error_rates)
        
        # Normalize each error rate to 0-100 scale
        if max_error > baseline:
            severity_array = ((error_rates - baseline) / (max_error - baseline + 1e-8)) * 100
        else:
            severity_array = np.zeros_like(error_rates)
        
        return np.clip(severity_array, 0, 100)
    
    @staticmethod
    def _calculate_load_anomaly_score(loads, window=10, threshold_std=2.5):
        """
        Calculate anomaly score for load (0-100)
        Based on deviation from moving average
        """
        if len(loads) < window:
            return np.zeros(len(loads))
        
        ma = pd.Series(loads).rolling(window=window).mean().values
        mstd = pd.Series(loads).rolling(window=window).std().values
        
        # Calculate z-score
        z_scores = np.abs((loads - ma) / (mstd + 1e-8))
        
        # Replace NaN with 0 (occurs in early window period)
        z_scores = np.nan_to_num(z_scores, nan=0.0)
        
        # Normalize to 0-100
        scores = np.minimum((z_scores / threshold_std) * 100, 100)
        
        return scores
    
    @staticmethod
    def _calculate_sustained_anomaly_factor(anomalies_bool, window=5):
        """
        Calculate sustained anomaly factor (0-100)
        Consecutive anomalies indicate more severity
        """
        if len(anomalies_bool) < window:
            return np.zeros(len(anomalies_bool))
        
        sustained = np.zeros(len(anomalies_bool))
        for i in range(len(anomalies_bool)):
            if i < window:
                window_size = i + 1
            else:
                window_size = window
            
            # Count consecutive anomalies in window
            if i >= window_size:
                count = np.sum(anomalies_bool[i-window_size+1:i+1])
            else:
                count = np.sum(anomalies_bool[:i+1])
            
            # Score: 100 if all consecutive, less if intermittent
            sustained[i] = (count / window_size) * 100
        
        return sustained
    
    @staticmethod
    def detect_ddos(loads, error_rates, request_sources=None, 
                   time_window_minutes=5, adaptive=True):
        """
        Professional DDoS detection with multi-factor scoring
        
        Args:
            loads: array of request loads
            error_rates: array of error rates (0-1 scale)
            request_sources: dict mapping timestamp to list of unique source IPs/hosts
            time_window_minutes: window for pattern analysis (default 5 min)
            adaptive: use adaptive thresholds based on historical data
        
        Returns:
            dict with:
                - anomalies: boolean array of detected DDoS points
                - scores: float array of DDoS scores (0-100)
                - confidence: float array of confidence levels (0-100)
                - details: detailed analysis per point
        """
        if len(loads) == 0 or len(error_rates) == 0:
            return {'anomalies': np.array([]), 'scores': np.array([]), 
                   'confidence': np.array([])}
        
        # Ensure same length
        min_len = min(len(loads), len(error_rates))
        loads = loads[:min_len]
        error_rates = np.clip(error_rates[:min_len], 0, 1)
        
        # Calculate component scores
        load_scores = AnomalyDetector._calculate_load_anomaly_score(loads)
        roc_anomalies = AnomalyDetector._detect_request_rate_anomaly(loads)
        error_severity_array = AnomalyDetector._calculate_error_rate_severity_array(error_rates)
        sustained = AnomalyDetector._calculate_sustained_anomaly_factor(load_scores > 50)
        
        # Adaptive thresholding
        if adaptive:
            load_baseline = np.percentile(loads, 75)
            error_baseline = np.percentile(error_rates, 75)
        else:
            load_baseline = np.percentile(loads, 50)
            error_baseline = 0.3
        
        # Multi-factor DDoS scoring
        ddos_scores = np.zeros(len(loads))
        
        for i in range(len(loads)):
            # Factor 1: Load anomaly (weight: 35%)
            load_factor = load_scores[i] * 0.35
            
            # Factor 2: Error rate severity (weight: 40%) - prioritize errors for DDoS
            error_factor = error_severity_array[i] * 0.40
            
            # Factor 3: Rate of change (weight: 15%)
            roc_factor = 100 * roc_anomalies[i] * 0.15
            
            # Factor 4: Sustained anomaly (weight: 10%)
            sustained_factor = sustained[i] * 0.10
            
            # Combine factors
            ddos_scores[i] = load_factor + error_factor + roc_factor + sustained_factor
        
        # Confidence based on multiple indicators
        confidence = np.zeros(len(loads))
        for i in range(len(loads)):
            indicators = 0
            max_indicators = 4
            
            if load_scores[i] > 50:
                indicators += 1
            if error_rates[i] > error_baseline:
                indicators += 1
            if roc_anomalies[i]:
                indicators += 1
            if sustained[i] > 50:
                indicators += 1
            
            confidence[i] = (indicators / max_indicators) * 100
        
        # Final anomaly detection
        anomalies = ddos_scores > AnomalyDetector.DDOS_SCORE_THRESHOLD
        
        logger.info(f"DDoS Detection Summary:")
        logger.info(f"  - Points analyzed: {len(loads)}")
        logger.info(f"  - Anomalies detected: {np.sum(anomalies)}")
        logger.info(f"  - Average DDoS score: {np.mean(ddos_scores):.2f}")
        logger.info(f"  - Max DDoS score: {np.max(ddos_scores):.2f}")
        logger.info(f"  - Average confidence: {np.mean(confidence):.2f}%")
        
        return {
            'anomalies': anomalies,
            'scores': ddos_scores,
            'confidence': confidence,
            'load_scores': load_scores,
            'error_severity': error_severity_array,
            'roc_anomalies': roc_anomalies,
            'sustained_factor': sustained
        }


def generate_scaling_report(policies_results, save_path=None):
    """Generate scaling analysis report"""
    
    report = "AUTOSCALING POLICY COMPARISON REPORT\n"
    report += "=" * 60 + "\n\n"
    
    for policy_name, metrics in policies_results.items():
        report += f"Policy: {policy_name}\n"
        report += "-" * 40 + "\n"
        for metric, value in metrics.items():
            if isinstance(value, float):
                report += f"  {metric}: {value:.4f}\n"
            else:
                report += f"  {metric}: {value}\n"
        report += "\n"
    
    if save_path:
        with open(save_path, 'w') as f:
            f.write(report)
        logger.info(f"Report saved to {save_path}")
    
    return report


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    
    # Generate synthetic load data
    np.random.seed(42)
    t = np.arange(1440)  # 24 hours in minutes
    loads = 5000 + 2000 * np.sin(2 * np.pi * t / 1440) + np.random.normal(0, 500, 1440)
    loads = np.maximum(loads, 0)
    
    # Test policies
    policies = [
        ThresholdScalingPolicy(scale_out_threshold=0.75, scale_in_threshold=0.30),
        PredictiveScalingPolicy(scale_out_threshold=0.75, scale_in_threshold=0.30),
        HysteresisScalingPolicy(scale_out_threshold=0.75, scale_in_threshold=0.30),
    ]
    
    # Compare policies
    results = CostAnalyzer.compare_policies(loads, policies)
    
    # Generate report
    report = generate_scaling_report(results)
    print(report)
    
    # Test anomaly detection
    anomalies = AnomalyDetector.detect_spike(loads, window=10, threshold=2.0)
    print(f"Detected {np.sum(anomalies)} anomalies out of {len(loads)} data points")

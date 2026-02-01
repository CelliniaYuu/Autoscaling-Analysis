#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Test script demonstrating the new professional DDoS detection system
"""

import sys
import numpy as np
import pandas as pd
from src.autoscaling import AnomalyDetector
import logging

# Fix encoding on Windows
if sys.platform == 'win32':
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_ddos_detection():
    """Test various DDoS detection scenarios"""
    
    print("\n" + "="*80)
    print("🚨 PROFESSIONAL DDoS DETECTION SYSTEM - TEST SUITE")
    print("="*80 + "\n")
    
    # Scenario 1: Normal traffic with spike
    print("\n" + "-"*80)
    print("Scenario 1: Normal Traffic with Legitimate Spike")
    print("-"*80)
    
    # Normal baseline: 5000 requests, gradually varying
    loads_1 = 5000 + np.random.normal(0, 500, 100)
    # One big spike (could be legitimate)
    loads_1[50:55] = 8000
    loads_1 = np.maximum(loads_1, 0)
    
    # Low error rate (legitimate spike = low errors)
    error_rates_1 = 0.05 + np.random.normal(0, 0.02, 100)
    error_rates_1[50:55] = 0.08  # Slightly elevated but still low
    error_rates_1 = np.clip(error_rates_1, 0, 1)
    
    result_1 = AnomalyDetector.detect_ddos(loads_1, error_rates_1, adaptive=True)
    
    print(f"✓ Test 1 Results:")
    print(f"  Anomalies detected: {np.sum(result_1['anomalies'])}")
    print(f"  Avg DDoS score: {np.mean(result_1['scores']):.2f}")
    print(f"  Max DDoS score: {np.max(result_1['scores']):.2f}")
    print(f"  High confidence alerts: {np.sum(result_1['confidence'] > 80)}")
    print(f"  Expected: LOW score (legitimate spike, low errors)")
    
    # Scenario 2: Sustained DDoS attack
    print("\n" + "-"*80)
    print("Scenario 2: Sustained DDoS Attack")
    print("-"*80)
    
    # Normal baseline
    loads_2 = 5000 + np.random.normal(0, 500, 100)
    # Sustained attack: high load for 30 points + gradually increasing
    attack_start = 30
    loads_2[attack_start:attack_start+30] = 12000 + np.linspace(0, 3000, 30)
    loads_2 = np.maximum(loads_2, 0)
    
    # High error rate during attack (DDoS = errors)
    error_rates_2 = 0.05 + np.random.normal(0, 0.02, 100)
    error_rates_2[attack_start:attack_start+30] = 0.35 + np.random.normal(0, 0.05, 30)
    error_rates_2 = np.clip(error_rates_2, 0, 1)
    
    result_2 = AnomalyDetector.detect_ddos(loads_2, error_rates_2, adaptive=True)
    
    attack_indices = np.where(result_2['anomalies'])[0]
    attack_scores = result_2['scores'][attack_indices]
    
    print(f"✓ Test 2 Results:")
    print(f"  Anomalies detected: {np.sum(result_2['anomalies'])}")
    print(f"  Avg DDoS score: {np.mean(result_2['scores']):.2f}")
    print(f"  Max DDoS score: {np.max(result_2['scores']):.2f}")
    print(f"  High confidence alerts: {np.sum(result_2['confidence'] > 80)}")
    if len(attack_indices) > 0:
        print(f"  Attack period avg score: {np.mean(attack_scores):.2f}")
    print(f"  Expected: HIGH score (sustained, high errors)")
    
    # Scenario 3: Distributed attack pattern
    print("\n" + "-"*80)
    print("Scenario 3: Distributed Attack (Multiple Spikes)")
    print("-"*80)
    
    loads_3 = 5000 + np.random.normal(0, 500, 100)
    # Multiple attack waves
    for i in range(3):
        start = 20 + i*20
        loads_3[start:start+8] = 10000
    loads_3 = np.maximum(loads_3, 0)
    
    # High errors during all attack periods
    error_rates_3 = 0.05 + np.random.normal(0, 0.02, 100)
    for i in range(3):
        start = 20 + i*20
        error_rates_3[start:start+8] = 0.30
    error_rates_3 = np.clip(error_rates_3, 0, 1)
    
    result_3 = AnomalyDetector.detect_ddos(loads_3, error_rates_3, adaptive=True)
    
    print(f"✓ Test 3 Results:")
    print(f"  Anomalies detected: {np.sum(result_3['anomalies'])}")
    print(f"  Avg DDoS score: {np.mean(result_3['scores']):.2f}")
    print(f"  Max DDoS score: {np.max(result_3['scores']):.2f}")
    print(f"  High confidence alerts: {np.sum(result_3['confidence'] > 80)}")
    print(f"  Expected: HIGH score (multiple attack patterns)")
    
    # Scenario 4: Rapid ramping attack
    print("\n" + "-"*80)
    print("Scenario 4: Rapid Ramping Attack (Fast Escalation)")
    print("-"*80)
    
    loads_4 = 5000 + np.random.normal(0, 500, 100)
    # Rapid increase in 10 steps
    attack_start = 40
    loads_4[attack_start:attack_start+10] = np.linspace(5500, 15000, 10)
    loads_4 = np.maximum(loads_4, 0)
    
    error_rates_4 = 0.05 + np.random.normal(0, 0.02, 100)
    error_rates_4[attack_start:attack_start+10] = np.linspace(0.08, 0.40, 10)
    error_rates_4 = np.clip(error_rates_4, 0, 1)
    
    result_4 = AnomalyDetector.detect_ddos(loads_4, error_rates_4, adaptive=True)
    
    print(f"✓ Test 4 Results:")
    print(f"  Anomalies detected: {np.sum(result_4['anomalies'])}")
    print(f"  Avg DDoS score: {np.mean(result_4['scores']):.2f}")
    print(f"  Max DDoS score: {np.max(result_4['scores']):.2f}")
    print(f"  High confidence alerts: {np.sum(result_4['confidence'] > 80)}")
    print(f"  Expected: HIGH score (rapid rate of change)")
    
    # Comparison Summary
    print("\n" + "="*80)
    print("📊 COMPARISON SUMMARY")
    print("="*80)
    
    scenarios = [
        ("Legitimate Spike", result_1),
        ("Sustained DDoS", result_2),
        ("Distributed Attack", result_3),
        ("Rapid Ramping", result_4)
    ]
    
    print("\n{:<20} {:<15} {:<15} {:<20}".format("Scenario", "Anomalies", "Avg Score", "High Conf Alerts"))
    print("-" * 70)
    
    for name, result in scenarios:
        n_anomalies = np.sum(result['anomalies'])
        avg_score = np.mean(result['scores'])
        high_conf = np.sum(result['confidence'] > 80)
        print("{:<20} {:<15} {:<15.2f} {:<20}".format(name, n_anomalies, avg_score, high_conf))
    
    # Component analysis for Scenario 2 (clear DDoS case)
    print("\n" + "="*80)
    print("🔍 DETAILED COMPONENT ANALYSIS - Scenario 2 (Sustained DDoS)")
    print("="*80)
    
    attack_mask = np.zeros(len(loads_2), dtype=bool)
    attack_mask[30:60] = True
    
    print(f"\nAttack Period (indices 30-60):")
    print(f"  Load anomaly avg score: {np.mean(result_2['load_scores'][attack_mask]):.2f}")
    print(f"  Error severity avg: {np.mean(result_2['error_severity'][attack_mask]):.2f}")
    print(f"  RoC anomalies detected: {np.sum(result_2['roc_anomalies'][attack_mask])}")
    print(f"  Sustained anomaly factor avg: {np.mean(result_2['sustained_factor'][attack_mask]):.2f}")
    
    print(f"\nNormal Period (indices 0-29):")
    normal_mask = ~attack_mask
    print(f"  Load anomaly avg score: {np.mean(result_2['load_scores'][normal_mask]):.2f}")
    print(f"  RoC anomalies detected: {np.sum(result_2['roc_anomalies'][normal_mask])}")
    print(f"  Sustained anomaly factor avg: {np.mean(result_2['sustained_factor'][normal_mask]):.2f}")
    
    # Final composite DDoS scores
    print("\n" + "="*80)
    print("🎯 FINAL COMPOSITE DDoS SCORES & DECISIONS")
    print("="*80)
    
    for idx, (name, result) in enumerate(scenarios, 1):
        print(f"\n[Scenario {idx}] {name}")
        print("-" * 40)
        
        ddos_points = np.sum(result['anomalies'])
        avg_score = np.mean(result['scores'])
        max_score = np.max(result['scores'])
        avg_confidence = np.mean(result['confidence'])
        high_conf_count = np.sum(result['confidence'] > 80)
        
        print(f"Composite DDoS Score (avg):    {avg_score:.2f}/100")
        print(f"Composite DDoS Score (max):    {max_score:.2f}/100")
        print(f"Confidence Level (avg):        {avg_confidence:.2f}%")
        print(f"High-Confidence Alerts (>80%): {high_conf_count} points")
        print(f"Anomalies Detected (>70):      {ddos_points} points")
        
        # Decision logic
        if avg_score >= 70 or max_score >= 85:
            decision = "🚨 LIKELY DDoS ATTACK"
            severity = "HIGH"
        elif avg_score >= 50 or max_score >= 70:
            decision = "⚠️  SUSPICIOUS ACTIVITY"
            severity = "MEDIUM"
        else:
            decision = "✓ NORMAL TRAFFIC"
            severity = "LOW"
        
        print(f"Decision:                      {decision}")
        print(f"Severity Level:                {severity}")
    
    print("\n" + "="*80)
    print("\n" + "="*80)
    print("✅ All tests completed successfully!")
    print("="*80 + "\n")

if __name__ == "__main__":
    test_ddos_detection()

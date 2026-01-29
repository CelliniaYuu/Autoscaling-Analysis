"""
Script to create sample CSV file for dashboard upload
"""
import pandas as pd
import numpy as np
from datetime import datetime, timedelta

def create_sample_csv(output_file="DATA/sample_load_data.csv", days=30, freq='5min'):
    """Generate sample CSV file with required columns"""
    # Create time index
    end = datetime.now()
    start = end - timedelta(days=days)
    dates = pd.date_range(start, end, freq=freq)
    
    # Generate synthetic load with trend and seasonality
    t = np.arange(len(dates))
    base_load = 5000
    trend = t * 0.1
    daily_pattern = 2000 * np.sin(2 * np.pi * (t % 288) / 288)
    noise = np.random.normal(0, 500, len(t))
    
    load = base_load + trend + daily_pattern + noise
    load = np.maximum(load, 100)
    
    bytes_data = load * np.random.uniform(500, 2000, len(load))
    error_rate = 0.02 + 0.05 * np.sin(2 * np.pi * t / 1440) + np.random.uniform(-0.01, 0.01, len(t))
    error_rate = np.clip(error_rate, 0, 0.1)
    
    df = pd.DataFrame({
        'timestamp': dates,
        'requests': load.astype(int),
        'bytes': bytes_data.astype(int),
        'error_rate': error_rate
    })
    
    # Save to CSV
    df.to_csv(output_file, index=False)
    print(f"✓ Created: {output_file}")
    print(f"  Rows: {len(df)}")
    print(f"  Columns: {list(df.columns)}")
    print(f"\nFirst 5 rows:")
    print(df.head())
    
    return df

if __name__ == "__main__":
    create_sample_csv()

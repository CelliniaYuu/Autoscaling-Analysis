#!/usr/bin/env python
"""
Data cleaning script - process raw logs and save cleaned data
Removes duplicates, invalid records, detects outliers and gaps
Processes train and test files separately
"""

import pandas as pd
import numpy as np
from pathlib import Path
from src.data_loader import HTTPLogParser
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

print("=" * 70)
print("DATA CLEANING PIPELINE")
print("=" * 70)

# Define function to clean single file
def clean_log_file(input_path, output_txt_path, output_csv_path):
    """Clean a single log file and save both TXT and CSV formats"""
    
    # STEP 1: LOAD RAW LOGS
    print(f"\n[STEP 1] LOADING RAW LOGS from {Path(input_path).name}...")
    parser = HTTPLogParser()
    logs = parser.load_logs(str(input_path))
    df = parser.to_dataframe()
    
    print(f"[OK] Loaded: {len(df):,} raw records")
    print(f"     Date range: {df['timestamp'].min()} - {df['timestamp'].max()}")
    
    # STEP 2: REMOVE DUPLICATES
    print(f"\n[STEP 2] REMOVING DUPLICATES...")
    before_dup = len(df)
    df_clean = df.drop_duplicates(subset=['timestamp', 'host', 'method', 'url'], keep='first')
    removed_dup = before_dup - len(df_clean)
    print(f"[OK] Removed: {removed_dup:,} duplicates ({removed_dup/before_dup*100:.1f}%)")
    
    # STEP 3: REMOVE INVALID RECORDS
    print(f"\n[STEP 3] REMOVING INVALID RECORDS...")
    before_invalid = len(df_clean)
    df_clean = df_clean[df_clean['status'].between(100, 599)]
    df_clean = df_clean[df_clean['bytes'] >= 0]
    df_clean = df_clean[df_clean['timestamp'].notna()]
    removed_invalid = before_invalid - len(df_clean)
    print(f"[OK] Removed: {removed_invalid:,} invalid records ({removed_invalid/before_invalid*100:.1f}%)")
    
    # STEP 4: DETECT OUTLIERS
    print(f"\n[STEP 4] DETECTING OUTLIERS (flagged, not removed)...")
    bytes_mean = df_clean['bytes'].mean()
    bytes_std = df_clean['bytes'].std()
    outlier_threshold = bytes_mean + 3 * bytes_std
    df_clean['is_outlier'] = df_clean['bytes'] > outlier_threshold
    outlier_count = df_clean['is_outlier'].sum()
    print(f"[OK] Detected: {outlier_count:,} outliers ({outlier_count/len(df_clean)*100:.2f}%)")
    print(f"     (Threshold: bytes > {outlier_threshold:.0f})")
    
    # STEP 5: DETECT GAPS IN TIME SERIES
    print(f"\n[STEP 5] DETECTING TIME GAPS...")
    df_clean = df_clean.sort_values('timestamp').reset_index(drop=True)
    time_diffs = df_clean['timestamp'].diff()
    gap_mask = time_diffs > pd.Timedelta(minutes=5)
    gap_count = gap_mask.sum()
    max_gap = time_diffs.max()
    print(f"[OK] Detected: {gap_count} gaps (>5 min)")
    if gap_count > 0:
        print(f"     Longest gap: {max_gap}")
    
    # STEP 6: SAVE CLEANED DATA
    print(f"\n[STEP 6] SAVING CLEANED DATA...")
    
    # Save as CSV
    df_clean.to_csv(output_csv_path, index=False)
    csv_size = Path(output_csv_path).stat().st_size / 1e6
    print(f"[OK] CSV: {Path(output_csv_path).name} ({csv_size:.1f} MB)")
    
    # Save as TXT (Apache log format) - vectorized
    print(f"[OK] TXT: {Path(output_txt_path).name} (generating...)")
    timestamp_strs = df_clean['timestamp'].dt.strftime('%d/%b/%Y:%H:%M:%S -0400')
    requests = df_clean[['method', 'url', 'protocol']].apply(lambda x: f"{x['method']} {x['url']} {x['protocol']}", axis=1)
    bytes_val = df_clean['bytes'].apply(lambda x: int(x) if x > 0 else '-')
    log_lines = (df_clean['host'] + ' - - [' + timestamp_strs + '] "' + requests + '" ' + 
                 df_clean['status'].astype(str) + ' ' + bytes_val.astype(str) + '\n')
    
    with open(output_txt_path, 'w', encoding='utf-8', errors='ignore') as f:
        f.writelines(log_lines.values)
    
    txt_size = Path(output_txt_path).stat().st_size / 1e6
    print(f"    Completed: {txt_size:.1f} MB")
    
    return {
        'input_records': before_dup,
        'duplicates_removed': removed_dup,
        'invalid_removed': removed_invalid,
        'final_records': len(df_clean),
        'outliers': outlier_count,
        'gaps': gap_count,
        'csv_path': output_csv_path,
        'txt_path': output_txt_path
    }

# Process train and test files separately
print("\n" + "=" * 70)
print("PROCESSING TRAIN FILE")
print("=" * 70)
train_stats = clean_log_file(
    'DATA/train.txt',
    'DATA/clean_data_train.txt',
    'DATA/clean_data_train.csv'
)

print("\n" + "=" * 70)
print("PROCESSING TEST FILE")
print("=" * 70)
test_stats = clean_log_file(
    'DATA/test.txt',
    'DATA/clean_data_test.txt',
    'DATA/clean_data_test.csv'
)

# FINAL SUMMARY
print("\n" + "=" * 70)
print("CLEANING SUMMARY")
print("=" * 70)

print("\nTRAIN DATA:")
print(f"  Raw records:          {train_stats['input_records']:>15,}")
print(f"  Duplicates removed:   {train_stats['duplicates_removed']:>15,}")
print(f"  Invalid removed:      {train_stats['invalid_removed']:>15,}")
print(f"  Final records:        {train_stats['final_records']:>15,}")
print(f"  Outliers:             {train_stats['outliers']:>15,} (flagged)")
print(f"  Gaps:                 {train_stats['gaps']:>15,} (>5 min)")

print("\nTEST DATA:")
print(f"  Raw records:          {test_stats['input_records']:>15,}")
print(f"  Duplicates removed:   {test_stats['duplicates_removed']:>15,}")
print(f"  Invalid removed:      {test_stats['invalid_removed']:>15,}")
print(f"  Final records:        {test_stats['final_records']:>15,}")
print(f"  Outliers:             {test_stats['outliers']:>15,} (flagged)")
print(f"  Gaps:                 {test_stats['gaps']:>15,} (>5 min)")

# Save combined statistics
stats_path = Path('DATA/cleaning_stats.txt')
with open(stats_path, 'w', encoding='utf-8') as f:
    f.write("DATA CLEANING STATISTICS\n")
    f.write("=" * 50 + "\n\n")
    f.write("TRAIN DATA:\n")
    f.write(f"Raw records:           {train_stats['input_records']:,}\n")
    f.write(f"Duplicates removed:    {train_stats['duplicates_removed']:,}\n")
    f.write(f"Invalid removed:       {train_stats['invalid_removed']:,}\n")
    f.write(f"Cleaned records:       {train_stats['final_records']:,}\n")
    f.write(f"Outliers detected:     {train_stats['outliers']:,}\n")
    f.write(f"Gaps (>5 min):         {train_stats['gaps']}\n\n")
    f.write("TEST DATA:\n")
    f.write(f"Raw records:           {test_stats['input_records']:,}\n")
    f.write(f"Duplicates removed:    {test_stats['duplicates_removed']:,}\n")
    f.write(f"Invalid removed:       {test_stats['invalid_removed']:,}\n")
    f.write(f"Cleaned records:       {test_stats['final_records']:,}\n")
    f.write(f"Outliers detected:     {test_stats['outliers']:,}\n")
    f.write(f"Gaps (>5 min):         {test_stats['gaps']}\n")

print(f"\n[OK] Stats: {stats_path.name}")

print("\n[DONE] CLEANING COMPLETE!")
print("\nFiles created:")
print("  - DATA/clean_data_train.txt  (Train data - Apache log format)")
print("  - DATA/clean_data_train.csv  (Train data - CSV format)")
print("  - DATA/clean_data_test.txt   (Test data - Apache log format)")
print("  - DATA/clean_data_test.csv   (Test data - CSV format)")
print("  - DATA/cleaning_stats.txt    (Statistics)")


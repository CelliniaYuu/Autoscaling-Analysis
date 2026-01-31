#!/usr/bin/env python
"""
Data cleaning script - process raw logs and save cleaned data
Removes duplicates, invalid records, detects outliers and gaps
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

# STEP 1: LOAD RAW LOGS
print("\n[STEP 1] LOADING RAW LOGS...")
raw_data_path = Path('DATA/combined.txt')

# Always recombine to ensure latest data
print("Combining train.txt + test.txt...")
with open('DATA/combined.txt', 'w', encoding='utf-8', errors='ignore') as combined:
    for file in ['DATA/train.txt', 'DATA/test.txt']:
        if Path(file).exists():
            with open(file, 'r', encoding='utf-8', errors='ignore') as f:
                combined.write(f.read())

parser = HTTPLogParser()
logs = parser.load_logs(str(raw_data_path))
df = parser.to_dataframe()

print(f"[OK] Loaded: {len(df):,} raw records")
print(f"     Date range: {df['timestamp'].min()} - {df['timestamp'].max()}")

# STEP 2: REMOVE DUPLICATES
print("\n[STEP 2] REMOVING DUPLICATES...")
before_dup = len(df)
df_clean = df.drop_duplicates(subset=['timestamp', 'host', 'method', 'url'], keep='first')
removed_dup = before_dup - len(df_clean)
print(f"[OK] Removed: {removed_dup:,} duplicates ({removed_dup/before_dup*100:.1f}%)")

# STEP 3: REMOVE INVALID RECORDS
print("\n[STEP 3] REMOVING INVALID RECORDS...")
before_invalid = len(df_clean)
df_clean = df_clean[df_clean['status'].between(100, 599)]
df_clean = df_clean[df_clean['bytes'] >= 0]
df_clean = df_clean[df_clean['timestamp'].notna()]
removed_invalid = before_invalid - len(df_clean)
print(f"[OK] Removed: {removed_invalid:,} invalid records ({removed_invalid/before_invalid*100:.1f}%)")

# STEP 4: DETECT OUTLIERS
print("\n[STEP 4] DETECTING OUTLIERS (flagged, not removed)...")
bytes_mean = df_clean['bytes'].mean()
bytes_std = df_clean['bytes'].std()
outlier_threshold = bytes_mean + 3 * bytes_std
df_clean['is_outlier'] = df_clean['bytes'] > outlier_threshold
outlier_count = df_clean['is_outlier'].sum()
print(f"[OK] Detected: {outlier_count:,} outliers ({outlier_count/len(df_clean)*100:.2f}%)")
print(f"     (Threshold: bytes > {outlier_threshold:.0f})")

# STEP 5: DETECT GAPS IN TIME SERIES
print("\n[STEP 5] DETECTING TIME GAPS...")
df_clean = df_clean.sort_values('timestamp').reset_index(drop=True)
time_diffs = df_clean['timestamp'].diff()
gap_mask = time_diffs > pd.Timedelta(minutes=5)
gap_count = gap_mask.sum()
max_gap = time_diffs.max()
print(f"[OK] Detected: {gap_count} gaps (>5 min)")
if gap_count > 0:
    print(f"     Longest gap: {max_gap}")

# STEP 6: SAVING CLEANED DATA
print("\n[STEP 6] SAVING CLEANED DATA...")

# Save as CSV
csv_path = Path('DATA/cleaned_data.csv')
df_clean.to_csv(csv_path, index=False)
csv_size = csv_path.stat().st_size / 1e6
print(f"[OK] CSV: {csv_path.name} ({csv_size:.1f} MB)")

# Save as TXT (Apache log format)
txt_path = Path('DATA/cleaned_data.txt')
with open(txt_path, 'w', encoding='utf-8', errors='ignore') as f:
    for _, row in df_clean.iterrows():
        timestamp_str = row['timestamp'].strftime('%d/%b/%Y:%H:%M:%S -0400')
        request = f"{row['method']} {row['url']} {row['protocol']}"
        bytes_val = int(row['bytes']) if row['bytes'] > 0 else '-'
        log_line = f"{row['host']} - - [{timestamp_str}] \"{request}\" {row['status']} {bytes_val}\n"
        f.write(log_line)

txt_size = txt_path.stat().st_size / 1e6
print(f"[OK] TXT: {txt_path.name} ({txt_size:.1f} MB)")

# Save statistics
stats_path = Path('DATA/cleaning_stats.txt')
with open(stats_path, 'w', encoding='utf-8') as f:
    f.write("DATA CLEANING STATISTICS\n")
    f.write("=" * 50 + "\n\n")
    f.write(f"Raw records:           {before_dup:,}\n")
    f.write(f"Duplicates removed:    {removed_dup:,} ({removed_dup/before_dup*100:.1f}%)\n")
    f.write(f"Invalid removed:       {removed_invalid:,} ({removed_invalid/before_invalid*100:.1f}%)\n")
    f.write(f"Cleaned records:       {len(df_clean):,}\n")
    f.write(f"Outliers detected:     {outlier_count:,} ({outlier_count/len(df_clean)*100:.2f}%)\n")
    f.write(f"Gaps (>5 min):         {gap_count}\n")
    f.write(f"Date range:            {df_clean['timestamp'].min()} - {df_clean['timestamp'].max()}\n")

print(f"[OK] Stats: {stats_path.name}")

# FINAL SUMMARY
print("\n" + "=" * 70)
print("CLEANING SUMMARY")
print("=" * 70)
print(f"\nRaw records:          {before_dup:>15,}")
print(f"Duplicates removed:   {removed_dup:>15,} ({removed_dup/before_dup*100:>5.1f}%)")
print(f"Invalid removed:      {removed_invalid:>15,} ({removed_invalid/before_invalid*100:>5.1f}%)")
print(f"Final records:        {len(df_clean):>15,}")
print(f"\nOutliers:             {outlier_count:>15,} (flagged)")
print(f"Gaps:                 {gap_count:>15,} (>5 min)")

print("\n[DONE] CLEANING COMPLETE!")
print("\nFiles created:")
print("  - DATA/cleaned_data.csv   (CSV format)")
print("  - DATA/cleaned_data.txt   (Apache log format)")
print("  - DATA/cleaning_stats.txt (Statistics)")


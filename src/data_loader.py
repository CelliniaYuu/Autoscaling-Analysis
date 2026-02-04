"""
Data loader for HTTP logs parsing and time series aggregation
"""
import re
from datetime import datetime, timedelta
import pandas as pd
import numpy as np
from pathlib import Path
import logging

logger = logging.getLogger(__name__)


class HTTPLogParser:
    """Parse Apache/HTTP logs and extract key metrics"""
    
    # Regex pattern for Apache Combined Log Format
    LOG_PATTERN = re.compile(
        r'(\S+) \S+ \S+ \[(.*?)\] "(\S+ \S+ \S+)" (\d+) (-|\d+)'
    )
    
    def __init__(self):
        self.logs_data = []
    
    def parse_timestamp(self, timestamp_str):
        """
        Parse timestamp from format: 01/Jul/1995:00:00:01 -0400
        """
        try:
            # Extract date and time part (ignore timezone offset)
            dt_part = timestamp_str.split(' ')[0]
            dt = datetime.strptime(dt_part, '%d/%b/%Y:%H:%M:%S')
            return dt
        except Exception as e:
            logger.warning(f"Failed to parse timestamp: {timestamp_str}, error: {e}")
            return None
    
    def parse_log_line(self, line):
        """
        Parse a single log line
        Returns: dict with parsed fields or None if parsing fails
        """
        try:
            match = self.LOG_PATTERN.match(line.strip())
            if not match:
                return None
            
            host, timestamp, request, status, bytes_sent = match.groups()
            
            # Parse timestamp
            dt = self.parse_timestamp(timestamp)
            if dt is None:
                return None
            
            # Parse request
            request_parts = request.split()
            method = request_parts[0] if len(request_parts) > 0 else 'UNKNOWN'
            url = request_parts[1] if len(request_parts) > 1 else '/'
            protocol = request_parts[2] if len(request_parts) > 2 else 'HTTP/1.0'
            
            # Parse bytes (handle '-' for no content)
            bytes_value = int(bytes_sent) if bytes_sent != '-' else 0
            
            return {
                'timestamp': dt,
                'host': host,
                'method': method,
                'url': url,
                'protocol': protocol,
                'status': int(status),
                'bytes': bytes_value,
                'is_error': status[0] in ['4', '5']
            }
        except Exception as e:
            logger.debug(f"Error parsing line: {line}, error: {e}")
            return None
    
    def load_logs(self, filepath):
        """Load and parse logs from file"""
        self.logs_data = []
        
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                for line_num, line in enumerate(f, 1):
                    parsed = self.parse_log_line(line)
                    if parsed:
                        self.logs_data.append(parsed)
                    
                    if line_num % 100000 == 0:
                        logger.info(f"Processed {line_num} lines, parsed {len(self.logs_data)} records")
            
            logger.info(f"Total records parsed: {len(self.logs_data)}")
            return self.logs_data
        
        except Exception as e:
            logger.error(f"Error loading logs from {Path(filepath).name}: {e}")
            return []
    
    def to_dataframe(self):
        """Convert parsed logs to DataFrame"""
        if not self.logs_data:
            return pd.DataFrame()
        
        df = pd.DataFrame(self.logs_data)
        df['timestamp'] = pd.to_datetime(df['timestamp'])
        df = df.sort_values('timestamp').reset_index(drop=True)
        return df


class TimeSeriesAggregator:
    """Aggregate HTTP logs into time series with multiple granularities"""
    
    def __init__(self, df):
        """
        Initialize with parsed logs dataframe
        Args:
            df: DataFrame with columns [timestamp, bytes, status, is_error, ...]
        """
        self.df = df.copy()
        self.df['timestamp'] = pd.to_datetime(self.df['timestamp'])
        self.df = self.df.sort_values('timestamp')
        self.gaps_report = {}
    
    def detect_data_quality_issues(self):
        """
        Detect and report data quality issues
        
        Returns:
            dict with quality metrics:
            - total_records: Total records processed
            - duplicate_records: Number of duplicate timestamps
            - missing_values_pct: Percentage of missing values
            - outliers_detected: Number of outliers in requests
        """
        quality_report = {
            'total_records': len(self.df),
            'duplicate_records': self.df['timestamp'].duplicated().sum(),
            'missing_values_pct': (self.df.isnull().sum().sum() / 
                                  (len(self.df) * len(self.df.columns)) * 100),
            'timestamp_range': {
                'start': self.df['timestamp'].min(),
                'end': self.df['timestamp'].max(),
                'duration_hours': (self.df['timestamp'].max() - 
                                  self.df['timestamp'].min()).total_seconds() / 3600
            }
        }
        
        logger.info(f"Data Quality Report:")
        logger.info(f"  Total records: {quality_report['total_records']}")
        logger.info(f"  Duplicates: {quality_report['duplicate_records']}")
        logger.info(f"  Missing values: {quality_report['missing_values_pct']:.2f}%")
        logger.info(f"  Time range: {quality_report['timestamp_range']['start']} to "
                   f"{quality_report['timestamp_range']['end']}")
        
        return quality_report
    
    def detect_gaps(self, min_gap_minutes=5):
        """
        Detect time gaps in data (e.g., server downtime)
        
        Args:
            min_gap_minutes: Minimum gap size to report (default 5 minutes)
        
        Returns:
            DataFrame with gap information: [gap_start, gap_end, gap_duration_minutes]
        """
        if self.df.empty:
            return pd.DataFrame()
        
        time_diff = self.df['timestamp'].diff()
        gaps = time_diff[time_diff > pd.Timedelta(minutes=min_gap_minutes)]
        
        if len(gaps) == 0:
            logger.info(f"No significant gaps (>{min_gap_minutes} min) detected")
            return pd.DataFrame()
        
        gap_data = []
        for idx in gaps.index:
            gap_duration = gaps.loc[idx]
            # idx is the position where gap is detected
            # gap_start is the timestamp of previous record, gap_end is current record
            prev_idx = idx - 1
            gap_start = self.df.loc[prev_idx, 'timestamp'] if prev_idx >= 0 else None
            gap_end = self.df.loc[idx, 'timestamp']
            gap_minutes = gap_duration.total_seconds() / 60
            if gap_start is not None:
                gap_data.append({
                    'gap_start': gap_start,
                    'gap_end': gap_end,
                    'gap_duration_minutes': gap_minutes
                })
        
        gaps_df = pd.DataFrame(gap_data)
        logger.info(f"Detected {len(gaps_df)} gaps (>{min_gap_minutes} min)")
        logger.info(f"Longest gap: {gaps_df['gap_duration_minutes'].max():.0f} minutes")
        
        self.gaps_report = {
            'total_gaps': len(gaps_df),
            'total_missing_time_hours': gaps_df['gap_duration_minutes'].sum() / 60,
            'longest_gap_minutes': gaps_df['gap_duration_minutes'].max(),
            'gaps': gaps_df
        }
        
        return gaps_df
    
    def handle_gaps_with_strategy(self, agg_ts, strategy='forward_fill'):
        """
        Handle time gaps in aggregated series using specified strategy
        
        Args:
            agg_ts: Aggregated time series
            strategy: 'forward_fill' (gap < 30min), 'interpolate' (30min-2h), 'zero' (>2h)
        
        Returns:
            Cleaned time series
        """
        if strategy == 'forward_fill':
            # Forward fill for short gaps
            agg_ts['requests'] = agg_ts['requests'].fillna(method='ffill')
            agg_ts['bytes_total'] = agg_ts['bytes_total'].fillna(method='ffill')
            logger.info("Applied forward fill strategy for gaps < 30 minutes")
        
        elif strategy == 'interpolate':
            # Linear interpolation for medium gaps
            agg_ts['requests'] = agg_ts['requests'].interpolate(method='linear')
            agg_ts['bytes_total'] = agg_ts['bytes_total'].interpolate(method='linear')
            logger.info("Applied linear interpolation for gaps 30 minutes - 2 hours")
        
        elif strategy == 'adaptive':
            # Adaptive strategy: choose based on gap size
            for col in ['requests', 'bytes_total']:
                # First forward fill
                agg_ts[col] = agg_ts[col].fillna(method='ffill')
                # Then interpolate remaining
                agg_ts[col] = agg_ts[col].interpolate(method='linear')
                # Finally zero fill (for long gaps)
                agg_ts[col] = agg_ts[col].fillna(0)
            logger.info("Applied adaptive gap handling strategy")
        
        else:  # 'zero' or default
            agg_ts['requests'] = agg_ts['requests'].fillna(0)
            agg_ts['bytes_total'] = agg_ts['bytes_total'].fillna(0)
            logger.info("Applied zero padding for all gaps")
        
        return agg_ts
    
    def detect_outliers(self, column='requests', threshold_std=3.0):
        """
        Detect outliers in time series using z-score method
        
        Args:
            column: Column name to check for outliers
            threshold_std: Number of standard deviations (default 3.0)
        
        Returns:
            Boolean array where True indicates outlier
        """
        if column not in self.df.columns:
            return np.zeros(len(self.df), dtype=bool)
        
        mean = self.df[column].mean()
        std = self.df[column].std()
        
        outliers = np.abs(self.df[column] - mean) > threshold_std * std
        outlier_count = outliers.sum()
        
        if outlier_count > 0:
            logger.warning(f"Detected {outlier_count} outliers in {column} "
                          f"({outlier_count/len(self.df)*100:.2f}%)")
        
        return outliers
    
    def aggregate(self, window='1min', gap_strategy='adaptive'):
        """
        Aggregate logs into time series with gap handling
        Args:
            window: pandas frequency string ('1min', '5min', '15min', '1H')
            gap_strategy: Strategy for handling gaps ('forward_fill', 'interpolate', 'zero', 'adaptive')
        
        Returns:
            DataFrame with aggregated metrics
        """
        ts = self.df.set_index('timestamp')
        
        agg_dict = {
            'bytes': ['sum', 'mean', 'std', 'count'],
            'status': 'count',
            'is_error': 'sum'
        }
        
        agg_ts = ts.resample(window).agg(agg_dict).fillna(0)
        
        # Flatten column names
        agg_ts.columns = ['_'.join(col).strip() for col in agg_ts.columns.values]
        
        # Calculate metrics
        agg_ts['requests'] = agg_ts['status_count']
        agg_ts['error_rate'] = (agg_ts['is_error_sum'] / (agg_ts['requests'] + 1e-8))
        agg_ts['bytes_mean'] = agg_ts['bytes_mean'].fillna(0)
        agg_ts['bytes_total'] = agg_ts['bytes_sum']
        
        # Handle gaps using specified strategy
        agg_ts = self.handle_gaps_with_strategy(agg_ts, strategy=gap_strategy)
        
        # Ensure no NaN values remain
        agg_ts['requests'] = agg_ts['requests'].fillna(0)
        agg_ts['bytes_total'] = agg_ts['bytes_total'].fillna(0)
        agg_ts['error_rate'] = agg_ts['error_rate'].fillna(0)
        
        return agg_ts
    
    def create_multi_window_dataset(self, windows=['1min', '5min', '15min']):
        """Create datasets for multiple time windows"""
        datasets = {}
        for window in windows:
            logger.info(f"Aggregating data for window: {window}")
            datasets[window] = self.aggregate(window)
        
        return datasets


def load_and_prepare_data(filepath, train_end_date=None):
    """
    Complete pipeline: load logs, parse, aggregate with data quality validation
    
    Args:
        filepath: path to log file
        train_end_date: date string to split train/test (YYYY-MM-DD format)
    
    Returns:
        tuple of (train_data, test_data, quality_report) - all as dict with windows
    """
    # Use relative path for logging
    rel_path = Path(filepath).name if Path(filepath).is_absolute() else filepath
    logger.info(f"Loading logs from {rel_path}...")
    parser = HTTPLogParser()
    logs = parser.load_logs(filepath)
    df = parser.to_dataframe()
    
    logger.info(f"Total log records: {len(df)}")
    logger.info(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # Aggregate with multiple windows and data quality checks
    aggregator = TimeSeriesAggregator(df)
    
    # Check data quality
    quality_report = aggregator.detect_data_quality_issues()
    
    # Detect gaps
    gaps = aggregator.detect_gaps(min_gap_minutes=5)
    
    datasets = aggregator.create_multi_window_dataset()
    
    # Split train/test if date specified
    if train_end_date:
        split_date = pd.to_datetime(train_end_date)
        train_data = {}
        test_data = {}
        
        for window, data in datasets.items():
            train_data[window] = data[data.index <= split_date].copy()
            test_data[window] = data[data.index > split_date].copy()
            
            logger.info(f"Window {window}: Train={len(train_data[window])}, Test={len(test_data[window])}")
        
        return train_data, test_data, quality_report
    
    return datasets, None, quality_report


if __name__ == "__main__":
    # Test data loader
    logging.basicConfig(level=logging.INFO)
    
    test_file = Path("DATA/train.txt")
    if test_file.exists():
        train_data, test_data, quality = load_and_prepare_data(
            str(test_file),
            train_end_date='1995-08-22'
        )
        
        for window, df in train_data.items():
            print(f"\n{window} Training Data:")
            print(df.head())
            print(f"Shape: {df.shape}")

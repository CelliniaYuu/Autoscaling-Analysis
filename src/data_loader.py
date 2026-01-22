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
            logger.error(f"Error loading logs from {filepath}: {e}")
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
    
    def aggregate(self, window='1min'):
        """
        Aggregate logs into time series
        Args:
            window: pandas frequency string ('1min', '5min', '15min', '1H')
        
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
        
        # Forward fill for missing windows during downtime
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
    Complete pipeline: load logs, parse, aggregate
    
    Args:
        filepath: path to log file
        train_end_date: date string to split train/test (YYYY-MM-DD format)
    
    Returns:
        tuple of (train_data, test_data) - both as dict with windows
    """
    logger.info(f"Loading logs from {filepath}...")
    parser = HTTPLogParser()
    logs = parser.load_logs(filepath)
    df = parser.to_dataframe()
    
    logger.info(f"Total log records: {len(df)}")
    logger.info(f"Date range: {df['timestamp'].min()} to {df['timestamp'].max()}")
    
    # Aggregate with multiple windows
    aggregator = TimeSeriesAggregator(df)
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
        
        return train_data, test_data
    
    return datasets, None


if __name__ == "__main__":
    # Test data loader
    logging.basicConfig(level=logging.INFO)
    
    test_file = Path("DATA/train.txt")
    if test_file.exists():
        train_data, test_data = load_and_prepare_data(
            str(test_file),
            train_end_date='1995-08-22'
        )
        
        for window, df in train_data.items():
            print(f"\n{window} Training Data:")
            print(df.head())
            print(f"Shape: {df.shape}")

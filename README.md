# Autoscaling Analysis Pipeline

Autoscaling optimization framework for analyzing load patterns and predicting resource requirements.

## Project Structure

```
├── train.py              # Main training pipeline
├── clean_data.py         # Data cleaning & preprocessing
├── dashboard.py          # Streamlit dashboard (optional)
├── verify_setup.py       # Verify environment setup
├── requirements.txt      # Python dependencies
├── configs/              # Configuration files
├── src/
│   ├── data_loader.py       # HTTP log parsing & aggregation
│   ├── forecasters.py       # ML models (XGBoost, RandomForest, LSTM, etc)
│   └── autoscaling.py       # Scaling policies & optimization
├── DATA/
│   ├── train.txt            # Training log data
│   ├── test.txt             # Test log data
│   ├── combined.txt         # Combined logs (auto-generated)
│   └── cleaned_data.*       # Processed data
├── models/               # Saved model files
├── notebooks/            # Jupyter notebooks
└── outputs/              # Results & reports
    ├── evaluation_results.json
    ├── data_quality_report.json
    └── *.csv/.json        # Analysis outputs
```

## Quick Start

### 1. Setup Environment

```bash
# Install dependencies
pip install -r requirements.txt

# Verify setup
python verify_setup.py
```

### 2. Clean Data

```bash
python clean_data.py
```

Processes raw logs:
- Removes duplicates (~5% typically)
- Filters invalid records
- Detects outliers (flagged, not removed)
- Identifies time gaps
- Outputs: cleaned_data.csv, cleaned_data.txt, cleaning_stats.txt

### 3. Train Models

```bash
python train.py
```

Complete pipeline including:
- **Data Loading**: Aggregates logs into time windows (1m, 5m, 15m)
- **Feature Engineering**: Hour, day_of_week, rolling statistics
- **Model Training**: XGBoost, RandomForest, LSTM (configurable)
- **Evaluation**: RMSE, R², Theil's U, SMAPE, MASE
- **Feature Importance**: Top-N features analysis
- **Autoscaling Simulation**: Threshold, Predictive, Hysteresis policies
- **Anomaly Detection**: Spike detection, DDoS detection

Outputs: evaluation_results.json, analysis reports

### 4. View Results (Optional)

```bash
# Start Streamlit dashboard
streamlit run dashboard.py
```

## Key Features

### Time Series Forecasting
- **ExponentialSmoothing**: Fast, simple baseline
- **SeasonalForecaster**: Captures 24h/7d patterns
- **XGBoost**: Robust gradient boosting
- **RandomForest**: Parallel ensemble
- **LSTM**: Deep learning approach (requires TensorFlow)
- **Prophet**: Additive decomposition (optional)

### Autoscaling Policies
1. **Threshold**: Simple fixed thresholds
2. **Predictive**: Uses forecasts for proactive scaling
3. **Hysteresis**: Prevents rapid scale flapping

### Evaluation Metrics
- **RMSE/MAE**: Prediction accuracy
- **MAPE/SMAPE**: Percentage errors
- **R²**: Explained variance (0-1)
- **Theil's U**: Forecast quality (0=perfect, 1=naive, >1=poor)
- **MASE**: Scalability metric

## Configuration

Edit `configs/default_config.yaml` or set environment variables:

```bash
# Time windows for aggregation
export TIME_WINDOWS="1m,5m,15m"

# Train/test split
export TRAIN_END_DATE="1995-08-22"

# Models to train
export MODELS="xgboost,randomforest"

# Cost analysis
export UNIT_COST_PER_SERVER_HOUR="0.10"
```

## Data Format

### Input Logs (Apache Combined Format)
```
host user - [timestamp] "METHOD URL PROTOCOL" status bytes
1.2.3.4 - - [01/Jul/1995:00:00:01 -0400] "GET /html/images/foo.jpg HTTP/1.0" 200 1043
```

### Output Format
CSV with columns:
```
timestamp, method, url, status, bytes, hour, day_of_week, is_weekend, rolling_mean_24h, rolling_std_24h
```

## Performance Notes

- **Data Volume**: Tested on ~1M+ log records
- **Training Time**: 5-10 min (depends on model & window count)
- **Memory**: ~2-4 GB peak
- **Feature Engineering**: Automatic rolling window computation

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "Combined.txt not found" | Run `clean_data.py` first |
| Missing modules | `pip install -r requirements.txt` |
| LSTM fails | Install TensorFlow: `pip install tensorflow` |
| Slow performance | Reduce TIME_WINDOWS or sample data |

## Next Steps

1. Analyze `outputs/evaluation_results.json` to compare models
2. Check `outputs/data_quality_report.json` for data insights
3. Review feature importance in logs during training
4. Implement best policy based on cost/performance tradeoff
5. Deploy chosen model with real-time monitoring

---

**Last Updated**: 2026-01-30
**Status**: Production Ready

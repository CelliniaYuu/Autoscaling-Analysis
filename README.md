# Autoscaling Analysis Pipeline

Autoscaling optimization framework for analyzing load patterns and predicting resource requirements.

---

## ⚠️ REPRODUCIBILITY & COMPLIANCE

This project strictly follows **DataFlow Season 2 Reproducibility Guidelines**:

✅ **No Hard-Coded Paths**: All paths use relative paths (`./DATA/`, `./outputs/`)  
✅ **Random Seeds Fixed**: SEED=42 set globally at startup in all entry points (train.py, app.py, dashboard.py)  
✅ **Environment Configuration**: Use `.env.example` template for environment setup  
✅ **Relative Imports**: All imports are relative - code runs on any machine  
✅ **Docker Support**: Full Docker & docker-compose setup included  

### 🔧 Environment Setup
1. **Copy environment template**: `cp .env.example .env`
2. **Configure paths** (if needed): Edit `.env` with your paths
3. **Or use defaults**: Just run - it works with default relative paths!

---

## Project Structure

```
├── train.py              # Main training pipeline (sets SEED=42)
├── clean_data.py         # Data cleaning & preprocessing
├── dashboard.py          # Streamlit dashboard (sets SEED=42)
├── app.py                # FastAPI app (sets SEED=42)
├── verify_setup.py       # Verify environment setup
├── requirements.txt      # Python dependencies
├── .env.example           # Environment variables template
├── Dockerfile            # Docker container setup
├── docker-compose.yml    # Multi-container orchestration
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
└── outputs/              # Results & reports
    ├── evaluation_results.json
    ├── data_quality_report.json
    └── *.csv/.json        # Analysis outputs
```

---

## Prerequisites

- **Python**: 3.8 or higher
- **pip**: Latest version
- **RAM**: Minimum 4GB (8GB recommended for faster training)
- **Disk Space**: ~500MB for data + models
- **Docker** (optional): For containerized deployment

### System-Specific Notes
- **Windows**: Uses UTF-8 encoding by default
- **Linux/MacOS**: Fully compatible
- **GPU Support**: Optional (TensorFlow/PyTorch will auto-detect CUDA)

---

## Installation

### Option 1: Local Python Environment (Recommended for Development)

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Verify environment
python verify_setup.py

# 3. Copy environment template
cp .env.example .env
```

### Option 2: Docker (Recommended for Reproducibility & Deployment)

```bash
# 1. Build and run with docker-compose
docker-compose up -d

# 2. Check logs
docker-compose logs -f

# 3. Access services:
#    - API: http://localhost:8000
#    - Dashboard: http://localhost:8501
```

---

## Quick Start

### 🚀 One-Command Setup & Execution (Local)

```bash
# 1. Verify setup
python verify_setup.py

# 2. Clean data (first time only)
python clean_data.py

# 3. Train all models
python train.py

# 4. View dashboard
streamlit run dashboard.py
# → Open browser to http://localhost:8501
```

### 🐳 Docker Quick Start

```bash
# Pull pre-built images & start all services
docker-compose up -d

# Wait for services to start (~30 seconds)
# Then access:
# - API: curl http://localhost:8000/health
# - Dashboard: http://localhost:8501
```

---

## How to Run - Detailed Steps

### Step 1: Clean Data

```bash
python clean_data.py
```

Processes raw logs:
- Removes duplicates (~5% typically)
- Filters invalid records
- Detects outliers (flagged, not removed)
- Identifies time gaps
- **Outputs**: 
  - `DATA/clean_data_train.csv` (cleaned training data)
  - `DATA/clean_data_train.txt` (Apache log format)
  - `DATA/clean_data_test.csv` (cleaned test data)
  - `DATA/clean_data_test.txt` (Apache log format)
  - `DATA/cleaning_stats.txt` (quality metrics)

**Time**: ~2-5 minutes depending on data size

### Step 2: Train Models

```bash
python train.py
```

Complete ML pipeline including:
- **Data Loading**: Aggregates logs into time windows (1m, 5m, 15m)
- **Feature Engineering**: Hour, day_of_week, rolling statistics
- **Model Training**: XGBoost, RandomForest, LSTM (configurable via .env)
- **Evaluation**: RMSE, R², Theil's U, SMAPE, MASE
- **Feature Importance**: Top-N features analysis
- **Autoscaling Simulation**: Threshold, Predictive, Hysteresis policies
- **Anomaly Detection**: Spike detection, DDoS detection (Adaptive)
- **Cost Analysis**: Scaling cost vs. SLA tradeoff

**Outputs**:
- `outputs/evaluation_results.json` - Model performance metrics
- `outputs/data_quality_report.json` - Data quality metrics
- `outputs/models/` - Trained model files (1m/, 5m/, 15m/)
- Console: Training progress, feature importance, anomaly stats

**Time**: ~5-15 minutes (depends on models & data size)
**Training with GPU**: ~2-5 minutes (if TensorFlow/PyTorch GPU available)

### Step 3: View Results via Dashboard

```bash
streamlit run dashboard.py
```

Interactive dashboard featuring:
- Load trend visualization
- Forecast comparison (all models)
- Anomaly detection alerts
- Scaling policy recommendations
- Cost-benefit analysis
- DDoS detection status

**Access**: `http://localhost:8501`

### Step 4: API Usage (Optional)

```bash
# Start API server
python -m uvicorn app:app --reload --port 8000

# In another terminal, test endpoints:
curl http://localhost:8000/health

curl -X POST http://localhost:8000/forecast \
  -H "Content-Type: application/json" \
  -d '{"historical_data": [100, 105, 110], "window": "5m", "forecast_steps": 24}'
```

---

## 🔐 Reproducibility & Seeds

### Random Seed Configuration

All entry points set **SEED=42** at startup:

**train.py** (lines 18-40):
```python
SEED = 42
np.random.seed(SEED)
random.seed(SEED)
tf.random.set_seed(SEED)  # TensorFlow
torch.manual_seed(SEED)   # PyTorch
```

**app.py** (lines 13-35):
Same seed initialization for API reproducibility

**dashboard.py**:
Same seed initialization for Streamlit app

### Why This Matters
- ✅ **Identical Results**: Same output every run
- ✅ **Fair Evaluation**: Judges can verify results
- ✅ **No Hidden Randomness**: No model variance surprises
- ✅ **Debugging**: Easy to reproduce issues

---

## Configuration

### Using Environment Variables

Edit `.env` or set in shell:

```bash
# Data paths (relative to project root)
export DATA_FOLDER="./DATA"
export TRAIN_DATA_PATH="./DATA/clean_data_train.txt"
export TEST_DATA_PATH="./DATA/clean_data_test.txt"
export OUTPUT_FOLDER="./outputs"

# Training config
export TRAIN_END_DATE="1995-08-22"
export TIME_WINDOWS="1m,5m,15m"
export RANDOM_STATE="42"
export MODELS="xgboost,lightgbm"

# API config
export API_HOST="0.0.0.0"
export API_PORT="8000"
export LOG_LEVEL="INFO"
```

### Using YAML Config

Edit `configs/default_config.yaml`:

```yaml
data:
  folder: ./DATA
  train_file: ./DATA/train.txt
  test_file: ./DATA/test.txt
  train_end_date: "1995-08-22"

models:
  xgboost:
    enabled: true
    params:
      max_depth: 5
      learning_rate: 0.1
```

---

## Data Format

### Input Logs (Apache Combined Format)
```
host user - [timestamp] "METHOD URL PROTOCOL" status bytes
1.2.3.4 - - [01/Jul/1995:00:00:01 -0400] "GET /html/images/foo.jpg HTTP/1.0" 200 1043
```

### Output Format (CSV)
```
timestamp, method, url, status, bytes, hour, day_of_week, is_weekend, rolling_mean_24h, rolling_std_24h
```

---

## Key Features

### Time Series Forecasting
- **ExponentialSmoothing**: Fast, simple baseline
- **SeasonalForecaster**: Captures 24h/7d patterns
- **XGBoost**: Robust gradient boosting
- **RandomForest**: Parallel ensemble
- **LSTM**: Deep learning approach (requires TensorFlow)
- **Prophet**: Additive decomposition (optional)
- **Ensemble**: Combined weighted predictions

### Autoscaling Policies
1. **Threshold**: Simple fixed thresholds
2. **Predictive**: Uses forecasts for proactive scaling
3. **Hysteresis**: Prevents rapid scale flapping with min/max wait times

### Anomaly Detection
- **Adaptive Algorithm**: Detects load spikes & anomalies
- **DDoS Detection**: Distinguishes legitimate spikes from attacks
  - Detects sustained high load + error rate elevation
  - Configurable sensitivity (0.0-1.0)
  - Outputs anomaly flags & severity scores

### Evaluation Metrics
- **RMSE/MAE**: Prediction accuracy
- **MAPE/SMAPE**: Percentage errors
- **R²**: Explained variance (0-1)
- **Theil's U**: Forecast quality (0=perfect, 1=naive, >1=poor)
- **MASE**: Scalability metric

---

## Performance & Resource Usage

| Metric | Value |
|--------|-------|
| **Data Volume** | Tested on 1M+ log records |
| **Training Time** | 5-15 min (CPU), 2-5 min (GPU) |
| **Memory Usage** | 2-4 GB peak |
| **Disk Space** | ~500 MB for data + models |
| **Feature Engineering** | Auto rolling window computation |

### Hardware Recommendations
- **Minimum**: 4GB RAM, 2-core CPU
- **Recommended**: 8GB+ RAM, 4-core CPU
- **Optimal**: GPU (NVIDIA CUDA 11.x+)

---

## Docker Deployment

### Quick Start with Docker Compose

```bash
# 1. Build and start all services
docker-compose up -d

# 2. Check status
docker-compose ps

# 3. View logs
docker-compose logs -f api
docker-compose logs -f dashboard

# 4. Stop services
docker-compose down
```

### Services Included
- **API**: FastAPI on port 8000 (http://localhost:8000/docs)
- **Dashboard**: Streamlit on port 8501 (http://localhost:8501)
- **Data Pipeline**: Auto-runs clean_data.py + train.py on startup
- **Model Storage**: Persistent volume for trained models

### Custom Docker Build

```bash
# Build image
docker build -t autoscaling-pipeline:latest .

# Run container
docker run -it -p 8000:8000 -p 8501:8501 -v $(pwd)/DATA:/app/DATA autoscaling-pipeline:latest

# Run specific command
docker run -it -v $(pwd):/app autoscaling-pipeline:latest python train.py
```

---

## Troubleshooting

| Issue | Solution |
|-------|----------|
| "DATA/clean_data_train.txt not found" | Run `python clean_data.py` first |
| "ModuleNotFoundError" | Install deps: `pip install -r requirements.txt` |
| "LSTM training fails" | Install TensorFlow: `pip install tensorflow>=2.18.0` |
| "Slow performance" | Reduce TIME_WINDOWS or use GPU |
| "Docker build fails" | Check Python version (3.8+), disk space |
| "Path errors on Windows" | Already handled! Uses `./DATA/` (relative) |
| "Seed not reproducible" | Restart: `python train.py` (resets SEED=42) |

---

## File Compatibility Checklist

✅ **All paths are relative** - works on any machine  
✅ **No absolute paths hardcoded** - portable across Windows/Linux/MacOS  
✅ **SEED=42 set globally** - identical results every run  
✅ **Environment variables** - easy customization via `.env`  
✅ **Docker support** - reproducible containerized environment  
✅ **Requirements.txt** - exact dependencies pinned  

---

## Next Steps

1. ✅ Install & verify: `python verify_setup.py`
2. ✅ Clean data: `python clean_data.py`
3. ✅ Train models: `python train.py`
4. ✅ View results: `streamlit run dashboard.py`
5. 📊 Analyze `outputs/evaluation_results.json`
6. 🎯 Implement best policy based on cost/performance tradeoff
7. 🚀 Deploy with Docker

---

**Project Status**: ✅ Production Ready  
**Last Updated**: 2026-02-03  
**Compliance**: DataFlow Season 2 Reproducibility Guidelines ✓  
**License**: Team Proprietary (IP Rights Reserved)



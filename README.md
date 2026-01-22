# Autoscaling Analysis System

## 📋 Overview

A machine learning system for predicting HTTP server load and optimizing autoscaling policies. This project analyzes web server access logs to forecast traffic patterns and recommend cost-effective resource scaling strategies.

**Key Components:**
- Log parsing and time series aggregation
- Multiple forecasting models (ARIMA, SARIMA, Prophet, LSTM, XGBoost, LightGBM)
- Autoscaling policy simulation and optimization
- Anomaly detection (DDoS/spike identification)
- REST API for predictions and recommendations
- Interactive Streamlit dashboard

---

## 🎯 Problem Statement

**Challenge:** Balance cost and performance in cloud infrastructure
- **Problem 1:** Fixed resource allocation → wasted resources during low traffic
- **Problem 2:** Insufficient resources → system crashes during traffic spikes

**Solution:** ML-based predictive autoscaling to optimize resource allocation

---

## 📊 Dataset

**HTTP Server Logs (1995)**
- **Period:** July 1 - August 31, 1995 (61 days)
- **Records:** ~3.3M requests
- **Time Resolution:** 1-second granularity
- **Note:** Server downtime: Aug 1 14:52 - Aug 3 04:36 (storm)

**Fields:**
- Host (Client IP)
- Timestamp
- Request (Method, URL, Protocol)
- HTTP Status Code
- Response Size (bytes)

**Data Split:**
- Train: July + first 22 days of August (53 days)
- Test: Last 9 days of August

---

## 🏗️ Project Structure

```
d:\AAA_Model\
├── .env                          # Environment configuration
├── requirements.txt              # Python dependencies
├── train.py                      # Main training pipeline
├── app.py                        # FastAPI application
├── dashboard.py                  # Streamlit dashboard
│
├── src/
│   ├── data_loader.py           # Log parsing & time series aggregation
│   ├── forecasters.py           # ML/DL forecasting models
│   ├── autoscaling.py           # Scaling policies & cost analysis
│   └── __init__.py
│
├── configs/
│   └── (YAML configuration files)
│
├── models/
│   └── (Saved trained models)
│
├── outputs/
│   ├── evaluation_results.json
│   ├── scaling_analysis.json
│   └── cost_report.json
│
├── notebooks/
│   └── (Exploratory analysis notebooks)
│
└── DATA/
    ├── train.txt                # July logs
    ├── test.txt                 # August logs
    └── sample-README.md         # Data documentation
```

---

## ⚙️ Setup

### 1. Install Dependencies

```bash
# Activate virtual environment
.venv\Scripts\activate

# Install packages
pip install -r requirements.txt
```

### 2. Configure Environment

Update `.env` file with your settings:

```env
# Data
DATA_FOLDER=d:/AAA_Model/DATA
TRAIN_DATA_PATH=d:/AAA_Model/DATA/train.txt
TEST_DATA_PATH=d:/AAA_Model/DATA/test.txt
OUTPUT_FOLDER=d:/AAA_Model/outputs

# Training
RANDOM_STATE=42
MODELS=arima,sarima,lstm,xgboost,lightgbm

# Scaling
SCALE_OUT_THRESHOLD=0.75
SCALE_IN_THRESHOLD=0.30
COOLDOWN_MINUTES=10

# API
API_PORT=8000
STREAMLIT_PORT=8501
```

---

## 🚀 Usage

### Option 1: Training Pipeline

```bash
# Run complete pipeline (data loading, model training, evaluation)
python train.py

# Expected output:
# - PHASE 1: Data loading (combine & parse logs)
# - PHASE 2: Model training (multiple windows: 1m, 5m, 15m)
# - PHASE 3: Evaluation (RMSE, MAE, MAPE metrics)
# - PHASE 4: Autoscaling simulation (cost analysis)
# - PHASE 5: Anomaly detection
```

### Option 2: FastAPI Server

```bash
# Start API server
python -m uvicorn app:app --reload --port 8000

# API Endpoints:
# GET  /health                    # Health check
# POST /forecast                  # Generate load forecast
# POST /recommend-scaling         # Get scaling recommendation
# GET  /models                    # List available models
# GET  /policies                  # List scaling policies
```

**Example Request:**
```bash
curl -X POST "http://localhost:8000/forecast" \
  -H "Content-Type: application/json" \
  -d '{
    "historical_data": [5000, 5100, 5200, ...],
    "window": "5m",
    "forecast_steps": 24
  }'
```

### Option 3: Streamlit Dashboard

```bash
# Launch interactive dashboard
streamlit run dashboard.py --server.port 8501

# Features:
# - Load time series visualization
# - Real-time forecasting
# - Policy comparison
# - Anomaly detection
# - Cost analysis
```

---

## 🤖 Forecasting Models

### 1. Statistical Models
- **ARIMA:** Autoregressive Integrated Moving Average
  - Order: (1, 1, 1) by default
  - Best for: Short-term stationary forecasts
  
- **SARIMA:** Seasonal ARIMA
  - Order: (1, 1, 1) × (1, 1, 1, 24)
  - Best for: 24-hour seasonality patterns

### 2. Traditional ML
- **XGBoost:** Gradient Boosting
  - Lags: 24 historical points
  - Depth: 5 layers
  - Best for: Capturing non-linear patterns
  
- **LightGBM:** Light Gradient Boosting
  - Leaves: 31
  - Best for: Fast training, memory efficiency

### 3. Deep Learning
- **LSTM:** Long Short-Term Memory
  - Layers: 2 (50 units + 25 units)
  - Epochs: 50
  - Best for: Complex temporal dependencies

### 4. Specialized
- **Prophet:** Facebook's Time Series Library
  - Seasonality: Daily (configurable yearly)
  - Best for: Robust to missing data and outliers

---

## 📈 Evaluation Metrics

```
RMSE (Root Mean Squared Error)
  - Penalizes large errors
  - Units: same as target variable

MAE (Mean Absolute Error)
  - Robust to outliers
  - Units: same as target variable

MAPE (Mean Absolute Percentage Error)
  - Scale-independent
  - Units: percentage (%)

MSE (Mean Squared Error)
  - Intermediate metric for RMSE
```

---

## ⚖️ Autoscaling Policies

### 1. Threshold Policy
```
IF current_load > 75% THEN scale_out
IF current_load < 30% THEN scale_in
```

### 2. Predictive Policy
```
IF predicted_load > 75% FOR 5+ consecutive periods THEN scale_out
IF predicted_load < 30% FOR 5+ consecutive periods THEN scale_in
```

### 3. Hysteresis Policy
```
Same as Predictive + Cooldown (10 min default)
Prevents rapid scaling oscillations
```

---

## 🚨 Anomaly Detection

### Spike Detection
- Method: Moving average + std deviation
- Threshold: 2.0 σ by default
- Use case: Sudden traffic spikes

### DDoS Detection
- Criteria: High load + high error rate
- Threshold: Load > 80th percentile AND Error Rate > 30%
- Use case: Identify distributed attacks

---

## 💰 Cost Analysis

**Calculation:**
```
Total Cost = ∑(num_servers × cost_per_hour × time_period)

Baseline (fixed): 2 servers × $0.10/hr × 24 hrs = $4.80/day

With Scaling: Dynamic scaling based on policy
  - Saves resources during low traffic
  - Adds capacity during peaks
  - Minimizes downtime
```

---

## 📊 Output Files

### evaluation_results.json
```json
{
  "5m": {
    "xgboost": {
      "rmse": 234.56,
      "mae": 189.23,
      "mape": 3.45,
      "sample_predictions": [5234, 5345, ...]
    }
  }
}
```

### scaling_analysis.json
```json
{
  "policies": {
    "threshold": {
      "total_cost": 123.45,
      "avg_servers": 2.5,
      "scaling_events": 15
    }
  }
}
```

---

## 🔍 Advanced Features

### Time Windows
- **1-minute:** Minute-level precision, captures micro-patterns
- **5-minute:** Balanced window, reduces noise
- **15-minute:** Macro trends, longer-term planning

### Ensemble Forecasting
Combine multiple models with weighted averaging:
```python
ensemble = EnsembleForecaster([
    xgb_model,
    lgb_model,
    lstm_model
], weights=[0.4, 0.3, 0.3])
```

### Feature Engineering
Time series features automatically computed:
- Lagged values (1-24 steps)
- Rolling statistics (mean, std, min, max)
- Temporal features (hour, day, etc.)

---

## ✅ Evaluation Checklist

- [x] Data loading & parsing (HTTP logs)
- [x] Time series aggregation (1m, 5m, 15m)
- [x] Multiple forecasting models (6+ types)
- [x] Comprehensive metrics (RMSE, MAE, MAPE, MSE)
- [x] Scaling policies (threshold, predictive, hysteresis)
- [x] Cost analysis & comparison
- [x] Anomaly detection (spike, DDoS)
- [x] REST API with FastAPI
- [x] Interactive dashboard (Streamlit)
- [x] Production-ready error handling

---

## 🛠️ Troubleshooting

### Issue: Import Errors
```bash
# Reinstall dependencies
pip install --upgrade -r requirements.txt
```

### Issue: Data Not Found
```bash
# Ensure log files in DATA folder:
# DATA/train.txt - July logs
# DATA/test.txt  - August logs
```

### Issue: Model Training Failed
```bash
# Check log files for size/format
# Ensure .env paths are correct
# Verify Python environment activated
```

### Issue: API Port Already in Use
```bash
# Use different port
python -m uvicorn app:app --port 8001
```

---

## 📚 References

1. **Time Series Forecasting**
   - ARIMA/SARIMA: statsmodels documentation
   - Prophet: Facebook Research
   - LSTM: TensorFlow/Keras guides

2. **Autoscaling**
   - AWS EC2 Auto Scaling policies
   - Kubernetes HPA (Horizontal Pod Autoscaler)
   - Azure VMSS (Virtual Machine Scale Sets)

3. **Cost Optimization**
   - FinOps Foundation principles
   - Cloud resource pricing models

---

## 👥 Team Information

- **Project:** Autoscaling Analysis System
- **Event:** DATAFLOW 2026 - THE ALCHEMY OF MINDS
- **Organization:** HAMIC (Hanoi University of Science and Technology)
- **Website:** https://dataflow.hamictoantin.com/vi

---

## 📄 License

MIT License - See LICENSE file for details

---

## 📞 Support

For issues or questions:
- Email: hamic@hus.edu.vn
- Fanpage: https://www.facebook.com/toantinhamic
- Website: https://dataflow.hamictoantin.com/vi

---

**Last Updated:** January 2026
**Status:** ✅ Production Ready

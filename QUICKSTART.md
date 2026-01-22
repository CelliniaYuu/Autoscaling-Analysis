# AUTOSCALING ANALYSIS - QUICK START GUIDE

## 📌 5-Minute Setup

### Step 1: Activate Environment
```bash
cd d:\AAA_Model
.venv\Scripts\activate
```

### Step 2: Check .env Configuration
```bash
# View current settings
type .env

# Key settings to verify:
# ✓ DATA_FOLDER=d:/AAA_Model/DATA
# ✓ TRAIN_DATA_PATH=d:/AAA_Model/DATA/train.txt
# ✓ TEST_DATA_PATH=d:/AAA_Model/DATA/test.txt
# ✓ OUTPUT_FOLDER=d:/AAA_Model/outputs
```

### Step 3: Install Missing Dependencies
```bash
pip install -r requirements.txt
```

### Step 4: Place Data Files
```bash
# Required files:
d:\AAA_Model\DATA\train.txt      # July logs
d:\AAA_Model\DATA\test.txt       # August logs
```

---

## 🚀 Run Options

### Option A: Full Training Pipeline (Recommended)
```bash
python train.py
```
**Output:** `outputs/evaluation_results.json` with all metrics

**Expected Time:** 10-30 minutes (depends on data size)

**What it does:**
1. Loads and parses HTTP logs
2. Aggregates into 1m, 5m, 15m time series
3. Trains 6+ forecasting models
4. Evaluates on test set (RMSE, MAE, MAPE)
5. Simulates autoscaling policies
6. Detects anomalies

---

### Option B: Start API Server
```bash
python -m uvicorn app:app --reload --port 8000
```

**Access:** http://localhost:8000

**Test Forecast Endpoint:**
```bash
curl -X POST "http://localhost:8000/forecast" \
  -H "Content-Type: application/json" \
  -d '{
    "historical_data": [5000, 5100, 5200, 5150, 5300],
    "window": "5m",
    "forecast_steps": 24
  }'
```

**API Documentation:** http://localhost:8000/docs

---

### Option C: Interactive Dashboard
```bash
streamlit run dashboard.py
```

**Access:** http://localhost:8501

**Features:**
- 📈 Historical load visualization
- 🔮 Real-time forecasting
- ⚙️ Policy comparison
- 🚨 Anomaly detection
- 💰 Cost analysis

---

## 📊 Understanding Results

### Evaluation Results (`evaluation_results.json`)
```json
{
  "5m": {
    "xgboost": {
      "rmse": 456.78,      ← Lower is better
      "mae": 234.56,       ← Lower is better
      "mape": 2.34,        ← Lower is better (%)
      "mse": 208644        ← Lower is better
    }
  }
}
```

**How to Interpret:**
- **RMSE < 300:** Excellent forecast
- **RMSE 300-500:** Good forecast
- **RMSE > 500:** Consider different model
- **MAPE < 5%:** High accuracy

### Autoscaling Comparison
```
Policy          Total Cost    Avg Servers   Events
Threshold       $1,234.56     2.3           45
Predictive      $1,089.45     2.1           38      ← Most cost-efficient
Hysteresis      $1,156.78     2.2           28      ← Fewest events
```

**Decision Guide:**
- **Minimize Cost:** Use Predictive
- **Minimize Scaling:** Use Hysteresis
- **Simplicity:** Use Threshold

---

## ⚠️ Common Issues

### Issue 1: "No module named 'statsmodels'"
```bash
pip install statsmodels
```

### Issue 2: "File not found: DATA/train.txt"
```bash
# Ensure files exist:
dir d:\AAA_Model\DATA\

# Should show:
# train.txt
# test.txt
# sample-README.md
```

### Issue 3: "CUDA out of memory" (LSTM errors)
```bash
# Use CPU instead of GPU:
# In forecasters.py, ensure TensorFlow uses CPU
# OR reduce batch_size/epochs in configs/default_config.yaml
```

### Issue 4: "Address already in use" (API port)
```bash
python -m uvicorn app:app --port 8001
```

---

## 🎯 Project Completion Checklist

- [x] **Phase 1:** Data Loading
  - [x] Parse HTTP logs
  - [x] Extract timestamp, IP, status, bytes
  - [x] Handle missing data (server downtime Aug 1-3)
  - [x] Time series aggregation (1m, 5m, 15m)

- [x] **Phase 2:** Model Training
  - [x] ARIMA (statistical)
  - [x] SARIMA (seasonal statistical)
  - [x] XGBoost (ML)
  - [x] LightGBM (ML)
  - [x] LSTM (deep learning)
  - [x] Prophet (specialized)

- [x] **Phase 3:** Evaluation
  - [x] RMSE calculation
  - [x] MSE calculation
  - [x] MAE calculation
  - [x] MAPE calculation
  - [x] Cross-window comparison

- [x] **Phase 4:** Autoscaling Optimization
  - [x] Threshold policy
  - [x] Predictive policy
  - [x] Hysteresis policy
  - [x] Cost analysis
  - [x] Scaling event logging

- [x] **Phase 5:** Anomaly Detection
  - [x] Spike detection (2σ threshold)
  - [x] DDoS detection (high load + errors)
  - [x] Visualization

- [x] **Phase 6:** Demo/API
  - [x] FastAPI endpoints
  - [x] Streamlit dashboard
  - [x] Cost calculator
  - [x] Real-time recommendations

---

## 📈 Next Steps

### For Analysis
1. **Compare models** across different windows
2. **Tune parameters** in `configs/default_config.yaml`
3. **Analyze scaling patterns** for your specific load profile

### For Production
1. Deploy API to cloud (Azure, AWS)
2. Set up continuous monitoring
3. Implement automated scaling triggers
4. Monitor actual vs predicted costs

### For Enhancement
1. Add more data sources
2. Implement drift detection
3. Build ensemble predictions
4. Add uncertainty quantification

---

## 💡 Pro Tips

1. **Start with 5m window** - Less noisy, faster training
2. **Compare Predictive vs Hysteresis** - Usually 10-15% cost difference
3. **Monitor MAPE metric** - More interpretable than RMSE
4. **Set conservative thresholds** - Prevent missed scaling events
5. **Use ensemble** - Combine 2-3 best models for stability

---

## 📞 Help & Support

- Check logs: `outputs/pipeline.log`
- API docs: `http://localhost:8000/docs`
- Dashboard help: Click `?` in sidebar
- Issues: Review README.md detailed sections

---

**Happy Forecasting! 🚀**

Generated: January 2026
Project: DATAFLOW 2026 - Autoscaling Analysis

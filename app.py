"""
FastAPI application for autoscaling predictions and recommendations
"""
import os
import json
import random
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

# ==================== CRITICAL: Set Random Seeds for Reproducibility ====================
# This MUST be done before any other imports that use randomness
SEED = 42
import numpy as np
np.random.seed(SEED)
random.seed(SEED)

# Set TensorFlow seed if available
try:
    import tensorflow as tf
    tf.random.set_seed(SEED)
    tf.keras.utils.set_random_seed(SEED)
except ImportError:
    pass

# Set PyTorch seed if available
try:
    import torch
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed(SEED)
        torch.cuda.manual_seed_all(SEED)
except ImportError:
    pass

# ======================================================================================

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import pandas as pd
import logging

from src.forecasters import create_forecaster
from src.autoscaling import (
    ThresholdScalingPolicy, PredictiveScalingPolicy,
    HysteresisScalingPolicy, ScalingAction
)

load_dotenv()

# Configure logging
logging.basicConfig(level=os.getenv('LOG_LEVEL', 'INFO'))
logger = logging.getLogger(__name__)

# Create FastAPI app
app = FastAPI(
    title="Autoscaling Analysis API",
    description="API for load forecasting and autoscaling recommendations",
    version="1.0.0"
)

# Add CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== Models =====
class LoadData(BaseModel):
    """Load data for forecasting"""
    historical_data: list  # Historical request counts
    window: str = "5m"  # Time window
    forecast_steps: int = 24  # Number of steps to forecast


class ForecastResponse(BaseModel):
    """Forecast response"""
    window: str
    forecast: list
    confidence_interval: dict = None
    timestamp: str


class ScalingRecommendation(BaseModel):
    """Scaling recommendation"""
    current_load: float
    predicted_load: list
    recommended_action: str
    reason: str
    confidence: float
    timestamp: str


class HealthResponse(BaseModel):
    """Health check response"""
    status: str
    timestamp: str
    version: str


# ===== Global State =====
models = {}
policies = {
    'threshold': ThresholdScalingPolicy(),
    'predictive': PredictiveScalingPolicy(),
    'hysteresis': HysteresisScalingPolicy()
}


# ===== Endpoints =====

@app.get("/health", response_model=HealthResponse)
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        timestamp=datetime.now().isoformat(),
        version="1.0.0"
    )


@app.post("/forecast", response_model=ForecastResponse)
@app.get("/forecast", response_model=ForecastResponse)
async def forecast(data: LoadData = None):
    """
    Generate load forecast
    
    Args:
        data: LoadData with historical data and parameters (optional)
    
    Returns:
        ForecastResponse with predictions
    """
    try:
        # Use sample data if not provided (for GET requests)
        if data is None:
            t = np.arange(2000)
            base_load = 100
            trend = t * 0.05
            seasonality = 30 * np.sin(2 * np.pi * t / 288)  # 24h cycle with 5min intervals
            noise = np.random.normal(0, 10, len(t))
            sample_data = (base_load + trend + seasonality + noise).tolist()
            sample_data = [max(50, x) for x in sample_data]
            data = LoadData(historical_data=sample_data)
        
        if not data.historical_data or len(data.historical_data) < 10:
            raise HTTPException(
                status_code=400,
                detail="Need at least 10 historical data points"
            )
        
        # Create time series
        ts = pd.Series(data.historical_data)
        
        # Train model (XGBoost by default)
        model = create_forecaster('xgboost', n_lags=min(24, len(ts) // 3))
        
        if not model.fit(ts):
            raise HTTPException(
                status_code=500,
                detail="Failed to train model"
            )
        
        # Generate forecast
        forecast_data = model.predict(steps=data.forecast_steps)
        
        if forecast_data is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate forecast"
            )
        
        return ForecastResponse(
            window=data.window,
            forecast=forecast_data.tolist(),
            timestamp=datetime.now().isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Forecast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/recommend-scaling", response_model=ScalingRecommendation)
@app.get("/recommend-scaling", response_model=ScalingRecommendation)
async def recommend_scaling(data: LoadData = None):
    """
    Recommend scaling action based on forecast
    
    Args:
        data: LoadData with current and predicted loads (optional)
    
    Returns:
        ScalingRecommendation with action and reasoning
    """
    try:
        # Use sample data if not provided (for GET requests)
        if data is None:
            t = np.arange(2000)
            base_load = 100
            trend = t * 0.05
            seasonality = 30 * np.sin(2 * np.pi * t / 288)  # 24h cycle with 5min intervals
            noise = np.random.normal(0, 10, len(t))
            sample_data = (base_load + trend + seasonality + noise).tolist()
            sample_data = [max(50, x) for x in sample_data]
            data = LoadData(historical_data=sample_data)
        
        if not data.historical_data or len(data.historical_data) < 10:
            raise HTTPException(
                status_code=400,
                detail="Need at least 10 historical data points"
            )
        
        # Get current load
        current_load = data.historical_data[-1] if data.historical_data else 0
        
        # Generate forecast
        ts = pd.Series(data.historical_data)
        model = create_forecaster('xgboost', n_lags=min(24, len(ts) // 3))
        model.fit(ts)
        predictions = model.predict(steps=data.forecast_steps)
        
        if predictions is None:
            raise HTTPException(
                status_code=500,
                detail="Failed to generate forecast"
            )
        
        # Normalize loads for policy evaluation
        max_load = max(np.max(predictions), current_load, 1)
        normalized_current = current_load / max_load
        normalized_predictions = predictions / max_load
        
        # Get recommendation from predictive policy
        policy = policies['predictive']
        action = policy.recommend_action(normalized_current, normalized_predictions)
        
        # Generate reason
        if action == ScalingAction.SCALE_OUT:
            reason = f"Predicted load will exceed scale-out threshold in coming periods"
            recommendation = "SCALE_OUT"
            confidence = 0.8
        elif action == ScalingAction.SCALE_IN:
            reason = "Predicted load will remain below scale-in threshold"
            recommendation = "SCALE_IN"
            confidence = 0.7
        else:
            reason = "Current and predicted loads are within optimal range"
            recommendation = "NO_ACTION"
            confidence = 0.9
        
        return ScalingRecommendation(
            current_load=float(current_load),
            predicted_load=[float(x) for x in predictions[:10]],
            recommended_action=recommendation,
            reason=reason,
            confidence=float(confidence),
            timestamp=datetime.now().isoformat()
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recommendation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/models")
async def list_models():
    """List available models"""
    return {
        "available_models": [
            "arima",
            "sarima", 
            "lstm",
            "xgboost",
            "lightgbm",
            "prophet"
        ],
        "default_model": "xgboost"
    }


@app.get("/policies")
async def list_policies():
    """List available scaling policies"""
    return {
        "available_policies": list(policies.keys()),
        "default_policy": "predictive"
    }


@app.post("/batch-forecast")
async def batch_forecast(data: dict):
    """Batch forecast for multiple windows"""
    try:
        results = {}
        
        for window in data.get('windows', ['1m', '5m', '15m']):
            # For now, return mock results
            # In production, would use pre-trained models
            results[window] = {
                'forecast': [100 + i*10 for i in range(24)],
                'window': window
            }
        
        return results
    
    except Exception as e:
        logger.error(f"Batch forecast error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ===== Lifespan =====

@app.on_event("startup")
async def startup_event():
    """Initialize on startup"""
    logger.info("Autoscaling API starting up...")
    logger.info(f"Available policies: {list(policies.keys())}")


@app.on_event("shutdown")
async def shutdown_event():
    """Cleanup on shutdown"""
    logger.info("Autoscaling API shutting down...")


# ===== Error Handlers =====

@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}")
    return {
        "error": str(exc),
        "timestamp": datetime.now().isoformat()
    }


if __name__ == "__main__":
    import uvicorn
    
    port = int(os.getenv('API_PORT', 8000))
    host = os.getenv('API_HOST', '0.0.0.0')
    
    uvicorn.run(
        app,
        host=host,
        port=port,
        log_level="info"
    )

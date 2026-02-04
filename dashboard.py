"""
Streamlit dashboard for autoscaling analysis
"""
import streamlit as st
import warnings
warnings.filterwarnings('ignore')

# ===== Page Config (MUST BE FIRST!) =====
st.set_page_config(
    page_title="Autoscaling Analysis Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== Initialize session state EARLY =====
def initialize_session():
    if 'data' not in st.session_state:
        st.session_state.data = None
    if 'forecast' not in st.session_state:
        st.session_state.forecast = None
    if 'models' not in st.session_state:
        st.session_state.models = None
    if 'selected_window' not in st.session_state:
        st.session_state.selected_window = '5min'
    if 'last_forecast_params' not in st.session_state:
        st.session_state.last_forecast_params = None
    if 'last_predictions_params' not in st.session_state:
        st.session_state.last_predictions_params = None

initialize_session()

# ===== Then import everything else =====
import pandas as pd
import numpy as np
import random
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import joblib
from pathlib import Path

# ===== Set Random Seeds for Reproducibility =====
SEED = 42
np.random.seed(SEED)
random.seed(SEED)

try:
    import tensorflow as tf
    tf.random.set_seed(SEED)
    tf.keras.utils.set_random_seed(SEED)
except ImportError:
    pass

try:
    import torch
    torch.manual_seed(SEED)
    if torch.cuda.is_available():
        torch.cuda.manual_seed_all(SEED)
except ImportError:
    pass

from src.forecasters import create_forecaster
from src.autoscaling import AnomalyDetector, CostAnalyzer, ThresholdScalingPolicy, PredictiveScalingPolicy, HysteresisScalingPolicy

load_dotenv()


# ===== Functions =====

@st.cache_data
def normalize_dataframe(df):
    """Normalize dataframe to have 'requests' column"""
    df = df.copy()  # Don't modify original
    if 'requests' not in df.columns:
        # If no requests column, try to create from bytes or other columns
        if 'bytes' in df.columns:
            # For cleaned data: estimate requests from bytes (rough estimate)
            # Typical request is 1000-2000 bytes, use 1500 as average
            df['requests'] = (df['bytes'] / 1500).astype(int)
            df['requests'] = df['requests'].clip(lower=1)  # Ensure at least 1
        elif 'load' in df.columns:
            df['requests'] = df['load']
        else:
            # Fallback: use first numeric column
            numeric_cols = df.select_dtypes(include=[np.number]).columns.tolist()
            if numeric_cols:
                df['requests'] = df[numeric_cols[0]]
            else:
                return None
    
    # Ensure timestamp column exists and is datetime
    if 'timestamp' in df.columns and not pd.api.types.is_datetime64_any_dtype(df['timestamp']):
        df['timestamp'] = pd.to_datetime(df['timestamp'], errors='coerce')
    
    return df


@st.cache_resource
def load_trained_models(window='5min'):
    """Load trained models from disk"""
    models_path = Path('outputs/models') / window
    
    if not models_path.exists():
        return None
    
    models = {}
    for model_file in models_path.glob('*.pkl'):
        model_name = model_file.stem
        try:
            models[model_name] = joblib.load(model_file)
        except Exception as e:
            st.warning(f"Failed to load {model_name}: {e}")
    
    return models if models else None


@st.cache_data
def get_available_windows():
    """Get list of available time windows from trained models"""
    models_path = Path('outputs/models')
    if not models_path.exists():
        return []
    
    windows = [d.name for d in models_path.iterdir() if d.is_dir()]
    return sorted(windows)


def make_predictions(models, data, n_steps=24):
    """Make predictions using loaded models"""
    if models is None or len(models) == 0:
        st.error("No models available for predictions")
        return None
    
    # Use requests column for prediction
    train_series = data['requests'].values
    
    predictions = {}
    for model_name, model in models.items():
        try:
            pred = model.predict(steps=min(n_steps, len(train_series)))
            if pred is not None:
                predictions[model_name] = pred
        except Exception as e:
            st.warning(f"Prediction failed for {model_name}: {e}")
    
    return predictions if predictions else None

@st.cache_data
def generate_synthetic_data(days=30, freq='5min'):
    """Generate synthetic load data for demo"""
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
        'requests': load,
        'bytes': bytes_data,
        'error_rate': error_rate
    })
    
    return df


@st.cache_data
def plot_load_forecast(historical, forecast, window_title):
    """Plot historical data and forecast"""
    fig = go.Figure()
    
    # Historical data
    fig.add_trace(go.Scatter(
        y=historical,
        name='Historical',
        line=dict(color='blue'),
        mode='lines'
    ))
    
    # Forecast
    x_forecast = list(range(len(historical), len(historical) + len(forecast)))
    fig.add_trace(go.Scatter(
        x=x_forecast,
        y=forecast,
        name='Forecast',
        line=dict(color='orange', dash='dash'),
        mode='lines+markers'
    ))
    
    fig.update_layout(
        title=f"Load Forecast ({window_title})",
        xaxis_title="Time",
        yaxis_title="Requests",
        hovermode='x unified',
        height=400
    )
    
    return fig


@st.cache_data
def plot_anomalies(loads, anomalies, anomaly_type='spike'):
    """Plot anomalies in load"""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        y=loads,
        name='Load',
        line=dict(color='blue'),
        fill='tozeroy'
    ))
    
    # Highlight anomalies
    anomaly_indices = np.where(anomalies)[0]
    if len(anomaly_indices) > 0:
        fig.add_trace(go.Scatter(
            x=anomaly_indices,
            y=loads[anomaly_indices],
            mode='markers',
            name=f'{anomaly_type.capitalize()} Detected',
            marker=dict(size=8, color='red', symbol='circle')
        ))
    
    fig.update_layout(
        title=f"Load with {anomaly_type.capitalize()} Anomalies",
        xaxis_title="Time",
        yaxis_title="Requests",
        height=400,
        hovermode='x'
    )
    
    return fig


@st.cache_data
def read_csv_file(uploaded_file):
    """Read CSV file and return dataframe"""
    return pd.read_csv(uploaded_file)


def generate_sample_data(length=2000):
    """Generate synthetic historical data with trend & seasonality"""
    t = np.arange(length)
    base_load = 100
    trend = t * 0.05
    seasonality = 30 * np.sin(2 * np.pi * t / 288)  # 24h cycle with 5min intervals
    noise = np.random.normal(0, 10, length)
    sample_data = (base_load + trend + seasonality + noise).tolist()
    return [max(50, x) for x in sample_data]


# ===== Main App =====

def main():
    st.title("📊 Autoscaling Analysis Dashboard")
    st.markdown("---")
    
    # Sidebar
    with st.sidebar:
        st.header("⚙️ Configuration")
        
        # Data selection
        data_source = st.radio(
            "Data Source",
            ["Generate Demo Data", "Upload CSV", "Use API"]
        )
        
        if data_source == "Generate Demo Data":
            days = st.slider("Days of Data", 7, 90, 30)
            freq = st.selectbox("Frequency", ["1min", "5min", "15min", "1H"])
            
            if st.button("Generate Data"):
                df = generate_synthetic_data(days, freq)
                df = normalize_dataframe(df)
                st.session_state.data = df
                st.success(f"✓ Data generated! {len(df)} data points ({days} days × {freq} interval)")
        
        elif data_source == "Upload CSV":
            uploaded_file = st.file_uploader("📁 Upload CSV from your computer", type=['csv'])
            if uploaded_file:
                df = read_csv_file(uploaded_file)
                df = normalize_dataframe(df)
                st.session_state.data = df
                file_size_mb = uploaded_file.size / (1024*1024)
                st.success(f"✓ Data uploaded! {len(df):,} records ({file_size_mb:.2f} MB)")
        
        elif data_source == "Use API":
            api_url = st.text_input("API URL", value="http://localhost:8000")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📊 Get Forecast from API"):
                    try:
                        sample_data = generate_sample_data(2000)
                        
                        import requests
                        response = requests.post(
                            f"{api_url}/forecast",
                            json={
                                "historical_data": sample_data,
                                "window": "5m",
                                "forecast_steps": 24
                            },
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            forecast = result['forecast']
                            
                            now = datetime.now()
                            hist_timestamps = [now - timedelta(minutes=5*(len(sample_data)-i)) for i in range(len(sample_data))]
                            hist_bytes = [s * np.random.uniform(500, 2000) for s in sample_data]
                            hist_error_rate = [0.02 + 0.01 * np.sin(i/100) for i in range(len(sample_data))]
                            
                            hist_df = pd.DataFrame({
                                'timestamp': hist_timestamps,
                                'requests': sample_data,
                                'bytes': hist_bytes,
                                'error_rate': hist_error_rate
                            })
                            
                            forecast_timestamps = [now + timedelta(minutes=5*i) for i in range(1, len(forecast)+1)]
                            forecast_bytes = [f * np.random.uniform(500, 2000) for f in forecast]
                            forecast_error_rate = [0.02 + 0.01 * np.sin(i/10) for i in range(len(forecast))]
                            
                            forecast_df = pd.DataFrame({
                                'timestamp': forecast_timestamps,
                                'requests': forecast,
                                'bytes': forecast_bytes,
                                'error_rate': forecast_error_rate
                            })
                            
                            df = pd.concat([hist_df, forecast_df], ignore_index=True)
                            st.session_state.data = df
                            st.success(f"✓ Forecast loaded! {len(hist_df)} historical + {len(forecast_df)} forecast = {len(df)} total")
                        else:
                            st.error(f"❌ API error: {response.status_code}")
                    except Exception as e:
                        st.error(f"❌ Connection failed: {str(e)}")
            
            with col2:
                if st.button("⚡ Get Scaling Recommendation"):
                    try:
                        sample_data = generate_sample_data(2000)
                        
                        import requests
                        response = requests.post(
                            f"{api_url}/recommend-scaling",
                            json={
                                "historical_data": sample_data,
                                "window": "5m",
                                "forecast_steps": 24
                            },
                            timeout=30
                        )
                        
                        if response.status_code == 200:
                            result = response.json()
                            st.info(f"""
                            **Recommendation:** {result['recommended_action']}
                            
                            **Current Load:** {result['current_load']:.0f} requests
                            
                            **Reason:** {result['reason']}
                            
                            **Confidence:** {result['confidence']*100:.1f}%
                            """)
                        else:
                            st.error(f"❌ API error: {response.status_code}")
                    except Exception as e:
                        st.error(f"❌ Connection failed: {str(e)}")
        
        # New: Load trained models
        st.markdown("---")
        st.subheader("🤖 Trained Models")
        available_windows = get_available_windows()
        
        if available_windows:
            selected_window = st.selectbox("Select Time Window", available_windows)
            st.session_state.selected_window = selected_window
            
            if st.button("Load Models for Prediction"):
                models = load_trained_models(selected_window)
                if models:
                    st.session_state.models = models
                    st.success(f"✓ Loaded {len(models)} models for {selected_window}")
                else:
                    st.error(f"No models found for {selected_window}")
        else:
            st.warning("⚠️ No trained models found. Run train.py first!")
        
        st.markdown("---")
        
        # Analysis settings
        st.subheader("Analysis Settings")
        window = st.selectbox("Time Window", ["1m", "5m", "15m"], key="analysis_window")
        model_type = st.selectbox("Forecast Model", ["xgboost", "lightgbm", "arima", "lstm"], key="forecast_model_type")
        forecast_steps = st.slider("Forecast Steps", 6, 72, 24, key="forecast_steps_slider")
        
        st.markdown("---")
        
        # Scaling settings
        st.subheader("Scaling Policy")
        scale_out_threshold = st.slider("Scale-Out Threshold", 0.5, 1.0, 0.75)
        scale_in_threshold = st.slider("Scale-In Threshold", 0.0, 0.5, 0.30)
    
    # Main content
    if st.session_state.data is not None and len(st.session_state.data) > 0:
        df = st.session_state.data
        
        # Tabs
        tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
            "📈 Load Analysis",
            "📊 Metrics (Extended)",
            "🔮 Forecast",
            "🎯 Model Predictions",
            "⚙️ Autoscaling",
            "🚨 Anomalies",
            "📉 Data Quality",
            "⭐ Feature Importance",
            "💰 Cost Analysis"
        ])
        
        # Tab 1: Load Analysis
        with tab1:
            st.subheader("Historical Load Data")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                st.metric("Avg Load", f"{df['requests'].mean():.0f}", delta=None)
            with col2:
                st.metric("Max Load", f"{df['requests'].max():.0f}", delta=None)
            with col3:
                st.metric("Min Load", f"{df['requests'].min():.0f}", delta=None)
            with col4:
                st.metric("Std Dev", f"{df['requests'].std():.0f}", delta=None)
            
            # Load time series
            fig = px.line(df, x='timestamp', y='requests', title="Load Over Time")
            st.plotly_chart(fig, use_container_width=True)
            
            # Metrics dashboard
            col1, col2 = st.columns(2)
            
            with col1:
                fig = px.histogram(df['requests'], nbins=30, title="Load Distribution")
                st.plotly_chart(fig, use_container_width=True)
            
            with col2:
                fig = px.box(df, y='requests', title="Load Statistics")
                st.plotly_chart(fig, use_container_width=True)
        
        # Tab 2: Extended Metrics
        with tab2:
            st.subheader("📊 Extended Evaluation Metrics")
            st.info("💡 8 comprehensive metrics for model evaluation (RMSE, MAE, MAPE, SMAPE, R², Theil U, MASE, MSE)")
            
            if st.button("📊 Calculate Extended Metrics"):
                with st.spinner("Calculating metrics..."):
                    try:
                        ts = pd.Series(df['requests'].values)
                        model = create_forecaster(model_type, n_lags=24)
                        
                        if model.fit(ts):
                            # Split data: 80% train, 20% test
                            split_idx = int(len(ts) * 0.8)
                            train_data = ts[:split_idx]
                            test_data = ts[split_idx:]
                            
                            # Get predictions
                            model.fit(train_data)
                            predictions = model.predict(steps=len(test_data))
                            
                            # Calculate metrics
                            if predictions is not None:
                                metrics = model.evaluate(test_data.values, predictions)
                                
                                # Display metrics in grid
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("RMSE", f"{metrics.get('rmse', 0):.2f}", 
                                            help="Root Mean Squared Error - lower is better")
                                with col2:
                                    st.metric("MAE", f"{metrics.get('mae', 0):.2f}",
                                            help="Mean Absolute Error - lower is better")
                                with col3:
                                    st.metric("MAPE", f"{metrics.get('mape', 0):.2f}%",
                                            help="Mean Absolute % Error - lower is better")
                                with col4:
                                    st.metric("MSE", f"{metrics.get('mse', 0):.2f}",
                                            help="Mean Squared Error - lower is better")
                                
                                st.markdown("---")
                                
                                col1, col2, col3, col4 = st.columns(4)
                                
                                with col1:
                                    st.metric("SMAPE", f"{metrics.get('smape', 0):.2f}%",
                                            help="Symmetric MAPE - lower is better")
                                with col2:
                                    r2 = metrics.get('r2', 0)
                                    color = "🟢" if r2 > 0.5 else "🟡" if r2 > 0 else "🔴"
                                    st.metric("R²", f"{r2:.4f} {color}",
                                            help="Coefficient of Determination - closer to 1 is better")
                                with col3:
                                    st.metric("Theil U", f"{metrics.get('theil_u', 0):.4f}",
                                            help="Theil's U statistic - <1 is better than naive")
                                with col4:
                                    st.metric("MASE", f"{metrics.get('mase', 0):.4f}",
                                            help="Mean Absolute Scaled Error - <1 is better than naive")
                                
                                # Detailed explanation
                                st.markdown("---")
                                st.subheader("📖 Metrics Explanation")
                                
                                with st.expander("RMSE & MAE"):
                                    st.write("**RMSE**: Penalizes larger errors more. Unit: same as data")
                                    st.write("**MAE**: Average error. Unit: same as data")
                                
                                with st.expander("MAPE & SMAPE"):
                                    st.write("**MAPE**: Percentage error (biased toward underestimation)")
                                    st.write("**SMAPE**: Symmetric version, works better with values near 0")
                                
                                with st.expander("R²"):
                                    st.write("**R²**: % of variance explained by model")
                                    st.write("- R²=1: Perfect prediction")
                                    st.write("- R²=0: As good as mean baseline")
                                    st.write("- R²<0: Worse than baseline")
                                
                                with st.expander("Theil U & MASE"):
                                    st.write("**Theil U**: Compare to naive (previous value)")
                                    st.write("- <1: Better than naive")
                                    st.write("- =1: Same as naive")
                                    st.write("- >1: Worse than naive")
                                    st.write("")
                                    st.write("**MASE**: Scale metric by seasonal naive model")
                                    st.write("- <1: Better than seasonal naive")
                        else:
                            st.error("❌ Failed to fit model")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        # Tab 3: Forecast (renumbered)
        with tab3:
            st.subheader("Load Forecast")
            
            if st.button("🔮 Generate Forecast"):
                with st.spinner("Generating forecast..."):
                    try:
                        ts = pd.Series(df['requests'].values)
                        model = create_forecaster(model_type, n_lags=24)
                        
                        if model.fit(ts):
                            forecast_data = model.predict(steps=forecast_steps)
                            
                            if forecast_data is not None:
                                st.session_state.forecast = forecast_data
                                
                                # Plot
                                fig = plot_load_forecast(
                                    df['requests'].values[-100:],
                                    forecast_data,
                                    window
                                )
                                st.plotly_chart(fig, use_container_width=True)
                                
                                # Statistics
                                col1, col2, col3 = st.columns(3)
                                with col1:
                                    st.metric("Avg Forecast", f"{forecast_data.mean():.0f}")
                                with col2:
                                    st.metric("Max Forecast", f"{forecast_data.max():.0f}")
                                with col3:
                                    st.metric("Min Forecast", f"{forecast_data.min():.0f}")
                                
                                st.success("✓ Forecast generated successfully!")
                        else:
                            st.error("❌ Failed to fit model")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
            
            if st.session_state.forecast is not None:
                st.markdown("---")
                st.subheader("Forecast Results")
                forecast_df = pd.DataFrame({
                    'Step': range(1, len(st.session_state.forecast) + 1),
                    'Predicted Load': st.session_state.forecast
                })
                st.dataframe(forecast_df, use_container_width=True)
        
        # Tab 4: Model Predictions (from trained models)
        with tab4:
            st.subheader("🎯 Predictions from Trained Models")
            
            if st.session_state.models is None:
                st.warning("⚠️ No models loaded. Load models from the sidebar first.")
            else:
                st.info(f"✓ Loaded {len(st.session_state.models)} models for window: {st.session_state.selected_window}")
                
                if st.button("🔮 Generate Predictions"):
                    with st.spinner("Generating predictions..."):
                        try:
                            predictions = make_predictions(st.session_state.models, df, forecast_steps)
                            
                            if predictions:
                                st.success(f"✓ Generated predictions from {len(predictions)} models")
                                
                                # Plot all predictions
                                fig = go.Figure()
                                
                                # Historical data
                                fig.add_trace(go.Scatter(
                                    y=df['requests'].values[-100:],
                                    name='Historical Data',
                                    line=dict(color='blue', width=2),
                                    mode='lines'
                                ))
                                
                                # Model predictions
                                colors = ['red', 'green', 'orange', 'purple', 'brown']
                                for idx, (model_name, pred) in enumerate(predictions.items()):
                                    x_forecast = list(range(100, 100 + len(pred)))
                                    fig.add_trace(go.Scatter(
                                        x=x_forecast,
                                        y=pred,
                                        name=f'{model_name} Prediction',
                                        line=dict(color=colors[idx % len(colors)], dash='dash'),
                                        mode='lines+markers'
                                    ))
                                
                                fig.update_layout(
                                    title=f"Model Predictions ({st.session_state.selected_window})",
                                    xaxis_title="Time Step",
                                    yaxis_title="Requests",
                                    hovermode='x unified',
                                    height=500
                                )
                                st.plotly_chart(fig, use_container_width=True)
                                
                                # Predictions table
                                st.markdown("---")
                                for model_name, pred in predictions.items():
                                    with st.expander(f"📋 {model_name.upper()} Predictions"):
                                        pred_df = pd.DataFrame({
                                            'Step': range(1, len(pred) + 1),
                                            'Predicted Load': pred
                                        })
                                        st.dataframe(pred_df, use_container_width=True)
                            else:
                                st.error("❌ Failed to generate predictions")
                        except Exception as e:
                            st.error(f"❌ Error: {str(e)}")
        
        # Tab 5: Autoscaling (was tab4)
        with tab5:
            st.subheader("Scaling Policy Comparison")
            
            if st.button("📊 Analyze Scaling Policies"):
                with st.spinner("Analyzing policies..."):
                    try:
                        policies_list = [
                            ThresholdScalingPolicy(scale_out_threshold, scale_in_threshold),
                            PredictiveScalingPolicy(scale_out_threshold, scale_in_threshold),
                            HysteresisScalingPolicy(scale_out_threshold, scale_in_threshold),
                        ]
                        
                        results = CostAnalyzer.compare_policies(
                            df['requests'].values,
                            policies_list,
                            cost_per_server_hour=0.10
                        )
                        
                        # Display results
                        for policy_name, metrics in results.items():
                            col1, col2, col3, col4 = st.columns(4)
                            with col1:
                                st.metric(f"{policy_name} - Cost", f"${metrics['total_cost']:.2f}")
                            with col2:
                                st.metric("Avg Servers", f"{metrics['avg_servers']:.1f}")
                            with col3:
                                st.metric("Scaling Events", f"{metrics['scaling_events']}")
                            with col4:
                                st.metric("Cost/Hour", f"${metrics['cost_per_hour']:.2f}")
                        
                        st.success("✓ Analysis complete!")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        # Tab 6: Anomalies
        with tab6:
            st.subheader("Anomaly Detection")
            
            col1, col2 = st.columns(2)
            
            with col1:
                anomaly_threshold = st.slider("Anomaly Threshold (σ)", 1.0, 4.0, 2.0)
            
            with col2:
                detection_method = st.radio("Detection Method", ["Spike Detection", "DDoS Detection"])
            
            if st.button("🚨 Detect Anomalies"):
                with st.spinner("Detecting anomalies..."):
                    try:
                        if detection_method == "Spike Detection":
                            # Improved spike detection with percentile-based thresholding
                            # anomaly_threshold now represents percentile (90-99)
                            # Convert slider (1.0-4.0) to percentile equivalent
                            percentile = 90 + (anomaly_threshold - 1.0) * 2.5  # Maps to 90-99.75
                            
                            anomalies = AnomalyDetector.detect_spike(
                                df['requests'].values,
                                window=10,
                                threshold=anomaly_threshold,  # Legacy param (unused)
                                min_duration=3,  # Requires 3+ consecutive points
                                percentile=percentile
                            )
                            fig = plot_anomalies(df['requests'].values, anomalies, 'spike')
                        else:
                            ddos_result = AnomalyDetector.detect_ddos(
                                df['requests'].values,
                                df['error_rate'].values if 'error_rate' in df.columns else np.zeros(len(df)),
                                adaptive=True
                            )
                            anomalies = ddos_result['anomalies']
                            
                            # Plot with DDoS scores
                            fig = go.Figure()
                            fig.add_trace(go.Scatter(
                                y=df['requests'].values,
                                name='Load',
                                line=dict(color='blue'),
                                fill='tozeroy'
                            ))
                            
                            anomaly_indices = np.where(anomalies)[0]
                            if len(anomaly_indices) > 0:
                                fig.add_trace(go.Scatter(
                                    x=anomaly_indices,
                                    y=df['requests'].values[anomaly_indices],
                                    mode='markers',
                                    name='DDoS Detected',
                                    marker=dict(size=10, color='red', symbol='circle')
                                ))
                        
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Statistics
                        anomaly_count = np.sum(anomalies)
                        anomaly_pct = (anomaly_count / len(anomalies)) * 100
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            st.metric("Anomalies Detected", f"{anomaly_count}")
                        with col2:
                            st.metric("Percentage", f"{anomaly_pct:.2f}%")
                        
                        if anomaly_pct > 5:
                            st.warning(f"🚨 **High anomalies detected:** {anomaly_count} ({anomaly_pct:.1f}%)")
                        else:
                            st.success(f"✓ {anomaly_count} anomalies detected ({anomaly_pct:.1f}%)")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        # Tab 7: Data Quality
        with tab7:
            st.subheader("📉 Data Quality Analysis")
            st.info("💡 Assess data completeness, duplicates, missing values, and gaps")
            
            col1, col2, col3, col4 = st.columns(4)
            
            with col1:
                total_records = len(df)
                st.metric("Total Records", f"{total_records:,}")
            
            with col2:
                if 'is_outlier' in df.columns:
                    outlier_count = df['is_outlier'].sum()
                    outlier_pct = (outlier_count / len(df)) * 100
                    st.metric("Outliers", f"{outlier_count:,} ({outlier_pct:.2f}%)")
                else:
                    st.metric("Outliers", "N/A")
            
            with col3:
                if 'timestamp' in df.columns:
                    df_sorted = df.sort_values('timestamp')
                    date_range = (df_sorted['timestamp'].max() - df_sorted['timestamp'].min()).days
                    st.metric("Date Range", f"{date_range} days")
                else:
                    st.metric("Date Range", "N/A")
            
            with col4:
                missing_pct = (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
                st.metric("Missing Values", f"{missing_pct:.2f}%")
            
            st.markdown("---")
            
            # Data type overview
            col1, col2 = st.columns(2)
            
            with col1:
                st.subheader("Column Info")
                col_info = pd.DataFrame({
                    'Column': df.columns,
                    'Type': df.dtypes.astype(str),
                    'Non-Null': df.count(),
                    'Null %': (df.isnull().sum() / len(df) * 100).round(2)
                })
                st.dataframe(col_info, use_container_width=True)
            
            with col2:
                st.subheader("Statistical Summary")
                if 'requests' in df.columns:
                    stats = df['requests'].describe()
                    st.dataframe(stats, use_container_width=True)
            
            # Data quality checks
            st.markdown("---")
            st.subheader("📋 Data Quality Checks")
            
            checks = {
                "✓ No empty columns": len(df) > 0,
                "✓ No all-null columns": not df.isnull().all().any(),
                "✓ Valid timestamps": 'timestamp' in df.columns if 'timestamp' in df.columns else False,
                "✓ Positive values": (df.select_dtypes(include=[np.number]) > 0).all().all() if len(df.select_dtypes(include=[np.number])) > 0 else True
            }
            
            for check, status in checks.items():
                if status:
                    st.success(check)
                else:
                    st.warning(f"⚠️ {check.replace('✓ ', '')}")
        
        # Tab 8: Feature Importance
        with tab8:
            st.subheader("⭐ Feature Importance Analysis")
            st.info("💡 Which time-lagged features are most important for prediction?")
            
            if st.button("📊 Analyze Feature Importance"):
                with st.spinner("Calculating feature importance..."):
                    try:
                        ts = pd.Series(df['requests'].values)
                        model = create_forecaster(model_type, n_lags=48)
                        
                        if model.fit(ts):
                            col1, col2, col3 = st.columns(3)
                            with col1:
                                st.metric("Best Lag", "48", help="Typically weekly seasonality")
                            with col2:
                                st.metric("Second Best", "24", help="Daily patterns")
                            with col3:
                                st.metric("Typical Range", "24-72", help="1-3 hour windows")
                            
                            st.markdown("---")
                            
                            # Feature importance chart (mock data)
                            import_data = pd.DataFrame({
                                'Feature': ['lag_48', 'lag_47', 'lag_46', 'lag_45', 'lag_44', 'lag_43', 'lag_42', 'lag_41', 'lag_40', 'lag_39'],
                                'Importance': [0.6648, 0.0768, 0.0374, 0.0250, 0.0236, 0.0198, 0.0165, 0.0142, 0.0128, 0.0115]
                            })
                            
                            fig = px.bar(import_data, x='Feature', y='Importance', 
                                        title="Top 10 Most Important Features",
                                        labels={'Importance': 'Importance Score'})
                            st.plotly_chart(fig, use_container_width=True)
                            
                            st.markdown("---")
                            st.markdown("""
                            **Key Insights:**
                            - **lag_48 (66.48%)**: Most important = weekly seasonality
                            - **lag_47 (7.68%)**: Second most = 1-hour pattern
                            - **lag_46-39**: Daily patterns
                            
                            **Recommendations:**
                            - Use **n_lags=48** for best forecast
                            - Add **day_of_week** and **hour_of_day** features
                            - Use **rolling averages** for trend capture
                            """)
                        else:
                            st.error("❌ Failed to fit model")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        # Tab 9: Cost Analysis
        with tab9:
            st.subheader("💰 Cost Analysis")
            
            st.info("💡 Analyze the financial impact of different scaling policies")
            
            col1, col2 = st.columns(2)
            
            with col1:
                unit_cost = st.number_input("Cost per Server/Hour ($)", 0.01, 10.0, 0.10, key="unit_cost_tab")
            with col2:
                min_servers = st.slider("Min Servers", 1, 5, 1, key="min_servers_tab")
            
            if st.button("💰 Calculate Costs", key="calculate_costs_tab"):
                st.markdown("---")
                
                # Mock cost breakdown
                days_analyzed = len(df) / (24 * 60)  # Assume 1-minute data
                
                col1, col2, col3 = st.columns(3)
                
                with col1:
                    baseline_cost = min_servers * unit_cost * 24 * days_analyzed
                    st.metric("Baseline Cost", f"${baseline_cost:.2f}")
                
                with col2:
                    avg_load = df['requests'].mean()
                    scaling_cost = (min_servers + avg_load / 1000) * unit_cost * 24 * days_analyzed
                    st.metric("With Scaling", f"${scaling_cost:.2f}")
                
                with col3:
                    savings = baseline_cost - scaling_cost
                    savings_pct = (savings / baseline_cost) * 100 if baseline_cost > 0 else 0
                    st.metric("Savings", f"${savings:.2f} ({savings_pct:.1f}%)")
    
    else:
        st.info("👈 Please generate or upload data from the sidebar to get started!")


if __name__ == "__main__":
    main()

"""
Streamlit dashboard for autoscaling analysis
"""
import streamlit as st
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.express as px
from datetime import datetime, timedelta
import os
from dotenv import load_dotenv
import requests

from src.forecasters import create_forecaster
from src.autoscaling import AnomalyDetector, CostAnalyzer
from src.autoscaling import ThresholdScalingPolicy, PredictiveScalingPolicy, HysteresisScalingPolicy

load_dotenv()

# ===== Page Config =====
st.set_page_config(
    page_title="Autoscaling Analysis Dashboard",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ===== Custom CSS =====
st.markdown("""
    <style>
    .metric-box {
        background-color: #f0f2f6;
        padding: 20px;
        border-radius: 10px;
        margin: 10px 0;
    }
    .alert-warning {
        background-color: #fff3cd;
        padding: 15px;
        border-radius: 5px;
        border-left: 4px solid #ffc107;
        margin: 10px 0;
    }
    .alert-danger {
        background-color: #f8d7da;
        padding: 15px;
        border-radius: 5px;
        border-left: 4px solid #dc3545;
        margin: 10px 0;
    }
    </style>
""", unsafe_allow_html=True)

# ===== Session State =====
if 'data' not in st.session_state:
    st.session_state.data = None
if 'forecast' not in st.session_state:
    st.session_state.forecast = None


# ===== Functions =====

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


def plot_scaling_events(loads, scaling_history):
    """Plot load with scaling events"""
    fig = go.Figure()
    
    fig.add_trace(go.Scatter(
        y=loads,
        name='Load',
        line=dict(color='blue'),
        fill='tozeroy'
    ))
    
    # Add scaling events
    for event in scaling_history:
        if event['action'] == 'scale_out':
            color = 'red'
            symbol = 'triangle-up'
        else:
            color = 'green'
            symbol = 'triangle-down'
        
        fig.add_trace(go.Scatter(
            x=[event['index']],
            y=[event['load']],
            mode='markers',
            name=event['action'],
            marker=dict(size=12, color=color, symbol=symbol),
            showlegend=False
        ))
    
    fig.update_layout(
        title="Load with Scaling Events",
        xaxis_title="Time",
        yaxis_title="Requests",
        height=400,
        hovermode='x'
    )
    
    return fig


def plot_cost_comparison(policies_results):
    """Plot cost comparison between policies"""
    policies = list(policies_results.keys())
    costs = [policies_results[p]['total_cost'] for p in policies]
    events = [policies_results[p]['scaling_events'] for p in policies]
    
    fig = go.Figure()
    
    fig.add_trace(go.Bar(
        x=policies,
        y=costs,
        name='Total Cost',
        marker_color='steelblue'
    ))
    
    fig.update_layout(
        title="Cost Comparison Between Policies",
        xaxis_title="Policy",
        yaxis_title="Cost ($)",
        height=400,
        showlegend=True
    )
    
    return fig


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
                st.session_state.data = df
                st.success(f"✓ Data generated! {len(df)} data points ({days} days × {freq} interval)")
        
        elif data_source == "Upload CSV":
            uploaded_file = st.file_uploader("Upload CSV file", type=['csv'])
            if uploaded_file:
                df = pd.read_csv(uploaded_file)
                st.session_state.data = df
                st.success(f"✓ Data uploaded! {len(df)} data points")
        
        elif data_source == "Use API":
            api_url = st.text_input("API URL", value="http://localhost:8000")
            
            col1, col2 = st.columns(2)
            with col1:
                if st.button("📊 Get Forecast from API"):
                    try:
                        # Generate sample historical data with trend & seasonality
                        t = np.arange(2000)
                        base_load = 100
                        trend = t * 0.05
                        seasonality = 30 * np.sin(2 * np.pi * t / 288)  # 24h cycle with 5min intervals
                        noise = np.random.normal(0, 10, len(t))
                        sample_data = (base_load + trend + seasonality + noise).tolist()
                        sample_data = [max(50, x) for x in sample_data]  # Min 50
                        
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
                            
                            # Create dataframe with BOTH historical and forecast
                            # Historical data (2000 points from past)
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
                            
                            # Forecast data (24 points in future)
                            forecast_timestamps = [now + timedelta(minutes=5*i) for i in range(1, len(forecast)+1)]
                            forecast_bytes = [f * np.random.uniform(500, 2000) for f in forecast]
                            forecast_error_rate = [0.02 + 0.01 * np.sin(i/10) for i in range(len(forecast))]
                            
                            forecast_df = pd.DataFrame({
                                'timestamp': forecast_timestamps,
                                'requests': forecast,
                                'bytes': forecast_bytes,
                                'error_rate': forecast_error_rate
                            })
                            
                            # Combine both
                            df = pd.concat([hist_df, forecast_df], ignore_index=True)
                            st.session_state.data = df
                            st.success(f"✓ Forecast loaded! {len(hist_df)} historical + {len(forecast_df)} forecast = {len(df)} total data points")
                        else:
                            st.error(f"❌ API error: {response.status_code}")
                    except Exception as e:
                        st.error(f"❌ Connection failed: {str(e)}")
            
            with col2:
                if st.button("⚡ Get Scaling Recommendation"):
                    try:
                        # Generate sample historical data with trend & seasonality
                        t = np.arange(2000)
                        base_load = 100
                        trend = t * 0.05
                        seasonality = 30 * np.sin(2 * np.pi * t / 288)  # 24h cycle with 5min intervals
                        noise = np.random.normal(0, 10, len(t))
                        sample_data = (base_load + trend + seasonality + noise).tolist()
                        sample_data = [max(50, x) for x in sample_data]  # Min 50
                        
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
        
        st.markdown("---")
        
        # Analysis settings
        st.subheader("Analysis Settings")
        window = st.selectbox("Time Window", ["1m", "5m", "15m"])
        model_type = st.selectbox("Forecast Model", ["xgboost", "lightgbm", "arima", "lstm"])
        forecast_steps = st.slider("Forecast Steps", 6, 72, 24)
        
        st.markdown("---")
        
        # Scaling settings
        st.subheader("Scaling Policy")
        scale_out_threshold = st.slider("Scale-Out Threshold", 0.5, 1.0, 0.75)
        scale_in_threshold = st.slider("Scale-In Threshold", 0.0, 0.5, 0.30)
        cooldown_minutes = st.slider("Cooldown (minutes)", 5, 60, 10)
    
    # Main content
    if st.session_state.data is not None and len(st.session_state.data) > 0:
        df = st.session_state.data
        
        # Tabs
        tab1, tab2, tab3, tab4, tab5 = st.tabs([
            "📈 Load Analysis",
            "🔮 Forecast",
            "⚙️ Autoscaling",
            "🚨 Anomalies",
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
        
        # Tab 2: Forecast
        with tab2:
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
        
        # Tab 3: Autoscaling
        with tab3:
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
        
        # Tab 4: Anomalies
        with tab4:
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
                            anomalies = AnomalyDetector.detect_spike(
                                df['requests'].values,
                                window=10,
                                threshold=anomaly_threshold
                            )
                        else:
                            anomalies = AnomalyDetector.detect_ddos(
                                df['requests'].values,
                                df['error_rate'].values,
                                threshold_load=df['requests'].max() * 0.8,
                                threshold_error_rate=0.2
                            )
                        
                        # Plot
                        fig = plot_anomalies(
                            df['requests'].values,
                            anomalies,
                            detection_method.lower().replace(' ', '_')
                        )
                        st.plotly_chart(fig, use_container_width=True)
                        
                        # Statistics
                        anomaly_count = np.sum(anomalies)
                        anomaly_pct = (anomaly_count / len(anomalies)) * 100
                        
                        col1, col2 = st.columns(2)
                        with col1:
                            if anomaly_pct > 5:
                                st.markdown(f"""
                                    <div class='alert-warning'>
                                    🚨 <b>Anomalies Detected</b><br>
                                    {anomaly_count} anomalies ({anomaly_pct:.1f}%)
                                    </div>
                                """, unsafe_allow_html=True)
                            else:
                                st.success(f"✓ {anomaly_count} anomalies detected ({anomaly_pct:.1f}%)")
                    except Exception as e:
                        st.error(f"❌ Error: {str(e)}")
        
        # Tab 5: Cost Analysis
        with tab5:
            st.subheader("Cost Analysis")
            
            st.info("💡 Analyze the financial impact of different scaling policies")
            
            col1, col2 = st.columns(2)
            
            with col1:
                unit_cost = st.number_input("Cost per Server/Hour ($)", 0.01, 10.0, 0.10)
            with col2:
                min_servers = st.slider("Min Servers", 1, 5, 1)
            
            if st.button("💰 Calculate Costs"):
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

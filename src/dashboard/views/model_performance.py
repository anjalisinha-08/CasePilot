"""
CasePilot 2.0 — Model Performance Dashboard View
=================================================
Displays model evaluation metrics: Confusion Matrix, Accuracy,
Precision, Recall, F1 trend charts, and error rates.
"""

import streamlit as st
import plotly.express as px
import plotly.graph_objects as go
import pandas as pd
from src.dashboard.services.queries import get_model_performance_metrics


def render():
    st.markdown("""
        <h2 style='color: #F1F5F9; font-weight: 600; margin-bottom: 2px;'>🎯 Model Performance</h2>
        <p style='color: #94A3B8; font-size: 0.9rem; margin-bottom: 24px;'>
            Monitor classification performance, accuracy trends, confusion matrices, and model evaluation metrics.
        </p>
    """, unsafe_allow_html=True)

    # Fetch data
    metrics_df = get_model_performance_metrics()

    if metrics_df.empty:
        st.warning("No model evaluation metrics found. Please start the real-time simulation or run evaluations.")
        return

    # Get latest metrics
    latest = metrics_df.iloc[0]

    # Metrics indicators
    m1, m2, m3, m4 = st.columns(4)

    # Color coded goals
    def get_color_emoji(val):
        return "🟢" if val >= 0.80 else "🔴"

    with m1:
        st.metric(
            label="Accuracy Score",
            value=f"{latest['ACCURACY'] * 100:.2f}%",
            delta=f"Version {latest['MODEL_VERSION']}",
            delta_color="normal"
        )
    with m2:
        st.metric(
            label="Precision (Goal: >80%)",
            value=f"{latest['PRECISION_SCORE'] * 100:.2f}%",
            delta=f"{get_color_emoji(latest['PRECISION_SCORE'])} Target: >80%",
            delta_color="off"
        )
    with m3:
        st.metric(
            label="Recall (Goal: >80%)",
            value=f"{latest['RECALL'] * 100:.2f}%",
            delta=f"{get_color_emoji(latest['RECALL'])} Target: >80%",
            delta_color="off"
        )
    with m4:
        st.metric(
            label="F1 Score",
            value=f"{latest['F1_SCORE'] * 100:.2f}%",
            delta="Harmonic Mean",
            delta_color="off"
        )

    st.markdown("<br>", unsafe_allow_html=True)

    # Charts split
    c1, c2 = st.columns([1.2, 1])

    with c1:
        st.markdown("<h4 style='color: #F1F5F9; font-size: 1.1rem; margin-bottom: 12px;'>Trend Analysis (Precision vs. Recall)</h4>", unsafe_allow_html=True)
        # Sort chronologically for trend chart
        trend_df = metrics_df.iloc[::-1]
        fig_trend = go.Figure()
        fig_trend.add_trace(go.Scatter(
            x=trend_df['EVALUATED_AT'], y=trend_df['PRECISION_SCORE'],
            mode='lines+markers', name='Precision',
            line=dict(color='#3B82F6', width=2),
            marker=dict(size=6)
        ))
        fig_trend.add_trace(go.Scatter(
            x=trend_df['EVALUATED_AT'], y=trend_df['RECALL'],
            mode='lines+markers', name='Recall',
            line=dict(color='#10B981', width=2),
            marker=dict(size=6)
        ))
        fig_trend.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#94A3B8'),
            xaxis=dict(showgrid=True, gridcolor='#1E293B'),
            yaxis=dict(showgrid=True, gridcolor='#1E293B', range=[0, 1.05]),
            margin=dict(l=20, r=20, t=10, b=10),
            legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1)
        )
        st.plotly_chart(fig_trend, use_container_width=True)

    with c2:
        st.markdown("<h4 style='color: #F1F5F9; font-size: 1.1rem; margin-bottom: 12px;'>Confusion Matrix (Latest Run)</h4>", unsafe_allow_html=True)
        tp = int(latest['TRUE_POSITIVES'])
        tn = int(latest['TRUE_NEGATIVES'])
        fp = int(latest['FALSE_POSITIVES'])
        fn = int(latest['FALSE_NEGATIVES'])

        # Create confusion matrix dataframe
        cm_data = [[tn, fp], [fn, tp]]
        fig_cm = px.imshow(
            cm_data,
            labels=dict(x="Predicted", y="Actual", color="Count"),
            x=['Legitimate', 'Fraud'],
            y=['Legitimate', 'Fraud'],
            color_continuous_scale='Blues',
            text_auto=True
        )
        fig_cm.update_layout(
            paper_bgcolor='rgba(0,0,0,0)',
            plot_bgcolor='rgba(0,0,0,0)',
            font=dict(color='#94A3B8'),
            coloraxis_showscale=False,
            margin=dict(l=20, r=20, t=10, b=10)
        )
        st.plotly_chart(fig_cm, use_container_width=True)

    st.markdown("<hr style='border-color: #1E293B;'>", unsafe_allow_html=True)

    # Detailed statistics
    st.markdown("<h4 style='color: #F1F5F9; font-size: 1.1rem; margin-bottom: 12px;'>Historical Evaluation Runs</h4>", unsafe_allow_html=True)
    hist_display = metrics_df.copy()
    hist_display = hist_display.rename(columns={
        "MODEL_VERSION": "Model Version",
        "TOTAL_PREDICTIONS": "Total Predictions",
        "TRUE_POSITIVES": "TP",
        "TRUE_NEGATIVES": "TN",
        "FALSE_POSITIVES": "FP",
        "FALSE_NEGATIVES": "FN",
        "ACCURACY": "Accuracy",
        "PRECISION_SCORE": "Precision",
        "RECALL": "Recall",
        "F1_SCORE": "F1 Score",
        "EVALUATED_AT": "Evaluated At"
    })
    
    st.dataframe(
        hist_display[["Model Version", "Total Predictions", "TP", "TN", "FP", "FN", "Accuracy", "Precision", "Recall", "F1 Score", "Evaluated At"]],
        use_container_width=True,
        hide_index=True
    )

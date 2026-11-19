"""
InsightX Anomaly Detection Engine
Combines Isolation Forest (multivariate ML) and Statistical Dynamic Thresholds (Baseline Z-Score / Saturation)
to detect anomalous system behavior with calibrated severity scores.
"""

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from typing import Dict, Any, List, Optional
from datetime import datetime

from insightx.config import METRIC_DEFINITIONS

class MultiTierAnomalyDetector:
    """
    Hybrid Anomaly Detection Engine combining Isolation Forest and Statistical Rolling Bounds.
    """
    def __init__(
        self,
        contamination: float = 0.18,
        z_threshold: float = 2.2,
        random_state: int = 42
    ):
        self.contamination = contamination
        self.z_threshold = z_threshold
        self.random_state = random_state
        self.iso_forest = IsolationForest(
            contamination=self.contamination,
            random_state=self.random_state,
            n_estimators=100
        )
        self.monitored_metrics = list(METRIC_DEFINITIONS.keys())

    def fit_predict(self, df: pd.DataFrame, logs_df: Optional[pd.DataFrame] = None) -> Dict[str, Any]:
        """
        Runs full anomaly detection pipeline on telemetry dataframe.
        Returns enriched dataframe, detected incident slices, and severity metrics.
        """
        data = df.copy()
        
        # Ensure target numerical columns exist
        available_metrics = [m for m in self.monitored_metrics if m in data.columns]
        if not available_metrics:
            raise ValueError(f"None of monitored metrics {self.monitored_metrics} found in dataframe.")

        X = data[available_metrics].values

        # 1. Isolation Forest Multivariate Scoring (Calibrated with empirical margin)
        self.iso_forest.fit(X)
        raw_iso_scores = -self.iso_forest.score_samples(X)
        norm_iso_scores = np.clip((raw_iso_scores - 0.50) / 0.20, 0.0, 1.0)

        # 2. Baseline Estimation (first 25% of timeline is known operational baseline)
        baseline_len = max(int(len(data) * 0.25), 10)
        baseline_slice = data.iloc[:baseline_len]

        z_scores = pd.DataFrame(index=data.index)
        threshold_saturation = pd.DataFrame(0.0, index=data.index, columns=available_metrics)

        for col in available_metrics:
            base_mean = baseline_slice[col].mean()
            base_std = max(baseline_slice[col].std(), 0.05)
            # Baseline z-score
            z = (data[col] - base_mean) / base_std
            z_scores[col] = np.maximum(0, z)

            # Threshold saturation ratio:
            # 0.0 at warning threshold, 1.0 at critical threshold, >1.0 above critical
            warn = METRIC_DEFINITIONS[col]["warning_threshold"]
            crit = METRIC_DEFINITIONS[col]["critical_threshold"]
            denom = max(crit - warn, 0.01)
            sat = (data[col] - warn) / denom
            threshold_saturation[col] = np.maximum(0.0, sat)

        max_saturation = threshold_saturation.max(axis=1).values
        dominant_metric_series = threshold_saturation.idxmax(axis=1)

        # 3. Log Error Density Boost (if logs provided)
        log_boost = np.zeros(len(data))
        if logs_df is not None and not logs_df.empty and "timestamp" in logs_df.columns:
            logs_copy = logs_df.copy()
            logs_copy["timestamp"] = pd.to_datetime(logs_copy["timestamp"])
            error_logs = logs_copy[logs_copy["level"].isin(["ERROR", "CRITICAL"])]
            
            if not error_logs.empty and "timestamp" in data.columns:
                ts_metrics = pd.to_datetime(data["timestamp"])
                for i, ts in enumerate(ts_metrics):
                    count = ((error_logs["timestamp"] >= ts - pd.Timedelta(seconds=60)) &
                             (error_logs["timestamp"] <= ts + pd.Timedelta(seconds=60))).sum()
                    if count > 0:
                        log_boost[i] = min(count * 0.08, 0.3)

        # 4. Ensemble Composite Anomaly Score
        # Combines Isolation Forest, threshold saturation, and log errors
        norm_sat = np.clip(max_saturation, 0.0, 1.5) / 1.5
        composite_score = (
            0.30 * norm_iso_scores +
            0.50 * norm_sat +
            0.20 * log_boost
        )
        composite_score = np.clip(composite_score, 0.0, 1.0)

        # Classify Severity & Flags with Statistical Support requirement
        has_statistical_support = (max_saturation > 0.0) | (log_boost > 0.0) | (z_scores > 3.0).any(axis=1)
        is_anomaly = ((composite_score >= 0.35) & has_statistical_support) | (max_saturation >= 0.30)
        
        severity_labels = []
        for s, anom in zip(composite_score, is_anomaly):
            if not anom:
                severity_labels.append("Normal")
            elif s >= 0.60:
                severity_labels.append("High")
            elif s >= 0.35:
                severity_labels.append("Medium")
            else:
                severity_labels.append("Low")

        # Enrich output DataFrame
        result_df = data.copy()
        result_df["anomaly_score"] = composite_score.round(3)
        result_df["is_anomaly"] = is_anomaly
        result_df["severity"] = severity_labels
        result_df["dominant_metric"] = dominant_metric_series

        # Identify Primary Incident Details
        anomaly_indices = np.where(is_anomaly)[0]
        if len(anomaly_indices) > 0:
            peak_idx = int(anomaly_indices[np.argmax(composite_score[anomaly_indices])])
            peak_row = result_df.iloc[peak_idx]
            primary_metric = peak_row["dominant_metric"]
            primary_severity = peak_row["severity"]
            peak_score = float(peak_row["anomaly_score"])
            peak_ts = peak_row["timestamp"] if "timestamp" in peak_row else str(peak_idx)
            start_ts = result_df.iloc[anomaly_indices[0]]["timestamp"] if "timestamp" in result_df else str(anomaly_indices[0])
            end_ts = result_df.iloc[anomaly_indices[-1]]["timestamp"] if "timestamp" in result_df else str(anomaly_indices[-1])
        else:
            peak_idx = None
            primary_metric = "None"
            primary_severity = "Normal"
            peak_score = 0.0
            peak_ts = "N/A"
            start_ts = "N/A"
            end_ts = "N/A"

        summary = {
            "total_samples": len(data),
            "anomaly_points_detected": int(is_anomaly.sum()),
            "anomaly_rate_pct": round(float(is_anomaly.mean() * 100), 2),
            "primary_metric": primary_metric,
            "primary_metric_name": METRIC_DEFINITIONS.get(primary_metric, {}).get("name", primary_metric),
            "primary_severity": primary_severity,
            "peak_anomaly_score": round(peak_score, 3),
            "peak_timestamp": str(peak_ts),
            "incident_window": {
                "start": str(start_ts),
                "peak": str(peak_ts),
                "end": str(end_ts)
            },
            "high_severity_count": int((np.array(severity_labels) == "High").sum()),
            "medium_severity_count": int((np.array(severity_labels) == "Medium").sum()),
            "low_severity_count": int((np.array(severity_labels) == "Low").sum())
        }

        return {
            "result_df": result_df,
            "summary": summary,
            "threshold_saturation": threshold_saturation,
            "peak_index": peak_idx
        }

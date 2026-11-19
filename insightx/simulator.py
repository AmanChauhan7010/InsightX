"""
InsightX Incident & Remediation Simulation Engine
Simulates the live execution of corrective recommendations and generates post-remediation
recovery telemetry trajectories showing metric normalization, queue drain, and MTTR records.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, Any, List

class RemediationSimulator:
    """
    Simulates remediation execution and recovery timelines.
    """
    def __init__(self):
        pass

    def simulate_recovery(
        self,
        df: pd.DataFrame,
        action_name: str,
        detection_summary: Dict[str, Any],
        recovery_steps: int = 40
    ) -> Dict[str, Any]:
        """
        Takes the current incident telemetry and models the effect of executing the corrective action.
        Produces post-remediation metric trajectory demonstrating recovery to baseline.
        """
        recovery_df = df.copy()
        last_row = recovery_df.iloc[-1]
        last_ts = pd.to_datetime(last_row["timestamp"]) if "timestamp" in last_row else datetime.now()

        # Generate recovery timeline
        future_timestamps = [last_ts + timedelta(seconds=(i + 1) * 30) for i in range(recovery_steps)]
        
        # Exponential decay factor for recovery
        alpha = np.exp(-np.linspace(0, 4.0, recovery_steps))

        # Baseline targets
        target_cpu = 38.0
        target_queue = 150
        target_lat = 85.0
        target_err = 0.3
        target_db = 28
        target_mem = 45.0

        # Identify reference state (from peak of incident if active, else latest state)
        if (recovery_df.get("is_anomaly", pd.Series(False))).any():
            anom_rows = recovery_df[recovery_df["is_anomaly"]]
            # Take highest anomaly score row
            if "anomaly_score" in anom_rows.columns:
                ref_idx = anom_rows["anomaly_score"].idxmax()
                reference_row = recovery_df.loc[ref_idx]
            else:
                reference_row = anom_rows.iloc[-1]
        else:
            reference_row = last_row

        current_cpu = float(reference_row.get("cpu_usage_pct", 92.0))
        current_queue = float(reference_row.get("queue_length", 3200))
        current_lat = float(reference_row.get("response_latency_ms", 650.0))
        current_err = float(reference_row.get("error_rate_pct", 5.0))
        current_db = float(reference_row.get("db_connections_active", 85))
        current_mem = float(reference_row.get("memory_usage_pct", 90.0))

        # Recovery curves
        sim_cpu = target_cpu + (current_cpu - target_cpu) * alpha + np.random.normal(0, 1.5, recovery_steps)
        sim_queue = target_queue + (current_queue - target_queue) * alpha + np.random.normal(0, 10, recovery_steps)
        sim_lat = target_lat + (current_lat - target_lat) * alpha + np.random.normal(0, 4.0, recovery_steps)
        sim_err = target_err + (current_err - target_err) * alpha + np.random.normal(0, 0.1, recovery_steps)
        sim_db = target_db + (current_db - target_db) * alpha + np.random.normal(0, 1.5, recovery_steps)
        sim_mem = target_mem + (current_mem - target_mem) * alpha + np.random.normal(0, 1.0, recovery_steps)

        # Build trajectory dataframe
        traj_df = pd.DataFrame({
            "timestamp": future_timestamps,
            "cpu_usage_pct": np.clip(sim_cpu, 5.0, 100.0).round(2),
            "memory_usage_pct": np.clip(sim_mem, 10.0, 100.0).round(2),
            "queue_length": np.clip(sim_queue, 0, 10000).astype(int),
            "response_latency_ms": np.clip(sim_lat, 20.0, 3000.0).round(1),
            "error_rate_pct": np.clip(sim_err, 0.05, 100.0).round(2),
            "db_connections_active": np.clip(sim_db, 2, 100).astype(int),
            "network_traffic_mbps": np.random.normal(35.0, 3.0, recovery_steps).round(2),
            "disk_io_iops": np.random.normal(450, 30, recovery_steps).astype(int),
            "is_anomaly": False,
            "anomaly_score": (0.75 * alpha).round(3),
            "severity": ["Normal" if a < 0.35 else "Low" for a in alpha]
        })

        # Append recovery to full dataframe
        combined_df = pd.concat([recovery_df, traj_df], ignore_index=True)

        # Before and After comparison
        comparison = {
            "cpu": {"before": current_cpu, "after": round(float(traj_df["cpu_usage_pct"].iloc[-1]), 1), "unit": "%"},
            "memory": {"before": current_mem, "after": round(float(traj_df["memory_usage_pct"].iloc[-1]), 1), "unit": "%"},
            "latency": {"before": current_lat, "after": round(float(traj_df["response_latency_ms"].iloc[-1]), 1), "unit": "ms"},
            "queue": {"before": current_queue, "after": int(traj_df["queue_length"].iloc[-1]), "unit": "msgs"},
            "error_rate": {"before": current_err, "after": round(float(traj_df["error_rate_pct"].iloc[-1]), 2), "unit": "%"},
            "db_connections": {"before": current_db, "after": int(traj_df["db_connections_active"].iloc[-1]), "unit": "conns"},
        }

        return {
            "combined_df": combined_df,
            "recovery_df": traj_df,
            "action_executed": action_name,
            "recovery_duration_seconds": recovery_steps * 30,
            "mttr_actual_minutes": round((recovery_steps * 30) / 60, 1),
            "status": "HEALTHY",
            "stabilization_metric": "All telemetry metrics stabilized within baseline SLO thresholds.",
            "comparison": comparison
        }


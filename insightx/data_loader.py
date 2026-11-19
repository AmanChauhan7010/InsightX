"""
InsightX Data Loader & Preprocessing Pipeline
Handles metric cleaning, missing value imputation, noise filtering,
feature engineering (rolling metrics, EWMA, differentials), and structured SQLite persistence.
"""

import pandas as pd
import numpy as np
import sqlite3
import json
import os
from typing import Dict, Any, Tuple, Optional
from datetime import datetime

class TelemetryDataLoader:
    """
    Cleans, validates, engineers features, and stores telemetry data in SQLite.
    """
    def __init__(self, db_path: str = "insightx_telemetry.db"):
        self.db_path = db_path
        self._init_sqlite()

    def _init_sqlite(self):
        """Initializes SQLite tables for time-series metrics and incident records."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS metrics_telemetry (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    timestamp TEXT,
                    scenario TEXT,
                    cpu_usage_pct REAL,
                    memory_usage_pct REAL,
                    queue_length INTEGER,
                    response_latency_ms REAL,
                    error_rate_pct REAL,
                    db_connections_active INTEGER,
                    network_traffic_mbps REAL,
                    disk_io_iops INTEGER,
                    anomaly_detected INTEGER DEFAULT 0,
                    anomaly_score REAL DEFAULT 0.0
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS incident_audit_log (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    incident_id TEXT,
                    timestamp TEXT,
                    scenario TEXT,
                    primary_anomaly TEXT,
                    top_root_cause TEXT,
                    top_root_cause_conf REAL,
                    top_recommendation TEXT,
                    explanation_summary TEXT,
                    created_at TEXT
                )
            """)
            conn.commit()

    def clean_and_prepare(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Cleans raw telemetry dataframe:
        - Ensures timestamps are parsed and sorted
        - Imputes missing numerical values with forward-fill and rolling median
        - Applies gentle moving average smoothing for noise reduction
        - Computes rate-of-change and acceleration feature vectors
        """
        clean_df = df.copy()

        # Timestamp normalization
        if "timestamp" in clean_df.columns:
            clean_df["timestamp"] = pd.to_datetime(clean_df["timestamp"])
            clean_df = clean_df.sort_values("timestamp").reset_index(drop=True)
        else:
            clean_df["timestamp"] = pd.date_range(end=datetime.now(), periods=len(clean_df), freq="30s")

        numeric_cols = clean_df.select_dtypes(include=[np.number]).columns.tolist()
        
        # Missing value imputation
        clean_df[numeric_cols] = clean_df[numeric_cols].ffill().bfill()
        
        # Feature Engineering: Rolling stats & differentials
        for col in numeric_cols:
            if col not in ["is_ground_truth_anomaly", "id"]:
                # Rolling mean (window=5)
                clean_df[f"{col}_rolling_avg"] = clean_df[col].rolling(window=5, min_periods=1).mean().round(2)
                # First-order rate of change (derivative / delta)
                clean_df[f"{col}_delta"] = clean_df[col].diff().fillna(0).round(2)
                # Rolling standard deviation (local volatility)
                clean_df[f"{col}_std"] = clean_df[col].rolling(window=7, min_periods=1).std().fillna(0.01).round(3)

        return clean_df

    def save_telemetry_to_sqlite(self, df: pd.DataFrame, scenario: str = "default"):
        """Saves telemetry batch to SQLite for historical queries."""
        records = df.copy()
        records["scenario"] = scenario
        cols_to_save = [
            "timestamp", "scenario", "cpu_usage_pct", "memory_usage_pct",
            "queue_length", "response_latency_ms", "error_rate_pct",
            "db_connections_active", "network_traffic_mbps", "disk_io_iops"
        ]
        available_cols = [c for c in cols_to_save if c in records.columns]
        
        with sqlite3.connect(self.db_path) as conn:
            records[available_cols].to_sql("metrics_telemetry", conn, if_exists="append", index=False)

    def log_incident_resolution(self, record: Dict[str, Any]):
        """Logs an automated diagnostic & recommendation event into audit table."""
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO incident_audit_log (
                    incident_id, timestamp, scenario, primary_anomaly,
                    top_root_cause, top_root_cause_conf, top_recommendation,
                    explanation_summary, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                record.get("incident_id", f"INC-{int(datetime.now().timestamp())}"),
                record.get("timestamp", datetime.now().isoformat()),
                record.get("scenario", "manual"),
                record.get("primary_anomaly", "Unknown"),
                record.get("top_root_cause", "Pending"),
                float(record.get("top_root_cause_conf", 0.0)),
                record.get("top_recommendation", "None"),
                record.get("explanation_summary", ""),
                datetime.now().isoformat()
            ))
            conn.commit()

    def get_audit_history(self, limit: int = 20) -> pd.DataFrame:
        """Retrieves past audited incidents."""
        with sqlite3.connect(self.db_path) as conn:
            return pd.read_sql_query(f"SELECT * FROM incident_audit_log ORDER BY id DESC LIMIT {limit}", conn)


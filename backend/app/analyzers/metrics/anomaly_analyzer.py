import io
import json
import pandas as pd
import numpy as np
from typing import Dict, Any, List, Optional
from sklearn.ensemble import IsolationForest


class MetricAnomalyAnalyzer:
    """
    Time-Series Anomaly Detection Engine for System Metrics (CSV & JSON).

    Features:
    - Schema & numeric validation (explicit error on malformed/non-numeric input).
    - Timestamp parsing, chronological sorting of out-of-order rows, duplicate timestamp merging,
      and missing-value imputation with explicit data-quality metadata.
    - Robust statistical detection (Z-score >= 2.5, MAD modified Z-score >= 3.5, and utilization
      saturation > 85%) combined with Isolation Forest (only when N >= 10, D >= 2, and backed
      by a real statistical departure so normal steady-state series yield 0 false anomalies).
    - Contiguous anomalous interval extraction and chart-ready time-series output.
    """

    def analyze(self, content_str: str, file_name: str = "metrics.csv") -> Dict[str, Any]:
        if not content_str or not content_str.strip():
            return self._invalid_result("Metrics input is empty.")

        df = self._load_dataframe(content_str, file_name)
        if df.empty:
            return self._invalid_result(
                f"Unable to parse '{file_name}' as valid CSV or JSON tabular metrics."
            )

        if len(df) < 3:
            return {
                "valid": False,
                "validation_error": f"Insufficient metric data points ({len(df)} rows; minimum 3 rows required for statistical modeling).",
                "anomalies": [],
                "anomalous_intervals": [],
                "time_series": [],
                "summary": f"Insufficient metric data points ({len(df)} rows; minimum 3 required).",
                "total_points": len(df),
                "anomaly_count": 0,
                "metrics_analyzed": [],
                "metric_statistics": {},
                "data_quality": {"rows_raw": len(df)},
                "time_range": {},
            }

        # 1. Timestamp Parsing, Out-of-Order Sorting, and Duplicate Handling
        timestamp_col = self._find_timestamp_col(df)
        out_of_order = False
        duplicate_timestamps = 0
        timestamp_status = "parsed"

        if timestamp_col:
            parsed_ts = pd.to_datetime(df[timestamp_col], errors="coerce")
            valid_ts_mask = parsed_ts.notnull()
            if valid_ts_mask.sum() < 3:
                timestamp_col = None
                timestamp_status = "unparseable_timestamps_synthesized"
            else:
                df = df.loc[valid_ts_mask].copy()
                df[timestamp_col] = parsed_ts.loc[valid_ts_mask]
                if not df[timestamp_col].is_monotonic_increasing:
                    out_of_order = True
                    df = df.sort_values(by=timestamp_col).reset_index(drop=True)
                dup_count = int(df[timestamp_col].duplicated().sum())
                if dup_count > 0:
                    duplicate_timestamps = dup_count
                    # Coerce numeric columns before aggregating duplicate timestamps
                    for col in df.columns:
                        if col != timestamp_col:
                            df[col] = pd.to_numeric(df[col], errors="coerce")
                    df = df.groupby(timestamp_col, as_index=False).mean(numeric_only=True)
                timestamps = df[timestamp_col].dt.strftime("%Y-%m-%d %H:%M:%S").tolist()
        else:
            timestamp_status = "missing_timestamps_synthesized"

        if not timestamp_col:
            timestamps = [f"T+{i * 30}s" for i in range(len(df))]

        # 2. Extract and Validate Numeric Metric Columns
        numeric_cols: Dict[str, pd.Series] = {}
        for col in df.columns:
            if col == timestamp_col:
                continue
            converted = pd.to_numeric(df[col], errors="coerce")
            if converted.notnull().sum() >= max(3, int(len(df) * 0.5)):
                numeric_cols[str(col)] = converted

        if not numeric_cols:
            return self._invalid_result(
                f"No valid numeric telemetry columns found in '{file_name}'."
            )

        numeric_df = pd.DataFrame(numeric_cols)
        missing_before = int(numeric_df.isna().sum().sum())
        numeric_df = numeric_df.ffill().bfill().fillna(0.0)

        # 3. Statistical Summary & Univariate Robust Anomaly Detection
        anomalies: List[Dict[str, Any]] = []
        metric_stats: Dict[str, Any] = {}
        anomalous_row_indices = set()

        for col in numeric_df.columns:
            series = numeric_df[col].astype(float)
            mean_val = float(series.mean())
            raw_std = float(series.std())
            std_val = raw_std if raw_std > 1e-6 else 0.0
            median_val = float(series.median())
            mad = float(np.median(np.abs(series - median_val)))
            p95_val = float(series.quantile(0.95))
            max_val = float(series.max())
            min_val = float(series.min())

            metric_stats[col] = {
                "mean": round(mean_val, 2),
                "std": round(std_val, 2),
                "median": round(median_val, 2),
                "p95": round(p95_val, 2),
                "max": round(max_val, 2),
                "min": round(min_val, 2),
            }

            for idx, val in enumerate(series):
                z_score = abs(val - mean_val) / std_val if std_val > 1e-6 else 0.0
                mad_z = (0.6745 * abs(val - median_val) / mad) if mad > 1e-6 else 0.0

                # Absolute saturation only for utilization percentage metrics (0-100 scale)
                is_utilization = any(k in col.lower() for k in ["cpu", "utilization", "util_pct", "mem_pct"])
                is_saturation = is_utilization and val > 85.0 and max_val <= 105.0

                # Trigger only on genuine statistical departure or clear utilization saturation
                is_stat_anomaly = z_score >= 2.5 or (mad_z >= 3.5 and abs(val - median_val) > max(1e-3, abs(median_val) * 0.15))
                if is_stat_anomaly or is_saturation:
                    effective_z = max(z_score, mad_z)
                    severity = (
                        "Critical" if (effective_z >= 3.5 or (is_saturation and val > 95.0))
                        else "High" if (effective_z >= 2.8 or is_saturation)
                        else "Medium"
                    )
                    anomaly_score = min(1.0, round(float(max(effective_z / 5.0, 0.55 if is_saturation else 0.0)), 3))
                    anomalies.append({
                        "timestamp": timestamps[idx],
                        "metric_name": col,
                        "observed_value": round(float(val), 2),
                        "baseline_mean": round(mean_val, 2),
                        "baseline_std": round(std_val, 2),
                        "anomaly_score": anomaly_score,
                        "severity": severity,
                        "detection_method": "Dynamic Statistical Z-Score / MAD / Saturation Bounds",
                    })
                    anomalous_row_indices.add(idx)

        # 4. Multivariate Isolation Forest (only with sufficient rows, dimensions, and real variance)
        non_const_cols = [c for c in numeric_df.columns if metric_stats[c]["std"] > 1e-6]
        if len(numeric_df) >= 10 and len(non_const_cols) >= 2:
            try:
                sub_df = numeric_df[non_const_cols]
                contamination = min(0.15, max(0.03, 4.0 / len(sub_df)))
                iso_forest = IsolationForest(
                    n_estimators=100,
                    contamination=contamination,
                    random_state=42,
                )
                preds = iso_forest.fit_predict(sub_df)
                scores = iso_forest.decision_function(sub_df)

                for idx, (pred, score) in enumerate(zip(preds, scores)):
                    if pred != -1:
                        continue
                    deviations = {
                        c: abs(float(sub_df[c].iloc[idx]) - metric_stats[c]["mean"]) / metric_stats[c]["std"]
                        for c in non_const_cols
                    }
                    top_col = max(deviations, key=deviations.get)
                    top_z = deviations[top_col]

                    # Guard against forced contamination false positives on normal Gaussian/steady data:
                    # Require meaningful statistical deviation alongside Isolation Forest outlier flag.
                    if top_z < 2.2:
                        continue

                    existing = any(
                        a["timestamp"] == timestamps[idx] and a["metric_name"] == top_col
                        for a in anomalies
                    )
                    if not existing:
                        anomalies.append({
                            "timestamp": timestamps[idx],
                            "metric_name": f"{top_col} (Multivariate Outlier)",
                            "observed_value": round(float(sub_df[top_col].iloc[idx]), 2),
                            "baseline_mean": metric_stats[top_col]["mean"],
                            "baseline_std": metric_stats[top_col]["std"],
                            "anomaly_score": round(float(max(0.0, min(1.0, 1.0 - (score + 0.5)))), 3),
                            "severity": "High" if top_z >= 2.8 else "Medium",
                            "detection_method": "Multivariate Isolation Forest",
                        })
                        anomalous_row_indices.add(idx)
            except Exception:
                pass

        anomalies.sort(key=lambda x: (x["timestamp"], x["metric_name"]))

        # 5. Extract Contiguous Anomalous Intervals
        anomalous_intervals = self._extract_intervals(anomalies, timestamps)

        # 6. Build Chart-Ready Time Series (downsampled to max 120 points preserving all anomalous rows)
        time_series = self._build_chart_series(numeric_df, timestamps, anomalous_row_indices)

        data_quality = {
            "rows_analyzed": len(numeric_df),
            "timestamp_status": timestamp_status,
            "out_of_order_sorted": out_of_order,
            "duplicate_timestamps_merged": duplicate_timestamps,
            "missing_values_imputed": missing_before,
        }

        return {
            "valid": True,
            "validation_error": None,
            "anomalies": anomalies,
            "anomalous_intervals": anomalous_intervals,
            "time_series": time_series,
            "summary": (
                f"Analyzed {len(numeric_df)} telemetry observations across {len(numeric_df.columns)} metric(s). "
                f"Detected {len(anomalies)} anomalous observation(s) across {len(anomalous_intervals)} interval(s)."
            ),
            "total_points": len(numeric_df),
            "anomaly_count": len(anomalies),
            "metrics_analyzed": list(numeric_df.columns),
            "metric_statistics": metric_stats,
            "data_quality": data_quality,
            "time_range": {
                "start": timestamps[0] if timestamps else "",
                "end": timestamps[-1] if timestamps else "",
            },
        }

    def _invalid_result(self, error_msg: str) -> Dict[str, Any]:
        return {
            "valid": False,
            "validation_error": error_msg,
            "anomalies": [],
            "anomalous_intervals": [],
            "time_series": [],
            "summary": error_msg,
            "total_points": 0,
            "anomaly_count": 0,
            "metrics_analyzed": [],
            "metric_statistics": {},
            "data_quality": {},
            "time_range": {},
        }

    def _extract_intervals(self, anomalies: List[Dict[str, Any]], timestamps: List[str]) -> List[Dict[str, Any]]:
        if not anomalies:
            return []
        ts_to_idx = {ts: i for i, ts in enumerate(timestamps)}
        by_metric: Dict[str, List[Dict[str, Any]]] = {}
        for a in anomalies:
            base = a["metric_name"].split(" (")[0]
            by_metric.setdefault(base, []).append(a)

        intervals: List[Dict[str, Any]] = []
        for metric, items in by_metric.items():
            items.sort(key=lambda x: ts_to_idx.get(x["timestamp"], 0))
            curr_start = items[0]["timestamp"]
            curr_end = items[0]["timestamp"]
            curr_last_idx = ts_to_idx.get(curr_start, 0)
            curr_peak = items[0]["observed_value"]
            curr_count = 1

            for item in items[1:]:
                idx = ts_to_idx.get(item["timestamp"], curr_last_idx + 2)
                if idx <= curr_last_idx + 1:
                    curr_end = item["timestamp"]
                    curr_last_idx = idx
                    curr_peak = max(curr_peak, item["observed_value"])
                    curr_count += 1
                else:
                    intervals.append({
                        "metric_name": metric,
                        "start": curr_start,
                        "end": curr_end,
                        "count": curr_count,
                        "peak_value": curr_peak,
                    })
                    curr_start = item["timestamp"]
                    curr_end = item["timestamp"]
                    curr_last_idx = idx
                    curr_peak = item["observed_value"]
                    curr_count = 1

            intervals.append({
                "metric_name": metric,
                "start": curr_start,
                "end": curr_end,
                "count": curr_count,
                "peak_value": curr_peak,
            })
        return intervals

    def _build_chart_series(
        self,
        numeric_df: pd.DataFrame,
        timestamps: List[str],
        anomalous_indices: set,
        max_points: int = 120,
    ) -> List[Dict[str, Any]]:
        n = len(numeric_df)
        if n <= max_points:
            indices = list(range(n))
        else:
            step = max(1, n // max_points)
            indices = sorted(set(range(0, n, step)) | anomalous_indices)

        series_out: List[Dict[str, Any]] = []
        cols = list(numeric_df.columns)[:5]  # Up to 5 metrics for clean charting
        for i in indices:
            point: Dict[str, Any] = {
                "timestamp": timestamps[i],
                "is_anomaly": i in anomalous_indices,
            }
            for c in cols:
                point[c] = round(float(numeric_df[c].iloc[i]), 2)
            series_out.append(point)
        return series_out

    def _load_dataframe(self, content_str: str, file_name: str) -> pd.DataFrame:
        clean = content_str.strip()
        if clean.startswith("[") or clean.startswith("{"):
            try:
                data = json.loads(clean)
                if isinstance(data, dict):
                    for _, v in data.items():
                        if isinstance(v, list) and v and isinstance(v[0], dict):
                            return pd.DataFrame(v)
                    return pd.DataFrame([data])
                elif isinstance(data, list) and data and isinstance(data[0], dict):
                    return pd.DataFrame(data)
            except Exception:
                return pd.DataFrame()

        try:
            df = pd.read_csv(io.StringIO(content_str))
            return df
        except Exception:
            return pd.DataFrame()

    def _find_timestamp_col(self, df: pd.DataFrame) -> Optional[str]:
        candidates = ["timestamp", "time", "datetime", "date", "ts", "created_at", "@timestamp"]
        for col in df.columns:
            if str(col).lower() in candidates:
                return col
        first_col = df.columns[0]
        if pd.api.types.is_numeric_dtype(df[first_col]):
            return None
        try:
            parsed = pd.to_datetime(df[first_col].iloc[:5], errors="coerce", format="mixed")
            if parsed.notnull().all():
                return first_col
        except Exception:
            return None
        return None

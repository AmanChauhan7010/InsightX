"""
Tests for Anomaly Detector
"""

import unittest
from insightx.data_generator import generate_telemetry_dataset
from insightx.anomaly_detector import MultiTierAnomalyDetector

class TestAnomalyDetector(unittest.TestCase):
    def test_anomaly_detection_cpu_spike(self):
        pkg = generate_telemetry_dataset("cpu_pipeline_delay", duration_minutes=60, interval_seconds=30)
        detector = MultiTierAnomalyDetector()
        res = detector.fit_predict(pkg["metrics_df"], pkg["logs_df"])
        
        summary = res["summary"]
        self.assertGreater(summary["anomaly_points_detected"], 0)
        self.assertIn(summary["primary_severity"], ["High", "Medium"])
        self.assertIn("cpu_usage_pct", summary["primary_metric"])
        self.assertGreater(summary["peak_anomaly_score"], 0.4)

    def test_anomaly_detection_normal_baseline(self):
        pkg = generate_telemetry_dataset("normal", duration_minutes=60, interval_seconds=30)
        detector = MultiTierAnomalyDetector()
        res = detector.fit_predict(pkg["metrics_df"], pkg["logs_df"])
        summary = res["summary"]
        self.assertEqual(summary["high_severity_count"], 0)

if __name__ == "__main__":
    unittest.main()

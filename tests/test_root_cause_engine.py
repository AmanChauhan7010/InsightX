"""
Tests for Root Cause Analysis (RCA) Engine
"""

import unittest
from insightx.data_generator import generate_telemetry_dataset
from insightx.anomaly_detector import MultiTierAnomalyDetector
from insightx.root_cause_engine import RootCauseEngine

class TestRootCauseEngine(unittest.TestCase):
    def test_rca_pipeline_delay(self):
        pkg = generate_telemetry_dataset("cpu_pipeline_delay")
        detector = MultiTierAnomalyDetector()
        det = detector.fit_predict(pkg["metrics_df"], pkg["logs_df"])
        
        rca = RootCauseEngine()
        rca_res = rca.diagnose(det["result_df"], det["summary"], pkg["logs_df"])
        
        top = rca_res["top_cause"]
        self.assertIn("Data pipeline delay", top["cause"])
        self.assertGreater(top["confidence_pct"], 45.0)
        self.assertEqual(rca_res["root_service"], "data-pipeline")
        self.assertGreater(len(rca_res["blast_radius_services"]), 0)

    def test_rca_memory_leak(self):
        pkg = generate_telemetry_dataset("memory_leak_crash")
        detector = MultiTierAnomalyDetector()
        det = detector.fit_predict(pkg["metrics_df"], pkg["logs_df"])
        
        rca = RootCauseEngine()
        rca_res = rca.diagnose(det["result_df"], det["summary"], pkg["logs_df"])
        
        top = rca_res["top_cause"]
        self.assertIn("Memory leak", top["cause"])

    def test_rca_nominal_operation(self):
        pkg = generate_telemetry_dataset("normal")
        detector = MultiTierAnomalyDetector()
        det = detector.fit_predict(pkg["metrics_df"], pkg["logs_df"])
        
        rca = RootCauseEngine()
        rca_res = rca.diagnose(det["result_df"], det["summary"], pkg["logs_df"])
        
        top = rca_res["top_cause"]
        self.assertIn("Nominal", top["cause"])
        self.assertEqual(rca_res["root_service"], "None (System Healthy)")
        self.assertEqual(len(rca_res["blast_radius_services"]), 0)

if __name__ == "__main__":
    unittest.main()

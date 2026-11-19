"""
End-to-End Pipeline Integration Test
"""

import unittest
from insightx.data_generator import generate_telemetry_dataset
from insightx.anomaly_detector import MultiTierAnomalyDetector
from insightx.root_cause_engine import RootCauseEngine
from insightx.recommendation_engine import ActionRecommendationEngine
from insightx.explanation_engine import ExplanationEngine
from insightx.simulator import RemediationSimulator

class TestEndToEndPipeline(unittest.TestCase):
    def test_full_e2e_pipeline(self):
        # 1. Ingest Data
        pkg = generate_telemetry_dataset("cpu_pipeline_delay")
        
        # 2. Detect Anomalies
        detector = MultiTierAnomalyDetector()
        det_res = detector.fit_predict(pkg["metrics_df"], pkg["logs_df"])
        summary = det_res["summary"]
        self.assertGreater(summary["anomaly_points_detected"], 0)
        
        # 3. Diagnose Root Cause
        rca = RootCauseEngine()
        rca_res = rca.diagnose(det_res["result_df"], summary, pkg["logs_df"])
        self.assertIn("Data pipeline delay", rca_res["top_cause"]["cause"])
        
        # 4. Recommend Actions
        rec = ActionRecommendationEngine()
        rec_res = rec.recommend(rca_res["top_cause"], summary)
        self.assertEqual(rec_res["top_recommendation"]["action"], "Restart data pipeline")
        self.assertEqual(rec_res["top_recommendation"]["impact"], "High Impact")
        
        # 5. Explain Decision
        exp = ExplanationEngine()
        exp_res = exp.explain(summary, rca_res, rec_res, "cpu_pipeline_delay")
        self.assertIn("data pipeline", exp_res["top_explanation"].lower())
        self.assertGreaterEqual(len(exp_res["supporting_evidence"]), 3)
        
        # 6. Simulate Remediation
        sim = RemediationSimulator()
        recovery = sim.simulate_recovery(det_res["result_df"], rec_res["top_recommendation"]["action"], summary)
        self.assertEqual(recovery["status"], "HEALTHY")
        self.assertLess(recovery["combined_df"].iloc[-1]["cpu_usage_pct"], 50.0)

if __name__ == "__main__":
    unittest.main()

"""
Tests for Data Generator and Telemetry Synthesis
"""

import unittest
import pandas as pd
from insightx.data_generator import (
    generate_telemetry_dataset,
    get_historical_incident_knowledge_base,
    get_standard_runbooks
)

class TestDataGenerator(unittest.TestCase):
    def test_generate_telemetry_cpu_delay(self):
        pkg = generate_telemetry_dataset("cpu_pipeline_delay", duration_minutes=60, interval_seconds=30)
        self.assertIn("metrics_df", pkg)
        self.assertIn("logs_df", pkg)
        self.assertIn("events_df", pkg)
        df = pkg["metrics_df"]
        self.assertEqual(len(df), 120)
        self.assertIn("cpu_usage_pct", df.columns)
        self.assertIn("queue_length", df.columns)
        self.assertGreater(df["cpu_usage_pct"].max(), 80.0)
        self.assertGreater(df["queue_length"].max(), 1000)

    def test_generate_telemetry_memory_leak(self):
        pkg = generate_telemetry_dataset("memory_leak_crash", duration_minutes=60, interval_seconds=30)
        df = pkg["metrics_df"]
        self.assertGreater(df["memory_usage_pct"].max(), 85.0)
        self.assertEqual(pkg["primary_metric"], "memory_usage_pct")

    def test_knowledge_base(self):
        kb = get_historical_incident_knowledge_base()
        self.assertGreaterEqual(len(kb), 4)
        for inc in kb:
            self.assertIn("id", inc)
            self.assertIn("root_cause", inc)
            self.assertIn("recommended_actions", inc)

    def test_standard_runbooks(self):
        rb = get_standard_runbooks()
        self.assertIn("Restart data pipeline", rb)
        self.assertIn("command", rb["Restart data pipeline"])
        self.assertIn("steps", rb["Restart data pipeline"])

if __name__ == "__main__":
    unittest.main()

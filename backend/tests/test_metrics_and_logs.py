import pytest
from backend.app.analyzers.metrics.anomaly_analyzer import MetricAnomalyAnalyzer
from backend.app.analyzers.logs.log_analyzer import LogAnalyzer

def test_metrics_anomaly_detection():
    analyzer = MetricAnomalyAnalyzer()
    csv_data = "timestamp,cpu,latency,memory\n"
    for i in range(25):
        if 10 <= i <= 15:
            csv_data += f"2026-11-15T10:{i:02d}:00,99.5,4500.0,2048.0\n"
        else:
            csv_data += f"2026-11-15T10:{i:02d}:00,20.0,50.0,512.0\n"

    res = analyzer.analyze(csv_data, file_name="metrics.csv")
    assert res["total_points"] == 25
    assert res["anomaly_count"] > 0
    assert len(res["anomalies"]) > 0
    assert any(m in a["metric_name"].lower() for a in res["anomalies"] for m in ["cpu", "latency", "memory"])

def test_log_analyzer_stack_traces():
    analyzer = LogAnalyzer()
    log_text = (
        "2026-11-15 14:00:01 INFO Server starting\n"
        "2026-11-15 14:00:10 WARN High memory usage\n"
        "2026-11-15 14:00:15 ERROR Traceback (most recent call last):\n"
        '  File "service/processor.py", line 42, in process_batch\n'
        "    result = 100 / divisor\n"
        "ZeroDivisionError: division by zero\n"
    )
    res = analyzer.analyze(log_text, file_name="test.log")
    assert len(res["stack_traces"]) == 1
    st = res["stack_traces"][0]
    assert st["exception_type"] == "ZeroDivisionError"
    assert st["file_path"] == "service/processor.py"
    assert st["line_number"] == 42
    assert res["counts"]["CRITICAL"] >= 1

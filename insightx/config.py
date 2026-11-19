"""
InsightX Configuration and Domain Schema
Defines service topologies, metric definitions, incident presets, and model hyperparameters.
"""

from dataclasses import dataclass, field
from typing import List, Dict, Any

# Platform Metadata
PLATFORM_NAME = "InsightX"
TAGLINE = "From Alerts to Answers — AI Root Cause & Decision Intelligence Platform"
PROJECT_INFO = "DA-IICT | MSc Data Science | Group Innovation Project"
AUTHORS = ["Aman Chauhan (202518004)", "Mannan Agarwal (202518013)"]

# Microservice Topology for Root Cause Blast-Radius Analysis
SERVICE_TOPOLOGY = {
    "ingress-gateway": ["auth-service", "order-api"],
    "auth-service": ["redis-cache", "postgres-db"],
    "order-api": ["data-pipeline", "postgres-db", "payment-gateway"],
    "data-pipeline": ["postgres-db", "redis-cache"],
    "payment-gateway": [],
    "postgres-db": [],
    "redis-cache": []
}

# Monitored Telemetry Metrics
METRIC_DEFINITIONS = {
    "cpu_usage_pct": {
        "name": "CPU Usage",
        "unit": "%",
        "warning_threshold": 75.0,
        "critical_threshold": 90.0,
        "description": "Total processor utilization across cluster cores"
    },
    "memory_usage_pct": {
        "name": "Memory Usage",
        "unit": "%",
        "warning_threshold": 80.0,
        "critical_threshold": 92.0,
        "description": "RAM consumption across active workloads"
    },
    "queue_length": {
        "name": "Processing Queue Length",
        "unit": "msgs",
        "warning_threshold": 1200,
        "critical_threshold": 3000,
        "description": "Backlog of pending jobs in data pipeline queue"
    },
    "response_latency_ms": {
        "name": "P95 Response Latency",
        "unit": "ms",
        "warning_threshold": 250.0,
        "critical_threshold": 600.0,
        "description": "95th percentile service response duration"
    },
    "error_rate_pct": {
        "name": "HTTP 5xx Error Rate",
        "unit": "%",
        "warning_threshold": 2.5,
        "critical_threshold": 6.0,
        "description": "Percentage of failed client requests"
    },
    "db_connections_active": {
        "name": "DB Active Connections",
        "unit": "conns",
        "warning_threshold": 80,
        "critical_threshold": 95,
        "description": "PostgreSQL connection pool saturation level"
    },
    "network_traffic_mbps": {
        "name": "Network Throughput",
        "unit": "MB/s",
        "warning_threshold": 75.0,
        "critical_threshold": 110.0,
        "description": "Inbound and outbound network bandwidth"
    },
    "disk_io_iops": {
        "name": "Disk I/O Operations",
        "unit": "IOPS",
        "warning_threshold": 1500,
        "critical_threshold": 2400,
        "description": "Read/Write input-output operations per second"
    }
}

# Incident Presets
INCIDENT_PRESETS = {
    "cpu_pipeline_delay": {
        "title": "CPU Spike via Data Pipeline Worker Delay",
        "summary": "Sudden spike in CPU utilization caused by queue build-up and retry storm in processing service.",
        "primary_metric": "cpu_usage_pct",
        "secondary_metrics": ["queue_length", "response_latency_ms"],
        "anomaly_time_str": "16:23:00",
        "ground_truth_root_cause": "Data pipeline delay",
        "ground_truth_actions": ["Restart data pipeline", "Scale server resources", "Optimize query", "Check memory usage"]
    },
    "memory_leak_crash": {
        "title": "Progressive Memory Leak in Cache Worker",
        "summary": "Monotonic uncollected memory allocation leading to garbage collection pauses and OOM kill risk.",
        "primary_metric": "memory_usage_pct",
        "secondary_metrics": ["response_latency_ms", "error_rate_pct"],
        "anomaly_time_str": "14:15:00",
        "ground_truth_root_cause": "Memory leak in cache worker",
        "ground_truth_actions": ["Graceful pod restart", "Flush cache & collect heap dump", "Increase container memory limit", "Rollback recent release"]
    },
    "db_pool_exhaustion": {
        "title": "Database Connection Pool Saturation & Lock Cascade",
        "summary": "Unindexed transaction holding table lock, driving DB pool exhaustion and API timeouts.",
        "primary_metric": "db_connections_active",
        "secondary_metrics": ["response_latency_ms", "error_rate_pct", "cpu_usage_pct"],
        "anomaly_time_str": "11:40:00",
        "ground_truth_root_cause": "DB connection pool exhaustion / Lock contention",
        "ground_truth_actions": ["Kill slow locking transaction", "Increase DB connection pool size", "Add database read-replica", "Enable query circuit breaker"]
    },
    "external_api_timeout": {
        "title": "Downstream Payment API Outage & Latency Ripple",
        "summary": "Third-party payment gateway latency degradations cascading upstream into thread pool exhaustion.",
        "primary_metric": "response_latency_ms",
        "secondary_metrics": ["error_rate_pct", "queue_length"],
        "anomaly_time_str": "09:30:00",
        "ground_truth_root_cause": "External API latency & timeout",
        "ground_truth_actions": ["Enable circuit breaker for payment API", "Reroute to secondary payment provider", "Increase client timeout buffer", "Queue requests in background buffer"]
    },
    "normal_baseline": {
        "title": "Normal Baseline Operation",
        "summary": "Nominal system operation across all microservices with no anomalies, healthy telemetry, and stable baseline performance.",
        "primary_metric": "cpu_usage_pct",
        "secondary_metrics": ["memory_usage_pct", "response_latency_ms"],
        "anomaly_time_str": "N/A",
        "ground_truth_root_cause": "None — Nominal Operation",
        "ground_truth_actions": ["Continue routine telemetry monitoring", "Maintain automated alerting thresholds", "Verify backup schedules"]
    }
}

# Canonical Proposal Scenario Definition (DA-IICT MSc Data Science Proposal Slides 3 & 6)
PROPOSAL_DATA_PIPELINE_EXAMPLE = {
    "title": "Proposal Example: Data Pipeline Delay & Worker Crash",
    "service": "data-pipeline",
    "filename": "data_pipeline_worker.py",
    "language": "Python",
    "scenario_key": "cpu_pipeline_delay",
    "description": "Worker queue ingestion blockage causing thread backlog, CPU saturation, and ZeroDivisionError crash on empty retry batch (as presented in Innovation Proposal Slides 3 & 6).",
    "code": '''import time
import queue

task_queue = queue.Queue(maxsize=5000)
retry_history = []

def process_pipeline_batch(batch_id, records, audit_log=[]):
    """
    Data Pipeline Ingestion & Transformation Worker
    Incident: Queue backlog, worker delay & ZeroDivisionError crash
    """
    # Defect 1: Arithmetic crash if batch has 0 records
    batch_throughput = 1000 / len(records)
    
    # Defect 2: Mutable default argument persists state across invocations
    audit_log.append(batch_id)
    
    # Defect 3: Unbounded retry tracking causing progressive memory growth
    retry_history.append({"batch": batch_id, "size": len(records)})
    
    # Simulates worker delay causing queue backlog and CPU retry storm
    time.sleep(0.5)
    
    return {"status": "success", "batch_id": batch_id, "throughput": batch_throughput}

if __name__ == "__main__":
    process_pipeline_batch("batch_901", [])
''',
    "trace": '''Traceback (most recent call last):
  File "data_pipeline_worker.py", line 25, in <module>
    process_pipeline_batch("batch_901", [])
  File "data_pipeline_worker.py", line 14, in process_pipeline_batch
    batch_throughput = 1000 / len(records)
ZeroDivisionError: division by zero'''
}


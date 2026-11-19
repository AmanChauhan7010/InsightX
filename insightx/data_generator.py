"""
InsightX Telemetry & Incident Data Generator
Generates realistic multi-tier system metrics, structured application logs,
runtime events, and a rich historical incident knowledge base.
"""

import numpy as np
import pandas as pd
from datetime import datetime, timedelta
import random
from typing import Dict, Any, List, Tuple

from insightx.config import METRIC_DEFINITIONS, SERVICE_TOPOLOGY

def generate_telemetry_dataset(
    scenario: str = "cpu_pipeline_delay",
    duration_minutes: int = 120,
    interval_seconds: int = 30,
    random_seed: int = 42
) -> Dict[str, Any]:
    """
    Generates a realistic multi-tier microservice telemetry dataset for a chosen scenario.
    Includes time-series metrics, application logs, system alerts, and ground truth metadata.
    """
    np.random.seed(random_seed)
    random.seed(random_seed)

    total_points = (duration_minutes * 60) // interval_seconds
    start_time = datetime(2026, 10, 28, 15, 0, 0)
    timestamps = [start_time + timedelta(seconds=i * interval_seconds) for i in range(total_points)]

    # Anomaly window: happens roughly at 60% into the timeline (e.g. ~16:23 for 15:00 start)
    anomaly_start_idx = int(total_points * 0.58)
    anomaly_peak_idx = int(total_points * 0.68)
    anomaly_end_idx = int(total_points * 0.85)

    # Base normal telemetry
    t = np.linspace(0, 4 * np.pi, total_points)
    
    # 1. CPU Usage (%)
    base_cpu = 38.0 + 8.0 * np.sin(t) + np.random.normal(0, 2.5, total_points)
    
    # 2. Memory Usage (%)
    base_mem = 48.0 + 4.0 * np.cos(t * 0.5) + np.random.normal(0, 1.2, total_points)
    
    # 3. Queue Length
    base_queue = 150 + 40 * np.sin(t * 1.5) + np.random.normal(0, 15, total_points)
    
    # 4. Response Latency (ms)
    base_latency = 85.0 + 12.0 * np.sin(t) + np.random.normal(0, 6.0, total_points)
    
    # 5. Error Rate (%)
    base_error = np.clip(0.3 + np.random.exponential(0.2, total_points), 0.05, 1.5)
    
    # 6. DB Connections
    base_db_conn = 28 + 5 * np.cos(t) + np.random.normal(0, 2, total_points)
    
    # 7. Network Traffic (MB/s)
    base_net = 35.0 + 10.0 * np.sin(t) + np.random.normal(0, 3.0, total_points)
    
    # 8. Disk I/O (IOPS)
    base_disk = 450 + 80 * np.cos(t) + np.random.normal(0, 25, total_points)

    logs: List[Dict[str, Any]] = []
    events: List[Dict[str, Any]] = []

    # Inject Scenario Dynamics
    if scenario == "cpu_pipeline_delay":
        # Signature: Data pipeline delay causes queue backlog, which triggers worker CPU spike & latency spike
        ramp = np.linspace(0, 1, anomaly_peak_idx - anomaly_start_idx)
        decay = np.linspace(1, 0, anomaly_end_idx - anomaly_peak_idx)
        envelope = np.concatenate([ramp, decay])

        # Queue builds up FIRST (Causal precursor)
        base_queue[anomaly_start_idx:anomaly_end_idx] += envelope * 3200
        # Worker CPU spikes to 94%+
        base_cpu[anomaly_start_idx:anomaly_end_idx] += envelope * 54.0
        # Latency ripples upward
        base_latency[anomaly_start_idx:anomaly_end_idx] += envelope * 480.0
        # Mild error rate increase
        base_error[anomaly_start_idx:anomaly_end_idx] += envelope * 4.2
        # Disk IOPS increase due to queuing
        base_disk[anomaly_start_idx:anomaly_end_idx] += envelope * 950

        scenario_name = "CPU Spike & Pipeline Queue Delay"
        primary_metric = "cpu_usage_pct"
        root_cause = "Data pipeline delay"
        description = "Delayed ingestion in data-pipeline worker caused queue build-up and a severe CPU spike."

    elif scenario == "memory_leak_crash":
        # Signature: Monotonically increasing memory usage leading to GC pauses
        leak_len = total_points - anomaly_start_idx
        leak_trend = np.linspace(0, 48.0, leak_len)
        base_mem[anomaly_start_idx:] += leak_trend
        # GC pauses cause latency surges near the end
        gc_impact = np.where(base_mem > 85.0, (base_mem - 85.0) * 15.0, 0.0)
        base_latency += gc_impact
        base_error += np.where(base_mem > 92.0, 5.5, 0.0)

        scenario_name = "Progressive Memory Leak in Worker"
        primary_metric = "memory_usage_pct"
        root_cause = "Memory leak in background processing service"
        description = "Continuous unreleased cache memory allocations causing impending OOM failure."

    elif scenario == "db_pool_exhaustion":
        # Signature: Active DB connections lock up to 100%, causing query wait queues & massive latency spike
        ramp = np.linspace(0, 1, anomaly_peak_idx - anomaly_start_idx)
        decay = np.linspace(1, 0, anomaly_end_idx - anomaly_peak_idx)
        envelope = np.concatenate([ramp, decay])

        base_db_conn[anomaly_start_idx:anomaly_end_idx] += envelope * 68
        base_latency[anomaly_start_idx:anomaly_end_idx] += envelope * 750.0
        base_error[anomaly_start_idx:anomaly_end_idx] += envelope * 8.5
        base_cpu[anomaly_start_idx:anomaly_end_idx] += envelope * 25.0

        scenario_name = "Database Connection Pool Saturation"
        primary_metric = "db_connections_active"
        root_cause = "DB connection pool exhaustion / Lock contention"
        description = "Long-running exclusive transaction lock holding connection pool slots, starving API workers."

    elif scenario == "external_api_timeout":
        # Signature: Latency explodes on payment-gateway, cascading error rate
        ramp = np.linspace(0, 1, anomaly_peak_idx - anomaly_start_idx)
        decay = np.linspace(1, 0, anomaly_end_idx - anomaly_peak_idx)
        envelope = np.concatenate([ramp, decay])

        base_latency[anomaly_start_idx:anomaly_end_idx] += envelope * 880.0
        base_error[anomaly_start_idx:anomaly_end_idx] += envelope * 12.0
        base_queue[anomaly_start_idx:anomaly_end_idx] += envelope * 1600

        scenario_name = "External API Latency Cascade"
        primary_metric = "response_latency_ms"
        root_cause = "External API latency & timeout"
        description = "Downstream 3rd party payment gateway latency degraded from 80ms to 2400ms causing request backpressure."

    else:
        # Default baseline with minor fluctuations
        scenario_name = "Normal Baseline Operation"
        primary_metric = "cpu_usage_pct"
        root_cause = "None"
        description = "System operating within standard operational parameters."

    # Ground truth anomaly mask based on actual anomalous deviation
    if scenario == "memory_leak_crash":
        anomaly_mask = (base_mem >= 75.0)
    elif scenario == "normal":
        anomaly_mask = np.zeros(total_points, dtype=bool)
    else:
        anomaly_mask = np.zeros(total_points, dtype=bool)
        anomaly_mask[anomaly_start_idx:anomaly_end_idx] = True

    # Clip values within valid physical bounds
    df = pd.DataFrame({
        "timestamp": timestamps,
        "cpu_usage_pct": np.clip(base_cpu, 2.0, 99.8).round(2),
        "memory_usage_pct": np.clip(base_mem, 10.0, 99.5).round(2),
        "queue_length": np.clip(base_queue, 0, 10000).astype(int),
        "response_latency_ms": np.clip(base_latency, 15.0, 3500.0).round(1),
        "error_rate_pct": np.clip(base_error, 0.0, 100.0).round(2),
        "db_connections_active": np.clip(base_db_conn, 2, 100).astype(int),
        "network_traffic_mbps": np.clip(base_net, 1.0, 250.0).round(2),
        "disk_io_iops": np.clip(base_disk, 50, 5000).astype(int),
        "is_ground_truth_anomaly": anomaly_mask
    })

    # Generate Synthetic System & Application Logs
    services = ["ingress-gateway", "auth-service", "order-api", "data-pipeline", "postgres-db", "redis-cache"]
    for idx, row in df.iterrows():
        ts = row["timestamp"]
        ts_str = ts.strftime("%Y-%m-%d %H:%M:%S")

        # Regular periodic operational logs
        if idx % 4 == 0:
            service = random.choice(services)
            logs.append({
                "timestamp": ts_str,
                "service": service,
                "level": "INFO",
                "message": f"Healthcheck OK: service {service} responsive, memory={row['memory_usage_pct']}%, cpu={row['cpu_usage_pct']}%",
                "trace_id": f"trc-{random.randint(100000, 999999)}"
            })

        # Inject diagnostic error/warning logs during anomaly window
        if row["is_ground_truth_anomaly"]:
            if scenario == "cpu_pipeline_delay":
                if idx % 2 == 0:
                    logs.append({
                        "timestamp": ts_str,
                        "service": "data-pipeline",
                        "level": "WARN" if row["queue_length"] < 2000 else "ERROR",
                        "message": f"Worker thread queue backpressure detected: queue_size={row['queue_length']} exceeded batch threshold (1200). Pipeline latency +380ms",
                        "trace_id": f"pipe-{random.randint(10000, 99999)}"
                    })
                if idx % 3 == 0:
                    logs.append({
                        "timestamp": ts_str,
                        "service": "order-api",
                        "level": "ERROR",
                        "message": f"Downstream queue delay: event publishing timed out waiting for data-pipeline ack after 450ms",
                        "trace_id": f"ord-{random.randint(10000, 99999)}"
                    })
            elif scenario == "memory_leak_crash":
                if idx % 2 == 0:
                    logs.append({
                        "timestamp": ts_str,
                        "service": "redis-cache",
                        "level": "WARN" if row["memory_usage_pct"] < 85 else "CRITICAL",
                        "message": f"JVM garbage collection pause exceeded 650ms: heap usage={row['memory_usage_pct']}%. Eviction buffer full.",
                        "trace_id": f"mem-{random.randint(10000, 99999)}"
                    })
            elif scenario == "db_pool_exhaustion":
                if idx % 2 == 0:
                    logs.append({
                        "timestamp": ts_str,
                        "service": "postgres-db",
                        "level": "ERROR",
                        "message": f"FATAL: remaining connection slots reserved for non-replication superuser connections. Pool={row['db_connections_active']}/100",
                        "trace_id": f"pg-{random.randint(10000, 99999)}"
                    })
            elif scenario == "external_api_timeout":
                if idx % 2 == 0:
                    logs.append({
                        "timestamp": ts_str,
                        "service": "order-api",
                        "level": "ERROR",
                        "message": f"HTTP Gateway Timeout: Payment provider endpoint /v2/charge failed to respond within 2000ms. Returning 504",
                        "trace_id": f"pay-{random.randint(10000, 99999)}"
                    })

    # Generate Alerts & System Events
    if scenario != "normal":
        anomaly_peak_time = timestamps[anomaly_peak_idx].strftime("%H:%M:%S")
        events.append({
            "timestamp": timestamps[anomaly_start_idx].strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": "THRESHOLD_WARNING",
            "metric": primary_metric,
            "message": f"Metric {primary_metric} crossed warning threshold ({METRIC_DEFINITIONS[primary_metric]['warning_threshold']})",
            "severity": "Medium"
        })
        events.append({
            "timestamp": timestamps[anomaly_peak_idx].strftime("%Y-%m-%d %H:%M:%S"),
            "event_type": "ANOMALY_TRIGGERED",
            "metric": primary_metric,
            "message": f"High severity anomaly detected in {primary_metric} at {anomaly_peak_time}",
            "severity": "High"
        })

    logs_df = pd.DataFrame(logs)
    events_df = pd.DataFrame(events)

    return {
        "scenario": scenario,
        "scenario_name": scenario_name,
        "primary_metric": primary_metric,
        "ground_truth_root_cause": root_cause,
        "description": description,
        "metrics_df": df,
        "logs_df": logs_df,
        "events_df": events_df,
        "anomaly_window": {
            "start": timestamps[anomaly_start_idx].strftime("%Y-%m-%d %H:%M:%S"),
            "peak": timestamps[anomaly_peak_idx].strftime("%Y-%m-%d %H:%M:%S"),
            "end": timestamps[anomaly_end_idx].strftime("%Y-%m-%d %H:%M:%S"),
            "peak_time_str": timestamps[anomaly_peak_idx].strftime("%H:%M")
        }
    }


def get_historical_incident_knowledge_base() -> List[Dict[str, Any]]:
    """
    Returns curated historical incidents database with known resolutions,
    matching Slide 4 & Slide 6 specifications.
    """
    return [
        {
            "id": "INC-2024-0512",
            "date": "2024-05-12",
            "title": "CPU surge on data-pipeline worker due to queue bottleneck",
            "symptom": "CPU usage spiked to 92% and queue length reached 3400 msgs",
            "root_cause": "Data pipeline delay",
            "resolution": "Restarted data pipeline worker pods and flushed stale consumer group lag. System stabilized in 4 mins.",
            "recommended_actions": [
                {"action": "Restart data pipeline", "impact": "High", "confidence": 0.94},
                {"action": "Scale server resources", "impact": "Medium", "confidence": 0.78},
                {"action": "Optimize query", "impact": "Medium", "confidence": 0.55},
                {"action": "Check memory usage", "impact": "Low", "confidence": 0.35}
            ],
            "mttr_minutes": 14,
            "category": "Pipeline Congestion"
        },
        {
            "id": "INC-2024-0603",
            "date": "2024-06-03",
            "title": "Batch ingestion backlog causing CPU saturation",
            "symptom": "Sustained CPU 89% and high queue latency after bulk data import",
            "root_cause": "Data pipeline delay",
            "resolution": "Restarted pipeline daemon with increased worker concurrency from 8 to 24 workers.",
            "recommended_actions": [
                {"action": "Restart data pipeline", "impact": "High", "confidence": 0.92},
                {"action": "Scale server resources", "impact": "High", "confidence": 0.85},
                {"action": "Optimize query", "impact": "Medium", "confidence": 0.50}
            ],
            "mttr_minutes": 18,
            "category": "Pipeline Congestion"
        },
        {
            "id": "INC-2024-0819",
            "date": "2024-08-19",
            "title": "Unbounded cache retention memory leak in API gateway",
            "symptom": "Memory usage monotonic climb from 45% to 96% with GC pause latency",
            "root_cause": "Memory leak in background processing service",
            "resolution": "Captured heap dump, performed rolling restart, and patched LRU cache eviction TTL.",
            "recommended_actions": [
                {"action": "Graceful pod restart", "impact": "High", "confidence": 0.95},
                {"action": "Flush cache & collect heap dump", "impact": "High", "confidence": 0.88},
                {"action": "Increase container memory limit", "impact": "Medium", "confidence": 0.60},
                {"action": "Rollback recent release", "impact": "Medium", "confidence": 0.52}
            ],
            "mttr_minutes": 22,
            "category": "Memory Exhaustion"
        },
        {
            "id": "INC-2024-1104",
            "date": "2024-11-04",
            "title": "PostgreSQL connection starvation via unindexed join query",
            "symptom": "Active DB connections pegged at 100/100, HTTP 500 error spike to 8.2%",
            "root_cause": "DB connection pool exhaustion / Lock contention",
            "resolution": "Identified and terminated PID holding table lock; added temporary index and raised pool max size.",
            "recommended_actions": [
                {"action": "Kill slow locking transaction", "impact": "High", "confidence": 0.96},
                {"action": "Increase DB connection pool size", "impact": "High", "confidence": 0.82},
                {"action": "Add database read-replica", "impact": "Medium", "confidence": 0.70},
                {"action": "Enable query circuit breaker", "impact": "Medium", "confidence": 0.65}
            ],
            "mttr_minutes": 11,
            "category": "Database Lock"
        },
        {
            "id": "INC-2025-0215",
            "date": "2025-02-15",
            "title": "Third-party payment gateway latency spike & timeout avalanche",
            "symptom": "P95 latency reached 2800ms and 504 gateway timeouts spiked across checkout",
            "root_cause": "External API latency & timeout",
            "resolution": "Activated fallback secondary payment gateway and engaged circuit breaker to fast-fail.",
            "recommended_actions": [
                {"action": "Enable circuit breaker for payment API", "impact": "High", "confidence": 0.95},
                {"action": "Reroute to secondary payment provider", "impact": "High", "confidence": 0.90},
                {"action": "Increase client timeout buffer", "impact": "Medium", "confidence": 0.60},
                {"action": "Queue requests in background buffer", "impact": "Medium", "confidence": 0.55}
            ],
            "mttr_minutes": 9,
            "category": "Dependency Failure"
        }
    ]


def get_standard_runbooks() -> Dict[str, Dict[str, Any]]:
    """
    Returns standard operational runbooks with executable shell commands,
    risk profiles, and recovery verification criteria.
    """
    return {
        "Restart data pipeline": {
            "id": "RBK-PIPE-001",
            "title": "Graceful Restart of Data Pipeline Workers",
            "estimated_recovery_sec": 45,
            "risk_level": "Low",
            "command": "kubectl rollout restart deployment/data-pipeline-worker -n production",
            "steps": [
                "1. Signal worker pods to stop accepting new dequeue tasks.",
                "2. Wait up to 15 seconds for active batch inflight items to commit.",
                "3. Terminate stalled worker containers and spin up healthy replacements.",
                "4. Verify queue dequeue rate resumes normal baseline (> 120 msgs/sec)."
            ],
            "expected_outcome": "CPU utilization drops back to normal baseline (30-45%) within 2 minutes."
        },
        "Scale server resources": {
            "id": "RBK-SCALE-002",
            "title": "Horizontal Scale-Out of Processing Nodes",
            "estimated_recovery_sec": 90,
            "risk_level": "Low",
            "command": "kubectl scale deployment/data-pipeline-worker --replicas=6 -n production",
            "steps": [
                "1. Provision 3 additional worker pods across available cluster nodes.",
                "2. Partition event queue partitions evenly among active consumers.",
                "3. Monitor cluster CPU aggregate load to ensure even distribution."
            ],
            "expected_outcome": "Immediate 50% reduction in per-node CPU load and queue backlog drain."
        },
        "Optimize query": {
            "id": "RBK-DB-003",
            "title": "Apply Query Plan Index & Flush Plan Cache",
            "estimated_recovery_sec": 120,
            "risk_level": "Medium",
            "command": "psql -d production_db -c 'REINDEX TABLE queue_messages; ANALYZE queue_messages;'",
            "steps": [
                "1. Check pg_stat_activity for queries with execution duration > 1000ms.",
                "2. Refresh table statistics to enable optimal index scan selection.",
                "3. Reset query planner cache."
            ],
            "expected_outcome": "Query latency drops below 25ms."
        },
        "Check memory usage": {
            "id": "RBK-MEM-004",
            "title": "Inspect Memory Profile & Garbage Collection Metrics",
            "estimated_recovery_sec": 30,
            "risk_level": "Low",
            "command": "jcmd 1 GC.heap_info && top -b -n 1 -p $(pgrep -f worker)",
            "steps": [
                "1. Review resident memory size (RSS) versus configured heap bounds.",
                "2. Inspect GC logs for stop-the-world pauses exceeding 200ms.",
                "3. Confirm off-heap buffers are within safety threshold."
            ],
            "expected_outcome": "Diagnostic verification of memory state."
        },
        "Graceful pod restart": {
            "id": "RBK-POD-005",
            "title": "Rolling Pod Restart for Memory Reclamation",
            "estimated_recovery_sec": 60,
            "risk_level": "Low",
            "command": "kubectl rollout restart deployment/redis-cache -n production",
            "steps": [
                "1. Trigger rolling restart of redis-cache pods.",
                "2. Validate session failover to replica.",
                "3. Monitor memory consumption drop from 95% down to 25%."
            ],
            "expected_outcome": "Memory reclaimed completely."
        },
        "Flush cache & collect heap dump": {
            "id": "RBK-MEM-006",
            "title": "Heap Dump Capture & Cache Flush",
            "estimated_recovery_sec": 180,
            "risk_level": "Medium",
            "command": "jcmd 1 GC.heap_dump /var/log/heap_dump.hprof && redis-cli flushdb async",
            "steps": [
                "1. Trigger asynchronous heap dump to S3 diagnostic bucket.",
                "2. Evict expired cache keys with asynchronous cleanup.",
                "3. Verify hit ratio recovers."
            ],
            "expected_outcome": "Heap dump saved for forensic analysis and cache reclaimed."
        },
        "Kill slow locking transaction": {
            "id": "RBK-DB-007",
            "title": "Terminate Stalled PostgreSQL Lock Holder",
            "estimated_recovery_sec": 15,
            "risk_level": "Medium",
            "command": "SELECT pg_terminate_backend(pid) FROM pg_stat_activity WHERE state != 'idle' AND age(clock_timestamp(), query_start) > interval '2 minutes';",
            "steps": [
                "1. Identify PID blocking access to table locks.",
                "2. Terminate hung backend query safely.",
                "3. Connection pool slots freed immediately."
            ],
            "expected_outcome": "Active DB connections plunge from 100 to under 30 within seconds."
        },
        "Enable circuit breaker for payment API": {
            "id": "RBK-CB-008",
            "title": "Engage Upstream Circuit Breaker",
            "estimated_recovery_sec": 10,
            "risk_level": "Low",
            "command": "curl -X POST http://api-gateway/admin/circuits/payment/trip",
            "steps": [
                "1. Force circuit breaker into OPEN state.",
                "2. Direct client checkouts to fallback queue or secondary provider.",
                "3. Prevent worker threads from blocking on unresponsive downstream."
            ],
            "expected_outcome": "API latency returns immediately to sub-100ms baseline."
        }
    }

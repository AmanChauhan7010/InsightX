"""
InsightX Recommendation Engine
Ranks corrective actions using historical incident case retrieval (RAG / similarity search),
engineering rule engines, and operational runbook mapping with expected impact ratings.
"""

from typing import Dict, Any, List, Optional
import numpy as np
from difflib import SequenceMatcher

from insightx.data_generator import get_historical_incident_knowledge_base, get_standard_runbooks

class ActionRecommendationEngine:
    """
    Ranks corrective actions with Impact level, confidence, and runbook instructions.
    """
    def __init__(self):
        self.knowledge_base = get_historical_incident_knowledge_base()
        self.runbooks = get_standard_runbooks()

        # Engineering Rule Registry
        self.domain_rules = [
            {
                "cause_pattern": "Data pipeline delay",
                "actions": [
                    {"action": "Restart data pipeline", "impact": "High Impact", "base_score": 0.94, "mttr_est": "3-5 mins"},
                    {"action": "Scale server resources", "impact": "Medium Impact", "base_score": 0.78, "mttr_est": "8-12 mins"},
                    {"action": "Optimize query", "impact": "Medium Impact", "base_score": 0.52, "mttr_est": "15-20 mins"},
                    {"action": "Check memory usage", "impact": "Low Impact", "base_score": 0.35, "mttr_est": "5 mins"}
                ],
                "rationale": "Restarting the pipeline worker flushes deadlocked consumer partitions and resets the message processing rate. Scaling adds worker throughput."
            },
            {
                "cause_pattern": "Memory leak",
                "actions": [
                    {"action": "Graceful pod restart", "impact": "High Impact", "base_score": 0.95, "mttr_est": "2-4 mins"},
                    {"action": "Flush cache & collect heap dump", "impact": "High Impact", "base_score": 0.88, "mttr_est": "5-8 mins"},
                    {"action": "Increase container memory limit", "impact": "Medium Impact", "base_score": 0.62, "mttr_est": "10 mins"},
                    {"action": "Rollback recent release", "impact": "Medium Impact", "base_score": 0.50, "mttr_est": "15 mins"}
                ],
                "rationale": "A graceful rolling restart releases uncollected heap allocations and prevents kernel OOM-killer termination."
            },
            {
                "cause_pattern": "DB connection",
                "actions": [
                    {"action": "Kill slow locking transaction", "impact": "High Impact", "base_score": 0.96, "mttr_est": "1-2 mins"},
                    {"action": "Increase DB connection pool size", "impact": "High Impact", "base_score": 0.82, "mttr_est": "5 mins"},
                    {"action": "Add database read-replica", "impact": "Medium Impact", "base_score": 0.70, "mttr_est": "20 mins"},
                    {"action": "Enable query circuit breaker", "impact": "Medium Impact", "base_score": 0.65, "mttr_est": "3 mins"}
                ],
                "rationale": "Killing the lock-holding transaction frees blocked worker connection slots instantly."
            },
            {
                "cause_pattern": "External API latency",
                "actions": [
                    {"action": "Enable circuit breaker for payment API", "impact": "High Impact", "base_score": 0.95, "mttr_est": "1 min"},
                    {"action": "Reroute to secondary payment provider", "impact": "High Impact", "base_score": 0.90, "mttr_est": "3-5 mins"},
                    {"action": "Increase client timeout buffer", "impact": "Medium Impact", "base_score": 0.60, "mttr_est": "5 mins"},
                    {"action": "Queue requests in background buffer", "impact": "Medium Impact", "base_score": 0.55, "mttr_est": "8 mins"}
                ],
                "rationale": "Engaging the circuit breaker prevents upstream worker thread starvation while downstream services recover."
            }
        ]

    def _string_similarity(self, a: str, b: str) -> float:
        return SequenceMatcher(None, a.lower(), b.lower()).ratio()

    def find_similar_past_incidents(self, root_cause: str, symptom_text: str, top_k: int = 2) -> List[Dict[str, Any]]:
        """
        Retrieves matching historical incidents from knowledge base.
        """
        scored_incidents = []
        for inc in self.knowledge_base:
            cause_sim = self._string_similarity(root_cause, inc["root_cause"])
            symp_sim = self._string_similarity(symptom_text, inc["symptom"])
            combined_score = 0.65 * cause_sim + 0.35 * symp_sim
            scored_incidents.append((inc, combined_score))

        scored_incidents.sort(key=lambda x: x[1], reverse=True)
        return [
            {
                **inc,
                "similarity_score": round(score, 3),
                "match_pct": round(score * 100, 1)
            }
            for inc, score in scored_incidents[:top_k]
        ]

    def recommend(
        self,
        top_root_cause: Dict[str, Any],
        detection_summary: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Synthesizes ranked corrective recommendations with runbook procedures and impact ratings.
        """
        cause_label = top_root_cause.get("cause", "")
        cause_conf = top_root_cause.get("confidence_score", 0.5)
        primary_metric = detection_summary.get("primary_metric_name", "System Metric")
        severity = detection_summary.get("primary_severity", "High")

        # 1. Match Domain Rules
        matched_rule = None
        for rule in self.domain_rules:
            if rule["cause_pattern"].lower() in cause_label.lower():
                matched_rule = rule
                break
        
        if not matched_rule:
            matched_rule = self.domain_rules[0]

        # 2. Retrieve Historical Incidents
        symptom_summary = f"{primary_metric} {severity} anomaly detected at {detection_summary.get('peak_timestamp', '')}"
        similar_incidents = self.find_similar_past_incidents(cause_label, symptom_summary)

        # 3. Compile and Rank Actions
        # Compile and Rank Actions with Operational Risk and Verification Steps
        if severity == "Normal" or "none" in cause_label.lower():
            nom_action = {
                "action": "Maintain Telemetry Monitoring & Baseline SLOs",
                "priority": "P4",
                "impact": "Nominal",
                "confidence_score": 1.0,
                "confidence_pct": 100.0,
                "mttr_estimate": "N/A",
                "reasoning": "All system telemetry metrics and error logs remain within nominal baseline operating limits.",
                "supporting_evidence": "Zero threshold saturation violations; stable EWMA baselines.",
                "operational_risk": "Zero risk. Passive monitoring maintains standard telemetry ingestion.",
                "verification_step": "Verify active Prometheus/OpenTelemetry scraping and alert channel health.",
                "runbook": {
                    "id": "RBK-NOM-001",
                    "title": "Standard Telemetry Observability",
                    "estimated_recovery_sec": 0,
                    "risk_level": "None",
                    "command": "kubectl get pods -A && curl -s http://localhost:8080/health",
                    "steps": ["1. Review telemetry metrics.", "2. Ensure alert thresholds remain active."],
                    "expected_outcome": "Continuous stable operation."
                }
            }
            return {
                "top_recommendation": nom_action,
                "ranked_actions": [nom_action],
                "domain_rationale": "System is operating within standard baseline bounds; no intervention required.",
                "similar_incidents": []
            }

        # Operational details by action name
        action_metadata = {
            "Restart data pipeline": {
                "risk": "Brief 5-10s message consumption pause during worker restart; mitigated by consumer group rebalance.",
                "verification": "Confirm Kafka/RabbitMQ queue backlog drops below 300 msgs and worker CPU drops below 50% within 3 minutes.",
                "evidence": f"Elevated {primary_metric} alongside queue build-up."
            },
            "Scale server resources": {
                "risk": "Additional cloud infrastructure cost; takes 2-4 minutes for node provisioning.",
                "verification": "Ensure newly scheduled replica pods achieve Ready status and CPU per-pod drops below 65%.",
                "evidence": "Sustained high compute load across all active worker instances."
            },
            "Optimize query": {
                "risk": "Requires code change and deployment pipeline approval; cannot be applied instantly.",
                "verification": "Check query explain plan and ensure index scan is utilized instead of sequential scan.",
                "evidence": "Database query duration exceeded P95 SLA target."
            },
            "Check memory usage": {
                "risk": "Diagnostic inspection only; does not directly remediate the issue.",
                "verification": "Inspect heap profile and GC pause durations in APM dashboard.",
                "evidence": "Memory metrics nearing allocation limits."
            },
            "Graceful pod restart": {
                "risk": "In-flight requests may receive HTTP 503 if termination grace period is under 15 seconds.",
                "verification": "Verify RSS memory drops from 95% to nominal 45% post-restart with 0 unhandled exceptions.",
                "evidence": "Monotonic uncollected memory accumulation."
            },
            "Flush cache & collect heap dump": {
                "risk": "Cache miss storm on primary database; pre-warm critical keys prior to general traffic.",
                "verification": "Inspect heap dump file in storage bucket and verify memory utilization normalizes.",
                "evidence": "Cache worker footprint monotonically increasing over time."
            },
            "Kill slow locking transaction": {
                "risk": "The terminated query will be rolled back; caller client will receive a transaction abort error.",
                "verification": "Run 'SELECT count(*) FROM pg_stat_activity WHERE state = \"active\"' to confirm pool availability > 70 slots.",
                "evidence": "Active database connection pool saturated at 95%+."
            },
            "Increase DB connection pool size": {
                "risk": "Increasing pool size without database memory tuning can trigger database server swap starvation.",
                "verification": "Verify connection pool metrics show available connections > 20 and wait queue drops to 0.",
                "evidence": "Worker requests queueing on database pool checkout."
            },
            "Enable circuit breaker for payment API": {
                "risk": "Users will receive graceful fallback messages or delayed payment processing.",
                "verification": "Confirm upstream API latency drops from 2400ms to < 100ms as circuit trips to open/half-open.",
                "evidence": "Downstream payment gateway latency degraded to > 2000ms."
            },
            "Reroute to secondary payment provider": {
                "risk": "May incur different gateway transaction fees or require currency reconciliation.",
                "verification": "Verify payment success rate rebounds above 99.2% on the secondary payment rail.",
                "evidence": "Primary payment provider timeout rate > 10%."
            }
        }

        ranked_actions = []
        for idx, item in enumerate(matched_rule["actions"], 1):
            act_name = item["action"]
            meta = action_metadata.get(act_name, {
                "risk": "Standard operational risk; follow deployment safety guardrails.",
                "verification": "Confirm target telemetry metrics return to baseline within 5 minutes.",
                "evidence": f"Correlated with anomalous {primary_metric} behavior."
            })
            runbook_info = self.runbooks.get(act_name, {
                "id": f"RBK-{idx:03d}",
                "title": f"Execute {act_name}",
                "estimated_recovery_sec": 60,
                "risk_level": "Low",
                "command": f"# Execute standard remediation for {act_name}",
                "steps": [f"1. Run diagnostic check on {act_name}.", "2. Apply configuration update.", "3. Verify metrics normalize."],
                "expected_outcome": "Metrics return to baseline."
            })

            calibrated_score = round(item["base_score"] * (0.8 + 0.2 * cause_conf), 3)

            ranked_actions.append({
                "action": act_name,
                "priority": f"P{min(idx, 4)}",
                "impact": item["impact"],
                "confidence_score": calibrated_score,
                "confidence_pct": round(calibrated_score * 100, 1),
                "mttr_estimate": item["mttr_est"],
                "reasoning": f"Addresses {cause_label} by resolving the primary operational bottleneck and freeing starved resources.",
                "supporting_evidence": meta["evidence"],
                "operational_risk": meta["risk"],
                "verification_step": meta["verification"],
                "runbook": runbook_info
            })

        # Sort descending by confidence score
        ranked_actions.sort(key=lambda x: x["confidence_score"], reverse=True)

        return {
            "top_recommendation": ranked_actions[0],
            "ranked_actions": ranked_actions,
            "domain_rationale": matched_rule["rationale"],
            "similar_incidents": similar_incidents
        }


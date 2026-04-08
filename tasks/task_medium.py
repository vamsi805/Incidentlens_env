"""
Task 2: Cascading Database Failure (Medium)

Scenario: Database connection pool exhaustion causes a cascade.
1. db-primary connection pool fills up due to slow queries
2. Services start timing out on DB connections
3. order-service and payment-service start failing
4. api-gateway sees elevated 5xx rates
5. queue-worker backs up because jobs can't write to DB

The agent must trace the cascade back to the DB connection pool as root cause,
not get distracted by the downstream symptoms.
"""

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from incidentlens_env.tasks.log_generator import generate_baseline_logs

TASK_ID = "cascading_db_failure"
TASK_NAME = "Cascading Database Failure"
TASK_DIFFICULTY = "medium"
TASK_DESCRIPTION = (
    "ALERT: Elevated 5xx error rate across multiple services. "
    "order-service, payment-service, and queue-worker all reporting failures. "
    "api-gateway latency p99 spiked to 15s. Investigate and identify the root cause."
)

GROUND_TRUTH = {
    "root_cause": "connection_pool_exhaustion",  # db connection pool
    "affected_service": "db-primary",
    "severity": "critical",
    "incident_start_offset_minutes": 20,
}


def generate(seed: int = 42) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    rng = random.Random(seed)
    start_time = datetime(2025, 3, 15, 9, 0, 0)

    # Phase 1: Normal (0-15 min)
    normal = generate_baseline_logs(rng, start_time, duration_minutes=15, logs_per_minute=12)

    # Phase 2: Slow query starts (15-20 min) — the actual root cause
    phase2_start = start_time + timedelta(minutes=15)
    phase2 = generate_baseline_logs(rng, phase2_start, duration_minutes=5, logs_per_minute=10)

    # Inject slow queries eating connections
    for i in range(8):
        t = phase2_start + timedelta(seconds=30 * i)
        phase2.append({
            "timestamp": t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "service": "db-primary",
            "level": "WARN",
            "message": f"Slow query on table orders: {2000 + i * 500}ms. Query: SELECT * FROM orders JOIN order_items... Full table scan detected.",
        })
        pool_used = 30 + i * 3
        phase2.append({
            "timestamp": (t + timedelta(seconds=5)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "service": "db-primary",
            "level": "WARN",
            "message": f"Connection pool utilization: {pool_used}/50 ({pool_used*2}%). Active queries: {10 + i * 2}",
        })

    # Phase 3: Pool exhaustion + cascade (20-30 min)
    phase3_start = start_time + timedelta(minutes=20)
    phase3 = []

    # DB pool maxes out
    phase3.append({
        "timestamp": phase3_start.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "service": "db-primary",
        "level": "ERROR",
        "message": "Connection pool exhausted: 50/50 connections in use. 12 requests waiting. Max wait time: 30s.",
    })

    # Services start failing — this is the cascade
    cascade_services = ["order-service", "payment-service", "user-service", "queue-worker"]
    for i in range(30):
        t = phase3_start + timedelta(seconds=2 + i * 3)
        svc = cascade_services[i % len(cascade_services)]

        # DB connection timeouts
        phase3.append({
            "timestamp": t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "service": svc,
            "level": "ERROR",
            "message": f"Database connection timeout after 30000ms. Unable to acquire connection from pool. request_id=req-{rng.randint(100000, 999999)}",
        })

        # Some services retry and fail
        if rng.random() < 0.3:
            phase3.append({
                "timestamp": (t + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "service": svc,
                "level": "ERROR",
                "message": f"Retry 1/3 failed: connection pool timeout. Circuit breaker OPEN for db-primary.",
            })

    # More DB errors
    for i in range(5):
        t = phase3_start + timedelta(seconds=10 + i * 8)
        phase3.append({
            "timestamp": t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "service": "db-primary",
            "level": "ERROR",
            "message": f"Connection pool exhausted. {15 + i * 3} requests queued. Oldest waiting: {30 + i * 10}s. Active long-running queries: {5 + i}",
        })

    # api-gateway sees downstream failures
    for i in range(10):
        t = phase3_start + timedelta(seconds=5 + i * 5)
        endpoint = rng.choice(["/api/v1/orders", "/api/v1/payments", "/api/v1/users"])
        phase3.append({
            "timestamp": t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "service": "api-gateway",
            "level": "ERROR",
            "message": f"Upstream error: {rng.choice(cascade_services)} returned 503 for {endpoint}. Latency: {15000 + rng.randint(0, 5000)}ms",
        })

    # Queue worker backs up
    for i in range(4):
        t = phase3_start + timedelta(minutes=2, seconds=i * 20)
        phase3.append({
            "timestamp": t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "service": "queue-worker",
            "level": "ERROR",
            "message": f"Failed to process message from queue 'orders': database connection unavailable. Queue depth: {500 + i * 200}. Messages will be retried.",
        })

    # Background normal logs from unaffected services
    phase3_bg = generate_baseline_logs(
        rng, phase3_start, duration_minutes=10, logs_per_minute=5,
        services=["auth-service", "notification-service", "search-service", "cache-layer"],
    )

    # Phase 4: Resolution (30-40 min)
    phase4_start = start_time + timedelta(minutes=30)
    phase4 = []
    phase4.append({
        "timestamp": phase4_start.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "service": "db-primary",
        "level": "WARN",
        "message": "Long-running queries terminated by DBA. 8 queries killed after running >60s.",
    })
    phase4.append({
        "timestamp": (phase4_start + timedelta(seconds=10)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "service": "db-primary",
        "level": "INFO",
        "message": "Connection pool recovering: 35/50 connections active, 0 waiting.",
    })
    phase4.append({
        "timestamp": (phase4_start + timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "service": "db-primary",
        "level": "INFO",
        "message": "Connection pool healthy: 12/50 connections active, 0 waiting.",
    })

    recovery = generate_baseline_logs(rng, phase4_start + timedelta(minutes=1), duration_minutes=9, logs_per_minute=10)

    all_logs = normal + phase2 + phase3 + phase3_bg + phase4 + recovery
    all_logs.sort(key=lambda x: x["timestamp"])

    return all_logs, GROUND_TRUTH


def grade(diagnosis: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, float]:
    scores = {}

    # Root cause (40%) - must identify DB connection pool, not downstream services
    cause = str(diagnosis.get("root_cause", "")).lower()
    db_pool_keywords = ["connection pool", "pool exhaustion", "pool exhausted",
                        "db connection", "database connection", "connection timeout",
                        "pool full", "connection limit"]
    if any(kw in cause for kw in db_pool_keywords):
        scores["root_cause_score"] = 1.0
    elif "database" in cause or "db" in cause or "connection" in cause:
        scores["root_cause_score"] = 0.6
    elif "slow query" in cause or "slow queries" in cause:
        scores["root_cause_score"] = 0.7  # close — the slow queries caused pool exhaustion
    elif any(svc in cause for svc in ["order-service", "payment-service", "queue-worker"]):
        scores["root_cause_score"] = 0.2  # fell for the symptom, not the cause
    else:
        scores["root_cause_score"] = 0.0

    # Affected service (25%) - must say db-primary, not downstream
    svc = str(diagnosis.get("affected_service", "")).lower().strip()
    if svc in ("db-primary", "db primary", "database", "db"):
        scores["service_score"] = 1.0
    elif "db" in svc or "database" in svc:
        scores["service_score"] = 0.8
    elif svc in ("order-service", "payment-service"):
        scores["service_score"] = 0.3  # these are symptoms
    else:
        scores["service_score"] = 0.0

    # Severity (15%)
    sev = str(diagnosis.get("severity", "")).lower().strip()
    scores["severity_score"] = {"critical": 1.0, "high": 0.6, "medium": 0.3}.get(sev, 0.1)

    # Time (10%)
    submitted_time = str(diagnosis.get("start_time", ""))
    if "09:20" in submitted_time or "09:19" in submitted_time or "09:21" in submitted_time:
        scores["time_score"] = 1.0
    elif "09:15" in submitted_time or "09:1" in submitted_time:
        scores["time_score"] = 0.6
    elif "09:2" in submitted_time or "09:3" in submitted_time:
        scores["time_score"] = 0.5
    elif submitted_time:
        scores["time_score"] = 0.2
    else:
        scores["time_score"] = 0.0

    # Description (10%)
    desc = str(diagnosis.get("description", "")).lower()
    d = 0.0
    if any(w in desc for w in ["connection pool", "pool exhaust"]):
        d += 0.4
    if any(w in desc for w in ["cascade", "downstream", "multiple services"]):
        d += 0.3
    if any(w in desc for w in ["slow query", "slow queries", "full scan"]):
        d += 0.3
    scores["description_score"] = min(1.0, d)

    total = (
        0.40 * scores["root_cause_score"]
        + 0.25 * scores["service_score"]
        + 0.15 * scores["severity_score"]
        + 0.10 * scores["time_score"]
        + 0.10 * scores["description_score"]
    )
    scores["total"] = round(min(1.0, total), 4)
    return scores

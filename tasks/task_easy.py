"""
Task 1: Single Service OOM Crash (Easy)

Scenario: The order-service crashes with an OutOfMemoryError.
Symptoms are clear — explicit OOM errors, service restart messages,
and increased error rates. A straightforward investigation.

Root cause: order-service memory leak causing OOM crash
Affected service: order-service
Severity: critical
Time window: errors start ~30 minutes into the logs
"""

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from incidentlens_env.tasks.log_generator import (
    generate_baseline_logs, format_log_line, _fill_template
)

TASK_ID = "single_service_oom"
TASK_NAME = "Single Service OOM Crash"
TASK_DIFFICULTY = "easy"
TASK_DESCRIPTION = (
    "ALERT: order-service health check failures detected. "
    "Multiple 5xx errors reported by api-gateway for /api/v1/orders endpoints. "
    "Investigate the logs to determine: what failed, why, and severity."
)
MIN_SCORE = 0.01
MAX_SCORE = 0.99

# Ground truth for grading
GROUND_TRUTH = {
    "root_cause": "oom",  # keywords: oom, out of memory, memory leak, memory exhaustion
    "affected_service": "order-service",
    "severity": "critical",
    "incident_start_offset_minutes": 30,  # errors start at ~30 min mark
}


def generate(seed: int = 42) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    """Generate logs with an OOM crash scenario."""
    rng = random.Random(seed)
    start_time = datetime(2025, 3, 15, 14, 0, 0)

    # Phase 1: Normal operations (0-25 min)
    normal_logs = generate_baseline_logs(
        rng, start_time, duration_minutes=25, logs_per_minute=10,
    )

    # Phase 2: Memory pressure building (25-30 min)
    pressure_start = start_time + timedelta(minutes=25)
    pressure_logs = generate_baseline_logs(
        rng, pressure_start, duration_minutes=5, logs_per_minute=8,
    )
    # Inject memory warnings
    t = pressure_start + timedelta(minutes=1)
    for i in range(6):
        heap_pct = 75 + i * 4
        pressure_logs.append({
            "timestamp": (t + timedelta(seconds=30 * i)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "service": "order-service",
            "level": "WARN",
            "message": f"JVM heap usage at {heap_pct}% (threshold: 85%). GC pause: {50 + i * 30}ms",
        })
    pressure_logs.append({
        "timestamp": (pressure_start + timedelta(minutes=4)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "service": "order-service",
        "level": "WARN",
        "message": "Memory allocation rate exceeding GC collection rate. Possible memory leak detected.",
    })

    # Phase 3: Crash (30-35 min)
    crash_time = start_time + timedelta(minutes=30)
    crash_logs = []

    crash_logs.append({
        "timestamp": crash_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "service": "order-service",
        "level": "ERROR",
        "message": "java.lang.OutOfMemoryError: Java heap space. Failed to allocate 67108864 bytes.",
    })
    crash_logs.append({
        "timestamp": (crash_time + timedelta(seconds=1)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "service": "order-service",
        "level": "ERROR",
        "message": "FATAL: Service shutting down due to unrecoverable error. Heap dump written to /var/log/order-service/heapdump.hprof",
    })
    crash_logs.append({
        "timestamp": (crash_time + timedelta(seconds=2)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "service": "order-service",
        "level": "ERROR",
        "message": "Process exited with code 137 (OOM killed by system)",
    })

    # api-gateway starts seeing failures
    for i in range(8):
        t = crash_time + timedelta(seconds=3 + i * 2)
        crash_logs.append({
            "timestamp": t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "service": "api-gateway",
            "level": "ERROR",
            "message": f"Upstream order-service connection refused. Request POST /api/v1/orders failed with 503. request_id=req-{rng.randint(100000,999999)}",
        })

    # Service restart
    restart_time = crash_time + timedelta(seconds=25)
    crash_logs.append({
        "timestamp": restart_time.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "service": "order-service",
        "level": "INFO",
        "message": "Service restarting (attempt 1/3). Reason: process crash detected by supervisor.",
    })
    crash_logs.append({
        "timestamp": (restart_time + timedelta(seconds=10)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
        "service": "order-service",
        "level": "INFO",
        "message": "Service started successfully. Heap: 512MB allocated, 45MB used.",
    })

    # Phase 4: Recovery with some lingering errors (35-45 min)
    recovery_logs = generate_baseline_logs(
        rng, crash_time + timedelta(minutes=5), duration_minutes=10, logs_per_minute=10,
    )
    # A few more 503s during recovery
    for i in range(3):
        t = crash_time + timedelta(minutes=5, seconds=i * 10)
        recovery_logs.append({
            "timestamp": t.strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
            "service": "api-gateway",
            "level": "WARN",
            "message": f"Upstream order-service elevated latency: {800 + rng.randint(0, 500)}ms",
        })

    all_logs = normal_logs + pressure_logs + crash_logs + recovery_logs
    all_logs.sort(key=lambda x: x["timestamp"])

    return all_logs, GROUND_TRUTH


def grade(diagnosis: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, float]:
    """Grade the agent's diagnosis against ground truth."""
    scores = {}

    # Root cause identification (40%)
    submitted_cause = str(diagnosis.get("root_cause", "")).lower()
    oom_keywords = ["oom", "out of memory", "outofmemory", "memory leak", "memory exhaustion",
                    "heap space", "heap", "memory"]
    if any(kw in submitted_cause for kw in oom_keywords):
        scores["root_cause_score"] = 1.0
    elif "memory" in submitted_cause or "crash" in submitted_cause:
        scores["root_cause_score"] = 0.5
    else:
        scores["root_cause_score"] = 0.0

    # Affected service (25%)
    submitted_service = str(diagnosis.get("affected_service", "")).lower().strip()
    if submitted_service == "order-service":
        scores["service_score"] = 1.0
    elif "order" in submitted_service:
        scores["service_score"] = 0.7
    else:
        scores["service_score"] = 0.0

    # Severity (15%)
    submitted_severity = str(diagnosis.get("severity", "")).lower().strip()
    if submitted_severity == "critical":
        scores["severity_score"] = 1.0
    elif submitted_severity == "high":
        scores["severity_score"] = 0.6
    else:
        scores["severity_score"] = 0.2

    # Time window (10%)
    submitted_time = str(diagnosis.get("start_time", ""))
    if "14:30" in submitted_time or "14:29" in submitted_time or "14:31" in submitted_time:
        scores["time_score"] = 1.0
    elif "14:2" in submitted_time or "14:3" in submitted_time:
        scores["time_score"] = 0.6
    elif submitted_time:
        scores["time_score"] = 0.2
    else:
        scores["time_score"] = 0.0

    # Description quality (10%)
    desc = str(diagnosis.get("description", "")).lower()
    desc_score = 0.0
    if any(w in desc for w in ["oom", "out of memory", "memory"]):
        desc_score += 0.4
    if any(w in desc for w in ["order", "order-service"]):
        desc_score += 0.3
    if any(w in desc for w in ["crash", "killed", "restart", "heap"]):
        desc_score += 0.3
    scores["description_score"] = min(1.0, desc_score)

    total = (
        0.40 * scores["root_cause_score"]
        + 0.25 * scores["service_score"]
        + 0.15 * scores["severity_score"]
        + 0.10 * scores["time_score"]
        + 0.10 * scores["description_score"]
    )
    scores["total"] = round(max(MIN_SCORE, min(MAX_SCORE, total)), 4)
    return scores

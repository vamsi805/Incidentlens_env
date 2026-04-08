"""
Task 3: Subtle Memory Leak with Correlated GC Pauses (Hard)

Scenario: A gradual memory leak in cache-layer causes increasingly frequent
GC pauses. These pauses correlate with specific request patterns (search queries).
No single log line screams the problem — the agent must:
1. Notice the gradual degradation pattern across time
2. Correlate search-service latency spikes with cache-layer GC pauses
3. Identify cache-layer memory growth as the root cause
4. Not get distracted by the periodic latency spikes (they look like normal variance)

This is hard because:
- No explicit ERROR at the root cause service until very late
- The signal is statistical (gradually increasing latency + memory)
- Multiple services show symptoms at different times
- The real cause (cache-layer memory leak) is buried in WARN messages
"""

import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Tuple

from incidentlens_env.tasks.log_generator import generate_baseline_logs

TASK_ID = "subtle_memory_leak"
TASK_NAME = "Subtle Memory Leak with Correlated GC Pauses"
TASK_DIFFICULTY = "hard"
TASK_DESCRIPTION = (
    "ALERT: Intermittent latency spikes observed across search-service and api-gateway "
    "over the past hour. No clear error spike. p99 latency gradually climbing from 200ms "
    "to 2000ms. Some users reporting slow search results. Investigate the root cause."
)
MIN_SCORE = 0.01
MAX_SCORE = 0.99

GROUND_TRUTH = {
    "root_cause": "memory_leak_cache_layer",
    "affected_service": "cache-layer",
    "severity": "high",
    "incident_start_offset_minutes": 15,
}


def generate(seed: int = 42) -> Tuple[List[Dict[str, str]], Dict[str, Any]]:
    rng = random.Random(seed)
    start_time = datetime(2025, 3, 15, 10, 0, 0)
    all_logs = []

    # Generate 60 minutes of logs with gradually degrading cache-layer
    for minute in range(60):
        t = start_time + timedelta(minutes=minute)
        phase = minute / 60.0  # 0.0 to 1.0 progression

        # Normal baseline logs
        for _ in range(rng.randint(6, 12)):
            service = rng.choice(["api-gateway", "auth-service", "user-service",
                                  "order-service", "search-service", "db-primary"])
            latency = rng.randint(5, 200)
            all_logs.append({
                "timestamp": (t + timedelta(seconds=rng.uniform(0, 59))).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "service": service,
                "level": "INFO",
                "message": f"Request processed in {latency}ms",
            })

        # cache-layer: gradually increasing memory usage (the root cause)
        if minute >= 15:
            mem_pct = 50 + int(phase * 45)  # 50% -> 95%
            gc_pause = int(20 + phase * phase * 800)  # quadratic growth

            all_logs.append({
                "timestamp": (t + timedelta(seconds=rng.randint(10, 50))).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "service": "cache-layer",
                "level": "INFO" if mem_pct < 75 else "WARN",
                "message": f"Memory stats: heap_used={mem_pct}%, objects={10000 + minute * 500}, "
                           f"gc_pause={gc_pause}ms, evictions={minute * 2}/min",
            })

            # GC pauses cause search latency spikes
            if gc_pause > 100 and rng.random() < 0.6:
                search_latency = 200 + gc_pause + rng.randint(0, 200)
                all_logs.append({
                    "timestamp": (t + timedelta(seconds=rng.randint(10, 55))).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "service": "search-service",
                    "level": "WARN" if search_latency > 500 else "INFO",
                    "message": f"Search query completed in {search_latency}ms "
                               f"(cache_lookup={gc_pause + rng.randint(10, 50)}ms, "
                               f"db_fallback={'yes' if gc_pause > 200 else 'no'})",
                })

            # api-gateway sees elevated latency
            if gc_pause > 200 and rng.random() < 0.4:
                gw_latency = search_latency + rng.randint(50, 150)
                all_logs.append({
                    "timestamp": (t + timedelta(seconds=rng.randint(15, 55))).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "service": "api-gateway",
                    "level": "WARN",
                    "message": f"Slow response: GET /api/v1/search took {gw_latency}ms (threshold: 500ms)",
                })

        # cache-layer object growth warnings (subtle)
        if minute >= 20 and minute % 5 == 0:
            all_logs.append({
                "timestamp": (t + timedelta(seconds=30)).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "service": "cache-layer",
                "level": "WARN" if minute > 35 else "INFO",
                "message": f"Cache size: {10000 + minute * 500} objects, "
                           f"memory: {200 + minute * 8}MB/{512 if minute < 40 else 512}MB, "
                           f"hit_rate={max(60, 95 - minute)}%",
            })

        # Late stage: cache-layer starts failing (after 45 min)
        if minute >= 45:
            if rng.random() < 0.3:
                all_logs.append({
                    "timestamp": (t + timedelta(seconds=rng.randint(5, 55))).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "service": "cache-layer",
                    "level": "ERROR",
                    "message": f"GC overhead limit exceeded. GC pause: {500 + rng.randint(0, 500)}ms. "
                               f"Memory: {90 + rng.randint(0, 8)}% utilized.",
                })

            # search falls back to DB more
            if rng.random() < 0.4:
                all_logs.append({
                    "timestamp": (t + timedelta(seconds=rng.randint(5, 55))).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                    "service": "search-service",
                    "level": "WARN",
                    "message": f"Cache miss rate elevated: {40 + rng.randint(0, 20)}%. "
                               f"Falling back to database for search queries.",
                })

        # Red herrings: occasional unrelated errors
        if rng.random() < 0.03:
            all_logs.append({
                "timestamp": (t + timedelta(seconds=rng.randint(0, 59))).strftime("%Y-%m-%d %H:%M:%S.%f")[:-3],
                "service": rng.choice(["auth-service", "notification-service"]),
                "level": "ERROR",
                "message": rng.choice([
                    f"Failed to send notification to user usr-{rng.randint(10000,99999)}: SMTP timeout",
                    f"Rate limit exceeded for IP {rng.randint(1,255)}.{rng.randint(0,255)}.{rng.randint(0,255)}.{rng.randint(1,255)}",
                    f"Token validation failed: expired token for session sess-{rng.randint(100000,999999)}",
                ]),
            })

    all_logs.sort(key=lambda x: x["timestamp"])
    return all_logs, GROUND_TRUTH


def grade(diagnosis: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, float]:
    scores = {}

    cause = str(diagnosis.get("root_cause", "")).lower()
    # Must identify cache-layer memory leak, not just "search is slow"
    cache_mem_keywords = ["memory leak", "cache memory", "cache-layer memory",
                          "gc overhead", "gc pause", "garbage collection",
                          "heap", "cache leak", "object growth", "memory growth"]
    if any(kw in cause for kw in cache_mem_keywords):
        scores["root_cause_score"] = 1.0
    elif "cache" in cause and ("memory" in cause or "leak" in cause):
        scores["root_cause_score"] = 0.9
    elif "memory" in cause or "leak" in cause:
        scores["root_cause_score"] = 0.6
    elif "cache" in cause:
        scores["root_cause_score"] = 0.5
    elif "gc" in cause:
        scores["root_cause_score"] = 0.5
    elif "search" in cause or "latency" in cause:
        scores["root_cause_score"] = 0.2  # symptom not cause
    else:
        scores["root_cause_score"] = 0.0

    # Affected service (25%)
    svc = str(diagnosis.get("affected_service", "")).lower().strip()
    if svc in ("cache-layer", "cache layer", "cache"):
        scores["service_score"] = 1.0
    elif "cache" in svc:
        scores["service_score"] = 0.8
    elif svc == "search-service":
        scores["service_score"] = 0.3  # symptom
    else:
        scores["service_score"] = 0.0

    # Severity (15%)
    sev = str(diagnosis.get("severity", "")).lower().strip()
    scores["severity_score"] = {"high": 1.0, "critical": 0.7, "medium": 0.5}.get(sev, 0.1)

    # Time (10%)
    submitted_time = str(diagnosis.get("start_time", ""))
    if any(t in submitted_time for t in ["10:15", "10:14", "10:16"]):
        scores["time_score"] = 1.0
    elif "10:1" in submitted_time or "10:2" in submitted_time:
        scores["time_score"] = 0.6
    elif submitted_time:
        scores["time_score"] = 0.2
    else:
        scores["time_score"] = 0.0

    # Description (10%)
    desc = str(diagnosis.get("description", "")).lower()
    d = 0.0
    if any(w in desc for w in ["memory leak", "memory growth"]):
        d += 0.3
    if "cache" in desc:
        d += 0.2
    if any(w in desc for w in ["gc", "garbage collection", "gc pause"]):
        d += 0.2
    if any(w in desc for w in ["gradual", "increasing", "growing", "progressive"]):
        d += 0.15
    if any(w in desc for w in ["search", "latency", "correlation", "correlated"]):
        d += 0.15
    scores["description_score"] = min(1.0, d)

    total = (
        0.40 * scores["root_cause_score"]
        + 0.25 * scores["service_score"]
        + 0.15 * scores["severity_score"]
        + 0.10 * scores["time_score"]
        + 0.10 * scores["description_score"]
    )
    scores["total"] = round(max(MIN_SCORE, min(MAX_SCORE, total)), 4)
    return scores

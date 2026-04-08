"""
IncidentLens Environment Implementation.

Simulates incident triage from application logs. Agents investigate
log data using search/filter operations and submit a diagnosis.
"""

import re
from collections import Counter
from typing import Any, Dict, List, Optional
from uuid import uuid4

from openenv.core.env_server.interfaces import Environment
from openenv.core.env_server.types import State

try:
    from incidentlens_env.models import IncidentLensAction, IncidentLensObservation, IncidentLensState
    from incidentlens_env.tasks.registry import TASK_REGISTRY, get_task
    from incidentlens_env.tasks.log_generator import format_log_line
except ImportError:
    from models import IncidentLensAction, IncidentLensObservation, IncidentLensState
    from tasks.registry import TASK_REGISTRY, get_task
    from tasks.log_generator import format_log_line


MAX_STEPS = 25
MAX_RESULT_LINES = 50


class IncidentLensEnvironment(Environment):
    """
    IncidentLens environment for log analysis and incident triage.

    Multi-step episodes where agents investigate logs and submit a diagnosis.
    Dense reward based on how close the diagnosis is to the ground truth.
    """

    SUPPORTS_CONCURRENT_SESSIONS: bool = True

    def __init__(self):
        self._state = IncidentLensState(episode_id=str(uuid4()))
        self._logs: List[Dict[str, str]] = []
        self._ground_truth: Dict[str, Any] = {}
        self._task_def = None
        self._incident_summary = ""
        self._services_seen: set = set()

    def reset(
        self,
        task_id: Optional[str] = None,
        seed: Optional[int] = None,
        episode_id: Optional[str] = None,
    ) -> IncidentLensObservation:
        task_id = task_id or "single_service_oom"
        seed = seed or 42

        task_def = get_task(task_id)
        if task_def is None:
            available = ", ".join(TASK_REGISTRY.keys())
            return IncidentLensObservation(
                done=True, reward=0.0,
                result=f"Unknown task_id '{task_id}'. Available: {available}",
            )

        self._task_def = task_def
        self._incident_summary = task_def.description
        logs, ground_truth = task_def.generate(seed=seed)
        self._logs = logs
        self._ground_truth = ground_truth
        self._services_seen = set()

        self._state = IncidentLensState(
            episode_id=episode_id or str(uuid4()),
            task_id=task_id,
            step_count=0,
            max_steps=MAX_STEPS,
            diagnosed=False,
            current_score=None,
        )

        # Initial overview
        services = sorted(set(l["service"] for l in self._logs))
        levels = Counter(l["level"] for l in self._logs)
        time_range = f"{self._logs[0]['timestamp']} to {self._logs[-1]['timestamp']}" if self._logs else "N/A"
        overview = (
            f"Incident Investigation Started\n"
            f"{'='*50}\n"
            f"Alert: {self._incident_summary}\n\n"
            f"Log summary: {len(self._logs)} lines, time range: {time_range}\n"
            f"Services: {', '.join(services)}\n"
            f"Log levels: {dict(levels)}\n\n"
            f"Available commands: view_logs, grep, filter_service, filter_level, "
            f"filter_time_range, count_by_service, count_by_level, "
            f"count_errors_over_time, show_unique_errors, diagnose"
        )

        return self._make_obs(overview)

    def step(self, action: IncidentLensAction) -> IncidentLensObservation:
        if self._state.diagnosed:
            return self._make_obs("Investigation complete. Call reset() for a new incident.", done=True)

        self._state.step_count += 1
        if self._state.step_count > self._state.max_steps:
            return self._auto_diagnose()

        op = action.operation.lower().strip()
        params = action.params or {}

        try:
            if op == "diagnose":
                return self._do_diagnose(params)
            elif op == "view_logs":
                return self._op_view_logs(params)
            elif op == "grep":
                return self._op_grep(params)
            elif op == "filter_service":
                return self._op_filter_service(params)
            elif op == "filter_level":
                return self._op_filter_level(params)
            elif op == "filter_time_range":
                return self._op_filter_time_range(params)
            elif op == "count_by_service":
                return self._op_count_by_service()
            elif op == "count_by_level":
                return self._op_count_by_level()
            elif op == "count_errors_over_time":
                return self._op_count_errors_over_time(params)
            elif op == "show_unique_errors":
                return self._op_show_unique_errors(params)
            else:
                return self._make_obs(
                    f"Unknown operation '{op}'. Available: view_logs, grep, filter_service, "
                    f"filter_level, filter_time_range, count_by_service, count_by_level, "
                    f"count_errors_over_time, show_unique_errors, diagnose"
                )
        except Exception as e:
            return self._make_obs(f"Error: {str(e)}")

    @property
    def state(self) -> IncidentLensState:
        return self._state

    # --- Operations ---

    def _do_diagnose(self, params: Dict) -> IncidentLensObservation:
        self._state.diagnosed = True
        scores = self._task_def.grade(params, self._ground_truth)
        total = scores.get("total", 0.0)
        self._state.current_score = total

        return IncidentLensObservation(
            result=f"Diagnosis submitted. Score: {total:.4f}",
            total_log_lines=len(self._logs),
            incident_summary=self._incident_summary,
            task_id=self._state.task_id,
            step_number=self._state.step_count,
            max_steps=self._state.max_steps,
            services_seen=sorted(self._services_seen),
            score=total,
            score_breakdown=scores,
            done=True,
            reward=total,
        )

    def _auto_diagnose(self) -> IncidentLensObservation:
        # Empty diagnosis gets low score
        return self._do_diagnose({
            "root_cause": "unknown",
            "affected_service": "unknown",
            "severity": "medium",
            "start_time": "",
            "description": "Investigation timed out.",
        })

    def _op_view_logs(self, params: Dict) -> IncidentLensObservation:
        start = int(params.get("start", 0))
        count = min(int(params.get("count", 20)), MAX_RESULT_LINES)
        subset = self._logs[start:start + count]
        self._track_services(subset)
        lines = [format_log_line(l) for l in subset]
        header = f"Showing lines {start}-{start + len(subset)} of {len(self._logs)}"
        return self._make_obs(header + "\n" + "\n".join(lines))

    def _op_grep(self, params: Dict) -> IncidentLensObservation:
        pattern = str(params.get("pattern", ""))
        if not pattern:
            return self._make_obs("Specify params.pattern to search for.")
        case_sensitive = params.get("case_sensitive", False)
        flags = 0 if case_sensitive else re.IGNORECASE
        try:
            regex = re.compile(pattern, flags)
        except re.error as e:
            return self._make_obs(f"Invalid regex: {e}")

        matches = [l for l in self._logs if regex.search(l["message"]) or regex.search(l["service"])]
        self._track_services(matches)

        if not matches:
            return self._make_obs(f"No matches for pattern '{pattern}'.")

        lines = [format_log_line(l) for l in matches[:MAX_RESULT_LINES]]
        header = f"grep '{pattern}': {len(matches)} matches" + (f" (showing first {MAX_RESULT_LINES})" if len(matches) > MAX_RESULT_LINES else "")
        return self._make_obs(header + "\n" + "\n".join(lines))

    def _op_filter_service(self, params: Dict) -> IncidentLensObservation:
        service = str(params.get("service", "")).lower()
        if not service:
            services = sorted(set(l["service"] for l in self._logs))
            return self._make_obs(f"Available services: {', '.join(services)}\nSpecify params.service.")

        matches = [l for l in self._logs if l["service"].lower() == service]
        self._track_services(matches)

        if not matches:
            return self._make_obs(f"No logs from service '{service}'.")

        lines = [format_log_line(l) for l in matches[:MAX_RESULT_LINES]]
        levels = Counter(l["level"] for l in matches)
        header = f"Service '{service}': {len(matches)} entries. Levels: {dict(levels)}"
        if len(matches) > MAX_RESULT_LINES:
            header += f" (showing first {MAX_RESULT_LINES})"
        return self._make_obs(header + "\n" + "\n".join(lines))

    def _op_filter_level(self, params: Dict) -> IncidentLensObservation:
        level = str(params.get("level", "ERROR")).upper()
        matches = [l for l in self._logs if l["level"] == level]
        self._track_services(matches)

        if not matches:
            return self._make_obs(f"No {level} entries found.")

        lines = [format_log_line(l) for l in matches[:MAX_RESULT_LINES]]
        by_svc = Counter(l["service"] for l in matches)
        header = f"{level} entries: {len(matches)}. By service: {dict(by_svc)}"
        if len(matches) > MAX_RESULT_LINES:
            header += f" (showing first {MAX_RESULT_LINES})"
        return self._make_obs(header + "\n" + "\n".join(lines))

    def _op_filter_time_range(self, params: Dict) -> IncidentLensObservation:
        start_time = str(params.get("start_time", ""))
        end_time = str(params.get("end_time", ""))
        if not start_time or not end_time:
            return self._make_obs("Specify params.start_time and params.end_time (e.g., '2025-03-15 14:30:00').")

        matches = [l for l in self._logs if start_time <= l["timestamp"] <= end_time]
        self._track_services(matches)

        if not matches:
            return self._make_obs(f"No logs in range {start_time} to {end_time}.")

        lines = [format_log_line(l) for l in matches[:MAX_RESULT_LINES]]
        levels = Counter(l["level"] for l in matches)
        header = f"Time range {start_time} to {end_time}: {len(matches)} entries. Levels: {dict(levels)}"
        if len(matches) > MAX_RESULT_LINES:
            header += f" (showing first {MAX_RESULT_LINES})"
        return self._make_obs(header + "\n" + "\n".join(lines))

    def _op_count_by_service(self) -> IncidentLensObservation:
        counts = Counter(l["service"] for l in self._logs)
        error_counts = Counter(l["service"] for l in self._logs if l["level"] == "ERROR")
        warn_counts = Counter(l["service"] for l in self._logs if l["level"] == "WARN")

        lines = ["Service               | Total | ERROR | WARN",
                 "----------------------+-------+-------+------"]
        for svc, total in counts.most_common():
            lines.append(f"{svc:22s}| {total:5d} | {error_counts.get(svc, 0):5d} | {warn_counts.get(svc, 0):4d}")
            self._services_seen.add(svc)

        return self._make_obs("\n".join(lines))

    def _op_count_by_level(self) -> IncidentLensObservation:
        counts = Counter(l["level"] for l in self._logs)
        lines = [f"{level}: {count}" for level, count in counts.most_common()]
        return self._make_obs("Log level distribution:\n" + "\n".join(lines))

    def _op_count_errors_over_time(self, params: Dict) -> IncidentLensObservation:
        bucket_min = int(params.get("bucket_minutes", 5))
        if bucket_min < 1:
            bucket_min = 1

        errors = [l for l in self._logs if l["level"] == "ERROR"]
        if not errors:
            return self._make_obs("No ERROR entries found.")

        # Parse timestamps and bucket
        buckets: Dict[str, int] = {}
        for l in errors:
            ts = l["timestamp"][:16]  # YYYY-MM-DD HH:MM
            # Round to bucket
            try:
                minute = int(ts[-2:])
                bucket_minute = (minute // bucket_min) * bucket_min
                bucket_key = f"{ts[:-2]}{bucket_minute:02d}"
            except (ValueError, IndexError):
                bucket_key = ts
            buckets[bucket_key] = buckets.get(bucket_key, 0) + 1

        lines = ["Time Bucket          | Errors",
                 "---------------------+-------"]
        for bucket in sorted(buckets):
            bar = "#" * min(buckets[bucket], 40)
            lines.append(f"{bucket:20s} | {buckets[bucket]:3d} {bar}")

        return self._make_obs("\n".join(lines))

    def _op_show_unique_errors(self, params: Dict) -> IncidentLensObservation:
        service_filter = params.get("service")
        errors = [l for l in self._logs if l["level"] == "ERROR"]
        if service_filter:
            errors = [l for l in errors if l["service"].lower() == str(service_filter).lower()]
            self._services_seen.add(str(service_filter).lower())

        if not errors:
            svc_msg = f" from '{service_filter}'" if service_filter else ""
            return self._make_obs(f"No ERROR entries{svc_msg}.")

        # Group by message pattern (first 80 chars)
        patterns: Dict[str, Dict] = {}
        for l in errors:
            key = l["message"][:80]
            if key not in patterns:
                patterns[key] = {"count": 0, "first": l["timestamp"], "last": l["timestamp"], "service": l["service"]}
            patterns[key]["count"] += 1
            patterns[key]["last"] = l["timestamp"]

        lines = []
        for msg, info in sorted(patterns.items(), key=lambda x: -x[1]["count"]):
            lines.append(f"[{info['service']}] ({info['count']}x, {info['first']} - {info['last']})")
            lines.append(f"  {msg}")
            lines.append("")

        header = f"Unique error patterns: {len(patterns)}" + (f" (service: {service_filter})" if service_filter else "")
        return self._make_obs(header + "\n" + "\n".join(lines[:MAX_RESULT_LINES * 3]))

    # --- Helpers ---

    def _track_services(self, logs: List[Dict]):
        for l in logs:
            self._services_seen.add(l["service"])

    def _make_obs(self, result: str, done: bool = False) -> IncidentLensObservation:
        # Dense reward: proportional to investigation progress
        # More services seen + more steps used = higher base, but actual score from diagnosis
        reward = 0.0
        if not done:
            # Small reward for investigation progress
            progress = min(1.0, len(self._services_seen) / 5.0) * 0.1
            reward = progress

        return IncidentLensObservation(
            result=result,
            total_log_lines=len(self._logs),
            incident_summary=self._incident_summary,
            task_id=self._state.task_id,
            step_number=self._state.step_count,
            max_steps=self._state.max_steps,
            services_seen=sorted(self._services_seen),
            score=None,
            score_breakdown=None,
            done=done,
            reward=reward,
        )

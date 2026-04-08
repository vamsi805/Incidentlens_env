"""
Data models for the IncidentLens Environment.

IncidentLens simulates real-world incident triage from application logs.
Agents must investigate log data, identify root causes, and classify severity.
"""

from typing import Any, Dict, List, Optional

from pydantic import Field

try:
    from openenv.core.env_server.types import Action, Observation, State
except ImportError:
    from pydantic import BaseModel as Action
    from pydantic import BaseModel as Observation
    from pydantic import BaseModel as State


class IncidentLensAction(Action):
    """Action for the IncidentLens environment — an investigation operation.

    Supported operations:
        - view_logs: View raw log lines. params: {"start": int, "count": int}
        - grep: Search logs by pattern. params: {"pattern": str, "case_sensitive": bool}
        - filter_service: Filter logs by service name. params: {"service": str}
        - filter_level: Filter by log level. params: {"level": "ERROR"|"WARN"|"INFO"|"DEBUG"}
        - filter_time_range: Filter by time window. params: {"start_time": str, "end_time": str}
        - count_by_service: Count log entries per service. params: {}
        - count_by_level: Count entries per log level. params: {}
        - count_errors_over_time: Show error counts in time buckets. params: {"bucket_minutes": int}
        - show_unique_errors: List unique error messages. params: {"service": str|null}
        - diagnose: Submit diagnosis. params: {"root_cause": str, "affected_service": str, "severity": "critical"|"high"|"medium"|"low", "start_time": str, "description": str}
    """

    operation: str = Field(
        ...,
        description="The investigation operation to perform",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Operation-specific parameters",
    )


class IncidentLensObservation(Observation):
    """Observation from the IncidentLens environment."""

    result: str = Field(
        default="",
        description="Output from the last operation (log lines, counts, etc.)",
    )
    total_log_lines: int = Field(
        default=0,
        description="Total number of log lines in the incident",
    )
    incident_summary: str = Field(
        default="",
        description="Brief description of the alert that triggered this investigation",
    )
    task_id: str = Field(
        default="",
        description="Current task identifier",
    )
    step_number: int = Field(
        default=0,
        description="Current step in this episode",
    )
    max_steps: int = Field(
        default=25,
        description="Maximum investigation steps allowed",
    )
    services_seen: List[str] = Field(
        default_factory=list,
        description="List of service names seen in the logs so far",
    )
    score: Optional[float] = Field(
        default=None,
        description="Score after diagnosis submission (0.0-1.0)",
    )
    score_breakdown: Optional[Dict[str, float]] = Field(
        default=None,
        description="Detailed score breakdown after diagnosis",
    )


class IncidentLensState(State):
    """Server-side state for an IncidentLens session."""

    task_id: str = Field(default="")
    step_count: int = Field(default=0)
    max_steps: int = Field(default=25)
    diagnosed: bool = Field(default=False)
    current_score: Optional[float] = Field(default=None)

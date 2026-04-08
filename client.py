"""
IncidentLens Environment Client.

Async WebSocket client for interacting with the IncidentLens environment server.
Uses the OpenEnv EnvClient for stateful sessions.
"""

from typing import Any, Dict

from openenv.core.env_client import EnvClient, StepResult

from incidentlens_env.models import IncidentLensAction, IncidentLensObservation, IncidentLensState


class IncidentLensEnv(EnvClient[IncidentLensAction, IncidentLensObservation, IncidentLensState]):
    """Remote async client for the IncidentLens environment."""

    def __init__(self, base_url: str = "http://localhost:8000", **kwargs):
        super().__init__(base_url=base_url, **kwargs)

    def _step_payload(self, action: IncidentLensAction) -> Dict[str, Any]:
        """Convert action to JSON payload for the server."""
        return action.model_dump()

    def _parse_result(self, payload: Dict[str, Any]) -> StepResult[IncidentLensObservation]:
        """Parse server response into StepResult."""
        obs_data = payload.get("observation", payload)
        observation = IncidentLensObservation(**obs_data)
        return StepResult(
            observation=observation,
            reward=payload.get("reward"),
            done=payload.get("done", False),
        )

    def _parse_state(self, payload: Dict[str, Any]) -> IncidentLensState:
        """Parse server state response."""
        return IncidentLensState(**payload)

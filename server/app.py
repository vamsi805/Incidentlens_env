"""
FastAPI application for the IncidentLens Environment.

Endpoints:
    - POST /reset: Reset the environment
    - POST /step: Execute an action
    - GET /state: Get current environment state
    - GET /schema: Get action/observation schemas
    - WS /ws: WebSocket endpoint for persistent sessions
"""

try:
    from openenv.core.env_server.http_server import create_app
    from incidentlens_env.models import IncidentLensAction, IncidentLensObservation
    from incidentlens_env.server.incidentlens_environment import IncidentLensEnvironment
except ImportError:
    from openenv.core.env_server.http_server import create_app
    from models import IncidentLensAction, IncidentLensObservation
    from server.incidentlens_environment import IncidentLensEnvironment


app = create_app(
    IncidentLensEnvironment,
    IncidentLensAction,
    IncidentLensObservation,
    env_name="incidentlens_env",
    max_concurrent_envs=1,
)


@app.get("/", tags=["Metadata"])
def root():
    """Friendly root endpoint for Space previews and manual checks."""
    return {
        "name": "incidentlens_env",
        "status": "ok",
        "message": "IncidentLens OpenEnv environment is running.",
        "docs": "/docs",
        "health": "/health",
        "schema": "/schema",
    }


def main(host: str = "0.0.0.0", port: int = 8000):
    """Entry point for direct execution via uv run server or python -m."""
    import uvicorn
    uvicorn.run(app, host=host, port=port)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, default=8000)
    args = parser.parse_args()
    if args.port == 8000:
        main()
    else:
        main(port=args.port)

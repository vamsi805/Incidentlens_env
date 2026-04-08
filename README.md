---
title: IncidentLens Environment
emoji: "🔍"
colorFrom: red
colorTo: yellow
sdk: docker
app_port: 8000
tags:
  - openenv
---

# IncidentLens: Log Analysis & Incident Triage Environment

An OpenEnv-compatible reinforcement learning environment that simulates real-world incident triage from application logs. Agents must investigate log data from microservice architectures, identify root causes, and submit a diagnosis.

## Tasks

| Task ID | Difficulty | Scenario | Key Challenge |
|---------|-----------|----------|---------------|
| `single_service_oom` | Easy | Order-service OOM crash | Single service, clear error signal |
| `cascading_db_failure` | Medium | DB connection pool exhaustion cascade | Trace symptoms back to root cause across services |
| `subtle_memory_leak` | Hard | Cache-layer memory leak with correlated GC pauses | Statistical signal, no clear errors until late, red herrings |

## Action Space

| Operation | Params | Description |
|-----------|--------|-------------|
| `view_logs` | `start`, `count` | View raw log lines |
| `grep` | `pattern`, `case_sensitive` | Regex search across logs |
| `filter_service` | `service` | Filter by service name |
| `filter_level` | `level` | Filter by ERROR/WARN/INFO/DEBUG |
| `filter_time_range` | `start_time`, `end_time` | Filter by time window |
| `count_by_service` | - | Count entries per service with error/warn breakdown |
| `count_by_level` | - | Distribution of log levels |
| `count_errors_over_time` | `bucket_minutes` | Error histogram over time |
| `show_unique_errors` | `service` (optional) | Deduplicated error patterns |
| `diagnose` | `root_cause`, `affected_service`, `severity`, `start_time`, `description` | Submit final diagnosis |

## Observation Space

| Field | Type | Description |
|-------|------|-------------|
| `result` | str | Output from the last operation |
| `total_log_lines` | int | Total log lines in the incident |
| `incident_summary` | str | Alert that triggered the investigation |
| `step_number` | int | Current step |
| `max_steps` | int | Maximum allowed steps (25) |
| `services_seen` | list[str] | Services investigated so far |
| `score` | float/null | Score after diagnosis (0.0-1.0) |
| `score_breakdown` | dict/null | Detailed scoring breakdown |

## Reward Design

- **Dense intermediate reward**: Small reward (0-0.1) for investigation progress based on services explored
- **Terminal reward**: Weighted score from diagnosis grading:
  - Root cause identification: 40%
  - Affected service: 25%
  - Severity assessment: 15%
  - Incident start time: 10%
  - Description quality: 10%

## Setup

```bash
uv sync
uv run server
```

Required inference environment variables:

- `HF_TOKEN`: token used by the OpenAI client for model calls
- `API_BASE_URL`: OpenAI-compatible API base URL
- `MODEL_NAME`: model identifier for inference

Optional local baseline variable:

- `LOCAL_IMAGE_NAME`: local Docker image name to launch with `EnvClient.from_docker_image(...)`

## Running

```bash
# Local server
uv run server

# Docker
docker build -t incidentlens .
docker run -p 8000:8000 incidentlens

# Baseline inference
python3 inference.py
```

## Baseline Scores

`inference.py` writes reproducible per-task results to `baseline_results.json` for the configured `MODEL_NAME`, `API_BASE_URL`, and seed set (`42` for all tasks).

Baseline run used:

- `MODEL_NAME=Qwen/Qwen2.5-72B-Instruct`
- `API_BASE_URL=https://router.huggingface.co/v1`
- `ENV_BASE_URL=https://vamsi805-incidentlens-env.hf.space`

Observed scores:

| Task ID | Score | Steps |
|---------|-------|-------|
| `single_service_oom` | `0.99` | `6` |
| `cascading_db_failure` | `0.93` | `8` |
| `subtle_memory_leak` | `0.83` | `6` |

Average score: `0.92`  
Total runtime: `100.4s`

## API

- `POST /reset` - Start new investigation
- `POST /step` - Execute investigation action
- `GET /state` - Current session state
- `WS /ws` - WebSocket for stateful sessions (recommended)

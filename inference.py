"""
IncidentLens Baseline Inference Script
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

STDOUT FORMAT
- The script emits [START], [STEP], and [END] lines as required.
"""

import asyncio
import json
import os
import time
from typing import Any, Dict, List, Optional

from openai import OpenAI

ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:8000")
IMAGE_NAME = os.getenv("IMAGE_NAME")
LOCAL_IMAGE_NAME = os.getenv("LOCAL_IMAGE_NAME") or IMAGE_NAME

API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY") or os.getenv("OPENAI_API_KEY")
API_BASE_URL = os.getenv("API_BASE_URL") or "https://router.huggingface.co/v1"
MODEL_NAME = os.getenv("MODEL_NAME") or "Qwen/Qwen2.5-72B-Instruct"

BENCHMARK = "incidentlens_env"
MAX_STEPS_PER_TASK = 20

TASKS = [
    {"task_id": "single_service_oom", "seed": 42},
    {"task_id": "cascading_db_failure", "seed": 42},
    {"task_id": "subtle_memory_leak", "seed": 42},
]

SYSTEM_PROMPT = """You are an expert SRE (Site Reliability Engineer) investigating a production incident.
You have access to application logs from multiple microservices. Your goal is to identify the root cause
of the incident by investigating the logs systematically.

Each turn you must respond with a SINGLE JSON action object. Do NOT include any other text.
The JSON must have these fields:
{
    "operation": "<operation_name>",
    "params": {<operation_specific_params>}
}

Available operations:
- view_logs: View raw log lines. params: {"start": int, "count": int}
- grep: Search logs by regex pattern. params: {"pattern": str, "case_sensitive": bool}
- filter_service: Filter logs by service name. params: {"service": str}
- filter_level: Filter by log level. params: {"level": "ERROR"|"WARN"|"INFO"|"DEBUG"}
- filter_time_range: Filter by time window. params: {"start_time": "YYYY-MM-DD HH:MM:SS", "end_time": "YYYY-MM-DD HH:MM:SS"}
- count_by_service: Count log entries per service. params: {}
- count_by_level: Count entries per log level. params: {}
- count_errors_over_time: Show error counts in time buckets. params: {"bucket_minutes": int}
- show_unique_errors: List unique error patterns. params: {"service": str|null}
- diagnose: Submit your diagnosis. params: {"root_cause": str, "affected_service": str, "severity": "critical"|"high"|"medium"|"low", "start_time": "YYYY-MM-DD HH:MM:SS", "description": str}

Investigation strategy:
1. Start with count_by_service and count_by_level to get an overview
2. Look at errors: show_unique_errors and count_errors_over_time
3. Drill into suspicious services with filter_service
4. Use grep to search for specific patterns
5. Use filter_time_range to narrow down incident start
6. When confident, submit a diagnosis with diagnose

Be thorough but efficient. Look for the ROOT CAUSE, not just symptoms.
When submitting diagnosis, be specific about what caused the incident.
"""


def create_client() -> OpenAI:
    if not API_KEY:
        raise RuntimeError(
            "Missing API key. Set HF_TOKEN or OPENAI_API_KEY before running inference.py."
        )
    return OpenAI(api_key=API_KEY, base_url=API_BASE_URL)


def call_llm(client: OpenAI, messages: List[Dict[str, str]]) -> str:
    response = client.chat.completions.create(
        model=MODEL_NAME,
        messages=messages,
        max_tokens=512,
        temperature=0.0,
    )
    return response.choices[0].message.content.strip()


def parse_action(text: str) -> Optional[Dict[str, Any]]:
    text = text.strip()
    if "```" in text:
        parts = text.split("```")
        for part in parts:
            part = part.strip()
            if part.startswith("json"):
                part = part[4:].strip()
            try:
                return json.loads(part)
            except json.JSONDecodeError:
                continue
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    end = text.rfind("}") + 1
    if start >= 0 and end > start:
        try:
            return json.loads(text[start:end])
        except json.JSONDecodeError:
            pass
    return None


def _obs_to_dict(obs) -> Dict[str, Any]:
    if isinstance(obs, dict):
        return obs
    if hasattr(obs, "model_dump"):
        return obs.model_dump()
    return vars(obs)


def _format_action_str(action: Dict) -> str:
    op = action.get("operation", "unknown")
    params = action.get("params", {})
    if op == "diagnose":
        value = str(params.get("root_cause", ""))[:50].replace("\n", " ").replace(" ", "_")
        return f"diagnose(root_cause='{value}')"
    if params:
        compact = ",".join(
            f"{k}={str(v).replace(chr(10), ' ').replace(' ', '_')}"
            for k, v in list(params.items())[:2]
        )
        return f"{op}({compact})"
    return op


async def _create_env():
    from incidentlens_env.client import IncidentLensEnv

    if LOCAL_IMAGE_NAME:
        return await IncidentLensEnv.from_docker_image(LOCAL_IMAGE_NAME)

    return IncidentLensEnv(base_url=ENV_BASE_URL)


async def run_task_ws(client: OpenAI, task_id: str, seed: int = 42) -> Dict[str, Any]:
    """Run a single task using the OpenEnv client."""
    from incidentlens_env.models import IncidentLensAction

    # [START] line
    print(f"[START] task={task_id} env={BENCHMARK} model={MODEL_NAME}")

    rewards: List[float] = []
    steps_taken = 0
    final_score = 0.0
    success = False

    try:
        env = await _create_env()
        async with env:
            result = await env.reset(task_id=task_id, seed=seed)
            obs = _obs_to_dict(result.observation)

            messages = [{"role": "system", "content": SYSTEM_PROMPT}]

            for step in range(MAX_STEPS_PER_TASK):
                user_msg = (
                    f"Step {step + 1}/{MAX_STEPS_PER_TASK}\n"
                    f"Alert: {obs.get('incident_summary', '')}\n\n"
                    f"Investigation result:\n{obs.get('result', '')}\n\n"
                    f"Services seen so far: {obs.get('services_seen', [])}\n"
                    f"Total log lines: {obs.get('total_log_lines', 0)}\n\n"
                    f"Respond with a single JSON action object."
                )
                messages.append({"role": "user", "content": user_msg})

                response_text = call_llm(client, messages)
                messages.append({"role": "assistant", "content": response_text})

                action = parse_action(response_text)
                if action is None:
                    action = {
                        "operation": "diagnose",
                        "params": {
                            "root_cause": "unknown",
                            "affected_service": "unknown",
                            "severity": "medium",
                            "start_time": "",
                            "description": "Could not determine root cause.",
                        },
                    }

                action_str = _format_action_str(action)
                op = action.get("operation", "")
                params = action.get("params", {})

                result = await env.step(IncidentLensAction(
                    operation=op,
                    params=params or {},
                ))
                obs = _obs_to_dict(result.observation)
                reward = result.reward or 0.0
                done = result.done
                steps_taken = step + 1
                rewards.append(reward)

                error = "null"

                # [STEP] line
                print(f"[STEP] step={steps_taken} action={action_str} reward={reward:.2f} done={'true' if done else 'false'} error={error}")

                if done:
                    final_score = obs.get("score") or reward
                    success = final_score > 0.1
                    break

                if len(messages) > 14:
                    messages = [messages[0]] + messages[-8:]

            else:
                # Force diagnose
                action = {
                    "operation": "diagnose",
                    "params": {
                        "root_cause": "unknown",
                        "affected_service": "unknown",
                        "severity": "medium",
                        "start_time": "",
                        "description": "Investigation ran out of steps.",
                    },
                }
                result = await env.step(IncidentLensAction(
                    operation="diagnose",
                    params=action["params"],
                ))
                obs = _obs_to_dict(result.observation)
                reward = result.reward or 0.0
                rewards.append(reward)
                steps_taken += 1
                print(f"[STEP] step={steps_taken} action=diagnose(timeout) reward={reward:.2f} done=true error=null")
                final_score = obs.get("score") or reward
                success = final_score > 0.1

    except Exception as e:
        rewards_str = ",".join(f"{r:.2f}" for r in rewards) if rewards else "0.00"
        print(f"[END] success=false steps={steps_taken} score=0.00 rewards={rewards_str}")
        return {"task_id": task_id, "score": 0.0, "steps": steps_taken}

    # [END] line
    rewards_str = ",".join(f"{r:.2f}" for r in rewards)
    print(f"[END] success={'true' if success else 'false'} steps={steps_taken} score={final_score:.2f} rewards={rewards_str}")

    return {"task_id": task_id, "score": final_score, "steps": steps_taken}


async def async_main():
    llm_client = create_client()
    results = []
    start_time = time.time()

    for task_config in TASKS:
        task_result = await run_task_ws(
            llm_client,
            task_id=task_config["task_id"],
            seed=task_config["seed"],
        )
        results.append(task_result)

    elapsed = time.time() - start_time
    avg_score = sum(r["score"] for r in results) / len(results) if results else 0.0

    output = {
        "model": MODEL_NAME,
        "api_base_url": API_BASE_URL,
        "results": results,
        "average_score": avg_score,
        "total_time_seconds": round(elapsed, 1),
    }
    with open("baseline_results.json", "w") as f:
        json.dump(output, f, indent=2)


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    main()

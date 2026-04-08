"""Task registry for IncidentLens environment."""

from typing import Any, Dict, List, Optional, Tuple

from incidentlens_env.tasks import task_easy, task_medium, task_hard


class TaskDef:
    def __init__(self, module):
        self.task_id: str = module.TASK_ID
        self.task_name: str = module.TASK_NAME
        self.difficulty: str = module.TASK_DIFFICULTY
        self.description: str = module.TASK_DESCRIPTION
        self._module = module

    def generate(self, seed: int = 42) -> Tuple[Any, Any]:
        return self._module.generate(seed=seed)

    def grade(self, diagnosis: Dict[str, Any], ground_truth: Dict[str, Any]) -> Dict[str, float]:
        return self._module.grade(diagnosis, ground_truth)


TASK_REGISTRY: Dict[str, TaskDef] = {
    task_easy.TASK_ID: TaskDef(task_easy),
    task_medium.TASK_ID: TaskDef(task_medium),
    task_hard.TASK_ID: TaskDef(task_hard),
}


def get_task(task_id: str) -> Optional[TaskDef]:
    return TASK_REGISTRY.get(task_id)


def list_tasks() -> List[Dict[str, str]]:
    return [
        {"task_id": t.task_id, "name": t.task_name, "difficulty": t.difficulty}
        for t in TASK_REGISTRY.values()
    ]

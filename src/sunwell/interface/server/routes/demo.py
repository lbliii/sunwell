"""Demo comparison and evaluation routes (RFC-095, RFC-098)."""

import json
import uuid
from pathlib import Path
from typing import Any

import yaml
from fastapi import APIRouter
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

router = APIRouter(prefix="/api", tags=["demo"])


# ═══════════════════════════════════════════════════════════════
# REQUEST MODELS
# ═══════════════════════════════════════════════════════════════


class DemoRunRequest(BaseModel):
    task: str | None = None
    model: str | None = None
    provider: str | None = None


class EvalRunRequest(BaseModel):
    task: str | None = None
    model: str | None = None
    provider: str | None = None
    lens: str | None = None


# ═══════════════════════════════════════════════════════════════
# DEMO ROUTES (RFC-095)
# ═══════════════════════════════════════════════════════════════


@router.get("/demo/tasks")
async def list_demo_tasks() -> list[dict[str, Any]]:
    """List available demo tasks."""
    try:
        from sunwell.benchmark.demo.tasks import BUILTIN_TASKS

        return [
            {
                "name": task.name,
                "prompt": task.prompt,
                "description": task.description,
                "expected_features": list(task.expected_features),
            }
            for task in BUILTIN_TASKS.values()
        ]
    except Exception as e:
        return [{"error": str(e)}]


@router.post("/demo/run")
async def run_demo(request: DemoRunRequest) -> dict[str, Any]:
    """Run a demo comparison (single-shot vs Sunwell).

    Code is saved to files to avoid JSON escaping issues.
    Use /api/demo/code/{run_id}/{method} to fetch raw code.
    """
    try:
        from sunwell.interface.generative.cli.helpers import resolve_model
        from sunwell.foundation.config import get_config
        from sunwell.benchmark.demo import DemoComparison, DemoExecutor, DemoScorer, get_task
        from sunwell.benchmark.demo.files import cleanup_old_demos, save_demo_code

        config = get_config()
        provider = request.provider or (config.model.default_provider if config else "ollama")
        model_name = request.model or (config.model.default_model if config else "gemma3:4b")

        model = resolve_model(provider, model_name)
        if not model:
            return {"error": "No model available"}

        task_name = request.task or "divide"
        demo_task = get_task(task_name)

        executor = DemoExecutor(model, verbose=False)
        scorer = DemoScorer()

        single_shot = await executor.run_single_shot(demo_task)
        sunwell = await executor.run_sunwell(demo_task)

        single_score = scorer.score(single_shot.code, demo_task.expected_features)
        sunwell_score = scorer.score(sunwell.code, demo_task.expected_features)

        comparison = DemoComparison(
            task=demo_task,
            single_shot=single_shot,
            sunwell=sunwell,
            single_score=single_score,
            sunwell_score=sunwell_score,
        )

        run_id = str(uuid.uuid4())[:8]
        save_demo_code(run_id, single_shot.code, sunwell.code)
        cleanup_old_demos(keep_count=20)

        return {
            "model": f"{provider}:{model_name}",
            "task": {"name": demo_task.name, "prompt": demo_task.prompt},
            "run_id": run_id,
            "single_shot": {
                "score": single_score.score,
                "lines": single_score.lines,
                "time_ms": single_shot.time_ms,
                "features": single_score.features,
            },
            "sunwell": {
                "score": sunwell_score.score,
                "lines": sunwell_score.lines,
                "time_ms": sunwell.time_ms,
                "iterations": sunwell.iterations,
                "features": sunwell_score.features,
            },
            "improvement_percent": round(comparison.improvement_percent, 1),
        }
    except Exception as e:
        return {"error": str(e)}


@router.get("/demo/code/{run_id}/{method}", response_model=None)
async def get_demo_code(run_id: str, method: str) -> PlainTextResponse | JSONResponse:
    """Get raw code from a demo run.

    Args:
        run_id: The demo run identifier.
        method: Either 'single_shot' or 'sunwell'.

    Returns:
        Raw code as plain text (not JSON-escaped).
    """
    from sunwell.benchmark.demo.files import load_demo_code

    if method not in ("single_shot", "sunwell"):
        return JSONResponse(
            {"error": f"Invalid method: {method}. Must be 'single_shot' or 'sunwell'."},
            status_code=400,
        )

    result = load_demo_code(run_id)
    if result is None:
        return JSONResponse({"error": f"Demo run not found: {run_id}"}, status_code=404)

    single_shot_code, sunwell_code = result
    code = single_shot_code if method == "single_shot" else sunwell_code

    return PlainTextResponse(content=code, media_type="text/plain")


# ═══════════════════════════════════════════════════════════════
# EVALUATION ROUTES (RFC-098)
# ═══════════════════════════════════════════════════════════════


@router.get("/eval/tasks")
async def list_eval_tasks() -> list[dict[str, Any]]:
    """List available evaluation tasks from benchmark/tasks/."""
    try:
        tasks_dir = Path(__file__).parent.parent.parent.parent / "benchmark" / "tasks"
        if not tasks_dir.exists():
            return []

        tasks = []
        for category_dir in tasks_dir.iterdir():
            if not category_dir.is_dir():
                continue
            for task_file in category_dir.glob("*.yaml"):
                try:
                    with open(task_file) as f:
                        task_data = yaml.safe_load(f)
                    tasks.append({
                        "id": f"{category_dir.name}/{task_file.stem}",
                        "name": task_data.get("name", task_file.stem),
                        "prompt": task_data.get("prompt", ""),
                        "category": category_dir.name,
                    })
                except Exception:
                    continue

        return tasks
    except Exception as e:
        return [{"error": str(e)}]


@router.get("/eval/history")
async def get_eval_history(limit: int = 20) -> list[dict[str, Any]]:
    """Get evaluation history."""
    try:
        history_dir = Path.cwd() / ".sunwell" / "eval_history"
        if not history_dir.exists():
            return []

        entries = []
        for f in sorted(history_dir.glob("*.json"), reverse=True)[:limit]:
            try:
                with open(f) as fp:
                    entries.append(json.load(fp))
            except Exception:
                continue
        return entries
    except Exception as e:
        return [{"error": str(e)}]


@router.get("/eval/stats")
async def get_eval_stats() -> dict[str, Any]:
    """Get evaluation statistics."""
    try:
        history = await get_eval_history(limit=100)
        if not history or (len(history) == 1 and "error" in history[0]):
            return {
                "total_runs": 0,
                "avg_improvement": 0,
                "sunwell_wins": 0,
                "single_shot_wins": 0,
                "ties": 0,
                "by_task": {},
            }

        total = len(history)
        improvements = [h.get("improvement_percent", 0) for h in history]
        sunwell_wins = sum(1 for h in history if h.get("improvement_percent", 0) > 0)
        single_shot_wins = sum(1 for h in history if h.get("improvement_percent", 0) < 0)
        ties = total - sunwell_wins - single_shot_wins

        return {
            "total_runs": total,
            "avg_improvement": sum(improvements) / total if total else 0,
            "sunwell_wins": sunwell_wins,
            "single_shot_wins": single_shot_wins,
            "ties": ties,
            "by_task": {},
        }
    except Exception as e:
        return {"error": str(e)}


@router.post("/eval/run")
async def run_eval(request: EvalRunRequest) -> dict[str, Any]:
    """Run an evaluation (placeholder - full implementation requires more setup)."""
    return {
        "error": "Full evaluation requires CLI: sunwell eval --task <task>",
        "hint": "The HTTP API for eval is under development.",
    }

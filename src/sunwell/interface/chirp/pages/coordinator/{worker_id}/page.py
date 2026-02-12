"""Worker detail view - shows individual worker status and history."""

from chirp import NotFound, Page

from sunwell.interface.chirp.services import CoordinatorService


def get(worker_id: str, coordinator_svc: CoordinatorService) -> Page:
    """Display detailed worker information.

    Args:
        worker_id: Worker identifier
        coordinator_svc: Coordinator service for worker data

    Returns:
        Page with worker details

    Shows:
        - Worker status (active/idle/stopped)
        - Currently running tasks
        - Task history
        - Performance metrics
        - Resource usage
    """
    # Get all workers to find the requested one
    workers = coordinator_svc.list_workers()
    worker = next((w for w in workers if w["id"] == worker_id), None)

    if not worker:
        raise NotFound(f"Worker not found: {worker_id}")

    # Get worker tasks (TODO: integrate with actual coordinator)
    running_tasks = [
        {
            "id": "task-1",
            "description": "Analyzing codebase structure",
            "started": 1707667200.0,  # Placeholder timestamp
            "progress": 45,
        },
        {
            "id": "task-2",
            "description": "Generating test cases",
            "started": 1707667500.0,
            "progress": 20,
        },
    ] if worker["status"] == "active" else []

    task_history = [
        {
            "id": "task-101",
            "description": "Refactored authentication module",
            "completed": 1707666000.0,
            "duration": 120.5,
            "status": "success",
        },
        {
            "id": "task-102",
            "description": "Updated documentation",
            "completed": 1707665000.0,
            "duration": 45.2,
            "status": "success",
        },
        {
            "id": "task-103",
            "description": "Fixed type errors",
            "completed": 1707664000.0,
            "duration": 30.1,
            "status": "success",
        },
    ]

    # Worker metrics
    metrics = {
        "uptime": "2h 15m",
        "avg_task_duration": "65s",
        "success_rate": "98%",
        "cpu_usage": "35%",
        "memory_usage": "512 MB",
    }

    return Page(
        "coordinator/{worker_id}/page.html",
        "content",
        worker=worker,
        running_tasks=running_tasks,
        task_history=task_history,
        metrics=metrics,
    )

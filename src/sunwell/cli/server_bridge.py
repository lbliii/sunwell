"""Server bridge for unified CLI/Studio visibility (RFC-119).

When the Sunwell server is running, CLI commands can route through it
so Studio Observatory can observe all activity.
"""

from collections.abc import Callable
from typing import Any

import httpx

DEFAULT_SERVER_URL = "http://127.0.0.1:8080"


async def detect_server(url: str = DEFAULT_SERVER_URL) -> str | None:
    """Check if Sunwell server is running.

    Returns server URL if available, None otherwise.
    Fast timeout (500ms) to avoid blocking CLI startup.
    """
    try:
        async with httpx.AsyncClient(timeout=0.5) as client:
            resp = await client.get(f"{url}/api/health")
            if resp.status_code == 200:
                return url
    except (httpx.ConnectError, httpx.TimeoutException):
        pass
    return None


async def run_via_server(
    server_url: str,
    goal: str,
    *,
    workspace: str | None = None,
    project_id: str | None = None,
    lens: str | None = None,
    provider: str | None = None,
    model: str | None = None,
    trust: str = "workspace",
    timeout: int = 300,
    event_callback: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    """Execute goal through server for unified visibility.

    Args:
        server_url: Server base URL
        goal: Goal to execute
        workspace: Workspace path
        project_id: Project ID
        lens: Lens name
        provider: Model provider
        model: Model name
        trust: Trust level
        timeout: Timeout seconds
        event_callback: Optional callback for each event

    Returns:
        Final run status dict
    """
    import json

    import websockets

    async with httpx.AsyncClient(timeout=timeout + 10) as client:
        # Start run via HTTP
        resp = await client.post(
            f"{server_url}/api/run",
            json={
                "goal": goal,
                "workspace": workspace,
                "project_id": project_id,
                "lens": lens,
                "provider": provider,
                "model": model,
                "trust": trust,
                "timeout": timeout,
                "source": "cli",  # Tag origin for visibility
            },
        )
        data = resp.json()

        if "error" in data:
            return {"run_id": None, "status": "error", "error": data["error"]}

        run_id = data["run_id"]

        # Connect to WebSocket for event stream
        ws_url = server_url.replace("http://", "ws://").replace("https://", "wss://")
        ws_url = f"{ws_url}/api/run/{run_id}/events"

        final_status = "complete"
        events: list[dict[str, Any]] = []

        try:
            async with websockets.connect(ws_url) as ws:
                async for message in ws:
                    event = json.loads(message)
                    events.append(event)

                    if event_callback:
                        event_callback(event)

                    # Check for terminal events
                    event_type = event.get("type", "")
                    if event_type in ("complete", "error", "cancelled"):
                        final_status = event_type
                        break

        except websockets.exceptions.ConnectionClosed:
            # Connection closed normally (run completed)
            pass

        return {
            "run_id": run_id,
            "status": final_status,
            "event_count": len(events),
        }

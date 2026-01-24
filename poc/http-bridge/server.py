"""
Minimal HTTP/WebSocket bridge — proof of concept.

This replaces 13K lines of Rust with ~80 lines of Python.

Run: uv run python server.py
Open: http://localhost:8765
"""

import asyncio
import json
import time
from pathlib import Path

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
import uvicorn

app = FastAPI(title="Sunwell HTTP Bridge POC")

# Serve static files
STATIC_DIR = Path(__file__).parent / "static"


@app.get("/")
async def index():
    return FileResponse(STATIC_DIR / "index.html")


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    """Single WebSocket for all communication."""
    await ws.accept()
    print("✓ Client connected")

    try:
        while True:
            # Receive command from client
            data = await ws.receive_json()
            cmd = data.get("type")

            if cmd == "ping":
                await ws.send_json({"type": "pong", "ts": time.time()})

            elif cmd == "run":
                # Simulate agent run with streaming events
                goal = data.get("goal", "test")
                await stream_fake_agent(ws, goal)

            else:
                await ws.send_json({"type": "error", "message": f"Unknown command: {cmd}"})

    except WebSocketDisconnect:
        print("✗ Client disconnected")
    except Exception as e:
        print(f"✗ Error: {e}")
        try:
            await ws.send_json({"type": "error", "message": str(e)})
        except:
            pass


async def stream_fake_agent(ws: WebSocket, goal: str):
    """Simulate agent streaming events — replace with real agent.run()."""
    
    events = [
        {"type": "memory_loaded", "data": {"learnings": 5, "dead_ends": 2}},
        {"type": "plan_start", "data": {"goal": goal}},
        {"type": "plan_candidate", "data": {"id": 1, "tasks": ["Research", "Implement", "Test"]}},
        {"type": "plan_candidate", "data": {"id": 2, "tasks": ["Prototype", "Iterate"]}},
        {"type": "plan_winner", "data": {"id": 1, "score": 0.87}},
        {"type": "task_start", "data": {"task": "Research", "index": 0}},
        {"type": "task_progress", "data": {"task": "Research", "progress": 0.5}},
        {"type": "task_complete", "data": {"task": "Research", "result": "Found 3 approaches"}},
        {"type": "task_start", "data": {"task": "Implement", "index": 1}},
        {"type": "model_start", "data": {"model": "claude-sonnet-4-20250514"}},
        {"type": "model_tokens", "data": {"tokens": 150, "preview": "def solve(...):\n    ..."}},
        {"type": "model_complete", "data": {"tokens": 450, "duration_ms": 1200}},
        {"type": "task_complete", "data": {"task": "Implement", "files_changed": 2}},
        {"type": "task_start", "data": {"task": "Test", "index": 2}},
        {"type": "gate_start", "data": {"gate": "syntax"}},
        {"type": "gate_pass", "data": {"gate": "syntax"}},
        {"type": "gate_start", "data": {"gate": "types"}},
        {"type": "gate_pass", "data": {"gate": "types"}},
        {"type": "task_complete", "data": {"task": "Test", "passed": True}},
        {"type": "complete", "data": {"goal": goal, "tasks_completed": 3, "duration_s": 4.2}},
    ]

    for event in events:
        event["timestamp"] = time.time()
        await ws.send_json(event)
        # Simulate processing time — real agent would yield naturally
        await asyncio.sleep(0.15)


# Mount static files after routes
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


if __name__ == "__main__":
    print("\n" + "=" * 50)
    print("  HTTP Bridge POC")
    print("  Open: http://localhost:8765")
    print("=" * 50 + "\n")
    uvicorn.run(app, host="127.0.0.1", port=8765, log_level="warning")

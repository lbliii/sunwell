# HTTP Bridge Proof-of-Concept

Minimal viable replacement for Tauri bridge. Test reliability before committing.

## Run It

```bash
# Terminal 1: Start server
cd poc/http-bridge
uv run python server.py

# Terminal 2: Open browser
open http://localhost:8765
```

## What This Proves

1. **No dropped events** — WebSocket is reliable, no stdout buffering
2. **Auto-reconnect** — Disconnect WiFi, reconnect, events resume
3. **Dead simple** — ~150 lines total

## Structure

```
poc/http-bridge/
├── server.py          # FastAPI + WebSocket (80 lines)
├── static/
│   ├── index.html     # Minimal UI
│   └── app.js         # WebSocket client (40 lines)
└── pyproject.toml     # Dependencies
```

## If This Works

Replace `studio/src-tauri/` with this pattern. The full migration:

1. Move `server.py` → `src/sunwell/server/main.py`
2. Update Svelte stores to use WebSocket instead of Tauri invoke
3. Delete `studio/src-tauri/` (13K lines)
4. Ship

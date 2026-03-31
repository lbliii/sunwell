# Running Sunwell Studio UI

## Quick Start

### Start the Server

```bash
# Start on default port (8080)
python -m sunwell serve

# Or with shortcuts
sunwell serve                  # Same as above
sunwell serve --open          # Opens browser automatically
sunwell serve --port 3000     # Custom port
```

### Access the UI

Once the server starts, open your browser to:
- **http://localhost:8080** (or your custom port)

You'll see the Chirp-powered Studio UI with all pages available:
- **Home** - Dashboard with recent projects
- **Projects** - Project management and CRUD
- **Settings** - Configuration (provider, API keys, preferences)
- **Library** - Skills and spells
- **Backlog** - Goal management
- **Writer** - Document editing
- **Memory** - Memory browser
- **Coordinator** - Worker monitoring
- **Observatory** - Run visualization
- **DAG** - Execution graph

### No Build Step Required!

Unlike the old Svelte setup:
- ✅ **No `npm install`** - Python only
- ✅ **No `npm run build`** - No build step
- ✅ **No Vite dev server** - Direct server-side rendering
- ✅ **Just refresh** - Edit `.py` or `.html` files and refresh browser

### Stopping the Server

Press `Ctrl+C` in the terminal to stop the server.

---

## Architecture

```
┌─────────────────────────────────────────┐
│  http://localhost:8080                  │
├─────────────────────────────────────────┤
│                                         │
│  / (Chirp Pages)                        │
│  ├── Server-Side Rendering (SSR)       │
│  ├── Kida templates                     │
│  ├── htmx progressive enhancement       │
│  └── Real-time SSE updates              │
│                                         │
│  /api/* (FastAPI JSON APIs)             │
│  └── Core functionality endpoints       │
│                                         │
└─────────────────────────────────────────┘
```

### What Changed (Phase 3 Migration)

**Before (Svelte SPA)**:
- Start Vite dev server: `cd studio && npm run dev`
- Build for production: `npm run build`
- Run server: `sunwell serve`
- Dependencies: Python + Node.js

**After (Chirp SSR)**:
- Just run: `sunwell serve` ✨
- Dependencies: Python only
- No build step
- Faster page loads (SSR)

---

## Troubleshooting

### Port already in use

```bash
# Use a different port
sunwell serve --port 3000
```

### Import errors

Make sure dependencies are installed:
```bash
uv sync
```

### Pages not loading

Check that the server started successfully:
- Look for "🌐 Sunwell Studio" in the terminal
- Verify no error messages
- Try accessing http://localhost:8080 directly

### Old Svelte references

If you see errors about `studio/` directory or Svelte:
- The migration is complete - those references should be removed
- Report as a bug if found

---

## Next Steps

- **Try all pages**: Navigate through Home, Projects, Settings, etc.
- **Create a project**: Use the Projects page to set up a workspace
- **Configure settings**: Set your model provider and API keys
- **Run an agent**: Use the CLI or API to trigger runs

Enjoy the simplified Python-only stack! 🎉

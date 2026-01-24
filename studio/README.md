# Sunwell Studio

**AI-native creative environment** — A minimal, beautiful GUI for creative work with AI.

## Overview

Sunwell Studio inverts the traditional IDE paradigm: instead of adding AI to an editor, it adds an editor to an AI. The interface adapts dynamically to what you're building—code, novels, screenplays, or games—surfacing relevant context and hiding everything else.

### Core Principles

- **Ollama-inspired simplicity** — One input, focused output
- **Adaptive UI** — Panels change based on project and task
- **One-click preview** — ▶ TRY IT for instant feedback
- **Local-first** — Runs entirely on your machine
- **Multi-domain** — Code, prose, scripts, dialogue

## Tech Stack

- **Svelte 5** — Reactive frontend with no runtime overhead
- **Python HTTP Server** — FastAPI backend for all communication
- **WebSocket** — Real-time streaming of agent events

## Development

### Prerequisites

- Node.js 20+
- Python 3.14+ with Sunwell installed

### Setup

```bash
cd studio

# Install dependencies
npm install

# Start Vite dev server (frontend only)
npm run dev

# In another terminal, start the Python backend
sunwell serve --dev
```

Then open http://localhost:5173 in your browser.

### Build

```bash
# Build frontend for production
npm run build

# The Python server can serve the built files:
sunwell serve
```

## Project Structure

```
studio/
├── src/                 # Svelte frontend
│   ├── routes/          # Page components
│   ├── components/      # UI components
│   ├── layouts/         # Adaptive layouts
│   ├── stores/          # State management
│   ├── styles/          # CSS design system
│   └── lib/             # Types and utilities
│
└── package.json
```

## Architecture (RFC-113)

```
┌─────────────────────────────────────────────────────────────┐
│                    Sunwell Studio                           │
├─────────────────────────────────────────────────────────────┤
│                  Svelte Frontend (Browser)                  │
│   ┌─────────────────────────┐    ┌─────────────────────┐   │
│   │  Home / Project / Preview│    │  socket.ts          │   │
│   │  (adaptive layouts)     │◄───│  HTTP + WebSocket   │   │
│   └─────────────────────────┘    └──────────┬──────────┘   │
│              ▲                               │              │
│              │                               │              │
│   ┌──────────┴──────────────┐                │              │
│   │  Stores (agent, project)│                │              │
│   └─────────────────────────┘                │              │
└──────────────────────────────────────────────┼──────────────┘
                                               │
                              ┌────────────────▼────────────────┐
                              │    Python Server (FastAPI)       │
                              │    sunwell serve                 │
                              │                                  │
                              │    /api/run      → Start agent   │
                              │    /api/events   → WebSocket     │
                              │    /api/memory   → Simulacrum    │
                              │    /api/lenses   → Lens library  │
                              └──────────────────────────────────┘
```

## Design System

The UI follows a dark, minimal aesthetic:

- **Typography**: Berkeley Mono (UI), Newsreader (prose)
- **Colors**: Near-black backgrounds, high-contrast text
- **Components**: Subtle borders, minimal chrome
- **Animations**: Fast (150ms), purposeful transitions

See `src/styles/variables.css` for the full design token system.

## References

- [RFC-043: Sunwell Studio](../docs/RFC-043-sunwell-studio.md) — Original specification
- [RFC-113: Native HTTP Bridge](../docs/RFC-113-native-http-bridge.md) — Current architecture
- [Svelte Documentation](https://svelte.dev/)

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

- **Tauri** — Rust app shell (~10MB vs Electron's 200MB+)
- **Svelte 5** — Reactive frontend with no runtime overhead
- **Sunwell Agent** — Python AI engine (subprocess communication)

## Development

### Prerequisites

- Node.js 20+
- Rust 1.70+
- Python 3.14+ with Sunwell installed

### Setup

```bash
cd studio

# Install dependencies
npm install

# Start development server
npm run tauri dev
```

### Build

```bash
# Build for production
npm run tauri build
```

## Project Structure

```
studio/
├── src-tauri/           # Rust backend
│   └── src/
│       ├── main.rs      # Entry point
│       ├── agent.rs     # Sunwell agent bridge
│       ├── commands.rs  # IPC commands
│       ├── preview.rs   # Preview management
│       └── project.rs   # Project detection
│
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

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│                    Sunwell Studio (Tauri)                   │
├───────────────────────────────────┬─────────────────────────┤
│          Svelte Frontend          │     Rust Backend        │
│   ┌─────────────────────────┐    │   ┌─────────────────┐   │
│   │  Home / Project / Preview│    │   │  Agent Bridge   │   │
│   │  (adaptive layouts)     │◄───┼───┤  (subprocess)   │   │
│   └─────────────────────────┘    │   └────────┬────────┘   │
│              ▲                   │            │            │
│              │                   │            ▼            │
│   ┌──────────┴──────────────┐    │   ┌─────────────────┐   │
│   │  Stores (agent, project)│◄───┼───┤  NDJSON Events  │   │
│   └─────────────────────────┘    │   └────────┬────────┘   │
└───────────────────────────────────┴────────────┼────────────┘
                                                 │
                                    ┌────────────▼────────────┐
                                    │    Sunwell Agent        │
                                    │    (Python subprocess)  │
                                    │    sunwell agent run    │
                                    │    --json "goal"        │
                                    └─────────────────────────┘
```

## Design System

The UI follows a dark, minimal aesthetic:

- **Typography**: Berkeley Mono (UI), Newsreader (prose)
- **Colors**: Near-black backgrounds, high-contrast text
- **Components**: Subtle borders, minimal chrome
- **Animations**: Fast (150ms), purposeful transitions

See `src/styles/variables.css` for the full design token system.

## References

- [RFC-043: Sunwell Studio](../docs/RFC-043-sunwell-studio.md) — Full specification
- [Tauri Documentation](https://tauri.app/)
- [Svelte Documentation](https://svelte.dev/)

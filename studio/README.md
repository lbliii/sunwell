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

### Development Notes

**Hot Reload Warning**: During development, you may see this warning in the console:
```
[TAURI] Couldn't find callback id 3217448598. This might happen when the app is reloaded while Rust is running an asynchronous operation.
```

This is **expected and harmless** during development. It occurs when:
- The frontend hot-reloads (Vite reloads the page)
- While Rust is processing an async `invoke` call

**Why it's safe:**
- The app continues to work normally
- Event streaming (`app.emit()`) doesn't rely on callbacks, so agent events still work
- This only happens during development hot-reloads, not in production builds

**To avoid the warning:**
- Wait for async operations to complete before saving files (triggers hot reload)
- Or simply ignore it - it's just a warning, not an error

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

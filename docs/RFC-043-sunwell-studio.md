# RFC-043: Sunwell Studio — The AI-Native Creative Environment

**Status**: Draft  
**Created**: 2026-01-19  
**Authors**: Sunwell Team  
**Depends on**: RFC-042 (Adaptive Agent)

---

## Summary

Sunwell Studio is a minimal, beautiful GUI application for creative work with AI. It inverts the traditional IDE paradigm: instead of adding AI to an editor, it adds an editor to an AI. The interface adapts dynamically to what you're building — code, novels, screenplays, or games — surfacing relevant context and hiding everything else.

**Core principles:**
- Ollama-inspired simplicity (one input, focused output)
- Adaptive UI (panels change based on project and task)
- One-click preview (▶ TRY IT for instant feedback)
- Local-first (runs entirely on your machine)
- Multi-domain (code, prose, scripts, dialogue)

---

## Motivation

### The Problem with Traditional IDEs

Traditional IDEs evolved from text editors over 40 years. They accumulated:
- Menu bars, toolbars, status bars
- Dozens of panels (explorer, outline, problems, output, terminal, git, ...)
- Hundreds of settings
- Plugin ecosystems
- The assumption that humans write code

**But in an AI-native world:**
- The AI writes; the human supervises
- Context matters more than tools
- Simplicity beats configurability
- The output (your creation) is the star

### The Problem with Existing AI Tools

| Tool | Problem |
|------|---------|
| Claude Code | Cloud-only, no memory, terminal-only |
| Cursor | Still a complex IDE, AI bolted on |
| Copilot | Completion only, no agentic capability |
| Sudowrite | Writing only, no memory, session-based |

**No tool offers:**
- Beautiful, minimal GUI
- Adaptive interface that changes per project type
- Persistent memory across sessions
- One-click preview of generated work
- Local-first privacy

---

## Design Philosophy

### Ollama Energy

Ollama succeeded by asking: "What if running LLMs was just one command?"

Sunwell Studio asks: "What if creative AI was just one input?"

```
Before:  Learn IDE → Configure → Install extensions → Write prompt → 
         Wait → Figure out how to run → Debug → ...

After:   Type what you want → Watch it happen → Click to try
```

### The Inverted IDE

```
Traditional:   IDE is primary, AI is a feature
               User adapts to tool
               Fixed layout for all tasks

Sunwell:       AI is primary, editor is a window into it
               Tool adapts to user
               Layout changes per task
```

### Content is King

The UI exists to showcase your creation, not itself:
- No chrome (minimal window decorations)
- No distractions (panels appear only when needed)
- The work fills the space
- Typography and whitespace do the heavy lifting

---

## User Experience

### Launch State

The app opens to a single input. Nothing else.

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│                                                                 │
│                                                                 │
│                           ☀️                                    │
│                        SUNWELL                                  │
│                                                                 │
│                                                                 │
│     ┌───────────────────────────────────────────────────┐      │
│     │ What would you like to create?                    │      │
│     └───────────────────────────────────────────────────┘      │
│                                                                 │
│           Recent: The Lighthouse Keeper · forum-app            │
│                                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Working State

Progress streams in as the agent works:

```
┌─────────────────────────────────────────────────────────────────┐
│  forum-app                                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  > Build a forum app with users, posts, comments               │
│                                                                 │
│  ────────────────────────────────────────────────────────────  │
│                                                                 │
│  Building                                                       │
│  ├─ [1] User model                    ████████████████████  ✓  │
│  ├─ [2] Post model                    ████████████████████  ✓  │
│  ├─ [3] Comment model                 ████████████████████  ✓  │
│  ├─ [4] Auth routes                   ████████████░░░░░░░░     │
│  ├─ [5] Post routes                   ░░░░░░░░░░░░░░░░░░░░     │
│  └─ ...                                                        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Done State

A prominent button invites you to try your creation:

```
┌─────────────────────────────────────────────────────────────────┐
│  forum-app                                                      │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  > Build a forum app with users, posts, comments               │
│                                                                 │
│  ────────────────────────────────────────────────────────────  │
│                                                                 │
│  ✓ Done                                                8 tasks  │
│                                                                 │
│                                                                 │
│                     ┌─────────────────┐                        │
│                     │                 │                        │
│                     │    ▶ TRY IT     │                        │
│                     │                 │                        │
│                     └─────────────────┘                        │
│                                                                 │
│          files · terminal · edit                               │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Preview State

Click "TRY IT" and your creation runs inline:

```
┌─────────────────────────────────────────────────────────────────┐
│  forum-app › preview                                            │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │                                                         │   │
│  │                      MY FORUM                           │   │
│  │                                                         │   │
│  │  [register]  [login]                                   │   │
│  │                                                         │   │
│  │  Latest Posts                                           │   │
│  │  ─────────────────────────────────────────────────────  │   │
│  │  Welcome to the forum                                   │   │
│  │  posted by admin · 0 comments                          │   │
│  │                                                         │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│          ← back · open in browser · stop                       │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Adaptive Interface

The UI transforms based on what you're working on.

### Project Type Detection

```python
class ProjectDetector:
    """Detects project type from goal and context."""
    
    async def detect(self, goal: str, files: list[Path] | None) -> ProjectType:
        # Check existing files
        if files:
            if any(f.suffix == '.py' for f in files):
                return ProjectType.CODE_PYTHON
            if any(f.suffix == '.fountain' for f in files):
                return ProjectType.SCREENPLAY
            # ...
        
        # Infer from goal
        signals = await extract_signals(goal, self.model)
        
        if signals.domain == "code":
            return ProjectType.CODE
        if signals.domain == "fiction":
            return self._detect_fiction_type(goal)
        if signals.domain == "game":
            return ProjectType.GAME_DIALOGUE
        
        return ProjectType.GENERAL
```

### Layout Configurations

Each project type has a tailored layout:

**Code Project:**
```
┌──────────────┬────────────────────────────┬─────────────────────┐
│  📁 Files    │   📝 Code                  │  🧪 Tests          │
│  📦 Models   │   🔗 Related Docs          │  📊 Coverage       │
└──────────────┴────────────────────────────┴─────────────────────┘
```

**Novel Project:**
```
┌──────────────┬────────────────────────────┬─────────────────────┐
│  📑 Chapters │   ✍️ Writing               │  👥 Characters     │
│  🧵 Threads  │   💡 Remember              │  📊 Word Count     │
└──────────────┴────────────────────────────┴─────────────────────┘
```

**Screenplay Project:**
```
┌──────────────┬────────────────────────────┬─────────────────────┐
│  🎬 Scenes   │   ✍️ Script                │  🎭 Beat Sheet     │
│  ⏱ Timeline │   💬 Dialogue Style        │  📐 Format Check   │
└──────────────┴────────────────────────────┴─────────────────────┘
```

**Game Dialogue Project:**
```
┌──────────────┬────────────────────────────┬─────────────────────┐
│  👥 NPCs     │   🌳 Dialogue Tree         │  📋 Quest Info     │
│  📍 Location │   🎭 NPC State             │  🔗 Variables      │
└──────────────┴────────────────────────────┴─────────────────────┘
```

### Dynamic Panel Surfacing

The AI decides what's relevant for the current task:

```python
class AdaptiveLayout:
    """AI-driven layout that surfaces relevant context."""
    
    async def compute_layout(
        self,
        project: Project,
        current_task: str,
        memory: Simulacrum,
    ) -> Layout:
        # Understand the task
        task_analysis = await self.analyze_task(current_task)
        
        # Identify relevant entities
        entities = await self.extract_entities(task_analysis, memory)
        
        # Determine what user needs to know
        context_needs = await self.compute_context_needs(task_analysis)
        
        # Build layout with only relevant panels
        return Layout(
            primary=self.writing_panel(project.type),
            secondary=self.select_relevant_panels(entities, context_needs),
            alerts=self.compute_alerts(memory, task_analysis),
        )
    
    async def on_task_change(self, new_task: str):
        """Smoothly transition layout when task changes."""
        new_layout = await self.compute_layout(...)
        await self.animate_transition(self.current_layout, new_layout)
```

### AI Suggestions

The AI can proactively surface relevant information:

```
┌─────────────────────────────────────────────────────────────────┐
│                                                                 │
│  💡 AI Suggestion                                    [Dismiss]  │
│  ─────────────────────────────────────────────────────────────  │
│                                                                 │
│  "You're writing a scene set in 1987, but you referenced       │
│   smartphones in chapter 2. Should I show the timeline?"       │
│                                                                 │
│       [Show Timeline]    [It's intentional]    [Fix it]        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## One-Click Preview

The "▶ TRY IT" button is the core UX innovation. Zero friction from "done" to "experience."

### Preview by Project Type

| Project Type | Preview Mode |
|--------------|--------------|
| Web app (Flask, etc.) | Embedded browser, auto-start server |
| CLI tool | Embedded terminal with command pre-filled |
| Novel chapter | Formatted prose reader |
| Screenplay | Fountain-formatted script view |
| Game dialogue | Interactive dialogue player |
| API | Swagger/OpenAPI UI |
| Static site | Embedded browser |

### Implementation

```python
class PreviewManager:
    """Manages one-click preview for all project types."""
    
    async def launch(self, project: Project) -> PreviewSession:
        match project.type:
            case ProjectType.CODE_WEB:
                return await self._launch_web_app(project)
            case ProjectType.CODE_CLI:
                return await self._launch_cli(project)
            case ProjectType.NOVEL:
                return await self._launch_prose_reader(project)
            case ProjectType.SCREENPLAY:
                return await self._launch_fountain_viewer(project)
            case ProjectType.GAME_DIALOGUE:
                return await self._launch_dialogue_player(project)
    
    async def _launch_web_app(self, project: Project) -> PreviewSession:
        # Detect framework
        framework = self.detect_framework(project.path)
        
        # Install dependencies if needed
        if not (project.path / "venv").exists():
            await self.install_deps(project)
        
        # Find free port
        port = self.find_free_port()
        
        # Start server
        process = await self.start_server(project, framework, port)
        
        # Wait for ready
        await self.wait_for_ready(f"http://localhost:{port}")
        
        return PreviewSession(
            url=f"http://localhost:{port}",
            process=process,
            view_type="webview",
        )
    
    async def _launch_prose_reader(self, project: Project) -> PreviewSession:
        # Render chapter as formatted HTML
        content = await self.render_prose(project.current_chapter)
        
        return PreviewSession(
            content=content,
            view_type="prose",
            navigation={
                "prev": project.previous_chapter,
                "next": project.next_chapter,
            },
        )
```

### Dialogue Preview Player

For game projects, an interactive dialogue tester:

```
┌─────────────────────────────────────────────────────────────────┐
│  🎮 Dialogue Preview — Gretchen                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│   ┌───────────────────────────────────────────────────────┐    │
│   │                                                       │    │
│   │  GRETCHEN                                             │    │
│   │  "Welcome to the Rusty Anchor, stranger. What'll     │    │
│   │   it be? Ale, information, or trouble?"              │    │
│   │                                                       │    │
│   └───────────────────────────────────────────────────────┘    │
│                                                                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │  [1] "Just an ale, thanks."                            │  │
│   │  [2] "I'm looking for someone."                        │  │
│   │  [3] "Trouble? Who said anything about trouble?"       │  │
│   │  [4] [Leave]                                            │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                 │
│   Variables: met_gretchen=true, quest_started=false            │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Simulacrum Integration

Sunwell Studio is deeply integrated with Simulacrum for persistent memory.

### Session Management

```
┌─────────────────────────────────────────────────────────────────┐
│  ☀️ SUNWELL                                                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  Recent Projects                                                │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  📖 The Lighthouse Keeper                               │   │
│  │      Novel · Chapter 3 of 12 · 23,450 words            │   │
│  │      12 characters · 4 plot threads                     │   │
│  │      Last edited: 2 hours ago                          │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  🔧 forum-app                                           │   │
│  │      Flask · 8 files · Ready to run                    │   │
│  │      5 learnings · 0 dead ends                         │   │
│  │      Last edited: yesterday                            │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │  🎬 Untitled Noir                                       │   │
│  │      Screenplay · 47 scenes · 89 pages                 │   │
│  │      Last edited: 3 days ago                           │   │
│  └─────────────────────────────────────────────────────────┘   │
│                                                                 │
│     ┌───────────────────────────────────────────────────┐      │
│     │ Start something new...                            │      │
│     └───────────────────────────────────────────────────┘      │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Memory Display

For creative projects, show what the AI remembers:

```
┌─────────────────────────────────────────────────────────────────┐
│  🧠 Memory — The Lighthouse Keeper                  [Manage →]  │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  👥 Characters (12)                                            │
│  ├─ Sarah (protagonist) — detective, 34, green eyes            │
│  ├─ Marcus (antagonist?) — Sarah's ex, presumed dead           │
│  ├─ Chen — Sarah's partner, loyal                              │
│  └─ [+9 more]                                                  │
│                                                                 │
│  🧵 Plot Threads (4)                                           │
│  ├─ The missing artifact — introduced ch2, unresolved          │
│  ├─ Sarah's past — introduced ch1, unresolved                  │
│  ├─ Marcus's betrayal — introduced ch3, unresolved             │
│  └─ The lighthouse secret — hinted ch1, unresolved             │
│                                                                 │
│  🌍 World Rules (3)                                            │
│  ├─ Set in coastal Maine, present day                          │
│  ├─ The lighthouse has been dark for 3 years                   │
│  └─ Sarah and Marcus were married for 5 years                  │
│                                                                 │
│  📝 Style                                                       │
│  └─ Third person limited (Sarah), past tense, noir tone        │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## Visual Design

### Color Palette

```css
:root {
  /* Backgrounds */
  --bg-primary: #0d0d0d;      /* Almost black */
  --bg-secondary: #1a1a1a;    /* Cards, panels */
  --bg-tertiary: #262626;     /* Hover states */
  --bg-elevated: #2a2a2a;     /* Modals, dropdowns */
  
  /* Text */
  --text-primary: #e5e5e5;    /* Main text */
  --text-secondary: #8b8b8b;  /* Muted text */
  --text-tertiary: #525252;   /* Very muted */
  
  /* Accent */
  --accent: #f5f5f5;          /* Buttons, focus */
  --accent-muted: #404040;    /* Borders */
  
  /* Semantic */
  --success: #22c55e;
  --warning: #eab308;
  --error: #ef4444;
  --info: #3b82f6;
}
```

### Typography

```css
:root {
  /* Fonts */
  --font-mono: 'Berkeley Mono', 'SF Mono', 'Fira Code', monospace;
  --font-sans: 'Inter', -apple-system, sans-serif;
  --font-serif: 'Newsreader', 'Georgia', serif;  /* For prose */
  
  /* Sizes */
  --text-xs: 11px;
  --text-sm: 13px;
  --text-base: 15px;
  --text-lg: 17px;
  --text-xl: 21px;
  --text-2xl: 28px;
}

/* Default: monospace for UI */
body {
  font-family: var(--font-mono);
  font-size: var(--text-base);
  line-height: 1.5;
}

/* Prose content: serif for readability */
.prose {
  font-family: var(--font-serif);
  font-size: var(--text-lg);
  line-height: 1.8;
  max-width: 65ch;
}

/* Code content: monospace */
.code {
  font-family: var(--font-mono);
  font-size: var(--text-sm);
  line-height: 1.6;
}
```

### Components

**Input Bar:**
```
┌──────────────────────────────────────────────────────────────┐
│ What would you like to create?                          ⏎    │
└──────────────────────────────────────────────────────────────┘

- Rounded corners (8px)
- Subtle border (#404040)
- Focus glow (white, 10% opacity)
- Placeholder text (#525252)
```

**Progress Bar:**
```
├─ [3] Comment model                 ████████████████████  ✓  │

- Inline with task name
- Thin (4px height)
- Color: white when in progress, green when complete
- Monospace numbers
```

**Primary Button:**
```
         ┌─────────────────┐
         │                 │
         │    ▶ TRY IT     │
         │                 │
         └─────────────────┘

- Large touch target (min 48px height)
- High contrast (white on near-black)
- Subtle hover state (lighten 5%)
- Play icon (▶) signals action
```

**Navigation Links:**
```
         ← back · edit · export

- Text links, not buttons
- Separated by middot (·)
- Muted color, brighten on hover
- No underlines
```

**Alert/Suggestion:**
```
┌─────────────────────────────────────────────────────────────┐
│  💡 Marcus doesn't know Sarah found the letter             │
└─────────────────────────────────────────────────────────────┘

- Subtle background (#1a1a1a)
- Left border accent (white, 2px)
- Dismissable
- Emoji for quick recognition
```

### Animation

Principles:
- **Subtle**: Never flashy or attention-grabbing
- **Fast**: 150-200ms for most transitions
- **Purposeful**: Animation should communicate state change
- **Reducible**: Respect `prefers-reduced-motion`

```css
/* Standard transition */
.panel {
  transition: opacity 150ms ease, transform 150ms ease;
}

/* Panel entrance */
.panel-enter {
  opacity: 0;
  transform: translateY(8px);
}
.panel-enter-active {
  opacity: 1;
  transform: translateY(0);
}

/* Progress bar */
.progress-bar {
  transition: width 300ms ease-out;
}

/* Respect user preferences */
@media (prefers-reduced-motion: reduce) {
  * {
    transition: none !important;
    animation: none !important;
  }
}
```

---

## Technical Architecture

### Stack

**Tauri** — The app shell
- Rust backend for performance and security
- Small bundle size (~10MB vs Electron's 200MB+)
- Native OS integration (file dialogs, notifications, etc.)
- Web frontend for UI flexibility

**Svelte** — The frontend
- Compiles away (no runtime overhead)
- Simple, readable component syntax
- Reactive by default
- Fast

**Sunwell Core** — The AI engine
- Python-based agent (existing codebase)
- Communicates with Tauri via IPC
- Runs as subprocess or connects to local server

### Project Structure

```
sunwell-studio/
├── src-tauri/                    # Rust backend
│   ├── src/
│   │   ├── main.rs              # Entry point
│   │   ├── commands.rs          # IPC commands
│   │   ├── preview.rs           # Preview management
│   │   ├── project.rs           # Project detection
│   │   └── agent.rs             # Sunwell agent bridge
│   ├── Cargo.toml
│   └── tauri.conf.json
│
├── src/                          # Svelte frontend
│   ├── App.svelte               # Root component
│   ├── routes/
│   │   ├── Home.svelte          # Launch screen
│   │   ├── Project.svelte       # Working screen
│   │   └── Preview.svelte       # Preview screen
│   ├── components/
│   │   ├── InputBar.svelte
│   │   ├── Progress.svelte
│   │   ├── Panel.svelte
│   │   ├── Button.svelte
│   │   └── ...
│   ├── layouts/
│   │   ├── CodeLayout.svelte
│   │   ├── NovelLayout.svelte
│   │   ├── ScreenplayLayout.svelte
│   │   └── GameLayout.svelte
│   ├── stores/
│   │   ├── project.ts
│   │   ├── agent.ts
│   │   └── layout.ts
│   └── styles/
│       ├── reset.css
│       ├── variables.css
│       └── global.css
│
├── package.json
└── vite.config.ts
```

### Agent Communication

```rust
// src-tauri/src/agent.rs

use std::process::{Command, Stdio};
use tokio::io::{AsyncBufReadExt, BufReader};

pub struct AgentBridge {
    process: Option<Child>,
}

impl AgentBridge {
    pub async fn run_goal(&mut self, goal: &str) -> impl Stream<Item = AgentEvent> {
        // Start Sunwell agent as subprocess
        let mut child = Command::new("python")
            .args(["-m", "sunwell", "--json", goal])
            .stdout(Stdio::piped())
            .spawn()
            .expect("Failed to start agent");
        
        let stdout = child.stdout.take().unwrap();
        let reader = BufReader::new(stdout);
        
        // Stream events as they arrive
        reader.lines().map(|line| {
            let line = line.unwrap();
            serde_json::from_str::<AgentEvent>(&line).unwrap()
        })
    }
}
```

```typescript
// src/stores/agent.ts

import { invoke } from '@tauri-apps/api/tauri';
import { listen } from '@tauri-apps/api/event';
import { writable } from 'svelte/store';

export const agentState = writable<AgentState>({
  status: 'idle',
  tasks: [],
  currentTask: null,
});

export async function runGoal(goal: string) {
  agentState.update(s => ({ ...s, status: 'running' }));
  
  // Listen for streaming events
  const unlisten = await listen('agent-event', (event) => {
    const data = event.payload as AgentEvent;
    handleAgentEvent(data);
  });
  
  // Start the agent
  await invoke('run_goal', { goal });
  
  unlisten();
}

function handleAgentEvent(event: AgentEvent) {
  switch (event.type) {
    case 'task_start':
      agentState.update(s => ({
        ...s,
        currentTask: event.data.task,
      }));
      break;
    case 'task_complete':
      agentState.update(s => ({
        ...s,
        tasks: [...s.tasks, { ...event.data.task, status: 'complete' }],
      }));
      break;
    case 'complete':
      agentState.update(s => ({ ...s, status: 'done' }));
      break;
  }
}
```

### Preview System

```rust
// src-tauri/src/preview.rs

use std::process::Command;
use std::net::TcpListener;

pub struct PreviewManager {
    active_previews: HashMap<String, PreviewSession>,
}

impl PreviewManager {
    pub async fn launch(&mut self, project: &Project) -> Result<PreviewSession> {
        match project.project_type {
            ProjectType::WebApp => self.launch_web_app(project).await,
            ProjectType::Novel => self.launch_prose_reader(project).await,
            ProjectType::Screenplay => self.launch_fountain_viewer(project).await,
            ProjectType::GameDialogue => self.launch_dialogue_player(project).await,
            _ => self.launch_generic(project).await,
        }
    }
    
    async fn launch_web_app(&mut self, project: &Project) -> Result<PreviewSession> {
        // Detect framework
        let framework = detect_framework(&project.path)?;
        
        // Find free port
        let port = find_free_port()?;
        
        // Start server based on framework
        let process = match framework {
            Framework::Flask => {
                Command::new("python")
                    .args(["-m", "flask", "run", "--port", &port.to_string()])
                    .current_dir(&project.path)
                    .spawn()?
            }
            Framework::FastAPI => {
                Command::new("uvicorn")
                    .args(["main:app", "--port", &port.to_string()])
                    .current_dir(&project.path)
                    .spawn()?
            }
            // ... other frameworks
        };
        
        // Wait for server to be ready
        wait_for_server(&format!("http://localhost:{}", port)).await?;
        
        Ok(PreviewSession {
            url: format!("http://localhost:{}", port),
            process: Some(process),
            view_type: ViewType::WebView,
        })
    }
}

fn find_free_port() -> Result<u16> {
    let listener = TcpListener::bind("127.0.0.1:0")?;
    Ok(listener.local_addr()?.port())
}
```

---

## Implementation Plan

### Phase 1: Foundation (Weeks 1-2)

- [ ] Tauri + Svelte project setup
- [ ] Basic window with launch screen
- [ ] Dark theme implementation
- [ ] Input bar component
- [ ] Connect to Sunwell agent (subprocess)
- [ ] Basic event streaming

**Deliverable**: App that accepts goal, runs agent, shows raw output

### Phase 2: Progress UX (Weeks 3-4)

- [ ] Task progress component
- [ ] Streaming progress display
- [ ] Done state with "TRY IT" button
- [ ] Basic navigation (back, home)
- [ ] Error states

**Deliverable**: App with proper progress visualization

### Phase 3: Preview System (Weeks 5-6)

- [ ] Framework detection (Flask, FastAPI, Node, etc.)
- [ ] Web app preview (embedded webview)
- [ ] Server lifecycle management
- [ ] "Open in browser" fallback
- [ ] Preview error handling

**Deliverable**: One-click preview for web apps

### Phase 4: Adaptive Layouts (Weeks 7-8)

- [ ] Project type detection
- [ ] Code project layout
- [ ] Novel project layout
- [ ] Layout switching animation
- [ ] Panel components (files, characters, etc.)

**Deliverable**: UI that changes based on project type

### Phase 5: Creative Modes (Weeks 9-10)

- [ ] Prose reader preview
- [ ] Screenplay (Fountain) preview
- [ ] Dialogue tree preview
- [ ] Character/entity panels
- [ ] Memory display panels

**Deliverable**: Full support for non-code projects

### Phase 6: Simulacrum Integration (Weeks 11-12)

- [ ] Session management UI
- [ ] Recent projects list
- [ ] Memory browser
- [ ] Session resume
- [ ] Cross-session learning display

**Deliverable**: Persistent memory integrated into UI

### Phase 7: Polish (Weeks 13-14)

- [ ] Keyboard shortcuts
- [ ] Accessibility audit
- [ ] Performance optimization
- [ ] Edge case handling
- [ ] Documentation

**Deliverable**: Production-ready application

### Phase 8: Distribution (Weeks 15-16)

- [ ] macOS build + signing
- [ ] Windows build + signing
- [ ] Linux build (AppImage, deb)
- [ ] Auto-update system
- [ ] Landing page

**Deliverable**: Downloadable app for all platforms

---

## Metrics

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Time to first interaction | < 3s | App launch to input ready |
| Time to preview | < 2s after done | Click TRY IT to visible app |
| Bundle size | < 20MB | Compressed download |
| Memory usage | < 200MB | During typical use |
| First-run experience | < 30s | Install to seeing first output |

---

## Open Questions

1. **Should the app bundle Ollama/models?**
   - Pro: True "download and go" experience
   - Con: Much larger bundle, complex updates
   - Leaning: No, require Ollama installed separately (like requiring Python)

2. **Web version?**
   - Could offer a hosted version for those who don't want to install
   - Would require cloud backend (defeats local-first)
   - Leaning: Desktop-first, web later if demand

3. **Mobile apps?**
   - Tauri supports mobile (iOS, Android)
   - Different UX challenges on small screens
   - Leaning: Desktop-first, mobile much later

4. **Plugin system?**
   - Could allow community-built preview modes, layouts, etc.
   - Adds complexity
   - Leaning: Not in v1, consider for v2

---

## References

### Internal
- RFC-042: Adaptive Agent (event streaming, Simulacrum)
- Sunwell agent codebase (`src/sunwell/`)

### External
- [Tauri](https://tauri.app/) — App framework
- [Svelte](https://svelte.dev/) — UI framework
- [Ollama](https://ollama.ai/) — Design inspiration
- [Linear](https://linear.app/) — Clean UI inspiration
- [Obsidian](https://obsidian.md/) — Local-first inspiration

---

## Appendix: Design Mockups

### Launch Screen (Full)

```
┌─────────────────────────────────────────────────────────────────┐
│                                                         ─  □  x │
│                                                                 │
│                                                                 │
│                                                                 │
│                                                                 │
│                                                                 │
│                           ☀️                                    │
│                                                                 │
│                        SUNWELL                                  │
│                                                                 │
│                                                                 │
│                                                                 │
│     ┌───────────────────────────────────────────────────┐      │
│     │ What would you like to create?                  ⏎ │      │
│     └───────────────────────────────────────────────────┘      │
│                                                                 │
│                                                                 │
│     Recent                                                      │
│                                                                 │
│     📖 The Lighthouse Keeper          Novel · Ch 3 · 2h ago    │
│     🔧 forum-app                      Flask · Ready · 1d ago    │
│     🎬 Untitled Noir                  Script · 89p · 3d ago    │
│                                                                 │
│                                                                 │
│                                                                 │
│                                                                 │
│                                                     v0.1.0      │
└─────────────────────────────────────────────────────────────────┘
```

### Working Screen (Full)

```
┌─────────────────────────────────────────────────────────────────┐
│  forum-app                                              ─  □  x │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  > Build a forum app with users, posts, and comments           │
│                                                                 │
│  ────────────────────────────────────────────────────────────  │
│                                                                 │
│  📋 Planning                                                    │
│  └─ 8 tasks identified                                  2.3s   │
│                                                                 │
│  ⚡ Building                                                    │
│                                                                 │
│  ├─ [1] User model                    ████████████████████  ✓  │
│  ├─ [2] Post model                    ████████████████████  ✓  │
│  ├─ [3] Comment model                 ████████████████████  ✓  │
│  ├─ [4] Auth routes                   ████████████████████  ✓  │
│  ├─ [5] Post routes                   ████████████░░░░░░░░     │
│  ├─ [6] Comment routes                ░░░░░░░░░░░░░░░░░░░░     │
│  ├─ [7] Database setup                ░░░░░░░░░░░░░░░░░░░░     │
│  └─ [8] App factory                   ░░░░░░░░░░░░░░░░░░░░     │
│                                                                 │
│  📝 Working on: post routes with CRUD operations...            │
│                                                                 │
│                                                                 │
│                                                                 │
│                                                                 │
│                                                        45s      │
└─────────────────────────────────────────────────────────────────┘
```

### Done Screen (Full)

```
┌─────────────────────────────────────────────────────────────────┐
│  forum-app                                              ─  □  x │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  > Build a forum app with users, posts, and comments           │
│                                                                 │
│  ────────────────────────────────────────────────────────────  │
│                                                                 │
│  ✓ Done                                            8 tasks 67s  │
│                                                                 │
│                                                                 │
│                                                                 │
│                                                                 │
│                                                                 │
│                     ┌─────────────────────┐                    │
│                     │                     │                    │
│                     │      ▶ TRY IT       │                    │
│                     │                     │                    │
│                     └─────────────────────┘                    │
│                                                                 │
│                                                                 │
│                                                                 │
│                                                                 │
│                                                                 │
│              files · terminal · edit · rebuild                 │
│                                                                 │
│                                                                 │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

### Novel Writing (Full)

```
┌─────────────────────────────────────────────────────────────────┐
│  The Lighthouse Keeper                                  ─  □  x │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  > Write the confrontation at the lighthouse                   │
│                                                                 │
│  ────────────────────────────────────────────────────────────  │
│                                                                 │
│                                                                 │
│                                                                 │
│        Sarah's boots crunched on the gravel path leading       │
│     to the old lighthouse. The beam hadn't turned in three     │
│     years—not since the night Marcus disappeared.              │
│                                                                 │
│        She pulled her coat tighter against the November        │
│     wind. The letter in her pocket felt heavier than paper     │
│     had any right to be.                                       │
│                                                                 │
│        "You came."                                              │
│                                                                 │
│        She didn't turn. She'd know that voice anywhere.        │
│                                                                 │
│        "I wasn't sure you would," Marcus said, stepping        │
│     out from the shadow of the lighthouse door.                │
│                                                                 │
│                                                                 │
│                              ▪ ▪ ▪                              │
│                                                                 │
│                                                                 │
│         ← ch 2 · edit · regenerate · ch 4 →         847 words  │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

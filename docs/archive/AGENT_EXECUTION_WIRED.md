# Agent Execution Wired Up! 🎉

The Chirp frontend is now fully wired to execute background agent tasks using your local Ollama models.

## What Was Implemented

### 1. Project Agent Execution (`/projects/{project_id}/run`)
- **File**: `src/sunwell/interface/chirp/pages/projects/{project_id}/run.py`
- **Features**:
  - Accepts optional goal description from form input
  - Initializes Ollama model from config (prefers `naaru.wisdom` model)
  - Creates ToolExecutor with project context
  - Loads PersistentMemory for the project
  - Spawns background session via BackgroundManager
  - Returns session ID for tracking

### 2. Goal Agent Execution (`/backlog/goals/{goal_id}/run`)
- **File**: `src/sunwell/interface/chirp/pages/backlog/goals/{goal_id}/run.py`
- **Features**:
  - Uses goal description as agent's objective
  - Resolves project from registry (default or current directory)
  - Same model/executor/memory setup as project execution
  - Spawns background session for goal completion

### 3. Background Task Helper
- **File**: `src/sunwell/interface/chirp/helpers/background.py`
- **Features**:
  - Manages persistent event loop in background thread
  - Allows synchronous Chirp handlers to spawn async background tasks
  - Uses `run_coroutine_threadsafe()` for proper async scheduling
  - Background tasks continue running after HTTP response returns

### 4. UI Enhancements
- **Project Page**: Added goal input field for custom instructions
- **Form Styling**: Clean input with placeholder text
- **Status Messages**: Shows session ID when execution starts

## How to Test

### Prerequisites
1. **Ollama Running**: Make sure Ollama is running at `http://localhost:11434`
   ```bash
   ollama serve
   ```

2. **Models Available**: Verify you have models pulled
   ```bash
   ollama list
   # Should show: gemma3:12b, gemma3:4b, qwen2.5:1.5b, etc.
   ```

3. **Start Chirp**: Launch the Chirp interface
   ```bash
   cd /Users/llane/Documents/github/python/sunwell
   python -m sunwell.interface.chirp.main
   # Or however you start the Chirp server
   ```

### Test Scenarios

#### Test 1: Project Execution with Default Goal
1. Navigate to a project detail page (e.g., `/projects/sunwell`)
2. Leave the goal field empty
3. Click "Run Agent"
4. **Expected**: See message "Agent execution started for [project name]! Session ID: bg-xxxxxxxx"
5. **Result**: Agent will run with default goal: "Analyze and improve code in [project name]"

#### Test 2: Project Execution with Custom Goal
1. Navigate to a project detail page
2. Enter custom goal: "Add docstrings to all functions in src/sunwell/memory"
3. Click "Run Agent"
4. **Expected**: Session starts with your custom goal
5. **Result**: Agent will work on your specific objective

#### Test 3: Goal Execution from Backlog
1. Navigate to Backlog (`/backlog`)
2. Click on a goal to view details
3. Click "Run Agent" button
4. **Expected**: Session starts with goal description
5. **Result**: Agent works on completing the backlog goal

#### Test 4: Verify Background Execution
1. After starting an agent, immediately navigate away from the page
2. Check Observatory (`/observatory`) to see running sessions
3. **Expected**: Session continues running in background
4. **Result**: Files will be modified even after you left the page

### Monitoring Sessions

**Observatory Page** (`/observatory`):
- Shows all background sessions
- View session status (pending, running, completed, failed)
- See session IDs, goals, and timestamps
- Track which files were modified

**Session Status**:
- `pending`: Session created but not started yet
- `running`: Agent is actively working
- `completed`: Successfully finished
- `failed`: Encountered an error
- `cancelled`: User cancelled the session

## Configuration

### Model Selection
The system uses models from your config (`.sunwell/config.yaml`):
- **Default Provider**: `model.default_provider` (ollama)
- **Default Model**: `model.default_model` (claude-sonnet-4-5 if using Anthropic)
- **Ollama Wisdom Model**: `naaru.wisdom` (gemma3:12b in your config)

For **local Ollama execution**, the system will use `naaru.wisdom` model, which in your config is `gemma3:12b`.

### Override Model
To use a different model, edit `.sunwell/config.yaml`:
```yaml
naaru:
  wisdom: gemma3:12b  # Change to any Ollama model
```

Or change the default:
```yaml
model:
  default_provider: ollama
  default_model: llama3.1:8b
```

## Troubleshooting

### Error: "Project not found"
- Make sure you have projects registered in the registry
- Create a project via `/projects` page or use CLI: `sunwell project init`

### Error: "No project found" (Goal execution)
- Set a default project: `/projects/{project_id}/set-default`
- Or run from a project directory

### Error: Model not found
- Pull the model: `ollama pull gemma3:12b`
- Check available models: `ollama list`
- Update config to use available model

### Error: Connection refused (Ollama)
- Start Ollama: `ollama serve`
- Check Ollama is at `http://localhost:11434`
- Update config if using different URL

### Agent not working
- Check logs in `.sunwell/logs/`
- View Observatory for session status and errors
- Verify ToolExecutor has proper permissions for project

## Next Steps

### Enhancements You Can Add:
1. **Cancel Button**: Add UI to cancel running sessions
2. **Progress Updates**: Show real-time progress via SSE
3. **Session History**: Detailed view of completed sessions
4. **Retry Failed**: Button to retry failed sessions
5. **Queue Limit**: Prevent too many concurrent executions

### Integration Ideas:
1. **Auto-Run Goals**: Automatically run high-priority backlog goals
2. **Scheduled Tasks**: Cron-like scheduling for recurring goals
3. **Webhooks**: Trigger executions from external events
4. **CI/CD Integration**: Run agents on git push/PR events

## Files Modified

- `src/sunwell/interface/chirp/pages/projects/{project_id}/run.py` - Project execution endpoint
- `src/sunwell/interface/chirp/pages/projects/{project_id}/page.html` - Added goal input form
- `src/sunwell/interface/chirp/pages/backlog/goals/{goal_id}/run.py` - Goal execution endpoint
- `src/sunwell/interface/chirp/helpers/background.py` - Background task spawning helper (NEW)
- `src/sunwell/interface/chirp/helpers/__init__.py` - Helpers package init (NEW)

## Technical Details

### Architecture
- **Synchronous Handlers**: Chirp uses sync request handlers
- **Async Spawning**: BackgroundManager.spawn() is async
- **Event Loop Bridge**: Custom helper creates persistent background event loop
- **Thread-Safe**: Uses `run_coroutine_threadsafe()` for cross-thread scheduling

### Background Loop
- Runs in daemon thread named "chirp-background"
- Persists for lifetime of Chirp server
- All background tasks execute in this single loop
- Automatically cleaned up when server stops

### Memory Safety
- Each project gets its own PersistentMemory instance
- Memory loaded fresh for each execution
- No shared state between sessions

---

**Status**: ✅ Ready for testing!
**Models Used**: Local Ollama (gemma3:12b via naaru.wisdom)
**Execution**: Background threads with persistent event loop
**UI**: Fully functional with session tracking

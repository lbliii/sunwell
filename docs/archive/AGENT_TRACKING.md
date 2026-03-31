# Agent Execution Tracking - User Visibility

## ✅ **Full Visibility Implemented!**

Users now have complete visibility into background agent execution with live updates.

## User Journey

### 1. **Start an Agent Task**

From Project page (`/projects/sunwell`):
- Enter optional goal description
- Click "Run Agent"
- Get immediate feedback with action buttons

**Success Message:**
```
✅ Agent execution started for sunwell!
[View All Sessions →] [Track This Session →]
```

### 2. **Track Live Progress**

Click "Track This Session" to go to session detail page:

**Session Detail Page** (`/observatory/runs/{session_id}`):
- Shows real-time status (🔴 Live indicator)
- Auto-refreshes every 2 seconds while running
- Displays:
  - Current status (pending/running/completed/failed)
  - Start time and duration
  - Tasks completed
  - Files changed
  - Error details (if failed)
  - Result summary (when complete)

**Live Updates:**
- Status changes from "pending" → "running" → "completed"
- Task count increments as work progresses
- Files list populates as changes are made
- Duration updates in real-time

### 3. **View All Sessions**

Observatory page (`/observatory`):
- Lists all background sessions
- Shows status at-a-glance
- Click any session to see details
- Filter by status (future enhancement)

## What Users See

### Running Session:
```
🔴 Live
Status: running
Started: 2 minutes ago
Duration: 120s
Tasks Completed: 3
Files Changed: 2

↻ Auto-refreshing every 2 seconds...
```

### Completed Session:
```
Status: completed
Started: 5 minutes ago
Duration: 287s
Tasks Completed: 8
Files Changed: 5

✅ Session completed!

Summary:
Added type hints and docstrings to 5 helper functions.
Updated imports and fixed formatting issues.

Files Changed:
- src/sunwell/interface/chirp/helpers/background.py
- src/sunwell/interface/chirp/pages/projects/{project_id}/run.py
- ...
```

### Failed Session:
```
Status: failed
Started: 1 minute ago
Duration: 45s

❌ Session failed. See error details below.

Error:
Anthropic not installed. Run: pip install sunwell[anthropic]
```

## Features

### Auto-Refresh
- **Enabled**: When status is "pending" or "running"
- **Frequency**: Every 2 seconds
- **Stops**: Automatically when session completes/fails
- **Technology**: HTMX polling (`hx-trigger="every 2s"`)

### Visual Indicators
- 🔴 **Live indicator**: Pulsing red dot for running sessions
- ✅ **Success badge**: Green for completed
- ❌ **Error badge**: Red for failed
- ⏳ **Pending badge**: Blue for queued

### Navigation
- **Breadcrumbs**: Easy navigation back to Observatory
- **Quick Actions**: Jump to session from success message
- **Session List**: Browse all sessions in Observatory

## Technical Details

### Components Created:
1. **`_action_status.html`** - Success message with navigation links
2. **`status.py`** - Live status endpoint for polling
3. **`_status.html`** - Status fragment for HTMX updates
4. **Updated run endpoints** - Return session_id for tracking

### Endpoints:
- `POST /projects/{id}/run` → Returns session_id + links
- `POST /backlog/goals/{id}/run` → Returns session_id + links
- `GET /observatory` → Lists all sessions
- `GET /observatory/runs/{id}` → Session detail with auto-refresh
- `GET /observatory/runs/{id}/status` → Live status updates (HTMX)

### Data Flow:
```
User clicks "Run Agent"
  ↓
POST /projects/{id}/run
  ↓
spawn_background_session()
  ↓
Returns session_id
  ↓
User clicks "Track This Session"
  ↓
GET /observatory/runs/{session_id}
  ↓
Page loads with HTMX polling
  ↓
Every 2s: GET /observatory/runs/{session_id}/status
  ↓
Updates status, tasks, files in real-time
  ↓
Stops polling when complete/failed
```

## Future Enhancements

### Phase 2:
- **Canvas Visualizations**: ResonanceWave, PrismFracture, ExecutionCinema
- **Event Timeline**: Detailed step-by-step execution log
- **File Diff Viewer**: See exactly what changed
- **Replay Mode**: Step through execution history
- **Notifications**: Browser notifications when tasks complete

### Nice-to-Have:
- **Session Filters**: Filter by status/date/project
- **Search**: Find sessions by goal text
- **Favorites**: Star important sessions
- **Export**: Download session logs
- **Compare**: Compare two sessions side-by-side

## User Benefits

✅ **Immediate Feedback**: Know the task started successfully
✅ **Live Progress**: See work happening in real-time
✅ **Navigate Away**: Can leave page, task continues
✅ **Check Anytime**: Return to Observatory to see status
✅ **Error Clarity**: Clear error messages when things fail
✅ **Result Summary**: Know what was accomplished
✅ **File Tracking**: See exactly what changed

## Example Workflow

```bash
# 1. User opens Chirp
python test_agent_execution.py

# 2. Navigate to project
http://127.0.0.1:8888/projects/sunwell

# 3. Enter goal
"Add docstrings to helper functions"

# 4. Click "Run Agent"
→ ✅ Agent execution started!
  [View All Sessions] [Track This Session →]

# 5. Click "Track This Session"
→ Shows live page with:
  🔴 Live
  Status: running
  Tasks: 0 → 1 → 2 → 3
  Files: 0 → 1 → 2
  ↻ Auto-refreshing...

# 6. After 2 minutes...
  Status: completed ✅
  Tasks: 5
  Files: 3

  Summary: Added docstrings to all helper functions

  Files Changed:
  - background.py
  - run.py
  - status.py
```

## Testing

```bash
# Start server
python test_agent_execution.py

# Run agent on a project
curl -X POST http://127.0.0.1:8888/projects/sunwell/run \
  --data "goal=Test task"

# Check session list
curl http://127.0.0.1:8888/observatory

# View specific session (replace ID)
curl http://127.0.0.1:8888/observatory/runs/bg-abc123

# Poll for status updates
while true; do
  curl http://127.0.0.1:8888/observatory/runs/bg-abc123/status
  sleep 2
done
```

---

**Status**: ✅ **Fully Functional**
**UX**: Excellent - Users have full visibility
**Performance**: Efficient - Polling only when active
**Maintainability**: Clean - Follows Chirp patterns

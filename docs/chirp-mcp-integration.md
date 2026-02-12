# Chirp MCP Integration Architecture

**Status**: In Progress
**Date**: 2026-02-11

## Overview

Integrate Chirp's built-in MCP tool system (`@app.tool()`) into Sunwell UI, exposing Sunwell's capabilities via MCP protocol while maintaining the existing web interface.

## Architecture

```
┌─────────────────────────────────────────────────────────────┐
│  External AI Agents (Claude Desktop, Cursor, etc.)         │
│                                                              │
│  POST /mcp {"method": "tools/call", "params": {...}}       │
└──────────────────────┬──────────────────────────────────────┘
                       │ JSON-RPC (MCP Protocol)
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  Chirp App (chirp.tools built-in MCP server)               │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                              │
│  @app.tool("sunwell_add_goal")                              │
│  @app.tool("sunwell_search")                                │
│  @app.tool("sunwell_recall")                                │
│  @app.tool("sunwell_lens")                                  │
│                                                              │
│  ToolEventBus → Real-time activity monitoring               │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  Tool Wrapper Layer (src/sunwell/interface/chirp/tools/)   │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                              │
│  - tools/backlog.py    → BacklogService wrapper             │
│  - tools/knowledge.py  → KnowledgeService wrapper           │
│  - tools/memory.py     → MemoryService wrapper              │
│  - tools/planning.py   → PlanningService wrapper            │
│  - tools/execution.py  → ExecutionService wrapper           │
│  - tools/lens.py       → LensService wrapper                │
└──────────────────────┬──────────────────────────────────────┘
                       │
                       ↓
┌─────────────────────────────────────────────────────────────┐
│  Sunwell Core Services                                      │
│  ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ │
│                                                              │
│  - BacklogService                                           │
│  - KnowledgeService                                         │
│  - MemoryService                                            │
│  - PlanningService                                          │
│  - ExecutionService                                         │
│  - LensLoader / LensDiscovery                               │
└─────────────────────────────────────────────────────────────┘
```

## Tool Categories

### 1. Backlog Tools (`tools/backlog.py`)
| Tool | Description | Parameters |
|------|-------------|------------|
| `sunwell_add_goal` | Add a goal to backlog | title, description, priority? |
| `sunwell_list_goals` | List goals by status | status?, limit? |
| `sunwell_search_goals` | Search goals | query |
| `sunwell_update_goal` | Update goal status | goal_id, status |
| `sunwell_get_goal` | Get goal details | goal_id |

### 2. Knowledge Tools (`tools/knowledge.py`)
| Tool | Description | Parameters |
|------|-------------|------------|
| `sunwell_search` | Semantic search codebase | query, scope?, limit? |
| `sunwell_ask` | Ask a question about code | question |
| `sunwell_codebase` | Get codebase structure | aspect? |
| `sunwell_workspace` | List known projects | - |

### 3. Memory Tools (`tools/memory.py`)
| Tool | Description | Parameters |
|------|-------------|------------|
| `sunwell_briefing` | Get rolling briefing | format? |
| `sunwell_recall` | Query learnings | query, scope? |
| `sunwell_lineage` | Get artifact provenance | file_path |
| `sunwell_session` | Get session history | - |

### 4. Planning Tools (`tools/planning.py`)
| Tool | Description | Parameters |
|------|-------------|------------|
| `sunwell_plan` | Generate execution plan | goal |
| `sunwell_classify` | Classify intent | input |
| `sunwell_reason` | Make reasoned decision | question, options |

### 5. Execution Tools (`tools/execution.py`)
| Tool | Description | Parameters |
|------|-------------|------------|
| `sunwell_execute` | Run agent pipeline | goal |
| `sunwell_validate` | Run validators | file_path |
| `sunwell_complete` | Report completion | goal, files_modified?, learnings? |

### 6. Lens Tools (`tools/lens.py`)
| Tool | Description | Parameters |
|------|-------------|------------|
| `sunwell_lens` | Get lens expertise | name, components? |
| `sunwell_list_lenses` | List available lenses | - |
| `sunwell_route` | Route shortcut to lens | command |

## Tool Naming Convention

**Pattern**: `sunwell_<category>_<action>` or `sunwell_<action>`

**Examples**:
- `sunwell_add_goal` (backlog category implied)
- `sunwell_search` (knowledge category implied)
- `sunwell_lens` (lens category implied)

**Rationale**: Prefix prevents naming conflicts, indicates source

## Implementation Plan

### Phase 1: Core Tool Wrappers (Day 1)
1. Create `src/sunwell/interface/chirp/tools/` module
2. Implement tool wrappers for each service
3. Register tools in `main.py`
4. Test with curl (JSON-RPC calls)

### Phase 2: UI Components (Day 2)
1. Activity Monitor - Real-time tool call feed
2. Tool Inspector - Browse and test tools
3. Integrate into existing layout (sidebar/nav)

### Phase 3: Integration (Day 3)
1. Refactor existing pages to use tool functions
2. Add tool auth/permissions if needed
3. Documentation and examples

## UI Components

### Activity Monitor
**Location**: `/activity` or sidebar widget
**Features**:
- Real-time SSE feed from `app.tool_events`
- Show: tool name, args, result, timestamp, caller
- Filter by category, status
- Sparkline charts for call volume

**Template**:
```html
{% from "chirpui/card.html" import card %}
{% from "chirpui/badge.html" import badge %}

{% call card(title="Activity", collapsible=true) %}
  <div hx-get="/activity/feed" hx-trigger="load" hx-swap="beforeend">
    <!-- SSE events append here -->
  </div>
{% end %}
```

### Tool Inspector
**Location**: `/tools`
**Features**:
- List all registered tools with schemas
- Interactive tool tester (form builder from schema)
- Execution history per tool
- Copy curl commands

**Sections**:
1. Tool List (grouped by category)
2. Schema Viewer (JSON Schema display)
3. Try It (form to call tool)
4. History (past executions)

## Data Flow Example

### AI Agent calls `sunwell_search`:

```
1. Agent → POST /mcp
   {
     "jsonrpc": "2.0",
     "method": "tools/call",
     "params": {
       "name": "sunwell_search",
       "arguments": {"query": "authentication logic"}
     },
     "id": 1
   }

2. Chirp → Routes to registered tool function

3. Tool wrapper → Calls KnowledgeService.search()

4. Service → Performs semantic search

5. Tool wrapper → Returns formatted results

6. Chirp → Emits ToolCallEvent to bus

7. Activity Monitor → Receives event via SSE, updates UI

8. Chirp → Returns JSON-RPC response
   {
     "jsonrpc": "2.0",
     "result": {
       "content": [{
         "type": "text",
         "text": "[{\"file\": \"auth.py\", \"score\": 0.95}, ...]"
       }]
     },
     "id": 1
   }
```

## Benefits

### For AI Agents
- ✅ Direct access to Sunwell via MCP
- ✅ Automatic tool discovery
- ✅ Type-safe schemas
- ✅ No separate MCP server needed

### For Humans
- ✅ Same functions callable from web UI
- ✅ Real-time visibility into AI activity
- ✅ Tool testing/debugging interface
- ✅ Unified codebase (no duplication)

### For Developers
- ✅ Single function serves both interfaces
- ✅ Built-in observability (tool events)
- ✅ Simplified architecture
- ✅ Type-safe with Python annotations

## Migration Notes

### Before (separate MCP server):
```python
# Separate MCP server process
python -m sunwell.mcp

# Separate code for MCP tools
# src/sunwell/mcp/tools/backlog.py
```

### After (integrated):
```python
# Chirp app with built-in MCP
from chirp import App

app = App()

@app.tool("sunwell_add_goal", description="Add a goal")
async def add_goal(title: str, description: str) -> dict:
    # Same function used by web UI and AI agents!
    goal = backlog_service.create(title, description)
    return {"id": goal.id, "title": goal.title}
```

## Testing

### Manual Testing (curl)
```bash
# List tools
curl -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"tools/list","id":1,"params":{}}'

# Call tool
curl -X POST http://localhost:8000/mcp \
  -H 'Content-Type: application/json' \
  -d '{"jsonrpc":"2.0","method":"tools/call","id":2,"params":{"name":"sunwell_search","arguments":{"query":"test"}}}'
```

### Automated Testing
```python
# tests/chirp/test_mcp_tools.py
async def test_sunwell_search_tool():
    client = TestClient(app)
    response = await client.post("/mcp", json={
        "jsonrpc": "2.0",
        "method": "tools/call",
        "params": {
            "name": "sunwell_search",
            "arguments": {"query": "authentication"}
        },
        "id": 1
    })
    assert response.status_code == 200
    assert "content" in response.json()["result"]
```

## Open Questions

1. **Authentication**: Do MCP tools need separate auth? Or inherit from session?
2. **Rate Limiting**: Should AI agents have different limits than humans?
3. **Tool Permissions**: Fine-grained tool access control?
4. **Format Parameter**: Support compact/full formats like Sunwell MCP server?
5. **Backwards Compatibility**: Keep standalone MCP server or deprecate?

## Next Steps

1. ✅ Create architecture document (this file)
2. [ ] Implement tool wrappers (`tools/*.py`)
3. [ ] Register tools in `main.py`
4. [ ] Build Activity Monitor UI
5. [ ] Build Tool Inspector UI
6. [ ] Refactor pages to use tools
7. [ ] Add tests
8. [ ] Document usage

---

**Questions?** See examples in `/Users/llane/Documents/github/python/chirp/examples/tools/`

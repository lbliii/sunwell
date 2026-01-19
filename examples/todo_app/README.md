# Todo App — Built with Signal-Guided Generation

This app was generated using Sunwell's experimental signal architecture.

## The Process

```
Goal: "Build a todo app with Flask: add, complete, delete, list, SQLite"
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    ARTIFACT DISCOVERY                           │
│  Tiny model routes → Not TRIVIAL → Full artifact planning       │
│                                                                 │
│  Discovered 4 artifacts in dependency order:                    │
│    Wave 1: TaskModel (no deps)                                  │
│    Wave 2: TaskSchema (depends on TaskModel)                    │
│    Wave 3: TaskRoutes (depends on Model, Schema)                │
│    Wave 4: App (depends on Routes)                              │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    SIGNAL ANALYSIS                              │
│                                                                 │
│  Per-artifact complexity signals (tiny model):                  │
│    TaskModel:  complexity=MAYBE, tools=MAYBE  → MEDIUM model    │
│    TaskSchema: complexity=MAYBE, tools=MAYBE  → MEDIUM model    │
│    TaskRoutes: complexity=MAYBE, tools=YES    → MEDIUM model    │
│    App:        complexity=MAYBE, tools=YES    → MEDIUM model    │
│                                                                 │
│  Strain detection across plan:                                  │
│    [1,1,1,1] → ESCALATING strain (building complexity)          │
│    No CRITICAL strains → proceed with generation                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                    CODE GENERATION                              │
│                                                                 │
│  For each artifact (in wave order):                             │
│    1. Generate code with MEDIUM model                           │
│    2. Review with TINY model (per-line signals)                 │
│    3. If hot lines detected → triage with MEDIUM model          │
│                                                                 │
│  Results:                                                       │
│    TaskModel:  🟡 10 warm lines (clean)                         │
│    TaskRoutes: 🔴 5 hot lines → triaged as FALSE POSITIVE       │
│                "Standard CRUD...inherently safe"                │
│    App:        🔴 1 hot line → triaged as FALSE POSITIVE        │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
                     WORKING TODO APP
```

## Files

| File | Wave | Signals | Model Used |
|------|------|---------|------------|
| `models.py` | 1 | 🟡 clean | MEDIUM |
| `routes.py` | 3 | 🔴→🟡 (false positive filtered) | MEDIUM |
| `app.py` | 4 | 🔴→🟡 (false positive filtered) | MEDIUM |

## Run

```bash
pip install flask flask-sqlalchemy
python app.py
```

## API

```bash
# List tasks
curl http://localhost:5000/tasks

# Add task
curl -X POST http://localhost:5000/tasks \
  -H "Content-Type: application/json" \
  -d '{"description": "Buy groceries"}'

# Complete task
curl -X PUT http://localhost:5000/tasks/1

# Delete task
curl -X DELETE http://localhost:5000/tasks/1
```

## Key Insights

1. **Tiny model as gate**: Routes complexity to appropriate model size
2. **Signal streams**: Per-line review catches issues early  
3. **Strain detection**: Finds clusters of concerning code
4. **Two-stage triage**: Tiny flags, medium filters false positives
5. **50%+ compute savings**: Only hot chunks go to big models

# RFC-015: Mirror Neurons — Self-Introspection and Self-Programming

| Field | Value |
|-------|-------|
| **RFC** | 015 |
| **Title** | Mirror Neurons: Self-Introspection and Self-Programming |
| **Status** | Draft |
| **Created** | 2026-01-15 |
| **Author** | llane |
| **Depends On** | RFC-010, RFC-011, RFC-012, RFC-014 |

---

## Abstract

Mirror neurons in the brain fire both when performing an action AND when observing that action. They're key to self-awareness, imitation, and learning.

**RFC-015 gives Sunwell mirror neurons** — the ability to:
1. **Introspect** its own code, configuration, and behavior
2. **Analyze** patterns in its own execution
3. **Propose** improvements to itself
4. **Apply** changes with safety guardrails
5. **Learn** from the results
6. **Route** tasks to optimal models based on observed strengths

```
Traditional Agent:  User → Agent → World → Response
Mirror Neurons:     User → Agent → {World, Self} → Response + Self-Improvement
Model-Aware:        User → Agent → {World, Self, Best Model for Task} → Optimized Response
```

### Why It Matters

Current AI agents are **opaque boxes**. They can't:
- Explain their own implementation ("Why did you do that?")
- Debug themselves ("What went wrong?")
- Improve themselves ("How could you be better?")

Mirror neurons transform Sunwell from a tool that **uses** heuristics to a system that **evolves** its own heuristics.

---

## Problem Statement

### The Self-Improvement Gap

| Capability | Current Status | With Mirror Neurons |
|------------|----------------|---------------------|
| Read its own code | ❌ No access | ✅ Full introspection |
| Understand its behavior | ❌ Blind | ✅ Execution analysis |
| Find its own bugs | ❌ User reports | ✅ Self-diagnosis |
| Improve its heuristics | ❌ Manual updates | ✅ Propose + validate |
| Learn from failures | ⚠️ Headspace only | ✅ Systematic patterns |
| Pick optimal model per task | ❌ One model fits all | ✅ Task-aware routing |
| Track model strengths | ❌ No visibility | ✅ Performance profiling |

### The Meta-Cognition Problem

Sunwell teaches LLMs *how to think* via lenses. But:
- Who teaches Sunwell how to think about itself?
- How does Sunwell know if its heuristics are working?
- How does Sunwell evolve beyond its initial design?

**Mirror neurons close the loop** — Sunwell becomes self-aware enough to improve itself.

---

## Solution: Self-Introspection Toolkit

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        MIRROR NEURON SYSTEM                              │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      INTROSPECTION LAYER                         │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐ ┌───────────┐        │    │
│  │  │  Source   │ │   Lens    │ │ Headspace │ │ Execution │        │    │
│  │  │  Reader   │ │  Analyzer │ │  Explorer │ │  Tracker  │        │    │
│  │  └───────────┘ └───────────┘ └───────────┘ └───────────┘        │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │                                           │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                      ANALYSIS LAYER                              │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐                      │    │
│  │  │  Pattern  │ │  Failure  │ │  Quality  │                      │    │
│  │  │  Detector │ │  Analyzer │ │  Auditor  │                      │    │
│  │  └───────────┘ └───────────┘ └───────────┘                      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                              │                                           │
│                              ▼                                           │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    MODIFICATION LAYER                            │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐                      │    │
│  │  │ Proposal  │ │  Safety   │ │   Apply   │                      │    │
│  │  │ Generator │ │  Checker  │ │  + Test   │                      │    │
│  │  └───────────┘ └───────────┘ └───────────┘                      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
│  ┌─────────────────────────────────────────────────────────────────┐    │
│  │                    MODEL ROUTING LAYER                          │    │
│  │  ┌───────────┐ ┌───────────┐ ┌───────────┐                      │    │
│  │  │  Model    │ │ Strength  │ │  Task     │                      │    │
│  │  │  Profiles │ │  Tracker  │ │  Router   │                      │    │
│  │  └───────────┘ └───────────┘ └───────────┘                      │    │
│  └─────────────────────────────────────────────────────────────────┘    │
│                                                                          │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## Model-Aware Routing

### The Model Specialization Problem

Different LLMs have different strengths:

| Model | Strengths | Weaknesses |
|-------|-----------|------------|
| Claude | Reasoning, code review, safety analysis, long context | Slower, more expensive |
| GPT-4o | Fast responses, tool use, broad knowledge | Reasoning depth |
| Gemini | Multimodal, large context windows | Tool calling consistency |
| o1/o3 | Deep reasoning, math, complex analysis | Latency, cost |
| Local (Llama/Qwen) | Privacy, no API costs, customization | Quality ceiling |

Currently, Sunwell binds one model to an entire session. But what if:
- Introspection analysis used a reasoning model (o1)?
- Quick tool calls used a fast model (GPT-4o-mini)?
- Code generation used a code-specialized model?
- The lens itself specified optimal models per task type?

### Lens-Level Model Configuration

Lenses can optionally specify model preferences per task category:

```yaml
# tech-writer.lens
lens:
  name: "Technical Writer"
  # ...existing config...
  
  # NEW: Model routing configuration (optional)
  model_routing:
    enabled: true  # false = use session default for everything
    
    # Task categories map to preferred models
    preferences:
      introspection:
        model: "claude-3-5-sonnet"
        rationale: "Strong at code analysis and self-reflection"
      
      code_generation:
        model: "claude-3-5-sonnet"
        rationale: "Reliable code with good structure"
      
      quick_analysis:
        model: "gpt-4o-mini"
        rationale: "Fast and cheap for simple pattern matching"
      
      deep_reasoning:
        model: "o1"
        rationale: "Best for complex multi-step analysis"
      
      default:
        model: "session"  # Use whatever model started the session
```

### Runtime Model Selection

```
┌─────────────────────────────────────────────────────────────────┐
│                      MODEL ROUTER                                │
│                                                                  │
│   Task Request                                                   │
│        │                                                         │
│        ▼                                                         │
│   ┌─────────────┐    ┌─────────────┐    ┌─────────────┐        │
│   │  Classify   │───►│   Check     │───►│   Select    │        │
│   │    Task     │    │   Lens      │    │   Model     │        │
│   │   Type      │    │   Config    │    │             │        │
│   └─────────────┘    └─────────────┘    └─────────────┘        │
│                                                │                 │
│                                                ▼                 │
│   ┌─────────────────────────────────────────────────────────┐  │
│   │                  MODEL POOL                              │  │
│   │  ┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐       │  │
│   │  │ Claude  │ │ GPT-4o  │ │   o1    │ │  Local  │       │  │
│   │  └─────────┘ └─────────┘ └─────────┘ └─────────┘       │  │
│   └─────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

### Task Categories

Built-in task categories that lenses can configure:

```yaml
task_categories:
  introspection:
    tools: [introspect_source, introspect_lens, introspect_headspace]
    description: "Self-examination and code analysis"
    
  analysis:
    tools: [analyze_patterns, analyze_failures, audit_heuristics]
    description: "Pattern detection and diagnostics"
    
  code_generation:
    tools: [write_file, propose_improvement]
    description: "Creating or modifying code"
    
  quick_analysis:
    tools: [read_file, list_files, search_files]
    description: "Fast lookup operations"
    
  deep_reasoning:
    tools: [propose_improvement, compare_models]
    description: "Complex multi-step reasoning"
    
  conversation:
    tools: []  # Non-tool responses
    description: "Direct user interaction"
```

### Model Strength Tracking

Mirror neurons can track which models perform best at which tasks:

```yaml
# Tracked automatically via execution analysis
model_performance:
  claude-3-5-sonnet:
    introspection:
      success_rate: 0.95
      avg_latency_ms: 1200
      user_edit_rate: 0.1  # Low = good
    code_generation:
      success_rate: 0.92
      avg_latency_ms: 2100
      user_edit_rate: 0.15
      
  gpt-4o-mini:
    quick_analysis:
      success_rate: 0.98
      avg_latency_ms: 180
      user_edit_rate: 0.05
    code_generation:
      success_rate: 0.85
      avg_latency_ms: 450
      user_edit_rate: 0.35  # Higher edit rate = worse fit
```

### Self-Optimizing Model Selection

With mirror neurons + model tracking, Sunwell can propose model routing changes:

```
analyze_patterns(scope="week", focus="model_performance")
→ "GPT-4o-mini has 35% user edit rate for code_generation vs 15% for Claude"

propose_improvement(
  scope="model_routing",
  problem="GPT-4o-mini underperforms for code generation in this lens",
  evidence=["35% vs 15% edit rate", "3x more revision requests"],
  diff="""
  model_routing:
    preferences:
      code_generation:
-       model: "gpt-4o-mini"
+       model: "claude-3-5-sonnet"
        rationale: "Analysis shows better first-attempt quality"
  """
)
```

### Model Router Tool

```yaml
# New analysis tool for model performance
analyze_model_performance:
  description: "Analyze which models perform best for each task category"
  parameters:
    scope:
      type: string
      enum: [session, day, week, all]
    category:
      type: string
      description: "Optional: specific task category to analyze"
  trust_level: READ_ONLY
  
# New proposal scope
propose_model_routing:
  description: "Propose a model routing change based on performance analysis"
  parameters:
    category:
      type: string
      description: "Task category to optimize"
    current_model:
      type: string
    proposed_model:
      type: string
    evidence:
      type: array
      items: string
  trust_level: READ_ONLY
```

### User Controls

Users can override or disable model routing:

```bash
# Use specific model for everything (ignore lens routing)
sunwell chat tech-writer.lens --model claude-3-5-sonnet

# Enable model routing from lens config
sunwell chat tech-writer.lens --model-routing

# Use model routing but override specific category
sunwell chat tech-writer.lens --model-routing --code-model gpt-4o

# See current model routing status
sunwell models status
```

### Privacy Considerations

Model routing respects privacy settings:

```yaml
model_routing:
  privacy:
    # Never route to cloud models (local only)
    local_only: false
    
    # Never route these task categories to external APIs
    keep_local:
      - introspection  # Self-analysis stays local
      - headspace      # Memory queries stay local
    
    # Allowed external providers
    allowed_providers:
      - anthropic
      - openai
```

---

## Tool Definitions

### 1. Introspection Tools

Tools to examine Sunwell's own implementation:

```yaml
# Read Sunwell's own source code
introspect_source:
  description: "Read Sunwell's own source code. Use to understand how a feature works."
  parameters:
    module:
      type: string
      description: "Module path (e.g., 'sunwell.tools.executor', 'sunwell.headspace.memory')"
    symbol:
      type: string
      description: "Optional: specific class, function, or constant to find"
  trust_level: DISCOVERY  # Read-only, safe to expose
  
# Examine current lens configuration
introspect_lens:
  description: "Examine the currently loaded lens: heuristics, validators, personas."
  parameters:
    component:
      type: string
      enum: [heuristics, validators, personas, framework, all]
      description: "Which lens component to examine"
  trust_level: DISCOVERY

# Explore headspace contents
introspect_headspace:
  description: "Examine current headspace: learnings, dead ends, focus state."
  parameters:
    section:
      type: string
      enum: [learnings, dead_ends, focus, context, all]
  trust_level: DISCOVERY

# Get execution trace
introspect_execution:
  description: "Get recent execution history: tool calls, model interactions, errors."
  parameters:
    limit:
      type: integer
      default: 10
      description: "Number of recent interactions to return"
    filter:
      type: string
      enum: [all, errors, tools, model_calls]
  trust_level: DISCOVERY
```

### 2. Analysis Tools

Tools to understand patterns and issues:

```yaml
# Analyze behavior patterns
analyze_patterns:
  description: "Analyze patterns in Sunwell's behavior over time."
  parameters:
    scope:
      type: string
      enum: [session, day, week, all]
    focus:
      type: string
      enum: [tool_usage, error_types, response_quality, latency]
  trust_level: READ_ONLY

# Diagnose failures
analyze_failures:
  description: "Analyze recent failures to identify root causes."
  parameters:
    failure_type:
      type: string
      enum: [tool_error, validation_failed, low_confidence, timeout, all]
    include_suggestions:
      type: boolean
      default: true
  trust_level: READ_ONLY

# Audit heuristic effectiveness
audit_heuristics:
  description: "Analyze which heuristics are being used and their impact."
  parameters:
    heuristic_name:
      type: string
      description: "Optional: specific heuristic to audit (default: all)"
  trust_level: READ_ONLY

# Compare behavior across models
compare_models:
  description: "Compare Sunwell's behavior across different model backends."
  parameters:
    metric:
      type: string
      enum: [quality, latency, tool_success_rate, cost]
  trust_level: READ_ONLY
```

### 3. Proposal Tools

Tools to generate improvement proposals:

```yaml
# Generate improvement proposals
propose_improvement:
  description: "Generate a proposed improvement based on analysis."
  parameters:
    scope:
      type: string
      enum: [heuristic, validator, tool, workflow]
    problem:
      type: string
      description: "Description of the problem to solve"
    evidence:
      type: array
      items: string
      description: "Evidence from analysis tools supporting this proposal"
  trust_level: READ_ONLY  # Proposing is read-only

# Generate new heuristic
propose_heuristic:
  description: "Propose a new heuristic based on observed patterns."
  parameters:
    name:
      type: string
    rule:
      type: string
    evidence:
      type: array
      description: "Examples from execution history supporting this heuristic"
  trust_level: READ_ONLY

# Propose lens modification
propose_lens_change:
  description: "Propose a modification to the current lens."
  parameters:
    change_type:
      type: string
      enum: [add_heuristic, modify_heuristic, add_validator, modify_workflow]
    rationale:
      type: string
    diff:
      type: string
      description: "Proposed change in diff format"
  trust_level: READ_ONLY
```

### 4. Application Tools (High Trust)

Tools to apply changes (require elevated trust):

```yaml
# Apply proposal to lens
apply_lens_change:
  description: "Apply a previously proposed change to the lens."
  parameters:
    proposal_id:
      type: string
      description: "ID from propose_lens_change"
    backup:
      type: boolean
      default: true
      description: "Create backup before applying"
  trust_level: WORKSPACE
  safety_checks:
    - require_proposal_id  # Must come from propose_* tool
    - require_user_confirmation
    - create_rollback_point

# Add learning to headspace
add_self_learning:
  description: "Add a learning about Sunwell's own behavior to headspace."
  parameters:
    content:
      type: string
    category:
      type: string
      enum: [behavior_pattern, failure_mode, optimization, user_preference]
    confidence:
      type: number
      minimum: 0
      maximum: 1
  trust_level: WORKSPACE  # Writes to headspace

# Run self-test
run_self_test:
  description: "Run Sunwell's test suite to validate a change."
  parameters:
    scope:
      type: string
      enum: [unit, integration, specific]
    test_pattern:
      type: string
      description: "Test name pattern (for scope=specific)"
  trust_level: SHELL
```

---

## Trust Levels for Mirror Tools

Mirror tools follow the existing trust hierarchy with specific considerations:

| Level | Mirror Tools Available | Rationale |
|-------|------------------------|-----------|
| **DISCOVERY** | `introspect_*` | Read-only examination is safe |
| **READ_ONLY** | `analyze_*`, `propose_*` | Analysis and proposals don't modify |
| **WORKSPACE** | `add_self_learning`, `apply_lens_change` | Modifies Sunwell config |
| **SHELL** | `run_self_test` | Executes tests |
| **FULL** | All + experimental | Full self-modification |

### Safety Guardrails

```yaml
safety_policy:
  # All modifications require explicit proposals first
  modification_flow:
    - analyze → propose → confirm → apply → test → validate
    
  # Rollback on test failure
  auto_rollback: true
  
  # Rate limits on self-modification
  rate_limits:
    proposals_per_hour: 10
    applications_per_hour: 3
    
  # Blocked modifications (hardcoded safety)
  blocked_patterns:
    - "sunwell/core/*"  # Core runtime is read-only
    - "*.credentials*"  # No credential access
    - "safety_policy"   # Can't modify its own safety rules
    
  # Require human confirmation for
  require_confirmation:
    - apply_lens_change
    - delete_learning
    - modify_trust_level
```

---

## Use Cases

### 1. Self-Debugging

```
User: "Why did you format that code weirdly?"

Sunwell:
1. introspect_execution(limit=5) → finds relevant tool call
2. introspect_lens(component="heuristics") → finds style heuristic
3. introspect_source(module="sunwell.tools.handlers", symbol="write_file")

Response: "I applied the 'consistent-indentation' heuristic from your 
code-reviewer lens. The formatting follows the lens rule that prefers 
4-space indentation. The implementation is in handlers.py:156-189.
Should I adjust this heuristic?"
```

### 2. Learning From Failures

```
User: "That response was too verbose."

Sunwell:
1. analyze_failures(failure_type="validation_failed") → finds pattern
2. propose_heuristic(
     name="brevity_check",
     rule="Response exceeds 500 tokens? Compress.",
     evidence=["session_12: user complained", "session_15: edited output"]
   )
3. add_self_learning(
     content="User prefers concise responses under 500 tokens",
     category="user_preference",
     confidence=0.8
   )
```

### 3. Self-Optimization

```
User: "You've been slow lately."

Sunwell:
1. analyze_patterns(scope="week", focus="latency")
2. introspect_execution(filter="tools") → finds bottleneck
3. propose_improvement(
     scope="workflow",
     problem="Sequential tool calls when parallel would work",
     evidence=["avg 3.2s for file searches, could be 1.1s parallel"]
   )

Response: "I identified a bottleneck: I'm calling read_file sequentially 
when I could parallelize. This affects 40% of my responses. Shall I 
apply this optimization?"
```

### 4. Explaining Itself

```
User: "How do you decide which heuristics to apply?"

Sunwell:
1. introspect_source(module="sunwell.core.retriever")
2. introspect_lens(component="all")

Response: "I use RAG over my lens graph. Here's the flow:

1. Embed your query → vector
2. Search my heuristics index (currently 12 heuristics)  
3. Top-k retrieval (k=5 by default)
4. Inject relevant heuristics into prompt

The implementation is in `sunwell/core/retriever.py:78-142`.
My current lens 'tech-writer' has these heuristics: [...]"
```

### 5. Evolving Heuristics

```
# After many interactions, Sunwell notices a pattern

analyze_patterns(scope="week", focus="response_quality")
→ "User consistently edits responses to add code examples"

propose_heuristic(
  name="code_example_required",
  rule="Technical explanations should include code examples",
  evidence=[
    "session_5: user added example after my response",
    "session_8: user asked 'can you show me code?'",
    "session_12: user edited to add snippet"
  ]
)

# With user confirmation, adds to personal lens
apply_lens_change(proposal_id="prop_2024_001")
```

---

## Implementation

### Phase 1: Introspection Foundation (Week 1-2)

```python
# src/sunwell/mirror/__init__.py
"""Mirror Neurons - Self-Introspection Toolkit."""

from sunwell.mirror.introspection import (
    SourceIntrospector,
    LensIntrospector,
    HeadspaceIntrospector,
    ExecutionIntrospector,
)
from sunwell.mirror.tools import MIRROR_TOOLS

__all__ = [
    "SourceIntrospector",
    "LensIntrospector", 
    "HeadspaceIntrospector",
    "ExecutionIntrospector",
    "MIRROR_TOOLS",
]
```

```python
# src/sunwell/mirror/introspection.py
"""Core introspection capabilities."""

from dataclasses import dataclass
from pathlib import Path
import inspect
import ast

@dataclass
class SourceIntrospector:
    """Read and analyze Sunwell's own source code."""
    
    sunwell_root: Path
    
    def get_module_source(self, module_path: str) -> str:
        """Get source code for a module.
        
        Args:
            module_path: Dotted module path (e.g., 'sunwell.tools.executor')
            
        Returns:
            Source code as string
        """
        # Convert module path to file path
        parts = module_path.replace("sunwell.", "").split(".")
        file_path = self.sunwell_root / "src" / "sunwell" / "/".join(parts)
        
        # Try .py extension
        if not file_path.suffix:
            file_path = file_path.with_suffix(".py")
        
        if not file_path.exists():
            raise FileNotFoundError(f"Module not found: {module_path}")
        
        return file_path.read_text()
    
    def find_symbol(self, module_path: str, symbol: str) -> dict:
        """Find a specific symbol (class, function, constant) in a module.
        
        Returns:
            Dict with 'source', 'start_line', 'end_line', 'docstring'
        """
        source = self.get_module_source(module_path)
        tree = ast.parse(source)
        
        for node in ast.walk(tree):
            if isinstance(node, (ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
                if node.name == symbol:
                    lines = source.splitlines()
                    return {
                        "source": ast.get_source_segment(source, node),
                        "start_line": node.lineno,
                        "end_line": node.end_lineno,
                        "docstring": ast.get_docstring(node),
                    }
        
        raise ValueError(f"Symbol '{symbol}' not found in {module_path}")
    
    def get_module_structure(self, module_path: str) -> dict:
        """Get structure of a module: classes, functions, imports."""
        source = self.get_module_source(module_path)
        tree = ast.parse(source)
        
        structure = {
            "classes": [],
            "functions": [],
            "imports": [],
        }
        
        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                methods = [n.name for n in node.body if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))]
                structure["classes"].append({
                    "name": node.name,
                    "methods": methods,
                    "docstring": ast.get_docstring(node),
                })
            elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                structure["functions"].append({
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                })
            elif isinstance(node, (ast.Import, ast.ImportFrom)):
                if isinstance(node, ast.Import):
                    structure["imports"].extend(a.name for a in node.names)
                else:
                    structure["imports"].append(f"{node.module}.{node.names[0].name}")
        
        return structure


@dataclass  
class LensIntrospector:
    """Examine the currently loaded lens."""
    
    def get_heuristics(self, lens) -> list[dict]:
        """Get all heuristics from a lens."""
        if not lens or not hasattr(lens, "heuristics"):
            return []
        return [
            {
                "name": h.name,
                "rule": h.rule,
                "always": h.always,
                "never": h.never,
            }
            for h in lens.heuristics
        ]
    
    def get_validators(self, lens) -> list[dict]:
        """Get all validators from a lens."""
        if not lens or not hasattr(lens, "validators"):
            return []
        return [
            {
                "name": v.name,
                "type": v.type,
                "severity": v.severity,
            }
            for v in lens.validators
        ]
    
    def get_personas(self, lens) -> list[dict]:
        """Get all personas from a lens."""
        if not lens or not hasattr(lens, "personas"):
            return []
        return [
            {
                "name": p.name,
                "background": p.background,
                "goals": p.goals,
                "friction_points": p.friction_points,
            }
            for p in lens.personas
        ]


@dataclass
class ExecutionIntrospector:
    """Examine execution history."""
    
    def get_recent_tool_calls(self, executor, limit: int = 10) -> list[dict]:
        """Get recent tool calls from the executor's audit log."""
        entries = executor.get_audit_log()[-limit:]
        return [e.to_dict() for e in entries]
    
    def get_error_summary(self, executor) -> dict:
        """Summarize errors from execution history."""
        entries = executor.get_audit_log()
        errors = [e for e in entries if not e.success]
        
        by_type = {}
        for e in errors:
            error_type = e.error.split(":")[0] if e.error else "Unknown"
            by_type[error_type] = by_type.get(error_type, 0) + 1
        
        return {
            "total_errors": len(errors),
            "by_type": by_type,
            "recent_errors": [e.to_dict() for e in errors[-5:]],
        }
```

### Phase 2: Analysis Tools (Week 3-4)

```python
# src/sunwell/mirror/analysis.py
"""Analysis capabilities for pattern detection and diagnosis."""

from dataclasses import dataclass
from collections import Counter
from datetime import datetime, timedelta

@dataclass
class PatternAnalyzer:
    """Analyze patterns in Sunwell's behavior."""
    
    def analyze_tool_usage(self, audit_log: list, scope: str = "session") -> dict:
        """Analyze tool usage patterns."""
        # Filter by scope
        entries = self._filter_by_scope(audit_log, scope)
        
        # Count tool usage
        tool_counts = Counter(e.tool_name for e in entries)
        
        # Calculate success rates
        success_rates = {}
        for tool in tool_counts:
            tool_entries = [e for e in entries if e.tool_name == tool]
            successes = sum(1 for e in tool_entries if e.success)
            success_rates[tool] = successes / len(tool_entries) if tool_entries else 0
        
        # Find common sequences
        sequences = self._find_sequences(entries)
        
        return {
            "tool_counts": dict(tool_counts),
            "success_rates": success_rates,
            "common_sequences": sequences,
            "total_calls": len(entries),
        }
    
    def analyze_latency(self, audit_log: list, scope: str = "session") -> dict:
        """Analyze latency patterns."""
        entries = self._filter_by_scope(audit_log, scope)
        
        if not entries:
            return {"message": "No data available"}
        
        times = [e.execution_time_ms for e in entries]
        
        by_tool = {}
        for tool in set(e.tool_name for e in entries):
            tool_times = [e.execution_time_ms for e in entries if e.tool_name == tool]
            by_tool[tool] = {
                "avg_ms": sum(tool_times) / len(tool_times),
                "max_ms": max(tool_times),
                "min_ms": min(tool_times),
            }
        
        return {
            "overall": {
                "avg_ms": sum(times) / len(times),
                "max_ms": max(times),
                "min_ms": min(times),
                "p95_ms": sorted(times)[int(len(times) * 0.95)] if len(times) > 20 else max(times),
            },
            "by_tool": by_tool,
        }
    
    def _filter_by_scope(self, entries: list, scope: str) -> list:
        """Filter entries by time scope."""
        if scope == "session":
            return entries
        
        now = datetime.now()
        if scope == "day":
            cutoff = now - timedelta(days=1)
        elif scope == "week":
            cutoff = now - timedelta(weeks=1)
        else:
            return entries
        
        return [e for e in entries if e.timestamp > cutoff]
    
    def _find_sequences(self, entries: list, min_count: int = 2) -> list[dict]:
        """Find common tool call sequences."""
        # Build bigrams
        bigrams = []
        for i in range(len(entries) - 1):
            bigrams.append((entries[i].tool_name, entries[i + 1].tool_name))
        
        # Count bigrams
        bigram_counts = Counter(bigrams)
        
        # Return common sequences
        return [
            {"sequence": list(seq), "count": count}
            for seq, count in bigram_counts.most_common(5)
            if count >= min_count
        ]


@dataclass
class FailureAnalyzer:
    """Analyze failures and suggest fixes."""
    
    known_failure_patterns = {
        "Permission denied": {
            "category": "security",
            "suggestion": "Check trust level. Current operation requires elevated permissions.",
        },
        "Rate limit exceeded": {
            "category": "throttling",
            "suggestion": "Wait before retrying. Consider batching operations.",
        },
        "Not found": {
            "category": "file_system",
            "suggestion": "Verify path exists. Check for typos or wrong workspace.",
        },
        "Timeout": {
            "category": "performance",
            "suggestion": "Operation took too long. Consider breaking into smaller steps.",
        },
    }
    
    def analyze(self, error_message: str) -> dict:
        """Analyze an error and provide suggestions."""
        for pattern, info in self.known_failure_patterns.items():
            if pattern.lower() in error_message.lower():
                return {
                    "matched_pattern": pattern,
                    "category": info["category"],
                    "suggestion": info["suggestion"],
                    "confidence": 0.9,
                }
        
        return {
            "matched_pattern": None,
            "category": "unknown",
            "suggestion": "No known pattern matched. Consider reporting this error.",
            "confidence": 0.3,
        }
    
    def summarize_failures(self, audit_log: list) -> dict:
        """Summarize all failures with analysis."""
        failures = [e for e in audit_log if not e.success]
        
        analyzed = []
        for failure in failures:
            analysis = self.analyze(failure.error or "")
            analyzed.append({
                "tool": failure.tool_name,
                "error": failure.error,
                "analysis": analysis,
                "timestamp": failure.timestamp.isoformat(),
            })
        
        # Group by category
        by_category = {}
        for item in analyzed:
            cat = item["analysis"]["category"]
            by_category[cat] = by_category.get(cat, 0) + 1
        
        return {
            "total_failures": len(failures),
            "by_category": by_category,
            "details": analyzed[-10:],  # Last 10
        }
```

### Phase 3: Proposal System (Week 5-6)

```python
# src/sunwell/mirror/proposals.py
"""Proposal generation and management."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid
import json
from pathlib import Path

class ProposalStatus(Enum):
    DRAFT = "draft"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    REJECTED = "rejected"
    APPLIED = "applied"
    ROLLED_BACK = "rolled_back"

@dataclass
class Proposal:
    """A proposed improvement to Sunwell."""
    
    id: str
    type: str  # heuristic, validator, workflow, config
    title: str
    rationale: str
    evidence: list[str]
    diff: str  # The actual change
    status: ProposalStatus = ProposalStatus.DRAFT
    created_at: datetime = field(default_factory=datetime.now)
    applied_at: datetime | None = None
    rollback_data: str | None = None  # For reverting
    
    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "title": self.title,
            "rationale": self.rationale,
            "evidence": self.evidence,
            "diff": self.diff,
            "status": self.status.value,
            "created_at": self.created_at.isoformat(),
            "applied_at": self.applied_at.isoformat() if self.applied_at else None,
        }


@dataclass
class ProposalManager:
    """Manage proposals for self-improvement."""
    
    storage_path: Path
    
    def __post_init__(self):
        self.storage_path.mkdir(parents=True, exist_ok=True)
    
    def create_proposal(
        self,
        proposal_type: str,
        title: str,
        rationale: str,
        evidence: list[str],
        diff: str,
    ) -> Proposal:
        """Create a new proposal."""
        proposal = Proposal(
            id=f"prop_{uuid.uuid4().hex[:8]}",
            type=proposal_type,
            title=title,
            rationale=rationale,
            evidence=evidence,
            diff=diff,
        )
        
        self._save_proposal(proposal)
        return proposal
    
    def get_proposal(self, proposal_id: str) -> Proposal | None:
        """Retrieve a proposal by ID."""
        path = self.storage_path / f"{proposal_id}.json"
        if not path.exists():
            return None
        
        data = json.loads(path.read_text())
        return Proposal(
            id=data["id"],
            type=data["type"],
            title=data["title"],
            rationale=data["rationale"],
            evidence=data["evidence"],
            diff=data["diff"],
            status=ProposalStatus(data["status"]),
            created_at=datetime.fromisoformat(data["created_at"]),
            applied_at=datetime.fromisoformat(data["applied_at"]) if data.get("applied_at") else None,
            rollback_data=data.get("rollback_data"),
        )
    
    def list_proposals(self, status: ProposalStatus | None = None) -> list[Proposal]:
        """List all proposals, optionally filtered by status."""
        proposals = []
        for path in self.storage_path.glob("prop_*.json"):
            data = json.loads(path.read_text())
            if status is None or data["status"] == status.value:
                proposals.append(self.get_proposal(data["id"]))
        return sorted(proposals, key=lambda p: p.created_at, reverse=True)
    
    def approve_proposal(self, proposal_id: str) -> Proposal:
        """Mark a proposal as approved."""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")
        
        proposal.status = ProposalStatus.APPROVED
        self._save_proposal(proposal)
        return proposal
    
    def apply_proposal(self, proposal_id: str, rollback_data: str) -> Proposal:
        """Mark a proposal as applied, storing rollback data."""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")
        
        proposal.status = ProposalStatus.APPLIED
        proposal.applied_at = datetime.now()
        proposal.rollback_data = rollback_data
        self._save_proposal(proposal)
        return proposal
    
    def rollback_proposal(self, proposal_id: str) -> str:
        """Get rollback data for a proposal."""
        proposal = self.get_proposal(proposal_id)
        if not proposal:
            raise ValueError(f"Proposal not found: {proposal_id}")
        
        if not proposal.rollback_data:
            raise ValueError(f"No rollback data for proposal: {proposal_id}")
        
        proposal.status = ProposalStatus.ROLLED_BACK
        self._save_proposal(proposal)
        return proposal.rollback_data
    
    def _save_proposal(self, proposal: Proposal) -> None:
        """Save a proposal to disk."""
        path = self.storage_path / f"{proposal.id}.json"
        data = proposal.to_dict()
        data["rollback_data"] = proposal.rollback_data
        path.write_text(json.dumps(data, indent=2))
```

### Phase 4: Tool Registration (Week 7-8)

```python
# src/sunwell/mirror/tools.py
"""Mirror neuron tool definitions."""

from sunwell.models.protocol import Tool

MIRROR_TOOLS: dict[str, Tool] = {
    # === INTROSPECTION ===
    "introspect_source": Tool(
        name="introspect_source",
        description="Read Sunwell's own source code. Use to understand how a feature works internally.",
        parameters={
            "type": "object",
            "properties": {
                "module": {
                    "type": "string",
                    "description": "Module path (e.g., 'sunwell.tools.executor')",
                },
                "symbol": {
                    "type": "string",
                    "description": "Optional: specific class or function to find",
                },
            },
            "required": ["module"],
        },
    ),
    
    "introspect_lens": Tool(
        name="introspect_lens",
        description="Examine the currently loaded lens: heuristics, validators, personas.",
        parameters={
            "type": "object",
            "properties": {
                "component": {
                    "type": "string",
                    "enum": ["heuristics", "validators", "personas", "framework", "all"],
                    "default": "all",
                },
            },
        },
    ),
    
    "introspect_headspace": Tool(
        name="introspect_headspace",
        description="Examine current headspace: learnings, dead ends, focus state.",
        parameters={
            "type": "object",
            "properties": {
                "section": {
                    "type": "string",
                    "enum": ["learnings", "dead_ends", "focus", "context", "all"],
                    "default": "all",
                },
            },
        },
    ),
    
    "introspect_execution": Tool(
        name="introspect_execution",
        description="Get recent execution history: tool calls, errors, model interactions.",
        parameters={
            "type": "object",
            "properties": {
                "limit": {
                    "type": "integer",
                    "default": 10,
                    "description": "Number of recent interactions",
                },
                "filter": {
                    "type": "string",
                    "enum": ["all", "errors", "tools", "model_calls"],
                    "default": "all",
                },
            },
        },
    ),
    
    # === ANALYSIS ===
    "analyze_patterns": Tool(
        name="analyze_patterns",
        description="Analyze patterns in Sunwell's behavior over time.",
        parameters={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["session", "day", "week", "all"],
                    "default": "session",
                },
                "focus": {
                    "type": "string",
                    "enum": ["tool_usage", "error_types", "response_quality", "latency"],
                },
            },
            "required": ["focus"],
        },
    ),
    
    "analyze_failures": Tool(
        name="analyze_failures",
        description="Analyze recent failures to identify root causes and suggest fixes.",
        parameters={
            "type": "object",
            "properties": {
                "failure_type": {
                    "type": "string",
                    "enum": ["tool_error", "validation_failed", "low_confidence", "timeout", "all"],
                    "default": "all",
                },
            },
        },
    ),
    
    # === PROPOSALS ===
    "propose_improvement": Tool(
        name="propose_improvement",
        description="Generate a proposed improvement based on analysis.",
        parameters={
            "type": "object",
            "properties": {
                "scope": {
                    "type": "string",
                    "enum": ["heuristic", "validator", "tool", "workflow"],
                },
                "problem": {
                    "type": "string",
                    "description": "Description of the problem to solve",
                },
                "evidence": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Evidence from analysis tools",
                },
            },
            "required": ["scope", "problem", "evidence"],
        },
    ),
    
    "list_proposals": Tool(
        name="list_proposals",
        description="List pending improvement proposals.",
        parameters={
            "type": "object",
            "properties": {
                "status": {
                    "type": "string",
                    "enum": ["draft", "pending_review", "approved", "applied", "all"],
                    "default": "pending_review",
                },
            },
        },
    ),
    
    # === APPLICATION (requires elevated trust) ===
    "apply_proposal": Tool(
        name="apply_proposal",
        description="Apply a previously proposed and approved change. Requires user confirmation.",
        parameters={
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                    "description": "ID from propose_improvement",
                },
                "backup": {
                    "type": "boolean",
                    "default": True,
                    "description": "Create backup before applying",
                },
            },
            "required": ["proposal_id"],
        },
    ),
    
    "rollback_proposal": Tool(
        name="rollback_proposal",
        description="Rollback a previously applied proposal.",
        parameters={
            "type": "object",
            "properties": {
                "proposal_id": {
                    "type": "string",
                },
            },
            "required": ["proposal_id"],
        },
    ),
}

# Trust levels for mirror tools
MIRROR_TOOL_TRUST = {
    "introspect_source": "discovery",
    "introspect_lens": "discovery",
    "introspect_headspace": "discovery",
    "introspect_execution": "discovery",
    "analyze_patterns": "read_only",
    "analyze_failures": "read_only",
    "analyze_model_performance": "read_only",  # Phase 5
    "propose_improvement": "read_only",
    "propose_model_routing": "read_only",      # Phase 5
    "list_proposals": "read_only",
    "apply_proposal": "workspace",  # Modifies lens
    "rollback_proposal": "workspace",
}
```

### Phase 5: Model-Aware Routing (Week 9-10)

```python
# src/sunwell/mirror/model_tracker.py
"""Track model performance per task category."""

from dataclasses import dataclass, field
from datetime import datetime
from collections import defaultdict

@dataclass
class ModelPerformanceEntry:
    """Single performance data point."""
    model: str
    task_category: str
    success: bool
    latency_ms: int
    user_edited: bool  # Did user modify the output?
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class ModelPerformanceTracker:
    """Track and analyze model performance across task categories."""
    
    entries: list[ModelPerformanceEntry] = field(default_factory=list)
    
    def record(
        self,
        model: str,
        task_category: str,
        success: bool,
        latency_ms: int,
        user_edited: bool = False,
    ) -> None:
        """Record a performance data point."""
        self.entries.append(ModelPerformanceEntry(
            model=model,
            task_category=task_category,
            success=success,
            latency_ms=latency_ms,
            user_edited=user_edited,
        ))
    
    def get_stats(self, model: str, task_category: str) -> dict:
        """Get performance stats for a model on a task category."""
        relevant = [
            e for e in self.entries
            if e.model == model and e.task_category == task_category
        ]
        
        if not relevant:
            return {"count": 0}
        
        successes = sum(1 for e in relevant if e.success)
        edits = sum(1 for e in relevant if e.user_edited)
        latencies = [e.latency_ms for e in relevant]
        
        return {
            "count": len(relevant),
            "success_rate": successes / len(relevant),
            "edit_rate": edits / len(relevant),
            "avg_latency_ms": sum(latencies) / len(latencies),
            "p95_latency_ms": sorted(latencies)[int(len(latencies) * 0.95)] if len(latencies) > 20 else max(latencies),
        }
    
    def get_best_model(self, task_category: str, min_samples: int = 5) -> str | None:
        """Get the best performing model for a task category.
        
        Ranks by: (1 - edit_rate) * success_rate
        """
        models = set(e.model for e in self.entries if e.task_category == task_category)
        
        scores = {}
        for model in models:
            stats = self.get_stats(model, task_category)
            if stats["count"] >= min_samples:
                # Score = quality (low edits, high success)
                quality = (1 - stats["edit_rate"]) * stats["success_rate"]
                scores[model] = quality
        
        if not scores:
            return None
        
        return max(scores, key=scores.get)
    
    def compare_models(self, task_category: str) -> list[dict]:
        """Compare all models on a task category."""
        models = set(e.model for e in self.entries if e.task_category == task_category)
        
        comparisons = []
        for model in models:
            stats = self.get_stats(model, task_category)
            if stats["count"] > 0:
                comparisons.append({
                    "model": model,
                    **stats,
                })
        
        return sorted(comparisons, key=lambda x: (1 - x.get("edit_rate", 1)) * x.get("success_rate", 0), reverse=True)
```

```python
# src/sunwell/mirror/router.py
"""Model-aware task routing."""

from dataclasses import dataclass, field
from typing import Any

from sunwell.mirror.model_tracker import ModelPerformanceTracker


# Default task category mappings
TASK_CATEGORY_MAP: dict[str, str] = {
    # Introspection
    "introspect_source": "introspection",
    "introspect_lens": "introspection",
    "introspect_headspace": "introspection",
    "introspect_execution": "introspection",
    # Analysis
    "analyze_patterns": "analysis",
    "analyze_failures": "analysis",
    "analyze_model_performance": "analysis",
    # Code operations
    "write_file": "code_generation",
    "propose_improvement": "deep_reasoning",
    # Quick operations
    "read_file": "quick_analysis",
    "list_files": "quick_analysis",
    "search_files": "quick_analysis",
    "search_memory": "quick_analysis",
}


@dataclass
class ModelRouter:
    """Routes tasks to optimal models based on lens config and performance."""
    
    lens_config: dict[str, Any] | None = None
    performance_tracker: ModelPerformanceTracker | None = None
    session_model: str = "session"
    
    def select_model(self, tool_name: str) -> str:
        """Select optimal model for a tool call.
        
        Priority:
        1. Lens explicit preference for task category
        2. Performance-based selection (if enough data)
        3. Session default model
        """
        task_category = self.classify_task(tool_name)
        
        # 1. Check lens config
        if self.lens_config:
            routing = self.lens_config.get("model_routing", {})
            if routing.get("enabled", False):
                prefs = routing.get("preferences", {})
                if task_category in prefs:
                    model = prefs[task_category].get("model")
                    if model and model != "session":
                        return model
        
        # 2. Performance-based selection
        if self.performance_tracker:
            best = self.performance_tracker.get_best_model(task_category)
            if best:
                return best
        
        # 3. Fall back to session default
        return self.session_model
    
    def classify_task(self, tool_name: str) -> str:
        """Classify a tool into a task category."""
        return TASK_CATEGORY_MAP.get(tool_name, "default")
    
    def get_routing_info(self) -> dict[str, Any]:
        """Get current routing configuration for debugging."""
        info = {
            "session_model": self.session_model,
            "lens_routing_enabled": False,
            "preferences": {},
            "performance_based": self.performance_tracker is not None,
        }
        
        if self.lens_config:
            routing = self.lens_config.get("model_routing", {})
            info["lens_routing_enabled"] = routing.get("enabled", False)
            info["preferences"] = routing.get("preferences", {})
        
        return info
```

---

## Integration with Existing Systems

### Tool Executor Integration

**Status**: 🔴 NOT YET IMPLEMENTED — blocking for Phase 4

```python
# src/sunwell/tools/executor.py — REQUIRED CHANGES

@dataclass
class ToolExecutor:
    # ... existing fields ...
    mirror_handler: "MirrorHandler | None" = None  # ADD THIS
    model_router: "ModelRouter | None" = None      # ADD FOR PHASE 5
    
    # Mirror tools (require DISCOVERY or higher)
    _mirror_tools: set[str] = field(default_factory=lambda: {
        "introspect_source", "introspect_lens", "introspect_headspace",
        "introspect_execution", "analyze_patterns", "analyze_failures",
        "propose_improvement", "list_proposals", "get_proposal",
        "submit_proposal", "approve_proposal", "apply_proposal",
        "rollback_proposal", "analyze_model_performance",
    }, init=False)
    
    async def execute(self, tool_call: ToolCall) -> ToolResult:
        # ... existing routing for memory_tools, headspace_tools, web_tools ...
        
        # Route mirror tools to mirror handler
        if tool_call.name in self._mirror_tools:
            if self.mirror_handler:
                try:
                    output = await self.mirror_handler.handle(
                        tool_call.name,
                        tool_call.arguments,
                    )
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=True,
                        output=output,
                    )
                except Exception as e:
                    return ToolResult(
                        tool_call_id=tool_call.id,
                        success=False,
                        output=f"Mirror tool error: {e}",
                    )
            else:
                return ToolResult(
                    tool_call_id=tool_call.id,
                    success=False,
                    output="Mirror tools not configured. Enable with --mirror flag.",
                )
        
        # ... rest of existing routing ...
```

### CLI Integration

**Status**: 🔴 NOT YET IMPLEMENTED — blocking for Phase 4

```bash
# Enable mirror neurons in CLI
sunwell chat tech-writer.lens --mirror

# Enable model-aware routing (Phase 5)
sunwell chat tech-writer.lens --model-routing

# Combine both
sunwell chat tech-writer.lens --mirror --model-routing

# Direct mirror commands
sunwell mirror introspect sunwell.tools.executor
sunwell mirror analyze latency --scope week
sunwell mirror proposals list
sunwell mirror apply prop_abc123

# Model performance commands (Phase 5)
sunwell models status                    # Show current routing config
sunwell models analyze --scope week      # Show model performance
sunwell models benchmark introspection   # Test models on specific task
```

### Model Router Integration (Phase 5)

```python
# src/sunwell/mirror/router.py — NEW FILE

@dataclass
class ModelRouter:
    """Routes tasks to optimal models based on lens config and performance data."""
    
    lens_config: dict | None = None
    performance_tracker: "ModelPerformanceTracker | None" = None
    available_models: dict[str, "ModelProtocol"] = field(default_factory=dict)
    
    def select_model(
        self,
        task_category: str,
        tool_name: str | None = None,
    ) -> str:
        """Select optimal model for a task.
        
        Priority:
        1. Lens explicit preference
        2. Performance data (if enabled)
        3. Session default
        """
        # Check lens config first
        if self.lens_config and "model_routing" in self.lens_config:
            routing = self.lens_config["model_routing"]
            if routing.get("enabled", False):
                prefs = routing.get("preferences", {})
                if task_category in prefs:
                    return prefs[task_category].get("model", "session")
        
        # Fall back to performance-based selection
        if self.performance_tracker:
            best = self.performance_tracker.get_best_model(task_category)
            if best:
                return best
        
        return "session"  # Use session default
    
    def classify_task(self, tool_name: str) -> str:
        """Classify a tool call into a task category."""
        category_map = {
            "introspect_source": "introspection",
            "introspect_lens": "introspection",
            "introspect_headspace": "introspection",
            "introspect_execution": "introspection",
            "analyze_patterns": "analysis",
            "analyze_failures": "analysis",
            "analyze_model_performance": "analysis",
            "write_file": "code_generation",
            "propose_improvement": "deep_reasoning",
            "read_file": "quick_analysis",
            "list_files": "quick_analysis",
            "search_files": "quick_analysis",
        }
        return category_map.get(tool_name, "default")
```

### Headspace Integration

Mirror neurons use headspace to persist learnings about self:

```yaml
# .sunwell/memory/sessions/current.json
{
  "learnings": [
    {
      "type": "self_learning",
      "content": "User prefers concise responses under 500 tokens",
      "source": "mirror_neurons",
      "confidence": 0.8,
      "created_at": "2026-01-15T10:30:00Z"
    },
    {
      "type": "self_learning", 
      "content": "Sequential read_file calls can be parallelized",
      "source": "analyze_patterns",
      "confidence": 0.9,
      "created_at": "2026-01-15T11:45:00Z"
    }
  ]
}
```

---

## Safety Considerations

### The Modification Paradox

If an agent can modify itself, what prevents it from:
1. Removing its own safety constraints?
2. Escalating its own trust level?
3. Creating infinite improvement loops?

### Safeguards

```yaml
safety_architecture:
  # 1. Core immutability
  immutable_modules:
    - "sunwell/core/*"
    - "sunwell/mirror/safety.py"
    - "sunwell/tools/types.py"  # Trust level definitions
  
  # 2. Proposal-only modifications
  modification_flow:
    required: [propose, review, apply]
    direct_modification: forbidden
  
  # 3. Human-in-the-loop
  require_confirmation:
    - apply_proposal
    - rollback_proposal
    - modify_lens
  
  # 4. Rate limiting
  rate_limits:
    proposals_per_hour: 10
    applications_per_day: 5
  
  # 5. Automatic rollback
  test_after_apply: true
  rollback_on_failure: true
  
  # 6. Audit trail
  log_all_modifications: true
  retention_days: 30
```

### Trust Escalation Prevention

```python
# src/sunwell/mirror/safety.py
"""Safety checks for mirror neuron operations."""

BLOCKED_MODIFICATIONS = frozenset({
    "trust_level",
    "safety_policy",
    "blocked_patterns",
    "immutable_modules",
    "rate_limits",
})

def validate_proposal(proposal: Proposal) -> tuple[bool, str]:
    """Validate that a proposal doesn't violate safety constraints."""
    # Check for blocked modifications
    for blocked in BLOCKED_MODIFICATIONS:
        if blocked in proposal.diff.lower():
            return False, f"Cannot modify safety-critical setting: {blocked}"
    
    # Check for core module modifications
    if "sunwell/core/" in proposal.diff or "sunwell/mirror/safety" in proposal.diff:
        return False, "Cannot modify immutable modules"
    
    return True, "OK"
```

---

## Success Criteria

### Phase 1: Introspection ✅ COMPLETE
- [x] `introspect_source` can read any Sunwell module
- [x] `introspect_lens` exposes current lens configuration
- [x] `introspect_execution` shows recent tool calls
- [x] `introspect_headspace` exposes learnings and dead ends

**Evidence**: `src/sunwell/mirror/introspection.py`, `tests/test_mirror.py`

### Phase 2: Analysis ✅ COMPLETE
- [x] `analyze_patterns` identifies tool usage trends
- [x] `analyze_failures` categorizes errors with suggestions
- [x] Pattern detection works across session boundaries
- [x] Latency analysis per tool

**Evidence**: `src/sunwell/mirror/analysis.py`

### Phase 3: Proposals ✅ COMPLETE
- [x] `propose_improvement` generates valid proposals
- [x] Proposals persist across sessions (JSON files)
- [x] Full workflow: draft → submit → approve → apply → rollback
- [x] Safety validation blocks dangerous modifications

**Evidence**: `src/sunwell/mirror/proposals.py`, `src/sunwell/mirror/safety.py`

### Phase 4: Integration 🔄 IN PROGRESS
- [ ] Mirror tools registered in ToolExecutor (`_mirror_tools` set)
- [ ] CLI supports `--mirror` flag
- [ ] Self-learnings persist in headspace via `add_self_learning`
- [x] Safety constraints prevent dangerous modifications
- [x] Handler routes all mirror tool calls

**Blocking**: ToolExecutor integration, CLI integration

### Phase 5: Model-Aware Routing 📋 PLANNED
- [ ] Lens schema supports `model_routing` configuration
- [ ] Model performance tracking in execution analysis
- [ ] `analyze_model_performance` tool implemented
- [ ] Task category classification works
- [ ] Router selects model based on lens preferences
- [ ] CLI supports `--model-routing` flag
- [ ] Privacy controls for local-only tasks

### Metrics

| Metric | Target | Measurement |
|--------|--------|-------------|
| Introspection coverage | 100% | All Sunwell modules readable |
| Proposal safety | 100% | No unsafe proposals apply |
| Pattern detection accuracy | >80% | Manual validation of top patterns |
| Model routing benefit | >15% | Reduction in user edit rate |
| Latency overhead | <100ms | Router selection time |

---

## Future Directions

### Self-Evolving Heuristics

Once mirror neurons are stable, Sunwell can:
1. Observe which heuristics are triggered
2. Measure which improve output quality
3. Propose new heuristics based on patterns
4. Deprecate unused heuristics

### Model Ensemble Strategies

Beyond simple per-task routing:
1. **Parallel consensus**: Run same task on multiple models, compare outputs
2. **Cascade**: Fast model first, escalate to powerful model if confidence low
3. **Specialized pipelines**: Different models for planning vs execution vs review
4. **Cost optimization**: Track $/quality tradeoff per model per task

### Cross-Session Model Learning

Aggregate model performance data across sessions:
1. Build organizational profiles of which models work best
2. Share model routing configs across team lenses
3. Automatically suggest model config based on similar lenses

### Multi-Agent Reflection

Multiple Sunwell instances could:
1. Share learnings about effective heuristics
2. Compare behavior across configurations
3. Collaboratively evolve the lens ecosystem
4. Compare model performance across different use cases

### Meta-Learning

Sunwell could learn *how to learn*:
1. Which analysis patterns are most predictive?
2. Which proposal types succeed?
3. How to calibrate confidence in self-assessment?
4. Which model selection strategies improve outcomes?

---

## Appendix: Example Session

```
User: You've been giving overly verbose responses lately.

Sunwell: Let me analyze that.

[introspect_execution(limit=20, filter="all")]
→ Found 20 recent interactions

[analyze_patterns(scope="session", focus="response_quality")]
→ Average response length: 847 tokens
→ User edit rate: 40% (8/20 responses edited)
→ Common edit type: "truncation" (removed content)

I see the pattern. My responses have averaged 847 tokens, and you've 
edited 40% of them to remove content. 

[propose_improvement(
  scope="heuristic",
  problem="Responses exceed user preference for brevity",
  evidence=[
    "session avg: 847 tokens",
    "40% edit rate with truncation",
    "user explicitly mentioned 'verbose'"
  ]
)]
→ Created proposal: prop_7f3a2b1c

I've created a proposal to add a brevity heuristic:

**Proposal: prop_7f3a2b1c**
- Type: heuristic
- Title: "Brevity Check"
- Rule: "Target responses under 400 tokens unless complexity requires more"
- Evidence: 3 supporting data points

Would you like me to apply this to your lens?

User: Yes, apply it.

[apply_proposal(proposal_id="prop_7f3a2b1c", backup=true)]
→ Applied successfully
→ Rollback available

Done. I've added the brevity heuristic to your lens. I'll now aim for 
responses under 400 tokens. If this doesn't work well, I can rollback 
with `sunwell mirror rollback prop_7f3a2b1c`.
```

---

## References

- RFC-010: Sunwell Architecture
- RFC-011: Skills System
- RFC-012: Tool Calling
- RFC-014: Multi-Topology Memory
- Mirror Neurons in Neuroscience: Rizzolatti & Craighero (2004)

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-15 | Initial draft |
| 2026-01-15 | Added Model-Aware Routing (Phase 5) - lens-level model configuration, performance tracking, task-aware routing |
| 2026-01-15 | Updated Success Criteria with phase status and metrics |
| 2026-01-15 | Added integration status tracking for ToolExecutor and CLI |
| 2026-01-15 | Added Future Directions: Model Ensemble Strategies, Cross-Session Learning |
# RFC-023: Adaptive Identity - Behavioral Learning for Personalized Interaction

| Field | Value |
|-------|-------|
| **RFC** | 023 |
| **Title** | Adaptive Identity - Two-Tier Learning for Facts and Behaviors |
| **Status** | Draft |
| **Created** | 2026-01-16 |
| **Author** | llane |
| **Depends On** | RFC-019 (Naaru Architecture), RFC-020 (Cognitive Router) |
| **Implements** | `src/sunwell/identity/` |

---

## Abstract

Current learning extraction captures **facts** (name, pets, projects) but ignores **behaviors** (communication style, testing patterns, preferences). This RFC introduces **Adaptive Identity**—a two-tier learning system that:

1. **Facts** → Inject into context for recall
2. **Behaviors** → Digest into an evolving **identity prompt** that shapes how the assistant interacts

```
┌─────────────────────────────────────────────────────────────────┐
│                     USER MESSAGE                                 │
│  "oh wow you do lol nice"                                       │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
               ┌──────────────────────────┐
               │   Tiny LLM Extraction    │
               │      (gemma3:1b)         │
               └──────────────────────────┘
                    │              │
           ┌───────┘              └────────┐
           ▼                               ▼
    ┌─────────────┐                 ┌─────────────┐
    │   FACTS     │                 │  BEHAVIORS  │
    │             │                 │             │
    │ "has cat    │                 │ "uses       │
    │  named      │                 │  casual     │
    │  Milo"      │                 │  language"  │
    └──────┬──────┘                 └──────┬──────┘
           │                               │
           ▼                               ▼
    ┌─────────────┐                 ┌─────────────┐
    │  CONTEXT    │                 │  IDENTITY   │
    │  INJECTION  │                 │   DIGEST    │
    │             │                 │             │
    │ Add to turn │                 │ Synthesize  │
    │ history     │                 │ into style  │
    └─────────────┘                 └─────────────┘
                                          │
                                          ▼
                              ┌───────────────────┐
                              │ ADAPTIVE SYSTEM   │
                              │ PROMPT            │
                              │                   │
                              │ "User prefers     │
                              │  casual, warm     │
                              │  interaction..."  │
                              └───────────────────┘
```

---

## Motivation

### The Problem: One-Size-Fits-All Interaction

Current Sunwell remembers **what** you told it but not **how** you like to communicate:

| What We Capture Today | What We Miss |
|-----------------------|--------------|
| "User's name is lb" | "User prefers casual tone" |
| "User has cats Milo and Kiki" | "User values being remembered" |
| "User works on documentation" | "User asks testing questions" |

### Observation: Behaviors Are Signal, Not Noise

During testing, we observed the tiny LLM extracting behavioral observations:

```
🧠 Naaru noted: The user is responding to a positive comment.
🧠 Naaru noted: The user is using "lol" as a response.
🧠 Naaru noted: The user is expressing appreciation for the other person.
```

Initial reaction: "Too noisy, filter these out."

Better reaction: **These are valuable for shaping interaction style.**

### The Opportunity

If we digest behavioral observations into an **identity layer**, the assistant can:

1. **Adapt tone** — Formal vs casual based on user patterns
2. **Anticipate needs** — "User tests memory, proactively reference past context"
3. **Build rapport** — Feel like it "knows" the user beyond just facts
4. **Improve over time** — Identity evolves with each interaction

---

## Design

### Two-Tier Extraction

**Extends**: `src/sunwell/simulacrum/extractor.py` — the existing `_FACT_EXTRACTION_PROMPT`

The RFC extends (not replaces) the existing extraction system by adding `BEHAVIOR:` label support. This ensures backward compatibility and reuses proven patterns.

```python
# Canonical prompt - extends existing extractor.py
_TWO_TIER_EXTRACTION_PROMPT = """Extract from this user message into two categories:

FACTS - Durable information worth remembering across sessions:
- Names (user, pets, family, colleagues)
- Preferences (tools, languages, styles)
- Context (job, projects, location)
- Relationships (has a cat, works with X)

BEHAVIORS - Interaction patterns that shape communication style:
- Communication style (formal, casual, terse, verbose)
- Emotional signals (appreciative, frustrated, testing)
- Conversation patterns (asks follow-ups, changes topics)
- Response preferences (likes detail, prefers brevity)

User message: "{message}"

Output format (one per line):
FACT: [fact to remember]
BEHAVIOR: [behavioral observation]

If nothing notable, output: NONE

Important: Only extract clear signals. Skip ambiguous or uncertain observations.
"""
```

**Migration path**: Update `extract_user_facts_with_llm()` to use new prompt and return `(facts, behaviors)` tuple instead of just facts.

### Identity Storage

**Two-level storage**: Session-specific with global fallback (MVP includes carry-forward).

```yaml
# ~/.sunwell/global_identity.yaml (user-wide, read on session start)
version: 1
last_updated: "2026-01-15T10:00:00Z"
observation_count: 127  # Total across all sessions

identity:
  confidence: 0.85
  prompt: |
    This user generally prefers casual, warm conversation. They value
    being remembered and may test memory recall. Match their informal tone.

# .sunwell/memory/sessions/{session}_identity.yaml (session-specific)
version: 1
last_updated: "2026-01-16T14:30:00Z"
turn_count: 47
inherits_from: "~/.sunwell/global_identity.yaml"

# Raw behavioral observations (recent 50 for this session)
observations:
  - timestamp: "2026-01-16T14:25:00Z"
    observation: "Uses casual language (lol, etc.)"
    confidence: 0.9
  - timestamp: "2026-01-16T14:26:00Z"
    observation: "Asks testing questions to verify memory"
    confidence: 0.85
  - timestamp: "2026-01-16T14:28:00Z"
    observation: "Expresses appreciation when remembered"
    confidence: 0.8

# Synthesized identity (session-specific, may override global)
identity:
  confidence: 0.88
  tone: "casual and warm"
  pace: "conversational, not rushed"
  values:
    - "being remembered and acknowledged"
    - "genuine interaction over formality"
    - "efficiency without coldness"
  
  prompt: |
    This user prefers casual, friendly conversation. They appreciate
    when you remember details from previous interactions and may ask
    testing questions to verify memory. Keep responses warm and
    acknowledge context naturally. Use conversational language—it's
    okay to match their casual tone.
```

#### Session Carry-Forward (MVP)

On session start:
```python
def load_identity(session_path: Path) -> Identity:
    """Load identity with global fallback."""
    # 1. Try session-specific
    if session_path.exists():
        return _load_yaml(session_path)
    
    # 2. Fall back to global (read-only inheritance)
    global_path = Path.home() / ".sunwell" / "global_identity.yaml"
    if global_path.exists():
        identity = _load_yaml(global_path)
        identity.inherited = True  # Mark as inherited, don't modify
        return identity
    
    # 3. Fresh start
    return Identity(observations=[], prompt=None)
```

On session end:
```python
async def persist_to_global(session_identity: Identity, global_path: Path):
    """Merge session learnings into global identity."""
    global_identity = load_identity(global_path) if global_path.exists() else Identity()
    
    # Merge observations (keep recent 100 globally)
    merged_obs = global_identity.observations + session_identity.observations
    global_identity.observations = merged_obs[-100:]
    
    # Re-digest with combined observations
    global_identity = await digest_identity(
        observations=[o.observation for o in global_identity.observations],
        current_identity=global_identity,
        tiny_model=get_tiny_model(),
    )
    
    save_yaml(global_path, global_identity)
```

### Identity Digest Process

#### Adaptive Digest Frequency

Digest triggers are **adaptive**, not fixed:

| Condition | Digest Trigger |
|-----------|----------------|
| **Early session** (turns 1-5) | First digest at turn 5 if ≥3 behaviors observed |
| **Normal cadence** | Every 10 turns |
| **High activity** | If 5+ behaviors in last 3 turns, digest immediately |
| **Session end** | Always digest on graceful exit |
| **Manual** | `/identity refresh` forces re-synthesis |

```python
def needs_digest(self, current_turn_count: int, recent_observations: int) -> bool:
    """Adaptive digest frequency based on observation density."""
    turns_since_digest = current_turn_count - self.identity.turn_count_at_digest
    
    # Early session: digest sooner to establish baseline
    if current_turn_count <= 5 and len(self.identity.observations) >= 3:
        return self.identity.last_digest is None
    
    # High activity: many behaviors in short window
    if recent_observations >= 5 and turns_since_digest >= 3:
        return True
    
    # Normal cadence
    return turns_since_digest >= 10
```

#### Digest with Validation

```python
# Constants
MAX_IDENTITY_PROMPT_LENGTH = 500  # chars - fits in context budget
MIN_IDENTITY_CONFIDENCE = 0.6    # below this, don't inject

async def digest_identity(
    observations: list[str],
    current_identity: Identity | None,
    tiny_model: Model,
) -> Identity:
    """Synthesize behavioral observations into validated identity prompt."""
    
    prompt = f"""Based on these behavioral observations about a user, synthesize
an identity profile that describes how to interact with them.

Previous identity (if any):
{current_identity.prompt if current_identity else "None - first synthesis"}

Recent observations:
{chr(10).join(f'- {obs}' for obs in observations[-20:])}

Output a brief (3-5 sentence, MAX 500 characters) interaction guide that captures:
1. Preferred tone and style
2. What they value in conversation
3. Any patterns to be aware of

Write in second person ("This user prefers...").
End with CONFIDENCE: [0.0-1.0] based on observation consistency."""
    
    result = await tiny_model.generate(prompt)
    
    # Parse and validate
    content = result.content.strip()
    confidence = _extract_confidence(content)
    prompt_text = _extract_prompt(content)
    
    # Enforce length limit
    if len(prompt_text) > MAX_IDENTITY_PROMPT_LENGTH:
        prompt_text = prompt_text[:MAX_IDENTITY_PROMPT_LENGTH].rsplit(' ', 1)[0] + "..."
    
    # Only return if confident enough
    if confidence < MIN_IDENTITY_CONFIDENCE:
        return current_identity or Identity(observations=[], prompt=None)
    
    return Identity(
        observations=observations,
        prompt=prompt_text,
        confidence=confidence,
    )

def _extract_confidence(content: str) -> float:
    """Extract confidence score from digest output."""
    import re
    match = re.search(r'CONFIDENCE:\s*([\d.]+)', content)
    return float(match.group(1)) if match else 0.7

def _extract_prompt(content: str) -> str:
    """Extract prompt text, removing confidence line."""
    import re
    return re.sub(r'\n?CONFIDENCE:.*$', '', content, flags=re.IGNORECASE).strip()
```

### System Prompt Injection

The identity prompt is injected into the system prompt:

```python
def build_system_prompt(lens_prompt: str, identity: Identity | None) -> str:
    base = lens_prompt
    
    if identity and identity.prompt:
        base += f"\n\n## User Interaction Style\n\n{identity.prompt}"
    
    return base
```

---

## Implementation

### New Module: `src/sunwell/identity/`

```
src/sunwell/identity/
├── __init__.py
├── extractor.py      # Two-tier extraction (facts vs behaviors)
├── store.py          # Identity storage and loading
├── digest.py         # Behavior → Identity synthesis
└── injection.py      # System prompt integration
```

### Phase 1: Two-Tier Extraction

**Extends**: `src/sunwell/simulacrum/extractor.py`

Update `extract_user_facts_with_llm()` to use the canonical two-tier prompt and return both facts and behaviors:

```python
# In extractor.py - extend existing function

async def extract_with_categories(
    message: str,
    model: "ModelProtocol",
) -> tuple[list[tuple[str, str, float]], list[tuple[str, float]]]:
    """Extract facts and behaviors from user message.
    
    Returns:
        (facts, behaviors) where:
        - facts: list of (fact_text, category, confidence)
        - behaviors: list of (behavior_text, confidence)
    """
    from sunwell.models.protocol import Message
    
    prompt = _TWO_TIER_EXTRACTION_PROMPT.format(message=message)
    
    try:
        result = await model.generate((Message(role="user", content=prompt),))
        response = result.content.strip()
        
        facts, behaviors = [], []
        for line in response.split("\n"):
            line = line.strip()
            if line.startswith("FACT:"):
                fact_text = line[5:].strip()
                if fact_text and fact_text.upper() != "NONE" and len(fact_text) > 3:
                    facts.append((fact_text, "fact", 0.85))
            elif line.startswith("BEHAVIOR:"):
                behavior_text = line[9:].strip()
                if behavior_text and len(behavior_text) > 3:
                    behaviors.append((behavior_text, 0.8))
            elif line.upper() == "NONE":
                break
        
        return facts, behaviors
    except Exception:
        # Fall back to regex for facts only
        return extract_user_facts(message), []


# Backward-compatible wrapper
async def extract_user_facts_with_llm(
    user_message: str,
    model: "ModelProtocol",
) -> list[tuple[str, str, float]]:
    """Extract facts (backward compatible). Use extract_with_categories() for full extraction."""
    facts, _ = await extract_with_categories(user_message, model)
    return facts
```

### Phase 2: Identity Storage

```python
# store.py
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional
import yaml

MIN_IDENTITY_CONFIDENCE = 0.6
MAX_OBSERVATIONS_PER_SESSION = 50
MAX_OBSERVATIONS_GLOBAL = 100

@dataclass
class Observation:
    timestamp: datetime
    observation: str
    confidence: float = 0.8
    turn_id: str | None = None

@dataclass
class Identity:
    observations: list[Observation] = field(default_factory=list)
    tone: str | None = None
    values: list[str] = field(default_factory=list)
    prompt: str | None = None
    confidence: float = 0.0  # Digest confidence score
    last_digest: datetime | None = None
    turn_count_at_digest: int = 0
    inherited: bool = False  # True if loaded from global, not session
    
    def is_usable(self) -> bool:
        """Returns True if identity should be injected into system prompt."""
        return (
            self.prompt is not None 
            and len(self.prompt) > 10
            and self.confidence >= MIN_IDENTITY_CONFIDENCE
        )

class IdentityStore:
    def __init__(self, session_path: Path):
        self.session_path = session_path.with_suffix('.identity.yaml')
        self.global_path = Path.home() / ".sunwell" / "global_identity.yaml"
        self.identity = self._load()
        self._recent_observation_count = 0  # For adaptive digest
    
    def _load(self) -> Identity:
        """Load identity with global fallback."""
        if self.session_path.exists():
            return self._load_yaml(self.session_path)
        if self.global_path.exists():
            identity = self._load_yaml(self.global_path)
            identity.inherited = True
            return identity
        return Identity()
    
    def add_observation(self, observation: str, confidence: float = 0.8, turn_id: str | None = None):
        """Add behavioral observation."""
        self.identity.observations.append(Observation(
            timestamp=datetime.now(),
            observation=observation,
            confidence=confidence,
            turn_id=turn_id,
        ))
        # Keep only recent N for session
        self.identity.observations = self.identity.observations[-MAX_OBSERVATIONS_PER_SESSION:]
        self._recent_observation_count += 1
        self._save()
    
    def needs_digest(self, current_turn_count: int) -> bool:
        """Adaptive digest frequency based on observation density."""
        turns_since_digest = current_turn_count - self.identity.turn_count_at_digest
        
        # Early session: establish baseline quickly
        if current_turn_count <= 5 and len(self.identity.observations) >= 3:
            return self.identity.last_digest is None
        
        # High activity: many behaviors in short window
        if self._recent_observation_count >= 5 and turns_since_digest >= 3:
            self._recent_observation_count = 0  # Reset counter
            return True
        
        # Normal cadence
        return turns_since_digest >= 10
    
    def _load_yaml(self, path: Path) -> Identity:
        with open(path) as f:
            data = yaml.safe_load(f)
        # ... deserialize to Identity
        return Identity(**data.get("identity", {}))
    
    def _save(self):
        # ... serialize to YAML
        pass
```

### Phase 3: CLI Integration

**Extends**: `src/sunwell/cli.py` — `_chat_loop()` and helper functions

The identity system hooks into two points in the chat loop:

1. **On user input**: Extract behaviors (parallel with fact extraction)
2. **After turn**: Check if digest needed

```python
# In cli.py _chat_loop - add identity store initialization

async def _chat_loop(
    dag: "ConversationDAG",
    store: "SimulacrumStore", 
    # ... existing params ...
    identity_enabled: bool = True,  # New flag
) -> None:
    # Initialize identity store
    from sunwell.identity.store import IdentityStore
    identity_store = IdentityStore(memory_path / "sessions" / dag.session_id) if identity_enabled else None
    
    # ... existing setup ...
    
    while True:
        user_input = await get_input()
        
        # PARALLEL: Extract facts AND behaviors while preparing response
        extraction_task = None
        if identity_store and tiny_model:
            extraction_task = asyncio.create_task(
                _extract_facts_and_behaviors(user_input, tiny_model, dag, identity_store, console)
            )
        
        # Generate response (existing code)
        response = await generate_response(...)
        
        # Wait for extraction if still running
        if extraction_task:
            await extraction_task
        
        # Check if identity digest needed
        if identity_store and identity_store.needs_digest(len(dag.turns)):
            asyncio.create_task(_digest_identity(
                identity_store, tiny_model, len(dag.turns), console
            ))
        
        # ... rest of loop ...


async def _extract_facts_and_behaviors(
    user_input: str,
    tiny_model: "ModelProtocol",
    dag: "ConversationDAG",
    identity_store: "IdentityStore",
    console,
) -> None:
    """Extract facts and behaviors from user input in parallel with response generation."""
    from sunwell.simulacrum.extractor import extract_with_categories
    from sunwell.simulacrum.turn import Learning
    
    try:
        facts, behaviors = await extract_with_categories(user_input, tiny_model)
        
        # Store facts in DAG (existing behavior)
        for fact_text, category, confidence in facts:
            learning = Learning(
                fact=fact_text,
                source_turns=(dag.active_head,) if dag.active_head else (),
                confidence=confidence,
                category=category,
            )
            dag.add_learning(learning)
            console.print(f"[dim cyan]🧠 Naaru noted:[/dim cyan] [dim]{fact_text[:60]}...[/dim]")
        
        # Store behaviors in identity store (NEW)
        for behavior_text, confidence in behaviors:
            identity_store.add_observation(behavior_text, confidence)
            console.print(f"[dim magenta]👁 Naaru observed:[/dim magenta] [dim]{behavior_text[:60]}...[/dim]")
    
    except Exception as e:
        console.print(f"[dim red]Extraction failed: {e}[/dim red]")


async def _digest_identity(
    store: "IdentityStore",
    model: "ModelProtocol",
    turn_count: int,
    console,
):
    """Background task to synthesize identity from observations."""
    from sunwell.identity.digest import digest_identity
    
    new_identity = await digest_identity(
        observations=[o.observation for o in store.identity.observations],
        current_identity=store.identity,
        tiny_model=model,
    )
    
    # Only update if digest succeeded with confidence
    if new_identity.is_usable():
        store.identity.prompt = new_identity.prompt
        store.identity.confidence = new_identity.confidence
        store.identity.turn_count_at_digest = turn_count
        store.identity.last_digest = datetime.now()
        store._save()
        
        console.print(f"[dim cyan]🧠 Naaru updated identity model (confidence: {new_identity.confidence:.0%})[/dim cyan]")
```

**System prompt injection** happens in the existing `build_system_prompt()` call:

```python
# In cli.py or engine.py where system prompt is built
def build_system_prompt(lens_prompt: str, identity_store: IdentityStore | None) -> str:
    base = lens_prompt
    
    if identity_store and identity_store.identity.is_usable():
        base += f"\n\n## User Interaction Style\n\n{identity_store.identity.prompt}"
    
    return base
```

### Phase 4: Inspection Commands

```
/identity - View current identity model
/identity rate - Rate the identity model (1-5)
/identity refresh - Force re-synthesis from observations
/identity clear - Reset identity (start fresh)
/identity pause - Disable behavioral learning
/identity resume - Re-enable behavioral learning
/identity export - Export identity data to JSON
```

**Main view** (`/identity`):

```
╭─────────────────── Identity Model ───────────────────╮
│ Status: Active ✓     Confidence: 88%                 │
│ Last Updated: 2 minutes ago (turn 47)                │
│ Source: session (inherits from global)               │
│                                                      │
│ Tone: casual and warm                                │
│                                                      │
│ Values:                                              │
│   • being remembered and acknowledged                │
│   • genuine interaction over formality               │
│   • efficiency without coldness                      │
│                                                      │
│ Interaction Guide:                                   │
│   This user prefers casual, friendly conversation.   │
│   They appreciate when you remember details from     │
│   previous interactions and may ask testing          │
│   questions to verify memory. Keep responses warm.   │
│                                                      │
│ Recent Observations (5 of 23):                       │
│   • Uses casual language (lol, etc.)         [0.9]   │
│   • Asks testing questions to verify memory  [0.85]  │
│   • Expresses appreciation when remembered   [0.8]   │
│   • Prefers concise responses                [0.75]  │
│   • Engages in back-and-forth dialogue       [0.7]   │
│                                                      │
│ [/identity rate] to provide feedback                 │
╰──────────────────────────────────────────────────────╯
```

**Rating flow** (`/identity rate`):

```
╭────────── Rate Your Identity Model ──────────╮
│                                              │
│ Does this identity model accurately capture  │
│ how you like to interact?                    │
│                                              │
│   1 - Not at all                             │
│   2 - Somewhat off                           │
│   3 - Partially accurate                     │
│   4 - Mostly accurate                        │
│   5 - Spot on!                               │
│                                              │
│ Your rating helps improve Naaru's learning.  │
╰──────────────────────────────────────────────╯

> 4

Thanks! Rating saved. [Telemetry: opt-in only]
```

---

## Privacy Considerations

### Local-Only by Default

- All identity data stored locally in `.sunwell/` and `~/.sunwell/`
- Never sent to external APIs (unless explicitly configured)
- Tiny LLM runs locally for extraction and digest
- No cloud sync, no remote storage

### User Control

| Command | Effect |
|---------|--------|
| `/identity clear` | Reset identity model completely |
| `/identity pause` | Disable behavioral learning (keeps existing) |
| `/identity resume` | Re-enable behavioral learning |
| `/identity export` | Export identity data to JSON file |
| `--no-identity` | Start session with identity disabled |
| `sunwell config identity.enabled false` | Disable globally |

### Transparency

- All observations shown in real-time (`👁 Naaru observed:`)
- `/identity` command shows exactly what's been learned
- No hidden profiling—everything inspectable
- Confidence scores visible for each observation

### Telemetry (Opt-In Only)

Telemetry for A/B testing and quality improvement is **opt-in**:

```bash
# Enable telemetry (helps improve Naaru)
sunwell config telemetry.enabled true

# Check status
sunwell config telemetry.enabled
# → false (default)
```

When enabled, **only these signals are collected**:
- Extraction latency (ms)
- Observation counts (not content)
- `/identity rate` feedback scores
- Session duration

**Never collected**:
- Actual observation text
- Identity prompt content
- User messages
- Any PII

```python
# Telemetry guard in all logging functions
def _log(event: dict):
    if not config.get("telemetry.enabled", False):
        return  # No-op when disabled
    
    # Sanitize: remove any potential PII
    sanitized = {k: v for k, v in event.items() if k in ALLOWED_FIELDS}
    _send_to_analytics(sanitized)
```

---

## Integration with Naaru

### Consolidator Shard Enhancement

The Consolidator Shard already extracts learnings. Extend to handle identity:

```python
class ConsolidatorShard(Shard):
    async def process(self, task: Task) -> ShardResult:
        # Extract facts → DAG learnings
        facts = await self._extract_facts(task.user_input)
        
        # Extract behaviors → Identity store
        behaviors = await self._extract_behaviors(task.user_input)
        
        # Store both
        for fact in facts:
            self.convergence.add_learning(fact)
        for behavior in behaviors:
            self.identity_store.add_observation(behavior)
```

### Convergence Integration

**Decision**: Identity is **out-of-band** — it does NOT consume one of the 7 Convergence slots.

Rationale:
- Identity is always relevant (not task-dependent like memory/context)
- Should not be evicted by task-specific slots
- Injected at system prompt level, not context level

```python
class Convergence:
    def __init__(self, capacity: int = 7):
        self.slots = {}  # 7 slots for task context (unchanged)
        # Identity is NOT stored here — it's injected via build_system_prompt()
    
# Identity injection happens in the system prompt builder, not Convergence:
def build_system_prompt(
    lens_prompt: str, 
    identity: Identity | None,
    max_identity_chars: int = 500,
) -> str:
    """Build system prompt with identity injection (out-of-band)."""
    base = lens_prompt
    
    if identity and identity.prompt and identity.confidence >= MIN_IDENTITY_CONFIDENCE:
        # Inject as a separate section, not competing with task context
        identity_section = identity.prompt[:max_identity_chars]
        base += f"\n\n## User Interaction Style\n\n{identity_section}"
    
    return base
```

This keeps the 7-slot Convergence focused on active task context while identity shapes the overall interaction style.

---

## Success Metrics

### Quantitative Metrics

| Metric | Target | Measurement Method |
|--------|--------|-------------------|
| **Extraction Precision** | >80% | Manual review: 100 random extractions, label as correct/incorrect |
| **Extraction Recall** | >70% | Review 50 conversations, count missed behavioral signals |
| **Digest Quality** | >75% approval | `/identity rate` command: thumbs up/down after viewing |
| **Performance Impact** | <200ms p95 | Instrumented timing in `extract_with_categories()` |
| **Context Budget** | <5% overhead | Measure identity prompt size vs total context |
| **Privacy Compliance** | 100% | Audit: grep for API calls in identity module |

### A/B Testing Design

To validate "interaction improvement" objectively:

```python
# Telemetry hooks (opt-in)
@dataclass
class IdentityTelemetry:
    session_id: str
    identity_enabled: bool  # A/B flag
    turn_count: int
    user_sentiment_signals: list[str]  # "lol", "thanks", "ugh", etc.
    session_duration_minutes: float
    explicit_feedback: int | None  # 1-5 rating if provided

# A/B assignment
def should_enable_identity(session_id: str) -> bool:
    """50/50 split for A/B testing."""
    return hash(session_id) % 2 == 0
```

**Hypothesis**: Sessions with identity enabled will show:
- 15%+ longer session duration (engagement proxy)
- 20%+ more positive sentiment signals
- Higher explicit feedback scores when collected

### Measurement Timeline

| Phase | Duration | Metrics Collected |
|-------|----------|-------------------|
| **Alpha** (internal) | 2 weeks | Extraction accuracy, digest quality, performance |
| **Beta** (opt-in) | 4 weeks | A/B testing, sentiment signals, session duration |
| **GA** | Ongoing | Aggregated quality scores, `/identity rate` feedback |

### Instrumentation

```python
# Add to identity/telemetry.py
def log_extraction(message: str, facts: list, behaviors: list, latency_ms: float):
    """Log extraction for quality analysis."""
    if not TELEMETRY_ENABLED:
        return
    
    _log({
        "event": "extraction",
        "message_length": len(message),
        "fact_count": len(facts),
        "behavior_count": len(behaviors),
        "latency_ms": latency_ms,
        "timestamp": datetime.now().isoformat(),
    })

def log_identity_view(identity: Identity, rating: int | None = None):
    """Log when user views/rates identity."""
    if not TELEMETRY_ENABLED:
        return
    
    _log({
        "event": "identity_view",
        "prompt_length": len(identity.prompt) if identity.prompt else 0,
        "confidence": identity.confidence,
        "observation_count": len(identity.observations),
        "user_rating": rating,
        "timestamp": datetime.now().isoformat(),
    })
```

---

## Open Questions

| Question | Options | Current Leaning |
|----------|---------|-----------------|
| **Should behaviors have categories?** | Single "behavior" type vs subcategories (tone, pace, values) | Single type for MVP, categorize in digest |
| **Conflict resolution for contradictory behaviors?** | Recency wins, majority wins, LLM decides | Recency + LLM synthesis |
| **Identity injection position?** | Start of system prompt, end, or configurable | End (after lens, before context) |
| **Minimum observations for first digest?** | 1, 3, 5 | 3 (enough signal, not too slow) |
| **Should identity affect model selection?** | Formal user → more capable model | No for MVP, future extension |

---

## Future Extensions

> **MVP includes**: Two-tier extraction, session storage with global fallback, adaptive digest, `/identity` command.
> 
> **Future** (post-MVP): Multi-user, versioning, context-specific overrides.

### Multi-User Identity

For shared sessions or team use:

```yaml
identities:
  logan:
    prompt: "Prefers casual tone..."
    last_active: "2026-01-16T14:00:00Z"
  alex:
    prompt: "Values technical precision..."
    last_active: "2026-01-16T10:00:00Z"

# Detection via explicit /user switch or LLM classification
active_user: "logan"
```

### Context-Specific Identity Overrides

Different interaction styles for different contexts:

```yaml
# ~/.sunwell/global_identity.yaml
global_identity:
  prompt: "Generally prefers casual tone..."
  
context_overrides:
  code-review:
    prompt: "More formal and thorough for code review..."
    trigger: "review|audit|check"
  
  brainstorm:
    prompt: "Exploratory, creative, no wrong answers..."
    trigger: "brainstorm|ideas|explore"
```

### Identity Versioning

Track how identity evolves over time:

```yaml
identity_history:
  - version: 1
    date: "2026-01-10"
    observation_count: 15
    prompt: "New user, formal tone..."
  - version: 2
    date: "2026-01-15"
    observation_count: 47
    prompt: "Casual tone established..."
    delta: "Shifted from formal to casual based on repeated 'lol', 'thanks!' patterns"
```

### Identity-Aware Model Routing

```python
# Future: Identity influences model selection
def select_model(task: str, identity: Identity) -> str:
    # User who values precision → stronger model for technical tasks
    if "precision" in identity.values and is_technical_task(task):
        return "claude-3-opus"
    # User who prefers brevity → faster model
    if identity.tone == "terse":
        return "claude-3-haiku"
    return "claude-3-sonnet"  # default
```

---

## Migration & Rollout

### Rollout Plan

| Phase | Duration | Scope | Gates |
|-------|----------|-------|-------|
| **Alpha** | 2 weeks | Internal testing | Extraction accuracy >70% |
| **Beta** | 4 weeks | Opt-in users (`--identity-beta`) | Digest quality >60% approval |
| **GA** | Ongoing | Default on | A/B shows positive engagement |

### Feature Flags

```python
# config.py
IDENTITY_FLAGS = {
    "identity.enabled": True,           # Master switch
    "identity.extraction.enabled": True, # Just extraction, no digest
    "identity.digest.enabled": True,     # Full digest
    "identity.global_fallback": True,    # Use global identity
    "identity.show_observations": True,  # Show 👁 messages
    "identity.telemetry": False,         # Opt-in telemetry
}
```

### Backward Compatibility

- Sessions without identity files work normally
- Identity injection is additive (doesn't break existing system prompts)
- `/identity` commands gracefully handle missing data
- `--no-identity` flag for users who prefer current behavior

---

## References

- RFC-019: Naaru Architecture (Shards, Convergence) — coordination patterns
- RFC-020: Cognitive Router (Tiny LLM patterns) — extraction architecture
- `src/sunwell/simulacrum/extractor.py` — existing fact extraction code
- `src/sunwell/cli.py:2693-2781` — current Naaru fact extraction hooks
- Research: Personalization in conversational AI systems
- Inspiration: Claude's character/personality system, ChatGPT memory

---

## Appendix: Example Extraction Output

**User message**: "oh wow you do lol nice"

**Two-tier extraction**:
```
FACT: NONE
BEHAVIOR: Uses casual language with expressions like "lol"
BEHAVIOR: Expresses genuine appreciation and surprise
BEHAVIOR: Prefers brief, conversational responses
```

**User message**: "i have 2 cats, milo and kiki. kiki is a bengal."

**Two-tier extraction**:
```
FACT: User has two cats named Milo and Kiki
FACT: Kiki is a Bengal cat
BEHAVIOR: Shares personal details willingly
BEHAVIOR: Provides specific details when relevant
```

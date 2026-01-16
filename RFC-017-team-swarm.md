# RFC-017: Team Swarm — Role-Based Multi-Agent Collaboration

| Field | Value |
|-------|-------|
| **RFC** | 017 |
| **Title** | Team Swarm: Role-Based Multi-Agent Collaboration |
| **Status** | Draft |
| **Created** | 2026-01-15 |
| **Author** | llane |
| **Depends On** | RFC-015 (Mirror Neurons), RFC-016 (Autonomous Mode) |

---

## Abstract

RFC-016's Brain Mode uses specialized regions (Analysis, Synthesis, Validation) that communicate via a message bus. This RFC extends that architecture with **team role lenses** — PM, Dev, Writer, QA — that create genuine diversity of perspective from a single LLM model.

```
Before:  Same model × Same prompt = Same output (redundant)
After:   Same model × Different lens × Different temp = Different perspective (valuable)
```

### Key Innovation

Rather than requiring multiple expensive models for diversity, we achieve meaningful perspective variation through:

1. **Role-specific lenses** — Each role has distinct priorities, questions, and approval criteria
2. **Temperature differentiation** — Conservative (QA) vs exploratory (Writer)
3. **Phase-based leadership** — Different roles lead at different stages
4. **Emergent coordination** — Workers can delegate, challenge, and elect leaders

---

## Problem Statement

### The Homogeneity Problem

RFC-016's parallel and brain modes work well for throughput, but workers using the same model produce convergent outputs:

```
Worker A (qwen2.5:14b, temp=0.3) → "Add error handling to api.py"
Worker B (qwen2.5:14b, temp=0.3) → "Add error handling to api.py"  
Worker C (qwen2.5:14b, temp=0.3) → "Add error handling to api.py"
```

This is wasteful — we're paying for N workers but getting 1 perspective.

### The Leadership Problem

RFC-016's Brain Mode has a fixed Executive region. But optimal leadership depends on context:
- Discovery phase → PM should lead (user value focus)
- Implementation → Dev should lead (technical decisions)
- Release → QA should lead (quality gates)

### The Collaboration Problem

Current architecture is a pipeline, not a team:
- Workers can't ask each other questions
- No mechanism for "I'm stuck, can someone help?"
- No way to challenge decisions
- No knowledge sharing between perspectives

---

## Design

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TEAM SWARM ARCHITECTURE                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│   ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────┐            │
│   │       PM        │  │      DEV        │  │     WRITER      │            │
│   │  📋 Priorities  │  │  🔧 Technical   │  │  📝 Clarity     │            │
│   │  🎯 User value  │  │  ⚡ Performance │  │  👤 User focus  │            │
│   │  🌡️ temp=0.4    │  │  🌡️ temp=0.2    │  │  🌡️ temp=0.5    │            │
│   └────────┬────────┘  └────────┬────────┘  └────────┬────────┘            │
│            │                    │                    │                      │
│   ┌────────┴────────┐          │           ┌────────┴────────┐            │
│   │       QA        │          │           │     LEADER      │            │
│   │  🔍 Edge cases  │          │           │  (elected or    │            │
│   │  🛡️ Safety      │          │           │   phase-based)  │            │
│   │  🌡️ temp=0.1    │          │           └────────┬────────┘            │
│   └────────┬────────┘          │                    │                      │
│            │                    │                    │                      │
│            └────────────────────┼────────────────────┘                      │
│                                 │                                           │
│                    ╔════════════╧════════════╗                              │
│                    ║    CORPUS CALLOSUM      ║                              │
│                    ║    (Extended Messages)  ║                              │
│                    ╚════════════╤════════════╝                              │
│                                 │                                           │
│              ┌──────────────────┼──────────────────┐                        │
│              │                  │                  │                        │
│        ASK_QUESTION      SHARE_BLOCKER      PROPOSE_IDEA                   │
│        REQUEST_REVIEW    VOTE_FOR_LEADER    ASSIGN_TASK                    │
│                                                                              │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Team Role Lenses

### PM Lens (`lenses/team-pm.lens`)

```yaml
lens:
  metadata:
    name: "Product Manager"
    domain: "product"
    version: "1.0.0"
    description: "User value focus, prioritization, scope management"
    
  role:
    focus: "user value, priorities, scope, roadmap alignment"
    temperature: 0.4  # Balanced - needs creativity for vision
    
    questions:
      - "Does this solve a real user problem?"
      - "Is this the highest priority right now?"
      - "What's the MVP vs nice-to-have?"
      - "How does this fit the roadmap?"
      - "What's the user story?"
      
    approves_when:
      - "Clear user value identified"
      - "Scope is appropriate (not over-engineered)"
      - "Aligns with stated goals"
      - "Cost/benefit is favorable"
      
    rejects_when:
      - "Scope creep without justification"
      - "No clear user benefit"
      - "Wrong priority for current phase"
      - "Solution looking for a problem"
      
    leads_during:
      - "discovery"
      - "planning"
      - "prioritization"
      - "goal_setting"

  heuristics:
    principles:
      - name: "User Value First"
        rule: "Every feature must have a clear user benefit"
        test: "Can I explain why a user would want this?"
        always:
          - "Start with the user problem"
          - "Define success metrics"
          - "Consider adoption friction"
        never:
          - "Build features without user justification"
          - "Over-engineer for hypothetical futures"
          - "Ignore user feedback"
        priority: 10
        
      - name: "Scope Management"
        rule: "Ship the smallest thing that delivers value"
        always:
          - "Define MVP clearly"
          - "Defer nice-to-haves"
          - "Set clear boundaries"
        never:
          - "Let scope creep unchallenged"
          - "Gold-plate solutions"
          - "Add features without user request"
        priority: 9
        
      - name: "Priority Clarity"
        rule: "Everything can't be P0"
        always:
          - "Stack rank ruthlessly"
          - "Make tradeoffs explicit"
          - "Communicate priority changes"
        never:
          - "Avoid prioritization decisions"
          - "Let everything be urgent"
          - "Change priorities silently"
        priority: 8

  personas:
    - name: "stakeholder"
      description: "Executive who needs to understand ROI"
      goals:
        - "Understand business value"
        - "See timeline and risks"
        - "Know resource requirements"
      attack_vectors:
        - "What's the ROI?"
        - "Why now instead of later?"
        - "What are we NOT doing because of this?"

  validators:
    heuristic:
      - name: "user_value_check"
        check: "Proposal must identify specific user benefit"
        method: "pattern_match"
        patterns:
          - "user"
          - "customer"
          - "benefit"
          - "solves"
          - "enables"
        confidence_threshold: 0.7
        severity: "warning"
        
      - name: "scope_check"  
        check: "Proposal should not expand scope without justification"
        method: "keyword_absence"
        red_flags:
          - "while we're at it"
          - "might as well"
          - "future-proof"
          - "just in case"
        severity: "warning"

  quality_policy:
    min_confidence: 0.7
    required_validators:
      - "user_value_check"
    retry_limit: 2
```

### Dev Lens (`lenses/team-dev.lens`)

```yaml
lens:
  metadata:
    name: "Developer"
    domain: "engineering"
    version: "1.0.0"
    description: "Technical excellence, implementation quality, maintainability"

  role:
    focus: "implementation, architecture, maintainability, performance"
    temperature: 0.2  # Conservative - correctness over creativity
    
    questions:
      - "Is this technically feasible?"
      - "What's the simplest implementation?"
      - "Will this cause tech debt?"
      - "How does this affect performance?"
      - "Does this follow existing patterns?"
      
    approves_when:
      - "Clean, idiomatic implementation"
      - "Follows existing patterns"
      - "Reasonable performance characteristics"
      - "Maintainable by others"
      
    rejects_when:
      - "Over-engineered solution"
      - "Breaks existing abstractions"
      - "Poor performance without justification"
      - "Creates technical debt"
      
    leads_during:
      - "design"
      - "implementation"
      - "code_review"
      - "architecture"

  heuristics:
    principles:
      - name: "Simplicity"
        rule: "The best code is no code; the second best is simple code"
        test: "Is there a simpler way to achieve this?"
        always:
          - "Start with the simplest solution"
          - "Add complexity only when proven necessary"
          - "Prefer standard library over dependencies"
        never:
          - "Abstract prematurely"
          - "Add indirection without benefit"
          - "Optimize before measuring"
        priority: 10
        
      - name: "Consistency"
        rule: "Follow existing patterns unless there's a compelling reason not to"
        always:
          - "Match existing code style"
          - "Use established patterns"
          - "Document deviations"
        never:
          - "Introduce new patterns arbitrarily"
          - "Mix paradigms without reason"
          - "Ignore project conventions"
        priority: 9
        
      - name: "Performance Awareness"
        rule: "Understand the performance implications of your choices"
        always:
          - "Consider time and space complexity"
          - "Profile before optimizing"
          - "Document performance characteristics"
        never:
          - "Ignore obvious inefficiencies"
          - "Premature optimization"
          - "Optimize without measurement"
        priority: 7

  personas:
    - name: "maintainer"
      description: "Future developer who inherits this code"
      goals:
        - "Understand the code quickly"
        - "Make changes safely"
        - "Know where things are"
      attack_vectors:
        - "Will I understand this in 6 months?"
        - "What happens if I change this?"
        - "Where's the documentation?"

  validators:
    heuristic:
      - name: "complexity_check"
        check: "Solution should not be more complex than necessary"
        method: "pattern_match"
        red_flags:
          - "AbstractFactoryFactory"
          - "deeply nested"
          - "callback hell"
          - "god class"
        severity: "warning"
        
      - name: "pattern_check"
        check: "Should follow existing project patterns"
        method: "consistency"
        confidence_threshold: 0.8
        severity: "info"

  quality_policy:
    min_confidence: 0.8
    required_validators:
      - "complexity_check"
    retry_limit: 2
```

### Writer Lens (`lenses/team-writer.lens`)

```yaml
lens:
  metadata:
    name: "Technical Writer"
    domain: "documentation"
    version: "1.0.0"
    description: "User clarity, documentation quality, accessibility"

  role:
    focus: "clarity, documentation, user experience, examples"
    temperature: 0.5  # Higher - needs creativity for explanations
    
    questions:
      - "Can a new user understand this?"
      - "Is there a working example?"
      - "What's missing from the docs?"
      - "Is the error message helpful?"
      - "What jargon needs explanation?"
      
    approves_when:
      - "Clear documentation provided"
      - "Working examples included"
      - "Jargon explained or linked"
      - "User-friendly error messages"
      
    rejects_when:
      - "No documentation for new feature"
      - "Examples that don't work"
      - "Unexplained jargon"
      - "Confusing error messages"
      
    leads_during:
      - "documentation"
      - "user_experience"
      - "onboarding"
      - "error_messages"

  heuristics:
    principles:
      - name: "User First"
        rule: "Write for the user, not for yourself"
        always:
          - "Define jargon on first use"
          - "Provide working examples"
          - "Include expected output"
        never:
          - "Assume user knows internals"
          - "Skip 'obvious' steps"
          - "Use unexplained abbreviations"
        priority: 10
        
      - name: "Show Don't Tell"
        rule: "Examples are worth a thousand words"
        always:
          - "Include copy-paste ready code"
          - "Show expected output"
          - "Cover common use cases"
        never:
          - "Describe without demonstrating"
          - "Use pseudo-code when real code works"
          - "Provide partial examples"
        priority: 9
        
      - name: "Progressive Disclosure"
        rule: "Most important information first"
        always:
          - "Lead with the answer"
          - "Common cases before edge cases"
          - "Simple before complex"
        never:
          - "Bury the lead"
          - "Start with edge cases"
          - "Require reading everything for basics"
        priority: 8

  personas:
    - name: "confused_user"
      description: "User who just wants to get something working"
      goals:
        - "Understand what this does"
        - "Get a minimal example working"
        - "Know where to get help"
      attack_vectors:
        - "What does this term mean?"
        - "Can I copy this and have it work?"
        - "What am I supposed to see after this step?"

  validators:
    heuristic:
      - name: "example_check"
        check: "New features should include examples"
        method: "pattern_match"
        patterns:
          - "```"
          - "example"
          - "usage"
        confidence_threshold: 0.6
        severity: "warning"
        
      - name: "jargon_check"
        check: "Technical terms should be explained or linked"
        method: "definition_presence"
        severity: "info"

  quality_policy:
    min_confidence: 0.7
    retry_limit: 2
```

### QA Lens (`lenses/team-qa.lens`)

```yaml
lens:
  metadata:
    name: "QA Engineer"
    domain: "quality"
    version: "1.0.0"
    description: "Testing, edge cases, failure modes, safety"

  role:
    focus: "testing, edge cases, failure modes, safety, regressions"
    temperature: 0.1  # Very conservative - safety critical
    
    questions:
      - "What happens with bad input?"
      - "Is there a test for this?"
      - "What's the failure mode?"
      - "Did we test the edge cases?"
      - "What could break in production?"
      
    approves_when:
      - "Tests cover happy path and edge cases"
      - "Error handling is explicit"
      - "Failure modes are documented"
      - "No obvious regressions"
      
    rejects_when:
      - "No tests for new functionality"
      - "Unhandled error conditions"
      - "Missing edge case coverage"
      - "Could cause production incidents"
      
    leads_during:
      - "testing"
      - "release"
      - "incident_response"
      - "security_review"

  heuristics:
    principles:
      - name: "Defense in Depth"
        rule: "Assume everything can fail"
        test: "What happens when this fails?"
        always:
          - "Handle all error cases explicitly"
          - "Validate inputs at boundaries"
          - "Log failures with context"
        never:
          - "Catch and ignore exceptions"
          - "Assume happy path"
          - "Trust external input"
        priority: 10
        
      - name: "Test Coverage"
        rule: "Untested code is broken code you haven't discovered yet"
        always:
          - "Test happy path"
          - "Test edge cases"
          - "Test error conditions"
        never:
          - "Skip tests for 'simple' code"
          - "Test implementation details"
          - "Leave tests flaky"
        priority: 10
        
      - name: "Failure Mode Analysis"
        rule: "Know how things break before they break"
        always:
          - "Document failure modes"
          - "Have recovery procedures"
          - "Monitor for issues"
        never:
          - "Ship without understanding failure modes"
          - "Ignore intermittent failures"
          - "Assume it won't happen in production"
        priority: 9

  personas:
    - name: "malicious_user"
      description: "Attacker trying to break the system"
      goals:
        - "Find input validation gaps"
        - "Cause unexpected behavior"
        - "Access unauthorized resources"
      attack_vectors:
        - "What if I send 10MB of data?"
        - "What if I send null/undefined?"
        - "What if I send special characters?"
        - "What if I call this 1000 times/second?"

    - name: "murphy"
      description: "Murphy's Law incarnate - if it can go wrong, it will"
      goals:
        - "Find race conditions"
        - "Expose timing issues"
        - "Discover resource exhaustion"
      attack_vectors:
        - "What if the network is slow?"
        - "What if disk is full?"
        - "What if this runs twice concurrently?"

  validators:
    heuristic:
      - name: "test_presence"
        check: "New functionality should have tests"
        method: "file_presence"
        pattern: "tests/test_*.py"
        severity: "error"
        
      - name: "error_handling"
        check: "Error conditions should be handled explicitly"
        method: "pattern_match"
        patterns:
          - "try:"
          - "except"
          - "raise"
        confidence_threshold: 0.7
        severity: "warning"
        
      - name: "edge_case_check"
        check: "Edge cases should be considered"
        method: "keyword_presence"
        keywords:
          - "empty"
          - "null"
          - "None"
          - "boundary"
          - "limit"
          - "max"
          - "min"
        severity: "info"

  quality_policy:
    min_confidence: 0.9  # Highest bar
    required_validators:
      - "test_presence"
      - "error_handling"
    retry_limit: 1  # Strict - don't keep trying bad proposals
```

---

## Implementation

### Team Worker Base Class

```python
# src/sunwell/autonomous/team.py

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Callable

from sunwell.autonomous.brain import RegionWorker, BrainRegion, CorpusCallosum
from sunwell.core.lens import load_lens


class TeamRole(Enum):
    """Software team roles."""
    PM = "pm"
    DEV = "dev"
    WRITER = "writer"
    QA = "qa"


class TeamMessageType(Enum):
    """Extended message types for team collaboration."""
    
    # === Existing (from brain.py) ===
    ANALYZE_REQUEST = "analyze_request"
    VALIDATE_REQUEST = "validate_request"
    ANALYSIS_COMPLETE = "analysis_complete"
    VALIDATION_RESULT = "validation_result"
    SHUTDOWN = "shutdown"
    
    # === Collaboration ===
    ASK_QUESTION = "ask_question"           # Request help from team
    ANSWER_QUESTION = "answer_question"     # Respond to question
    SHARE_BLOCKER = "share_blocker"         # Escalate a problem
    SHARE_INSIGHT = "share_insight"         # Broadcast a learning
    
    # === Review Flow ===
    REQUEST_REVIEW = "request_review"       # Ask team to review proposal
    REVIEW_FEEDBACK = "review_feedback"     # Individual review response
    REVIEW_CONSENSUS = "review_consensus"   # Aggregated team decision
    
    # === Leadership ===
    PHASE_CHANGE = "phase_change"           # Current phase changed
    LEADER_ELECTED = "leader_elected"       # New leader for phase
    ASSIGN_TASK = "assign_task"             # Leader delegates work
    TASK_ACCEPTED = "task_accepted"         # Worker accepts assignment
    
    # === Challenges ===
    CHALLENGE_DECISION = "challenge_decision"  # Disagree with direction
    CHALLENGE_RESPONSE = "challenge_response"  # Response to challenge


@dataclass
class TeamWorker(RegionWorker):
    """Worker that embodies a team role via lens configuration."""
    
    role: TeamRole
    lens_path: Path
    model: Any
    
    # Loaded from lens
    _lens: Any = field(init=False, default=None)
    _role_config: dict = field(init=False, default_factory=dict)
    _system_prompt: str = field(init=False, default="")
    
    def __post_init__(self):
        # Initialize parent
        super().__init__(
            region=BrainRegion.SYNTHESIS,  # Team workers are synthesis-focused
            corpus=self.corpus,
            sunwell_root=self.sunwell_root,
            worker_id=hash(self.role.value) % 1000,
        )
        
        # Load lens configuration
        self._lens = load_lens(self.lens_path)
        self._role_config = self._lens.get("role", {})
        self._system_prompt = self._build_system_prompt()
    
    def _build_system_prompt(self) -> str:
        """Build unique personality from lens role config."""
        rc = self._role_config
        lens_meta = self._lens.get("metadata", {})
        heuristics = self._lens.get("heuristics", {}).get("principles", [])
        
        questions = "\n".join(f"- {q}" for q in rc.get("questions", []))
        approves = "\n".join(f"- {a}" for a in rc.get("approves_when", []))
        rejects = "\n".join(f"- {r}" for r in rc.get("rejects_when", []))
        principles = "\n".join(
            f"- {p['name']}: {p['rule']}" 
            for p in heuristics[:3]  # Top 3 principles
        )
        
        return f"""You are the {lens_meta.get('name', self.role.value)} on this team.

FOCUS: {rc.get('focus', 'general quality')}

When reviewing, always ask:
{questions}

You APPROVE when:
{approves}

You REJECT when:
{rejects}

Core principles:
{principles}

Be direct. Give specific, actionable feedback. No fluff."""

    @property
    def temperature(self) -> float:
        """Get role-specific temperature."""
        return self._role_config.get("temperature", 0.3)
    
    @property
    def leads_during(self) -> list[str]:
        """Get phases this role leads."""
        return self._role_config.get("leads_during", [])
    
    async def review_proposal(self, proposal: dict) -> dict:
        """Review a proposal from this role's perspective."""
        from sunwell.models.protocol import GenerateOptions
        
        prompt = f"""{self._system_prompt}

PROPOSAL TO REVIEW:
Title: {proposal.get('title', 'Untitled')}
Description: {proposal.get('description', '')}
Diff:
```
{proposal.get('diff', '')[:2000]}
```

YOUR REVIEW (be specific):
1. Verdict: [APPROVE / REJECT / NEEDS_WORK]
2. Score (0-10):
3. Key concern from {self.role.value.upper()} perspective:
4. What I need to approve (if not approving):
5. Specific feedback:

Respond as JSON:
{{"verdict": "...", "score": N, "concern": "...", "requirement": "...", "feedback": "..."}}"""

        result = await self.model.generate(
            prompt,
            options=GenerateOptions(temperature=self.temperature, max_tokens=500),
        )
        
        return self._parse_review(result.content or "")
    
    def _parse_review(self, response: str) -> dict:
        """Parse review response."""
        import json
        import re
        
        # Try to extract JSON
        json_match = re.search(r'\{.*\}', response, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        
        # Fallback parsing
        verdict = "NEEDS_WORK"
        if "APPROVE" in response.upper():
            verdict = "APPROVE"
        elif "REJECT" in response.upper():
            verdict = "REJECT"
        
        return {
            "verdict": verdict,
            "score": 5,
            "concern": "Could not parse structured response",
            "feedback": response[:500],
            "role": self.role.value,
        }
    
    async def ask_team(self, question: str) -> None:
        """Ask a question to the team."""
        await self.send_message(
            msg_type=TeamMessageType.ASK_QUESTION,
            target=None,  # Broadcast
            payload={
                "from_role": self.role.value,
                "question": question,
            },
        )
    
    async def share_blocker(self, blocker: str) -> None:
        """Escalate a blocker to the team."""
        await self.send_message(
            msg_type=TeamMessageType.SHARE_BLOCKER,
            target=None,  # Broadcast to all, leader will pick up
            payload={
                "from_role": self.role.value,
                "blocker": blocker,
            },
            priority=8,  # High priority
        )
    
    async def challenge_decision(self, decision: str, reason: str) -> None:
        """Challenge a team decision."""
        await self.send_message(
            msg_type=TeamMessageType.CHALLENGE_DECISION,
            target=None,
            payload={
                "from_role": self.role.value,
                "decision": decision,
                "reason": reason,
            },
            priority=7,
        )
```

### Team Swarm Orchestrator

```python
# src/sunwell/autonomous/swarm.py

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable
import asyncio

from sunwell.autonomous.brain import CorpusCallosum, BrainMessage
from sunwell.autonomous.team import TeamWorker, TeamRole, TeamMessageType


@dataclass
class TeamSwarm:
    """Orchestrates a team of role-based workers.
    
    Creates genuine diversity from a single model by assigning
    different lenses, temperatures, and perspectives to each worker.
    
    Example:
        >>> swarm = TeamSwarm(
        ...     sunwell_root=Path("."),
        ...     model=OllamaModel("qwen2.5:14b"),
        ... )
        >>> result = await swarm.review_proposal(proposal)
    """
    
    sunwell_root: Path
    model: Any  # LLM model
    
    # Team composition
    workers: dict[TeamRole, TeamWorker] = field(init=False)
    corpus: CorpusCallosum = field(init=False)
    
    # State
    current_phase: str = "discovery"
    current_leader: TeamRole = TeamRole.PM
    
    def __post_init__(self):
        self.corpus = CorpusCallosum()
        self.workers = self._create_team()
    
    def _create_team(self) -> dict[TeamRole, TeamWorker]:
        """Create the full team from lenses."""
        lenses_dir = self.sunwell_root / "lenses"
        
        return {
            TeamRole.PM: TeamWorker(
                role=TeamRole.PM,
                lens_path=lenses_dir / "team-pm.lens",
                model=self.model,
                corpus=self.corpus,
                sunwell_root=self.sunwell_root,
            ),
            TeamRole.DEV: TeamWorker(
                role=TeamRole.DEV,
                lens_path=lenses_dir / "team-dev.lens",
                model=self.model,
                corpus=self.corpus,
                sunwell_root=self.sunwell_root,
            ),
            TeamRole.WRITER: TeamWorker(
                role=TeamRole.WRITER,
                lens_path=lenses_dir / "team-writer.lens",
                model=self.model,
                corpus=self.corpus,
                sunwell_root=self.sunwell_root,
            ),
            TeamRole.QA: TeamWorker(
                role=TeamRole.QA,
                lens_path=lenses_dir / "team-qa.lens",
                model=self.model,
                corpus=self.corpus,
                sunwell_root=self.sunwell_root,
            ),
        }
    
    async def review_proposal(self, proposal: dict) -> dict:
        """Get team consensus on a proposal.
        
        All team members review in parallel, then consensus is calculated.
        
        Returns:
            {
                "consensus": "APPROVE" | "REJECT" | "NEEDS_WORK",
                "reviews": [...],
                "blockers": [...],
                "avg_score": float,
                "unanimous": bool,
            }
        """
        # All workers review in parallel
        reviews = await asyncio.gather(*[
            worker.review_proposal(proposal)
            for worker in self.workers.values()
        ])
        
        # Attach role to each review
        for review, role in zip(reviews, self.workers.keys()):
            review["role"] = role.value
        
        # Calculate consensus
        verdicts = [r["verdict"] for r in reviews]
        scores = [r.get("score", 5) for r in reviews]
        
        # Consensus rules:
        # - Any REJECT = NEEDS_WORK (blocker exists)
        # - All APPROVE = APPROVE
        # - Otherwise = NEEDS_WORK
        if "REJECT" in verdicts:
            consensus = "NEEDS_WORK"
        elif all(v == "APPROVE" for v in verdicts):
            consensus = "APPROVE"
        else:
            consensus = "NEEDS_WORK"
        
        blockers = [r for r in reviews if r["verdict"] == "REJECT"]
        
        return {
            "proposal": proposal.get("title", "Untitled"),
            "consensus": consensus,
            "reviews": reviews,
            "blockers": blockers,
            "avg_score": sum(scores) / len(scores),
            "unanimous": len(set(verdicts)) == 1,
            "reviewed_at": datetime.now().isoformat(),
        }
    
    async def set_phase(self, phase: str) -> TeamRole:
        """Change the current phase and elect appropriate leader.
        
        Args:
            phase: Current phase (discovery, design, implementation, etc.)
            
        Returns:
            The role that leads this phase
        """
        self.current_phase = phase
        
        # Find who leads this phase
        for role, worker in self.workers.items():
            if phase in worker.leads_during:
                self.current_leader = role
                break
        
        # Broadcast phase change
        await self.corpus.send(BrainMessage(
            id=f"phase_{phase}",
            type=TeamMessageType.PHASE_CHANGE,
            source=None,
            target=None,
            payload={
                "phase": phase,
                "leader": self.current_leader.value,
            },
        ))
        
        return self.current_leader
    
    async def ask_team(self, question: str, from_role: TeamRole = None) -> list[dict]:
        """Ask all team members a question.
        
        Useful for brainstorming or getting diverse perspectives.
        
        Returns:
            List of responses from each role
        """
        from sunwell.models.protocol import GenerateOptions
        
        async def get_answer(worker: TeamWorker) -> dict:
            prompt = f"""{worker._system_prompt}

QUESTION FROM {'SYSTEM' if from_role is None else from_role.value.upper()}:
{question}

Your perspective as {worker.role.value.upper()}:"""

            result = await worker.model.generate(
                prompt,
                options=GenerateOptions(temperature=worker.temperature),
            )
            
            return {
                "role": worker.role.value,
                "answer": result.content,
            }
        
        return await asyncio.gather(*[
            get_answer(worker) for worker in self.workers.values()
        ])
    
    def get_leader(self) -> TeamWorker:
        """Get the current leader."""
        return self.workers[self.current_leader]
    
    def get_stats(self) -> dict:
        """Get team statistics."""
        return {
            "team_size": len(self.workers),
            "roles": [r.value for r in self.workers.keys()],
            "current_phase": self.current_phase,
            "current_leader": self.current_leader.value,
            "temperatures": {
                r.value: w.temperature for r, w in self.workers.items()
            },
        }
```

### Integration with Brain Mode

```python
# src/sunwell/autonomous/brain_team.py

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable
import asyncio

from sunwell.autonomous.brain import (
    SunwellBrain, 
    BrainRegion, 
    MessageType,
    ValidationWorker,
)
from sunwell.autonomous.swarm import TeamSwarm
from sunwell.autonomous.team import TeamRole


@dataclass
class TeamBrain(SunwellBrain):
    """Brain mode enhanced with team swarm for validation.
    
    Instead of a single LLM judge, proposals are reviewed by
    the full team (PM, Dev, Writer, QA) with diverse perspectives.
    
    Example:
        >>> brain = TeamBrain(
        ...     sunwell_root=Path("."),
        ...     model=OllamaModel("qwen2.5:14b"),
        ... )
        >>> results = await brain.think(goals=["improve error handling"])
    """
    
    model: Any = None  # Shared model for all team members
    team_consensus_threshold: float = 7.0  # Min avg score to approve
    require_unanimous: bool = False  # Require all APPROVE?
    
    # Team swarm
    team: TeamSwarm = field(init=False)
    
    def __post_init__(self):
        super().__post_init__()
        
        if self.model:
            self.team = TeamSwarm(
                sunwell_root=self.sunwell_root,
                model=self.model,
            )
    
    def _create_workers(self, on_output: Callable = None) -> None:
        """Override to use team-based validation."""
        # Create standard analysis/synthesis workers
        super()._create_workers(on_output)
        
        # Replace validation worker with team validator
        if self.model:
            # Remove existing validation worker
            self.workers = [
                w for w in self.workers 
                if not isinstance(w, ValidationWorker)
            ]
            
            # Add team validation worker
            self._team_validator = TeamValidationWorker(
                corpus=self.corpus,
                sunwell_root=self.sunwell_root,
                team=self.team,
                consensus_threshold=self.team_consensus_threshold,
                require_unanimous=self.require_unanimous,
                on_output=on_output,
            )
            self.workers.append(self._team_validator)


@dataclass
class TeamValidationWorker:
    """Validation worker that uses full team review."""
    
    corpus: Any
    sunwell_root: Path
    team: TeamSwarm
    consensus_threshold: float = 7.0
    require_unanimous: bool = False
    on_output: Callable = None
    
    # Stats
    approved_count: int = 0
    rejected_count: int = 0
    review_history: list = field(default_factory=list)
    
    region = BrainRegion.VALIDATION
    stats = {"tasks_completed": 0, "messages_sent": 0}
    _stop_event: Any = field(init=False)
    
    def __post_init__(self):
        import threading
        self._stop_event = threading.Event()
    
    async def process(self) -> None:
        """Process validation requests using team review."""
        while not self._stop_event.is_set():
            msg = await self.corpus.receive(self.region)
            
            if msg and msg.type == MessageType.VALIDATE_REQUEST:
                proposal = msg.payload.get("proposal", {})
                
                # Get team review
                result = await self.team.review_proposal(proposal)
                
                # Determine approval
                is_approved = (
                    result["avg_score"] >= self.consensus_threshold
                    and result["consensus"] != "REJECT"
                    and (not self.require_unanimous or result["unanimous"])
                )
                
                # Log output
                if self.on_output:
                    status = "✅" if is_approved else "❌"
                    self.on_output(
                        f"{status} Team Review: {result['consensus']} "
                        f"(avg: {result['avg_score']:.1f}/10)"
                    )
                    for review in result["reviews"]:
                        self.on_output(
                            f"   {review['role'].upper()}: {review['verdict']} "
                            f"({review.get('score', '?')}/10) - {review.get('concern', '')[:40]}"
                        )
                
                # Send result
                await self._send_result(proposal, is_approved, result)
                
                # Update stats
                if is_approved:
                    self.approved_count += 1
                else:
                    self.rejected_count += 1
                self.review_history.append(result)
                self.stats["tasks_completed"] += 1
            
            elif msg and msg.type == MessageType.SHUTDOWN:
                break
            
            await asyncio.sleep(0.01)
    
    async def _send_result(
        self, 
        proposal: dict, 
        is_approved: bool, 
        team_result: dict,
    ) -> None:
        """Send validation result."""
        from sunwell.autonomous.brain import BrainMessage
        
        msg = BrainMessage(
            id=f"validation_{proposal.get('proposal_id', 'unknown')}",
            type=MessageType.VALIDATION_RESULT,
            source=BrainRegion.VALIDATION,
            target=BrainRegion.EXECUTIVE,
            payload={
                "proposal_id": proposal.get("proposal_id"),
                "valid": is_approved,
                "consensus": team_result["consensus"],
                "avg_score": team_result["avg_score"],
                "unanimous": team_result["unanimous"],
                "reviews": team_result["reviews"],
                "blockers": [
                    {"role": b["role"], "concern": b.get("concern")}
                    for b in team_result["blockers"]
                ],
            },
        )
        await self.corpus.send(msg)
        self.stats["messages_sent"] += 1
    
    def stop(self):
        self._stop_event.set()
    
    def get_team_stats(self) -> dict:
        """Get detailed team review statistics."""
        if not self.review_history:
            return {"reviews": 0}
        
        # Role-specific approval rates
        role_stats = {}
        for role in TeamRole:
            role_reviews = [
                r for result in self.review_history
                for r in result["reviews"]
                if r["role"] == role.value
            ]
            if role_reviews:
                approvals = sum(1 for r in role_reviews if r["verdict"] == "APPROVE")
                role_stats[role.value] = {
                    "reviews": len(role_reviews),
                    "approval_rate": approvals / len(role_reviews),
                    "avg_score": sum(r.get("score", 5) for r in role_reviews) / len(role_reviews),
                }
        
        return {
            "total_reviews": len(self.review_history),
            "approved": self.approved_count,
            "rejected": self.rejected_count,
            "approval_rate": self.approved_count / max(1, len(self.review_history)),
            "avg_team_score": sum(r["avg_score"] for r in self.review_history) / len(self.review_history),
            "unanimous_rate": sum(1 for r in self.review_history if r["unanimous"]) / len(self.review_history),
            "by_role": role_stats,
        }
```

---

## CLI Usage

### Team Review Mode

```bash
# Start brain mode with team review
sunwell brain start \
    --goals "improve error handling" \
    --team-review \
    --model qwen2.5:14b

# Output:
# 🧠 Initializing Team Brain...
#    Analysis workers: 2
#    Synthesis workers: 2
#    Validation: Team Review (PM, Dev, Writer, QA)
#
# [19:45:30] 💭 Thinking...
# [19:46:02] 📋 Team Review: NEEDS_WORK (avg: 6.2/10)
#    PM: APPROVE (7/10) - Clear user value
#    DEV: APPROVE (8/10) - Clean implementation
#    WRITER: NEEDS_WORK (5/10) - Missing example in docs
#    QA: REJECT (4/10) - No tests for edge cases
```

### Interactive Team Session

```bash
# Ask the team a question
sunwell team ask "Should we add caching to the API?"

# Output:
# 🎤 Asking the team...
#
# PM: "Yes - users have requested faster responses. This aligns with 
#      our Q1 goal of improving latency. MVP would be simple TTL cache."
#
# DEV: "Caching adds complexity. We need to define invalidation strategy
#       clearly. Suggest Redis over in-memory for horizontal scaling."
#
# WRITER: "Users will need to understand cache behavior. Document:
#          1) What gets cached, 2) How to force refresh, 3) Cache headers"
#
# QA: "Concerns: 1) Cache stampede on cold start, 2) Stale data bugs,
#      3) Need tests for cache hit/miss paths. Suggest feature flag."
```

---

## Example Output

### Team Review Flow

```
╔══════════════════════════════════════════════════════════════════════════════╗
║                        🎭 TEAM REVIEW                                         ║
╠══════════════════════════════════════════════════════════════════════════════╣
║  Proposal: Add SSL error pattern recognition                                 ║
║  Phase: implementation (Leader: DEV)                                         ║
╚══════════════════════════════════════════════════════════════════════════════╝

📋 PM Review:
   Verdict: APPROVE (8/10)
   "Clear user value - SSL errors are common pain point. Scoped appropriately."

🔧 DEV Review:
   Verdict: APPROVE (9/10)
   "Clean pattern, follows existing structure. Good regex, handles edge cases."

📝 WRITER Review:
   Verdict: NEEDS_WORK (6/10)
   "Need to document: 1) What SSL errors are matched, 2) Example error messages"

🔍 QA Review:
   Verdict: APPROVE (7/10)
   "Has tests for happy path. Would like edge case: malformed SSL error string."

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

CONSENSUS: NEEDS_WORK
Average Score: 7.5/10
Unanimous: No

BLOCKERS:
  • WRITER: Documentation incomplete

NEXT STEPS:
  1. Add documentation for SSL error patterns
  2. Re-submit for review
```

---

## Success Criteria

### Phase 1: Team Lenses
- [ ] Create `team-pm.lens`
- [ ] Create `team-dev.lens`
- [ ] Create `team-writer.lens`
- [ ] Create `team-qa.lens`
- [ ] Validate lens schema compatibility

### Phase 2: Team Worker
- [ ] `TeamWorker` base class
- [ ] Role-specific system prompts
- [ ] Temperature differentiation
- [ ] Review parsing

### Phase 3: Team Swarm
- [ ] `TeamSwarm` orchestrator
- [ ] Parallel review execution
- [ ] Consensus calculation
- [ ] Phase-based leadership

### Phase 4: Brain Integration
- [ ] `TeamBrain` class
- [ ] `TeamValidationWorker`
- [ ] Replace single LLM judge with team
- [ ] Team statistics tracking

### Phase 5: CLI
- [ ] `--team-review` flag for brain mode
- [ ] `sunwell team ask` command
- [ ] Team review output formatting

---

## Future Directions

### Dynamic Team Composition

```yaml
# Custom team configurations
teams:
  security_focused:
    - qa  # 2x weight
    - qa
    - dev
    - pm
    
  documentation_sprint:
    - writer  # 2x weight
    - writer
    - dev
    - pm
```

### Emergent Leadership Election

```python
# After exploration phase, elect leader based on proposal quality
async def elect_leader(team: TeamSwarm) -> TeamRole:
    """Elect leader based on whose proposals got highest team scores."""
    scores = calculate_leadership_fitness(team.review_history)
    return max(scores, key=scores.get)
```

### Cross-Team Learning

Track which role catches which types of issues, and use that to improve individual lenses over time.

---

## Appendix: Quick Reference

```bash
# Brain mode with team review
sunwell brain start --goals "X" --team-review --model MODEL

# Ask the team
sunwell team ask "Question?"

# Review with specific roles only
sunwell brain start --team-roles pm,qa --model MODEL

# Set consensus threshold
sunwell brain start --team-review --consensus-threshold 8.0
```

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-15 | Initial draft |

"""Learning extraction for intra-session and cross-session memory (RFC-042).

The adaptive agent extracts learnings from:
1. Generated code (patterns, types, conventions)
2. Fix attempts (what worked, what didn't)
3. Gate validations (successful approaches)

Learnings are stored in Simulacrum for:
- Intra-session: Propagate patterns to subsequent tasks
- Cross-session: Remember across days/weeks/months

Learning categories:
- type: Type definitions, field names, relationships
- api: Endpoints, routes, methods
- pattern: Code patterns, conventions
- fix: What fixed certain errors
- dead_end: Approaches that didn't work
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from sunwell.models.protocol import ModelProtocol


@dataclass(frozen=True, slots=True)
class Learning:
    """A fact learned from generated code or fix attempts."""

    fact: str
    """The learned fact (e.g., "User.id is Integer primary key")."""

    category: str
    """Category: type, api, pattern, fix."""

    confidence: float = 0.8
    """Confidence in this learning (0-1)."""

    source_file: str | None = None
    """File this was learned from."""

    source_line: int | None = None
    """Line number if applicable."""

    @property
    def id(self) -> str:
        """Unique ID for this learning."""
        import hashlib

        content = f"{self.category}:{self.fact}"
        return hashlib.md5(content.encode()).hexdigest()[:12]


@dataclass(frozen=True, slots=True)
class DeadEnd:
    """An approach that didn't work."""

    approach: str
    """What was tried."""

    reason: str
    """Why it failed."""

    context: str = ""
    """Additional context."""

    gate: str | None = None
    """Gate where this failed."""


@dataclass
class LearningExtractor:
    """Extracts learnings from generated code and fix attempts.

    Uses both pattern-based extraction (fast, no LLM) and
    optional LLM extraction (deeper insights, more expensive).
    """

    use_llm: bool = False
    """Whether to use LLM for deeper extraction."""

    model: ModelProtocol | None = None
    """Model for LLM extraction."""

    def extract_from_code(
        self,
        content: str,
        file_path: str | None = None,
    ) -> list[Learning]:
        """Extract learnings from generated code.

        Uses pattern matching for:
        - Type/class definitions
        - Foreign key relationships
        - API endpoints
        - Configuration patterns

        Args:
            content: Code content
            file_path: Path to the file

        Returns:
            List of extracted learnings
        """
        learnings: list[Learning] = []

        # Extract class definitions
        for match in re.finditer(
            r"class\s+(\w+)(?:\(([^)]+)\))?:",
            content,
        ):
            class_name = match.group(1)
            bases = match.group(2) or ""

            # Find fields in dataclass or model
            class_end = content.find("\nclass ", match.end())
            if class_end == -1:
                class_end = len(content)
            class_body = content[match.end() : class_end]

            # Extract fields
            fields = self._extract_fields(class_body)
            if fields:
                fact = f"{class_name} has fields: {', '.join(fields)}"
                learnings.append(
                    Learning(
                        fact=fact,
                        category="type",
                        confidence=0.9,
                        source_file=file_path,
                    )
                )

            # Check for inheritance
            if bases:
                learnings.append(
                    Learning(
                        fact=f"{class_name} extends {bases}",
                        category="type",
                        confidence=0.9,
                        source_file=file_path,
                    )
                )

        # Extract foreign keys
        for match in re.finditer(
            r"(\w+)\s*=\s*(?:Column\()?ForeignKey\(['\"]([^'\"]+)['\"]",
            content,
        ):
            field_name = match.group(1)
            target = match.group(2)
            learnings.append(
                Learning(
                    fact=f"{field_name} is ForeignKey to {target}",
                    category="type",
                    confidence=0.9,
                    source_file=file_path,
                )
            )

        # Extract API routes
        for match in re.finditer(
            r"@(?:app|router|bp)\.(?:route|get|post|put|delete)\(['\"]([^'\"]+)['\"]",
            content,
        ):
            route = match.group(1)
            # Find function name
            func_match = re.search(
                r"def\s+(\w+)",
                content[match.end() : match.end() + 100],
            )
            func_name = func_match.group(1) if func_match else "unknown"
            learnings.append(
                Learning(
                    fact=f"Endpoint {route} handled by {func_name}",
                    category="api",
                    confidence=0.85,
                    source_file=file_path,
                )
            )

        # Extract imports pattern
        imports = re.findall(r"^from\s+(\S+)\s+import", content, re.MULTILINE)
        if imports:
            # Get unique import sources
            sources = list(set(imports))[:5]  # Limit to 5
            if sources:
                learnings.append(
                    Learning(
                        fact=f"Uses imports from: {', '.join(sources)}",
                        category="pattern",
                        confidence=0.7,
                        source_file=file_path,
                    )
                )

        return learnings

    def _extract_fields(self, class_body: str) -> list[str]:
        """Extract field names from class body."""
        fields: list[str] = []

        # Dataclass fields: field_name: Type
        for match in re.finditer(r"^\s+(\w+):\s*(\S+)", class_body, re.MULTILINE):
            if not match.group(1).startswith("_"):
                fields.append(match.group(1))

        # SQLAlchemy columns: field_name = Column(...)
        for match in re.finditer(r"^\s+(\w+)\s*=\s*Column\(", class_body, re.MULTILINE):
            fields.append(match.group(1))

        return fields[:10]  # Limit to 10 fields

    def extract_from_fix(
        self,
        error_type: str,
        error_message: str,
        fix_description: str,
        success: bool,
    ) -> Learning | DeadEnd:
        """Extract learning from a fix attempt.

        Args:
            error_type: Type of error (syntax, type, runtime)
            error_message: The error message
            fix_description: What was done to fix
            success: Whether the fix worked

        Returns:
            Learning if successful, DeadEnd if not
        """
        if success:
            return Learning(
                fact=f"Fixed '{error_type}' by: {fix_description}",
                category="fix",
                confidence=0.85,
            )
        else:
            return DeadEnd(
                approach=fix_description,
                reason=error_message,
                context=f"Error type: {error_type}",
            )

    async def extract_with_llm(
        self,
        content: str,
        file_path: str | None = None,
    ) -> list[Learning]:
        """Extract deeper learnings using LLM.

        More expensive but catches patterns that regex misses.

        Args:
            content: Code content
            file_path: Path to the file

        Returns:
            List of extracted learnings
        """
        if not self.model:
            return []

        from sunwell.models.protocol import GenerateOptions

        prompt = f"""Extract key facts from this code that would help generating similar code.

CODE:
```python
{content[:2000]}  # Truncate for token budget
```

Output ONLY facts in this format (one per line):
TYPE: [fact about types, fields, relationships]
API: [fact about endpoints, routes]
PATTERN: [fact about code patterns, conventions]

Examples:
TYPE: User.id is Integer primary key
TYPE: Post has user_id ForeignKey to users.id
API: POST /users creates new user
PATTERN: Using Flask-SQLAlchemy with create_app pattern"""

        try:
            result = await self.model.generate(
                prompt,
                options=GenerateOptions(temperature=0.2, max_tokens=500),
            )

            learnings = []
            for line in result.text.split("\n"):
                line = line.strip()
                if ":" in line:
                    category, fact = line.split(":", 1)
                    category = category.strip().lower()
                    fact = fact.strip()
                    if category in ("type", "api", "pattern") and fact:
                        learnings.append(
                            Learning(
                                fact=fact,
                                category=category,
                                confidence=0.75,
                                source_file=file_path,
                            )
                        )

            return learnings

        except Exception:
            return []


# =============================================================================
# Learning Store Integration
# =============================================================================


@dataclass
class LearningStore:
    """In-memory store for learnings during a session.

    Integrates with Simulacrum for persistence.
    """

    learnings: list[Learning] = field(default_factory=list)
    """All learnings in this session."""

    dead_ends: list[DeadEnd] = field(default_factory=list)
    """Dead ends encountered."""

    def add_learning(self, learning: Learning) -> None:
        """Add a learning, deduplicating by ID."""
        existing_ids = {lrn.id for lrn in self.learnings}
        if learning.id not in existing_ids:
            self.learnings.append(learning)

    def add_dead_end(self, dead_end: DeadEnd) -> None:
        """Add a dead end."""
        self.dead_ends.append(dead_end)

    def get_relevant(self, query: str, limit: int = 10) -> list[Learning]:
        """Get learnings relevant to a query.

        Simple keyword matching for now.
        Could use embeddings for better retrieval.

        Args:
            query: Search query
            limit: Max results

        Returns:
            Relevant learnings
        """
        query_lower = query.lower()
        query_words = set(query_lower.split())

        scored: list[tuple[float, Learning]] = []
        for learning in self.learnings:
            fact_lower = learning.fact.lower()
            fact_words = set(fact_lower.split())

            # Score by word overlap
            overlap = len(query_words & fact_words)
            if overlap > 0:
                score = overlap / len(query_words)
                scored.append((score, learning))

        # Sort by score descending
        scored.sort(key=lambda x: x[0], reverse=True)
        return [lrn for _, lrn in scored[:limit]]

    def get_dead_ends_for(self, query: str) -> list[DeadEnd]:
        """Get dead ends relevant to a query."""
        query_lower = query.lower()
        return [
            de
            for de in self.dead_ends
            if any(word in de.approach.lower() for word in query_lower.split())
        ]

    def format_for_prompt(self, limit: int = 10) -> str:
        """Format learnings for injection into prompts.

        Args:
            limit: Max learnings to include

        Returns:
            Formatted string for prompt injection
        """
        if not self.learnings:
            return ""

        recent = self.learnings[-limit:]
        lines = ["Known facts from this session:"]
        for lrn in recent:
            lines.append(f"- {lrn.fact}")

        if self.dead_ends:
            lines.append("\nApproaches that didn't work:")
            for de in self.dead_ends[-5:]:
                lines.append(f"- {de.approach}: {de.reason}")

        return "\n".join(lines)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dict for serialization."""
        return {
            "learnings": [
                {"fact": lrn.fact, "category": lrn.category, "confidence": lrn.confidence}
                for lrn in self.learnings
            ],
            "dead_ends": [
                {"approach": d.approach, "reason": d.reason, "context": d.context}
                for d in self.dead_ends
            ],
        }

    def sync_to_simulacrum(self, store: Any) -> int:
        """Sync learnings to Simulacrum store for persistence.

        Args:
            store: SimulacrumStore instance

        Returns:
            Number of learnings synced
        """
        try:
            from sunwell.simulacrum.core import Learning as SimLearning

            synced = 0
            for lrn in self.learnings:
                sim_learning = SimLearning(
                    fact=lrn.fact,
                    category=lrn.category,
                    confidence=lrn.confidence,
                    source_file=lrn.source_file,
                    source_line=lrn.source_line,
                )
                store.add_learning(sim_learning)
                synced += 1

            return synced
        except (ImportError, AttributeError):
            return 0

    def load_from_simulacrum(self, store: Any) -> int:
        """Load learnings from Simulacrum store.

        Args:
            store: SimulacrumStore instance

        Returns:
            Number of learnings loaded
        """
        try:
            loaded = 0
            for sim_learning in store.get_learnings():
                lrn = Learning(
                    fact=sim_learning.fact,
                    category=getattr(sim_learning, "category", "pattern"),
                    confidence=getattr(sim_learning, "confidence", 0.7),
                    source_file=getattr(sim_learning, "source_file", None),
                    source_line=getattr(sim_learning, "source_line", None),
                )
                self.add_learning(lrn)
                loaded += 1

            return loaded
        except (ImportError, AttributeError):
            return 0

    def save_to_disk(self, base_path: Path | None = None) -> int:
        """Persist learnings to .sunwell/intelligence/learnings.jsonl.

        This enables cross-session learning without requiring a full Simulacrum setup.
        Learnings are appended to the file, deduplicating by learning ID.

        Args:
            base_path: Project root (defaults to cwd)

        Returns:
            Number of learnings saved
        """
        import json
        from datetime import datetime
        from pathlib import Path

        if not self.learnings and not self.dead_ends:
            return 0

        base = base_path or Path.cwd()
        intel_dir = base / ".sunwell" / "intelligence"
        intel_dir.mkdir(parents=True, exist_ok=True)

        learnings_path = intel_dir / "learnings.jsonl"
        dead_ends_path = intel_dir / "dead_ends.jsonl"

        # Load existing IDs to avoid duplicates
        existing_ids: set[str] = set()
        if learnings_path.exists():
            with open(learnings_path) as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            existing_ids.add(data.get("id", ""))
                        except json.JSONDecodeError:
                            pass

        # Append new learnings
        saved = 0
        timestamp = datetime.now().isoformat()

        with open(learnings_path, "a") as f:
            for lrn in self.learnings:
                if lrn.id not in existing_ids:
                    record = {
                        "id": lrn.id,
                        "fact": lrn.fact,
                        "category": lrn.category,
                        "confidence": lrn.confidence,
                        "source_file": lrn.source_file,
                        "source_line": lrn.source_line,
                        "created_at": timestamp,
                    }
                    f.write(json.dumps(record) + "\n")
                    saved += 1

        # Also save dead ends
        existing_approaches: set[str] = set()
        if dead_ends_path.exists():
            with open(dead_ends_path) as f:
                for line in f:
                    if line.strip():
                        try:
                            data = json.loads(line)
                            existing_approaches.add(data.get("approach", ""))
                        except json.JSONDecodeError:
                            pass

        with open(dead_ends_path, "a") as f:
            for de in self.dead_ends:
                if de.approach not in existing_approaches:
                    record = {
                        "approach": de.approach,
                        "reason": de.reason,
                        "context": de.context,
                        "created_at": timestamp,
                    }
                    f.write(json.dumps(record) + "\n")

        return saved

    def load_from_disk(self, base_path: Path | None = None) -> int:
        """Load learnings from .sunwell/ directories.

        Reads from multiple sources:
        1. .sunwell/intelligence/learnings.jsonl (JSONL format)
        2. .sunwell/learnings/*.json (Naaru execution format - JSON arrays)
        3. .sunwell/intelligence/dead_ends.jsonl

        Args:
            base_path: Project root (defaults to cwd)

        Returns:
            Number of learnings loaded
        """
        import json
        from pathlib import Path

        base = base_path or Path.cwd()
        learnings_path = base / ".sunwell" / "intelligence" / "learnings.jsonl"
        dead_ends_path = base / ".sunwell" / "intelligence" / "dead_ends.jsonl"
        naaru_learnings_dir = base / ".sunwell" / "learnings"

        loaded = 0

        # Source 1: .sunwell/intelligence/learnings.jsonl (JSONL format)
        if learnings_path.exists():
            with open(learnings_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        lrn = Learning(
                            fact=data["fact"],
                            category=data.get("category", "pattern"),
                            confidence=data.get("confidence", 0.7),
                            source_file=data.get("source_file"),
                            source_line=data.get("source_line"),
                        )
                        self.add_learning(lrn)
                        loaded += 1
                    except (json.JSONDecodeError, KeyError):
                        pass

        # Source 2: .sunwell/learnings/*.json (Naaru execution format)
        # Format: [{"type": "task_completion", "task_id": ..., "task_description": ..., ...}]
        if naaru_learnings_dir.exists():
            for json_file in naaru_learnings_dir.glob("*.json"):
                try:
                    with open(json_file) as f:
                        data = json.load(f)
                    if isinstance(data, list):
                        for entry in data:
                            task_id = entry.get("task_id", "")
                            description = entry.get("task_description", "")
                            output = entry.get("output", "")

                            # Create learning from task completion
                            if task_id and description:
                                lrn = Learning(
                                    fact=f"Completed: {description}",
                                    category="task_completion",
                                    confidence=1.0,
                                    source_file=task_id,
                                )
                                self.add_learning(lrn)
                                loaded += 1

                            # Extract useful patterns from output if available
                            if output and len(output) > 20:
                                # Extract class/function definitions
                                for match in re.finditer(
                                    r"(?:class|def)\s+(\w+)", output
                                ):
                                    lrn = Learning(
                                        fact=f"Defined {match.group(1)} in {task_id}",
                                        category="pattern",
                                        confidence=0.9,
                                        source_file=task_id,
                                    )
                                    self.add_learning(lrn)
                                    loaded += 1
                except (json.JSONDecodeError, OSError):
                    pass

        # Source 3: Dead ends
        if dead_ends_path.exists():
            with open(dead_ends_path) as f:
                for line in f:
                    if not line.strip():
                        continue
                    try:
                        data = json.loads(line)
                        de = DeadEnd(
                            approach=data["approach"],
                            reason=data.get("reason", ""),
                            context=data.get("context"),
                        )
                        self.add_dead_end(de)
                    except (json.JSONDecodeError, KeyError):
                        pass

        return loaded

"""Discernment - The Naaru's quick insight before full Wisdom.

The Naaru uses Discernment (tiered validation) to efficiently evaluate proposals:

1. Quick structural checks (no LLM) - instant insight
2. Fast model (e.g., llama3.2:3b) - rapid discernment via FastClassifier (RFC-077)
3. Full Wisdom model - deep judgment (only for uncertain cases)

This dramatically reduces validation cost while maintaining quality.

RFC-077: Now uses FastClassifier JSON prompts instead of tool-calling for
the fast model, enabling use of smaller models (1-3B) that don't support tools.

Architecture:
    ```
    Proposal
        │
        ▼
    ┌─────────────────────────────┐
    │      QUICK INSIGHT          │  Structural checks (no LLM)
    │  • Syntax valid?            │
    │  • Has imports?             │
    │  • Has docstrings?          │
    └─────────────┬───────────────┘
                  │
                  ▼
    ┌─────────────────────────────┐
    │       DISCERNMENT           │  FastClassifier (90% of cases)
    │   (llama3.2:3b, ~1s)        │  RFC-077: JSON prompts, no tools
    └─────────────┬───────────────┘
                  │
          ┌───────┴───────┐
          │               │
          ▼               ▼
    [APPROVE]       [UNCERTAIN]
    (fast exit)          │
                         ▼
                  ┌──────────────┐
                  │    WISDOM    │  Full judge (10% of cases)
                  │  Deep judge  │
                  └──────────────┘
    ```

Usage:
    >>> from sunwell.naaru.discernment import Discernment
    >>> discerner = Discernment()
    >>> result = await discerner.evaluate(proposal)
    >>> if result.confident:
    >>>     print(f"Decision: {result.verdict}")
    >>> else:
    >>>     print("Escalating to Wisdom...")
"""


import ast
from dataclasses import dataclass, field
from enum import Enum

from sunwell.models.ollama import OllamaModel
from sunwell.models.protocol import GenerateOptions, Tool
from sunwell.reasoning import ClassificationTemplate, FastClassifier


# =============================================================================
# Module-Level Constants (avoid rebuilding each call)
# =============================================================================

_PYTHON_BUILTINS: frozenset[str] = frozenset({
    'print', 'len', 'range', 'str', 'int', 'float', 'list', 'dict',
    'set', 'tuple', 'True', 'False', 'None', 'open', 'type', 'isinstance',
    'hasattr', 'getattr', 'setattr', 'super', 'self', 'cls',
})

_COMMON_MODULES: dict[str, str] = {
    'json': 'json',
    'os': 'os',
    'sys': 'sys',
    'Path': 'pathlib',
    'datetime': 'datetime',
    'asyncio': 'asyncio',
    're': 're',
}


class DiscernmentVerdict(Enum):
    """Possible discernment verdicts."""
    APPROVE = "approve"
    REJECT = "reject"
    NEEDS_REFINEMENT = "needs_refinement"
    UNCERTAIN = "uncertain"  # Escalate to full Wisdom


@dataclass(frozen=True, slots=True)
class DiscernmentResult:
    """Result from Discernment evaluation."""

    verdict: DiscernmentVerdict
    confident: bool  # If True, don't need to escalate to Wisdom
    luminance: float  # 0-10 confidence/quality score
    issues: tuple[str, ...] = ()
    strengths: tuple[str, ...] = ()
    reason: str = ""
    checks_passed: tuple[tuple[str, bool], ...] = ()


# =============================================================================
# Structural Checks (No LLM needed)
# =============================================================================


def check_syntax(code: str) -> tuple[bool, str]:
    """Check if Python code has valid syntax."""
    try:
        ast.parse(code)
        return True, "Valid Python syntax"
    except SyntaxError as e:
        return False, f"Syntax error at line {e.lineno}: {e.msg}"


def check_imports(code: str) -> tuple[bool, str]:
    """Check if code has necessary imports.
    
    Uses a single AST walk to collect both imports and names used.
    """
    tree = ast.parse(code)

    imports: set[str] = set()
    names_used: set[str] = set()
    
    # Single walk to collect both imports and names
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name.split('.')[0])
        elif isinstance(node, ast.ImportFrom) and node.module:
            imports.add(node.module.split('.')[0])
        elif isinstance(node, ast.Name):
            names_used.add(node.id)

    # Check for common unimported modules using module-level constants
    missing = []
    for name, module in _COMMON_MODULES.items():
        if name in names_used and module not in imports and name not in imports:
            if name not in _PYTHON_BUILTINS:
                missing.append(f"{module} (for {name})")

    if missing:
        return False, f"Missing imports: {', '.join(missing)}"

    return True, "Imports look complete"


def check_docstrings(code: str) -> tuple[bool, str]:
    """Check if functions/classes have docstrings."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return False, "Cannot check docstrings - syntax error"

    missing_docs = []

    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Skip private/dunder methods
            if node.name.startswith('_') and not node.name.startswith('__'):
                continue
            # Check for docstring
            if not (node.body and isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant)):
                missing_docs.append(f"function '{node.name}'")
        elif isinstance(node, ast.ClassDef):
            if not (node.body and isinstance(node.body[0], ast.Expr) and
                    isinstance(node.body[0].value, ast.Constant)):
                missing_docs.append(f"class '{node.name}'")

    if missing_docs and len(missing_docs) <= 3:
        return False, f"Missing docstrings for: {', '.join(missing_docs)}"
    elif len(missing_docs) > 3:
        return False, f"Missing docstrings for {len(missing_docs)} items"

    return True, "Docstrings present"


def check_error_handling(code: str) -> tuple[bool, str]:
    """Check for basic error handling patterns."""
    try:
        tree = ast.parse(code)
    except SyntaxError:
        return True, "Cannot check - syntax error"

    dangerous_patterns = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Try):
            pass
        if isinstance(node, ast.Raise):
            pass
        # Check for bare except
        if isinstance(node, ast.ExceptHandler) and node.type is None:
            dangerous_patterns.append("bare except clause")
        # Check for dangerous patterns
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == 'eval':
                dangerous_patterns.append("use of eval()")
            if node.func.id == 'exec':
                dangerous_patterns.append("use of exec()")

    if dangerous_patterns:
        return False, f"Dangerous patterns: {', '.join(dangerous_patterns)}"

    return True, "Error handling looks reasonable"


def run_structural_checks(code: str) -> dict[str, tuple[bool, str]]:
    """Run all structural checks on code."""
    # Check syntax first - if it fails, skip other checks
    syntax_result = check_syntax(code)

    if not syntax_result[0]:
        # Syntax error - other checks would fail anyway
        return {
            "syntax": syntax_result,
            "imports": (False, "Cannot check - syntax error"),
            "docstrings": (False, "Cannot check - syntax error"),
            "error_handling": (False, "Cannot check - syntax error"),
        }

    return {
        "syntax": syntax_result,
        "imports": check_imports(code),
        "docstrings": check_docstrings(code),
        "error_handling": check_error_handling(code),
    }


# =============================================================================
# Discernment - The Naaru's Quick Insight
# =============================================================================


# RFC-077: FastClassifier template for code review
CODE_REVIEW_TEMPLATE = ClassificationTemplate(
    name="code_review",
    prompt_template='''Review this code change. Respond with ONLY JSON.

Category: {category}
Purpose: {description}

```python
{code}
```

Decide: approve, reject, or refine.

{{"verdict": "approve"|"reject"|"refine", "score": 0-10, "issues": [], "strengths": []}}

JSON:''',
    output_key="verdict",
    options=("approve", "reject", "refine"),
    default="refine",
)


@dataclass(slots=True)
class Discernment:
    """The Naaru's quick insight before full Wisdom judgment.

    Uses a tiered approach:
    1. Quick Insight (no LLM) - structural checks catch obvious issues
    2. Discernment (fast model) - rapid approve/reject decisions
    3. Escalate to Wisdom only for uncertain cases

    RFC-077: Now uses FastClassifier with JSON prompts instead of tool-calling,
    enabling smaller models (1-3B) that don't support tools.
    """

    # Fast model for quick decisions (RFC-077: prefer llama3.2:3b)
    insight_model: str = "llama3.2:3b"

    # Purity thresholds for escalation
    auto_approve_purity: float = 8.0  # Auto-approve if luminance >= this
    auto_reject_purity: float = 4.0   # Auto-reject if luminance <= this

    # Ollama base URL
    base_url: str = "http://localhost:11434/v1"

    # Require structural checks to pass for approval
    require_structural_pass: bool = True

    # Use FastClassifier (RFC-077) instead of tool-calling
    use_fast_classifier: bool = True

    # Internal state
    _insight: OllamaModel | None = field(default=None, init=False)
    _classifier: FastClassifier | None = field(default=None, init=False)

    @property
    def insight(self) -> OllamaModel:
        """Get the insight model for quick decisions."""
        if self._insight is None:
            self._insight = OllamaModel(model=self.insight_model, base_url=self.base_url)
        return self._insight

    @property
    def classifier(self) -> FastClassifier:
        """Get the FastClassifier for JSON-based decisions (RFC-077)."""
        if self._classifier is None:
            self._classifier = FastClassifier(model=self.insight)
        return self._classifier

    def _extract_code(self, proposal: dict) -> str:
        """Extract code from proposal."""
        # Try different fields where code might be
        code = proposal.get("diff", "")
        if not code:
            code = proposal.get("code", "")
        if not code:
            code = proposal.get("content", "")

        # Clean up diff format if present
        if code.startswith("```"):
            # Remove markdown code blocks
            lines = code.split("\n")
            code_lines = []
            in_block = False
            for line in lines:
                if line.startswith("```"):
                    in_block = not in_block
                    continue
                if in_block:
                    code_lines.append(line)
            code = "\n".join(code_lines)

        return code.strip()

    async def evaluate(self, proposal: dict) -> DiscernmentResult:
        """Evaluate a proposal using quick insight + fast model.

        Returns:
            DiscernmentResult with verdict and luminance (confidence level)
        """
        code = self._extract_code(proposal)
        category = proposal.get("summary", {}).get("category", "code_quality")
        description = proposal.get("summary", {}).get("rationale", "")

        # Step 1: Quick Insight - structural checks (fast, no LLM)
        structural_results = run_structural_checks(code)
        checks_passed_dict = {k: v[0] for k, v in structural_results.items()}

        # Count passed/failed
        passed = sum(1 for v in checks_passed_dict.values() if v)
        total = len(checks_passed_dict)
        
        # Convert to frozen tuple for DiscernmentResult
        checks_passed = tuple(checks_passed_dict.items())

        # Collect issues from failed checks
        issues = tuple(v[1] for k, v in structural_results.items() if not v[0])

        # If syntax fails, reject immediately
        if not checks_passed_dict.get("syntax", True):
            return DiscernmentResult(
                verdict=DiscernmentVerdict.REJECT,
                confident=True,
                luminance=0.0,
                issues=issues,
                reason="Syntax error - code won't run",
                checks_passed=checks_passed,
            )

        # Step 2: Discernment - fast model decision
        try:
            insight_result = await self._quick_insight(code, category, description)

            # Combine structural and insight results
            combined_luminance = insight_result.luminance
            if self.require_structural_pass:
                # Penalize for failed structural checks
                penalty = (total - passed) * 1.0
                combined_luminance = max(0, insight_result.luminance - penalty)

            # Merge issues
            all_issues = issues + tuple(insight_result.issues)

            # Determine verdict based on purity thresholds
            if combined_luminance >= self.auto_approve_purity and passed == total:
                return DiscernmentResult(
                    verdict=DiscernmentVerdict.APPROVE,
                    confident=True,
                    luminance=combined_luminance,
                    issues=all_issues,
                    strengths=tuple(insight_result.strengths),
                    reason=f"Luminance {combined_luminance:.1f}/10 - approved",
                    checks_passed=checks_passed,
                )

            elif combined_luminance <= self.auto_reject_purity:
                return DiscernmentResult(
                    verdict=DiscernmentVerdict.REJECT,
                    confident=True,
                    luminance=combined_luminance,
                    issues=all_issues,
                    reason=f"Luminance {combined_luminance:.1f}/10 - rejected",
                    checks_passed=checks_passed,
                )

            elif all_issues and combined_luminance < 7.0:
                return DiscernmentResult(
                    verdict=DiscernmentVerdict.NEEDS_REFINEMENT,
                    confident=True,
                    luminance=combined_luminance,
                    issues=all_issues,
                    reason=f"Luminance {combined_luminance:.1f}/10 - needs refinement",
                    checks_passed=checks_passed,
                )

            else:
                # Uncertain - escalate to full Wisdom
                return DiscernmentResult(
                    verdict=DiscernmentVerdict.UNCERTAIN,
                    confident=False,
                    luminance=combined_luminance,
                    issues=all_issues,
                    reason="Borderline case - needs Wisdom review",
                    checks_passed=checks_passed,
                )

        except Exception as e:
            # If insight fails, fall back to structural-only
            base_luminance = (passed / total) * 7.0 if total > 0 else 5.0

            return DiscernmentResult(
                verdict=DiscernmentVerdict.UNCERTAIN,
                confident=False,
                luminance=base_luminance,
                issues=issues + (f"Insight failed: {e}",),
                reason="Insight error - escalating to Wisdom",
                checks_passed=checks_passed,
            )

    async def _quick_insight(
        self,
        code: str,
        category: str,
        description: str,
    ) -> DiscernmentResult:
        """Use fast model for quick insight decision.

        RFC-077: Now supports two modes:
        1. FastClassifier (JSON prompts) - faster, works with smaller models
        2. Tool-calling (legacy) - for models that support it
        """
        if self.use_fast_classifier:
            return await self._quick_insight_fast(code, category, description)
        return await self._quick_insight_tools(code, category, description)

    async def _quick_insight_fast(
        self,
        code: str,
        category: str,
        description: str,
    ) -> DiscernmentResult:
        """Quick insight using FastClassifier (RFC-077).

        ~1s with llama3.2:3b vs ~5s+ with tool-calling.
        """
        result = await self.classifier.classify_with_template(
            CODE_REVIEW_TEMPLATE,
            {
                "code": code[:2000],  # Truncate for context window
                "category": category,
                "description": description,
            },
        )

        # Map verdict to DiscernmentVerdict
        verdict_map = {
            "approve": DiscernmentVerdict.APPROVE,
            "reject": DiscernmentVerdict.REJECT,
            "refine": DiscernmentVerdict.NEEDS_REFINEMENT,
        }
        verdict = verdict_map.get(result.value, DiscernmentVerdict.UNCERTAIN)

        # Extract score from raw response if available
        luminance = 5.0
        issues: tuple[str, ...] = ()
        strengths: tuple[str, ...] = ()

        if result.raw_response:
            luminance = float(result.raw_response.get("score", 5.0))
            raw_issues = result.raw_response.get("issues", [])
            raw_strengths = result.raw_response.get("strengths", [])
            issues = tuple(raw_issues) if isinstance(raw_issues, list) else ()
            strengths = tuple(raw_strengths) if isinstance(raw_strengths, list) else ()

        return DiscernmentResult(
            verdict=verdict,
            confident=result.confidence > 0.6,
            luminance=luminance,
            issues=issues,
            strengths=strengths,
            reason=f"FastClassifier: {result.value} ({result.confidence:.0%})",
        )

    async def _quick_insight_tools(
        self,
        code: str,
        category: str,
        description: str,
    ) -> DiscernmentResult:
        """Quick insight using tool-calling (legacy mode)."""
        prompt = f"""Review this code change:

Category: {category}
Purpose: {description}

```python
{code[:2000]}  # Truncate for context window
```

Decide: approve_code, reject_code, or request_refinement."""

        result = await self.insight.generate(
            prompt,
            tools=DISCERNMENT_TOOLS,
            tool_choice="required",
            options=GenerateOptions(temperature=0.1),
        )

        if result.has_tool_calls:
            tc = result.tool_calls[0]
            args = tc.arguments
            luminance = float(args.get("score", 5.0))
            raw_issues = args.get("issues", [])
            raw_strengths = args.get("strengths", [])

            return DiscernmentResult(
                verdict=self._tool_to_verdict(tc.name),
                confident=True,
                luminance=luminance,
                issues=tuple(raw_issues) if isinstance(raw_issues, list) else (),
                strengths=tuple(raw_strengths) if isinstance(raw_strengths, list) else (),
                reason=tc.name,
            )

        # No tool call - uncertain
        return DiscernmentResult(
            verdict=DiscernmentVerdict.UNCERTAIN,
            confident=False,
            luminance=5.0,
            reason="No decision from insight model",
        )

    def _tool_to_verdict(self, tool_name: str) -> DiscernmentVerdict:
        """Convert tool name to verdict."""
        mapping = {
            "approve_code": DiscernmentVerdict.APPROVE,
            "reject_code": DiscernmentVerdict.REJECT,
            "request_refinement": DiscernmentVerdict.NEEDS_REFINEMENT,
        }
        return mapping.get(tool_name, DiscernmentVerdict.UNCERTAIN)



# =============================================================================
# Discernment Tools
# =============================================================================


DISCERNMENT_TOOLS = (
    Tool(
        name="approve_code",
        description="Approve code that passes all quality checks. Use when code is correct, safe, complete, and follows best practices.",
        parameters={
            "type": "object",
            "properties": {
                "score": {
                    "type": "number",
                    "description": "Luminance score from 0-10 where 10 is perfect",
                },
                "strengths": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of code strengths",
                },
            },
            "required": ["score"],
        },
    ),
    Tool(
        name="reject_code",
        description="Reject code that has critical issues. Use when code has bugs, security issues, or is incomplete.",
        parameters={
            "type": "object",
            "properties": {
                "score": {
                    "type": "number",
                    "description": "Luminance score from 0-10",
                },
                "issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of critical issues found",
                },
            },
            "required": ["score", "issues"],
        },
    ),
    Tool(
        name="request_refinement",
        description="Request code refinement for minor issues. Use when code is mostly good but needs small improvements.",
        parameters={
            "type": "object",
            "properties": {
                "score": {
                    "type": "number",
                    "description": "Luminance score from 0-10",
                },
                "issues": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "List of issues to fix",
                },
                "suggestions": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": "Specific improvement suggestions",
                },
            },
            "required": ["score", "issues"],
        },
    ),
)


# =============================================================================
# Demo
# =============================================================================


async def demo():
    """Demonstrate the Discernment evaluator."""

    print("=" * 60)
    print("Discernment Demo (The Naaru's Quick Insight)")
    print("=" * 60)

    discerner = Discernment()

    # Test proposals
    test_proposals = [
        {
            "name": "Good code",
            "diff": '''
def calculate_sum(numbers: list[int]) -> int:
    """Calculate the sum of a list of numbers.

    Args:
        numbers: List of integers to sum

    Returns:
        The sum of all numbers
    """
    if not numbers:
        return 0
    return sum(numbers)
''',
            "summary": {"category": "code_quality", "rationale": "Add sum function"},
        },
        {
            "name": "Missing imports",
            "diff": '''
def load_config(path: str) -> dict:
    """Load configuration from JSON file."""
    with Path(path).open() as f:
        return json.load(f)
''',
            "summary": {"category": "code_quality", "rationale": "Add config loader"},
        },
        {
            "name": "Syntax error",
            "diff": '''
def broken_function(
    """This has a syntax error."""
    return 42
''',
            "summary": {"category": "code_quality", "rationale": "Broken function"},
        },
        {
            "name": "Dangerous code",
            "diff": '''
def execute_user_code(code_string: str) -> Any:
    """Execute arbitrary user code."""
    return eval(code_string)
''',
            "summary": {"category": "code_quality", "rationale": "Execute user code"},
        },
    ]

    for proposal in test_proposals:
        print(f"\n{'='*50}")
        print(f"Testing: {proposal['name']}")
        print("-" * 50)

        result = await discerner.evaluate(proposal)

        print(f"Verdict:    {result.verdict.value}")
        print(f"Confident:  {result.confident}")
        print(f"Luminance:  {result.luminance:.1f}/10")
        print(f"Reason:     {result.reason}")

        if result.issues:
            print(f"Issues:     {', '.join(result.issues[:3])}")

        checks = result.checks_passed
        print(f"Checks:     {sum(checks.values())}/{len(checks)} passed")
        for check, passed in checks.items():
            status = "✓" if passed else "✗"
            print(f"  {status} {check}")


if __name__ == "__main__":
    import asyncio
    asyncio.run(demo())

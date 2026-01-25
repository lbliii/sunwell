"""Specification Extractor for Deep Verification (RFC-047).

Extract what the code *should* do from available sources:
1. Explicit contract from ArtifactSpec (RFC-036)
2. Docstrings and comments in the code
3. Type signatures and annotations
4. Existing tests (if modifying existing code)
5. LLM inference from function name/context
"""


import ast
import json
import re
from typing import TYPE_CHECKING

from sunwell.models import GenerateOptions
from sunwell.quality.verification.types import (
    InputSpec,
    OutputSpec,
    Specification,
)

if TYPE_CHECKING:
    from sunwell.models import ModelProtocol
    from sunwell.planning.naaru.artifacts import ArtifactSpec


# Pre-compiled regex patterns for performance (avoid recompiling per-call)
_EDGE_CASE_PATTERNS = (
    re.compile(r"handle[s]?\s+(.+?)(?:edge case|case)", re.I),
    re.compile(r"edge case[s]?:\s*(.+?)(?:\.|$)", re.I),
    re.compile(r"should handle\s+(.+?)(?:\.|$)", re.I),
)
_PRECONDITION_PATTERNS = (
    re.compile(r"requires?\s+(.+?)(?:\.|$)", re.I),
    re.compile(r"must have\s+(.+?)(?:\.|$)", re.I),
    re.compile(r"assuming\s+(.+?)(?:\.|$)", re.I),
)
_POSTCONDITION_PATTERNS = (
    re.compile(r"returns?\s+(.+?)(?:\.|$)", re.I),
    re.compile(r"produces?\s+(.+?)(?:\.|$)", re.I),
    re.compile(r"outputs?\s+(.+?)(?:\.|$)", re.I),
)
_PARAM_RE = re.compile(r"(\w+)\s*(?:\(([^)]+)\))?\s*:\s*(.+)")
_RETURN_RE = re.compile(r"(?:(\w+)\s*:\s*)?(.+)")
_RAISES_RE = re.compile(r"(\w+)\s*:\s*(.+)")
_JSON_EXTRACT_RE = re.compile(r"\{[\s\S]*\}")


class SpecificationExtractor:
    """Extract specifications from multiple sources.

    Sources (in priority order):
    1. Explicit contract from ArtifactSpec (RFC-036)
    2. Docstrings and comments in the code
    3. Type signatures and annotations
    4. Existing tests (if modifying existing code)
    5. LLM inference from function name/context
    """

    def __init__(self, model: ModelProtocol):
        self.model = model

    async def extract(
        self,
        artifact: ArtifactSpec,
        content: str,
        existing_tests: str | None = None,
    ) -> Specification:
        """Extract specification from all available sources.

        Args:
            artifact: The artifact specification with contract
            content: The generated code content
            existing_tests: Existing test code if available

        Returns:
            Merged Specification from all sources
        """
        specs: list[Specification | None] = []

        # 1. Start with explicit contract (highest confidence)
        contract_spec = self._extract_from_contract(artifact.contract)
        if contract_spec:
            specs.append(contract_spec)

        # 2. Parse docstrings
        docstring_spec = self._extract_from_docstrings(content)
        if docstring_spec:
            specs.append(docstring_spec)

        # 3. Analyze type signatures
        signature_spec = self._extract_from_signatures(content)
        if signature_spec:
            specs.append(signature_spec)

        # 4. Mine existing tests
        if existing_tests:
            test_spec = self._extract_from_tests(existing_tests)
            if test_spec:
                specs.append(test_spec)

        # 5. LLM inference for gaps
        inferred_spec = await self._infer_missing(
            artifact, content, [s for s in specs if s is not None]
        )
        if inferred_spec:
            specs.append(inferred_spec)

        # 6. Merge specifications
        return self._merge_specs([s for s in specs if s is not None])

    def _extract_from_contract(self, contract: str) -> Specification | None:
        """Parse explicit contract from artifact spec.

        Contract format from RFC-036:
        "Function that takes X and returns Y, handling Z edge cases"
        """
        if not contract:
            return None

        # Extract any mentioned edge cases
        edge_cases: list[str] = []
        for pattern in _EDGE_CASE_PATTERNS:
            matches = pattern.findall(contract)
            edge_cases.extend(matches)

        # Extract preconditions
        preconditions: list[str] = []
        for pattern in _PRECONDITION_PATTERNS:
            matches = pattern.findall(contract)
            preconditions.extend(matches)

        # Extract postconditions
        postconditions: list[str] = []
        for pattern in _POSTCONDITION_PATTERNS:
            matches = pattern.findall(contract)
            postconditions.extend(matches)

        return Specification(
            description=contract,
            inputs=(),
            outputs=(),
            preconditions=tuple(preconditions),
            postconditions=tuple(postconditions),
            invariants=(),
            edge_cases=tuple(edge_cases),
            source="contract",
            confidence=0.95,  # Explicit contracts are highly trusted
        )

    def _extract_from_docstrings(self, content: str) -> Specification | None:
        """Parse docstrings for specifications."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return None

        description_parts: list[str] = []
        inputs: list[InputSpec] = []
        outputs: list[OutputSpec] = []
        preconditions: list[str] = []
        postconditions: list[str] = []
        edge_cases: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef | ast.ClassDef):
                docstring = ast.get_docstring(node)
                if docstring:
                    parsed = self._parse_docstring(node.name, docstring)
                    if parsed:
                        description_parts.append(parsed.get("description", ""))
                        inputs.extend(parsed.get("inputs", []))
                        outputs.extend(parsed.get("outputs", []))
                        preconditions.extend(parsed.get("preconditions", []))
                        postconditions.extend(parsed.get("postconditions", []))
                        edge_cases.extend(parsed.get("edge_cases", []))

        if not description_parts and not inputs and not outputs:
            return None

        return Specification(
            description=" ".join(description_parts),
            inputs=tuple(inputs),
            outputs=tuple(outputs),
            preconditions=tuple(preconditions),
            postconditions=tuple(postconditions),
            invariants=(),
            edge_cases=tuple(edge_cases),
            source="docstring",
            confidence=0.85,
        )

    def _parse_docstring(
        self, name: str, docstring: str
    ) -> dict | None:
        """Parse Google/NumPy style docstrings.

        Handles formats like:
        Args:
            param (type): Description
        Returns:
            type: Description
        Raises:
            Exception: When condition
        """
        result: dict = {
            "description": "",
            "inputs": [],
            "outputs": [],
            "preconditions": [],
            "postconditions": [],
            "edge_cases": [],
        }

        lines = docstring.split("\n")
        current_section = "description"
        section_content: list[str] = []

        for line in lines:
            stripped = line.strip()

            # Detect section headers
            if stripped in ("Args:", "Arguments:", "Parameters:"):
                if section_content:
                    result["description"] = " ".join(section_content)
                current_section = "args"
                section_content = []
            elif stripped in ("Returns:", "Return:", "Yields:"):
                current_section = "returns"
                section_content = []
            elif stripped in ("Raises:", "Raise:", "Throws:"):
                current_section = "raises"
                section_content = []
            elif stripped in ("Example:", "Examples:"):
                current_section = "examples"
                section_content = []
            elif stripped in ("Note:", "Notes:", "Warning:", "Warnings:"):
                current_section = "notes"
                section_content = []
            else:
                # Parse content based on current section
                if current_section == "description" and stripped:
                    section_content.append(stripped)
                elif current_section == "args" and stripped:
                    # Parse parameter: "param (type): description" or "param: description"
                    match = _PARAM_RE.match(stripped)
                    if match:
                        param_name, param_type, param_desc = match.groups()
                        result["inputs"].append(
                            InputSpec(
                                name=param_name,
                                type_hint=param_type or "Any",
                                constraints=(),
                                examples=(),
                            )
                        )
                elif current_section == "returns" and stripped:
                    # Parse return: "type: description" or just "description"
                    match = _RETURN_RE.match(stripped)
                    if match:
                        ret_type, ret_desc = match.groups()
                        result["outputs"].append(
                            OutputSpec(
                                type_hint=ret_type or "Any",
                                constraints=(),
                                examples=(),
                            )
                        )
                        # Postcondition from return description
                        if ret_desc:
                            result["postconditions"].append(ret_desc)
                elif current_section == "raises" and stripped:
                    # Raises section indicates preconditions/edge cases
                    match = _RAISES_RE.match(stripped)
                    if match:
                        exc_type, exc_desc = match.groups()
                        result["edge_cases"].append(f"{exc_type}: {exc_desc}")

        # Capture remaining description
        if current_section == "description" and section_content:
            result["description"] = " ".join(section_content)

        return result if any(result.values()) else None

    def _extract_from_signatures(self, content: str) -> Specification | None:
        """Extract specs from type annotations."""
        try:
            tree = ast.parse(content)
        except SyntaxError:
            return None

        inputs: list[InputSpec] = []
        outputs: list[OutputSpec] = []
        invariants: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                # Extract input types from arguments
                for arg in node.args.args:
                    if arg.annotation:
                        type_hint = ast.unparse(arg.annotation)
                        constraints = self._constraints_from_type(type_hint)
                        inputs.append(
                            InputSpec(
                                name=arg.arg,
                                type_hint=type_hint,
                                constraints=tuple(constraints),
                                examples=(),
                            )
                        )

                # Extract return type
                if node.returns:
                    type_hint = ast.unparse(node.returns)
                    constraints = self._constraints_from_type(type_hint)
                    outputs.append(
                        OutputSpec(
                            type_hint=type_hint,
                            constraints=tuple(constraints),
                            examples=(),
                        )
                    )

            elif isinstance(node, ast.ClassDef):
                # Check for frozen dataclass (immutability invariant)
                for decorator in node.decorator_list:
                    if (
                        isinstance(decorator, ast.Call)
                        and isinstance(decorator.func, ast.Name)
                        and decorator.func.id == "dataclass"
                    ):
                        for kw in decorator.keywords:
                            if (
                                kw.arg == "frozen"
                                and isinstance(kw.value, ast.Constant)
                                and kw.value.value
                            ):
                                invariants.append(
                                    f"{node.name} is immutable (frozen)"
                                )

        if not inputs and not outputs and not invariants:
            return None

        return Specification(
            description="",
            inputs=tuple(inputs),
            outputs=tuple(outputs),
            preconditions=(),
            postconditions=(),
            invariants=tuple(invariants),
            edge_cases=(),
            source="signature",
            confidence=0.9,  # Type signatures are reliable
        )

    def _constraints_from_type(self, type_hint: str) -> list[str]:
        """Infer constraints from type hints."""
        constraints: list[str] = []

        # Optional types can be None
        if "None" in type_hint or "Optional" in type_hint:
            constraints.append("can be None")

        # Collection types
        if "list" in type_hint.lower() or "List" in type_hint:
            constraints.append("is a list")
        if "dict" in type_hint.lower() or "Dict" in type_hint:
            constraints.append("is a dict")
        if "set" in type_hint.lower() or "Set" in type_hint:
            constraints.append("is a set")
        if "tuple" in type_hint.lower() or "Tuple" in type_hint:
            constraints.append("is a tuple")

        # Numeric types
        if type_hint in ("int", "float"):
            constraints.append("is numeric")

        return constraints

    def _extract_from_tests(self, test_content: str) -> Specification | None:
        """Extract specifications from existing tests.

        Tests encode implicit specifications:
        - Assertions show expected behavior
        - Test names describe features
        - Edge case tests show boundary handling
        """
        try:
            tree = ast.parse(test_content)
        except SyntaxError:
            return None

        edge_cases: list[str] = []
        postconditions: list[str] = []

        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                # Test function names encode specifications
                if node.name.startswith("test_"):
                    test_name = node.name[5:]  # Remove 'test_' prefix

                    # Detect edge case tests
                    edge_case_keywords = [
                        "empty",
                        "none",
                        "null",
                        "zero",
                        "negative",
                        "boundary",
                        "edge",
                        "invalid",
                        "error",
                        "fail",
                        "exception",
                    ]
                    for keyword in edge_case_keywords:
                        if keyword in test_name.lower():
                            edge_cases.append(
                                f"Handles {test_name.replace('_', ' ')}"
                            )
                            break

                # Extract assertions for postconditions
                for stmt in ast.walk(node):
                    if isinstance(stmt, ast.Assert):
                        try:
                            assertion = ast.unparse(stmt.test)
                            postconditions.append(f"Assert: {assertion}")
                        except Exception:
                            pass

        if not edge_cases and not postconditions:
            return None

        return Specification(
            description="Derived from existing tests",
            inputs=(),
            outputs=(),
            preconditions=(),
            postconditions=tuple(postconditions[:5]),  # Limit to avoid noise
            invariants=(),
            edge_cases=tuple(edge_cases),
            source="existing_tests",
            confidence=0.8,
        )

    async def _infer_missing(
        self,
        artifact: ArtifactSpec,
        content: str,
        existing_specs: list[Specification],
    ) -> Specification | None:
        """Use LLM to infer missing specification elements."""
        # Format existing specs for context
        existing_spec_text = self._format_existing_specs(existing_specs)

        prompt = f"""ARTIFACT: {artifact.id}
DESCRIPTION: {artifact.description}

CODE:
```python
{content[:2000]}
```

EXISTING SPECIFICATIONS:
{existing_spec_text}

---

Based on the code and context, identify any MISSING specifications:

1. What edge cases should be tested that aren't already covered?
2. What invariants should hold?
3. What preconditions are assumed but not documented?
4. What postconditions are guaranteed but not documented?

Focus on things NOT already covered by existing specs.
Be specific and concrete.

Output JSON:
{{
  "edge_cases": ["case 1", "case 2"],
  "invariants": ["invariant 1"],
  "preconditions": ["precondition 1"],
  "postconditions": ["postcondition 1"]
}}"""

        try:
            result = await self.model.generate(
                prompt,
                options=GenerateOptions(temperature=0.2, max_tokens=1000),
            )

            return self._parse_inferred_spec(result.text)
        except Exception:
            # If LLM fails, return None - other sources should suffice
            return None

    def _format_existing_specs(self, specs: list[Specification]) -> str:
        """Format existing specifications for prompt context."""
        if not specs:
            return "None extracted yet."

        parts: list[str] = []
        for spec in specs:
            parts.append(f"Source: {spec.source} (confidence: {spec.confidence})")
            if spec.description:
                parts.append(f"  Description: {spec.description[:100]}")
            if spec.preconditions:
                parts.append(f"  Preconditions: {spec.preconditions}")
            if spec.postconditions:
                parts.append(f"  Postconditions: {spec.postconditions}")
            if spec.edge_cases:
                parts.append(f"  Edge cases: {spec.edge_cases}")
            if spec.invariants:
                parts.append(f"  Invariants: {spec.invariants}")
            parts.append("")

        return "\n".join(parts)

    def _parse_inferred_spec(self, response: str) -> Specification | None:
        """Parse LLM response into Specification."""
        # Extract JSON from response
        json_match = _JSON_EXTRACT_RE.search(response)
        if not json_match:
            return None

        try:
            data = json.loads(json_match.group())
        except json.JSONDecodeError:
            return None

        edge_cases = tuple(data.get("edge_cases", []))
        invariants = tuple(data.get("invariants", []))
        preconditions = tuple(data.get("preconditions", []))
        postconditions = tuple(data.get("postconditions", []))

        if not any([edge_cases, invariants, preconditions, postconditions]):
            return None

        return Specification(
            description="Inferred from code analysis",
            inputs=(),
            outputs=(),
            preconditions=preconditions,
            postconditions=postconditions,
            invariants=invariants,
            edge_cases=edge_cases,
            source="inferred",
            confidence=0.6,  # Lower confidence for inferred specs
        )

    def _merge_specs(self, specs: list[Specification]) -> Specification:
        """Merge multiple specifications, preferring higher confidence sources."""
        if not specs:
            return Specification(
                description="No specification available",
                inputs=(),
                outputs=(),
                preconditions=(),
                postconditions=(),
                invariants=(),
                edge_cases=(),
                source="inferred",
                confidence=0.3,
            )

        # Sort by confidence descending
        sorted_specs = sorted(specs, key=lambda s: s.confidence, reverse=True)

        # Take description from highest confidence source
        description = next(
            (s.description for s in sorted_specs if s.description), ""
        )

        # Merge all unique inputs/outputs/conditions
        all_inputs: list[InputSpec] = []
        all_outputs: list[OutputSpec] = []
        all_preconditions: set[str] = set()
        all_postconditions: set[str] = set()
        all_invariants: set[str] = set()
        all_edge_cases: set[str] = set()

        seen_input_names: set[str] = set()
        for spec in sorted_specs:
            for inp in spec.inputs:
                if inp.name not in seen_input_names:
                    all_inputs.append(inp)
                    seen_input_names.add(inp.name)

            # Just take first output (usually one return type)
            if not all_outputs and spec.outputs:
                all_outputs.extend(spec.outputs)

            all_preconditions.update(spec.preconditions)
            all_postconditions.update(spec.postconditions)
            all_invariants.update(spec.invariants)
            all_edge_cases.update(spec.edge_cases)

        # Compute merged confidence (weighted average)
        total_weight = sum(s.confidence for s in sorted_specs)
        merged_confidence = total_weight / len(sorted_specs) if sorted_specs else 0.3

        # Source is the highest confidence source
        source = sorted_specs[0].source if sorted_specs else "inferred"

        return Specification(
            description=description,
            inputs=tuple(all_inputs),
            outputs=tuple(all_outputs),
            preconditions=tuple(all_preconditions),
            postconditions=tuple(all_postconditions),
            invariants=tuple(all_invariants),
            edge_cases=tuple(all_edge_cases),
            source=source,
            confidence=merged_confidence,
        )

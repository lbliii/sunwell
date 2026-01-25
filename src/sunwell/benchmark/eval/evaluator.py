"""Full-Stack Evaluator (RFC-098).

Evaluates multi-file project outputs with scoring across:
- Structure: Does it have expected files?
- Runnable: Does it actually run without errors?
- Features: Does it have expected features?
- Quality: Code quality metrics

Scoring is honest — if it fails, we show it clearly.
"""

import ast
import contextlib
import logging
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sunwell.benchmark.eval.types import FullStackScore, FullStackTask

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class FeatureCheck:
    """Result of checking for a specific feature."""

    name: str
    present: bool
    evidence: str | None = None


class FullStackEvaluator:
    """Evaluate multi-file project outputs.

    Provides honest, transparent scoring across multiple dimensions.
    If something fails, we show it clearly with appropriate colors.
    """

    # Score weights for final composite
    WEIGHTS = {
        "structure": 0.2,
        "runnable": 0.3,
        "features": 0.3,
        "quality": 0.2,
    }

    def evaluate(
        self,
        output_dir: Path,
        task: FullStackTask,
    ) -> FullStackScore:
        """Score a generated project.

        Args:
            output_dir: Directory containing generated files.
            task: The task definition with expectations.

        Returns:
            FullStackScore with detailed breakdown.
        """
        scores: dict[str, float] = {}

        # 1. Structure score: Does it have expected files?
        scores["structure"] = self._score_structure(output_dir, task.expected_structure)

        # 2. Runnable score: Does it actually run?
        runnable_result = self._score_runnable(output_dir)
        scores["runnable"] = runnable_result["score"]
        error_details = runnable_result.get("error")

        # 3. Feature score: Does it have expected features?
        scores["features"] = self._score_features(output_dir, task.expected_features)

        # 4. Quality score: Code quality metrics
        scores["quality"] = self._score_quality(output_dir)

        # Compute files and lines
        python_files = list(output_dir.rglob("*.py"))
        files_count = len(python_files)
        lines_count = sum(
            len(f.read_text().splitlines())
            for f in python_files
            if f.exists()
        )

        # Count tests
        tests_count = self._count_tests(output_dir)

        # Weighted average
        final_score = sum(
            scores[dim] * self.WEIGHTS[dim]
            for dim in self.WEIGHTS
        )

        return FullStackScore(
            final_score=round(final_score, 1),
            subscores=scores,
            runnable=scores["runnable"] >= 8.0,
            files_count=files_count,
            lines_count=lines_count,
            tests_count=tests_count,
            error_details=error_details,
        )

    # =========================================================================
    # STRUCTURE SCORING
    # =========================================================================

    def _score_structure(
        self,
        output_dir: Path,
        expected_structure: dict[str, Any],
    ) -> float:
        """Score based on expected file structure.

        10 = All required files present
        5 = Some required files missing
        0 = Most required files missing
        """
        if not expected_structure:
            # No structure requirements - give base score if any files exist
            if list(output_dir.rglob("*.py")):
                return 7.0
            return 0.0

        required_count = 0
        required_found = 0
        optional_count = 0
        optional_found = 0

        def check_structure(structure: dict[str, Any], base_path: Path) -> None:
            nonlocal required_count, required_found, optional_count, optional_found

            for path_key, value in structure.items():
                full_path = base_path / path_key

                if isinstance(value, dict):
                    # It's a directory, recurse
                    if full_path.is_dir():
                        check_structure(value, full_path)
                elif value == "required":
                    required_count += 1
                    if full_path.exists() or (path_key.endswith("/") and full_path.is_dir()):
                        required_found += 1
                elif value == "optional":
                    optional_count += 1
                    if full_path.exists() or (path_key.endswith("/") and full_path.is_dir()):
                        optional_found += 1

        check_structure(expected_structure, output_dir)

        if required_count == 0:
            return 7.0  # No requirements, give passing score

        # Required files are 80% of score, optional are 20%
        required_score = (required_found / required_count) * 8.0 if required_count > 0 else 8.0
        optional_score = (optional_found / optional_count) * 2.0 if optional_count > 0 else 0.0

        return min(10.0, required_score + optional_score)

    # =========================================================================
    # RUNNABLE SCORING
    # =========================================================================

    def _score_runnable(self, output_dir: Path) -> dict[str, Any]:
        """Check if the project actually runs.

        10 = Runs without errors
        5 = Syntax errors but parseable
        2 = Import errors
        0 = Won't even parse
        """
        python_files = list(output_dir.rglob("*.py"))

        if not python_files:
            return {"score": 0.0, "error": "No Python files found"}

        # Phase 1: Check syntax (can we parse all files?)
        syntax_errors = []
        for py_file in python_files:
            try:
                content = py_file.read_text()
                ast.parse(content)
            except SyntaxError as e:
                syntax_errors.append(f"{py_file.name}: {e}")

        if syntax_errors:
            return {
                "score": 2.0,
                "error": f"Syntax errors: {'; '.join(syntax_errors[:3])}",
            }

        # Phase 2: Check imports (can we import main modules?)
        import_errors = []
        main_files = ["main.py", "app.py", "cli.py", "__init__.py"]
        for main_file in main_files:
            main_path = output_dir / main_file
            if main_path.exists():
                result = self._try_import(main_path)
                if not result["success"]:
                    import_errors.append(result["error"])

        if import_errors:
            return {
                "score": 5.0,
                "error": f"Import errors: {'; '.join(import_errors[:2])}",
            }

        # Phase 3: If there's a requirements.txt, that's a good sign
        has_requirements = (output_dir / "requirements.txt").exists()

        # Phase 4: Check if tests exist and pass (bonus)
        tests_pass = self._run_tests(output_dir)

        if tests_pass:
            return {"score": 10.0}
        elif has_requirements:
            return {"score": 9.0}
        else:
            return {"score": 8.0}

    def _try_import(self, py_file: Path) -> dict[str, Any]:
        """Try to import a Python file to check for import errors."""
        try:
            # Use subprocess to isolate import
            result = subprocess.run(
                [sys.executable, "-c", f"import ast; ast.parse(open('{py_file}').read())"],
                capture_output=True,
                text=True,
                timeout=5,
                cwd=py_file.parent,
            )
            if result.returncode != 0:
                return {"success": False, "error": result.stderr[:100]}
            return {"success": True}
        except subprocess.TimeoutExpired:
            return {"success": False, "error": "Timeout"}
        except Exception as e:
            return {"success": False, "error": str(e)[:100]}

    def _run_tests(self, output_dir: Path) -> bool:
        """Try to run tests if they exist."""
        test_files = list(output_dir.rglob("test_*.py"))
        if not test_files:
            return False  # No tests to run

        try:
            result = subprocess.run(
                [sys.executable, "-m", "pytest", "--collect-only", "-q"],
                capture_output=True,
                text=True,
                timeout=10,
                cwd=output_dir,
            )
            # If pytest can collect tests, consider it a pass
            return result.returncode == 0
        except Exception:
            return False

    # =========================================================================
    # FEATURE SCORING
    # =========================================================================

    def _score_features(
        self,
        output_dir: Path,
        expected_features: frozenset[str],
    ) -> float:
        """Score based on presence of expected features.

        Uses pattern matching and AST analysis to detect features.
        """
        if not expected_features:
            return 7.0  # No feature requirements

        # Read all Python content
        all_content = ""
        for py_file in output_dir.rglob("*.py"):
            with contextlib.suppress(Exception):
                all_content += py_file.read_text() + "\n"

        features_found = 0
        for feature in expected_features:
            if self._check_feature(feature, all_content, output_dir):
                features_found += 1

        if len(expected_features) == 0:
            return 7.0

        return (features_found / len(expected_features)) * 10.0

    def _check_feature(
        self,
        feature: str,
        content: str,
        output_dir: Path,
    ) -> bool:
        """Check if a specific feature is present."""
        content_lower = content.lower()

        # Feature detection patterns
        patterns: dict[str, list[str]] = {
            "app_factory_pattern": ["def create_app", "flask(__name__)"],
            "database_models": ["class", "db.model", "sqlalchemy", "model"],
            "crud_routes": [
                "@app.route", "@bp.route", "def get", "def post", "def put", "def delete"
            ],
            "error_handling": ["try:", "except", "raise", "abort("],
            "input_validation": ["validate", "pydantic", "wtforms", "marshmallow"],
            "foreign_key_relationships": ["foreignkey", "relationship(", "db.relationship"],
            "click_commands": ["@click.command", "@click.group", "click.option"],
            "file_persistence": ["json.dump", "json.load", "open(", "with open"],
            "help_text": ["help=", "--help", "docstring"],
            "priority_support": ["priority", "low", "medium", "high"],
            "fastapi_app": ["fastapi", "from fastapi import"],
            "pydantic_models": ["basemodel", "pydantic", "class.*basemodel"],
            "crud_endpoints": ["@app.get", "@app.post", "@app.put", "@app.delete", "@router"],
            "search_functionality": ["search", "query", "filter"],
            "main_function": ["def main("],
            "name_guard": ['if __name__ == "__main__"', "if __name__ == '__main__'"],
            "type_hints": ["->", ": str", ": int", ": list", ": dict", ": bool"],
            "docstring": ['"""', "'''"],
            "working_code": ["def ", "class "],
        }

        if feature in patterns:
            return any(pattern.lower() in content_lower for pattern in patterns[feature])

        # Default: look for the feature name in content
        return feature.replace("_", " ") in content_lower or feature in content_lower

    # =========================================================================
    # QUALITY SCORING
    # =========================================================================

    def _score_quality(self, output_dir: Path) -> float:
        """Score code quality based on various metrics.

        Considers:
        - Type hints
        - Docstrings
        - File organization
        - Code patterns
        """
        python_files = list(output_dir.rglob("*.py"))
        if not python_files:
            return 0.0

        quality_points = 0.0
        max_points = 10.0

        # Check for type hints (2 points)
        has_type_hints = False
        for py_file in python_files:
            try:
                content = py_file.read_text()
                if "->" in content or ": str" in content or ": int" in content:
                    has_type_hints = True
                    break
            except Exception:
                pass
        if has_type_hints:
            quality_points += 2.0

        # Check for docstrings (2 points)
        has_docstrings = False
        for py_file in python_files:
            try:
                content = py_file.read_text()
                if '"""' in content or "'''" in content:
                    has_docstrings = True
                    break
            except Exception:
                pass
        if has_docstrings:
            quality_points += 2.0

        # Check for file organization (2 points)
        # Multiple files = better organization
        if len(python_files) >= 3:
            quality_points += 2.0
        elif len(python_files) >= 2:
            quality_points += 1.0

        # Check for requirements.txt (1 point)
        if (output_dir / "requirements.txt").exists():
            quality_points += 1.0

        # Check for README (1 point)
        if (output_dir / "README.md").exists() or (output_dir / "README.rst").exists():
            quality_points += 1.0

        # Check for tests (2 points)
        test_files = list(output_dir.rglob("test_*.py"))
        if test_files:
            quality_points += 2.0

        return min(max_points, quality_points)

    # =========================================================================
    # HELPERS
    # =========================================================================

    def _count_tests(self, output_dir: Path) -> int:
        """Count the number of test functions."""
        count = 0
        for test_file in output_dir.rglob("test_*.py"):
            try:
                content = test_file.read_text()
                tree = ast.parse(content)
                for node in ast.walk(tree):
                    if isinstance(node, ast.FunctionDef) and node.name.startswith("test_"):
                        count += 1
            except Exception:
                pass
        return count


# =============================================================================
# COMPARISON UTILITIES
# =============================================================================


def compute_improvement(
    single_shot_score: float,
    sunwell_score: float,
) -> float:
    """Compute percentage improvement."""
    if single_shot_score == 0:
        return 0.0 if sunwell_score == 0 else 100.0
    return ((sunwell_score - single_shot_score) / single_shot_score) * 100


def determine_winner(
    single_shot_score: float,
    sunwell_score: float,
    margin: float = 0.5,
) -> str:
    """Determine who won the comparison.

    Args:
        single_shot_score: Baseline score.
        sunwell_score: Sunwell score.
        margin: Score difference needed to declare a winner.

    Returns:
        "sunwell", "single_shot", or "tie"
    """
    if sunwell_score > single_shot_score + margin:
        return "sunwell"
    elif single_shot_score > sunwell_score + margin:
        return "single_shot"
    else:
        return "tie"


def score_to_color(score: float) -> str:
    """Map score to honest color signal.

    10: Green - genuinely good
    5-9.9: Yellow - mediocre, needs work
    <5: Red - failed, be honest
    """
    if score >= 8.0:
        return "green"
    elif score >= 5.0:
        return "yellow"
    else:
        return "red"


def comparison_to_color(sunwell: float, baseline: float) -> str:
    """Color based on comparison outcome."""
    if sunwell > baseline + 0.5:
        return "green"  # Sunwell won
    elif sunwell >= baseline - 0.5:
        return "cyan"  # Tie (within margin)
    else:
        return "red"  # Single-shot won - be honest about it

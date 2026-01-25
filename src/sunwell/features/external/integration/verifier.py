"""Integration Verifier (RFC-067).

Verifies that artifacts are actually wired together, not just created.
Uses AST parsing for Python and regex patterns for other checks.

Key capabilities:
1. Import verification (does file A import symbol X from file B?)
2. Call verification (does function A call function B?)
3. Stub detection (pass, TODO, raise NotImplementedError)
4. Orphan detection (unused artifacts)
"""

import ast
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from sunwell.features.external.integration.types import (
    IntegrationCheck,
    IntegrationCheckType,
    IntegrationResult,
    IntegrationVerificationSummary,
    OrphanDetection,
    ProducedArtifact,
    RequiredIntegration,
    StubDetection,
)

# =============================================================================
# AST Visitors for Python Analysis
# =============================================================================


class ImportVisitor(ast.NodeVisitor):
    """Collect all imports from an AST."""

    def __init__(self) -> None:
        self.imports: list[tuple[str, str | None, int]] = []
        """List of (module, name, line) tuples."""

    def visit_Import(self, node: ast.Import) -> None:
        for alias in node.names:
            self.imports.append((alias.name, alias.asname, node.lineno))
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> None:
        module = node.module or ""
        for alias in node.names:
            full_import = f"{module}.{alias.name}" if module else alias.name
            self.imports.append((full_import, alias.asname, node.lineno))
        self.generic_visit(node)


class CallVisitor(ast.NodeVisitor):
    """Collect all function/method calls from an AST."""

    def __init__(self) -> None:
        self.calls: list[tuple[str, int]] = []
        """List of (call_name, line) tuples."""

    def visit_Call(self, node: ast.Call) -> None:
        call_name = self._get_call_name(node.func)
        if call_name:
            self.calls.append((call_name, node.lineno))
        self.generic_visit(node)

    def _get_call_name(self, node: ast.expr) -> str | None:
        """Extract the name of a call."""
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            value = self._get_call_name(node.value)
            if value:
                return f"{value}.{node.attr}"
            return node.attr
        return None


class StubVisitor(ast.NodeVisitor):
    """Detect stub implementations in an AST."""

    def __init__(self, file_path: Path) -> None:
        self.file_path = file_path
        self.stubs: list[StubDetection] = []

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self._check_function_body(node, node.name)
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self._check_function_body(node, node.name)
        self.generic_visit(node)

    def _check_function_body(
        self,
        node: ast.FunctionDef | ast.AsyncFunctionDef,
        name: str,
    ) -> None:
        """Check if function body is a stub."""
        if not node.body:
            self.stubs.append(StubDetection(
                file=self.file_path,
                line=node.lineno,
                symbol=name,
                stub_type="empty",
                context=f"def {name}(...): <empty body>",
            ))
            return

        # Check for single-statement stubs
        if len(node.body) == 1:
            stmt = node.body[0]

            # pass statement
            if isinstance(stmt, ast.Pass):
                self.stubs.append(StubDetection(
                    file=self.file_path,
                    line=stmt.lineno,
                    symbol=name,
                    stub_type="pass",
                    context=f"def {name}(...): pass",
                ))
                return

            # Ellipsis (...)
            if (
                isinstance(stmt, ast.Expr)
                and isinstance(stmt.value, ast.Constant)
                and stmt.value.value is ...
            ):
                    self.stubs.append(StubDetection(
                        file=self.file_path,
                        line=stmt.lineno,
                        symbol=name,
                        stub_type="ellipsis",
                        context=f"def {name}(...): ...",
                    ))
                    return

            # raise NotImplementedError or raise NotImplementedError()
            if isinstance(stmt, ast.Raise):
                exc = stmt.exc
                is_not_implemented = False

                # Handle: raise NotImplementedError (no parentheses)
                if isinstance(exc, ast.Name) and exc.id == "NotImplementedError":
                    is_not_implemented = True
                # Handle: raise NotImplementedError() (with parentheses)
                elif isinstance(exc, ast.Call):
                    func = exc.func
                    if isinstance(func, ast.Name) and func.id == "NotImplementedError":
                        is_not_implemented = True

                if is_not_implemented:
                    self.stubs.append(StubDetection(
                        file=self.file_path,
                        line=stmt.lineno,
                        symbol=name,
                        stub_type="not_implemented",
                        context=f"def {name}(...): raise NotImplementedError",
                    ))
                    return

        # Check for TODO/FIXME comments in body
        # Note: AST doesn't preserve comments, so we'd need to check source


class DefinitionVisitor(ast.NodeVisitor):
    """Collect class and function definitions."""

    def __init__(self) -> None:
        self.definitions: list[tuple[str, str, int]] = []
        """List of (name, type, line) tuples."""

    def visit_ClassDef(self, node: ast.ClassDef) -> None:
        self.definitions.append((node.name, "class", node.lineno))
        self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        self.definitions.append((node.name, "function", node.lineno))
        self.generic_visit(node)

    def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
        self.definitions.append((node.name, "function", node.lineno))
        self.generic_visit(node)


# =============================================================================
# Integration Verifier
# =============================================================================


@dataclass(slots=True)
class IntegrationVerifier:
    """Verify that artifacts are actually wired together.

    Detects:
    - Orphaned files (nothing imports them)
    - Dead code (functions never called)
    - Missing registrations (routes not in app)
    - Stub implementations (pass, TODO, NotImplementedError)

    Example:
        >>> verifier = IntegrationVerifier(project_root=Path("."))
        >>>
        >>> # Check if artifact is used
        >>> result = await verifier.verify_artifact_connected(artifact)
        >>> if not result.passed:
        ...     print(f"Orphan: {artifact.id}")
        >>>
        >>> # Run all checks for a goal
        >>> summary = await verifier.verify_goal(goal)
        >>> if not summary.overall_passed:
        ...     for result in summary.results:
        ...         if not result.passed:
        ...             print(f"Failed: {result.message}")
    """

    project_root: Path
    """Project root directory."""

    _ast_cache: dict[Path, ast.Module] = field(default_factory=dict)
    """Cache of parsed ASTs."""

    _import_cache: dict[Path, list[tuple[str, str | None, int]]] = field(default_factory=dict)
    """Cache of imports by file."""

    def clear_cache(self) -> None:
        """Clear AST and import caches."""
        self._ast_cache.clear()
        self._import_cache.clear()

    # =========================================================================
    # Core Verification Methods
    # =========================================================================

    async def verify_integration(
        self,
        source_file: Path,
        integration: RequiredIntegration,
    ) -> IntegrationResult:
        """Check that a specific integration exists.

        Args:
            source_file: File that should contain the integration
            integration: The required integration to verify

        Returns:
            IntegrationResult with pass/fail and details
        """
        check = IntegrationCheck(
            check_type=self._integration_type_to_check_type(integration.integration_type),
            target_file=source_file,
            pattern=integration.verification_pattern or integration.artifact_id,
            required=True,
            description=f"Verify {integration.integration_type.value} of {integration.artifact_id}",
        )
        return await self.run_check(check)

    async def verify_artifact_connected(
        self,
        artifact: ProducedArtifact,
        search_paths: list[Path] | None = None,
    ) -> IntegrationResult:
        """Check that an artifact is actually used somewhere.

        Detects orphaned artifacts (files exist but nothing uses them).

        Args:
            artifact: The artifact to check
            search_paths: Paths to search for usage (defaults to project_root)

        Returns:
            IntegrationResult indicating if artifact is used
        """
        search_paths = search_paths or [self.project_root]
        found_usages: list[str] = []

        # Get symbols to search for
        symbols_to_find = set(artifact.exports)
        if not symbols_to_find and ":" in artifact.location:
            # Extract from location if no exports specified
            symbol = artifact.location.split(":")[-1]
            symbols_to_find.add(symbol)

        # Search all Python files
        for search_path in search_paths:
            for py_file in search_path.rglob("*.py"):
                # Skip the artifact's own file
                if artifact.location.startswith(str(py_file)):
                    continue

                imports = await self._get_imports(py_file)
                for module, alias, line in imports:
                    for symbol in symbols_to_find:
                        if symbol in module or (alias and symbol == alias):
                            found_usages.append(f"{py_file}:{line}")

        # Determine target file from artifact location
        if ":" in artifact.location:
            target_file = Path(artifact.location.split(":")[0])
        else:
            target_file = Path(artifact.location)

        check = IntegrationCheck(
            check_type=IntegrationCheckType.USED_NOT_ORPHAN,
            target_file=target_file,
            pattern=",".join(symbols_to_find),
            required=True,
            description=f"Check {artifact.id} is imported/used somewhere",
        )

        if found_usages:
            return IntegrationResult(
                check=check,
                passed=True,
                found="; ".join(found_usages[:5]),
                message=f"Artifact {artifact.id} is used in {len(found_usages)} location(s)",
            )
        else:
            return IntegrationResult(
                check=check,
                passed=False,
                message=f"Artifact {artifact.id} is not imported anywhere (orphan)",
                suggestions=(
                    f"Import {next(iter(symbols_to_find), artifact.id)} in a file that needs it",
                    "Or remove the artifact if it's not needed",
                ),
            )

    async def detect_stubs(self, file_path: Path) -> list[StubDetection]:
        """Find incomplete implementations in a file.

        Detects:
        - `pass` statements in functions
        - `raise NotImplementedError`
        - `...` (ellipsis) bodies
        - Empty function bodies

        Args:
            file_path: File to check

        Returns:
            List of detected stubs
        """
        stubs: list[StubDetection] = []

        # AST-based detection
        try:
            tree = await self._get_ast(file_path)
            visitor = StubVisitor(file_path)
            visitor.visit(tree)
            stubs.extend(visitor.stubs)
        except SyntaxError:
            pass  # File has syntax errors, can't parse

        # Regex-based detection for TODO/FIXME comments
        try:
            content = file_path.read_text()
            for match in re.finditer(r"#\s*(TODO|FIXME)[:.]?\s*(.{0,50})", content, re.IGNORECASE):
                line_num = content[:match.start()].count("\n") + 1
                stub_type = "todo" if "TODO" in match.group(1).upper() else "fixme"
                stubs.append(StubDetection(
                    file=file_path,
                    line=line_num,
                    symbol="<comment>",
                    stub_type=stub_type,
                    context=match.group(0).strip(),
                ))
        except OSError:
            pass

        return stubs

    async def detect_stubs_in_directory(self, directory: Path) -> list[StubDetection]:
        """Find all stubs in a directory.

        Args:
            directory: Directory to search

        Returns:
            List of all detected stubs
        """
        all_stubs: list[StubDetection] = []

        for py_file in directory.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            stubs = await self.detect_stubs(py_file)
            all_stubs.extend(stubs)

        return all_stubs

    async def detect_orphans(
        self,
        artifacts: list[ProducedArtifact],
    ) -> list[OrphanDetection]:
        """Find artifacts that aren't used anywhere.

        Args:
            artifacts: List of artifacts to check

        Returns:
            List of orphaned artifacts
        """
        orphans: list[OrphanDetection] = []

        for artifact in artifacts:
            result = await self.verify_artifact_connected(artifact)
            if not result.passed:
                # Determine file and symbol from location
                if ":" in artifact.location:
                    file_str, symbol = artifact.location.rsplit(":", 1)
                else:
                    file_str = artifact.location
                    symbol = artifact.id

                orphans.append(OrphanDetection(
                    artifact=artifact,
                    file=Path(file_str),
                    symbol=symbol,
                    suggestion=result.suggestions[0] if result.suggestions else "",
                ))

        return orphans

    # =========================================================================
    # Check Execution
    # =========================================================================

    async def run_check(self, check: IntegrationCheck) -> IntegrationResult:
        """Execute an integration check.

        Routes to appropriate checker based on check_type.

        Args:
            check: The check to run

        Returns:
            IntegrationResult with pass/fail and details
        """
        match check.check_type:
            case IntegrationCheckType.IMPORT_EXISTS:
                return await self._check_import_exists(check)
            case IntegrationCheckType.CALL_EXISTS:
                return await self._check_call_exists(check)
            case IntegrationCheckType.ROUTE_REGISTERED:
                return await self._check_route_registered(check)
            case IntegrationCheckType.CONFIG_PRESENT:
                return await self._check_config_present(check)
            case IntegrationCheckType.TEST_EXISTS:
                return await self._check_test_exists(check)
            case IntegrationCheckType.USED_NOT_ORPHAN:
                return await self._check_used_not_orphan(check)
            case IntegrationCheckType.NO_STUBS:
                return await self._check_no_stubs(check)
            case _:
                return IntegrationResult(
                    check=check,
                    passed=False,
                    message=f"Unknown check type: {check.check_type}",
                )

    async def run_checks(
        self,
        checks: list[IntegrationCheck],
    ) -> list[IntegrationResult]:
        """Run multiple checks.

        Args:
            checks: Checks to run

        Returns:
            List of results
        """
        results = []
        for check in checks:
            result = await self.run_check(check)
            results.append(result)
        return results

    async def verify_goal(
        self,
        goal_id: str,
        checks: list[IntegrationCheck],
        produced_artifacts: list[ProducedArtifact] | None = None,
    ) -> IntegrationVerificationSummary:
        """Run all verifications for a goal.

        Args:
            goal_id: The goal being verified
            checks: Integration checks to run
            produced_artifacts: Artifacts to check for orphans/stubs

        Returns:
            IntegrationVerificationSummary with all results
        """
        results = await self.run_checks(checks)

        # Count results
        passed = sum(1 for r in results if r.passed)
        failed_required = sum(1 for r in results if not r.passed and r.check.required)
        failed_optional = sum(1 for r in results if not r.passed and not r.check.required)

        # Detect stubs in produced artifacts
        stubs: list[StubDetection] = []
        if produced_artifacts:
            for artifact in produced_artifacts:
                if ":" in artifact.location:
                    file_str = artifact.location.split(":")[0]
                else:
                    file_str = artifact.location

                file_path = self.project_root / file_str
                if file_path.exists() and file_path.suffix == ".py":
                    artifact_stubs = await self.detect_stubs(file_path)
                    stubs.extend(artifact_stubs)

        # Detect orphans
        orphans: list[OrphanDetection] = []
        if produced_artifacts:
            orphans = await self.detect_orphans(produced_artifacts)

        return IntegrationVerificationSummary(
            goal_id=goal_id,
            total_checks=len(checks),
            passed_checks=passed,
            failed_required=failed_required,
            failed_optional=failed_optional,
            stubs_detected=tuple(stubs),
            orphans_detected=tuple(orphans),
            results=tuple(results),
        )

    # =========================================================================
    # Private Check Implementations
    # =========================================================================

    async def _check_import_exists(self, check: IntegrationCheck) -> IntegrationResult:
        """Check if an import exists in a file."""
        if not check.target_file.exists():
            return IntegrationResult(
                check=check,
                passed=False,
                message=f"File does not exist: {check.target_file}",
                suggestions=(f"Create {check.target_file} first",),
            )

        imports = await self._get_imports(check.target_file)

        # Check if pattern matches any import
        pattern = check.pattern.lower()
        for module, alias, line in imports:
            if pattern in module.lower() or (alias and pattern in alias.lower()):
                return IntegrationResult(
                    check=check,
                    passed=True,
                    found=f"line {line}: import {module}" + (f" as {alias}" if alias else ""),
                    message=f"Found import matching '{check.pattern}'",
                )

        # Also check with regex if pattern looks like one
        try:
            content = check.target_file.read_text()
            if re.search(check.pattern, content):
                return IntegrationResult(
                    check=check,
                    passed=True,
                    found="<regex match>",
                    message=f"Found pattern matching '{check.pattern}'",
                )
        except re.error:
            pass  # Not a valid regex

        return IntegrationResult(
            check=check,
            passed=False,
            message=f"Import '{check.pattern}' not found in {check.target_file}",
            suggestions=(f"Add: {check.pattern}",),
        )

    async def _check_call_exists(self, check: IntegrationCheck) -> IntegrationResult:
        """Check if a function call exists in a file."""
        if not check.target_file.exists():
            return IntegrationResult(
                check=check,
                passed=False,
                message=f"File does not exist: {check.target_file}",
            )

        try:
            tree = await self._get_ast(check.target_file)
            visitor = CallVisitor()
            visitor.visit(tree)

            pattern = check.pattern.lower()
            for call_name, line in visitor.calls:
                if pattern in call_name.lower():
                    return IntegrationResult(
                        check=check,
                        passed=True,
                        found=f"line {line}: {call_name}()",
                        message=f"Found call to '{check.pattern}'",
                    )

            return IntegrationResult(
                check=check,
                passed=False,
                message=f"Call to '{check.pattern}' not found in {check.target_file}",
                suggestions=(f"Add a call to {check.pattern}() in {check.target_file}",),
            )
        except SyntaxError as e:
            return IntegrationResult(
                check=check,
                passed=False,
                message=f"Syntax error in {check.target_file}: {e}",
            )

    async def _check_route_registered(self, check: IntegrationCheck) -> IntegrationResult:
        """Check if a route is registered in an app."""
        if not check.target_file.exists():
            return IntegrationResult(
                check=check,
                passed=False,
                message=f"File does not exist: {check.target_file}",
            )

        content = check.target_file.read_text()

        # Look for Flask/FastAPI route patterns
        patterns = [
            rf"@\w+\.route\(['\"].*{check.pattern}.*['\"]",
            rf"@\w+\.get\(['\"].*{check.pattern}.*['\"]",
            rf"@\w+\.post\(['\"].*{check.pattern}.*['\"]",
            rf"@\w+\.put\(['\"].*{check.pattern}.*['\"]",
            rf"@\w+\.delete\(['\"].*{check.pattern}.*['\"]",
            rf"@\w+\.patch\(['\"].*{check.pattern}.*['\"]",
            rf"add_url_rule\(['\"].*{check.pattern}.*['\"]",
            r"include_router\(",  # FastAPI
        ]

        for pattern in patterns:
            match = re.search(pattern, content, re.IGNORECASE)
            if match:
                return IntegrationResult(
                    check=check,
                    passed=True,
                    found=match.group(0),
                    message=f"Route '{check.pattern}' is registered",
                )

        return IntegrationResult(
            check=check,
            passed=False,
            message=f"Route '{check.pattern}' not registered in {check.target_file}",
            suggestions=(
                f"Add @app.route('{check.pattern}') decorator",
                f"Or add to router with app.add_url_rule('{check.pattern}', ...)",
            ),
        )

    async def _check_config_present(self, check: IntegrationCheck) -> IntegrationResult:
        """Check if a config key is present."""
        if not check.target_file.exists():
            return IntegrationResult(
                check=check,
                passed=False,
                message=f"Config file does not exist: {check.target_file}",
            )

        content = check.target_file.read_text()

        # Handle different config formats
        if check.target_file.suffix in (".yaml", ".yml"):
            if check.pattern in content:
                return IntegrationResult(
                    check=check,
                    passed=True,
                    message=f"Config key '{check.pattern}' found",
                )
        elif check.target_file.suffix == ".json":
            if f'"{check.pattern}"' in content:
                return IntegrationResult(
                    check=check,
                    passed=True,
                    message=f"Config key '{check.pattern}' found",
                )
        elif check.target_file.suffix in (".env", ".toml", ".ini"):
            if re.search(rf"^{re.escape(check.pattern)}\s*=", content, re.MULTILINE):
                return IntegrationResult(
                    check=check,
                    passed=True,
                    message=f"Config key '{check.pattern}' found",
                )
        else:
            # Generic search
            if check.pattern in content:
                return IntegrationResult(
                    check=check,
                    passed=True,
                    message=f"Config key '{check.pattern}' found",
                )

        return IntegrationResult(
            check=check,
            passed=False,
            message=f"Config key '{check.pattern}' not found in {check.target_file}",
            suggestions=(f"Add {check.pattern} to {check.target_file}",),
        )

    async def _check_test_exists(self, check: IntegrationCheck) -> IntegrationResult:
        """Check if a test exists for a function/class."""
        # Search in tests directory
        tests_dir = self.project_root / "tests"
        if not tests_dir.exists():
            tests_dir = self.project_root / "test"

        if not tests_dir.exists():
            return IntegrationResult(
                check=check,
                passed=False,
                message="No tests directory found",
                suggestions=("Create a tests/ directory",),
            )

        pattern_lower = check.pattern.lower()
        test_patterns = [
            f"test_{pattern_lower}",
            f"test{pattern_lower}",
            f"{pattern_lower}_test",
        ]

        for test_file in tests_dir.rglob("test_*.py"):
            content = test_file.read_text().lower()
            for test_pattern in test_patterns:
                if test_pattern in content:
                    return IntegrationResult(
                        check=check,
                        passed=True,
                        found=str(test_file),
                        message=f"Test for '{check.pattern}' found in {test_file}",
                    )

        return IntegrationResult(
            check=check,
            passed=False,
            message=f"No test found for '{check.pattern}'",
            suggestions=(f"Add test_*{check.pattern.lower()}* to tests/",),
        )

    async def _check_used_not_orphan(self, check: IntegrationCheck) -> IntegrationResult:
        """Check if a symbol is used somewhere in the project."""
        symbol = check.pattern

        for py_file in self.project_root.rglob("*.py"):
            if "__pycache__" in str(py_file):
                continue
            if py_file == check.target_file:
                continue

            try:
                content = py_file.read_text()
                if symbol in content:
                    return IntegrationResult(
                        check=check,
                        passed=True,
                        found=str(py_file),
                        message=f"Symbol '{symbol}' used in {py_file}",
                    )
            except OSError:
                continue

        return IntegrationResult(
            check=check,
            passed=False,
            message=f"Symbol '{symbol}' is not used anywhere (orphan)",
            suggestions=(
                f"Import {symbol} in a file that needs it",
                "Or remove if not needed",
            ),
        )

    async def _check_no_stubs(self, check: IntegrationCheck) -> IntegrationResult:
        """Check that a file has no stub implementations."""
        stubs = await self.detect_stubs(check.target_file)

        if not stubs:
            return IntegrationResult(
                check=check,
                passed=True,
                message=f"No stubs found in {check.target_file}",
            )

        stub_list = "; ".join(f"{s.symbol} ({s.stub_type})" for s in stubs[:3])
        return IntegrationResult(
            check=check,
            passed=False,
            found=stub_list,
            message=f"Found {len(stubs)} stub(s) in {check.target_file}",
            suggestions=tuple(f"Implement {s.symbol}" for s in stubs[:3]),
        )

    # =========================================================================
    # Private Helpers
    # =========================================================================

    async def _get_ast(self, file_path: Path) -> ast.Module:
        """Get or cache AST for a file."""
        if file_path not in self._ast_cache:
            content = file_path.read_text()
            self._ast_cache[file_path] = ast.parse(content)
        return self._ast_cache[file_path]

    async def _get_imports(self, file_path: Path) -> list[tuple[str, str | None, int]]:
        """Get or cache imports for a file."""
        if file_path not in self._import_cache:
            try:
                tree = await self._get_ast(file_path)
                visitor = ImportVisitor()
                visitor.visit(tree)
                self._import_cache[file_path] = visitor.imports
            except SyntaxError:
                self._import_cache[file_path] = []
        return self._import_cache[file_path]

    def _integration_type_to_check_type(
        self,
        integration_type: Any,
    ) -> IntegrationCheckType:
        """Map integration type to check type."""
        from sunwell.features.external.integration.types import IntegrationType

        mapping = {
            IntegrationType.IMPORT: IntegrationCheckType.IMPORT_EXISTS,
            IntegrationType.CALL: IntegrationCheckType.CALL_EXISTS,
            IntegrationType.ROUTE: IntegrationCheckType.ROUTE_REGISTERED,
            IntegrationType.CONFIG: IntegrationCheckType.CONFIG_PRESENT,
            # Inheritance requires import
            IntegrationType.INHERIT: IntegrationCheckType.IMPORT_EXISTS,
            # Composition requires call
            IntegrationType.COMPOSE: IntegrationCheckType.CALL_EXISTS,
        }
        return mapping.get(integration_type, IntegrationCheckType.IMPORT_EXISTS)

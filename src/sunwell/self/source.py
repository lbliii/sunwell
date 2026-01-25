"""Source Knowledge for Self-Knowledge Architecture.

RFC-085: Read and understand Sunwell's own source code.

Provides capabilities to:
- Read module source code
- Find symbols (classes, functions, constants)
- Get module structure (imports, classes, functions)
- List all modules
- Search semantically across the codebase
- Generate explanations with citations
- Build architecture diagrams
"""

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sunwell.self.types import (
    ArchitectureDiagram,
    Citation,
    Explanation,
    ModuleStructure,
    SearchResult,
    SourceLocation,
    SymbolInfo,
)


@dataclass(slots=True)
class SourceKnowledge:
    """Understand Sunwell's source code.

    Usage via Self singleton:
        >>> from sunwell.self import Self
        >>> Self.get().source.read_module("sunwell.tools.executor")
        >>> Self.get().source.find_symbol("sunwell.tools.executor", "ToolExecutor")
    """

    root: Path

    def _get_module_path(self, module: str) -> Path:
        """Convert module path to file path."""
        parts = module.replace("sunwell.", "").split(".")
        file_path = self.root / "src" / "sunwell" / "/".join(parts)

        # Try .py extension
        if not file_path.suffix:
            file_path = file_path.with_suffix(".py")

        # Check for __init__.py in directory
        if not file_path.exists():
            dir_path = self.root / "src" / "sunwell" / "/".join(parts)
            if dir_path.is_dir():
                file_path = dir_path / "__init__.py"

        return file_path

    def read_module(self, module: str) -> str:
        """Read source code of a module.

        Args:
            module: Dotted module path (e.g., 'sunwell.tools.executor')

        Returns:
            Source code as string

        Raises:
            FileNotFoundError: If module doesn't exist

        Example:
            >>> Self.get().source.read_module("sunwell.tools.executor")
            '\"\"\"Tool calling support...\"\"\"\\n\\nfrom dataclasses...'
        """
        file_path = self._get_module_path(module)

        if not file_path.exists():
            raise FileNotFoundError(f"Module not found: {module}")

        return file_path.read_text()

    def find_symbol(self, module: str, name: str) -> SymbolInfo:
        """Find a class, function, or constant in a module.

        Args:
            module: Dotted module path
            name: Name of class, function, or constant

        Returns:
            SymbolInfo with source, location, docstring, etc.

        Raises:
            ValueError: If symbol not found

        Example:
            >>> info = Self.get().source.find_symbol("sunwell.tools.executor", "ToolExecutor")
            >>> info.type
            'class'
            >>> info.methods
            ('execute', 'get_audit_log', ...)
        """
        source = self.read_module(module)
        tree = ast.parse(source)

        for node in ast.walk(tree):
            if isinstance(node, ast.ClassDef) and node.name == name:
                methods = tuple(
                    n.name
                    for n in node.body
                    if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                )
                return SymbolInfo(
                    name=name,
                    type="class",
                    module=module,
                    source=ast.get_source_segment(source, node) or "",
                    start_line=node.lineno,
                    end_line=node.end_lineno,
                    docstring=ast.get_docstring(node),
                    methods=methods,
                )
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef) and node.name == name:
                return SymbolInfo(
                    name=name,
                    type="function",
                    module=module,
                    source=ast.get_source_segment(source, node) or "",
                    start_line=node.lineno,
                    end_line=node.end_lineno,
                    docstring=ast.get_docstring(node),
                    is_async=isinstance(node, ast.AsyncFunctionDef),
                )

        raise ValueError(f"Symbol '{name}' not found in {module}")

    def get_module_structure(self, module: str) -> ModuleStructure:
        """Get structure of a module: classes, functions, imports.

        Args:
            module: Dotted module path

        Returns:
            ModuleStructure with classes, functions, imports

        Example:
            >>> structure = Self.get().source.get_module_structure("sunwell.tools.executor")
            >>> structure.classes
            ({'name': 'ToolExecutor', 'methods': [...], ...},)
        """
        source = self.read_module(module)
        tree = ast.parse(source)

        classes: list[dict[str, Any]] = []
        functions: list[dict[str, Any]] = []
        imports: list[str] = []

        for node in ast.iter_child_nodes(tree):
            if isinstance(node, ast.ClassDef):
                methods = [
                    n.name
                    for n in node.body
                    if isinstance(n, ast.FunctionDef | ast.AsyncFunctionDef)
                ]
                classes.append({
                    "name": node.name,
                    "methods": methods,
                    "docstring": ast.get_docstring(node),
                    "line": node.lineno,
                })
            elif isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
                functions.append({
                    "name": node.name,
                    "docstring": ast.get_docstring(node),
                    "line": node.lineno,
                    "is_async": isinstance(node, ast.AsyncFunctionDef),
                })
            elif isinstance(node, ast.Import):
                imports.extend(a.name for a in node.names)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                for alias in node.names:
                    imports.append(f"{mod}.{alias.name}")

        return ModuleStructure(
            module=module,
            classes=tuple(classes),
            functions=tuple(functions),
            imports=tuple(imports),
        )

    def list_modules(self) -> list[str]:
        """List all available Sunwell modules.

        Returns:
            List of dotted module paths, sorted alphabetically

        Example:
            >>> modules = Self.get().source.list_modules()
            >>> 'sunwell.tools.executor' in modules
            True
        """
        sunwell_src = self.root / "src" / "sunwell"
        modules = []

        for path in sunwell_src.rglob("*.py"):
            if "__pycache__" in str(path):
                continue

            relative = path.relative_to(sunwell_src)
            parts = list(relative.parts)

            # Handle __init__.py
            if parts[-1] == "__init__.py":
                parts = parts[:-1]
                if not parts:
                    continue
            else:
                parts[-1] = parts[-1].replace(".py", "")

            module_path = "sunwell." + ".".join(parts)
            modules.append(module_path)

        return sorted(modules)

    def search(self, query: str, limit: int = 10) -> list[SearchResult]:
        """Semantic search across Sunwell's codebase.

        Note: This is a simple keyword-based search. For true semantic search,
        integrate with embedding-based retrieval in a future version.

        Args:
            query: Search query
            limit: Maximum number of results

        Returns:
            List of SearchResult objects

        Example:
            >>> results = Self.get().source.search("how does tool execution work")
            >>> results[0].module
            'sunwell.tools.executor'
        """
        results: list[SearchResult] = []
        query_lower = query.lower()
        query_words = set(query_lower.split())

        for module in self.list_modules():
            try:
                source = self.read_module(module)
            except FileNotFoundError:
                continue

            # Simple relevance scoring based on keyword matches
            source_lower = source.lower()
            score = 0.0

            for word in query_words:
                count = source_lower.count(word)
                if count > 0:
                    score += min(count * 0.1, 1.0)

            if score > 0:
                # Find best matching snippet
                lines = source.split("\n")
                best_line = 0
                best_line_score = 0.0

                for i, line in enumerate(lines):
                    line_lower = line.lower()
                    line_score = sum(1 for word in query_words if word in line_lower)
                    if line_score > best_line_score:
                        best_line_score = line_score
                        best_line = i

                # Get snippet context (3 lines before and after)
                start = max(0, best_line - 3)
                end = min(len(lines), best_line + 4)
                snippet = "\n".join(lines[start:end])

                results.append(SearchResult(
                    module=module,
                    symbol=None,
                    snippet=snippet[:500],
                    score=score,
                    location=SourceLocation(module=module, line=best_line + 1),
                ))

        # Sort by score descending
        results.sort(key=lambda r: r.score, reverse=True)
        return results[:limit]

    def explain(self, topic: str) -> Explanation:
        """Generate an explanation of a Sunwell concept.

        Uses source code + docstrings + type signatures to create
        a coherent explanation with citations.

        Args:
            topic: Topic to explain (e.g., "planning system", "memory architecture")

        Returns:
            Explanation with summary, details, and citations

        Example:
            >>> explanation = Self.get().source.explain("planning system")
            >>> explanation.summary
            "Sunwell's planning system uses..."
        """
        # Search for relevant modules
        search_results = self.search(topic, limit=5)

        if not search_results:
            return Explanation(
                topic=topic,
                summary=f"No information found about '{topic}'",
                details="",
                citations=(),
                related_modules=(),
            )

        # Gather information from top results
        citations: list[Citation] = []
        details_parts: list[str] = []
        related_modules: list[str] = []

        for result in search_results:
            try:
                structure = self.get_module_structure(result.module)
                related_modules.append(result.module)

                # Add classes
                for cls in structure.classes:
                    if cls.get("docstring"):
                        details_parts.append(f"**{cls['name']}**: {cls['docstring']}")
                        citations.append(Citation(
                            module=result.module,
                            line=cls["line"],
                            snippet=cls["docstring"][:200] if cls["docstring"] else None,
                        ))

                # Add functions
                for func in structure.functions:
                    if func.get("docstring") and not func["name"].startswith("_"):
                        details_parts.append(f"**{func['name']}**: {func['docstring']}")
                        citations.append(Citation(
                            module=result.module,
                            line=func["line"],
                            snippet=func["docstring"][:200] if func["docstring"] else None,
                        ))
            except (FileNotFoundError, ValueError):
                continue

        # Build summary from top result
        summary = f"Found {len(related_modules)} modules related to '{topic}'."
        if details_parts:
            summary += f" Key components include: {', '.join(d.split(':')[0].replace('**', '') for d in details_parts[:3])}"

        return Explanation(
            topic=topic,
            summary=summary,
            details="\n\n".join(details_parts[:10]),
            citations=tuple(citations[:10]),
            related_modules=tuple(related_modules),
        )

    def get_architecture(self) -> ArchitectureDiagram:
        """Generate architecture overview.

        Analyzes imports and class relationships to build
        a dependency graph visualization.

        Returns:
            ArchitectureDiagram with Mermaid syntax

        Example:
            >>> diagram = Self.get().source.get_architecture()
            >>> print(diagram.mermaid)
        """
        modules = self.list_modules()
        dependencies: list[tuple[str, str]] = []

        # Analyze dependencies
        sunwell_modules = {m for m in modules if m.startswith("sunwell.")}

        for module in modules:
            try:
                structure = self.get_module_structure(module)
                for imp in structure.imports:
                    if imp.startswith("sunwell."):
                        # Normalize to top-level package
                        imp_parts = imp.split(".")
                        if len(imp_parts) >= 2:
                            target = ".".join(imp_parts[:2])
                            if target in sunwell_modules:
                                source_parts = module.split(".")
                                if len(source_parts) >= 2:
                                    source = ".".join(source_parts[:2])
                                    if source != target:
                                        dependencies.append((source, target))
            except (FileNotFoundError, SyntaxError):
                continue

        # Deduplicate
        dependencies = list(set(dependencies))

        # Build Mermaid diagram
        mermaid_lines = ["graph TD"]
        seen_nodes = set()

        for source, target in dependencies:
            source_id = source.replace(".", "_")
            target_id = target.replace(".", "_")

            if source not in seen_nodes:
                mermaid_lines.append(f"    {source_id}[{source}]")
                seen_nodes.add(source)

            if target not in seen_nodes:
                mermaid_lines.append(f"    {target_id}[{target}]")
                seen_nodes.add(target)

            mermaid_lines.append(f"    {source_id} --> {target_id}")

        # Get top-level packages
        top_level = sorted({m.split(".")[1] for m in modules if "." in m})
        top_modules = [f"sunwell.{p}" for p in top_level]

        return ArchitectureDiagram(
            mermaid="\n".join(mermaid_lines),
            modules=tuple(top_modules),
            dependencies=tuple(dependencies),
        )

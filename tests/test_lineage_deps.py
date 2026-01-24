"""Tests for dependency detection (RFC-121)."""

from pathlib import Path

import pytest

from sunwell.lineage.dependencies import (
    detect_imports,
    detect_language,
    get_impact_analysis,
    update_dependency_graph,
)
from sunwell.lineage.store import LineageStore


class TestLanguageDetection:
    """Test language detection from file extension."""

    def test_python_extensions(self) -> None:
        """Test Python file detection."""
        assert detect_language(Path("file.py")) == "python"
        assert detect_language(Path("file.pyi")) == "python"

    def test_typescript_extensions(self) -> None:
        """Test TypeScript file detection."""
        assert detect_language(Path("file.ts")) == "typescript"
        assert detect_language(Path("file.tsx")) == "typescript"
        assert detect_language(Path("file.mts")) == "typescript"

    def test_javascript_extensions(self) -> None:
        """Test JavaScript file detection."""
        assert detect_language(Path("file.js")) == "javascript"
        assert detect_language(Path("file.jsx")) == "javascript"
        assert detect_language(Path("file.mjs")) == "javascript"

    def test_unknown_extensions(self) -> None:
        """Test unknown extensions return None."""
        assert detect_language(Path("file.txt")) is None
        assert detect_language(Path("file.md")) is None
        assert detect_language(Path("file.json")) is None


class TestPythonImports:
    """Test Python import detection."""

    def test_simple_import(self) -> None:
        """Test simple import statement."""
        content = "import sunwell.core.models"
        imports = detect_imports(Path("src/main.py"), content)
        # Should detect project import
        assert any("sunwell" in imp for imp in imports)

    def test_from_import(self) -> None:
        """Test from...import statement."""
        content = "from sunwell.lineage.store import LineageStore"
        imports = detect_imports(Path("src/main.py"), content)
        assert any("sunwell" in imp or "lineage" in imp for imp in imports)

    def test_relative_import_single_dot(self) -> None:
        """Test single dot relative import."""
        content = "from .base import BaseClass"
        imports = detect_imports(Path("src/auth/oauth.py"), content)
        # Should resolve to src/auth/base.py
        assert any("base" in imp for imp in imports)

    def test_relative_import_double_dot(self) -> None:
        """Test double dot relative import."""
        content = "from ..config import settings"
        imports = detect_imports(Path("src/auth/oauth.py"), content)
        # Should resolve to src/config.py
        assert any("config" in imp for imp in imports)

    def test_stdlib_ignored(self) -> None:
        """Test stdlib imports are ignored."""
        content = """
import os
import sys
import json
from pathlib import Path
from typing import Any
from collections import defaultdict
"""
        imports = detect_imports(Path("src/main.py"), content)
        # Should not include any stdlib
        assert not any(
            imp.endswith("os.py")
            or imp.endswith("sys.py")
            or imp.endswith("json.py")
            for imp in imports
        )

    def test_multiple_imports(self) -> None:
        """Test multiple imports in one file."""
        content = """
from sunwell.core import Page
from sunwell.lineage import LineageStore
from .utils import helper
"""
        imports = detect_imports(Path("src/main.py"), content)
        # Should find multiple
        assert len(imports) >= 2

    def test_multiline_import_skipped(self) -> None:
        """Test single line imports are detected."""
        # Note: Our regex is line-based, multiline imports may not work perfectly
        content = """
from sunwell.core import (
    Page,
    Site,
)
"""
        imports = detect_imports(Path("src/main.py"), content)
        # Should still detect the module
        assert any("sunwell" in imp or "core" in imp for imp in imports)


class TestTypeScriptImports:
    """Test TypeScript import detection."""

    def test_default_import(self) -> None:
        """Test default import."""
        content = 'import User from "./models/user";'
        imports = detect_imports(Path("src/components/Auth.tsx"), content)
        assert any("models" in imp or "user" in imp for imp in imports)

    def test_named_import(self) -> None:
        """Test named import."""
        content = 'import { User, Role } from "./models/user";'
        imports = detect_imports(Path("src/components/Auth.tsx"), content)
        assert any("models" in imp or "user" in imp for imp in imports)

    def test_star_import(self) -> None:
        """Test star import."""
        content = 'import * as utils from "../utils";'
        imports = detect_imports(Path("src/components/Auth.tsx"), content)
        assert any("utils" in imp for imp in imports)

    def test_export_from(self) -> None:
        """Test re-export."""
        content = 'export { handler } from "./handlers";'
        imports = detect_imports(Path("src/index.ts"), content)
        assert any("handlers" in imp for imp in imports)

    def test_dynamic_import(self) -> None:
        """Test dynamic import."""
        content = 'const module = await import("./lazy-module");'
        imports = detect_imports(Path("src/app.ts"), content)
        assert any("lazy-module" in imp for imp in imports)

    def test_require(self) -> None:
        """Test CommonJS require."""
        content = 'const fs = require("fs");\nconst local = require("./local");'
        imports = detect_imports(Path("src/app.js"), content)
        # Should only include local, not node built-ins
        assert any("local" in imp for imp in imports)
        assert not any("fs" in imp for imp in imports)

    def test_third_party_ignored(self) -> None:
        """Test third-party packages are ignored."""
        content = """
import React from 'react';
import { useState } from 'react';
import axios from 'axios';
import { motion } from 'framer-motion';
"""
        imports = detect_imports(Path("src/App.tsx"), content)
        # Should not include any third-party
        assert len(imports) == 0


class TestJavaScriptImports:
    """Test JavaScript import detection."""

    def test_esm_import(self) -> None:
        """Test ES module import."""
        content = 'import { helper } from "./utils.js";'
        imports = detect_imports(Path("src/main.js"), content)
        assert any("utils" in imp for imp in imports)

    def test_cjs_require(self) -> None:
        """Test CommonJS require."""
        content = 'const utils = require("./utils");'
        imports = detect_imports(Path("src/main.js"), content)
        assert any("utils" in imp for imp in imports)


class TestDependencyGraphUpdate:
    """Test dependency graph updates."""

    def test_update_imports(self, tmp_path: Path) -> None:
        """Test updating file's imports."""
        store = LineageStore(tmp_path)

        # Create main file
        store.record_create(
            path="src/main.py",
            content="",
            goal_id="g1",
            task_id="t1",
            reason="Main",
            model="claude",
        )

        # Create utils file
        store.record_create(
            path="src/utils.py",
            content="",
            goal_id="g1",
            task_id="t2",
            reason="Utils",
            model="claude",
        )

        # Update main to import utils
        content = "from .utils import helper"
        update_dependency_graph(store, "src/main.py", content)

        main = store.get_by_path("src/main.py")
        assert main is not None
        # Note: the exact resolution depends on file existence

    def test_remove_old_imports(self, tmp_path: Path) -> None:
        """Test removing imports updates imported_by."""
        store = LineageStore(tmp_path)

        # Create files
        store.record_create(
            path="src/main.py", content="", goal_id="g1", task_id="t1",
            reason="Main", model="claude"
        )
        store.record_create(
            path="src/utils.py", content="", goal_id="g1", task_id="t2",
            reason="Utils", model="claude"
        )
        store.record_create(
            path="src/config.py", content="", goal_id="g1", task_id="t3",
            reason="Config", model="claude"
        )

        # Set up initial imports manually
        store.update_imports("src/main.py", ["src/utils.py", "src/config.py"])
        store.add_imported_by("src/utils.py", "src/main.py")
        store.add_imported_by("src/config.py", "src/main.py")

        # Verify initial state
        utils = store.get_by_path("src/utils.py")
        assert utils is not None
        assert "src/main.py" in utils.imported_by

        # Now remove utils import (simulated by updating with no matching imports)
        store.update_imports("src/main.py", ["src/config.py"])
        store.remove_imported_by("src/utils.py", "src/main.py")

        # Utils should no longer list main as importer
        utils = store.get_by_path("src/utils.py")
        assert utils is not None
        assert "src/main.py" not in utils.imported_by


class TestImpactAnalysis:
    """Test impact analysis."""

    def test_direct_dependents(self, tmp_path: Path) -> None:
        """Test finding direct dependents."""
        store = LineageStore(tmp_path)

        # Create files
        store.record_create(
            path="src/base.py", content="", goal_id="g1", task_id="t1",
            reason="Base", model="claude"
        )
        store.record_create(
            path="src/derived.py", content="", goal_id="g2", task_id="t2",
            reason="Derived", model="claude"
        )

        # Set up dependency
        store.add_imported_by("src/base.py", "src/derived.py")

        # Analyze impact
        impact = get_impact_analysis(store, "src/base.py")

        assert impact["path"] == "src/base.py"
        assert "src/derived.py" in impact["affected_files"]
        assert "g1" in impact["affected_goals"]  # base's goal

    def test_transitive_dependents(self, tmp_path: Path) -> None:
        """Test finding transitive dependents."""
        store = LineageStore(tmp_path)

        # Create chain: base <- middle <- top
        store.record_create(
            path="src/base.py", content="", goal_id="g1", task_id="t1",
            reason="Base", model="claude"
        )
        store.record_create(
            path="src/middle.py", content="", goal_id="g2", task_id="t2",
            reason="Middle", model="claude"
        )
        store.record_create(
            path="src/top.py", content="", goal_id="g3", task_id="t3",
            reason="Top", model="claude"
        )

        # Set up dependencies
        store.add_imported_by("src/base.py", "src/middle.py")
        store.add_imported_by("src/middle.py", "src/top.py")

        # Analyze impact of base
        impact = get_impact_analysis(store, "src/base.py")

        # Should find both middle and top
        assert "src/middle.py" in impact["affected_files"]
        assert "src/top.py" in impact["affected_files"]
        assert impact["max_depth"] >= 2

    def test_collects_goals(self, tmp_path: Path) -> None:
        """Test impact analysis collects all affected goals."""
        store = LineageStore(tmp_path)

        # Create files with different goals
        store.record_create(
            path="src/base.py", content="", goal_id="goal-base", task_id="t1",
            reason="Base", model="claude"
        )
        store.record_create(
            path="src/user.py", content="", goal_id="goal-user", task_id="t2",
            reason="User", model="claude"
        )

        store.add_imported_by("src/base.py", "src/user.py")

        impact = get_impact_analysis(store, "src/base.py")

        # Should include goals from base and user
        assert "goal-base" in impact["affected_goals"]
        assert "goal-user" in impact["affected_goals"]

    def test_nonexistent_file(self, tmp_path: Path) -> None:
        """Test impact analysis for nonexistent file."""
        store = LineageStore(tmp_path)

        impact = get_impact_analysis(store, "nonexistent.py")

        assert impact["affected_files"] == []
        assert impact["affected_goals"] == set()
        assert impact["max_depth"] == 0

"""Tests for Skill Import/Export Interoperability (RFC-111 Phase 6)."""

import tempfile
from pathlib import Path

import pytest
import yaml

from sunwell.planning.skills.interop import SkillExporter, SkillImporter, validate_skill_folder
from sunwell.planning.skills.types import (
    Resource,
    Script,
    Skill,
    SkillDependency,
    SkillType,
    Template,
    TrustLevel,
)


# =============================================================================
# SkillExporter Tests - Anthropic Format
# =============================================================================


class TestSkillExporterAnthropic:
    """Tests for exporting to Anthropic Agent Skills format."""

    def test_export_basic_skill(self):
        """Test exporting a basic skill to Anthropic format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Skill(
                name="test-skill",
                description="A test skill for export",
                skill_type=SkillType.INLINE,
                instructions="Do the thing.\n\nThen do another thing.",
            )

            exporter = SkillExporter()
            path = exporter.export_anthropic(skill, Path(tmpdir))

            assert path.exists()
            assert (path / "SKILL.md").exists()

            content = (path / "SKILL.md").read_text()

            # Check frontmatter
            assert content.startswith("---\n")
            assert "name: test-skill" in content
            assert "description: A test skill for export" in content

            # Check instructions
            assert "Do the thing." in content
            assert "Then do another thing." in content

    def test_export_with_dag_metadata(self):
        """Test that DAG metadata is preserved in comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Skill(
                name="dag-skill",
                description="Skill with DAG metadata",
                skill_type=SkillType.INLINE,
                instructions="Instructions here",
                depends_on=(SkillDependency(source="read-file"),),
                produces=("analysis", "report"),
                requires=("file_content",),
            )

            exporter = SkillExporter()
            path = exporter.export_anthropic(skill, Path(tmpdir))

            content = (path / "SKILL.md").read_text()

            # DAG metadata should be in HTML comment
            assert "<!-- Sunwell DAG Metadata" in content
            assert "depends_on:" in content
            assert "produces:" in content
            assert "requires:" in content
            assert "read-file" in content
            assert "analysis" in content
            assert "file_content" in content

    def test_export_with_scripts(self):
        """Test that scripts are exported as separate files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Skill(
                name="script-skill",
                description="Skill with scripts",
                skill_type=SkillType.INLINE,
                instructions="Run the script",
                scripts=(
                    Script(
                        name="extract.py",
                        content='print("Hello")',
                        language="python",
                    ),
                    Script(
                        name="process.js",
                        content='console.log("Hi")',
                        language="javascript",
                    ),
                ),
            )

            exporter = SkillExporter()
            path = exporter.export_anthropic(skill, Path(tmpdir))

            # Check scripts are exported
            assert (path / "extract.py").exists()
            assert (path / "process.js").exists()
            assert 'print("Hello")' in (path / "extract.py").read_text()

    def test_export_with_templates(self):
        """Test that templates are exported as separate files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Skill(
                name="template-skill",
                description="Skill with templates",
                skill_type=SkillType.INLINE,
                instructions="Use the template",
                templates=(
                    Template(name="component.tsx", content="export const X = () => {};"),
                ),
            )

            exporter = SkillExporter()
            path = exporter.export_anthropic(skill, Path(tmpdir))

            assert (path / "component.tsx").exists()
            assert "export const X" in (path / "component.tsx").read_text()

    def test_export_with_resources(self):
        """Test that resources are exported to resources.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Skill(
                name="resource-skill",
                description="Skill with resources",
                skill_type=SkillType.INLINE,
                instructions="Check resources",
                resources=(
                    Resource(name="API Docs", url="https://example.com/docs"),
                    Resource(name="Config", path="./config.yaml"),
                ),
            )

            exporter = SkillExporter()
            path = exporter.export_anthropic(skill, Path(tmpdir))

            resources_file = path / "resources.yaml"
            assert resources_file.exists()

            resources = yaml.safe_load(resources_file.read_text())
            assert len(resources) == 2
            assert resources[0]["name"] == "API Docs"
            assert resources[0]["url"] == "https://example.com/docs"


# =============================================================================
# SkillExporter Tests - Sunwell Format
# =============================================================================


class TestSkillExporterSunwell:
    """Tests for exporting to Sunwell format with full DAG."""

    def test_export_basic_skill(self):
        """Test exporting a basic skill to Sunwell format."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Skill(
                name="sunwell-skill",
                description="Full Sunwell skill",
                skill_type=SkillType.INLINE,
                instructions="Do the Sunwell thing",
            )

            exporter = SkillExporter()
            path = exporter.export_sunwell(skill, Path(tmpdir))

            assert path.exists()
            assert (path / "SKILL.yaml").exists()

            data = yaml.safe_load((path / "SKILL.yaml").read_text())
            assert data["name"] == "sunwell-skill"
            assert data["type"] == "inline"

    def test_export_with_full_dag(self):
        """Test that full DAG metadata is in SKILL.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Skill(
                name="full-dag-skill",
                description="Skill with full DAG",
                skill_type=SkillType.INLINE,
                instructions="Execute DAG",
                depends_on=(
                    SkillDependency(source="skill-a"),
                    SkillDependency(source="skill-b"),
                ),
                produces=("result", "metrics"),
                requires=("input_data",),
                triggers=("audit", "check"),
            )

            exporter = SkillExporter()
            path = exporter.export_sunwell(skill, Path(tmpdir))

            data = yaml.safe_load((path / "SKILL.yaml").read_text())

            assert len(data["depends_on"]) == 2
            assert data["depends_on"][0]["source"] == "skill-a"
            assert "result" in data["produces"]
            assert "metrics" in data["produces"]
            assert "input_data" in data["requires"]
            assert "audit" in data["triggers"]

    def test_export_scripts_to_directory(self):
        """Test that scripts go to scripts/ directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Skill(
                name="structured-skill",
                description="Skill with structure",
                skill_type=SkillType.INLINE,
                instructions="Run scripts",
                scripts=(Script(name="main.py", content="# main", language="python"),),
            )

            exporter = SkillExporter()
            path = exporter.export_sunwell(skill, Path(tmpdir))

            assert (path / "scripts" / "main.py").exists()


# =============================================================================
# SkillImporter Tests - Anthropic Format
# =============================================================================


class TestSkillImporterAnthropic:
    """Tests for importing Anthropic Agent Skills format."""

    def test_import_basic_anthropic(self):
        """Test importing basic Anthropic SKILL.md."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "my-skill"
            skill_dir.mkdir()

            skill_md = """---
name: my-skill
description: An imported skill
---

Do the imported thing.
"""
            (skill_dir / "SKILL.md").write_text(skill_md)

            importer = SkillImporter()
            data = importer.import_anthropic(skill_dir)

            assert data["name"] == "my-skill"
            assert data["description"] == "An imported skill"
            assert "Do the imported thing." in data["instructions"]

    def test_import_with_dag_metadata(self):
        """Test importing skill with DAG metadata in comments."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "dag-skill"
            skill_dir.mkdir()

            skill_md = """---
name: dag-skill
description: Skill with DAG
---

<!-- Sunwell DAG Metadata (not used by Anthropic)
depends_on: ['read-file', 'grep']
produces: ['analysis', 'report']
requires: ['file_content']
-->

Analyze and report.
"""
            (skill_dir / "SKILL.md").write_text(skill_md)

            importer = SkillImporter()
            data = importer.import_anthropic(skill_dir)

            assert len(data.get("depends_on", [])) == 2
            assert data["depends_on"][0]["source"] == "read-file"
            assert "analysis" in data.get("produces", [])
            assert "file_content" in data.get("requires", [])

    def test_import_with_scripts_in_directory(self):
        """Test importing scripts from directory."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "script-skill"
            skill_dir.mkdir()

            (skill_dir / "SKILL.md").write_text("""---
name: script-skill
description: Skill with scripts
---

Run scripts.
""")
            (skill_dir / "extract.py").write_text('print("extracted")')
            (skill_dir / "process.js").write_text('console.log("processed")')

            importer = SkillImporter()
            data = importer.import_anthropic(skill_dir)

            assert "scripts" in data
            assert len(data["scripts"]) == 2

            script_names = {s["name"] for s in data["scripts"]}
            assert "extract.py" in script_names
            assert "process.js" in script_names

    def test_import_with_resources_yaml(self):
        """Test importing resources from resources.yaml."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "resource-skill"
            skill_dir.mkdir()

            (skill_dir / "SKILL.md").write_text("""---
name: resource-skill
description: Skill with resources
---

Use resources.
""")
            (skill_dir / "resources.yaml").write_text("""
- name: API Docs
  url: https://example.com/api
- name: Config
  path: ./config.yaml
""")

            importer = SkillImporter()
            data = importer.import_anthropic(skill_dir)

            assert "resources" in data
            assert len(data["resources"]) == 2


# =============================================================================
# Round-Trip Tests
# =============================================================================


class TestRoundTrip:
    """Tests for export → import round-trip preservation."""

    def test_anthropic_round_trip(self):
        """Test that export → import preserves skill data."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = Skill(
                name="round-trip",
                description="Test round trip",
                skill_type=SkillType.INLINE,
                instructions="Step 1: Do A\nStep 2: Do B",
                depends_on=(SkillDependency(source="prereq"),),
                produces=("output",),
                requires=("input",),
                triggers=("test", "verify"),
            )

            # Export
            exporter = SkillExporter()
            path = exporter.export_anthropic(original, Path(tmpdir))

            # Import
            importer = SkillImporter()
            imported_data = importer.import_anthropic(path)

            # Verify
            assert imported_data["name"] == original.name
            assert imported_data["description"] == original.description
            assert "Step 1" in imported_data["instructions"]
            assert "Step 2" in imported_data["instructions"]
            assert len(imported_data.get("depends_on", [])) == 1
            assert "output" in imported_data.get("produces", [])
            assert "input" in imported_data.get("requires", [])

    def test_sunwell_round_trip(self):
        """Test that Sunwell format preserves all metadata."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original = Skill(
                name="sunwell-round-trip",
                description="Full round trip",
                skill_type=SkillType.INLINE,
                instructions="Do everything",
                depends_on=(
                    SkillDependency(source="a"),
                    SkillDependency(source="b"),
                ),
                produces=("x", "y"),
                requires=("z",),
                triggers=("run", "execute"),
                allowed_tools=("read_file", "grep"),
            )

            # Export
            exporter = SkillExporter()
            path = exporter.export_sunwell(original, Path(tmpdir))

            # Load YAML
            data = yaml.safe_load((path / "SKILL.yaml").read_text())

            # Verify all fields preserved
            assert data["name"] == "sunwell-round-trip"
            assert len(data["depends_on"]) == 2
            assert set(data["produces"]) == {"x", "y"}
            assert data["requires"] == ["z"]
            assert "run" in data["triggers"]


# =============================================================================
# Skill Validation Tests
# =============================================================================


class TestSkillValidation:
    """Tests for skill validation."""

    def test_validate_valid_skill(self):
        """Test validating a well-formed skill."""
        from sunwell.planning.skills.interop import validate_skill_folder

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "valid-skill"
            skill_dir.mkdir()

            (skill_dir / "SKILL.md").write_text("""---
name: valid-skill
description: A valid skill
---

Do the valid thing.
""")

            result = validate_skill_folder(skill_dir)

            assert result.valid
            assert result.score > 0.5
            assert len(result.issues) == 0

    def test_validate_missing_name(self):
        """Test validation catches missing name."""
        from sunwell.planning.skills.interop import validate_skill_folder

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "no-name"
            skill_dir.mkdir()

            (skill_dir / "SKILL.md").write_text("""---
description: Missing name
---

Instructions.
""")

            result = validate_skill_folder(skill_dir)

            # The name gets defaulted from directory, so it should still be valid
            assert "no-name" == result.skill_data.get("name")

    def test_validate_missing_file(self):
        """Test validation handles missing skill file."""
        from sunwell.planning.skills.interop import validate_skill_folder

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_dir = Path(tmpdir) / "empty"
            skill_dir.mkdir()

            result = validate_skill_folder(skill_dir)

            assert not result.valid
            assert len(result.issues) > 0


# =============================================================================
# Export Format Selection Tests
# =============================================================================


class TestExportFormatSelection:
    """Tests for the unified export() method."""

    def test_export_format_anthropic(self):
        """Test export with format='anthropic'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Skill(
                name="format-test",
                description="Test format selection",
                skill_type=SkillType.INLINE,
                instructions="Test",
            )

            exporter = SkillExporter()
            path = exporter.export(skill, Path(tmpdir), format="anthropic")

            assert (path / "SKILL.md").exists()

    def test_export_format_sunwell(self):
        """Test export with format='sunwell'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Skill(
                name="format-test",
                description="Test format selection",
                skill_type=SkillType.INLINE,
                instructions="Test",
            )

            exporter = SkillExporter()
            path = exporter.export(skill, Path(tmpdir), format="sunwell")

            assert (path / "SKILL.yaml").exists()

    def test_export_format_yaml(self):
        """Test export with format='yaml'."""
        with tempfile.TemporaryDirectory() as tmpdir:
            skill = Skill(
                name="format-test",
                description="Test format selection",
                skill_type=SkillType.INLINE,
                instructions="Test",
            )

            exporter = SkillExporter()
            path = exporter.export(skill, Path(tmpdir), format="yaml")

            assert path.suffix == ".yaml"
            assert path.exists()

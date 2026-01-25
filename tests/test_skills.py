"""Tests for the skills module (RFC-011, RFC-094)."""

import time
from collections import OrderedDict

import pytest
from pathlib import Path

from sunwell.skills.types import (
    Skill,
    SkillType,
    TrustLevel,
    Script,
    Template,
    Resource,
    SkillValidation,
    SkillRetryPolicy,
    validate_skill_name,
)
from sunwell.skills.cache import SkillCache, SkillCacheKey, SkillCacheEntry
from sunwell.skills.sandbox import ScriptSandbox, expand_template_variables
from sunwell.schema.loader import LensLoader


class TestSkillTypes:
    """Tests for skill type definitions."""

    def test_validate_skill_name_valid(self):
        """Valid skill names should pass."""
        validate_skill_name("create-api-docs")
        validate_skill_name("my-skill")
        validate_skill_name("a")
        validate_skill_name("skill123")

    def test_validate_skill_name_invalid(self):
        """Invalid skill names should raise ValueError."""
        with pytest.raises(ValueError, match="starting with a letter"):
            validate_skill_name("123-skill")

        with pytest.raises(ValueError, match="start/end with hyphen"):
            validate_skill_name("-invalid")

        with pytest.raises(ValueError, match="start/end with hyphen"):
            validate_skill_name("invalid-")

        with pytest.raises(ValueError, match="consecutive hyphens"):
            validate_skill_name("invalid--name")

        with pytest.raises(ValueError, match="lowercase"):
            validate_skill_name("InvalidName")

    def test_skill_creation_inline(self):
        """Create an inline skill."""
        skill = Skill(
            name="test-skill",
            description="A test skill",
            skill_type=SkillType.INLINE,
            instructions="Do something",
        )
        assert skill.name == "test-skill"
        assert skill.skill_type == SkillType.INLINE
        assert skill.trust == TrustLevel.SANDBOXED  # default

    def test_skill_creation_reference(self):
        """Create a reference skill."""
        skill = Skill(
            name="external-skill",
            description="An external skill",
            skill_type=SkillType.REFERENCE,
            source="fount://my-skill@1.0",
        )
        assert skill.skill_type == SkillType.REFERENCE
        assert skill.source == "fount://my-skill@1.0"

    def test_skill_creation_local(self):
        """Create a local skill."""
        skill = Skill(
            name="local-skill",
            description="A local skill",
            skill_type=SkillType.LOCAL,
            path="./skills/my-skill/",
        )
        assert skill.skill_type == SkillType.LOCAL
        assert skill.path == "./skills/my-skill/"

    def test_skill_inline_requires_instructions(self):
        """Inline skills require instructions."""
        with pytest.raises(ValueError, match="requires instructions"):
            Skill(
                name="bad-skill",
                description="Missing instructions",
                skill_type=SkillType.INLINE,
            )

    def test_skill_reference_requires_source(self):
        """Reference skills require source."""
        with pytest.raises(ValueError, match="requires source"):
            Skill(
                name="bad-skill",
                description="Missing source",
                skill_type=SkillType.REFERENCE,
            )

    def test_skill_local_requires_path(self):
        """Local skills require path."""
        with pytest.raises(ValueError, match="requires path"):
            Skill(
                name="bad-skill",
                description="Missing path",
                skill_type=SkillType.LOCAL,
            )

    def test_script_creation(self):
        """Create a script."""
        script = Script(
            name="extract.py",
            content="print('hello')",
            language="python",
            description="A test script",
        )
        assert script.name == "extract.py"
        assert script.language == "python"

    def test_template_creation(self):
        """Create a template."""
        template = Template(
            name="readme.md",
            content="# ${Name}\n\n${description}",
        )
        assert template.name == "readme.md"
        assert "${Name}" in template.content

    def test_resource_url(self):
        """Create a URL resource."""
        resource = Resource(
            name="Docs",
            url="https://example.com/docs",
        )
        assert resource.url is not None
        assert resource.path is None

    def test_resource_path(self):
        """Create a path resource."""
        resource = Resource(
            name="Local Docs",
            path="./docs/guide.md",
        )
        assert resource.path is not None
        assert resource.url is None

    def test_resource_both_raises(self):
        """Resource cannot have both url and path."""
        with pytest.raises(ValueError, match="both url and path"):
            Resource(
                name="Invalid",
                url="https://example.com",
                path="./local",
            )

    def test_resource_neither_raises(self):
        """Resource must have either url or path."""
        with pytest.raises(ValueError, match="either url or path"):
            Resource(name="Invalid")

    def test_skill_validation(self):
        """Create skill validation config."""
        validation = SkillValidation(
            validators=("no_fluff", "evidence"),
            personas=("novice",),
            min_confidence=0.8,
        )
        assert len(validation.validators) == 2
        assert validation.min_confidence == 0.8

    def test_skill_validation_invalid_confidence(self):
        """Invalid confidence raises."""
        with pytest.raises(ValueError, match="between 0.0 and 1.0"):
            SkillValidation(min_confidence=1.5)

    def test_skill_retry_policy(self):
        """Create skill retry policy."""
        policy = SkillRetryPolicy(
            max_attempts=5,
            backoff_ms=(100, 200, 400),
            retry_on=("timeout",),
        )
        assert policy.max_attempts == 5
        assert len(policy.backoff_ms) == 3

    def test_skill_retry_invalid_attempts(self):
        """Invalid max_attempts raises."""
        with pytest.raises(ValueError, match="between 1 and 10"):
            SkillRetryPolicy(max_attempts=15)


class TestSkillSandbox:
    """Tests for script sandbox."""

    def test_sandbox_can_execute(self):
        """Test sandbox execution permission."""
        sandbox_full = ScriptSandbox(trust=TrustLevel.FULL)
        sandbox_sandboxed = ScriptSandbox(trust=TrustLevel.SANDBOXED)
        sandbox_none = ScriptSandbox(trust=TrustLevel.NONE)

        assert sandbox_full.can_execute() is True
        assert sandbox_sandboxed.can_execute() is True
        assert sandbox_none.can_execute() is False

    def test_expand_template_variables(self):
        """Test template variable expansion."""
        content = "# ${Name}\n\nBy ${Author}"
        result = expand_template_variables(
            content,
            {"Name": "MyProject", "Author": "John"},
        )
        assert "# MyProject" in result
        assert "By John" in result

    def test_expand_template_builtins(self):
        """Test built-in variable expansion."""
        content = "Date: ${DATE}"
        result = expand_template_variables(content, {})
        assert "Date: 2" in result  # Starts with year


class TestLensLoaderSkills:
    """Tests for loading lenses with skills."""

    def test_load_tech_writer_skills(self):
        """Load tech-writer lens and check skills (includes core-skills)."""
        loader = LensLoader()
        lens = loader.load(Path("lenses/tech-writer.lens"))

        # RFC-070: 9 validation + 5 creation + 5 transformation + 11 utility + 3 lens-specific = 33 total
        assert len(lens.skills) == 33

        # Check lens-specific skill (has custom script)
        skill = lens.get_skill("create-api-docs")
        assert skill is not None
        assert skill.skill_type == SkillType.INLINE
        assert skill.trust == TrustLevel.SANDBOXED
        assert len(skill.scripts) == 1
        assert skill.scripts[0].name == "extract_api.py"
        
        # Check that RFC-070 DORI skills are loaded
        assert lens.get_skill("audit-documentation") is not None
        assert lens.get_skill("polish-documentation") is not None

    def test_load_skill_with_templates(self):
        """Load skill with templates."""
        loader = LensLoader()
        lens = loader.load(Path("lenses/tech-writer.lens"))

        skill = lens.get_skill("create-readme")
        assert skill is not None
        assert len(skill.templates) == 1
        assert skill.templates[0].name == "readme-template.md"

    def test_load_skill_validation(self):
        """Load skill validation config."""
        loader = LensLoader()
        lens = loader.load(Path("lenses/tech-writer.lens"))

        skill = lens.get_skill("create-api-docs")
        assert skill is not None
        assert "evidence_required" in skill.validate_with.validators
        assert skill.validate_with.min_confidence == 0.8

    def test_load_skill_retry_policy(self):
        """Load skill retry policy."""
        loader = LensLoader()
        lens = loader.load(Path("lenses/tech-writer.lens"))

        assert lens.skill_retry is not None
        assert lens.skill_retry.max_attempts == 3
        assert "timeout" in lens.skill_retry.retry_on

    def test_get_skill_hyphen_underscore(self):
        """Get skill works with both hyphens and underscores."""
        loader = LensLoader()
        lens = loader.load(Path("lenses/tech-writer.lens"))

        # Both should work
        skill1 = lens.get_skill("create-api-docs")
        skill2 = lens.get_skill("create_api_docs")
        assert skill1 is not None
        assert skill2 is not None
        assert skill1.name == skill2.name

    def test_lens_summary_includes_skills(self):
        """Lens summary includes skill count."""
        loader = LensLoader()
        lens = loader.load(Path("lenses/tech-writer.lens"))

        summary = lens.summary()
        # RFC-070: 9 validation + 5 creation + 5 transformation + 11 utility + 3 lens-specific = 33
        assert "Skills: 33" in summary


class TestSkillPrompt:
    """Tests for skill prompt generation."""

    def test_skill_to_prompt_fragment(self):
        """Test skill prompt fragment generation."""
        skill = Skill(
            name="test-skill",
            description="A test skill for testing",
            skill_type=SkillType.INLINE,
            instructions="Do the thing",
            templates=(
                Template(name="test.txt", content="Hello ${name}"),
            ),
        )

        fragment = skill.to_prompt_fragment()
        assert "### Skill: test-skill" in fragment
        assert "A test skill for testing" in fragment
        assert "Do the thing" in fragment
        assert "test.txt" in fragment


# RFC-110: TestSkillAwareClassifier removed (SkillAwareClassifier was in deleted executor.py)


# =============================================================================
# RFC-011 Phase 4: Interop Tests
# =============================================================================


class TestSkillExporter:
    """Tests for skill export functionality."""

    def test_export_skill_md(self):
        """Export skill to SKILL.md format."""
        from sunwell.skills.interop import SkillExporter
        
        skill = Skill(
            name="test-skill",
            description="A test skill for unit tests",
            skill_type=SkillType.INLINE,
            instructions="Do the test thing.\n\n1. Step one\n2. Step two",
        )
        
        exporter = SkillExporter()
        md = exporter.export_skill_md(skill)
        
        assert "# test-skill" in md
        assert "## Description" in md
        assert "A test skill for unit tests" in md
        assert "## Instructions" in md
        assert "Step one" in md

    def test_export_skill_with_scripts(self):
        """Export skill with embedded scripts."""
        from sunwell.skills.interop import SkillExporter
        
        skill = Skill(
            name="scripted-skill",
            description="Skill with scripts",
            skill_type=SkillType.INLINE,
            instructions="Run the script",
            scripts=(
                Script(
                    name="test.py",
                    language="python",
                    content="print('hello')",
                    description="Test script",
                ),
            ),
        )
        
        exporter = SkillExporter()
        md = exporter.export_skill_md(skill)
        
        assert "## Scripts" in md
        assert "### test.py" in md
        assert "```python" in md
        assert "print('hello')" in md

    def test_export_skill_with_templates(self):
        """Export skill with templates."""
        from sunwell.skills.interop import SkillExporter
        
        skill = Skill(
            name="template-skill",
            description="Skill with templates",
            skill_type=SkillType.INLINE,
            instructions="Use the template",
            templates=(
                Template(name="component.tsx", content="export const ${Name} = () => {};"),
            ),
        )
        
        exporter = SkillExporter()
        md = exporter.export_skill_md(skill)
        
        assert "## Templates" in md
        assert "### component.tsx" in md
        assert "```typescript" in md  # Auto-detected from .tsx
        assert "${Name}" in md

    def test_export_to_yaml(self):
        """Export skill to YAML format."""
        from sunwell.skills.interop import SkillExporter
        import yaml
        
        skill = Skill(
            name="yaml-skill",
            description="Test YAML export",
            skill_type=SkillType.INLINE,
            instructions="Do things",
        )
        
        exporter = SkillExporter()
        yaml_str = exporter._skill_to_yaml(skill)
        data = yaml.safe_load(yaml_str)
        
        assert data["skill"]["name"] == "yaml-skill"
        assert data["skill"]["description"] == "Test YAML export"
        assert data["skill"]["type"] == "inline"

    def test_export_lens_skills(self, tmp_path):
        """Export all skills from a lens to files."""
        from sunwell.skills.interop import SkillExporter
        
        loader = LensLoader()
        lens = loader.load(Path("lenses/tech-writer.lens"))
        
        exporter = SkillExporter()
        created = exporter.export_lens_skills(lens, tmp_path, format="skill-md")
        
        # Should create skill folders
        assert len(created) == len(lens.skills)
        assert all(p.exists() for p in created)
        assert all(p.name == "SKILL.md" for p in created)


class TestSkillImporter:
    """Tests for skill import functionality."""

    def test_import_skill_md(self, tmp_path):
        """Import skill from SKILL.md file."""
        from sunwell.skills.interop import SkillImporter
        
        # Create a test SKILL.md
        skill_dir = tmp_path / "test-skill"
        skill_dir.mkdir()
        skill_file = skill_dir / "SKILL.md"
        skill_file.write_text("""# Test Skill

## Description
A skill for testing imports.

## Instructions
1. Do the first thing
2. Do the second thing

## Scripts
### run.py
Test script description.

**Language:** python
```python
print("hello from imported skill")
```
""")
        
        importer = SkillImporter()
        data = importer.import_skill_md(skill_dir)
        
        assert data["name"] == "test-skill"
        assert "testing imports" in data["description"]
        assert "first thing" in data["instructions"]
        assert len(data["scripts"]) == 1
        assert data["scripts"][0]["name"] == "run.py"

    def test_import_skill_yaml(self, tmp_path):
        """Import skill from YAML file."""
        from sunwell.skills.interop import SkillImporter
        import yaml
        
        skill_file = tmp_path / "skill.yaml"
        skill_file.write_text(yaml.dump({
            "skill": {
                "name": "yaml-import-test",
                "description": "Test YAML import",
                "type": "inline",
                "instructions": "Do YAML things",
            }
        }))
        
        importer = SkillImporter()
        data = importer.import_skill_yaml(skill_file)
        
        assert data["name"] == "yaml-import-test"
        assert data["description"] == "Test YAML import"

    def test_import_skill_folder_prefers_md(self, tmp_path):
        """Folder with both SKILL.md and skill.yaml prefers SKILL.md."""
        from sunwell.skills.interop import SkillImporter
        import yaml
        
        skill_dir = tmp_path / "hybrid-skill"
        skill_dir.mkdir()
        
        # Create both formats
        (skill_dir / "SKILL.md").write_text("""# MD Skill

## Description
From markdown file.
""")
        (skill_dir / "skill.yaml").write_text(yaml.dump({
            "skill": {
                "name": "yaml-skill",
                "description": "From YAML file",
            }
        }))
        
        importer = SkillImporter()
        data = importer.import_skill_folder(skill_dir)
        
        # Should prefer SKILL.md
        assert data["name"] == "md-skill"
        assert "markdown file" in data["description"]


class TestSkillValidation:
    """Tests for skill validation."""

    def test_validate_valid_skill(self, tmp_path):
        """Valid skill passes validation."""
        from sunwell.skills.interop import validate_skill_folder
        
        skill_dir = tmp_path / "valid-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""# Valid Skill

## Description
A properly formatted skill.

## Instructions
1. Do the thing
2. Check the result
""")
        
        result = validate_skill_folder(skill_dir)
        
        assert result.valid
        assert result.score > 0.7
        assert len(result.issues) == 0

    def test_validate_missing_description(self, tmp_path):
        """Skill missing description fails validation."""
        from sunwell.skills.interop import validate_skill_folder
        
        skill_dir = tmp_path / "bad-skill"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""# Bad Skill

## Instructions
Do something without saying what.
""")
        
        result = validate_skill_folder(skill_dir)
        
        # Missing description is an issue
        assert not result.valid or "description" in str(result.issues).lower()

    def test_validate_with_lens(self, tmp_path):
        """Validate skill against lens validators."""
        from sunwell.skills.interop import validate_skill_folder
        
        skill_dir = tmp_path / "lens-validated"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text("""# Lens Validated Skill

## Description
A skill to validate against a lens.

## Instructions
Follow the lens heuristics.
""")
        
        loader = LensLoader()
        lens = loader.load(Path("lenses/tech-writer.lens"))
        
        result = validate_skill_folder(skill_dir, lens)
        
        assert result.valid
        assert result.skill_data is not None

    def test_validate_nonexistent_folder(self, tmp_path):
        """Nonexistent folder fails validation."""
        from sunwell.skills.interop import validate_skill_folder
        
        result = validate_skill_folder(tmp_path / "does-not-exist")
        
        assert not result.valid
        assert len(result.issues) > 0


class TestExportImportRoundtrip:
    """Test export/import round-trip preserves skill data."""

    def test_roundtrip_skill_md(self, tmp_path):
        """Export to SKILL.md and import back preserves key data."""
        from sunwell.skills.interop import SkillExporter, SkillImporter
        
        # Create original skill
        original = Skill(
            name="roundtrip-test",
            description="Test round-trip export/import",
            skill_type=SkillType.INLINE,
            instructions="1. Export\n2. Import\n3. Compare",
            scripts=(
                Script(
                    name="test.py",
                    language="python",
                    content="print('roundtrip')",
                ),
            ),
            templates=(
                Template(name="output.md", content="# ${title}"),
            ),
        )
        
        # Export
        exporter = SkillExporter()
        md = exporter.export_skill_md(original)
        
        skill_dir = tmp_path / "roundtrip-test"
        skill_dir.mkdir()
        (skill_dir / "SKILL.md").write_text(md)
        
        # Import
        importer = SkillImporter()
        imported = importer.import_skill_folder(skill_dir)
        
        # Compare key fields
        assert imported["name"] == original.name
        assert original.description in imported["description"]
        assert "Export" in imported.get("instructions", "")
        assert len(imported.get("scripts", [])) == 1
        assert imported["scripts"][0]["name"] == "test.py"


# =============================================================================
# RFC-094: SkillCache O(1) LRU Tests
# =============================================================================


class TestSkillCacheKey:
    """Tests for SkillCacheKey hash computation."""

    def test_cache_key_hash_length(self):
        """Cache key hashes should be 20 chars (80 bits, RFC-094)."""
        skill = Skill(
            name="test-skill",
            description="Test",
            skill_type=SkillType.INLINE,
            instructions="Do something",
        )
        key = SkillCacheKey.compute(skill, {})
        
        assert len(key.skill_hash) == 20
        assert len(key.input_hash) == 20

    def test_cache_key_deterministic(self):
        """Same inputs should produce same cache key."""
        skill = Skill(
            name="test-skill",
            description="Test",
            skill_type=SkillType.INLINE,
            instructions="Do something",
            requires=frozenset({"input1", "input2"}),
        )
        context = {"input1": "value1", "input2": "value2"}
        
        key1 = SkillCacheKey.compute(skill, context)
        key2 = SkillCacheKey.compute(skill, context)
        
        assert key1.skill_hash == key2.skill_hash
        assert key1.input_hash == key2.input_hash
        assert str(key1) == str(key2)

    def test_cache_key_differs_on_skill_change(self):
        """Different skill content should produce different keys."""
        skill1 = Skill(
            name="test-skill",
            description="Test",
            skill_type=SkillType.INLINE,
            instructions="Do something",
        )
        skill2 = Skill(
            name="test-skill",
            description="Test",
            skill_type=SkillType.INLINE,
            instructions="Do something else",  # Different
        )
        
        key1 = SkillCacheKey.compute(skill1, {})
        key2 = SkillCacheKey.compute(skill2, {})
        
        assert key1.skill_hash != key2.skill_hash

    def test_cache_key_differs_on_input_change(self):
        """Different input context should produce different keys."""
        skill = Skill(
            name="test-skill",
            description="Test",
            skill_type=SkillType.INLINE,
            instructions="Do something",
            requires=frozenset({"input"}),
        )
        
        key1 = SkillCacheKey.compute(skill, {"input": "value1"})
        key2 = SkillCacheKey.compute(skill, {"input": "value2"})
        
        assert key1.input_hash != key2.input_hash


class TestSkillCacheLRU:
    """Tests for SkillCache LRU behavior (RFC-094)."""

    def _make_skill(self, name: str) -> Skill:
        """Helper to create a test skill."""
        return Skill(
            name=name,
            description=f"Test skill {name}",
            skill_type=SkillType.INLINE,
            instructions=f"Do {name}",
        )

    def _make_output(self, content: str):
        """Helper to create a mock SkillOutput."""
        from sunwell.skills.types import SkillOutput
        return SkillOutput(content=content)

    def test_cache_uses_ordered_dict(self):
        """Cache should use OrderedDict for O(1) LRU operations."""
        cache = SkillCache(max_size=10)
        assert isinstance(cache._cache, OrderedDict)

    def test_lru_eviction_order(self):
        """LRU eviction should evict oldest unused entry."""
        cache = SkillCache(max_size=3)
        
        skill_a = self._make_skill("a")
        skill_b = self._make_skill("b")
        skill_c = self._make_skill("c")
        skill_d = self._make_skill("d")
        
        key_a = SkillCacheKey.compute(skill_a, {})
        key_b = SkillCacheKey.compute(skill_b, {})
        key_c = SkillCacheKey.compute(skill_c, {})
        key_d = SkillCacheKey.compute(skill_d, {})
        
        # Fill cache: A, B, C
        cache.set(key_a, self._make_output("a"), "a", 100)
        cache.set(key_b, self._make_output("b"), "b", 100)
        cache.set(key_c, self._make_output("c"), "c", 100)
        
        # Access A to make it "recent"
        cache.get(key_a)
        
        # Add D — should evict B (oldest unused)
        cache.set(key_d, self._make_output("d"), "d", 100)
        
        assert cache.has(key_a)  # Recently accessed
        assert not cache.has(key_b)  # Evicted (oldest unused)
        assert cache.has(key_c)
        assert cache.has(key_d)

    def test_cache_hit_moves_to_end(self):
        """Cache hit should move entry to end (most recent)."""
        cache = SkillCache(max_size=3)
        
        skill_a = self._make_skill("a")
        skill_b = self._make_skill("b")
        skill_c = self._make_skill("c")
        
        key_a = SkillCacheKey.compute(skill_a, {})
        key_b = SkillCacheKey.compute(skill_b, {})
        key_c = SkillCacheKey.compute(skill_c, {})
        
        cache.set(key_a, self._make_output("a"), "a", 100)
        cache.set(key_b, self._make_output("b"), "b", 100)
        cache.set(key_c, self._make_output("c"), "c", 100)
        
        # A is oldest, access it
        cache.get(key_a)
        
        # Now B is oldest — verify by checking order
        keys = list(cache._cache.keys())
        assert keys[0] == str(key_b)  # B is now first (oldest)
        assert keys[-1] == str(key_a)  # A is now last (most recent)

    def test_cache_hit_rate_tracking(self):
        """Cache should track hits and misses."""
        cache = SkillCache(max_size=10)
        skill = self._make_skill("test")
        key = SkillCacheKey.compute(skill, {})
        
        # Miss
        cache.get(key)
        assert cache._misses == 1
        assert cache._hits == 0
        
        # Set
        cache.set(key, self._make_output("test"), "test", 100)
        
        # Hit
        cache.get(key)
        assert cache._hits == 1
        assert cache._misses == 1
        
        # Hit rate
        assert cache.hit_rate == 0.5

    def test_cache_performance_at_scale(self):
        """Cache operations should be O(1) even at scale."""
        cache = SkillCache(max_size=10000)
        
        # Fill cache
        skills = []
        keys = []
        for i in range(10000):
            skill = self._make_skill(f"skill-{i}")
            key = SkillCacheKey.compute(skill, {"i": i})
            skills.append(skill)
            keys.append(key)
            cache.set(key, self._make_output(f"output-{i}"), f"skill-{i}", 100)
        
        # Measure access time — should be constant
        start = time.perf_counter()
        for i in range(1000):
            cache.get(keys[i % 10000])
        elapsed = time.perf_counter() - start
        
        # Should complete in <50ms (O(1) * 1000 operations)
        # Being generous here to avoid flaky tests
        assert elapsed < 0.05, f"Cache access too slow: {elapsed:.3f}s for 1000 ops"

    def test_cache_invalidate_skill(self):
        """Invalidate all entries for a skill."""
        cache = SkillCache(max_size=10)
        
        # Use skill with requires to get different input hashes
        skill = Skill(
            name="target",
            description="Test skill",
            skill_type=SkillType.INLINE,
            instructions="Do target",
            requires=frozenset({"a"}),  # Requires 'a' so context affects hash
        )
        key1 = SkillCacheKey.compute(skill, {"a": 1})
        key2 = SkillCacheKey.compute(skill, {"a": 2})
        
        other_skill = self._make_skill("other")
        other_key = SkillCacheKey.compute(other_skill, {})
        
        cache.set(key1, self._make_output("1"), "target", 100)
        cache.set(key2, self._make_output("2"), "target", 100)
        cache.set(other_key, self._make_output("other"), "other", 100)
        
        # Invalidate target skill
        count = cache.invalidate_skill("target")
        
        assert count == 2
        assert not cache.has(key1)
        assert not cache.has(key2)
        assert cache.has(other_key)

    def test_cache_clear(self):
        """Clear should empty cache and reset stats."""
        cache = SkillCache(max_size=10)
        skill = self._make_skill("test")
        key = SkillCacheKey.compute(skill, {})
        
        cache.set(key, self._make_output("test"), "test", 100)
        cache.get(key)  # Hit
        
        cache.clear()
        
        assert cache.size == 0
        assert cache._hits == 0
        assert cache._misses == 0

    def test_cache_stats(self):
        """Stats should report accurate information."""
        cache = SkillCache(max_size=100)
        skill = self._make_skill("test")
        key = SkillCacheKey.compute(skill, {})
        
        cache.set(key, self._make_output("test"), "test", 100)
        cache.get(key)  # Hit
        cache.get(SkillCacheKey.compute(self._make_skill("miss"), {}))  # Miss
        
        stats = cache.stats()
        
        assert stats["size"] == 1
        assert stats["max_size"] == 100
        assert stats["hits"] == 1
        assert stats["misses"] == 1
        assert stats["hit_rate"] == 0.5

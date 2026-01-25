"""Tests for schema loader."""

from pathlib import Path

import pytest

from sunwell.foundation.schema.loader.loader import LensLoader
from sunwell.foundation.errors import SunwellError


class TestLensLoader:
    def test_load_tech_writer(self, lens_loader: LensLoader, lenses_dir: Path):
        lens = lens_loader.load(lenses_dir / "tech-writer.lens")

        assert lens.metadata.name == "Technical Writer"
        assert lens.metadata.domain == "documentation"
        assert len(lens.heuristics) >= 4
        assert len(lens.personas) >= 4
        assert lens.framework is not None
        assert lens.framework.name == "Diataxis"

    def test_load_code_reviewer(self, lens_loader: LensLoader, lenses_dir: Path):
        lens = lens_loader.load(lenses_dir / "code-reviewer.lens")

        assert lens.metadata.name == "Code Reviewer"
        assert lens.metadata.domain == "software"
        assert len(lens.heuristics) >= 4

    def test_load_nonexistent_raises(self, lens_loader: LensLoader):
        with pytest.raises(SunwellError) as exc_info:
            lens_loader.load(Path("/nonexistent/path.lens"))

        assert "not found" in exc_info.value.message

    def test_load_string(self, lens_loader: LensLoader):
        yaml_content = """
lens:
  metadata:
    name: "String Test"
    version: "0.1.0"
  heuristics:
    principles:
      - name: "Test Rule"
        rule: "Do the thing"
"""
        lens = lens_loader.load_string(yaml_content)
        assert lens.metadata.name == "String Test"
        assert len(lens.heuristics) == 1

    def test_parse_heuristics(self, lens_loader: LensLoader):
        yaml_content = """
lens:
  metadata:
    name: "Heuristic Test"
  heuristics:
    principles:
      - name: "Priority Test"
        rule: "Test priority"
        priority: 10
        always:
          - "Do this"
          - "And this"
        never:
          - "Not this"
        examples:
          good:
            - "Good example"
          bad:
            - "Bad example"
"""
        lens = lens_loader.load_string(yaml_content)
        h = lens.heuristics[0]

        assert h.name == "Priority Test"
        assert h.priority == 10
        assert len(h.always) == 2
        assert len(h.never) == 1
        assert len(h.examples.good) == 1
        assert len(h.examples.bad) == 1

    def test_parse_personas(self, lens_loader: LensLoader):
        yaml_content = """
lens:
  metadata:
    name: "Persona Test"
  personas:
    - name: "user1"
      description: "Test user"
      goals:
        - "Goal 1"
      friction_points:
        - "Friction 1"
      attack_vectors:
        - "Question 1"
"""
        lens = lens_loader.load_string(yaml_content)
        p = lens.personas[0]

        assert p.name == "user1"
        assert len(p.goals) == 1
        assert len(p.friction_points) == 1
        assert len(p.attack_vectors) == 1

    def test_parse_framework(self, lens_loader: LensLoader):
        yaml_content = """
lens:
  metadata:
    name: "Framework Test"
  framework:
    name: "Test Framework"
    description: "A test framework"
    categories:
      - name: "CAT1"
        purpose: "First category"
        triggers:
          - "trigger1"
"""
        lens = lens_loader.load_string(yaml_content)
        f = lens.framework

        assert f is not None
        assert f.name == "Test Framework"
        assert len(f.categories) == 1
        assert f.categories[0].name == "CAT1"

    def test_parse_validators(self, lens_loader: LensLoader):
        yaml_content = """
lens:
  metadata:
    name: "Validator Test"
  validators:
    deterministic:
      - name: "lint"
        script: "lint.py"
        severity: "error"
    heuristic:
      - name: "clarity"
        check: "Is content clear?"
        method: "pattern_match"
        confidence_threshold: 0.8
"""
        lens = lens_loader.load_string(yaml_content)

        assert len(lens.deterministic_validators) == 1
        assert len(lens.heuristic_validators) == 1
        assert lens.deterministic_validators[0].name == "lint"
        assert lens.heuristic_validators[0].name == "clarity"

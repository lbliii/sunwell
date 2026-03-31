"""Tests for unified tool surface assembly (policy, merge, fingerprint, deferral)."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from sunwell.agent.loop.config import LoopConfig
from sunwell.models import Tool
from sunwell.tools.core.types import ExecutionRole, ToolPolicy, ToolTrust
from sunwell.tools.surface import (
    DISCOVER_TOOLS_NAME,
    assemble_tools_for_model,
    compute_tool_surface_fingerprint,
    estimate_definition_tokens,
    estimate_skill_catalog_tokens,
    estimate_total_surface_tokens,
)


def _tool(name: str, desc: str = "d", schema: dict | None = None) -> Tool:
    return Tool(
        name=name,
        description=desc,
        parameters=schema or {"type": "object", "properties": {}},
    )


def test_fingerprint_stable_ordering() -> None:
    a = _tool("a")
    b = _tool("b")
    fp1 = compute_tool_surface_fingerprint((b, a))
    fp2 = compute_tool_surface_fingerprint((a, b))
    assert fp1 == fp2


def test_fingerprint_changes_when_schema_changes() -> None:
    t1 = _tool("x", schema={"type": "object", "properties": {"p": {"type": "string"}}})
    t2 = _tool("x", schema={"type": "object", "properties": {"q": {"type": "string"}}})
    assert compute_tool_surface_fingerprint((t1,)) != compute_tool_surface_fingerprint((t2,))


def test_policy_filters_tools() -> None:
    ex = MagicMock()
    ex.registry.get_active_schemas.return_value = (_tool("keep"), _tool("drop"))
    ex.skill_executor = None
    ex._materialized_deferred = set()
    policy = ToolPolicy(
        trust_level=ToolTrust.WORKSPACE,
        allowed_tools=frozenset({"keep"}),
    )
    surf = assemble_tools_for_model(ex, policy, None)
    assert {t.name for t in surf.tools} == {"keep"}


def test_subagent_role_removes_denied_tools() -> None:
    ex = MagicMock()
    ex.registry.get_active_schemas.return_value = (
        _tool("read_file"),
        _tool("delegate_task"),
    )
    ex.skill_executor = None
    ex._materialized_deferred = set()
    surf_main = assemble_tools_for_model(ex, None, ExecutionRole.MAIN)
    surf_sub = assemble_tools_for_model(ex, None, ExecutionRole.SUBAGENT)
    assert {t.name for t in surf_sub.tools}.issubset({t.name for t in surf_main.tools})
    assert "delegate_task" not in {t.name for t in surf_sub.tools}


def test_merge_registry_wins_collision(caplog: pytest.LogCaptureFixture) -> None:
    import logging

    ex = MagicMock()
    reg = _tool("same", desc="from registry")
    sk = _tool("same", desc="from skill")
    ex.registry.get_active_schemas.return_value = (reg,)
    sk_ex = MagicMock()
    sk_ex.get_tool_definitions.return_value = (sk,)
    ex.skill_executor = sk_ex
    ex._materialized_deferred = set()
    with caplog.at_level(logging.WARNING):
        surf = assemble_tools_for_model(ex, None, None)
    same = [t for t in surf.tools if t.name == "same"]
    assert len(same) == 1
    assert same[0].description == "from registry"
    assert "tool_collision_resolved" in caplog.text


def test_deferred_mode_adds_discover_and_reduces_tokens() -> None:
    ex = MagicMock()
    big_schema = {"type": "object", "properties": {f"k{i}": {"type": "string"} for i in range(80)}}
    tools = tuple(_tool(f"t{i}", "x" * 400, big_schema) for i in range(50))
    ex.registry.get_active_schemas.return_value = tools
    ex.skill_executor = None
    ex._materialized_deferred = set()
    cfg = LoopConfig(enable_deferred_tool_schemas=True, max_tool_surface_tokens=500)
    surf = assemble_tools_for_model(ex, None, None, loop_config=cfg)
    full_tok = estimate_total_surface_tokens(tools)
    assert surf.deferred_count >= 1
    assert surf.total_estimated_tokens < full_tok * 0.6
    assert any(t.name == DISCOVER_TOOLS_NAME for t in surf.tools)


def test_estimate_skill_catalog_tokens() -> None:
    t = _tool("s", "hello")
    assert estimate_skill_catalog_tokens((t,)) == estimate_definition_tokens(t)

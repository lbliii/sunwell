"""Unified tool surface assembly for model consumption.

Precedence: DynamicToolRegistry (core) > SkillExecutor > future MCP client tools.
On name collision: registry wins; collision is logged at WARNING level.
Future MCP client tools should use the ``mcp__{server}__{tool}`` namespace prefix.
"""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.models import Tool
from sunwell.tools.core.constants import ROLE_DENIED_TOOLS
from sunwell.tools.core.types import ExecutionRole, ToolPolicy
from sunwell.tools.observability.events import (
    log_tool_collision,
    log_tool_deferred,
    log_tool_surface_assembled,
)

if TYPE_CHECKING:
    from sunwell.agent.loop.config import LoopConfig
    from sunwell.tools.execution.executor import ToolExecutor

DISCOVER_TOOLS_NAME = "discover_tools"

_STUB_PARAMETERS: dict[str, object] = {
    "type": "object",
    "properties": {},
    "description": "[Full JSON schema available via discover_tools(select=<name>).]",
}


def estimate_definition_tokens(tool: Tool) -> int:
    """Rough token estimate for name, description, and JSON Schema (chars / 4 heuristic)."""
    name = len(tool.name) // 4
    desc = len(tool.description) // 4
    schema = len(json.dumps(tool.parameters, sort_keys=True)) // 4
    return name + desc + schema


def estimate_total_surface_tokens(tools: tuple[Tool, ...]) -> int:
    """Sum of per-tool estimates for the surface passed to the model."""
    return sum(estimate_definition_tokens(t) for t in tools)


def estimate_skill_catalog_tokens(skill_tools: tuple[Tool, ...]) -> int:
    """Token estimate for skill-derived tools only (catalog budgeting)."""
    return sum(estimate_definition_tokens(t) for t in skill_tools)


def compute_tool_surface_fingerprint(tools: tuple[Tool, ...]) -> str:
    """SHA-256 over sorted (name, schema_sha256) pairs — stable across runs."""
    parts: list[str] = []
    for t in sorted(tools, key=lambda x: x.name):
        schema_sha = hashlib.sha256(
            json.dumps(t.parameters, sort_keys=True).encode()
        ).hexdigest()
        parts.append(f"{t.name}:{schema_sha}")
    joined = "|".join(parts)
    return hashlib.sha256(joined.encode()).hexdigest()


def _first_sentence(text: str, *, max_len: int = 200) -> str:
    s = text.strip()
    if not s:
        return ""
    m = re.match(r"([^.!?]+[.!?]?)", s)
    one = m.group(1) if m else s[:max_len]
    return one[:max_len]


def _merge_registry_and_skills(
    registry_tools: tuple[Tool, ...],
    skill_tools: tuple[Tool, ...],
) -> tuple[Tool, ...]:
    """Registry wins on name collision; skills append for novel names."""
    seen = {t.name for t in registry_tools}
    out: list[Tool] = list(registry_tools)
    for t in skill_tools:
        if t.name in seen:
            log_tool_collision(t.name, "registry", "skill")
            continue
        out.append(t)
        seen.add(t.name)
    out.sort(key=lambda x: x.name)
    return tuple(out)


def _apply_policy(tools: tuple[Tool, ...], policy: ToolPolicy | None) -> tuple[Tool, ...]:
    if policy is None:
        return tools
    allowed = policy.get_allowed_tools()
    return tuple(t for t in tools if t.name in allowed)


def _apply_role(
    tools: tuple[Tool, ...],
    role: ExecutionRole | None,
) -> tuple[Tool, ...]:
    if role is None:
        return tools
    denied = ROLE_DENIED_TOOLS.get(role, frozenset())
    return tuple(t for t in tools if t.name not in denied)


def _discover_tool_definition() -> Tool:
    return Tool(
        name=DISCOVER_TOOLS_NAME,
        description=(
            "Search deferred tools by keyword or materialize a full JSON schema. "
            "Use query= for keyword search, or select= with an exact tool name. "
            "[Full schema available via discover_tools]"
        ),
        parameters={
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Keyword search over deferred tool names and descriptions",
                },
                "select": {
                    "type": "string",
                    "description": "Exact tool name whose full schema should be loaded",
                },
            },
        },
    )


def _deferral_names(
    tools: tuple[Tool, ...],
    *,
    threshold: int,
    max_budget: int,
    materialized: frozenset[str],
) -> set[str]:
    """Return tool names that should be deferred (stub schema only)."""
    tok_map = {t.name: estimate_definition_tokens(t) for t in tools}
    deferred: set[str] = set()
    for t in tools:
        if t.name in materialized:
            continue
        if tok_map[t.name] >= threshold:
            deferred.add(t.name)

    def active_total() -> int:
        return sum(
            tok_map[t.name]
            for t in tools
            if t.name not in deferred and t.name not in materialized
        )

    while active_total() > max_budget:
        movable = [
            t
            for t in tools
            if t.name not in deferred and t.name not in materialized
        ]
        if not movable:
            break
        victim = max(movable, key=lambda t: tok_map[t.name])
        deferred.add(victim.name)
    return deferred


def _stub_tool(full: Tool) -> Tool:
    return Tool(
        name=full.name,
        description=(
            f"{_first_sentence(full.description)} "
            "[Full schema available via discover_tools(select=…)]"
        ),
        parameters=dict(_STUB_PARAMETERS),
    )


@dataclass(frozen=True, slots=True)
class ToolSurface:
    """Tools and metadata exposed to the model for one assembly."""

    tools: tuple[Tool, ...]
    fingerprint: str
    tool_count: int
    """Number of tools in ``tools`` (after policy, role, and optional deferral)."""

    filtered_count: int
    """Tools removed from the merged registry+skills set by policy and/or role."""

    total_estimated_tokens: int
    deferred_count: int


def assemble_tools_for_model(
    executor: ToolExecutor,
    policy: ToolPolicy | None = None,
    role: ExecutionRole | None = None,
    *,
    loop_config: LoopConfig | None = None,
) -> ToolSurface:
    """Merge registry + skills, apply policy and role filters, optionally defer schemas.

    When ``loop_config`` is None, deferral is disabled (full schemas, no discover_tools).
    """
    reg = executor.registry
    reg_tools = tuple(reg.get_active_schemas()) if reg else ()
    skill_tup = (
        executor.skill_executor.get_tool_definitions()
        if executor.skill_executor
        else ()
    )
    merged = _merge_registry_and_skills(reg_tools, skill_tup)
    merged_count = len(merged)
    filtered = _apply_policy(merged, policy)
    filtered = _apply_role(filtered, role)
    filtered_count = merged_count - len(filtered)

    full_by_name: dict[str, Tool] = {t.name: t for t in filtered}
    executor._surface_full_tool_cache = full_by_name

    defer_active = False
    if loop_config is not None:
        defer_active = loop_config.enable_deferred_tool_schemas or len(filtered) > 30

    if not defer_active:
        tools = filtered
        fp = compute_tool_surface_fingerprint(tools)
        tok = estimate_total_surface_tokens(tools)
        log_tool_surface_assembled(
            tool_count=len(tools),
            total_estimated_tokens=tok,
            fingerprint=fp,
            deferred_count=0,
        )
        return ToolSurface(
            tools=tools,
            fingerprint=fp,
            tool_count=len(tools),
            filtered_count=filtered_count,
            total_estimated_tokens=tok,
            deferred_count=0,
        )

    assert loop_config is not None
    mat = frozenset(executor._materialized_deferred)
    threshold = loop_config.deferred_tool_schema_threshold
    max_budget = loop_config.max_tool_surface_tokens
    defer_names = _deferral_names(
        filtered,
        threshold=threshold,
        max_budget=max_budget,
        materialized=mat,
    )

    out: list[Tool] = []
    for t in filtered:
        if t.name in defer_names and t.name not in mat:
            stub = _stub_tool(t)
            out.append(stub)
            tok_t = estimate_definition_tokens(t)
            reason = "per_tool_threshold" if tok_t >= threshold else "surface_budget"
            log_tool_deferred(t.name, tok_t, reason)
        else:
            out.append(t)

    search_rows: list[tuple[str, str]] = []
    for t in filtered:
        if t.name in defer_names and t.name not in mat:
            search_rows.append((t.name, t.description))
    executor._deferred_search_index = search_rows

    if defer_names - set(mat):
        discover = _discover_tool_definition()
        names_out = {x.name for x in out}
        if discover.name not in names_out:
            out.append(discover)

    tools_out = tuple(sorted(out, key=lambda x: x.name))
    fp = compute_tool_surface_fingerprint(tools_out)
    tok = estimate_total_surface_tokens(tools_out)
    deferred_n = len(defer_names - set(mat))
    log_tool_surface_assembled(
        tool_count=len(tools_out),
        total_estimated_tokens=tok,
        fingerprint=fp,
        deferred_count=deferred_n,
    )
    return ToolSurface(
        tools=tools_out,
        fingerprint=fp,
        tool_count=len(tools_out),
        filtered_count=filtered_count,
        total_estimated_tokens=tok,
        deferred_count=deferred_n,
    )

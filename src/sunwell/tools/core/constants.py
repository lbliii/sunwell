"""Tool constants and trust level mappings."""

from sunwell.tools.core.types import ToolTrust

# Tools allowed at each trust level (RFC-024 expanded)
TRUST_LEVEL_TOOLS: dict[ToolTrust, frozenset[str]] = {
    ToolTrust.DISCOVERY: frozenset({
        "list_files", "search_files",
    }),
    ToolTrust.READ_ONLY: frozenset({
        "list_files", "search_files", "read_file",
        # File discovery - safe, no side effects
        "find_files",
        # Backup inspection - read-only
        "list_backups",
        # Git read operations - safe, no side effects
        "git_info", "git_status", "git_diff", "git_log", "git_blame", "git_show",
        # RFC-125: Self-knowledge tools (read-only, safe at READ_ONLY level)
        "sunwell_self_modules", "sunwell_self_search", "sunwell_self_read",
    }),
    ToolTrust.WORKSPACE: frozenset({
        "list_files", "search_files", "read_file", "write_file", "edit_file", "mkdir",
        # File management operations - create backups before destructive actions
        "delete_file", "rename_file", "copy_file", "find_files", "patch_file",
        # Undo/rollback operations
        "undo_file", "list_backups", "restore_file",
        "git_info", "git_status", "git_diff", "git_log", "git_blame", "git_show",
        # Staging operations - reversible, don't modify history
        "git_add", "git_restore",
        # Repository initialization - creates new repo, doesn't modify history
        "git_init",
        # RFC-125: Self-knowledge tools (inherited from READ_ONLY)
        "sunwell_self_modules", "sunwell_self_search", "sunwell_self_read",
        # RFC-125: Sunwell project tools (require workspace context)
        "sunwell_intel_decisions", "sunwell_intel_failures", "sunwell_intel_patterns",
        "sunwell_search_semantic", "sunwell_lineage_file", "sunwell_lineage_impact",
        "sunwell_weakness_scan", "sunwell_weakness_preview",
        "sunwell_workflow_chains", "sunwell_workflow_route",
    }),
    ToolTrust.SHELL: frozenset({
        "list_files", "search_files", "read_file", "write_file", "edit_file", "mkdir", "run_command",
        # File management operations
        "delete_file", "rename_file", "copy_file", "find_files", "patch_file",
        # Undo/rollback operations
        "undo_file", "list_backups", "restore_file",
        "git_info", "git_status", "git_diff", "git_log", "git_blame", "git_show",
        "git_add", "git_restore", "git_init",
        # History-modifying operations - require explicit trust
        "git_commit", "git_branch", "git_checkout", "git_stash",
        "git_reset", "git_merge",
        # RFC-125: All Sunwell tools (inherited from WORKSPACE)
        "sunwell_self_modules", "sunwell_self_search", "sunwell_self_read",
        "sunwell_intel_decisions", "sunwell_intel_failures", "sunwell_intel_patterns",
        "sunwell_search_semantic", "sunwell_lineage_file", "sunwell_lineage_impact",
        "sunwell_weakness_scan", "sunwell_weakness_preview",
        "sunwell_workflow_chains", "sunwell_workflow_route",
    }),
    ToolTrust.FULL: frozenset({
        # All previous tools
        "list_files", "search_files", "read_file", "write_file", "edit_file", "mkdir", "run_command",
        # File management operations
        "delete_file", "rename_file", "copy_file", "find_files", "patch_file",
        # Undo/rollback operations
        "undo_file", "list_backups", "restore_file",
        "git_info", "git_status", "git_diff", "git_log", "git_blame", "git_show",
        "git_add", "git_restore", "git_init",
        "git_commit", "git_branch", "git_checkout", "git_stash",
        "git_reset", "git_merge",
        # Network access
        "web_search", "web_fetch",
        # Restricted environment access (allowlist enforced)
        "get_env", "list_env",
        # Future: dynamic tool learning
        "learn_api",
        # RFC-125: All Sunwell tools (inherited from SHELL)
        "sunwell_self_modules", "sunwell_self_search", "sunwell_self_read",
        "sunwell_intel_decisions", "sunwell_intel_failures", "sunwell_intel_patterns",
        "sunwell_search_semantic", "sunwell_lineage_file", "sunwell_lineage_impact",
        "sunwell_weakness_scan", "sunwell_weakness_preview",
        "sunwell_workflow_chains", "sunwell_workflow_route",
    }),
}

# RFC-014: Memory tools (always available regardless of trust level)
MEMORY_TOOLS: frozenset[str] = frozenset({
    "search_memory", "recall_user_info", "find_related",
    "find_contradictions", "add_learning", "mark_dead_end",
})

# RFC-014: Simulacrum management tools (always available)
SIMULACRUM_TOOLS: frozenset[str] = frozenset({
    "list_headspaces", "switch_headspace", "create_headspace",
    "suggest_headspace", "query_all_headspaces", "current_headspace",
    "route_query", "spawn_status",  # Auto-spawning tools
    "headspace_health", "archive_headspace", "restore_headspace",  # Lifecycle tools
    "list_archived", "cleanup_headspaces", "shrink_headspace",
})

# Web search tools (require FULL trust level)
WEB_TOOLS: frozenset[str] = frozenset({
    "web_search", "web_fetch",
})

# RFC-015: Mirror neuron tools (self-introspection and self-improvement)
MIRROR_TOOLS: frozenset[str] = frozenset({
    # Introspection (DISCOVERY trust)
    "introspect_source", "introspect_lens", "introspect_headspace",
    "introspect_execution",
    # Analysis (READ_ONLY trust)
    "analyze_patterns", "analyze_failures", "analyze_model_performance",
    # Proposals (READ_ONLY trust)
    "propose_improvement", "propose_model_routing", "list_proposals",
    "get_proposal", "submit_proposal",
    # Application (WORKSPACE trust)
    "approve_proposal", "apply_proposal", "rollback_proposal",
})

# RFC-027: Expertise tools (self-directed expertise retrieval)
EXPERTISE_TOOLS: frozenset[str] = frozenset({
    "get_expertise", "verify_against_expertise", "list_expertise_areas",
})

# RFC-125: Sunwell self-access tools
SUNWELL_TOOLS: frozenset[str] = frozenset({
    "sunwell_intel_decisions", "sunwell_intel_failures", "sunwell_intel_patterns",
    "sunwell_search_semantic", "sunwell_lineage_file", "sunwell_lineage_impact",
    "sunwell_weakness_scan", "sunwell_weakness_preview",
    "sunwell_self_modules", "sunwell_self_search", "sunwell_self_read",
    "sunwell_workflow_chains", "sunwell_workflow_route",
})

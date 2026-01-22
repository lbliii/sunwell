# RFC-092: Skill Permission Defaults

**Status:** Implemented  
**Author:** AI Assistant  
**Created:** 2026-01-22  
**Implemented:** 2026-01-22  
**Related:** RFC-089 (Security-First Skills), RFC-087 (Skill-Lens DAG)

---

## Executive Summary

RFC-089 implemented the infrastructure for declarative skill permissions, but **Sunwell's 50+ built-in skills have no permissions declared**. They fall back to "ambient permissions" (legacy behavior), defeating the purpose of the security-first architecture.

This RFC:
1. Defines **permission presets** for common skill categories
2. Applies permissions to all built-in skills
3. Establishes **sane defaults** for security metadata
4. Provides a template for skill authors

**This is excellent dogfooding** — Sunwell's own skills demonstrating the security model — and **ideal for demos** showing declarative permissions in action.

---

## Problem Statement

### Current State

```bash
$ grep -c "permissions:" skills/*.yaml
0  # No skills declare permissions
```

All 50+ skills have:
- ✅ `trust: sandboxed` (basic sandbox)
- ✅ `allowed_tools: [...]` (tool whitelist)
- ❌ `permissions:` (filesystem, network, shell scopes)
- ❌ `security:` (classification, audit level)

### Impact

```
┌─────────────────────────────────────────────────────────────────┐
│                     WITHOUT PERMISSIONS                          │
│                                                                  │
│  User: "Run the docs-validation skills"                          │
│           ↓                                                      │
│  RFC-089: permissions = None                                     │
│           ↓                                                      │
│  Fallback: PermissionScope() → empty → ambient permissions       │
│           ↓                                                      │
│  Result: Skills can access ANYTHING the runtime allows           │
│                                                                  │
│  🚨 The security infrastructure exists but is NOT USED           │
└─────────────────────────────────────────────────────────────────┘
```

### Evidence

From `src/sunwell/security/analyzer.py:342-344`:

```python
if permissions is None:
    return PermissionScope()  # Empty scope = legacy behavior
```

From `skills/tool-skills.yaml` (15 skills):
- All have `trust: sandboxed`
- None have `permissions:` block

From `skills/docs-creation-skills.yaml` (5 skills):
- All have `allowed_tools: [...]`
- None have `permissions:` or `security:` blocks

---

## Solution: Permission Presets

### Design Principles

1. **Explicit over implicit** — Every skill declares what it needs
2. **Deny by default** — Network and shell blocked unless declared
3. **DRY** — Presets avoid repetition across 50+ skills
4. **Progressive** — Start restrictive, relax only when proven necessary

### Permission Preset Definitions

```yaml
# skills/permission-presets.yaml — NEW FILE

presets:
  # ============================================================================
  # READ-ONLY: Can read files, no writes, no network, no shell
  # ============================================================================
  read-only:
    permissions:
      filesystem:
        read: ["**/*"]
        write: []
      network:
        allow: []
        deny: ["*"]
      shell:
        allow: []
        deny: ["*"]
      environment:
        read: ["HOME", "USER", "PATH"]
        write: []
    security:
      data_classification: internal
      requires_approval: false
      audit_level: minimal

  # ============================================================================
  # WORKSPACE-WRITE: Can read/write within workspace
  # ============================================================================
  workspace-write:
    permissions:
      filesystem:
        read: ["**/*"]
        write: ["**/*"]  # Workspace only (enforced by sandbox)
      network:
        allow: []
        deny: ["*"]
      shell:
        allow: []
        deny: ["*"]
      environment:
        read: ["HOME", "USER", "PATH"]
        write: []
    security:
      data_classification: internal
      requires_approval: false
      audit_level: standard

  # ============================================================================
  # SAFE-SHELL: Common dev commands (lint, test, build)
  # ============================================================================
  safe-shell:
    permissions:
      filesystem:
        read: ["**/*"]
        write: ["**/*", "/tmp/*"]
      network:
        allow: []
        deny: ["*"]
      shell:
        allow:
          - "python"
          - "python -m pytest"
          - "python -m mypy"
          - "ruff"
          - "npm run"
          - "npm test"
          - "cargo"
          - "make"
          - "git status"
          - "git diff"
          - "git log"
          - "cat"
          - "head"
          - "tail"
          - "wc"
          - "grep"
          - "find"
          - "ls"
        deny:
          - "rm -rf"
          - "sudo"
          - "chmod 777"
          - "chown"
          - "curl"
          - "wget"
          - "ssh"
          - "scp"
          - "rsync"
          - "nc"
          - "ncat"
          - "eval"
      environment:
        read: ["HOME", "USER", "PATH", "PYTHONPATH", "NODE_PATH"]
        write: []
    security:
      data_classification: internal
      requires_approval: false
      audit_level: standard

  # ============================================================================
  # GIT-READ: Git status, diff, log (no modifications)
  # ============================================================================
  git-read:
    permissions:
      filesystem:
        read: ["**/*", "~/.gitconfig"]
        write: []
      network:
        allow: []
        deny: ["*"]
      shell:
        allow:
          - "git status"
          - "git diff"
          - "git log"
          - "git show"
          - "git branch"
          - "git remote -v"
        deny:
          - "git push"
          - "git fetch"
          - "git pull"
          - "git clone"
          - "git checkout"
          - "git reset"
          - "git rebase"
          - "git merge"
    security:
      data_classification: internal
      requires_approval: false
      audit_level: minimal

  # ============================================================================
  # GIT-WRITE: Full local git operations (no remote)
  # ============================================================================
  git-write:
    permissions:
      filesystem:
        read: ["**/*", "~/.gitconfig"]
        write: [".git/**", "**/*"]
      network:
        allow: []
        deny: ["*"]  # No push/fetch
      shell:
        allow:
          - "git status"
          - "git diff"
          - "git log"
          - "git show"
          - "git add"
          - "git commit"
          - "git branch"
          - "git checkout"
          - "git merge"
          - "git rebase"
          - "git stash"
          - "git reset"
        deny:
          - "git push"
          - "git fetch"
          - "git pull"
          - "git clone"
    security:
      data_classification: internal
      requires_approval: false
      audit_level: standard

  # ============================================================================
  # SEARCH-ONLY: Grep, find, semantic search
  # ============================================================================
  search-only:
    permissions:
      filesystem:
        read: ["**/*"]
        write: []
      network:
        allow: []
        deny: ["*"]
      shell:
        allow:
          - "grep"
          - "rg"
          - "find"
          - "fd"
          - "ag"
          - "ack"
        deny: ["*"]
    security:
      data_classification: internal
      requires_approval: false
      audit_level: minimal

  # ============================================================================
  # ELEVATED: Requires explicit approval (network, sensitive paths)
  # ============================================================================
  elevated:
    permissions:
      filesystem:
        read: ["**/*"]
        write: ["**/*"]
      network:
        allow: []  # Must be explicitly declared per-skill
        deny: []   # No default deny — skill must specify
      shell:
        allow: []  # Must be explicitly declared per-skill
        deny: []
    security:
      data_classification: confidential
      requires_approval: true
      audit_level: verbose
```

---

## Applying Presets to Built-in Skills

### tool-skills.yaml Updates

```yaml
# skills/tool-skills.yaml — UPDATED

skills:
  # ============================================================================
  # FILE OPERATIONS
  # ============================================================================
  
  - name: file-read
    description: Read file contents from the workspace.
    type: inline
    trust: sandboxed
    allowed_tools: [read_file]
    preset: read-only                    # NEW: inherits permissions
    instructions: |
      # ... existing instructions ...

  - name: file-write
    description: Write or create files in the workspace.
    type: inline
    trust: sandboxed
    allowed_tools: [write_file]
    preset: workspace-write              # NEW
    instructions: |
      # ... existing instructions ...

  - name: file-edit
    description: Make targeted edits to existing files.
    type: inline
    trust: sandboxed
    allowed_tools: [edit_file]
    preset: workspace-write              # NEW
    instructions: |
      # ... existing instructions ...

  - name: file-search
    description: Search for patterns in files using ripgrep.
    type: inline
    trust: sandboxed
    allowed_tools: [search_files]
    preset: search-only                  # NEW
    instructions: |
      # ... existing instructions ...

  - name: file-list
    description: List files and directories in the workspace.
    type: inline
    trust: sandboxed
    allowed_tools: [list_files]
    preset: read-only                    # NEW
    instructions: |
      # ... existing instructions ...

  # ============================================================================
  # SHELL OPERATIONS
  # ============================================================================

  - name: shell-run
    description: Run shell commands in a sandboxed environment.
    type: inline
    trust: sandboxed
    allowed_tools: [run_command]
    preset: safe-shell                   # NEW
    instructions: |
      # ... existing instructions ...

  - name: shell-mkdir
    description: Create directories in the workspace.
    type: inline
    trust: sandboxed
    allowed_tools: [mkdir]
    preset: workspace-write              # NEW
    instructions: |
      # ... existing instructions ...

  # ============================================================================
  # GIT OPERATIONS
  # ============================================================================

  - name: git-status
    description: Get git repository status.
    type: inline
    trust: sandboxed
    allowed_tools: [git_status]
    preset: git-read                     # NEW
    instructions: |
      # ... existing instructions ...

  - name: git-diff
    description: Show changes between commits or working tree.
    type: inline
    trust: sandboxed
    allowed_tools: [git_diff]
    preset: git-read                     # NEW
    instructions: |
      # ... existing instructions ...

  - name: git-log
    description: View commit history.
    type: inline
    trust: sandboxed
    allowed_tools: [git_log]
    preset: git-read                     # NEW
    instructions: |
      # ... existing instructions ...

  - name: git-commit-workflow
    description: Stage changes and create a commit.
    type: inline
    trust: sandboxed
    allowed_tools: [git_add, git_commit]
    preset: git-write                    # NEW
    instructions: |
      # ... existing instructions ...

  - name: git-branch-workflow
    description: Create, switch, or list git branches.
    type: inline
    trust: sandboxed
    allowed_tools: [git_branch, git_checkout]
    preset: git-write                    # NEW
    instructions: |
      # ... existing instructions ...

  # ============================================================================
  # COMPOUND SKILLS
  # ============================================================================

  - name: code-exploration
    description: Explore and understand a codebase.
    type: inline
    trust: sandboxed
    allowed_tools: [search_files, read_file, list_files]
    preset: read-only                    # NEW
    instructions: |
      # ... existing instructions ...

  - name: code-modification
    description: Make changes to code files with verification.
    type: inline
    trust: sandboxed
    allowed_tools: [read_file, edit_file, write_file, git_diff]
    preset: workspace-write              # NEW
    # Override preset's git permissions for verification
    permissions:
      shell:
        allow: ["git diff"]
    instructions: |
      # ... existing instructions ...

  - name: test-and-lint
    description: Run tests and linting to verify code quality.
    type: inline
    trust: sandboxed
    allowed_tools: [run_command]
    preset: safe-shell                   # NEW
    instructions: |
      # ... existing instructions ...
```

### docs-creation-skills.yaml Updates

```yaml
# skills/docs-creation-skills.yaml — UPDATED

skills:
  - name: draft-documentation
    description: Create new documentation with evidence-based research
    type: inline
    triggers: ["draft", "write", "create doc", "new doc"]
    allowed_tools: [read_file, codebase_search, grep, write]
    preset: workspace-write              # NEW
    instructions: |
      # ... existing instructions ...
    validate_with:
      validators: [evidence_required, no_marketing_fluff, front_loaded]
      personas: [novice, pragmatist]
      min_confidence: 0.75

  - name: create-overview-page
    description: Create product/platform overview (Explanation type)
    type: inline
    triggers: ["overview", "introduction", "what is", "::overview"]
    allowed_tools: [read_file, codebase_search, grep, write]
    preset: workspace-write              # NEW
    instructions: |
      # ... existing instructions ...

  - name: create-architecture-page
    description: Create architecture explanation page
    type: inline
    triggers: ["architecture", "how it works", "internals", "::architecture"]
    allowed_tools: [read_file, codebase_search, grep, write]
    preset: workspace-write              # NEW
    instructions: |
      # ... existing instructions ...

  - name: create-features-page
    description: Create comprehensive key features catalog (Reference type)
    type: inline
    triggers: ["features", "capabilities", "key features", "::features"]
    allowed_tools: [read_file, codebase_search, grep, write]
    preset: workspace-write              # NEW
    instructions: |
      # ... existing instructions ...

  - name: create-ecosystem-page
    description: Create ecosystem/positioning page
    type: inline
    triggers: ["ecosystem", "positioning", "comparison", "::ecosystem"]
    allowed_tools: [read_file, codebase_search, grep, write]
    preset: workspace-write              # NEW
    instructions: |
      # ... existing instructions ...
```

### docs-validation-skills.yaml Updates

```yaml
# skills/docs-validation-skills.yaml — UPDATED

skills:
  - name: audit-documentation
    description: Quick validation of documentation against source code
    type: inline
    triggers: ["audit", "validate", "check", "verify", "::a"]
    allowed_tools: [read_file, codebase_search, grep]
    preset: read-only                    # NEW: validation = read-only
    instructions: |
      # ... existing instructions ...
    validate_with:
      validators: [evidence_required]
      min_confidence: 0.8

  - name: audit-documentation-deep
    description: Comprehensive audit with triangulation and confidence scoring
    type: inline
    triggers: ["deep audit", "comprehensive", "thorough", "::a-2"]
    allowed_tools: [read_file, codebase_search, grep, run_terminal_cmd]
    preset: safe-shell                   # NEW: can run validation commands
    instructions: |
      # ... existing instructions ...

  - name: check-drift
    description: Detect when documentation has drifted from source
    type: inline
    triggers: ["drift", "stale", "outdated"]
    allowed_tools: [read_file, codebase_search]
    preset: read-only                    # NEW
    instructions: |
      # ... existing instructions ...

  - name: check-health
    description: System-wide documentation health check
    type: inline
    triggers: ["health", "check all", "::health"]
    allowed_tools: [read_file, codebase_search, grep, run_terminal_cmd]
    preset: safe-shell                   # NEW
    instructions: |
      # ... existing instructions ...
```

---

## Implementation

### 1. Extend Skill Type for Presets

```python
# src/sunwell/skills/types.py — UPDATE Skill dataclass

@dataclass(frozen=True, slots=True)
class Skill:
    """Skill definition with optional preset inheritance."""
    
    # ... existing fields ...
    
    # RFC-092: Permission preset inheritance
    preset: str | None = None
    """Name of permission preset to inherit.
    
    Presets are defined in skills/permission-presets.yaml.
    When set, the skill inherits all permissions and security
    metadata from the preset.
    
    The skill can override specific fields:
    
        preset: read-only
        permissions:
          shell:
            allow: ["git diff"]  # Override just shell
    
    Overrides are merged, not replaced.
    """
```

### 2. Preset Resolution in SkillLoader

```python
# src/sunwell/skills/loader.py — UPDATE skill loading

class SkillLoader:
    """Loads skills with preset resolution."""
    
    def __init__(self, presets_path: Path | None = None):
        self.presets = self._load_presets(presets_path)
    
    def _load_presets(self, path: Path | None) -> dict[str, dict]:
        """Load permission presets from YAML."""
        if path is None:
            path = Path(__file__).parent.parent.parent.parent / "skills" / "permission-presets.yaml"
        
        if not path.exists():
            return {}
        
        import yaml
        with open(path) as f:
            data = yaml.safe_load(f)
        
        return data.get("presets", {})
    
    def resolve_skill(self, skill_data: dict) -> Skill:
        """Resolve skill with preset inheritance."""
        preset_name = skill_data.get("preset")
        
        if preset_name:
            preset = self.presets.get(preset_name)
            if preset is None:
                raise ValueError(f"Unknown preset: {preset_name}")
            
            # Merge preset into skill (skill overrides preset)
            resolved = self._merge_preset(preset, skill_data)
        else:
            resolved = skill_data
        
        return Skill(**resolved)
    
    def _merge_preset(self, preset: dict, skill: dict) -> dict:
        """Deep merge preset with skill (skill wins on conflicts)."""
        result = {}
        
        # Copy preset permissions
        if "permissions" in preset:
            result["permissions"] = dict(preset["permissions"])
        
        # Copy preset security
        if "security" in preset:
            result["security"] = dict(preset["security"])
        
        # Override with skill-specific values
        if "permissions" in skill:
            if "permissions" not in result:
                result["permissions"] = {}
            self._deep_merge(result["permissions"], skill["permissions"])
        
        if "security" in skill:
            if "security" not in result:
                result["security"] = {}
            self._deep_merge(result["security"], skill["security"])
        
        # Copy all other skill fields
        for key, value in skill.items():
            if key not in ("permissions", "security", "preset"):
                result[key] = value
        
        return result
    
    def _deep_merge(self, base: dict, override: dict) -> None:
        """Deep merge override into base (mutates base)."""
        for key, value in override.items():
            if key in base and isinstance(base[key], dict) and isinstance(value, dict):
                self._deep_merge(base[key], value)
            else:
                base[key] = value
```

### 3. Validation: Ensure All Skills Have Permissions

```python
# scripts/validate_skill_permissions.py — NEW FILE

"""Validate all skills have permissions declared (directly or via preset)."""

import sys
from pathlib import Path

import yaml


def validate_skills(skills_dir: Path) -> tuple[list[str], list[str]]:
    """Validate all skills have permissions.
    
    Returns:
        (compliant_skills, non_compliant_skills)
    """
    compliant = []
    non_compliant = []
    
    # Load presets
    presets_path = skills_dir / "permission-presets.yaml"
    presets = set()
    if presets_path.exists():
        with open(presets_path) as f:
            data = yaml.safe_load(f) or {}
            presets = set(data.get("presets", {}).keys())
    
    # Check all skill files
    for skill_file in skills_dir.glob("*.yaml"):
        if skill_file.name == "permission-presets.yaml":
            continue
        
        with open(skill_file) as f:
            data = yaml.safe_load(f) or {}
        
        for skill in data.get("skills", []):
            name = skill.get("name", "unknown")
            
            has_permissions = "permissions" in skill
            has_preset = skill.get("preset") in presets
            
            if has_permissions or has_preset:
                compliant.append(f"{skill_file.name}:{name}")
            else:
                non_compliant.append(f"{skill_file.name}:{name}")
    
    return compliant, non_compliant


def main():
    skills_dir = Path(__file__).parent.parent / "skills"
    
    compliant, non_compliant = validate_skills(skills_dir)
    
    print(f"✅ Compliant: {len(compliant)} skills")
    print(f"❌ Non-compliant: {len(non_compliant)} skills")
    
    if non_compliant:
        print("\nSkills without permissions:")
        for skill in non_compliant:
            print(f"  - {skill}")
        sys.exit(1)
    
    print("\n✅ All skills have permissions declared!")
    sys.exit(0)


if __name__ == "__main__":
    main()
```

---

## Demo Value

### Before (Current State)

```bash
$ sunwell security analyze skills/tool-skills.yaml

📋 Permission Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Skills: 15

⚠️ No permissions declared — using ambient permissions
   Risk: UNKNOWN (cannot analyze)
   
Recommendation: Add permissions to skill definitions
```

### After (RFC-092 Applied)

```bash
$ sunwell security analyze skills/tool-skills.yaml

📋 Permission Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Skills: 15

🔒 Permission Scope
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Filesystem Read:   **/*
Filesystem Write:  **/* (workspace only)
Network:           DENIED
Shell Commands:    python, pytest, ruff, git (status/diff/log)

⚠️ Risk Assessment: LOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ No external network access
✓ No dangerous shell commands
✓ No credential path access
✓ Explicit deny for: rm -rf, sudo, curl, wget, ssh

Skills by Preset:
  read-only (5):      file-read, file-list, code-exploration, git-status, git-diff
  workspace-write (5): file-write, file-edit, shell-mkdir, code-modification, git-commit
  safe-shell (3):     shell-run, test-and-lint, audit-deep
  search-only (1):    file-search
  git-read (1):       git-log
```

### Enterprise Demo Scenario

```bash
$ sunwell run docs-workflow --lens tech-writer

📋 Pipeline Analysis
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
DAG: draft-documentation → audit-documentation → polish-documentation
Skills: 3

🔒 Permission Scope (Aggregated)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
Filesystem Read:   **/*
Filesystem Write:  docs/**/*.md (constrained to docs/)
Network:           DENIED
Shell:             DENIED

⚠️ Risk Assessment: LOW
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
✓ Write scope limited to docs/ directory
✓ No network access (cannot exfiltrate)
✓ No shell access (cannot execute arbitrary commands)
✓ Auto-approved (low risk + internal only)

Executing...
```

---

## Migration Path

### Phase 1: Add Presets File (Non-Breaking)

1. Create `skills/permission-presets.yaml` with preset definitions
2. Update `SkillLoader` to support presets
3. No changes to existing skills yet

### Phase 2: Soft Migration (Warnings)

1. Add `preset:` field to skills one file at a time
2. Run validation script in CI (warn only, don't fail)
3. Log skills without permissions in audit

### Phase 3: Hard Enforcement

1. Require all skills to have permissions (CI fails otherwise)
2. Remove ambient permission fallback in `PermissionAnalyzer`
3. Default to deny-all for skills without permissions

### Phase 4: Documentation & Demos

1. Update skill authoring docs with preset examples
2. Add "Security" section to each skill file header
3. Create demo video showing permission analysis

---

## Preset Assignment Matrix

| Skill File | Skills | Recommended Preset |
|------------|--------|-------------------|
| **tool-skills.yaml** | | |
| file-read, file-list | 2 | `read-only` |
| file-write, file-edit, shell-mkdir | 3 | `workspace-write` |
| file-search | 1 | `search-only` |
| shell-run, test-and-lint | 2 | `safe-shell` |
| git-status, git-diff, git-log | 3 | `git-read` |
| git-commit-workflow, git-branch-workflow | 2 | `git-write` |
| code-exploration | 1 | `read-only` |
| code-modification | 1 | `workspace-write` + git override |
| **core-skills.yaml** | | |
| save-document | 1 | `workspace-write` |
| read-source, list-workspace | 2 | `read-only` |
| analyze-code, find-patterns | 2 | `search-only` |
| dependency-audit | 1 | `safe-shell` |
| **docs-creation-skills.yaml** | | |
| draft-*, create-* | 5 | `workspace-write` |
| **docs-validation-skills.yaml** | | |
| audit-documentation, check-drift | 2 | `read-only` |
| audit-deep, check-health | 2 | `safe-shell` |
| **docs-transformation-skills.yaml** | | |
| polish-*, modularize-* | 3 | `workspace-write` |
| **docs-utility-skills.yaml** | | |
| fix-syntax, format-* | 3 | `workspace-write` |

**Total**: ~50 skills assigned to 6 presets

---

## Success Metrics

1. **Coverage**: 100% of built-in skills have permissions (via preset or direct)
2. **Demo readiness**: `sunwell security analyze` shows meaningful output for all skill files
3. **CI enforcement**: Validation script passes in CI
4. **Documentation**: All preset definitions documented with rationale
5. **Adoption**: 3+ external skill authors use presets within 30 days

---

## Open Questions

### Resolved

| Question | Resolution |
|----------|------------|
| How to avoid repetition? | Presets with inheritance |
| What's the default for network? | Deny all |
| What's the default for shell? | Deny dangerous commands |

### Still Open

1. **Should presets be versioned?** If we change a preset, do existing skills break?
   - *Proposal*: Presets are semantic, changes are additive
   
2. **Can users define their own presets?** 
   - *Proposal*: Yes, in `.sunwell/presets.yaml` (local override)

3. **How to handle skills that need network?**
   - *Proposal*: Use `elevated` preset + explicit `permissions.network.allow`

---

## Cross-Language Impact

### RFC-089 Infrastructure Already Exists

RFC-089 implemented the full cross-language security infrastructure:

| Layer | File | Types | Status |
|-------|------|-------|--------|
| **Python** | `src/sunwell/security/analyzer.py` | `PermissionScope`, `RiskAssessment` | ✅ Exists |
| **Rust** | `studio/src-tauri/src/security.rs` | `PermissionScope`, `RiskAssessment`, `SecurityApproval` | ✅ Exists |
| **TypeScript** | `studio/src/lib/security-types.ts` | Same types | ✅ Exists |
| **Svelte** | `studio/src/stores/security.svelte.ts` | Store + `SecurityApprovalModal` | ✅ Exists |

### RFC-092 Is Python-Only

**Preset resolution happens entirely in Python before data reaches Studio:**

```
┌─────────────────────────────────────────────────────────────────┐
│                    PRESET RESOLUTION FLOW                        │
│                                                                  │
│  YAML:  preset: read-only                                        │
│           ↓                                                      │
│  Python SkillLoader:  resolves preset → PermissionScope          │
│           ↓                                                      │
│  Python PermissionAnalyzer:  computes RiskAssessment             │
│           ↓                                                      │
│  JSON to Studio:  SecurityApproval {                             │
│                     permissions: PermissionScope,  ← RESOLVED    │
│                     risk: RiskAssessment                         │
│                   }                                              │
│           ↓                                                      │
│  Studio:  Displays resolved permissions (preset-agnostic)        │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

**Studio receives the already-resolved `PermissionScope`** — it doesn't need to know about presets.

### Changes Required

| Component | Changes | Required? |
|-----------|---------|-----------|
| **Python: `SkillLoader`** | Add preset resolution logic | ✅ Required |
| **Python: `Skill` dataclass** | Add `preset: str \| None` field | ✅ Required |
| **YAML: `permission-presets.yaml`** | Create preset definitions | ✅ Required |
| **Rust: `security.rs`** | None | ❌ Not needed |
| **TypeScript: `security-types.ts`** | None | ❌ Not needed |
| **Svelte: components** | None | ❌ Not needed |

### Optional Enhancement: Preset Transparency in UI

If we want the UI to show which preset a skill uses (e.g., "Using preset: `read-only`"), we'd need:

```typescript
// studio/src/lib/security-types.ts — OPTIONAL addition

/** Per-skill security info with preset transparency. */
interface SkillSecurityInfo {
  skillName: string;
  preset?: string;  // "read-only", "workspace-write", etc.
  permissions: PermissionScope;
}

interface SecurityApproval {
  // ... existing fields ...
  
  /** NEW: Per-skill breakdown showing preset names. */
  skillsBreakdown?: SkillSecurityInfo[];
}
```

```rust
// studio/src-tauri/src/security.rs — OPTIONAL addition

#[derive(Debug, Clone, Serialize, Deserialize)]
pub struct SkillSecurityInfo {
    #[serde(rename = "skillName")]
    pub skill_name: String,
    
    /// Preset name if skill uses one (e.g., "read-only").
    #[serde(skip_serializing_if = "Option::is_none")]
    pub preset: Option<String>,
    
    pub permissions: PermissionScope,
}
```

**This is a nice-to-have for debugging/transparency, not required for MVP.**

### Risk Assessment

| Risk | Mitigation |
|------|------------|
| **Low**: Python-only changes are self-contained | No cross-language coordination needed |
| **Low**: Existing types handle resolved permissions | No breaking changes to Studio |
| **Future**: Preset transparency requires cross-lang types | Defer to Phase 4 if needed |

---

## References

- **RFC-089**: Security-First Skill Execution — infrastructure for permissions
- **RFC-087**: Skill-Lens DAG — skill dependencies and flow
- `src/sunwell/security/analyzer.py` — `PermissionScope`, `PermissionAnalyzer`
- `src/sunwell/skills/types.py` — `Skill` dataclass
- `skills/*.yaml` — existing skill definitions

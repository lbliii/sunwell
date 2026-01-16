# RFC-011: Arming Sunwell Lenses with Agent Skills

**Status:** Draft  
**Author:** Sunwell Contributors  
**Created:** 2026-01-15  
**Updated:** 2026-01-15  
**Related:** [RFC-010: Sunwell Core](./RFC-010-sunwell.md)

> **Note on Agent Skills**: This RFC defines a skill format inspired by emerging "agent skills" patterns in the ecosystem (Cursor rules, GitHub Copilot instructions, MCP tools). The `skills` schema defined here is self-contained and does not depend on any external specification. Future interoperability with community standards is a goal, not a prerequisite.

---

## Summary

This RFC proposes integrating [Agent Skills](https://agentskills.io) into Sunwell Lenses, creating **Capable Lenses** that combine judgment (heuristics, validation) with action (instructions, scripts, tools).

**Core insight:** Lenses know *how to judge*. Skills know *how to do*. Together, they create agents that can both execute tasks AND evaluate their own output.

---

## Motivation

### The Gap Today

**Agent Skills** provide:
- ✅ Procedural instructions ("do X, then Y")
- ✅ Scripts and tools for execution
- ✅ Portable, version-controlled packages
- ❌ No quality judgment
- ❌ No validation that output is correct
- ❌ No refinement loop

**Sunwell Lenses** provide:
- ✅ Heuristics for quality judgment
- ✅ Validators to check output
- ✅ Personas for adversarial testing
- ✅ Refinement loops
- ❌ No execution capabilities
- ❌ No scripts or tools
- ❌ Limited to text generation

### The Vision: Capable Lenses

```
┌─────────────────────────────────────────────────────────────┐
│                      CAPABLE LENS                           │
├─────────────────────────────────────────────────────────────┤
│  JUDGMENT (Sunwell)          │  ACTION (Agent Skills)       │
│  ─────────────────────────   │  ─────────────────────────   │
│  • Heuristics                │  • Instructions              │
│  • Validators                │  • Scripts                   │
│  • Personas                  │  • Tools                     │
│  • Quality Policy            │  • Resources                 │
│  • Refinement Loop           │  • File Templates            │
└─────────────────────────────────────────────────────────────┘
```

An agent with a Capable Lens can:
1. **Execute** a task using skill instructions
2. **Validate** output using lens validators
3. **Refine** if validation fails
4. **Test** with personas before finalizing

---

## Design

### 1. Lens Schema Extension

Extend the lens schema to include optional skill references:

```yaml
# tech-writer.lens
metadata:
  name: Technical Writer
  version: 2.0.0
  domain: documentation

# Existing Sunwell components
heuristics:
  - name: Signal over Noise
    rule: Every sentence must earn its place
    # ...

validators:
  heuristic:
    - name: no_marketing_fluff
      # ...

personas:
  - name: novice
    # ...

# NEW: Agent Skills integration
skills:
  # Inline skill definition
  - name: create-api-docs
    type: inline
    description: Extract API surface and generate markdown documentation
    compatibility: Requires Python 3.10+ with ast module
    instructions: |
      To create API documentation:
      1. Read the source file
      2. Extract function signatures
      3. Generate markdown with examples
    scripts:
      - name: extract_signatures.py
        content: |
          import ast
          # ... script content
    
  # Reference external skill (Agent Skills fount)
  - name: markdown-formatting
    type: reference
    source: agentskills://markdown-formatter@1.0
    allowed_tools: [Read, Write]  # Pre-approved tools from spec
    
  # Local skill folder (SKILL.md format)
  - name: code-examples
    type: local
    path: ./skills/code-examples/
```

### 2. Skill-Lens Interop Protocol

Define how skills and lenses communicate:

```yaml
# Skill can request lens validation
skill:
  name: write-readme
  instructions: |
    Create a README.md file with:
    - Project description
    - Installation steps
    - Usage examples
  
  # Request Sunwell validation after execution
  validation:
    lens: sunwell://tech-writer@1.0
    validators:
      - no_marketing_fluff
      - evidence_required
    min_confidence: 0.8
    
  # Request persona testing
  personas:
    - novice  # Can a beginner follow this?
    - expert  # Does it satisfy advanced users?
```

### 3. Execution Flow

```
User Request
     │
     ▼
┌─────────────────────┐
│ 1. SKILL EXECUTION  │  ← Agent Skills handle the "doing"
│    Run instructions │
│    Execute scripts  │
│    Use tools        │
└─────────┬───────────┘
          │
          ▼
┌─────────────────────┐
│ 2. LENS VALIDATION  │  ← Sunwell handles the "judging"
│    Run validators   │
│    Check heuristics │
│    Test personas    │
└─────────┬───────────┘
          │
     Pass? ───No──► Refinement Loop
          │              │
         Yes             │
          │              │
          ▼              │
┌─────────────────────┐  │
│ 3. OUTPUT           │◄─┘
│    Validated result │
│    Confidence score │
│    Episode snapshot │
└─────────────────────┘
```

### 4. Skill Activation & Discovery

Skills are activated through two mechanisms:

**Explicit activation** (user requests a skill by name):
```bash
sunwell apply lens.lens "task" --skill create-api-docs
```

**Implicit activation** (classifier matches task to skill):

```python
# Runtime classifier integration (extends RFC-010 classifier)
@dataclass
class SkillAwareClassifier:
    """Extends base classifier with skill matching."""
    
    def classify(self, task: str, lens: Lens) -> ClassificationResult:
        # 1. Check explicit skill mention
        for skill in lens.skills:
            if skill.name in task.lower():
                return ClassificationResult(
                    skill=skill,
                    confidence=0.95,
                    reason="Explicit skill reference in task",
                )
        
        # 2. Semantic match against skill descriptions
        embeddings = self._embed_skills(lens.skills)
        task_embedding = self._embed(task)
        
        matches = self._cosine_similarity(task_embedding, embeddings)
        best_match = max(matches, key=lambda m: m.score)
        
        if best_match.score > 0.7:
            return ClassificationResult(
                skill=best_match.skill,
                confidence=best_match.score,
                reason=f"Semantic match: {best_match.skill.description}",
            )
        
        # 3. No skill match — use lens heuristics only
        return ClassificationResult(skill=None, confidence=1.0, reason="No skill needed")
```

**Activation triggers** (skill descriptions should include these):
- Action verbs: "create", "generate", "extract", "convert"
- Output types: "documentation", "tests", "README"
- File patterns: "*.py", "api/", "src/"

### 5. Error Handling & Failure Modes

Skills can fail at multiple points. Each failure mode has a defined recovery strategy:

| Failure Mode | Detection | Recovery |
|--------------|-----------|----------|
| **Script timeout** | `asyncio.TimeoutError` | Return partial output + error message |
| **Script crash** | `exit_code != 0` | Log stderr, retry once, then fail |
| **Sandbox violation** | `SecurityError` | Abort immediately, log attempt |
| **Validation failure** | `confidence < min_confidence` | Enter refinement loop |
| **Resource exhaustion** | Memory/output limits | Truncate + warn |

**Error result structure**:

```python
@dataclass
class SkillError:
    """Structured error from skill execution."""
    
    phase: Literal["parse", "execute", "validate", "refine"]
    skill_name: str
    message: str
    recoverable: bool
    details: dict[str, Any] = field(default_factory=dict)
    
    # Optional context for debugging
    script_name: str | None = None
    exit_code: int | None = None
    stderr: str | None = None
```

**Retry policy**:

```yaml
# Configurable in lens
skill_retry:
  max_attempts: 3
  backoff_ms: [100, 500, 2000]  # Exponential backoff
  retry_on:
    - timeout
    - validation_failure
  abort_on:
    - security_violation
    - script_crash
```

### 6. Output Contract

Skills and validators communicate through a structured output contract:

```python
@dataclass
class SkillOutput:
    """Output from skill execution, input to validation."""
    
    # Primary output (what the skill produced)
    content: str
    content_type: Literal["text", "code", "markdown", "json"]
    
    # Artifacts (files created/modified)
    artifacts: tuple[Artifact, ...] = ()
    
    # Metadata for validation
    metadata: SkillOutputMetadata = field(default_factory=SkillOutputMetadata)


@dataclass
class SkillOutputMetadata:
    """Metadata passed from skill to validators."""
    
    skill_name: str
    execution_time_ms: int
    scripts_run: tuple[str, ...] = ()
    
    # Hints for validators
    expected_format: str | None = None  # e.g., "markdown with code blocks"
    source_files: tuple[str, ...] = ()  # Files the skill read
    target_files: tuple[str, ...] = ()  # Files the skill wrote


@dataclass
class Artifact:
    """A file artifact produced by skill execution."""
    
    path: Path
    operation: Literal["created", "modified", "deleted"]
    content_hash: str  # SHA-256 for change detection
```

**Validation receives**:
1. `SkillOutput.content` — the primary output to validate
2. `SkillOutput.metadata.source_files` — files to check claims against
3. `SkillOutput.artifacts` — created files to verify

### 7. New CLI Commands

```bash
# Apply lens with skill execution
sunwell apply tech-writer.lens "Create API docs for auth.py" \
  --skill create_api_docs \
  --output docs/auth-api.md

# Execute skill with lens validation
sunwell exec skills/readme-generator/ \
  --validate-with lenses/tech-writer.lens \
  --output README.md

# Export lens as Agent Skill (for tools that only support skills)
sunwell export lenses/tech-writer.lens \
  --format agentskills \
  --output skills/tech-writer/

# Import Agent Skill into lens
sunwell import skills/external-skill/ \
  --into lenses/my-lens.lens

# Validate an existing Agent Skill
sunwell validate-skill skills/code-review/ \
  --with-lens lenses/quality-assurance.lens
```

### 8. Skill Definition Format

Skills within a lens follow a simplified Agent Skills format:

```yaml
skills:
  - name: create-component
    description: Create a React component with tests
    
    # Instructions for the agent
    instructions: |
      ## Goal
      Create a new React component with the following structure:
      
      ## Steps
      1. Create component file at `src/components/{name}.tsx`
      2. Create test file at `src/components/{name}.test.tsx`
      3. Export from `src/components/index.ts`
      
      ## Template
      Use the template in `templates/component.tsx`
    
    # Scripts that can be executed
    scripts:
      - name: scaffold.py
        description: Generate boilerplate files
        language: python
        content: |
          import sys
          from pathlib import Path
          
          name = sys.argv[1]
          # ... scaffolding logic
    
    # File templates
    templates:
      - name: component.tsx
        content: |
          import React from 'react';
          
          interface ${Name}Props {
            // props
          }
          
          export const ${Name}: React.FC<${Name}Props> = (props) => {
            return <div>{/* TODO */}</div>;
          };
    
    # Resources/references
    resources:
      - name: React Best Practices
        url: https://react.dev/learn
      - name: Testing Guide
        path: ./docs/testing.md
```

### 9. Runtime Integration

```python
# New module: sunwell/skills/executor.py

@dataclass
class SkillExecutor:
    """Execute skills with lens validation."""
    
    skill: Skill
    lens: Lens
    model: ModelProtocol
    
    async def execute(
        self,
        context: dict,
        validate: bool = True,
    ) -> SkillResult:
        """Execute skill and optionally validate with lens."""
        
        # 1. Build prompt from skill instructions
        prompt = self._build_skill_prompt(context)
        
        # 2. Execute with model
        result = await self.model.generate(prompt)
        
        # 3. Run any scripts
        if self.skill.scripts:
            result = await self._run_scripts(result, context)
        
        # 4. Validate with lens (if enabled)
        if validate:
            validation = await self._validate_with_lens(result)
            
            # 5. Refine if validation fails
            while not validation.passed:
                result = await self._refine(result, validation)
                validation = await self._validate_with_lens(result)
        
        return SkillResult(
            content=result,
            validation=validation,
            skill_name=self.skill.name,
            lens_name=self.lens.metadata.name,
        )
```

---

## Use Cases

### 1. Documentation Pipeline

```yaml
# docs-pipeline.lens
metadata:
  name: Documentation Pipeline
  version: 1.0.0

heuristics:
  - name: Accurate to Code
    rule: All code examples must be verified against source

validators:
  heuristic:
    - name: code_accuracy
      prompt: Verify all code snippets exist in the referenced files

skills:
  - name: extract-api-surface
    description: Extract public API from Python modules
    scripts:
      - name: extract_api.py
        content: |
          import ast
          import sys
          
          def extract_public_api(filepath):
              with open(filepath) as f:
                  tree = ast.parse(f.read())
              
              api = []
              for node in ast.walk(tree):
                  if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
                      if not node.name.startswith('_'):
                          api.append({
                              'name': node.name,
                              'type': type(node).__name__,
                              'lineno': node.lineno,
                          })
              return api
          
          if __name__ == '__main__':
              import json
              print(json.dumps(extract_public_api(sys.argv[1])))
  
  - name: generate-markdown
    description: Generate markdown from API data
    instructions: |
      Given the extracted API surface, create markdown documentation:
      1. Group by type (classes, functions)
      2. Include signatures with types
      3. Add usage examples
      4. Link to source file:line
```

### 2. Code Review with Auto-Fix

```yaml
# code-review-fix.lens
metadata:
  name: Code Review with Fixes
  version: 1.0.0

heuristics:
  - name: Security First
    rule: Flag potential security issues before style issues

validators:
  heuristic:
    - name: no_secrets
      prompt: Check for hardcoded secrets, API keys, passwords

skills:
  - name: apply-fix
    description: Apply suggested fix to code
    instructions: |
      When a fix is suggested:
      1. Create a backup of the original file
      2. Apply the fix using search/replace
      3. Run linter to verify syntax
      4. Run tests if available
    
    scripts:
      - name: apply_patch.py
        content: |
          import sys
          import shutil
          from pathlib import Path
          
          def apply_fix(filepath, old, new):
              path = Path(filepath)
              backup = path.with_suffix(path.suffix + '.bak')
              shutil.copy(path, backup)
              
              content = path.read_text()
              content = content.replace(old, new)
              path.write_text(content)
              
              return str(backup)
```

### 3. Test Generation

```yaml
# test-generator.lens
metadata:
  name: Test Generator
  version: 1.0.0

heuristics:
  - name: Edge Cases First
    rule: Generate edge case tests before happy path tests

validators:
  deterministic:
    - name: tests_run
      command: pytest {output_file} -v
      success_pattern: "passed"

skills:
  - name: generate-pytest
    description: Generate pytest tests for a module
    instructions: |
      Analyze the source module and generate tests:
      1. One test file per source file
      2. Test all public functions
      3. Include edge cases: empty input, None, type errors
      4. Use fixtures for shared setup
    
    templates:
      - name: test_template.py
        content: |
          import pytest
          from ${module} import ${function}
          
          class Test${Function}:
              def test_basic(self):
                  # Happy path
                  pass
              
              def test_empty_input(self):
                  # Edge case
                  pass
              
              def test_invalid_type(self):
                  with pytest.raises(TypeError):
                      ${function}(None)
```

---

## Compatibility

### Agent Skills Interop

Sunwell will support bidirectional compatibility with Agent Skills:

**Import:** Any valid Agent Skill can be used within a Sunwell lens:
```bash
sunwell import skills/external-skill/ --into lens.yaml
```

**Export:** Sunwell lenses can be exported as Agent Skills for tools that don't support lenses:
```bash
sunwell export lens.yaml --format agentskills
```

The exported skill will include:
- Instructions derived from heuristics
- Validation prompts as "verification steps"
- Persona descriptions as "user contexts"

### SKILL.md Format

When exporting, Sunwell generates a valid `SKILL.md`:

```markdown
# Technical Writer

## Description
Apply professional technical writing expertise with quality validation.

## Instructions
When creating documentation:

1. **Signal over Noise**: Every sentence must earn its place. Remove fluff.
2. **Evidence Required**: Include file:line references for all technical claims.
3. **Progressive Disclosure**: Layer information from overview to detail.
4. **Active Voice**: Use direct, active constructions.

## Verification
After generating content, verify:
- [ ] No marketing words (powerful, flexible, easy, robust, seamless)
- [ ] All code examples have file:line references
- [ ] Most important information appears first
- [ ] Active voice used throughout

## User Contexts
Consider these user perspectives:
- **Novice**: Can a beginner follow without prior knowledge?
- **Expert**: Does it address edge cases and advanced scenarios?
- **Pragmatist**: Is there copy-paste ready code?

## Resources
- Style Guide: ./resources/style-guide.md
- Examples: ./resources/examples/
```

---

## Implementation Plan

### Phase 1: Schema & Instructions Only (Weeks 1-3)

Focus: Get skill *instructions* working without script execution.

- [ ] Extend `Lens` dataclass with `skills: tuple[Skill, ...]` field
- [ ] Extend `LensLoader` to parse `skills:` key
- [ ] Create `Skill` dataclass with `name`, `description`, `instructions`, `templates`
- [ ] Add `--skill` flag to `sunwell apply` command
- [ ] Inject skill instructions into prompt alongside heuristics

**Exit criteria**: `sunwell apply lens.lens "task" --skill create_readme` works with instruction-based skills.

**Why instructions-first**: Validates the integration without sandbox complexity. Most skill value comes from instructions anyway.

### Phase 2: Sandbox Foundation (Weeks 4-6)

Focus: Build secure script execution infrastructure.

- [ ] Create `ScriptSandbox` class with path jailing
- [ ] Implement timeout and resource limits
- [ ] Add trust level enforcement
- [ ] Unit tests for sandbox escape attempts
- [ ] Integration with Python 3.14 subinterpreters (or Docker fallback)

**Exit criteria**: Scripts run in sandbox with verified isolation.

**Security gate**: Phase 2 must pass security review before proceeding.

### Phase 3: Full Skill Execution (Weeks 7-9)

Focus: Connect sandbox to skill runtime.

- [ ] Create `SkillExecutor` class
- [ ] Implement template variable expansion (`${Name}`, `${WORKSPACE_ROOT}`)
- [ ] Wire sandbox into `RuntimeEngine`
- [ ] Add `sunwell exec` command for standalone skill execution
- [ ] Add execution logging (opt-in)

**Exit criteria**: `sunwell exec skills/readme-generator/ --output README.md` works with sandboxed scripts.

### Phase 4: Interop & Export (Weeks 10-11)

Focus: Ecosystem compatibility.

- [ ] Add `sunwell export --format skill-md` (generates SKILL.md)
- [ ] Add `sunwell import` for external skill folders
- [ ] Test export/import round-trip
- [ ] Create 3 example capable lenses (docs, code-review, tests)

**Exit criteria**: Lenses can be exported to standalone skill format.

### Phase 5: Polish & Documentation (Week 12)

- [ ] CLI help text and examples
- [ ] User documentation
- [ ] Security documentation for skill authors
- [ ] Migration guide for existing lens users

---

### Timeline Summary

| Phase | Weeks | Deliverable | Risk |
|-------|-------|-------------|------|
| 1. Schema | 1-3 | Instruction-based skills | Low |
| 2. Sandbox | 4-6 | Secure script execution | **High** |
| 3. Execution | 7-9 | Full skill runtime | Medium |
| 4. Interop | 10-11 | Export/import | Low |
| 5. Polish | 12 | Docs, examples | Low |

**Total: 12 weeks** (vs. original 6 weeks)

**Critical path**: Phase 2 (sandbox) is the highest risk. If blocked, Phase 3-4 can proceed with `trust: none` skills only.

---

## Security Considerations

### Threat Model

Skills introduce executable code into the lens system. Primary threats:

| Threat | Vector | Mitigation |
|--------|--------|------------|
| **Arbitrary code execution** | Malicious script in skill | Sandbox + trust levels |
| **Data exfiltration** | Script reads sensitive files | Path allowlisting |
| **Network abuse** | Script makes unauthorized requests | Network disabled by default |
| **Resource exhaustion** | Infinite loops, memory bombs | Timeouts + resource limits |
| **Path traversal** | `../../../etc/passwd` in paths | Path canonicalization + jail |

### Trust Levels (Enforced)

Trust is not advisory—it maps directly to sandbox configuration:

```yaml
skills:
  - name: trusted-internal
    trust: full          # No sandbox. Use ONLY for your own scripts.
    source: internal
    
  - name: community-skill
    trust: sandboxed     # Default. Restricted execution.
    source: fount://community/skill@1.0
    
  - name: untrusted
    trust: none          # Instructions only. Scripts are IGNORED.
    source: https://example.com/skill.yaml
```

**Trust level enforcement**:

| Trust | Scripts | Filesystem | Network | Timeout |
|-------|---------|------------|---------|---------|
| `full` | ✅ Execute | Full access | Allowed | None |
| `sandboxed` | ✅ Execute | Allowlist only | Blocked | 30s |
| `none` | ❌ Ignored | N/A | N/A | N/A |

### Script Execution Sandbox

Skills with `trust: sandboxed` run in a restricted environment:

```python
@dataclass
class ScriptSandbox:
    """Sandboxed script execution with enforced restrictions."""
    
    allowed_interpreters: frozenset[str] = frozenset({"python", "node", "bash"})
    
    # Filesystem restrictions (paths are canonicalized and jailed)
    read_paths: tuple[Path, ...] = ()   # Empty = workspace root only
    write_paths: tuple[Path, ...] = ()  # Empty = temp dir only
    
    # Network is OFF by default, requires explicit opt-in
    allow_network: bool = False
    
    # Resource limits
    timeout_seconds: int = 30
    max_memory_mb: int = 512
    max_output_bytes: int = 1_000_000  # 1MB
    
    def _canonicalize_and_jail(self, path: Path, jail: Path) -> Path:
        """Resolve path and ensure it stays within jail directory."""
        resolved = (jail / path).resolve()
        if not resolved.is_relative_to(jail.resolve()):
            raise SecurityError(f"Path escapes jail: {path}")
        return resolved
    
    async def execute(self, script: Script, args: list[str]) -> ScriptResult:
        """Execute script in sandbox.
        
        Implementation options (in order of preference):
        1. Python 3.14+ subinterpreters (PEP 734) for Python scripts
        2. Docker/Podman container for multi-language support
        3. OS-level sandboxing (seccomp on Linux, sandbox-exec on macOS)
        """
        if script.language not in self.allowed_interpreters:
            raise SecurityError(f"Interpreter not allowed: {script.language}")
        
        # Prepare execution environment
        jail_dir = Path(self.write_paths[0]) if self.write_paths else Path(tempfile.mkdtemp())
        script_path = jail_dir / script.name
        script_path.write_text(script.content)
        
        # Build command with interpreter
        interpreter_map = {"python": "python3", "node": "node", "bash": "bash"}
        cmd = [interpreter_map[script.language], str(script_path), *args]
        
        try:
            proc = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=str(jail_dir),
                env=self._build_restricted_env(),
            )
            
            stdout, stderr = await asyncio.wait_for(
                proc.communicate(),
                timeout=self.timeout_seconds,
            )
            
            # Enforce output size limit
            if len(stdout) > self.max_output_bytes:
                stdout = stdout[:self.max_output_bytes] + b"\n[OUTPUT TRUNCATED]"
            
            return ScriptResult(
                exit_code=proc.returncode,
                stdout=stdout.decode("utf-8", errors="replace"),
                stderr=stderr.decode("utf-8", errors="replace"),
                timed_out=False,
            )
            
        except asyncio.TimeoutError:
            proc.kill()
            return ScriptResult(
                exit_code=-1,
                stdout="",
                stderr=f"Script timed out after {self.timeout_seconds}s",
                timed_out=True,
            )
    
    def _build_restricted_env(self) -> dict[str, str]:
        """Build environment with minimal variables."""
        return {
            "PATH": "/usr/bin:/bin",
            "HOME": str(self.write_paths[0]) if self.write_paths else "/tmp",
            "LANG": "C.UTF-8",
            # Block common exfiltration vectors
            "http_proxy": "",
            "https_proxy": "",
            "no_proxy": "*",
        }
```

### Default Sandbox Policy

When no explicit paths are configured, the sandbox uses these defaults:

```yaml
sandbox_defaults:
  read_paths:
    - "${WORKSPACE_ROOT}"      # Can read workspace files
    - "${LENS_DIR}"            # Can read lens resources
  write_paths:
    - "${TEMP_DIR}/sunwell-*"  # Can write to temp only
  blocked_patterns:
    - "**/.git/**"             # Never read git internals
    - "**/.env"                # Never read env files
    - "**/secrets/**"          # Never read secrets dirs
```

### Security Checklist for Skill Authors

- [ ] Scripts should be deterministic (same input → same output)
- [ ] Avoid hardcoded paths; use `${WORKSPACE_ROOT}` variable
- [ ] Document required permissions in skill description
- [ ] Prefer `trust: sandboxed` unless `full` is absolutely necessary
- [ ] Test scripts in sandbox before publishing

### Testing Skills

Skills should be tested in isolation before integration. Sunwell provides testing utilities:

**Unit testing scripts**:

```bash
# Test a script in sandbox without full lens execution
sunwell test-script skills/my-skill/scripts/extract.py \
  --input test-input.json \
  --expected test-output.json
```

**Skill dry-run**:

```bash
# Execute skill without writing files (outputs to stdout)
sunwell apply lens.lens "task" --skill create-readme --dry-run
```

**Validation-only mode**:

```bash
# Run validators against existing output
sunwell validate docs/api.md --with-lens lenses/tech-writer.lens
```

**Test fixtures**:

```yaml
# skills/my-skill/tests/fixtures.yaml
- name: basic_case
  input:
    task: "Create README for auth module"
    files: ["src/auth.py"]
  expected:
    contains: ["## Installation", "## Usage"]
    validators_pass: [no_marketing_fluff, evidence_required]
    
- name: edge_case_empty_module
  input:
    task: "Create README"
    files: []
  expected:
    error: "No source files provided"
```

**CI integration**:

```yaml
# .github/workflows/test-skills.yml
- name: Test skills
  run: |
    sunwell test-skills lenses/tech-writer.lens \
      --fixtures skills/*/tests/fixtures.yaml \
      --report junit
```

---

## Design Decisions

### 1. Skill Discovery

**Decision**: Skills are auto-indexed on lens load. No separate manifest needed.

When a lens is loaded, the runtime:
1. Parses inline skills from the `skills:` key
2. Resolves `type: reference` skills from fount
3. Loads `type: local` skills from disk
4. Builds a skill index keyed by `name`

```python
# Runtime behavior
lens = loader.load("my.lens")
lens.skills["create_readme"]  # Direct access by name
```

**Rationale**: Keeps lens files as single source of truth. No separate files to maintain.

### 2. Version Compatibility

**Decision**: Semver ranges with lockfile support.

```yaml
skills:
  - name: external-formatter
    type: reference
    source: fount://formatter@^1.0  # Accept 1.x, not 2.x
```

A `sunwell.lock` file pins exact versions:
```yaml
# sunwell.lock (auto-generated)
skills:
  formatter: 1.2.3
```

**Rationale**: Follows npm/cargo patterns that developers already understand.

### 3. Skill Precedence (Conflict Resolution)

**Decision**: Extend RFC-010's priority matrix to skills.

When lenses are composed and both have a skill with the same name:
1. Higher-priority lens wins (same as heuristic precedence)
2. If equal priority, later lens in `compose:` list wins
3. Skills can be explicitly overridden with `override: true`

```yaml
# child.lens
compose:
  - lens: parent.lens
    priority: 1

skills:
  - name: create-readme        # Overrides parent's create_readme
    override: true
    instructions: |
      Custom implementation...
```

**Rationale**: Consistent with existing lens composition model.

### 4. Parallel Skill Execution

**Decision**: Skills execute sequentially by default. Parallel execution is opt-in.

```yaml
workflows:
  - name: full_docs_pipeline
    steps:
      - skill: extract_api
      - skill: generate_markdown
      - parallel:               # Explicit parallel block
          - skill: lint_output
          - skill: check_links
```

**Rationale**: Sequential is safer and easier to debug. Parallel adds complexity only when needed.

### 5. Skill Dependencies

**Decision**: Skills cannot reference other skills directly. Use workflows for composition.

```yaml
# NOT supported:
skills:
  - name: skill-a
    depends_on: skill_b    # ❌ No skill-to-skill deps

# Supported:
workflows:
  - name: combined
    steps:
      - skill: skill_b     # ✅ Workflows compose skills
      - skill: skill_a
```

**Rationale**: Avoids circular dependency complexity. Workflows are already the composition mechanism.

### 6. Telemetry & Logging

**Decision**: Opt-in logging with privacy controls.

```yaml
# Global config (~/.sunwell/config.yaml)
telemetry:
  skill_execution: true      # Log skill runs
  include_output: false      # Don't log script output (may contain secrets)
  log_path: ~/.sunwell/logs/
```

Script output is logged only at DEBUG level and never sent to remote telemetry.

**Rationale**: Debugging needs visibility, but user data must stay local.

---

## Open Questions

1. **Fount governance**: Who can publish to `fount://`? Verification process?

2. **Skill marketplace**: Should skill authors be able to monetize? Revenue share model?

3. **Breaking changes**: How to communicate breaking skill changes to dependent lenses?

---

## Appendix A: Full Schema

```yaml
# Complete lens-with-skills schema (v2.0)
# Fields marked (required) must be present. Others are optional.

metadata:
  name: string                    # (required) Human-readable name
  version: semver                 # (required) e.g., "1.0.0"
  description: string
  domain: string
  author: string
  license: string

# Sunwell judgment components (unchanged from RFC-010)
heuristics: [...]
anti_heuristics: [...]
validators: {...}
personas: [...]
framework: {...}
quality_policy: {...}

# Skills integration (NEW in RFC-011)
skills:
  - name: string                  # (required) Unique identifier within lens
    description: string           # (required) Human-readable purpose for discovery
    type: inline | reference | local  # (required) How skill is defined
    
    # === Agent Skills spec alignment ===
    compatibility: string         # Environment requirements (Python version, tools, etc.)
    allowed_tools: [string]       # Pre-approved tools, e.g., ["Read", "Write", "Bash(git:*)"]
    
    # === For type: inline ===
    instructions: string          # (required for inline) Markdown instructions
    scripts:
      - name: string              # (required) Filename, e.g., "extract.py"
        description: string
        language: python | node | bash  # (required) Interpreter
        content: string           # (required) Script source code
    templates:
      - name: string              # (required) Template filename
        content: string           # (required) Template content with ${vars}
    resources:
      - name: string              # (required) Resource label
        url: string               # External URL (mutually exclusive with path)
        path: string              # Local path (mutually exclusive with url)
    
    # === For type: reference ===
    source: string                # (required for reference) e.g., "fount://name@^1.0"
    
    # === For type: local ===
    path: string                  # (required for local) e.g., "./skills/my-skill/"
    
    # === Execution settings (all types) ===
    trust: full | sandboxed | none  # Default: sandboxed
    timeout: integer              # Seconds. Default: 30. Range: 1-300.
    override: boolean             # If true, overrides same-name skill from parent
    
    # === Validation binding (all types) ===
    validate_with:
      validators: [string]        # Validator names from this lens
      personas: [string]          # Persona names for testing
      min_confidence: number      # 0.0-1.0. Default: 0.7

# Error handling configuration (NEW in RFC-011)
skill_retry:
  max_attempts: integer           # Default: 3. Range: 1-10.
  backoff_ms: [integer]           # Default: [100, 500, 2000]
  retry_on: [string]              # Events that trigger retry
  abort_on: [string]              # Events that abort immediately
```

### Schema Validation Rules

| Field | Constraint |
|-------|------------|
| `name` | Must match `^[a-z][a-z0-9-]*$` (lowercase, hyphens, no underscores per Agent Skills spec) |
| `name` | Max 64 characters, cannot start/end with hyphen, no consecutive hyphens |
| `description` | Required. Max 1024 characters. |
| `version` | Must be valid semver (`X.Y.Z`) |
| `type: inline` | Requires `instructions` field |
| `type: reference` | Requires `source` field |
| `type: local` | Requires `path` field |
| `compatibility` | Max 500 characters if provided |
| `allowed_tools` | Space-delimited or array of tool patterns |
| `timeout` | Integer in range 1-300 |
| `min_confidence` | Float in range 0.0-1.0 |
| `resources[].url` | Cannot be used with `path` |
| `resources[].path` | Cannot be used with `url` |
| `skill_retry.max_attempts` | Integer in range 1-10 |

### Template Variables

Templates support these built-in variables:

| Variable | Expands To |
|----------|------------|
| `${Name}` | Skill name, PascalCase |
| `${name}` | Skill name, lowercase |
| `${NAME}` | Skill name, UPPERCASE |
| `${WORKSPACE_ROOT}` | Absolute path to workspace |
| `${LENS_DIR}` | Directory containing the lens file |
| `${TEMP_DIR}` | System temp directory |
| `${DATE}` | Current date (YYYY-MM-DD) |
| `${TIMESTAMP}` | Unix timestamp |

---

## Appendix B: JSON Schema

A machine-readable JSON Schema for validation is provided at:

```
sunwell/schemas/lens-v2.schema.json
```

Validate with:
```bash
sunwell validate my.lens --schema v2
```

---

## Appendix C: Migration from v1 Lenses

Existing lenses (without skills) are fully compatible. No changes required.

To add skills to an existing lens:

```yaml
# Before (v1 lens)
lens:
  metadata:
    name: "My Lens"
    version: "1.0.0"
  heuristics:
    # ...

# After (v2 lens with skills)
lens:
  metadata:
    name: "My Lens"
    version: "2.0.0"    # Bump major version
  heuristics:
    # ... (unchanged)
  skills:               # Add skills section
    - name: my-skill
      type: inline
      instructions: |
        ...
```

---

## References

- [RFC-010: Sunwell Core](./RFC-010-sunwell.md)
- [Agent Skills Specification](https://agentskills.io/specification) — Interop target for skill format
- [Python 3.14 Subinterpreters (PEP 734)](https://peps.python.org/pep-0734/)
- [Deno Permissions Model](https://deno.land/manual/basics/permissions) — Inspiration for trust levels
- [Cursor Rules Documentation](https://docs.cursor.com/context/rules) — Related prior art

---

## Changelog

| Date | Change |
|------|--------|
| 2026-01-15 | Initial draft |
| 2026-01-15 | Added security threat model, trust level enforcement |
| 2026-01-15 | Resolved open questions (discovery, precedence, parallel execution) |
| 2026-01-15 | Extended timeline to 12 weeks with phased rollout |
| 2026-01-15 | Added schema validation rules and template variables |
| 2026-01-15 | Removed external spec dependency; schema is self-contained |
| 2026-01-15 | Added `compatibility`, `allowed_tools` fields (agentskills.io alignment) |
| 2026-01-15 | Added skill activation & classifier integration (Section 4) |
| 2026-01-15 | Added error handling & failure modes (Section 5) |
| 2026-01-15 | Added output contract specification (Section 6) |
| 2026-01-15 | Completed sandbox execute implementation |
| 2026-01-15 | Made `description` required (needed for implicit skill discovery) || 2026-01-15 | Added Testing Skills section with fixtures and CI integration |
| 2026-01-15 | Normalized skill names to use hyphens (per Agent Skills spec) |

"""RFC-011 Phase 4: Skill Import/Export for ecosystem interoperability.

This module provides:
- Export: Convert lens skills to standalone SKILL.md format
- Import: Import external skill folders into a lens
- Validate: Check skill folders against lens validators

SKILL.md Format (for ecosystem compatibility):
```markdown
# Skill Name

## Description
Brief description of what the skill does.

## Instructions
Detailed instructions for the agent.

## Scripts
Embedded scripts (optional).

## Templates  
File templates (optional).

## Verification
Validation checklist (optional).
```
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import TYPE_CHECKING
import re
import yaml

if TYPE_CHECKING:
    from sunwell.core.lens import Lens
    from sunwell.skills.types import Skill


@dataclass
class SkillExporter:
    """Export lens skills to standalone formats."""

    def export_skill_md(self, skill: "Skill", lens: "Lens" | None = None) -> str:
        """Export a single skill to SKILL.md format.
        
        Args:
            skill: The skill to export
            lens: Optional lens to include validation rules from
            
        Returns:
            Markdown content for SKILL.md
        """
        sections = []
        
        # Title
        sections.append(f"# {skill.name}\n")
        
        # Description
        sections.append("## Description\n")
        sections.append(f"{skill.description}\n")
        
        # Compatibility (if specified)
        if skill.compatibility:
            sections.append("## Compatibility\n")
            sections.append(f"{skill.compatibility}\n")
        
        # Instructions
        if skill.instructions:
            sections.append("## Instructions\n")
            # Escape any ## headers in instructions to ### to avoid section conflicts
            instructions = skill.instructions
            # Convert any ## headers to ### (preserve hierarchy)
            instructions = re.sub(r'^## ', '### ', instructions, flags=re.MULTILINE)
            sections.append(f"{instructions}\n")
        
        # Scripts
        if skill.scripts:
            sections.append("## Scripts\n")
            for script in skill.scripts:
                sections.append(f"### {script.name}\n")
                if script.description:
                    sections.append(f"{script.description}\n")
                sections.append(f"**Language:** {script.language}\n")
                sections.append(f"```{script.language}\n{script.content}\n```\n")
        
        # Templates
        if skill.templates:
            sections.append("## Templates\n")
            for template in skill.templates:
                sections.append(f"### {template.name}\n")
                # Detect language from filename
                ext = Path(template.name).suffix.lstrip('.')
                lang = {
                    'py': 'python', 'js': 'javascript', 'ts': 'typescript',
                    'tsx': 'typescript', 'jsx': 'javascript', 'md': 'markdown',
                    'yaml': 'yaml', 'yml': 'yaml', 'json': 'json',
                    'sh': 'bash', 'bash': 'bash',
                }.get(ext, '')
                sections.append(f"```{lang}\n{template.content}\n```\n")
        
        # Resources
        if skill.resources:
            sections.append("## Resources\n")
            for resource in skill.resources:
                if resource.url:
                    sections.append(f"- [{resource.name}]({resource.url})\n")
                elif resource.path:
                    sections.append(f"- {resource.name}: `{resource.path}`\n")
        
        # Verification (from lens validators if available)
        if lens and skill.validate_with.validators:
            sections.append("## Verification\n")
            sections.append("After generating content, verify:\n")
            for validator_name in skill.validate_with.validators:
                # Try to find the validator in the lens
                validator = None
                for v in lens.heuristic_validators:
                    if v.name == validator_name:
                        validator = v
                        break
                
                if validator and hasattr(validator, 'prompt'):
                    sections.append(f"- [ ] **{validator_name}**: {validator.prompt[:100]}...\n")
                else:
                    sections.append(f"- [ ] {validator_name}\n")
            
            if skill.validate_with.min_confidence:
                sections.append(f"\n**Minimum confidence:** {skill.validate_with.min_confidence * 100:.0f}%\n")
        
        # Metadata footer
        sections.append("---\n")
        sections.append(f"*Exported from Sunwell lens*\n")
        if skill.trust:
            sections.append(f"*Trust level: {skill.trust.value}*\n")
        
        return "\n".join(sections)

    def export_lens_skills(
        self, 
        lens: "Lens", 
        output_dir: Path,
        format: str = "skill-md",
    ) -> list[Path]:
        """Export all skills from a lens to a directory.
        
        Args:
            lens: The lens to export skills from
            output_dir: Directory to write skill files
            format: Export format ('skill-md' or 'yaml')
            
        Returns:
            List of created file paths
        """
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        
        created_files = []
        
        for skill in lens.skills:
            if format == "skill-md":
                content = self.export_skill_md(skill, lens)
                file_path = output_dir / skill.name / "SKILL.md"
                file_path.parent.mkdir(parents=True, exist_ok=True)
                file_path.write_text(content)
            elif format == "yaml":
                content = self._skill_to_yaml(skill)
                file_path = output_dir / f"{skill.name}.yaml"
                file_path.write_text(content)
            else:
                raise ValueError(f"Unknown format: {format}")
            
            created_files.append(file_path)
        
        return created_files

    def _skill_to_yaml(self, skill: "Skill") -> str:
        """Convert skill to YAML format."""
        data = {
            "skill": {
                "name": skill.name,
                "description": skill.description,
                "type": skill.skill_type.value,
                "trust": skill.trust.value,
            }
        }
        
        if skill.compatibility:
            data["skill"]["compatibility"] = skill.compatibility
        if skill.instructions:
            data["skill"]["instructions"] = skill.instructions
        if skill.scripts:
            data["skill"]["scripts"] = [
                {
                    "name": s.name,
                    "language": s.language,
                    "content": s.content,
                    **({"description": s.description} if s.description else {}),
                }
                for s in skill.scripts
            ]
        if skill.templates:
            data["skill"]["templates"] = [
                {"name": t.name, "content": t.content}
                for t in skill.templates
            ]
        if skill.resources:
            data["skill"]["resources"] = [
                {
                    "name": r.name,
                    **({"url": r.url} if r.url else {}),
                    **({"path": r.path} if r.path else {}),
                }
                for r in skill.resources
            ]
        
        return yaml.dump(data, default_flow_style=False, sort_keys=False, allow_unicode=True)


@dataclass
class SkillImporter:
    """Import external skills into lenses."""

    def import_skill_md(self, skill_path: Path) -> dict:
        """Parse a SKILL.md file into skill data.
        
        Args:
            skill_path: Path to SKILL.md file or directory containing it
            
        Returns:
            Dictionary of skill data suitable for LensLoader
        """
        # Handle both file and directory paths
        if skill_path.is_dir():
            skill_file = skill_path / "SKILL.md"
        else:
            skill_file = skill_path
        
        if not skill_file.exists():
            raise FileNotFoundError(f"Skill file not found: {skill_file}")
        
        content = skill_file.read_text()
        return self._parse_skill_md(content, skill_file.parent.name)

    def _parse_skill_md(self, content: str, default_name: str = "imported-skill") -> dict:
        """Parse SKILL.md markdown into skill data structure."""
        skill_data = {
            "name": default_name,
            "description": "",
            "type": "inline",
            "trust": "sandboxed",
        }
        
        # Extract title (# Skill Name)
        title_match = re.search(r'^#\s+(.+)$', content, re.MULTILINE)
        if title_match:
            skill_data["name"] = self._slugify(title_match.group(1))
        
        # Extract sections
        sections = self._split_sections(content)
        
        if "description" in sections:
            skill_data["description"] = sections["description"].strip()
        
        if "compatibility" in sections:
            skill_data["compatibility"] = sections["compatibility"].strip()
        
        if "instructions" in sections and sections["instructions"]:
            instructions = sections["instructions"].strip()
            # Remove footer markers if present
            if "---" in instructions:
                instructions = instructions.split("---")[0].strip()
            skill_data["instructions"] = instructions
        else:
            # Reconstruct instructions from common sub-sections if instructions is empty
            instruction_parts = []
            for key in ["goal", "process", "output", "steps", "usage"]:
                if key in sections and sections[key]:
                    content = sections[key]
                    # Remove footer markers if present
                    if "---" in content:
                        content = content.split("---")[0].strip()
                    if content:
                        instruction_parts.append(f"## {key.title()}\n{content}")
            if instruction_parts:
                skill_data["instructions"] = "\n\n".join(instruction_parts)
        
        if "scripts" in sections:
            skill_data["scripts"] = self._parse_scripts_section(sections["scripts"])
        
        if "templates" in sections:
            skill_data["templates"] = self._parse_templates_section(sections["templates"])
        
        if "resources" in sections:
            skill_data["resources"] = self._parse_resources_section(sections["resources"])
        
        return skill_data

    def _split_sections(self, content: str) -> dict[str, str]:
        """Split markdown into sections by ## headers.
        
        Preserves all content under each ## header, including nested ### headers.
        """
        sections = {}
        current_section = None
        current_content = []
        
        for line in content.split('\n'):
            # Only split on ## headers (not ### or deeper)
            if line.startswith('## ') and not line.startswith('### '):
                if current_section:
                    sections[current_section] = '\n'.join(current_content).strip()
                current_section = line[3:].strip().lower()
                current_content = []
            elif current_section:
                current_content.append(line)
        
        if current_section:
            sections[current_section] = '\n'.join(current_content).strip()
        
        return sections

    def _parse_scripts_section(self, content: str) -> list[dict]:
        """Parse scripts from markdown section."""
        scripts = []
        
        # Find all ### headers (script names) and their code blocks
        script_pattern = r'###\s+(.+?)\n(.*?)(?=###|\Z)'
        code_pattern = r'```(\w+)?\n(.*?)\n```'
        
        for match in re.finditer(script_pattern, content, re.DOTALL):
            script_name = match.group(1).strip()
            script_body = match.group(2)
            
            # Find code block in script body
            code_match = re.search(code_pattern, script_body, re.DOTALL)
            if code_match:
                language = code_match.group(1) or "python"
                code = code_match.group(2)
                
                # Extract description (text before code block)
                desc_match = re.search(r'^(.+?)(?=\*\*|\n```)', script_body, re.DOTALL)
                description = desc_match.group(1).strip() if desc_match else None
                
                scripts.append({
                    "name": script_name,
                    "language": language,
                    "content": code,
                    **({"description": description} if description else {}),
                })
        
        return scripts

    def _parse_templates_section(self, content: str) -> list[dict]:
        """Parse templates from markdown section."""
        templates = []
        
        # Find all ### headers (template names) and their code blocks
        template_pattern = r'###\s+(.+?)\n(.*?)(?=###|\Z)'
        code_pattern = r'```\w*\n(.*?)\n```'
        
        for match in re.finditer(template_pattern, content, re.DOTALL):
            template_name = match.group(1).strip()
            template_body = match.group(2)
            
            code_match = re.search(code_pattern, template_body, re.DOTALL)
            if code_match:
                templates.append({
                    "name": template_name,
                    "content": code_match.group(1),
                })
        
        return templates

    def _parse_resources_section(self, content: str) -> list[dict]:
        """Parse resources from markdown section."""
        resources = []
        
        # Parse markdown links: - [Name](url) or - Name: `path`
        link_pattern = r'-\s+\[(.+?)\]\((.+?)\)'
        path_pattern = r'-\s+(.+?):\s+`(.+?)`'
        
        for match in re.finditer(link_pattern, content):
            resources.append({
                "name": match.group(1),
                "url": match.group(2),
            })
        
        for match in re.finditer(path_pattern, content):
            if match.group(1) not in [r["name"] for r in resources]:
                resources.append({
                    "name": match.group(1),
                    "path": match.group(2),
                })
        
        return resources

    def _slugify(self, text: str) -> str:
        """Convert text to slug format (lowercase, hyphenated)."""
        slug = text.lower()
        slug = re.sub(r'[^\w\s-]', '', slug)
        slug = re.sub(r'[\s_]+', '-', slug)
        return slug.strip('-')

    def import_skill_yaml(self, skill_path: Path) -> dict:
        """Parse a skill YAML file into skill data.
        
        Args:
            skill_path: Path to skill YAML file
            
        Returns:
            Dictionary of skill data suitable for LensLoader
        """
        content = skill_path.read_text()
        data = yaml.safe_load(content)
        
        # Handle both {skill: {...}} and direct {...} formats
        if "skill" in data:
            return data["skill"]
        return data

    def import_skill_folder(self, folder_path: Path) -> dict:
        """Import a skill from a folder.
        
        Looks for:
        1. SKILL.md - Markdown format
        2. skill.yaml / skill.yml - YAML format
        3. SKILL.yaml - Alternative YAML format
        
        Args:
            folder_path: Path to skill folder
            
        Returns:
            Dictionary of skill data
        """
        folder_path = Path(folder_path)
        
        # Check for SKILL.md first (preferred format)
        skill_md = folder_path / "SKILL.md"
        if skill_md.exists():
            return self.import_skill_md(skill_md)
        
        # Check for YAML formats
        for yaml_name in ["skill.yaml", "skill.yml", "SKILL.yaml", "SKILL.yml"]:
            yaml_path = folder_path / yaml_name
            if yaml_path.exists():
                return self.import_skill_yaml(yaml_path)
        
        raise FileNotFoundError(
            f"No skill definition found in {folder_path}. "
            f"Expected SKILL.md or skill.yaml"
        )


@dataclass
class SkillValidator:
    """Validate skill folders against lens quality standards."""
    
    def validate_skill_folder(
        self,
        skill_path: Path,
        lens: "Lens" | None = None,
    ) -> "SkillValidationResult":
        """Validate a skill folder for correctness.
        
        Args:
            skill_path: Path to skill folder or file
            lens: Optional lens to validate against
            
        Returns:
            Validation result with issues and score
        """
        issues: list[str] = []
        warnings: list[str] = []
        
        # Import the skill to check structure
        importer = SkillImporter()
        try:
            skill_data = importer.import_skill_folder(skill_path)
        except FileNotFoundError as e:
            return SkillValidationResult(
                valid=False,
                score=0.0,
                issues=[str(e)],
                warnings=[],
            )
        except Exception as e:
            return SkillValidationResult(
                valid=False,
                score=0.0,
                issues=[f"Parse error: {e}"],
                warnings=[],
            )
        
        # Required fields
        if not skill_data.get("name"):
            issues.append("Missing required field: name")
        if not skill_data.get("description"):
            issues.append("Missing required field: description")
        
        # Recommended fields
        if not skill_data.get("instructions"):
            warnings.append("Missing instructions - skill provides no guidance")
        
        # Validate scripts
        for script in skill_data.get("scripts", []):
            if not script.get("name"):
                issues.append("Script missing name")
            if not script.get("content"):
                issues.append(f"Script '{script.get('name', 'unknown')}' has no content")
            if script.get("language") not in ["python", "bash", "javascript", "typescript", "node"]:
                warnings.append(
                    f"Script '{script.get('name')}' uses unusual language: {script.get('language')}"
                )
        
        # Validate templates
        for template in skill_data.get("templates", []):
            if not template.get("name"):
                issues.append("Template missing name")
            if not template.get("content"):
                issues.append(f"Template '{template.get('name', 'unknown')}' has no content")
        
        # Check for variable placeholders in templates
        for template in skill_data.get("templates", []):
            content = template.get("content", "")
            if "${" not in content and "{" not in content:
                warnings.append(
                    f"Template '{template.get('name')}' has no variables - may not be dynamic"
                )
        
        # Validate against lens if provided
        if lens:
            # Check if skill name follows lens conventions
            skill_name = skill_data.get("name", "")
            if "_" in skill_name:
                warnings.append(
                    f"Skill name '{skill_name}' uses underscores - prefer hyphens"
                )
            
            # Check for required validators
            validate_with = skill_data.get("validate_with", {})
            validators = validate_with.get("validators", [])
            
            lens_validators = {v.name for v in lens.heuristic_validators}
            for v in validators:
                if v not in lens_validators:
                    warnings.append(f"Validator '{v}' not found in lens")
        
        # Calculate score
        total_checks = 10
        passed_checks = total_checks - len(issues) - (len(warnings) * 0.5)
        score = max(0.0, min(1.0, passed_checks / total_checks))
        
        return SkillValidationResult(
            valid=len(issues) == 0,
            score=score,
            issues=issues,
            warnings=warnings,
            skill_data=skill_data,
        )


@dataclass
class SkillValidationResult:
    """Result of skill validation."""
    
    valid: bool
    score: float
    issues: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    skill_data: dict | None = None
    
    def summary(self) -> str:
        """Generate human-readable summary."""
        status = "✅ Valid" if self.valid else "❌ Invalid"
        lines = [
            f"{status} (Score: {self.score * 100:.0f}%)",
        ]
        
        if self.issues:
            lines.append("\nIssues:")
            for issue in self.issues:
                lines.append(f"  ❌ {issue}")
        
        if self.warnings:
            lines.append("\nWarnings:")
            for warning in self.warnings:
                lines.append(f"  ⚠️ {warning}")
        
        return "\n".join(lines)

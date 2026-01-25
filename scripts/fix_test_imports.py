#!/usr/bin/env python3
"""Fix import paths in test files after migration."""

import re
from pathlib import Path

# Import mappings: old -> new
IMPORT_MAPPINGS = [
    # Core models
    (r"from sunwell\.core\.lens import", "from sunwell.foundation.core.lens import"),
    (r"from sunwell\.core\.heuristic import", "from sunwell.core.models.heuristic import"),
    (r"from sunwell\.core\.persona import", "from sunwell.core.models.persona import"),
    (r"from sunwell\.core\.validator import", "from sunwell.core.models.validator import"),
    (r"from sunwell\.core\.types import", "from sunwell.core.types.types import"),
    
    # Feature modules
    (r"from sunwell\.backlog\.", "from sunwell.features.backlog."),
    (r"from sunwell\.incremental\.", "from sunwell.agent.incremental."),
    (r"from sunwell\.navigation\.", "from sunwell.knowledge.navigation."),
    (r"from sunwell\.fount\.", "from sunwell.features.fount."),
    
    # Schema loader
    (r"from sunwell\.schema\.loader import", "from sunwell.foundation.schema.loader.loader import"),
    
    # CLI modules
    (r"from sunwell\.interface\.cli\.main import", "from sunwell.interface.cli.core.main import"),
    (r"from sunwell\.interface\.cli\.team_cmd import", "from sunwell.interface.cli.commands.team_cmd import"),
    (r"from sunwell\.interface\.block_actions import", "from sunwell.interface.generative.block_actions import"),
    
    # Agent modules
    (r"from sunwell\.agent\.gates import", "from sunwell.agent.validation.gates import"),
    (r"from sunwell\.agent\.ephemeral_lens import", "from sunwell.agent.utils.ephemeral_lens import"),
    
    # Quality modules (handle both with and without trailing dot)
    (r"from sunwell\.confidence import", "from sunwell.quality.confidence import"),
    (r"from sunwell\.confidence\.", "from sunwell.quality.confidence."),
    (r"from sunwell\.guardrails import", "from sunwell.quality.guardrails import"),
    (r"from sunwell\.guardrails\.", "from sunwell.quality.guardrails."),
    (r"from sunwell\.security\.", "from sunwell.quality.security."),
    (r"from sunwell\.weakness\.", "from sunwell.quality.weakness."),
    
    # Memory modules
    (r"from sunwell\.lineage\.", "from sunwell.memory.lineage."),
    (r"from sunwell\.simulacrum\.", "from sunwell.memory.simulacrum."),
    
    # Planning modules
    (r"from sunwell\.skills\.", "from sunwell.planning.skills."),
    
    # Agent modules (additional)
    (r"from sunwell\.agent\.request import", "from sunwell.agent.utils.request import"),
    (r"from sunwell\.agent\.metrics import", "from sunwell.agent.utils.metrics import"),
    (r"from sunwell\.agent\.evaluation\.", "from sunwell.benchmark.evaluation."),
    
    # Interface modules
    (r"from sunwell\.interface\.types import", "from sunwell.interface.core.types import"),
    (r"from sunwell\.interface\.cli\.lineage_cmd import", "from sunwell.interface.cli.commands.lineage_cmd import"),
    
    # Other modules
    (r"from sunwell\.integration import", "from sunwell.agent.events.integration import"),
    (r"from sunwell\.integration\.", "from sunwell.agent.events.integration."),
    
    # Protocol - fix the adapters path
    (r"from sunwell\.models\.adapters\.protocol import", "from sunwell.models.core.protocol import"),
    
    # Other common patterns
    (r"from sunwell\.models\.mock import", "from sunwell.models.adapters.mock import"),
    (r"from sunwell\.models\.protocol import", "from sunwell.models.core.protocol import"),
    (r"from sunwell\.intelligence\.codebase import", "from sunwell.knowledge.codebase import"),
    (r"from sunwell\.providers\.", "from sunwell.models.providers."),
    
    # Identity store - special case
    (r"from sunwell\.identity\.store import Identity", "from sunwell.core.models.heuristic import Identity"),
    
    # Identity modules
    (r"from sunwell\.identity\.extractor import", "from sunwell.identity.extraction.extractor import"),
    
    # Agent modules (additional)
    (r"from sunwell\.agent\.thinking import", "from sunwell.agent.utils.thinking import"),
    (r"from sunwell\.agent\.budget import", "from sunwell.agent.utils.budget import"),
    (r"from sunwell\.agent\.fixer import", "from sunwell.agent.execution.fixer import"),
    (r"from sunwell\.agent\.spawn import", "from sunwell.agent.utils.spawn import"),
    
    # Interface modules (additional)
    (r"from sunwell\.interface\.executor import", "from sunwell.interface.generative.executor import"),
    (r"from sunwell\.interface\.views import", "from sunwell.interface.generative.views import"),
    (r"from sunwell\.interface\.router import", "from sunwell.interface.generative.router import"),
    
    # Tools modules
    (r"from sunwell\.tools\.types import", "from sunwell.tools.core.types import"),
    (r"from sunwell\.tools\.sunwell_tools import", "from sunwell.tools.definitions.sunwell import"),
    (r"from sunwell\.tools\.run_analyzer import", "from sunwell.tools.tracking.analyzer import"),
    (r"from sunwell\.tools\.web_search import", "from sunwell.tools.providers.web_search import"),
    (r"from sunwell\.tools\.invocation_tracker import", "from sunwell.tools.tracking.tracker import"),
    
    # Feature modules (additional)
    (r"from sunwell\.team import", "from sunwell.features.team import"),
    (r"from sunwell\.team\.", "from sunwell.features.team."),
    
    # Chat modules
    (r"from sunwell\.chat import", "from sunwell.interface.cli.chat import"),
    (r"from sunwell\.chat\.", "from sunwell.interface.cli.chat."),
    
    # Convergence modules
    (r"from sunwell\.convergence import", "from sunwell.planning.naaru.convergence import"),
    (r"from sunwell\.convergence\.", "from sunwell.planning.naaru.convergence."),
    
    # Memory modules (additional)
    (r"from sunwell\.memory\.persistent import", "from sunwell.memory.facade.persistent import"),
    (r"from sunwell\.memory\.types import", "from sunwell.memory.core.types import"),
    
    # Project modules
    (r"from sunwell\.project\.", "from sunwell.knowledge.project."),
    
    # Workflow modules
    (r"from sunwell\.workflow\.", "from sunwell.features.workflow."),
    
    # Server modules
    (r"from sunwell\.server\.", "from sunwell.interface.server."),
]

def fix_imports_in_file(file_path: Path) -> bool:
    """Fix imports in a single file. Returns True if file was modified."""
    try:
        content = file_path.read_text(encoding="utf-8")
        original = content
        
        for old_pattern, new_pattern in IMPORT_MAPPINGS:
            content = re.sub(old_pattern, new_pattern, content)
        
        if content != original:
            file_path.write_text(content, encoding="utf-8")
            return True
        return False
    except Exception as e:
        print(f"Error processing {file_path}: {e}")
        return False

def main():
    """Fix imports in all test files."""
    tests_dir = Path(__file__).parent.parent / "tests"
    test_files = list(tests_dir.rglob("*.py"))
    
    fixed_count = 0
    for test_file in test_files:
        if fix_imports_in_file(test_file):
            print(f"Fixed: {test_file.relative_to(tests_dir.parent)}")
            fixed_count += 1
    
    print(f"\n✅ Fixed imports in {fixed_count} files")

if __name__ == "__main__":
    main()

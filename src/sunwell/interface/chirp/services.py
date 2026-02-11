"""Service providers for Chirp pages.

Provides access to Sunwell core services:
- Configuration management
- Project registry
- Background session management
- Skill/spell registries
- Memory services
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from sunwell.foundation.config import get_config, SunwellConfig, reset_config
from sunwell.knowledge.project.registry import ProjectRegistry

logger = logging.getLogger(__name__)


@dataclass
class ConfigService:
    """Service for accessing and modifying Sunwell configuration."""

    def _get_config_path(self) -> Path:
        """Get path to user config file.

        Returns:
            Path to .sunwell/config.yaml (project) or ~/.sunwell/config.yaml (user)
        """
        # Prefer project-local config
        project_config = Path(".sunwell/config.yaml")
        if project_config.exists():
            return project_config

        # Fall back to user-global config
        user_config = Path.home() / ".sunwell" / "config.yaml"
        user_config.parent.mkdir(parents=True, exist_ok=True)
        return user_config

    def _load_config_dict(self) -> dict[str, Any]:
        """Load current config file as dict.

        Returns:
            Config dict (empty if file doesn't exist)
        """
        config_path = self._get_config_path()
        if not config_path.exists():
            return {}

        try:
            with open(config_path) as f:
                return yaml.safe_load(f) or {}
        except Exception as e:
            logger.warning("Failed to load config from %s: %s", config_path, e)
            return {}

    def _save_config_dict(self, config_dict: dict[str, Any]) -> bool:
        """Save config dict to YAML file.

        Args:
            config_dict: Config dictionary to save

        Returns:
            True if successful
        """
        config_path = self._get_config_path()

        try:
            config_path.parent.mkdir(parents=True, exist_ok=True)
            with open(config_path, "w") as f:
                yaml.safe_dump(config_dict, f, default_flow_style=False, sort_keys=False)

            # Reset cached config so next get_config() reloads
            reset_config()

            logger.info("Saved config to %s", config_path)
            return True
        except Exception as e:
            logger.error("Failed to save config to %s: %s", config_path, e)
            return False

    def get_config(self) -> SunwellConfig:
        """Get current configuration."""
        return get_config()

    def get_provider_config(self) -> dict[str, Any]:
        """Get provider configuration for Settings page.

        Returns:
            Dict with provider settings (model, api_key, etc.)
        """
        config = get_config()

        # Extract provider info from config
        # TODO: Update based on actual config structure
        return {
            "default_model": getattr(config, "default_model", "claude-sonnet-4-5"),
            "provider": "anthropic",  # Default to Anthropic
            "api_key_configured": True,  # TODO: Check if API key exists
            "ollama": {
                "base_url": config.ollama.base_url if hasattr(config, "ollama") else "http://localhost:11434",
                "enabled": True,
            },
        }

    def get_embedding_config(self) -> dict[str, Any]:
        """Get embedding configuration."""
        config = get_config()

        if hasattr(config, "embedding"):
            return {
                "prefer_local": config.embedding.prefer_local,
                "ollama_model": config.embedding.ollama_model,
                "fallback_to_hash": config.embedding.fallback_to_hash,
            }

        return {
            "prefer_local": True,
            "ollama_model": "all-minilm",
            "fallback_to_hash": True,
        }

    def get_preferences(self) -> dict[str, Any]:
        """Get user preferences."""
        config = get_config()

        return {
            "auto_archive": getattr(getattr(config, "simulacrum", None), "lifecycle", {}).get("auto_archive", True) if hasattr(config, "simulacrum") else True,
            "spawn_enabled": getattr(getattr(config, "simulacrum", None), "spawn", {}).get("enabled", True) if hasattr(config, "simulacrum") else True,
            "max_simulacrums": getattr(getattr(config, "simulacrum", None), "spawn", {}).get("max_simulacrums", 20) if hasattr(config, "simulacrum") else 20,
        }

    def update_provider_config(
        self,
        provider: str,
        api_key: str | None = None,
        model: str | None = None,
        ollama_base: str | None = None,
    ) -> bool:
        """Update provider configuration.

        Args:
            provider: Provider name (ollama, anthropic, openai)
            api_key: Optional API key to set
            model: Optional default model
            ollama_base: Optional Ollama base URL

        Returns:
            True if successful
        """
        config_dict = self._load_config_dict()

        # Ensure model section exists
        if "model" not in config_dict:
            config_dict["model"] = {}

        # Update provider
        config_dict["model"]["default_provider"] = provider

        # Update model if provided
        if model:
            config_dict["model"]["default_model"] = model

        # Update Ollama config if provided
        if ollama_base:
            if "ollama" not in config_dict:
                config_dict["ollama"] = {}
            config_dict["ollama"]["base_url"] = ollama_base

        # TODO: Securely store API keys (use keyring or encrypted storage)
        # For now, just log that we would save them
        if api_key:
            logger.info("API key update requested for provider: %s (not persisted - use keyring)", provider)

        return self._save_config_dict(config_dict)

    def update_preferences(self, preferences: dict[str, Any]) -> bool:
        """Update user preferences.

        Args:
            preferences: Dict of preference key-value pairs (theme, auto_save, etc.)

        Returns:
            True if successful
        """
        config_dict = self._load_config_dict()

        # Map UI preferences to config structure
        # Theme, auto_save, show_token_counts go to root or appropriate sections

        # Simulacrum preferences
        if "auto_archive" in preferences or "spawn_enabled" in preferences or "max_simulacrums" in preferences:
            if "simulacrum" not in config_dict:
                config_dict["simulacrum"] = {}

            if "auto_archive" in preferences:
                if "lifecycle" not in config_dict["simulacrum"]:
                    config_dict["simulacrum"]["lifecycle"] = {}
                config_dict["simulacrum"]["lifecycle"]["auto_archive"] = preferences["auto_archive"]

            if "spawn_enabled" in preferences:
                if "spawn" not in config_dict["simulacrum"]:
                    config_dict["simulacrum"]["spawn"] = {}
                config_dict["simulacrum"]["spawn"]["enabled"] = preferences["spawn_enabled"]

            if "max_simulacrums" in preferences:
                if "spawn" not in config_dict["simulacrum"]:
                    config_dict["simulacrum"]["spawn"] = {}
                config_dict["simulacrum"]["spawn"]["max_simulacrums"] = preferences["max_simulacrums"]

        # Note: theme, auto_save, show_token_counts are UI-only preferences
        # They don't map to Sunwell core config, so we'd need a separate
        # studio config file for these. For now, acknowledge but don't persist.
        if "theme" in preferences or "auto_save" in preferences or "show_token_counts" in preferences:
            logger.info("UI preferences (theme, auto_save, show_token_counts) not persisted yet - need studio config")

        return self._save_config_dict(config_dict)


@dataclass
class ProjectService:
    """Service for project management."""

    def __init__(self):
        self.registry = ProjectRegistry()

    def list_projects(self) -> list[dict[str, Any]]:
        """List all projects with metadata.

        Returns:
            List of project dicts with id, name, path, last_used, etc.
        """
        projects = []
        default_id = self.registry.default_project_id

        for project in self.registry.list_projects():
            # Validate project still exists
            if not project.root.exists():
                continue

            # Get last_used timestamp (convert datetime to float)
            last_used_float = 0.0
            if project.created_at:
                try:
                    last_used_float = project.created_at.timestamp()
                except (AttributeError, TypeError):
                    pass

            projects.append({
                "id": project.id,
                "name": project.name,
                "path": str(project.root),
                "last_used": last_used_float,
                "is_default": project.id == default_id,
            })

        # Sort by last_used (most recent first)
        projects.sort(key=lambda p: p["last_used"], reverse=True)

        return projects

    def get_project(self, project_id: str) -> dict[str, Any] | None:
        """Get single project by ID."""
        project = self.registry.get(project_id)
        if not project:
            return None

        last_used_float = 0.0
        if project.created_at:
            try:
                last_used_float = project.created_at.timestamp()
            except (AttributeError, TypeError):
                pass

        return {
            "id": project.id,
            "name": project.name,
            "path": str(project.root),
            "last_used": last_used_float,
            "is_default": project.id == self.registry.default_project_id,
        }

    def create_project(self, name: str, path: str | None = None) -> dict[str, Any]:
        """Create new project.

        Args:
            name: Project name
            path: Optional project path (defaults to current dir)

        Returns:
            Created project dict
        """
        from sunwell.knowledge.project.init import init_project

        project_path = Path(path) if path else Path.cwd()
        init_project(project_path, name=name)

        return {
            "id": name,  # TODO: Generate proper ID
            "name": name,
            "path": str(project_path),
            "last_used": 0.0,
            "is_default": False,
        }

    def set_default_project(self, project_id: str) -> bool:
        """Set default project.

        Args:
            project_id: Project ID to set as default

        Returns:
            True if successful
        """
        return self.registry.set_default_project(project_id)


@dataclass
class SkillService:
    """Service for skill/spell management."""

    def list_skills(self) -> list[dict[str, Any]]:
        """List all available skills.

        Returns:
            List of skill dicts
        """
        # TODO: Integrate with actual skill registry
        # For now, return placeholder data
        return [
            {
                "id": "analyzer",
                "name": "Code Analyzer",
                "category": "analysis",
                "description": "Analyze code structure and patterns",
            },
            {
                "id": "refactor",
                "name": "Refactorer",
                "category": "code",
                "description": "Refactor code for better maintainability",
            },
            {
                "id": "test-gen",
                "name": "Test Generator",
                "category": "testing",
                "description": "Generate unit tests for code",
            },
        ]

    def list_spells(self) -> list[dict[str, Any]]:
        """List all available spells.

        Returns:
            List of spell dicts
        """
        # TODO: Integrate with actual spell registry
        return [
            {
                "id": "quick-fix",
                "name": "Quick Fix",
                "tags": ["bug", "fix"],
                "description": "Quick bug fix workflow",
            },
            {
                "id": "feature-add",
                "name": "Add Feature",
                "tags": ["feature", "development"],
                "description": "Full feature implementation workflow",
            },
        ]


@dataclass
class BacklogService:
    """Service for goal/backlog management."""

    def list_goals(self) -> list[dict[str, Any]]:
        """List all backlog goals.

        Returns:
            List of goal dicts with status, progress, etc.
        """
        # TODO: Integrate with actual backlog/goal system
        return [
            {
                "id": "g1",
                "description": "Implement user authentication",
                "status": "in_progress",
                "priority": "high",
                "progress": 60,
                "tasks_completed": 3,
                "tasks_total": 5,
            },
            {
                "id": "g2",
                "description": "Add dark mode support",
                "status": "pending",
                "priority": "medium",
                "progress": 0,
                "tasks_completed": 0,
                "tasks_total": 8,
            },
        ]

    def create_goal(self, description: str, priority: str = "medium") -> dict[str, Any]:
        """Create new backlog goal."""
        # TODO: Implement actual goal creation
        return {
            "id": "g-new",
            "description": description,
            "status": "pending",
            "priority": priority,
            "progress": 0,
            "tasks_completed": 0,
            "tasks_total": 0,
        }


@dataclass
class WriterService:
    """Service for document management."""

    def list_documents(self) -> list[dict[str, Any]]:
        """List all documents.

        Returns:
            List of document dicts
        """
        # TODO: Integrate with actual document service
        return [
            {
                "id": "d1",
                "title": "API Documentation",
                "status": "draft",
                "word_count": 2500,
                "last_edited": 1707654321.0,
            },
            {
                "id": "d2",
                "title": "User Guide",
                "status": "published",
                "word_count": 5200,
                "last_edited": 1707550000.0,
            },
        ]


@dataclass
class MemoryService:
    """Service for memory/learning management."""

    def __init__(self, workspace: Path | None = None):
        """Initialize memory service.

        Args:
            workspace: Workspace path (defaults to current directory)
        """
        from sunwell.memory.facade.persistent import PersistentMemory

        self.workspace = workspace or Path.cwd()
        try:
            self.memory = PersistentMemory.load(self.workspace)
        except Exception as e:
            logger.warning("Failed to load memory: %s", e)
            self.memory = PersistentMemory.empty(self.workspace)

    def list_memories(self, limit: int = 50) -> list[dict[str, Any]]:
        """List recent learnings/memories.

        Args:
            limit: Maximum number of memories to return

        Returns:
            List of memory dicts
        """
        memories = []

        # Get learnings from simulacrum store
        if self.memory.simulacrum:
            try:
                # List simulacrums
                manager = getattr(self.memory.simulacrum, "_manager", None)
                if manager:
                    simulacrums = manager.list_simulacrums()

                    for sim_meta in simulacrums[:limit]:
                        # Load simulacrum to get learnings
                        sim = manager.load_simulacrum(sim_meta.name)
                        if sim and hasattr(sim, "planning_context"):
                            for learning in sim.planning_context.all_learnings()[:10]:
                                memories.append({
                                    "id": learning.id if hasattr(learning, "id") else f"l-{len(memories)}",
                                    "content": str(learning.content if hasattr(learning, "content") else learning),
                                    "type": "learning",
                                    "confidence": getattr(learning, "confidence", 1.0),
                                    "timestamp": getattr(learning, "timestamp", 0.0),
                                    "source": f"simulacrum:{sim_meta.name}",
                                })

                        if len(memories) >= limit:
                            break
            except Exception as e:
                logger.debug("Error loading simulacrum learnings: %s", e)

        # Get patterns from pattern profile
        if self.memory.patterns and len(memories) < limit:
            try:
                patterns = self.memory.patterns.list_patterns()
                for pattern in patterns[: limit - len(memories)]:
                    memories.append({
                        "id": f"p-{len(memories)}",
                        "content": pattern.get("description", str(pattern)),
                        "type": "pattern",
                        "confidence": 1.0,
                        "timestamp": pattern.get("timestamp", 0.0),
                        "source": "patterns",
                    })
            except Exception as e:
                logger.debug("Error loading patterns: %s", e)

        # Get recent decisions
        if self.memory.decisions and len(memories) < limit:
            try:
                decisions = self.memory.decisions.list_decisions()
                for decision in decisions[: limit - len(memories)]:
                    memories.append({
                        "id": decision.get("id", f"d-{len(memories)}"),
                        "content": decision.get("summary", str(decision)),
                        "type": "decision",
                        "confidence": 1.0,
                        "timestamp": decision.get("timestamp", 0.0),
                        "source": "decisions",
                    })
            except Exception as e:
                logger.debug("Error loading decisions: %s", e)

        # If no real memories, return placeholder
        if not memories:
            return [
                {
                    "id": "placeholder",
                    "content": "No memories found. Complete tasks to build memory.",
                    "type": "system",
                    "confidence": 1.0,
                    "timestamp": 0.0,
                    "source": "system",
                }
            ]

        return memories[:limit]


@dataclass
class CoordinatorService:
    """Service for worker/coordinator management."""

    def list_workers(self) -> list[dict[str, Any]]:
        """List active workers.

        Returns:
            List of worker dicts with status and task counts
        """
        # TODO: Integrate with actual coordinator
        return [
            {
                "id": "w1",
                "name": "Worker-1",
                "status": "active",
                "tasks_running": 2,
                "tasks_completed": 15,
            },
            {
                "id": "w2",
                "name": "Worker-2",
                "status": "idle",
                "tasks_running": 0,
                "tasks_completed": 8,
            },
        ]


@dataclass
class SessionService:
    """Service for background session management."""

    def __init__(self, workspace: Path | None = None):
        """Initialize session service.

        Args:
            workspace: Workspace path (defaults to current directory)
        """
        from sunwell.agent.background.manager import BackgroundManager

        self.workspace = workspace or Path.cwd()
        self.manager = BackgroundManager(self.workspace)

    def list_sessions(
        self,
        status_filter: str | None = None,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """List background sessions.

        Args:
            status_filter: Optional status to filter by (pending, running, completed, etc.)
            limit: Maximum number of sessions to return

        Returns:
            List of session dicts
        """
        from sunwell.agent.background.session import SessionStatus

        sessions = self.manager.list_sessions()

        # Filter by status if requested
        if status_filter:
            try:
                status_enum = SessionStatus(status_filter)
                sessions = [s for s in sessions if s.status == status_enum]
            except ValueError:
                pass  # Invalid status, return all

        # Convert to dicts
        result = []
        for session in sessions[:limit]:
            result.append({
                "id": session.session_id,
                "goal": session.goal,
                "status": session.status.value,
                "started_at": session.started_at.timestamp() if session.started_at else None,
                "completed_at": session.completed_at.timestamp() if session.completed_at else None,
                "tasks_completed": session.tasks_completed,
                "files_changed": len(session.files_changed),
                "duration": session.duration_seconds,
                "error": session.error,
                "result_summary": session.result_summary,
            })

        return result

    def get_session(self, session_id: str) -> dict[str, Any] | None:
        """Get single session by ID.

        Args:
            session_id: Session identifier

        Returns:
            Session dict or None if not found
        """
        session = self.manager.get_session(session_id)
        if not session:
            return None

        return {
            "id": session.session_id,
            "goal": session.goal,
            "status": session.status.value,
            "started_at": session.started_at.timestamp() if session.started_at else None,
            "completed_at": session.completed_at.timestamp() if session.completed_at else None,
            "tasks_completed": session.tasks_completed,
            "files_changed": session.files_changed,
            "duration": session.duration_seconds,
            "error": session.error,
            "result_summary": session.result_summary,
        }

    def get_running_count(self) -> int:
        """Get number of currently running sessions."""
        return self.manager.get_running_count()

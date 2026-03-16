"""Service providers for Chirp pages.

Provides access to Sunwell core services:
- Configuration management
- Project registry
- Background session management
- Skill/spell registries
- Memory services
"""

from sunwell.interface.chirp.services.chat import ChatService
from sunwell.interface.chirp.services.config import ConfigService
from sunwell.interface.chirp.services.memory import MemoryService
from sunwell.interface.chirp.services.project import ProjectService
from sunwell.interface.chirp.services.session import SessionService
from sunwell.interface.chirp.services.skill import SkillService

__all__ = [
    "ChatService",
    "ConfigService",
    "ProjectService",
    "SkillService",
    "MemoryService",
    "SessionService",
]

"""Shared Pydantic models for API routes.

All response models inherit from CamelModel which automatically converts
snake_case Python fields to camelCase in JSON responses.

Run `python scripts/generate_api_types.py` to generate TypeScript types.

This module re-exports all models from the models/ package for backward compatibility.
New code should import directly from sunwell.interface.server.routes.models.
"""

# Re-export everything from models package for backward compatibility
from sunwell.interface.server.routes.models import *  # noqa: F403, F401

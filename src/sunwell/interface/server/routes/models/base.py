"""Base models and utilities for API routes."""

from pydantic import BaseModel, ConfigDict


def _to_camel(string: str) -> str:
    """Convert snake_case to camelCase."""
    parts = string.split("_")
    return parts[0] + "".join(word.capitalize() for word in parts[1:])


class CamelModel(BaseModel):
    """Base model with camelCase support.

    - Accepts both camelCase and snake_case input (via alias_generator + populate_by_name)
    - Serializes as camelCase (JavaScript/TypeScript convention)
    """

    model_config = ConfigDict(
        alias_generator=_to_camel,
        populate_by_name=True,
        # Serialize using aliases (camelCase) for JavaScript/TypeScript convention
        serialize_by_alias=True,
    )


class SuccessResponse(CamelModel):
    """Generic success response."""

    success: bool
    message: str | None = None


class ErrorResponse(CamelModel):
    """Generic error response."""

    error: str
    message: str | None = None

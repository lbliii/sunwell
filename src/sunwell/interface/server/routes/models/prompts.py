"""Prompts response models."""

from sunwell.interface.server.routes.models.base import CamelModel


class SavedPromptItem(CamelModel):
    """A saved prompt."""

    text: str
    last_used: int


class SavedPromptsResponse(CamelModel):
    """List of saved prompts."""

    prompts: list[SavedPromptItem]


class PromptActionResponse(CamelModel):
    """Result of prompt save/remove action."""

    status: str
    total: int

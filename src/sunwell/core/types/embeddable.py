"""Embeddable protocol for objects convertible to embedding text.

This module defines the Embeddable protocol and helper function,
eliminating duplicate to_embedding_text() implementations across models.
"""

from typing import Protocol


class Embeddable(Protocol):
    """Protocol for objects that can be converted to embedding text.

    Implementers provide embedding_parts() which returns the fields
    to include in the embedding representation.

    Example:
        @dataclass(frozen=True, slots=True)
        class MyModel:
            name: str
            description: str | None = None

            def embedding_parts(self) -> tuple[str | None, ...]:
                return (self.name, self.description)

        text = to_embedding_text(my_model)  # "name description"
    """

    def embedding_parts(self) -> tuple[str | None, ...]:
        """Return parts to include in embedding text.

        Returns:
            Tuple of string fields (None values are filtered out).
        """
        ...


def to_embedding_text(obj: Embeddable) -> str:
    """Convert an Embeddable object to embedding text.

    Joins all non-None parts with spaces.

    Args:
        obj: Object implementing Embeddable protocol.

    Returns:
        Space-joined string of embedding parts.
    """
    return " ".join(p for p in obj.embedding_parts() if p)

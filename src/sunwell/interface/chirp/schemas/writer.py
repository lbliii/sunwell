"""Writer/document-related form schemas."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NewDocumentForm:
    """Form for creating a new document.

    Fields:
        title: Document title (required)
        path: File path where document should be created (required)
    """

    title: str
    path: str

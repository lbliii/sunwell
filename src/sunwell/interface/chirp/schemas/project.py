"""Project-related form schemas."""

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class NewProjectForm:
    """Form for creating a new project.

    Fields:
        name: Project name (required, max 64 chars, no path separators)
        path: Optional project path (defaults to workspace with slugified name)
    """

    name: str
    path: str = ""

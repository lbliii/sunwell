"""Sunwell Native Providers (RFC-075, RFC-078).

Local file-based implementations of the provider interfaces.
Data is stored in .sunwell/ directory within the project.
"""

from sunwell.models.providers.native.bookmarks import SunwellBookmarks
from sunwell.models.providers.native.calendar import SunwellCalendar
from sunwell.models.providers.native.contacts import SunwellContacts
from sunwell.models.providers.native.files import SunwellFiles
from sunwell.models.providers.native.git import SunwellGit
from sunwell.models.providers.native.habits import SunwellHabits
from sunwell.models.providers.native.lists import SunwellLists
from sunwell.models.providers.native.notes import SunwellNotes
from sunwell.models.providers.native.projects import SunwellProjects

__all__ = [
    "SunwellBookmarks",
    "SunwellCalendar",
    "SunwellContacts",
    "SunwellFiles",
    "SunwellGit",
    "SunwellHabits",
    "SunwellLists",
    "SunwellNotes",
    "SunwellProjects",
]

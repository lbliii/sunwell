"""Sunwell Native Providers (RFC-075, RFC-078).

Local file-based implementations of the provider interfaces.
Data is stored in .sunwell/ directory within the project.
"""

from sunwell.providers.native.bookmarks import SunwellBookmarks
from sunwell.providers.native.calendar import SunwellCalendar
from sunwell.providers.native.contacts import SunwellContacts
from sunwell.providers.native.files import SunwellFiles
from sunwell.providers.native.git import SunwellGit
from sunwell.providers.native.habits import SunwellHabits
from sunwell.providers.native.lists import SunwellLists
from sunwell.providers.native.notes import SunwellNotes
from sunwell.providers.native.projects import SunwellProjects

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

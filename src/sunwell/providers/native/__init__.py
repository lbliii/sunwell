"""Sunwell Native Providers (RFC-075).

Local file-based implementations of the provider interfaces.
Data is stored in .sunwell/ directory within the project.
"""

from sunwell.providers.native.calendar import SunwellCalendar
from sunwell.providers.native.lists import SunwellLists
from sunwell.providers.native.notes import SunwellNotes

__all__ = [
    "SunwellCalendar",
    "SunwellLists",
    "SunwellNotes",
]

"""Bootstrap Scanners — RFC-050.

Deterministic scanners for extracting evidence from project artifacts.
"""

from typing import Protocol, TypeVar

from sunwell.knowledge.bootstrap.scanners.code import CodeScanner
from sunwell.knowledge.bootstrap.scanners.config import ConfigScanner
from sunwell.knowledge.bootstrap.scanners.docs import DocScanner
from sunwell.knowledge.bootstrap.scanners.git import GitScanner

# Type variable for evidence types
E = TypeVar("E", covariant=True)


class Scanner(Protocol[E]):
    """Protocol for bootstrap scanners.

    All scanners implement an async scan() method that returns
    evidence of the appropriate type.
    """

    async def scan(self) -> E:
        """Scan and return evidence."""
        ...


__all__ = [
    "Scanner",
    "GitScanner",
    "CodeScanner",
    "DocScanner",
    "ConfigScanner",
]

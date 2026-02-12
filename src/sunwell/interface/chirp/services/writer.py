"""Document management service for Chirp interface."""

from dataclasses import dataclass
from typing import Any


@dataclass
class WriterService:
    """Service for document management."""

    def list_documents(self) -> list[dict[str, Any]]:
        """List all documents.

        Returns:
            List of document dicts
        """
        import time

        # TODO: Integrate with actual document service
        now = time.time()
        return [
            {
                "id": "d1",
                "title": "API Documentation",
                "status": "draft",
                "word_count": 2500,
                "modified": now - 86400,  # 1 day ago
            },
            {
                "id": "d2",
                "title": "User Guide",
                "status": "published",
                "word_count": 5200,
                "modified": now - 86400 * 3,  # 3 days ago
            },
        ]

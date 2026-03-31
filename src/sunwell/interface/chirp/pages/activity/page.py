"""Activity Monitor page - Real-time tool call monitoring."""


def get() -> dict:
    """Render activity monitor page."""
    return {
        "page_title": "Activity Monitor - Sunwell Studio",
        "breadcrumb_label": "Activity",
    }

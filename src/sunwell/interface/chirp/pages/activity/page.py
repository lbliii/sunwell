"""Activity Monitor page - Real-time tool call monitoring."""

from chirp import Page


def get() -> Page:
    """Render activity monitor page."""
    return Page(
        "activity/page.html",
        "content",
        current_page="activity",
        page_title="Activity Monitor - Sunwell Studio",
        breadcrumb_label="Activity",
    )

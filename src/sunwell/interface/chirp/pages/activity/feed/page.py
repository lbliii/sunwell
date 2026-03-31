"""Activity feed - polling endpoint returning Fragment (hybrid routing).

Use hx-get="/activity/feed" hx-trigger="every 5s" hx-swap="innerHTML".
Avoid page-load SSE (sse-connect on load causes infinite spinner).
"""

from chirp import App, Fragment


def get(app: App) -> Fragment:
    """Return recent tool call events as HTML fragment for polling.

    Polling pattern: GET returns Fragment; no long-lived SSE on page load.
    ToolEventBus has subscribe() only (no buffer); events placeholder for now.
    """
    return Fragment(
        "activity/_feed.html",
        "feed_content",
        events=[],
    )

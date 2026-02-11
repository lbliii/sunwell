"""Home page route using page convention."""

from chirp import Page


def get() -> Page:
    """Render the home page.

    Shows:
    - Recent projects
    - Quick actions
    - System status
    """
    # TODO: Inject ProjectStore via service provider once added
    # For now, use placeholder data
    recent_projects = [
        {
            "id": "proj-1",
            "name": "Example Project",
            "description": "A sample project for testing",
            "last_modified": "2026-02-11",
        }
    ]

    return Page(
        "page.html",
        "content",
        current_page="home",
        recent_projects=recent_projects,
        title="Home",
    )

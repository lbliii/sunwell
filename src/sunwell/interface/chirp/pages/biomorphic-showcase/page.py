"""Biomorphic Design System Showcase - Interactive demo page."""

from chirp import Page


def get() -> Page:
    """Render biomorphic design system showcase.

    Demonstrates:
    - Holy biomorphic components (organic shapes, divine light)
    - Component variants system
    - Spring physics animations
    - Theme switching
    - Floating particles
    - Interactive elements
    """
    return Page(
        "biomorphic-showcase/page.html",
        "content",
        current_page="design-system",
        title="Holy Biomorphic Design System",
    )

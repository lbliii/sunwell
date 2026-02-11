#!/usr/bin/env python3
"""Validate Chirp hypermedia contracts.

This script creates the Chirp app and runs contract validation.
Run this manually to check for broken htmx links, missing routes, etc.

Usage:
    python scripts/check_chirp_contracts.py

Note: This requires optional dependencies:
    pip install chirp[markdown]
"""

if __name__ == "__main__":
    from sunwell.interface.chirp import create_app

    app = create_app()
    app.check()

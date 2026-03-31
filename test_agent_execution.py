#!/usr/bin/env python
"""Test script for agent execution via Chirp interface."""

from sunwell.interface.chirp.main import create_app, register_providers

def main():
    """Start Chirp server with agent execution enabled."""
    print("🚀 Starting Chirp server...")

    # Create app (already registers MCP tools internally)
    app = create_app()

    # Register services
    register_providers(app)

    print("✅ App configured")
    print("\n📍 Server will be available at: http://127.0.0.1:8888")
    print("📍 Test agent execution at: http://127.0.0.1:8888/projects/sunwell")
    print("📍 Track sessions at: http://127.0.0.1:8888/observatory")
    print("\n⏹️  Press Ctrl+C to stop\n")

    # Run server
    app.run(host="127.0.0.1", port=8888)

if __name__ == "__main__":
    main()

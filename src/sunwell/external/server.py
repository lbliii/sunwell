"""Webhook Server for External Integration (RFC-049).

HTTP server for receiving webhooks from external services.
"""

import json
import logging
from pathlib import Path
from typing import TYPE_CHECKING

from sunwell.external.types import EventSource

if TYPE_CHECKING:
    from sunwell.external.processor import EventProcessor

logger = logging.getLogger(__name__)


class WebhookServer:
    """HTTP server for receiving webhooks.

    Uses FastAPI for async webhook handling with signature verification.
    """

    def __init__(
        self,
        processor: "EventProcessor",
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        """Initialize webhook server.

        Args:
            processor: Event processor to handle incoming events
            host: Host to bind to
            port: Port to listen on
        """
        self.processor = processor
        self.host = host
        self.port = port
        self.app = None
        self._setup_app()

    def _setup_app(self) -> None:
        """Configure FastAPI application and routes."""
        try:
            from fastapi import FastAPI, HTTPException, Request
            from fastapi.responses import JSONResponse
        except ImportError as e:
            logger.warning(f"FastAPI not available: {e}")
            return

        self.app = FastAPI(
            title="Sunwell External Integration",
            description="Webhook server for CI/CD, Git, and Issue Tracker events",
            version="0.1.0",
        )

        @self.app.post("/webhook/github")
        async def github_webhook(request: Request) -> JSONResponse:
            return await self._handle_github(request)

        @self.app.post("/webhook/gitlab")
        async def gitlab_webhook(request: Request) -> JSONResponse:
            return await self._handle_gitlab(request)

        @self.app.post("/webhook/linear")
        async def linear_webhook(request: Request) -> JSONResponse:
            return await self._handle_linear(request)

        @self.app.post("/webhook/sentry")
        async def sentry_webhook(request: Request) -> JSONResponse:
            return await self._handle_sentry(request)

        @self.app.get("/health")
        async def health() -> dict:
            return {
                "status": "healthy",
                "rate_limits": self.processor.get_rate_limit_stats(),
            }

        @self.app.get("/status")
        async def status() -> dict:
            return {
                "adapters": list(self.processor._adapters.keys()),
                "rate_limits": self.processor.get_rate_limit_stats(),
            }

    async def _handle_github(self, request) -> "JSONResponse":
        """Handle GitHub webhook.

        Verification sequence:
        1. Read raw body (bytes)
        2. Verify signature BEFORE parsing JSON
        3. Parse JSON
        4. Normalize and process
        """
        from fastapi import HTTPException
        from fastapi.responses import JSONResponse

        # 1. Read raw body
        body = await request.body()

        # 2. Verify signature BEFORE parsing
        signature = request.headers.get("X-Hub-Signature-256", "")
        adapter = self.processor._adapters.get(EventSource.GITHUB)

        if not adapter:
            raise HTTPException(503, "GitHub adapter not configured")

        if not await adapter.verify_webhook(body, signature):
            logger.warning(f"Invalid GitHub webhook signature from {request.client.host}")
            raise HTTPException(401, "Invalid signature")

        # 3. Parse JSON (now safe)
        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON payload")

        event_name = request.headers.get("X-GitHub-Event", "")

        # 4. Normalize and process
        event = adapter.normalize_webhook(event_name, payload)
        if event:
            try:
                await self.processor.process_event(event)
            except Exception as e:
                logger.error(f"Error processing GitHub event: {e}")
                # Don't fail the webhook - GitHub will retry
                return JSONResponse({"status": "error", "message": str(e)}, status_code=200)

        return JSONResponse({"status": "ok"})

    async def _handle_gitlab(self, request) -> "JSONResponse":
        """Handle GitLab webhook."""
        from fastapi import HTTPException
        from fastapi.responses import JSONResponse

        adapter = self.processor._adapters.get(EventSource.GITLAB)
        if not adapter:
            raise HTTPException(503, "GitLab adapter not configured")

        # GitLab uses X-Gitlab-Token for verification
        token = request.headers.get("X-Gitlab-Token", "")
        body = await request.body()

        if not await adapter.verify_webhook(body, token):
            raise HTTPException(401, "Invalid token")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON payload")

        event = adapter.normalize_webhook(payload)
        if event:
            await self.processor.process_event(event)

        return JSONResponse({"status": "ok"})

    async def _handle_linear(self, request) -> "JSONResponse":
        """Handle Linear webhook."""
        from fastapi import HTTPException
        from fastapi.responses import JSONResponse

        adapter = self.processor._adapters.get(EventSource.LINEAR)
        if not adapter:
            raise HTTPException(503, "Linear adapter not configured")

        body = await request.body()
        signature = request.headers.get("Linear-Webhook-Signature", "")

        if not await adapter.verify_webhook(body, signature):
            raise HTTPException(401, "Invalid signature")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON payload")

        event = adapter.normalize_webhook(payload)
        if event:
            await self.processor.process_event(event)

        return JSONResponse({"status": "ok"})

    async def _handle_sentry(self, request) -> "JSONResponse":
        """Handle Sentry webhook."""
        from fastapi import HTTPException
        from fastapi.responses import JSONResponse

        adapter = self.processor._adapters.get(EventSource.SENTRY)
        if not adapter:
            raise HTTPException(503, "Sentry adapter not configured")

        body = await request.body()
        signature = request.headers.get("Sentry-Hook-Signature", "")

        if not await adapter.verify_webhook(body, signature):
            raise HTTPException(401, "Invalid signature")

        try:
            payload = json.loads(body)
        except json.JSONDecodeError:
            raise HTTPException(400, "Invalid JSON payload")

        event = adapter.normalize_webhook(payload)
        if event:
            await self.processor.process_event(event)

        return JSONResponse({"status": "ok"})

    async def start(self) -> None:
        """Start the webhook server."""
        if not self.app:
            raise RuntimeError("FastAPI not available - install with 'pip install fastapi uvicorn'")

        import uvicorn

        config = uvicorn.Config(
            self.app,
            host=self.host,
            port=self.port,
            log_level="info",
        )
        server = uvicorn.Server(config)
        await server.serve()

    def get_webhook_urls(self) -> dict[str, str]:
        """Get webhook URLs for configuration.

        Returns:
            Dictionary of service name to webhook URL
        """
        base = f"http://{self.host}:{self.port}"
        return {
            "github": f"{base}/webhook/github",
            "gitlab": f"{base}/webhook/gitlab",
            "linear": f"{base}/webhook/linear",
            "sentry": f"{base}/webhook/sentry",
            "health": f"{base}/health",
        }

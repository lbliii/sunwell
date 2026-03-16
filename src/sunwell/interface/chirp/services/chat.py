"""Chat service - wraps UnifiedChatLoop for web use.

Uses Chirp Pattern 3 (streaming append): POST returns scaffolding with
sse-connect; GET /chat/stream yields Fragments as the agent works.
"""

import asyncio
import logging
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

from chirp import Fragment

from sunwell.agent.chat import ChatCheckpoint, ChatCheckpointType, UnifiedChatLoop
from sunwell.agent.chat.checkpoint import CheckpointResponse
from sunwell.agent.events import AgentEvent
from sunwell.interface.cli.helpers.models import resolve_model

logger = logging.getLogger(__name__)


@dataclass
class ChatSession:
    """Per-session chat state."""

    session_id: str
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    event_queue: asyncio.Queue[Fragment | None] = field(default_factory=asyncio.Queue)
    _loop: UnifiedChatLoop | None = None


def _resolve_model_web():  # noqa: ANN202
    """Resolve model for web chat — prefer Ollama (no extra deps)."""
    return resolve_model("ollama", None)


class ChatService:
    """Service wrapping UnifiedChatLoop for web chat.

    Pattern 3: POST returns scaffolding; background task pushes to queue;
    GET /chat/stream subscribes and yields Fragments.
    """

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = workspace or Path.cwd()
        self._sessions: dict[str, ChatSession] = {}

    def _get_or_create_session(self, session_id: str) -> ChatSession:
        if session_id not in self._sessions:
            self._sessions[session_id] = ChatSession(session_id=session_id)
        return self._sessions[session_id]

    def get_conversation_history(self, session_id: str) -> list[dict[str, str]]:
        """Return message history for a session."""
        session = self._get_or_create_session(session_id)
        return list(session.conversation_history)

    def _push(self, session: ChatSession, fragment: Fragment) -> None:
        """Push fragment to session queue (non-blocking)."""
        try:
            session.event_queue.put_nowait(fragment)
        except asyncio.QueueFull:
            logger.warning("Chat session queue full, dropping fragment")

    async def _run_loop(
        self,
        session_id: str,
        message: str,
    ) -> None:
        """Run the agent loop and push Fragments to the session queue."""
        session = self._get_or_create_session(session_id)
        model = _resolve_model_web()
        loop = UnifiedChatLoop(
            model=model,
            tool_executor=None,
            workspace=self.workspace,
            auto_confirm=True,
            stream_progress=True,
        )
        session._loop = loop

        gen = loop.run()
        await gen.asend(None)

        try:
            result = await gen.asend(message)
            while result is not None:
                if isinstance(result, str):
                    self._push(
                        session,
                        Fragment(
                            "chat/_message.html",
                            "assistant_message",
                            content=result,
                            role="assistant",
                        ),
                    )
                    session.conversation_history.append({"role": "user", "content": message})
                    session.conversation_history.append({"role": "assistant", "content": result})
                    result = None

                elif isinstance(result, ChatCheckpoint):
                    if result.type == ChatCheckpointType.FAILURE:
                        self._push(
                            session,
                            Fragment(
                                "chat/_message.html",
                                "error_message",
                                message=result.message,
                                error=result.error or "",
                            ),
                        )
                    elif result.type == ChatCheckpointType.COMPLETION:
                        self._push(
                            session,
                            Fragment(
                                "chat/_message.html",
                                "assistant_message",
                                content=result.message,
                                role="assistant",
                            ),
                        )
                    response = CheckpointResponse("continue")
                    if result.type == ChatCheckpointType.CONFIRMATION:
                        response = CheckpointResponse("y")
                    elif result.type == ChatCheckpointType.BACKGROUND_OFFER:
                        response = CheckpointResponse("wait")
                    result = await gen.asend(response)

                elif isinstance(result, AgentEvent):
                    data = result.data or {}
                    tool_name = data.get("tool_name") or "tool"
                    args = data.get("arguments", {})
                    result_str = str(data.get("result", data.get("output", "")))[:200]
                    err = str(data.get("error", "")) if data.get("error") else None
                    self._push(
                        session,
                        Fragment(
                            "chat/_message.html",
                            "tool_event",
                            tool_name=tool_name,
                            args=args,
                            result=result_str,
                            error=err,
                        ),
                    )
                    result = await gen.asend(None)

                else:
                    result = None
        except Exception as e:
            logger.exception("ChatService._run_loop error")
            self._push(
                session,
                Fragment(
                    "chat/_message.html",
                    "error_message",
                    message="An error occurred",
                    error=str(e),
                ),
            )
        finally:
            session._loop = None
            session.event_queue.put_nowait(None)  # Sentinel: stream complete

    def start_send(self, session_id: str, message: str) -> None:
        """Start agent loop in background. Call before returning scaffolding."""
        asyncio.create_task(self._run_loop(session_id, message))

    async def subscribe(
        self,
        session_id: str,
    ) -> AsyncIterator[Fragment]:
        """Subscribe to session events. Yields Fragments until stream complete."""
        session = self._get_or_create_session(session_id)
        while True:
            frag = await session.event_queue.get()
            if frag is None:
                break
            yield frag

    @staticmethod
    def new_session_id() -> str:
        """Generate a new session ID for chat."""
        return str(uuid.uuid4())

"""Chat service - wraps UnifiedChatLoop for web use.

Uses Chirp Pattern 3 (streaming append): POST returns scaffolding with
sse-connect; GET /chat/stream yields Fragments as the agent works.

Also supports channel adapters (Telegram, etc.) via run_for_channel().

Phase 4: Multi-step messages route to ExecutionManager (Naaru DAG).
"""

import asyncio
import logging
import time
import uuid
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from pathlib import Path

import httpx
from chirp import Fragment
from chirp.realtime.events import SSEEvent

from sunwell.agent.chat import ChatCheckpoint, ChatCheckpointType, UnifiedChatLoop
from sunwell.agent.chat.checkpoint import CheckpointResponse
from sunwell.agent.events import AgentEvent
from sunwell.agent.workflow import is_multi_step
from sunwell.channels.protocol import InboundMessage, OutboundAdapter
from sunwell.interface.cli.helpers.models import resolve_model

logger = logging.getLogger(__name__)

# Session TTL: evict inactive sessions after 1 hour
_SESSION_TTL_SECONDS = 3600
# Bounded queue for SSE subscribers; overflow drops and logs
_QUEUE_MAXSIZE = 512


@dataclass
class ChatSession:
    """Per-session chat state.

    Uses broadcast: multiple SSE subscribers (chat + activity panel) each get
    a queue; _push sends to all.
    """

    session_id: str
    conversation_history: list[dict[str, str]] = field(default_factory=list)
    model: str | None = None  # Per-session override; None = use default
    _subscriber_queues: list[asyncio.Queue[Fragment | SSEEvent | None]] = field(
        default_factory=list
    )
    _loop: UnifiedChatLoop | None = None
    _task: asyncio.Task[None] | None = None  # For cancel
    last_active: float = field(default_factory=time.monotonic)


def _resolve_model_web(model_override: str | None = None) -> object:  # noqa: ANN201
    """Resolve model for web chat — prefer Ollama (no extra deps)."""
    return resolve_model("ollama", model_override)


class ChatService:
    """Service wrapping UnifiedChatLoop for web chat.

    Pattern 3: POST returns scaffolding; background task pushes to queue;
    GET /chat/stream subscribes and yields Fragments.
    """

    def __init__(self, workspace: Path | None = None) -> None:
        self.workspace = workspace or Path.cwd()
        self._sessions: dict[str, ChatSession] = {}

    def _prune_stale_sessions(self) -> None:
        """Remove sessions older than TTL. Do not evict sessions with active _loop."""
        now = time.monotonic()
        stale = [
            sid
            for sid, s in self._sessions.items()
            if s._loop is None and (now - s.last_active) > _SESSION_TTL_SECONDS
        ]
        for sid in stale:
            del self._sessions[sid]
            logger.debug("Evicted stale chat session %s", sid[:8])

    def _get_or_create_session(self, session_id: str) -> ChatSession:
        self._prune_stale_sessions()
        if session_id not in self._sessions:
            self._sessions[session_id] = ChatSession(session_id=session_id)
        session = self._sessions[session_id]
        session.last_active = time.monotonic()
        return session

    def get_conversation_history(self, session_id: str) -> list[dict[str, str]]:
        """Return message history for a session."""
        session = self._get_or_create_session(session_id)
        return list(session.conversation_history)

    def has_session(self, session_id: str) -> bool:
        """Return True if session exists (for stream guard)."""
        return session_id in self._sessions

    def get_session_model(self, session_id: str) -> str:
        """Return effective model for session (per-session override or default)."""
        session = self._get_or_create_session(session_id)
        if session.model:
            return session.model
        m = resolve_model("ollama", None)
        return getattr(m, "model", "llama3.1:8b")

    def set_session_model(self, session_id: str, model: str) -> None:
        """Set per-session model override."""
        session = self._get_or_create_session(session_id)
        session.model = model

    def cancel_run(self, session_id: str) -> bool:
        """Cancel in-progress run. Returns True if a run was cancelled."""
        if session_id not in self._sessions:
            return False
        session = self._sessions[session_id]
        if session._task is None:
            return False
        session._task.cancel()
        return True

    def list_ollama_models(self) -> list[str]:
        """Return available Ollama model names. Empty list on failure."""
        try:
            from sunwell.foundation.config import get_config

            cfg = get_config()
            url = f"{cfg.embedding.ollama_url}/api/tags"
            resp = httpx.get(url, timeout=2.0)
            if resp.status_code != 200:
                return []
            data = resp.json()
            models = data.get("models", [])
            return [m["name"] for m in models if isinstance(m.get("name"), str)]
        except Exception:
            return []

    def _push(self, session: ChatSession, fragment: Fragment) -> None:
        """Push fragment to all subscriber queues (broadcast)."""
        for q in list(session._subscriber_queues):
            try:
                q.put_nowait(fragment)
            except asyncio.QueueFull:
                logger.warning(
                    "Chat session %s queue full (max=%s), dropping fragment",
                    session.session_id[:8],
                    _QUEUE_MAXSIZE,
                )

    def _broadcast(self, session: ChatSession, *items: Fragment | SSEEvent | None) -> None:
        """Broadcast items to all subscriber queues."""
        for q in list(session._subscriber_queues):
            for item in items:
                try:
                    q.put_nowait(item)
                except asyncio.QueueFull:
                    logger.warning(
                        "Chat session %s queue full (max=%s), dropping broadcast",
                        session.session_id[:8],
                        _QUEUE_MAXSIZE,
                    )

    async def _run_loop(
        self,
        session_id: str,
        message: str,
    ) -> None:
        """Run the agent loop and push Fragments to the session queue."""
        session = self._get_or_create_session(session_id)
        session.conversation_history.append({"role": "user", "content": message})

        try:
            model = _resolve_model_web(session.model)
            token_cb: object = None
            if hasattr(model, "generate_stream"):
                def _on_token(chunk: str) -> None:
                    self._push(
                        session,
                        Fragment(
                            "chat/_message.html",
                            "stream_token",
                            token=chunk,
                        ),
                    )
                token_cb = _on_token

            loop = UnifiedChatLoop(
                model=model,
                tool_executor=None,
                workspace=self.workspace,
                auto_confirm=True,
                stream_progress=True,
                token_callback=token_cb,
            )
            session._loop = loop

            gen = loop.run()
            await gen.asend(None)

            result = await gen.asend(message)
            while result is not None:
                if isinstance(result, str):
                    if token_cb:
                        self._push(
                            session,
                            Fragment(
                                "chat/_message.html",
                                "chat_stream_done",
                                target=f"chat-stream-{session_id}",
                                content=result,
                            ),
                        )
                    else:
                        self._push(
                            session,
                            Fragment(
                                "chat/_message.html",
                                "assistant_message",
                                content=result,
                                role="assistant",
                            ),
                        )
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
                                user_message=message,
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
                        session.conversation_history.append(
                            {"role": "assistant", "content": result.message or ""}
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
                    tool_frag = Fragment(
                        "chat/_message.html",
                        "tool_event",
                        tool_name=tool_name,
                        args=args,
                        result=result_str,
                        error=err,
                    )
                    self._push(session, tool_frag)
                    self._push(
                        session,
                        Fragment(
                            "chat/_message.html",
                            "tool_event",
                            target="chat-activity-feed",
                            tool_name=tool_name,
                            args=args,
                            result=result_str,
                            error=err,
                        ),
                    )
                    result = await gen.asend(None)

                else:
                    result = None
        except asyncio.CancelledError:
            self._push(
                session,
                Fragment(
                    "chat/_message.html",
                    "error_message",
                    message="Response cancelled",
                    error="",
                    user_message=message,
                ),
            )
            raise
        except Exception as e:
            logger.exception("ChatService._run_loop error")
            self._push(
                session,
                Fragment(
                    "chat/_message.html",
                    "error_message",
                    message="An error occurred",
                    error=str(e),
                    user_message=message,
                ),
            )
        finally:
            session._loop = None
            session._task = None
            self._broadcast(session, SSEEvent(event="done", data="complete"), None)

    async def _run_workflow(
        self,
        session_id: str,
        message: str,
    ) -> None:
        """Run multi-step workflow via ExecutionManager (Naaru DAG).

        Resolves project from workspace, builds ToolExecutor + ArtifactPlanner,
        forwards events to session queue as Fragments. Falls back to
        _run_loop if project resolution fails.
        """
        session = self._get_or_create_session(session_id)

        try:
            from sunwell.agent.execution.manager import ExecutionManager
            from sunwell.knowledge.project import (
                ProjectValidationError,
                create_project_from_workspace,
            )
            from sunwell.planning.naaru.planners.artifact import ArtifactPlanner
            from sunwell.tools.execution import ToolExecutor

            project = create_project_from_workspace(self.workspace)
        except Exception as e:
            if type(e).__name__ == "ProjectValidationError":
                logger.debug("Workflow: project validation failed, falling back to chat loop")
            else:
                logger.debug("Workflow: setup failed (%s), falling back to chat loop", e)
            await self._run_loop(session_id, message)
            return

        try:
            model = _resolve_model_web(session.model)
            planner = ArtifactPlanner(model=model)

            # Optional skill executor (research) when web search available
            skill_executor = None
            web_handler = None
            try:
                from sunwell.memory.facade.persistent import PersistentMemory
                from sunwell.skills import create_default_skill_executor
                from sunwell.tools.providers.web_search import (
                    WebSearchHandler,
                    create_web_search_provider,
                )

                try:
                    memory = PersistentMemory.load(project.root)
                except Exception:
                    memory = PersistentMemory.empty(project.root)
                web_provider = create_web_search_provider("auto")
                web_handler = WebSearchHandler(provider=web_provider)
                skill_executor = create_default_skill_executor(
                    project.root, web_search_handler=web_handler, memory=memory
                )
            except Exception:
                pass

            tool_executor = ToolExecutor(
                project=project,
                web_search_handler=web_handler,
                skill_executor=skill_executor,
            )

            # EventEmitter that forwards to session queue as Fragments
            def _push_fragment(event: AgentEvent) -> None:
                data = event.data or {}
                tool_name = event.type.value
                args = {k: v for k, v in data.items() if k not in ("result", "output", "error")}
                result_str = str(data.get("result", data.get("output", "")))[:200]
                err = str(data.get("error", "")) if data.get("error") else None
                tool_frag = Fragment(
                    "chat/_message.html",
                    "tool_event",
                    tool_name=tool_name,
                    args=args,
                    result=result_str,
                    error=err,
                )
                self._push(session, tool_frag)
                self._push(
                    session,
                    Fragment(
                        "chat/_message.html",
                        "tool_event",
                        target="chat-activity-feed",
                        tool_name=tool_name,
                        args=args,
                        result=result_str,
                        error=err,
                    ),
                )

            class _FragmentEmitter:
                def emit(self, event: AgentEvent) -> None:
                    _push_fragment(event)

            emitter = _FragmentEmitter()
            manager = ExecutionManager(root=project.root, emitter=emitter)

            exec_result = await manager.run_goal(
                message,
                planner=planner,
                executor=tool_executor,
                verbose=False,
            )

            summary = (
                f"Created {len(exec_result.artifacts_created)} artifact(s)"
                if exec_result.success
                else f"Failed: {exec_result.error or 'unknown'}"
            )
            self._push(
                session,
                Fragment(
                    "chat/_message.html",
                    "assistant_message",
                    content=summary,
                    role="assistant",
                ),
            )
            session.conversation_history.append({"role": "user", "content": message})
            session.conversation_history.append({"role": "assistant", "content": summary})

        except asyncio.CancelledError:
            self._push(
                session,
                Fragment(
                    "chat/_message.html",
                    "error_message",
                    message="Response cancelled",
                    error="",
                    user_message=message,
                ),
            )
            raise
        except Exception as e:
            logger.exception("ChatService._run_workflow error")
            self._push(
                session,
                Fragment(
                    "chat/_message.html",
                    "error_message",
                    message="Workflow failed",
                    error=str(e),
                    user_message=message,
                ),
            )
        finally:
            session._task = None
            self._broadcast(session, SSEEvent(event="done", data="complete"), None)

    def start_send(
        self, session_id: str, message: str, stream: bool = True
    ) -> Fragment | None:
        """Start agent loop. If stream=True, runs in background and returns None.
        If stream=False, runs synchronously and returns error Fragment or None
        (caller must use send_sync to get the response).

        Returns error Fragment if a response is already in progress; None otherwise.
        """
        session = self._get_or_create_session(session_id)
        if session._loop is not None:
            return Fragment(
                "chat/_message.html",
                "error_message",
                message="A response is already in progress.",
                error="Please wait for the current response to complete.",
                user_message=message,
            )
        if stream:
            if is_multi_step(message):
                task = asyncio.create_task(self._run_workflow(session_id, message))
            else:
                task = asyncio.create_task(self._run_loop(session_id, message))
            session._task = task
            return None
        return None  # Caller uses send_sync for non-streaming

    async def send_sync(self, session_id: str, message: str) -> tuple[str | None, str | None]:
        """Run agent loop synchronously and return (content, error).

        Only supports single-step messages. Multi-step falls back to streaming.
        Returns (assistant_content, None) on success, (None, error_msg) on failure.
        """
        if is_multi_step(message):
            self.start_send(session_id, message, stream=True)
            return None, "Multi-step tasks use streaming; please enable Stream."
        session = self._get_or_create_session(session_id)
        if session._loop is not None:
            return None, "A response is already in progress."
        session.conversation_history.append({"role": "user", "content": message})
        try:
            model = _resolve_model_web(session.model)
            loop = UnifiedChatLoop(
                model=model,
                tool_executor=None,
                workspace=self.workspace,
                auto_confirm=True,
                stream_progress=False,
                token_callback=None,
            )
            session._loop = loop
            gen = loop.run()
            await gen.asend(None)
            result = await gen.asend(message)
            while result is not None:
                if isinstance(result, str):
                    session.conversation_history.append(
                        {"role": "assistant", "content": result}
                    )
                    session._loop = None
                    return result, None
                if isinstance(result, ChatCheckpoint):
                    if result.type == ChatCheckpointType.FAILURE:
                        session._loop = None
                        return None, result.message or (result.error or "An error occurred")
                    if result.type == ChatCheckpointType.COMPLETION:
                        session.conversation_history.append(
                            {"role": "assistant", "content": result.message or ""}
                        )
                        session._loop = None
                        return result.message or "", None
                    response = CheckpointResponse("continue")
                    if result.type == ChatCheckpointType.CONFIRMATION:
                        response = CheckpointResponse("y")
                    elif result.type == ChatCheckpointType.BACKGROUND_OFFER:
                        response = CheckpointResponse("wait")
                    result = await gen.asend(response)
                elif isinstance(result, AgentEvent):
                    result = await gen.asend(None)
                else:
                    result = None
            session._loop = None
            return None, "No response"
        except Exception as e:
            logger.exception("ChatService.send_sync error")
            session._loop = None
            return None, str(e)

    async def subscribe(
        self,
        session_id: str,
    ) -> AsyncIterator[Fragment | SSEEvent]:
        """Subscribe to session events. Yields Fragments and SSEEvent until stream complete.

        Idempotent: multiple subscribers per session are supported.
        Uses bounded queue; overflow is logged and dropped.
        """
        session = self._get_or_create_session(session_id)
        queue: asyncio.Queue[Fragment | SSEEvent | None] = asyncio.Queue(
            maxsize=_QUEUE_MAXSIZE
        )
        session._subscriber_queues.append(queue)
        try:
            while True:
                item = await queue.get()
                if item is None:
                    break
                yield item
        finally:
            if queue in session._subscriber_queues:
                session._subscriber_queues.remove(queue)

    async def run_for_channel(
        self,
        msg: InboundMessage,
        outbound: OutboundAdapter,
    ) -> None:
        """Run agent loop for a channel message; send replies via outbound adapter.

        Same UnifiedChatLoop as web chat, but calls outbound.send_text() instead
        of pushing Fragments. Uses session_key (channel:peer_id) for conversation
        continuity.
        """
        session_id = msg.session_key
        session = self._get_or_create_session(session_id)
        model = _resolve_model_web(session.model)
        loop = UnifiedChatLoop(
            model=model,
            tool_executor=None,
            workspace=self.workspace,
            auto_confirm=True,
            stream_progress=False,
        )
        session._loop = loop

        gen = loop.run()
        await gen.asend(None)

        try:
            result = await gen.asend(msg.text)
            while result is not None:
                if isinstance(result, str):
                    await outbound.send_text(msg.peer_id, result)
                    session.conversation_history.append({"role": "user", "content": msg.text})
                    session.conversation_history.append({"role": "assistant", "content": result})
                    result = None

                elif isinstance(result, ChatCheckpoint):
                    if result.type == ChatCheckpointType.FAILURE:
                        err_msg = result.message or (result.error or "An error occurred")
                        await outbound.send_text(msg.peer_id, f"Error: {err_msg}")
                    elif result.type == ChatCheckpointType.COMPLETION:
                        await outbound.send_text(msg.peer_id, result.message or "")
                    response = CheckpointResponse("continue")
                    if result.type == ChatCheckpointType.CONFIRMATION:
                        response = CheckpointResponse("y")
                    elif result.type == ChatCheckpointType.BACKGROUND_OFFER:
                        response = CheckpointResponse("wait")
                    result = await gen.asend(response)

                elif isinstance(result, AgentEvent):
                    result = await gen.asend(None)

                else:
                    result = None
        except Exception as e:
            logger.exception("ChatService.run_for_channel error")
            await outbound.send_text(msg.peer_id, f"An error occurred: {e}")
        finally:
            session._loop = None

    @staticmethod
    def new_session_id() -> str:
        """Generate a new session ID for chat."""
        return str(uuid.uuid4())

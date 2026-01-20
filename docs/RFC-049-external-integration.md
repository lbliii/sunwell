# RFC-049: External Integration — CI, Git, and Issue Tracker Connection

**Status**: Draft (Revised)  
**Created**: 2026-01-19  
**Last Updated**: 2026-01-19  
**Revision**: 2 — Added backwards compatibility, rate limiting details, crash recovery  
**Authors**: Sunwell Team  
**Depends on**: RFC-046 (Autonomous Backlog), RFC-048 (Autonomy Guardrails)  
**Enables**: Phase 3 Autonomous Agent (external event-driven)

---

## Summary

External Integration connects Sunwell to the outside world — CI/CD pipelines, Git repositories, issue trackers, and production monitoring. Instead of operating in isolation, Sunwell can now **react to external events**: a failing CI build triggers automatic investigation, a new issue spawns a goal, a production error gets triaged overnight.

**Core insight**: True autonomy requires external awareness. An agent that only responds to user commands is still reactive. One that monitors CI, sees failures, and fixes them before the user wakes up is genuinely autonomous.

**Design approach**: Event-driven architecture with pluggable adapters. External services push events via webhooks or polling; Sunwell translates them to goals and executes via RFC-046 Autonomous Backlog. See "Design Alternatives Considered" for full comparison.

**One-liner**: Sunwell watches your CI, reads your issues, and gets to work — even when you're not there.

---

## Motivation

### The Island Problem

RFC-046 (Autonomous Backlog) gives Sunwell self-directed goal generation from code signals. But it's still an island:

```
┌────────────────────────────────────────────────────────────────────┐
│                         THE ISLAND                                  │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  Sunwell knows:                    Sunwell doesn't know:           │
│  ─────────────────────             ───────────────────────────     │
│  • Failing local tests             • CI build just failed          │
│  • TODOs in code                   • Someone opened an issue       │
│  • Type errors                     • Production is throwing 500s   │
│  • Lint warnings                   • PR was merged 5 minutes ago   │
│                                    • Dependency has security CVE   │
│                                                                    │
│  Internal signals ✅               External signals ❌              │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

Without external integration, Sunwell misses:
- **CI failures**: Build broke on main; local tests pass but CI fails
- **Issue triage**: 10 new issues overnight; user has to read and assign each
- **Production errors**: 500 errors spiking; no one notices until morning
- **Git events**: PR merged; dependent code needs update
- **Security advisories**: Vulnerable dependency; needs immediate attention

### What External Integration Enables

```
┌────────────────────────────────────────────────────────────────────┐
│                    CONNECTED SUNWELL                                │
├────────────────────────────────────────────────────────────────────┤
│                                                                    │
│  External Event                    Sunwell Response                │
│  ──────────────────────────        ───────────────────────────     │
│  CI build failed                → Investigate, propose fix         │
│  New issue opened               → Triage, estimate, start work     │
│  Production error spike         → Analyze, create hotfix goal      │
│  PR merged                      → Update dependent code            │
│  Security CVE published         → Assess impact, upgrade deps      │
│  Cron: midnight                 → Run autonomous backlog           │
│                                                                    │
│  Events come in → Goals come out → Guardrails approve → Execute    │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### The Complete Autonomous Loop

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        COMPLETE AUTONOMOUS LOOP                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │  EXTERNAL   │    │    RFC-049  │    │   RFC-046   │    │   RFC-048   │  │
│  │   EVENTS    │───►│  External   │───►│  Autonomous │───►│  Guardrails │  │
│  │             │    │ Integration │    │   Backlog   │    │             │  │
│  └─────────────┘    └─────────────┘    └─────────────┘    └─────────────┘  │
│        │                  │                   │                  │         │
│        │                  │                   │                  ▼         │
│        │                  │                   │           ┌─────────────┐  │
│   CI/CD ────────►   Event ────────►      Goal ────────►  │   RFC-042   │  │
│   Git   ────────►  Adapter ────────►   Generator ────►   │  Adaptive   │  │
│   Issues ───────►         ────────►                ────► │   Agent     │  │
│   Metrics ──────►                                        └─────────────┘  │
│                                                                │           │
│                                                                ▼           │
│                                                         [Code Changes]     │
│                                                                │           │
│                                                                ▼           │
│                              ┌───────────────────────────────────────┐     │
│                              │  Push to Git / Create PR / Comment   │     │
│                              └───────────────────────────────────────┘     │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Goals and Non-Goals

### Goals

1. **CI/CD integration** — React to build failures, test results, deployment events
2. **Git integration** — React to pushes, PRs, branch events, commit hooks
3. **Issue tracker integration** — Triage issues, generate goals from tickets
4. **Production monitoring** — React to error spikes, performance alerts
5. **Webhook-first architecture** — Real-time event processing via HTTP webhooks
6. **Polling fallback** — Support services without webhooks
7. **Event → Goal translation** — Convert external events to RFC-046 goals
8. **Bidirectional communication** — Push results back (comments, status updates)

### Non-Goals

1. **Full CI/CD replacement** — We trigger and observe, not orchestrate builds
2. **Issue tracker management** — We triage and work, not manage workflows
3. **Production deployment** — We propose, not deploy to production
4. **Multi-tenant SaaS** — Single-user, local-first focus
5. **Custom webhook format** — Standard formats only (GitHub, GitLab, etc.)
6. **Real-time chat integration** — Slack/Discord is future work

---

## Design Alternatives Considered

### Option A: Direct API Polling (Rejected)

```python
# Simple approach: Poll APIs periodically
async def poll_loop():
    while True:
        # Poll GitHub API
        issues = await github.list_issues(since=last_check)
        ci_runs = await github.list_workflow_runs(since=last_check)
        
        for issue in issues:
            await process_issue(issue)
        
        await asyncio.sleep(60)  # Poll every minute
```

**Pros**:
- Simple to implement (~100 lines)
- No webhook infrastructure needed
- Works with any API

**Cons**:
- ❌ High latency (up to 60s delay)
- ❌ API rate limits (GitHub: 5,000 req/hour)
- ❌ Wasteful polling when nothing changes
- ❌ Scales poorly with many repos
- ❌ Can't react to CI in real-time

**Verdict**: Too slow for real-time CI response. Rate limits problematic.

### Option B: Webhook-Only (Limited)

```python
# Webhook-only: Server receives all events
@app.post("/webhook/github")
async def github_webhook(request: Request):
    event = await request.json()
    await event_queue.put(("github", event))
```

**Pros**:
- Real-time events
- No polling overhead
- Efficient (only events we care about)

**Cons**:
- ❌ Requires publicly accessible server
- ❌ Not all services support webhooks
- ❌ Complex local development setup
- ❌ Security challenges (webhook verification)

**Verdict**: Ideal but not always available. Need fallback.

### Option C: Hybrid Event System (Selected) ✅

Webhook-first with polling fallback. Event-driven core with pluggable adapters.

```python
# Hybrid: Webhooks when available, polling when not
class EventSource(Protocol):
    """Unified interface for event sources."""
    
    async def subscribe(self, callback: EventCallback) -> None: ...
    async def poll(self) -> list[Event]: ...
    
class GitHubEventSource(EventSource):
    async def subscribe(self, callback):
        # Register webhook if server available
        if self.webhook_server:
            self.webhook_server.register("/github", callback)
        else:
            # Fall back to polling
            self._start_polling(callback)
```

**Pros**:
- ✅ Real-time when webhooks available
- ✅ Graceful fallback to polling
- ✅ Works locally (polling) and in server mode (webhooks)
- ✅ Pluggable adapter architecture
- ✅ Single abstraction for all event sources

**Cons**:
- More complex than pure polling
- Two code paths to maintain
- Webhook setup has security considerations

**Verdict**: Best balance of real-time performance and flexibility.

### Decision Matrix

| Criteria | Polling Only | Webhook Only | Hybrid |
|----------|--------------|--------------|--------|
| Real-time events | ❌ No | ✅ Yes | ✅ Yes |
| Local development | ✅ Easy | ❌ Hard | ✅ Easy |
| API rate limits | ❌ Problem | ✅ None | ✅ Minimal |
| Implementation | Low | Medium | Medium |
| Flexibility | Medium | Low | High |
| **Overall** | ❌ | ⚠️ | ✅ Selected |

---

## Design Overview

### Event-Driven Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        EVENT-DRIVEN ARCHITECTURE                             │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  EXTERNAL SERVICES                SUNWELL                                   │
│                                                                             │
│  ┌──────────────┐                 ┌───────────────────────────────────────┐ │
│  │   GitHub     │───webhook───────►                                       │ │
│  │   Actions    │                 │                                       │ │
│  └──────────────┘                 │           EVENT BUS                   │ │
│                                   │                                       │ │
│  ┌──────────────┐                 │    ┌─────────────────────────────┐    │ │
│  │   GitLab     │───webhook───────►    │   Unified Event Queue       │    │ │
│  │   CI         │                 │    │                             │    │ │
│  └──────────────┘                 │    │   • GitHub events           │    │ │
│                                   │    │   • GitLab events           │    │ │
│  ┌──────────────┐                 │    │   • Sentry alerts           │    │ │
│  │   Linear     │───webhook───────►    │   • Linear issues           │    │ │
│  │   Issues     │                 │    │   • Cron triggers           │    │ │
│  └──────────────┘                 │    │                             │    │ │
│                                   │    └─────────────┬───────────────┘    │ │
│  ┌──────────────┐                 │                  │                    │ │
│  │   Sentry     │───webhook───────►                  │                    │ │
│  │   Alerts     │                 │                  ▼                    │ │
│  └──────────────┘                 │    ┌─────────────────────────────┐    │ │
│                                   │    │     EVENT PROCESSOR         │    │ │
│  ┌──────────────┐                 │    │                             │    │ │
│  │   Cron       │───poll──────────►    │   • Filter by relevance     │    │ │
│  │   Scheduler  │                 │    │   • Deduplicate             │    │ │
│  └──────────────┘                 │    │   • Translate to Goals      │    │ │
│                                   │    │   • Enqueue to Backlog      │    │ │
│                                   │    └─────────────────────────────┘    │ │
│                                   │                                       │ │
│                                   └───────────────────────────────────────┘ │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Event Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            EVENT FLOW                                        │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. EVENT RECEIVED                                                          │
│     ──────────────────────────────────────────────────────────────────      │
│     Webhook POST /webhook/github                                            │
│     {                                                                       │
│       "action": "completed",                                                │
│       "workflow_run": { "conclusion": "failure", ... }                      │
│     }                                                                       │
│                                                                             │
│  2. ADAPTER NORMALIZES                                                      │
│     ──────────────────────────────────────────────────────────────────      │
│     ExternalEvent(                                                          │
│       source="github",                                                      │
│       event_type="ci_failure",                                              │
│       data={"workflow": "test", "conclusion": "failure", ...}               │
│     )                                                                       │
│                                                                             │
│  3. PROCESSOR TRANSLATES TO GOAL                                            │
│     ──────────────────────────────────────────────────────────────────      │
│     Goal(                                                                   │
│       id="ext-ci-failure-abc123",                                           │
│       title="Investigate CI failure: test workflow",                        │
│       category="fix",                                                       │
│       source_type="external",                                               │
│       external_ref="github:workflow_run:12345",                             │
│       priority=0.9,                                                         │
│       auto_approvable=False,  # CI failures need review                     │
│     )                                                                       │
│                                                                             │
│  4. BACKLOG RECEIVES (RFC-046)                                              │
│     ──────────────────────────────────────────────────────────────────      │
│     BacklogManager.add_goal(goal)                                           │
│     → Deduplicates if similar goal exists                                   │
│     → Prioritizes in backlog                                                │
│     → Awaits execution                                                      │
│                                                                             │
│  5. GUARDRAILS CHECK (RFC-048)                                              │
│     ──────────────────────────────────────────────────────────────────      │
│     GuardrailSystem.can_auto_approve(goal) → False (CI failure)             │
│     → Escalates for human approval                                          │
│                                                                             │
│  6. EXECUTION (RFC-042)                                                     │
│     ──────────────────────────────────────────────────────────────────      │
│     AdaptiveAgent.execute(goal)                                             │
│     → Investigates failure                                                  │
│     → Proposes fix                                                          │
│     → Creates commit                                                        │
│                                                                             │
│  7. FEEDBACK TO SOURCE                                                      │
│     ──────────────────────────────────────────────────────────────────      │
│     GitHubAdapter.post_comment(                                             │
│       workflow_run_id=12345,                                                │
│       body="Sunwell investigated. Root cause: missing mock. Fix: abc123"   │
│     )                                                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Components

### 1. External Event Types

```python
from enum import Enum
from dataclasses import dataclass
from datetime import datetime


class EventSource(Enum):
    """Supported external event sources."""
    
    GITHUB = "github"
    GITLAB = "gitlab"
    LINEAR = "linear"
    JIRA = "jira"
    SENTRY = "sentry"
    DATADOG = "datadog"
    CRON = "cron"
    MANUAL = "manual"


class EventType(Enum):
    """Types of external events."""
    
    # CI/CD Events
    CI_FAILURE = "ci_failure"
    CI_SUCCESS = "ci_success"
    DEPLOYMENT_STARTED = "deployment_started"
    DEPLOYMENT_COMPLETED = "deployment_completed"
    DEPLOYMENT_FAILED = "deployment_failed"
    
    # Git Events
    PUSH = "push"
    PULL_REQUEST_OPENED = "pull_request_opened"
    PULL_REQUEST_MERGED = "pull_request_merged"
    PULL_REQUEST_CLOSED = "pull_request_closed"
    BRANCH_CREATED = "branch_created"
    BRANCH_DELETED = "branch_deleted"
    TAG_CREATED = "tag_created"
    
    # Issue Events
    ISSUE_OPENED = "issue_opened"
    ISSUE_ASSIGNED = "issue_assigned"
    ISSUE_LABELED = "issue_labeled"
    ISSUE_CLOSED = "issue_closed"
    ISSUE_COMMENTED = "issue_commented"
    
    # Production Events
    ERROR_SPIKE = "error_spike"
    LATENCY_SPIKE = "latency_spike"
    ERROR_NEW = "error_new"
    ALERT_TRIGGERED = "alert_triggered"
    
    # Scheduled Events
    CRON_TRIGGER = "cron_trigger"


@dataclass(frozen=True, slots=True)
class ExternalEvent:
    """A normalized external event from any source."""
    
    id: str
    """Unique event identifier."""
    
    source: EventSource
    """Where this event came from."""
    
    event_type: EventType
    """Type of event."""
    
    timestamp: datetime
    """When the event occurred."""
    
    data: dict
    """Source-specific event data."""
    
    external_url: str | None = None
    """URL to the event in the external system."""
    
    external_ref: str | None = None
    """External reference ID (e.g., 'github:issue:123')."""
    
    raw_payload: dict | None = None
    """Original webhook payload for debugging."""
    
    @property
    def priority_hint(self) -> float:
        """Suggest priority based on event type."""
        match self.event_type:
            case EventType.CI_FAILURE | EventType.DEPLOYMENT_FAILED:
                return 0.95  # Critical
            case EventType.ERROR_SPIKE | EventType.ALERT_TRIGGERED:
                return 0.90  # High
            case EventType.ISSUE_OPENED:
                return 0.70  # Medium
            case EventType.PULL_REQUEST_OPENED:
                return 0.60  # Normal
            case _:
                return 0.50  # Default
```

---

### 2. Event Adapters

Adapters normalize events from different sources into `ExternalEvent`.

```python
from abc import ABC, abstractmethod
from typing import Protocol, AsyncIterator, Callable


class EventCallback(Protocol):
    """Callback for receiving events."""
    
    async def __call__(self, event: ExternalEvent) -> None: ...


class EventAdapter(ABC):
    """Base class for external service adapters.
    
    Each adapter:
    1. Receives events (webhook or polling)
    2. Normalizes to ExternalEvent
    3. Optionally pushes feedback back to service
    """
    
    @property
    @abstractmethod
    def source(self) -> EventSource:
        """Which source this adapter handles."""
        ...
    
    @abstractmethod
    async def start(self, callback: EventCallback) -> None:
        """Start receiving events, call callback for each."""
        ...
    
    @abstractmethod
    async def stop(self) -> None:
        """Stop receiving events."""
        ...
    
    @abstractmethod
    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify webhook signature for security."""
        ...
    
    @abstractmethod
    async def send_feedback(self, event: ExternalEvent, feedback: EventFeedback) -> None:
        """Send feedback back to the external service."""
        ...


@dataclass(frozen=True, slots=True)
class EventFeedback:
    """Feedback to send back to external service."""
    
    event_id: str
    """Original event ID."""
    
    status: Literal["acknowledged", "investigating", "fixed", "skipped"]
    """Status of Sunwell's response."""
    
    message: str
    """Human-readable message."""
    
    commit_sha: str | None = None
    """Commit SHA if a fix was applied."""
    
    goal_id: str | None = None
    """Internal goal ID for tracking."""
```

#### GitHub Adapter

```python
class GitHubAdapter(EventAdapter):
    """Adapter for GitHub events (Actions, Issues, PRs)."""
    
    source = EventSource.GITHUB
    
    def __init__(
        self,
        token: str,
        webhook_secret: str | None = None,
        repo: str | None = None,
        polling_interval: int = 60,
    ):
        self.token = token
        self.webhook_secret = webhook_secret
        self.repo = repo  # e.g., "owner/repo"
        self.polling_interval = polling_interval
        self._client = httpx.AsyncClient(
            base_url="https://api.github.com",
            headers={"Authorization": f"Bearer {token}"},
        )
    
    async def start(self, callback: EventCallback) -> None:
        """Start receiving GitHub events."""
        if self.webhook_secret:
            # Webhook mode: events come via HTTP
            self._webhook_callback = callback
        else:
            # Polling mode: poll API periodically
            self._polling_task = asyncio.create_task(
                self._poll_loop(callback)
            )
    
    async def _poll_loop(self, callback: EventCallback) -> None:
        """Poll GitHub API for events."""
        last_check = datetime.now(UTC)
        
        while True:
            try:
                # Poll workflow runs
                events = await self._poll_workflow_runs(last_check)
                events.extend(await self._poll_issues(last_check))
                events.extend(await self._poll_pull_requests(last_check))
                
                for event in events:
                    await callback(event)
                
                last_check = datetime.now(UTC)
            except Exception as e:
                logger.error(f"GitHub polling error: {e}")
            
            await asyncio.sleep(self.polling_interval)
    
    def normalize_webhook(self, event_name: str, payload: dict) -> ExternalEvent | None:
        """Convert GitHub webhook payload to ExternalEvent."""
        
        match event_name:
            case "workflow_run":
                if payload.get("action") == "completed":
                    run = payload["workflow_run"]
                    event_type = (
                        EventType.CI_FAILURE 
                        if run["conclusion"] == "failure" 
                        else EventType.CI_SUCCESS
                    )
                    return ExternalEvent(
                        id=f"github-workflow-{run['id']}",
                        source=EventSource.GITHUB,
                        event_type=event_type,
                        timestamp=datetime.fromisoformat(run["updated_at"].replace("Z", "+00:00")),
                        data={
                            "workflow_name": run["name"],
                            "conclusion": run["conclusion"],
                            "branch": run["head_branch"],
                            "commit_sha": run["head_sha"],
                            "run_id": run["id"],
                        },
                        external_url=run["html_url"],
                        external_ref=f"github:workflow_run:{run['id']}",
                        raw_payload=payload,
                    )
            
            case "issues":
                issue = payload["issue"]
                match payload.get("action"):
                    case "opened":
                        return ExternalEvent(
                            id=f"github-issue-{issue['id']}-opened",
                            source=EventSource.GITHUB,
                            event_type=EventType.ISSUE_OPENED,
                            timestamp=datetime.fromisoformat(issue["created_at"].replace("Z", "+00:00")),
                            data={
                                "issue_number": issue["number"],
                                "title": issue["title"],
                                "body": issue["body"],
                                "labels": [l["name"] for l in issue.get("labels", [])],
                                "author": issue["user"]["login"],
                            },
                            external_url=issue["html_url"],
                            external_ref=f"github:issue:{issue['number']}",
                            raw_payload=payload,
                        )
            
            case "pull_request":
                pr = payload["pull_request"]
                match payload.get("action"):
                    case "opened":
                        return ExternalEvent(
                            id=f"github-pr-{pr['id']}-opened",
                            source=EventSource.GITHUB,
                            event_type=EventType.PULL_REQUEST_OPENED,
                            timestamp=datetime.fromisoformat(pr["created_at"].replace("Z", "+00:00")),
                            data={
                                "pr_number": pr["number"],
                                "title": pr["title"],
                                "body": pr["body"],
                                "branch": pr["head"]["ref"],
                                "base_branch": pr["base"]["ref"],
                                "author": pr["user"]["login"],
                            },
                            external_url=pr["html_url"],
                            external_ref=f"github:pull_request:{pr['number']}",
                            raw_payload=payload,
                        )
        
        return None  # Unhandled event type
    
    async def verify_webhook(self, payload: bytes, signature: str) -> bool:
        """Verify GitHub webhook signature."""
        if not self.webhook_secret:
            return False
        
        expected = hmac.new(
            self.webhook_secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()
        
        return hmac.compare_digest(f"sha256={expected}", signature)
    
    async def send_feedback(self, event: ExternalEvent, feedback: EventFeedback) -> None:
        """Post feedback as a comment or status update."""
        
        match event.event_type:
            case EventType.CI_FAILURE:
                # Comment on the commit
                commit_sha = event.data.get("commit_sha")
                if commit_sha:
                    await self._client.post(
                        f"/repos/{self.repo}/commits/{commit_sha}/comments",
                        json={
                            "body": self._format_feedback_message(feedback),
                        },
                    )
            
            case EventType.ISSUE_OPENED:
                # Comment on the issue
                issue_number = event.data.get("issue_number")
                if issue_number:
                    await self._client.post(
                        f"/repos/{self.repo}/issues/{issue_number}/comments",
                        json={
                            "body": self._format_feedback_message(feedback),
                        },
                    )
    
    def _format_feedback_message(self, feedback: EventFeedback) -> str:
        """Format feedback as GitHub-flavored markdown."""
        status_emoji = {
            "acknowledged": "👀",
            "investigating": "🔍",
            "fixed": "✅",
            "skipped": "⏭️",
        }
        
        lines = [
            f"{status_emoji.get(feedback.status, '🤖')} **Sunwell**: {feedback.status.title()}",
            "",
            feedback.message,
        ]
        
        if feedback.commit_sha:
            lines.append(f"\n**Fix**: {feedback.commit_sha[:7]}")
        
        return "\n".join(lines)
```

#### Linear Adapter

```python
class LinearAdapter(EventAdapter):
    """Adapter for Linear issue tracking."""
    
    source = EventSource.LINEAR
    
    def __init__(
        self,
        api_key: str,
        webhook_secret: str | None = None,
        team_id: str | None = None,
    ):
        self.api_key = api_key
        self.webhook_secret = webhook_secret
        self.team_id = team_id
        self._client = httpx.AsyncClient(
            base_url="https://api.linear.app/graphql",
            headers={"Authorization": api_key},
        )
    
    def normalize_webhook(self, payload: dict) -> ExternalEvent | None:
        """Convert Linear webhook to ExternalEvent."""
        
        action = payload.get("action")
        data_type = payload.get("type")
        
        if data_type == "Issue" and action == "create":
            issue = payload.get("data", {})
            return ExternalEvent(
                id=f"linear-issue-{issue.get('id')}-created",
                source=EventSource.LINEAR,
                event_type=EventType.ISSUE_OPENED,
                timestamp=datetime.now(UTC),
                data={
                    "issue_id": issue.get("id"),
                    "title": issue.get("title"),
                    "description": issue.get("description"),
                    "priority": issue.get("priority"),
                    "labels": issue.get("labels", []),
                    "team": issue.get("team", {}).get("name"),
                },
                external_url=issue.get("url"),
                external_ref=f"linear:issue:{issue.get('id')}",
                raw_payload=payload,
            )
        
        return None
    
    async def send_feedback(self, event: ExternalEvent, feedback: EventFeedback) -> None:
        """Create a comment on the Linear issue."""
        
        issue_id = event.data.get("issue_id")
        if not issue_id:
            return
        
        mutation = """
        mutation CreateComment($issueId: String!, $body: String!) {
            commentCreate(input: { issueId: $issueId, body: $body }) {
                success
            }
        }
        """
        
        await self._client.post(
            "",
            json={
                "query": mutation,
                "variables": {
                    "issueId": issue_id,
                    "body": f"🤖 **Sunwell**: {feedback.message}",
                },
            },
        )
```

#### Sentry Adapter (Production Monitoring)

```python
class SentryAdapter(EventAdapter):
    """Adapter for Sentry error tracking."""
    
    source = EventSource.SENTRY
    
    def normalize_webhook(self, payload: dict) -> ExternalEvent | None:
        """Convert Sentry webhook to ExternalEvent."""
        
        action = payload.get("action")
        
        if action == "triggered":
            # Alert triggered
            data = payload.get("data", {})
            event_data = data.get("event", {})
            
            return ExternalEvent(
                id=f"sentry-alert-{event_data.get('event_id')}",
                source=EventSource.SENTRY,
                event_type=EventType.ALERT_TRIGGERED,
                timestamp=datetime.now(UTC),
                data={
                    "title": event_data.get("title"),
                    "message": event_data.get("message"),
                    "level": event_data.get("level"),
                    "culprit": event_data.get("culprit"),
                    "platform": event_data.get("platform"),
                    "tags": event_data.get("tags", {}),
                },
                external_url=event_data.get("web_url"),
                external_ref=f"sentry:event:{event_data.get('event_id')}",
                raw_payload=payload,
            )
        
        return None
```

---

### 3. Event Processor

Translates external events into RFC-046 goals.

```python
class EventProcessor:
    """Process external events and generate goals.
    
    Translation strategy:
    1. Receive ExternalEvent from adapter
    2. Check if similar goal already exists (dedupe)
    3. Translate to Goal using event-specific logic
    4. Add to BacklogManager (RFC-046)
    5. Optionally send acknowledgment back to source
    """
    
    def __init__(
        self,
        backlog_manager: BacklogManager,
        goal_policy: ExternalGoalPolicy,
        feedback_enabled: bool = True,
    ):
        self.backlog_manager = backlog_manager
        self.goal_policy = goal_policy
        self.feedback_enabled = feedback_enabled
        self._adapters: dict[EventSource, EventAdapter] = {}
    
    def register_adapter(self, adapter: EventAdapter) -> None:
        """Register an event adapter."""
        self._adapters[adapter.source] = adapter
    
    async def process_event(self, event: ExternalEvent) -> Goal | None:
        """Process an external event and potentially create a goal.
        
        Returns the created goal, or None if filtered/deduplicated.
        """
        # 1. Check policy (should we handle this event?)
        if not self.goal_policy.should_process(event):
            logger.debug(f"Event filtered by policy: {event.id}")
            return None
        
        # 2. Check for duplicates
        if await self._is_duplicate(event):
            logger.debug(f"Duplicate event: {event.id}")
            return None
        
        # 3. Translate to goal
        goal = await self._translate_to_goal(event)
        if goal is None:
            return None
        
        # 4. Add to backlog
        await self.backlog_manager.add_external_goal(goal)
        
        # 5. Send acknowledgment
        if self.feedback_enabled:
            adapter = self._adapters.get(event.source)
            if adapter:
                await adapter.send_feedback(
                    event,
                    EventFeedback(
                        event_id=event.id,
                        status="acknowledged",
                        message=f"Added to Sunwell backlog: {goal.title}",
                        goal_id=goal.id,
                    ),
                )
        
        return goal
    
    async def _translate_to_goal(self, event: ExternalEvent) -> Goal | None:
        """Convert external event to a Goal."""
        
        match event.event_type:
            case EventType.CI_FAILURE:
                return self._goal_from_ci_failure(event)
            case EventType.ISSUE_OPENED:
                return self._goal_from_issue(event)
            case EventType.ERROR_SPIKE | EventType.ALERT_TRIGGERED:
                return self._goal_from_alert(event)
            case EventType.PULL_REQUEST_OPENED:
                return self._goal_from_pr(event)
            case _:
                return None
    
    def _goal_from_ci_failure(self, event: ExternalEvent) -> Goal:
        """Create goal from CI failure."""
        return Goal(
            id=f"ext-ci-{event.data.get('run_id', event.id)}",
            title=f"Investigate CI failure: {event.data.get('workflow_name', 'unknown')}",
            description=(
                f"CI workflow '{event.data.get('workflow_name')}' failed on branch "
                f"'{event.data.get('branch')}'. Commit: {event.data.get('commit_sha', 'unknown')[:7]}.\n\n"
                f"View details: {event.external_url}"
            ),
            source_signals=(event.external_ref,) if event.external_ref else (),
            priority=0.95,  # CI failures are high priority
            estimated_complexity="simple",  # Investigation first
            requires=frozenset(),
            category="fix",
            auto_approvable=False,  # CI failures need human review
            scope=GoalScope(max_files=5, max_lines_changed=200),
            external_event=event,
        )
    
    def _goal_from_issue(self, event: ExternalEvent) -> Goal:
        """Create goal from new issue."""
        title = event.data.get("title", "Unknown issue")
        labels = event.data.get("labels", [])
        
        # Determine category from labels
        category = "improve"
        if "bug" in labels or "fix" in labels:
            category = "fix"
        elif "enhancement" in labels or "feature" in labels:
            category = "add"
        elif "documentation" in labels:
            category = "document"
        
        # Determine complexity from labels
        complexity = "moderate"
        if "trivial" in labels or "good first issue" in labels:
            complexity = "simple"
        elif "complex" in labels or "epic" in labels:
            complexity = "complex"
        
        return Goal(
            id=f"ext-issue-{event.data.get('issue_number', event.id)}",
            title=f"Issue #{event.data.get('issue_number')}: {title[:60]}",
            description=(
                f"**Issue**: {title}\n\n"
                f"**Author**: {event.data.get('author', 'unknown')}\n"
                f"**Labels**: {', '.join(labels) if labels else 'none'}\n\n"
                f"**Body**:\n{event.data.get('body', 'No description provided.')}\n\n"
                f"**Link**: {event.external_url}"
            ),
            source_signals=(event.external_ref,) if event.external_ref else (),
            priority=event.priority_hint,
            estimated_complexity=complexity,
            requires=frozenset(),
            category=category,
            auto_approvable=self.goal_policy.auto_approve_issues,
            scope=GoalScope(max_files=10, max_lines_changed=500),
            external_event=event,
        )
    
    def _goal_from_alert(self, event: ExternalEvent) -> Goal:
        """Create goal from production alert."""
        return Goal(
            id=f"ext-alert-{event.id}",
            title=f"Production alert: {event.data.get('title', 'Unknown')[:60]}",
            description=(
                f"**Alert**: {event.data.get('title')}\n\n"
                f"**Level**: {event.data.get('level', 'unknown')}\n"
                f"**Message**: {event.data.get('message', 'No message')}\n"
                f"**Culprit**: {event.data.get('culprit', 'unknown')}\n\n"
                f"**Link**: {event.external_url}"
            ),
            source_signals=(event.external_ref,) if event.external_ref else (),
            priority=0.90,  # Production alerts are high priority
            estimated_complexity="moderate",
            requires=frozenset(),
            category="fix",
            auto_approvable=False,  # Production issues need review
            scope=GoalScope(max_files=5, max_lines_changed=200),
            external_event=event,
        )
    
    async def _is_duplicate(self, event: ExternalEvent) -> bool:
        """Check if a similar goal already exists."""
        if not event.external_ref:
            return False
        
        existing_goals = await self.backlog_manager.get_goals_by_external_ref(
            event.external_ref
        )
        return len(existing_goals) > 0
```

---

### 4. Goal Policy for External Events

```python
@dataclass
class ExternalGoalPolicy:
    """Policy for handling external events as goals.
    
    Controls which events become goals and their behavior.
    """
    
    # === Event Filtering ===
    
    enabled_sources: frozenset[EventSource] = frozenset({
        EventSource.GITHUB,
        EventSource.GITLAB,
    })
    """Which event sources to process."""
    
    enabled_event_types: frozenset[EventType] = frozenset({
        EventType.CI_FAILURE,
        EventType.ISSUE_OPENED,
        EventType.ALERT_TRIGGERED,
    })
    """Which event types to process."""
    
    issue_label_filter: frozenset[str] | None = None
    """Only process issues with these labels. None = all issues."""
    
    exclude_labels: frozenset[str] = frozenset({"wontfix", "duplicate", "sunwell-skip"})
    """Skip issues with these labels."""
    
    min_priority: float = 0.3
    """Minimum priority to create goal (filter low-value events)."""
    
    # === Auto-Approval ===
    
    auto_approve_issues: bool = False
    """Auto-approve goals from issues (requires guardrails check)."""
    
    auto_approve_ci_failures: bool = False
    """Auto-approve CI failure investigations."""
    
    # === Rate Limiting ===
    
    max_events_per_hour: int = 50
    """Maximum events to process per hour (prevent runaway)."""
    
    max_goals_per_day: int = 20
    """Maximum goals to create per day."""
    
    cooldown_minutes: int = 5
    """Minimum time between goals from same external ref."""
    
    def should_process(self, event: ExternalEvent) -> bool:
        """Check if event should be processed."""
        # Check source
        if event.source not in self.enabled_sources:
            return False
        
        # Check event type
        if event.event_type not in self.enabled_event_types:
            return False
        
        # Check priority
        if event.priority_hint < self.min_priority:
            return False
        
        # Check issue labels
        if event.event_type == EventType.ISSUE_OPENED:
            labels = set(event.data.get("labels", []))
            
            # Exclude blocked labels
            if labels & self.exclude_labels:
                return False
            
            # Include only allowed labels (if filter set)
            if self.issue_label_filter and not (labels & self.issue_label_filter):
                return False
        
        return True
```

---

### 5. Webhook Server

For receiving webhook events when running in server mode.

```python
from fastapi import FastAPI, Request, HTTPException
from fastapi.responses import JSONResponse


class WebhookServer:
    """HTTP server for receiving webhooks."""
    
    def __init__(
        self,
        processor: EventProcessor,
        host: str = "0.0.0.0",
        port: int = 8080,
    ):
        self.processor = processor
        self.host = host
        self.port = port
        self.app = FastAPI(title="Sunwell Webhooks")
        self._setup_routes()
    
    def _setup_routes(self) -> None:
        """Configure webhook endpoints."""
        
        @self.app.post("/webhook/github")
        async def github_webhook(request: Request):
            return await self._handle_github(request)
        
        @self.app.post("/webhook/gitlab")
        async def gitlab_webhook(request: Request):
            return await self._handle_gitlab(request)
        
        @self.app.post("/webhook/linear")
        async def linear_webhook(request: Request):
            return await self._handle_linear(request)
        
        @self.app.post("/webhook/sentry")
        async def sentry_webhook(request: Request):
            return await self._handle_sentry(request)
        
        @self.app.get("/health")
        async def health():
            return {"status": "healthy"}
    
    async def _handle_github(self, request: Request) -> JSONResponse:
        """Handle GitHub webhook."""
        # Verify signature
        signature = request.headers.get("X-Hub-Signature-256", "")
        body = await request.body()
        
        adapter = self.processor._adapters.get(EventSource.GITHUB)
        if not adapter:
            raise HTTPException(503, "GitHub adapter not configured")
        
        if not await adapter.verify_webhook(body, signature):
            raise HTTPException(401, "Invalid webhook signature")
        
        # Parse and process
        event_name = request.headers.get("X-GitHub-Event", "")
        payload = await request.json()
        
        event = adapter.normalize_webhook(event_name, payload)
        if event:
            await self.processor.process_event(event)
        
        return JSONResponse({"status": "ok"})
    
    async def _handle_linear(self, request: Request) -> JSONResponse:
        """Handle Linear webhook."""
        adapter = self.processor._adapters.get(EventSource.LINEAR)
        if not adapter:
            raise HTTPException(503, "Linear adapter not configured")
        
        payload = await request.json()
        event = adapter.normalize_webhook(payload)
        if event:
            await self.processor.process_event(event)
        
        return JSONResponse({"status": "ok"})
    
    async def start(self) -> None:
        """Start the webhook server."""
        import uvicorn
        config = uvicorn.Config(self.app, host=self.host, port=self.port)
        server = uvicorn.Server(config)
        await server.serve()
```

---

### 6. Cron Scheduler

For scheduled events (nightly backlog runs, periodic polling).

```python
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger


class ExternalScheduler:
    """Schedule external events on cron patterns."""
    
    def __init__(self, processor: EventProcessor):
        self.processor = processor
        self.scheduler = AsyncIOScheduler()
    
    def add_cron_job(
        self,
        name: str,
        cron_expression: str,
        event_factory: Callable[[], ExternalEvent],
    ) -> None:
        """Add a scheduled job.
        
        Args:
            name: Job identifier
            cron_expression: Cron pattern (e.g., "0 0 * * *" for midnight)
            event_factory: Function that creates the event to process
        """
        trigger = CronTrigger.from_crontab(cron_expression)
        
        async def job():
            event = event_factory()
            await self.processor.process_event(event)
        
        self.scheduler.add_job(
            job,
            trigger=trigger,
            id=name,
            name=name,
            replace_existing=True,
        )
    
    def add_default_schedules(self) -> None:
        """Add default scheduled jobs."""
        
        # Nightly backlog refresh
        self.add_cron_job(
            name="nightly_backlog",
            cron_expression="0 0 * * *",  # Midnight
            event_factory=lambda: ExternalEvent(
                id=f"cron-nightly-{datetime.now().date()}",
                source=EventSource.CRON,
                event_type=EventType.CRON_TRIGGER,
                timestamp=datetime.now(UTC),
                data={"trigger": "nightly_backlog"},
            ),
        )
        
        # Dependency security check (weekly)
        self.add_cron_job(
            name="weekly_security",
            cron_expression="0 9 * * 1",  # Monday 9am
            event_factory=lambda: ExternalEvent(
                id=f"cron-security-{datetime.now().isocalendar().week}",
                source=EventSource.CRON,
                event_type=EventType.CRON_TRIGGER,
                timestamp=datetime.now(UTC),
                data={"trigger": "security_scan"},
            ),
        )
    
    def start(self) -> None:
        """Start the scheduler."""
        self.scheduler.start()
    
    def stop(self) -> None:
        """Stop the scheduler."""
        self.scheduler.shutdown()
```

---

## Configuration

```yaml
# sunwell.yaml or pyproject.toml [tool.sunwell.external]

external:
  enabled: true
  
  # Webhook server
  server:
    enabled: true
    host: "0.0.0.0"
    port: 8080
  
  # Event sources
  sources:
    github:
      enabled: true
      token: "${GITHUB_TOKEN}"  # Environment variable
      webhook_secret: "${GITHUB_WEBHOOK_SECRET}"
      repo: "owner/repo"
      polling_interval: 60  # Fallback polling interval
      
    linear:
      enabled: false
      api_key: "${LINEAR_API_KEY}"
      team_id: "team_id"
      
    sentry:
      enabled: false
      webhook_secret: "${SENTRY_WEBHOOK_SECRET}"
  
  # Event policy
  policy:
    enabled_event_types:
      - ci_failure
      - issue_opened
      - alert_triggered
    
    issue_label_filter:
      - bug
      - enhancement
      - sunwell
    
    exclude_labels:
      - wontfix
      - duplicate
      - sunwell-skip
    
    auto_approve_issues: false
    auto_approve_ci_failures: false
    
    rate_limiting:
      max_events_per_hour: 50
      max_goals_per_day: 20
      cooldown_minutes: 5
  
  # Scheduled jobs
  schedules:
    nightly_backlog:
      enabled: true
      cron: "0 0 * * *"  # Midnight
      
    weekly_security:
      enabled: true
      cron: "0 9 * * 1"  # Monday 9am
  
  # Feedback
  feedback:
    enabled: true
    post_acknowledgments: true
    post_completions: true
```

---

## CLI Integration

### Webhook Server and CLI Coexistence

The webhook server runs as a **separate process** from the main CLI:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                    PROCESS ARCHITECTURE                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Terminal 1                        Terminal 2                               │
│  ─────────────────                 ─────────────────                        │
│  $ sunwell external start          $ sunwell agent "Fix the bug"            │
│                                                                             │
│  ┌───────────────────────┐         ┌───────────────────────┐                │
│  │  WEBHOOK SERVER       │         │  INTERACTIVE CLI      │                │
│  │  (long-running)       │         │  (on-demand)          │                │
│  │                       │         │                       │                │
│  │  • HTTP server :8080  │         │  • User commands      │                │
│  │  • Event polling      │         │  • Agent execution    │                │
│  │  • Cron scheduler     │         │  • Direct goals       │                │
│  │                       │         │                       │                │
│  └───────────┬───────────┘         └───────────┬───────────┘                │
│              │                                 │                            │
│              │    ┌─────────────────────┐      │                            │
│              └───►│  SHARED BACKLOG     │◄─────┘                            │
│                   │  .sunwell/backlog/  │                                   │
│                   │                     │                                   │
│                   │  • File-based       │                                   │
│                   │  • Process-safe     │                                   │
│                   │  • Atomic writes    │                                   │
│                   └─────────────────────┘                                   │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Why separate processes?**

1. **Webhook server must stay running** — Can't block on user interaction
2. **CLI is interactive** — User expects immediate response
3. **Independence** — Server crash doesn't affect CLI, vice versa
4. **Simpler resource management** — No threading complexity

**Shared state via filesystem**:

```python
# Backlog uses file locking for process safety
class BacklogManager:
    def _save(self) -> None:
        import fcntl
        
        with open(self.backlog_path / "current.json", "w") as f:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                json.dump(self._serialize(), f)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
```

### Commands

```bash
# Start external integration
sunwell external start           # Start webhook server + polling
sunwell external start --no-server  # Polling only (no webhook server)

# Manual event processing
sunwell external poll            # Force poll all sources now
sunwell external poll github     # Poll specific source

# Configuration
sunwell external status          # Show external integration status
sunwell external test github     # Test GitHub connection

# View events
sunwell external events          # List recent events
sunwell external events --source github  # Filter by source
sunwell external events --pending  # Show unprocessed events

# Webhook management
sunwell external webhook setup github  # Interactive webhook setup
sunwell external webhook verify github  # Verify webhook config
sunwell external webhook url     # Show webhook URLs

# Schedule management
sunwell external schedules       # List scheduled jobs
sunwell external schedules run nightly_backlog  # Run job now
```

### Example Session

```
$ sunwell external start

🌐 External Integration Started
   Webhook server: http://0.0.0.0:8080
   
   Sources:
   ✅ GitHub: polling (webhook not configured)
   ✅ Cron: 2 scheduled jobs
   ❌ Linear: disabled
   ❌ Sentry: disabled
   
   Endpoints:
   POST /webhook/github → ready
   POST /webhook/linear → ready (disabled)
   GET  /health         → ready

📅 Scheduled Jobs:
   • nightly_backlog: 0 0 * * * (next: tonight 00:00)
   • weekly_security: 0 9 * * 1 (next: Monday 09:00)

Listening for events...

───────────────────────────────────────────────────────────────

[12:34:56] 📨 Event received: github:ci_failure
           Workflow: test (branch: main)
           
[12:34:56] ➕ Goal created: ext-ci-12345
           "Investigate CI failure: test workflow"
           Priority: 0.95 | Auto-approve: No
           
[12:34:57] 💬 Feedback sent to GitHub
           "Added to Sunwell backlog"

───────────────────────────────────────────────────────────────

[12:45:00] 📨 Event received: github:issue_opened
           Issue #42: "Add dark mode support"
           Labels: enhancement
           
[12:45:00] ➕ Goal created: ext-issue-42
           "Issue #42: Add dark mode support"
           Priority: 0.70 | Auto-approve: No
           
[12:45:01] 💬 Feedback sent to GitHub
           "Added to Sunwell backlog"
```

---

## Integration with Existing Systems

### With RFC-046 (Autonomous Backlog)

External events become goals in the backlog:

```python
# In BacklogManager (RFC-046)

class BacklogManager:
    async def add_external_goal(self, goal: Goal) -> None:
        """Add a goal from an external event.
        
        External goals are:
        1. Marked with source_type='external'
        2. Tracked separately for deduplication
        3. Prioritized alongside internal goals
        """
        # Mark as external
        goal = dataclasses.replace(
            goal,
            metadata={"source_type": "external"},
        )
        
        # Add to backlog
        self.backlog.goals[goal.id] = goal
        
        # Track external reference for deduplication
        if goal.external_event:
            self._external_refs[goal.external_event.external_ref] = goal.id
    
    async def get_goals_by_external_ref(self, ref: str) -> list[Goal]:
        """Get goals associated with an external reference."""
        goal_id = self._external_refs.get(ref)
        if goal_id and goal_id in self.backlog.goals:
            return [self.backlog.goals[goal_id]]
        return []
```

### With RFC-048 (Autonomy Guardrails)

External goals respect guardrails:

```python
# Guardrails check for external goals

class GuardrailSystem:
    async def can_auto_approve_external(self, goal: Goal) -> bool:
        """Check if external goal can be auto-approved.
        
        External goals have additional scrutiny:
        - Source must be trusted
        - Event type must allow auto-approval
        - Standard guardrail checks still apply
        """
        if not goal.external_event:
            return False
        
        event = goal.external_event
        
        # Check source trust
        if event.source not in self.config.trusted_sources:
            return False
        
        # Check event type allows auto-approve
        match event.event_type:
            case EventType.CI_FAILURE:
                if not self.config.policy.auto_approve_ci_failures:
                    return False
            case EventType.ISSUE_OPENED:
                if not self.config.policy.auto_approve_issues:
                    return False
            case _:
                return False  # Unknown types never auto-approve
        
        # Standard guardrail checks
        return await self.can_auto_approve(goal)
```

### With RFC-042 (Adaptive Agent)

CI failures inform technique selection:

```python
# Adaptive signals include external context

@dataclass
class AdaptiveSignals:
    # Existing signals
    complexity: Complexity
    error_state: ErrorState
    
    # New: External context
    is_external_goal: bool
    external_source: EventSource | None
    external_priority: float
    ci_context: CIContext | None  # Failed tests, logs, etc.
```

---

## Backwards Compatibility

This RFC introduces changes to existing dataclasses and managers. This section documents migration strategy.

### Goal Dataclass Extension

**Current implementation** (`src/sunwell/backlog/goals.py`):

```python
@dataclass(frozen=True, slots=True)
class Goal:
    id: str
    title: str
    description: str
    source_signals: tuple[str, ...]
    priority: float
    estimated_complexity: Literal["trivial", "simple", "moderate", "complex"]
    requires: frozenset[str]
    category: Literal["fix", "improve", "add", ...]
    auto_approvable: bool
    scope: GoalScope
```

**Proposed extension** — Add optional `external_ref` field (NOT embedding full `ExternalEvent`):

```python
@dataclass(frozen=True, slots=True)
class Goal:
    # ... existing fields ...
    
    external_ref: str | None = None
    """External reference for deduplication (e.g., 'github:issue:123').
    
    Using string ref instead of ExternalEvent object because:
    1. Goal is frozen/serialized — embedding mutable event data is problematic
    2. Deduplication only needs the ref, not full event
    3. Full event can be stored separately in ExternalEventStore
    """
```

**Migration strategy**:

1. Add `external_ref` with `None` default — backwards compatible
2. Existing backlog JSON will deserialize cleanly (missing field gets default)
3. No schema versioning needed for this change

**Why NOT embed ExternalEvent in Goal**:

The original RFC showed `external_event: ExternalEvent` on Goal. This is problematic:

- Goal is `frozen=True` with `slots=True` — serializes to JSON
- ExternalEvent contains `raw_payload: dict` which may be large/sensitive
- Deduplication only needs the `external_ref` string

**Instead**: Store full `ExternalEvent` in a separate `ExternalEventStore`:

```python
class ExternalEventStore:
    """Persistent store for external events (separate from backlog)."""
    
    def __init__(self, root: Path):
        self._path = root / ".sunwell" / "external" / "events.jsonl"
    
    async def store(self, event: ExternalEvent) -> None:
        """Append event to store."""
        ...
    
    async def get_by_ref(self, external_ref: str) -> ExternalEvent | None:
        """Retrieve event by external reference."""
        ...
```

### BacklogManager Extensions

**New methods** (additive, no breaking changes):

```python
class BacklogManager:
    # ... existing methods ...
    
    # NEW: Initialize external ref index
    def __init__(self, ...):
        ...
        self._external_refs: dict[str, str] = {}  # external_ref → goal_id
    
    # NEW: Add goal from external event
    async def add_external_goal(self, goal: Goal) -> None:
        """Add a goal from an external event.
        
        Separate method to:
        1. Track external refs for deduplication
        2. Apply external-specific policies
        3. Log external goal creation
        """
        self.backlog.goals[goal.id] = goal
        if goal.external_ref:
            self._external_refs[goal.external_ref] = goal.id
        self._save()
    
    # NEW: Lookup by external ref
    async def get_goals_by_external_ref(self, ref: str) -> list[Goal]:
        """Find goals by external reference for deduplication."""
        goal_id = self._external_refs.get(ref)
        if goal_id and goal_id in self.backlog.goals:
            return [self.backlog.goals[goal_id]]
        return []
```

**Persistence migration**:

The `_external_refs` index should be persisted alongside the backlog:

```python
def _save(self) -> None:
    data = {
        "goals": {...},
        "completed": [...],
        "in_progress": ...,
        "blocked": {...},
        "external_refs": self._external_refs,  # NEW
        "schema_version": 2,  # Bump version
    }
```

**Loading old backlogs**:

```python
def _load(self) -> None:
    data = json.loads(current_path.read_text())
    
    # Handle missing external_refs (old schema)
    self._external_refs = data.get("external_refs", {})
    
    # Rebuild index from goals if needed
    if not self._external_refs:
        for goal in self.backlog.goals.values():
            if goal.external_ref:
                self._external_refs[goal.external_ref] = goal.id
```

### AdaptiveSignals Extension (RFC-042)

**Approach**: Composition over modification.

Instead of modifying `AdaptiveSignals`, create a wrapper for external context:

```python
# NEW: src/sunwell/external/context.py

@dataclass(frozen=True, slots=True)
class ExternalContext:
    """External context for adaptive routing (RFC-042 integration)."""
    
    is_external_goal: bool = False
    """Whether this goal originated from an external event."""
    
    external_source: EventSource | None = None
    """Source of the external event (github, linear, etc.)."""
    
    external_priority: float = 0.5
    """Priority hint from external event."""
    
    ci_logs: str | None = None
    """CI failure logs if available (for CI failure goals)."""
    
    issue_body: str | None = None
    """Issue body if this is an issue-triggered goal."""


# Usage in AdaptiveAgent
async def execute(
    self,
    goal: str,
    *,
    external_context: ExternalContext | None = None,
) -> AsyncIterator[AgentEvent]:
    signals = await self._extract_signals(goal)
    
    # Boost signals based on external context
    if external_context and external_context.is_external_goal:
        # CI failures get VORTEX to explore failure causes
        if external_context.ci_logs:
            signals = signals.with_boost(0.1)  # More exploration
```

**Why composition over modification**:

1. `AdaptiveSignals` is stable, used across many modules
2. External context is optional — most goals won't have it
3. Avoids breaking existing signal extraction pipeline

### GuardrailSystem Extensions (RFC-048)

**New method** (additive):

```python
# src/sunwell/guardrails/system.py

class GuardrailSystem:
    # ... existing methods ...
    
    async def can_auto_approve_external(self, goal: Goal, event: ExternalEvent) -> bool:
        """Check if external-triggered goal can be auto-approved.
        
        External goals have ADDITIONAL scrutiny beyond normal guardrails:
        1. Source must be in trusted_sources
        2. Event type must allow auto-approval per policy
        3. All standard guardrail checks still apply
        """
        # Check source trust
        if event.source not in self.config.trusted_external_sources:
            return False
        
        # Check event type allows auto-approve
        policy = self.config.external_policy
        match event.event_type:
            case EventType.CI_FAILURE:
                if not policy.auto_approve_ci_failures:
                    return False
            case EventType.ISSUE_OPENED:
                if not policy.auto_approve_issues:
                    return False
            case _:
                return False  # Unknown types never auto-approve
        
        # Standard guardrail checks
        return await self.can_auto_approve(goal)
```

**Configuration extension**:

```python
# src/sunwell/guardrails/config.py

@dataclass
class GuardrailConfig:
    # ... existing fields ...
    
    # NEW: External integration settings
    trusted_external_sources: frozenset[EventSource] = frozenset({
        EventSource.GITHUB,
        EventSource.GITLAB,
    })
    """Sources trusted for external event processing."""
    
    external_policy: ExternalGoalPolicy | None = None
    """Policy for external goal auto-approval (default: None = never auto)."""
```

---

## Dependencies

### Required Packages

```toml
# pyproject.toml additions

[project.optional-dependencies]
external = [
    "httpx>=0.27.0",           # Async HTTP client for API calls
    "fastapi>=0.109.0",        # Webhook server
    "uvicorn>=0.27.0",         # ASGI server for FastAPI
    "apscheduler>=3.10.0",     # Cron scheduling
    "pydantic>=2.5.0",         # Request/response validation (FastAPI dep)
]
```

### Version Constraints Rationale

| Package | Min Version | Reason |
|---------|-------------|--------|
| `httpx` | 0.27.0 | Stable async client, HTTP/2 support |
| `fastapi` | 0.109.0 | Modern OpenAPI, Pydantic v2 |
| `uvicorn` | 0.27.0 | Matches FastAPI requirements |
| `apscheduler` | 3.10.0 | AsyncIO scheduler, cron syntax |

### Python Version

Requires Python 3.12+ (matches Sunwell baseline).

---

## Security Considerations

### Webhook Verification

All webhooks must be verified. Signature verification happens **before** JSON parsing to prevent attacks via malformed JSON.

**Verification Sequence**:

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                   WEBHOOK VERIFICATION SEQUENCE                              │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  GitHub/GitLab                 Sunwell Webhook Server                       │
│  ────────────────              ──────────────────────                       │
│                                                                             │
│  1. POST /webhook/github                                                    │
│     Headers:                                                                │
│       X-Hub-Signature-256: sha256=abc123...                                 │
│       X-GitHub-Event: workflow_run                                          │
│     Body: {"action": "completed", ...}                                      │
│           │                                                                 │
│           ▼                                                                 │
│  2. Read raw body (bytes)                                                   │
│     ──────────────────────────────                                          │
│     body = await request.body()                                             │
│     DO NOT parse JSON yet!                                                  │
│           │                                                                 │
│           ▼                                                                 │
│  3. Verify signature                                                        │
│     ──────────────────────────────                                          │
│     expected = hmac.new(secret, body, sha256).hexdigest()                   │
│     if not compare_digest(expected, signature):                             │
│         return 401 Unauthorized ───────────────────────► REJECT             │
│           │                                                                 │
│           ▼                                                                 │
│  4. Check IP allowlist (optional)                                           │
│     ──────────────────────────────                                          │
│     if ip not in allowed_ips:                                               │
│         return 403 Forbidden ──────────────────────────► REJECT             │
│           │                                                                 │
│           ▼                                                                 │
│  5. Parse JSON (now safe)                                                   │
│     ──────────────────────────────                                          │
│     payload = json.loads(body)                                              │
│           │                                                                 │
│           ▼                                                                 │
│  6. Normalize to ExternalEvent                                              │
│     ──────────────────────────────                                          │
│     event = adapter.normalize_webhook(event_name, payload)                  │
│           │                                                                 │
│           ▼                                                                 │
│  7. Process event                                                           │
│     ──────────────────────────────                                          │
│     await processor.process_event(event)                                    │
│           │                                                                 │
│           ▼                                                                 │
│  8. Return 200 OK ─────────────────────────────────────► SUCCESS            │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Implementation**:

```python
# GitHub: HMAC-SHA256
async def _handle_github(self, request: Request) -> JSONResponse:
    # 1. Read raw body FIRST
    body = await request.body()
    
    # 2. Verify signature BEFORE parsing
    signature = request.headers.get("X-Hub-Signature-256", "")
    adapter = self.processor._adapters.get(EventSource.GITHUB)
    
    if not adapter or not await adapter.verify_webhook(body, signature):
        # Log attempt but don't reveal details
        logger.warning(f"Invalid webhook signature from {request.client.host}")
        raise HTTPException(401, "Invalid signature")
    
    # 3. NOW safe to parse JSON
    payload = json.loads(body)
    event_name = request.headers.get("X-GitHub-Event", "")
    
    # 4. Process
    event = adapter.normalize_webhook(event_name, payload)
    if event:
        await self.processor.process_event(event)
    
    return JSONResponse({"status": "ok"})


# Signature verification implementation
async def verify_webhook(self, payload: bytes, signature: str) -> bool:
    """Verify GitHub webhook signature using constant-time comparison."""
    if not self.webhook_secret:
        return False
    
    expected = hmac.new(
        self.webhook_secret.encode(),
        payload,
        hashlib.sha256,
    ).hexdigest()
    
    # CRITICAL: Use constant-time comparison to prevent timing attacks
    return hmac.compare_digest(f"sha256={expected}", signature)
```

**Provider-specific verification**:

| Provider | Header | Algorithm |
|----------|--------|-----------|
| GitHub | `X-Hub-Signature-256` | HMAC-SHA256 |
| GitLab | `X-Gitlab-Token` | Secret token comparison |
| Linear | `Linear-Webhook-Signature` | HMAC-SHA256 |
| Sentry | `Sentry-Hook-Signature` | HMAC-SHA256 |

### Token Storage

```yaml
# Never store tokens in config files
# Use environment variables or secret managers

external:
  sources:
    github:
      token: "${GITHUB_TOKEN}"  # Environment variable
      # Or: token_file: "/run/secrets/github_token"  # Docker secret
      # Or: token_command: "vault read -field=token secret/github"  # Vault
```

### Network Isolation

```yaml
# Webhook server can be restricted
server:
  host: "127.0.0.1"  # Local only (use ngrok/tunnel for external)
  allowed_ips:
    - "192.30.252.0/22"  # GitHub webhook IPs
    - "185.199.108.0/22"
```

### Rate Limiting

Rate limiting uses a sliding window algorithm with per-source buckets:

```python
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import deque
import threading


@dataclass
class RateLimitBucket:
    """Sliding window rate limit bucket."""
    
    window_seconds: int = 3600  # 1 hour
    max_events: int = 50
    events: deque[datetime] = field(default_factory=deque)
    _lock: threading.Lock = field(default_factory=threading.Lock)
    
    def allow(self) -> bool:
        """Check if event is allowed under rate limit."""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        with self._lock:
            # Remove events outside window
            while self.events and self.events[0] < window_start:
                self.events.popleft()
            
            # Check limit
            if len(self.events) >= self.max_events:
                return False
            
            # Record event
            self.events.append(now)
            return True
    
    @property
    def remaining(self) -> int:
        """Events remaining in current window."""
        now = datetime.now()
        window_start = now - timedelta(seconds=self.window_seconds)
        
        with self._lock:
            while self.events and self.events[0] < window_start:
                self.events.popleft()
            return max(0, self.max_events - len(self.events))


class RateLimiter:
    """Per-source rate limiter."""
    
    def __init__(self, policy: ExternalGoalPolicy):
        self.policy = policy
        self._buckets: dict[EventSource, RateLimitBucket] = {}
        self._daily_count: dict[str, int] = {}  # date → count
        self._cooldowns: dict[str, datetime] = {}  # external_ref → last_goal_time
    
    def allow(self, event: ExternalEvent) -> tuple[bool, str]:
        """Check if event is allowed.
        
        Returns:
            (allowed, reason) — reason explains why blocked
        """
        # 1. Per-source hourly limit
        bucket = self._buckets.setdefault(
            event.source,
            RateLimitBucket(max_events=self.policy.max_events_per_hour),
        )
        if not bucket.allow():
            return False, f"Rate limited: {event.source} ({bucket.remaining} remaining)"
        
        # 2. Daily goal limit
        today = datetime.now().date().isoformat()
        daily = self._daily_count.get(today, 0)
        if daily >= self.policy.max_goals_per_day:
            return False, f"Daily limit reached: {daily}/{self.policy.max_goals_per_day}"
        
        # 3. Cooldown per external ref
        if event.external_ref:
            last_time = self._cooldowns.get(event.external_ref)
            if last_time:
                elapsed = (datetime.now() - last_time).total_seconds() / 60
                if elapsed < self.policy.cooldown_minutes:
                    return False, f"Cooldown: {event.external_ref} ({self.policy.cooldown_minutes - elapsed:.1f}m remaining)"
        
        return True, "allowed"
    
    def record_goal_created(self, event: ExternalEvent) -> None:
        """Record that a goal was created (for daily limit and cooldown)."""
        today = datetime.now().date().isoformat()
        self._daily_count[today] = self._daily_count.get(today, 0) + 1
        
        if event.external_ref:
            self._cooldowns[event.external_ref] = datetime.now()


# Usage in EventProcessor
class EventProcessor:
    def __init__(self, ...):
        ...
        self._rate_limiter = RateLimiter(self.goal_policy)
    
    async def process_event(self, event: ExternalEvent) -> Goal | None:
        # Check rate limits
        allowed, reason = self._rate_limiter.allow(event)
        if not allowed:
            logger.warning(f"Event rate limited: {event.id} — {reason}")
            return None
        
        # ... process event ...
        
        if goal:
            self._rate_limiter.record_goal_created(event)
        
        return goal
```

**Rate limit configuration defaults**:

| Limit | Default | Purpose |
|-------|---------|---------|
| `max_events_per_hour` | 50 | Prevent event flood per source |
| `max_goals_per_day` | 20 | Bound daily autonomous work |
| `cooldown_minutes` | 5 | Prevent duplicate goal spam |

---

## Risks and Mitigations

### Risk 1: Event Flood

**Problem**: External service sends massive event burst (DDoS, misconfigured webhook).

**Mitigation**:
- Per-source rate limiting (50/hour default)
- Event queue with backpressure
- Circuit breaker pattern
- Configurable `max_events_per_hour`

### Risk 2: Malicious Events

**Problem**: Attacker sends fake webhooks to trigger unwanted goals.

**Mitigation**:
- Mandatory webhook signature verification
- IP allowlisting for webhook sources
- External goals never auto-approve by default
- Human review for all external-triggered work

### Risk 3: Sensitive Data in Events

**Problem**: Events may contain sensitive data (error messages, user data).

**Mitigation**:
- Events stored locally only
- Configurable data redaction
- Don't log raw payloads by default
- Clear event history on request

### Risk 4: Stale Events

**Problem**: Events processed hours/days after they occurred (queue backup).

**Mitigation**:
- Event TTL (discard events older than 1 hour)
- Priority queue (newer events first)
- Monitoring for queue depth

### Risk 5: External Service Dependency

**Problem**: Sunwell becomes dependent on external services being available.

**Mitigation**:
- Graceful degradation (continue with internal signals)
- Retry with exponential backoff
- Health checks for adapters
- Clear status reporting

### Risk 6: Webhook Server Crash

**Problem**: What happens to in-flight events if the webhook server crashes?

**Mitigation**: Write-ahead logging (WAL) for event durability.

```python
class EventProcessor:
    """Event processor with crash recovery."""
    
    def __init__(self, root: Path, ...):
        ...
        self._wal_path = root / ".sunwell" / "external" / "wal.jsonl"
        self._wal_path.parent.mkdir(parents=True, exist_ok=True)
    
    async def process_event(self, event: ExternalEvent) -> Goal | None:
        # 1. Write event to WAL BEFORE processing
        await self._wal_append(event, status="received")
        
        try:
            # 2. Process event
            goal = await self._do_process(event)
            
            # 3. Mark as processed in WAL
            await self._wal_append(event, status="processed", goal_id=goal.id if goal else None)
            
            return goal
        except Exception as e:
            # 4. Mark as failed in WAL
            await self._wal_append(event, status="failed", error=str(e))
            raise
    
    async def _wal_append(self, event: ExternalEvent, **metadata) -> None:
        """Append event to write-ahead log."""
        entry = {
            "timestamp": datetime.now(UTC).isoformat(),
            "event_id": event.id,
            "source": event.source.value,
            "event_type": event.event_type.value,
            **metadata,
        }
        async with aiofiles.open(self._wal_path, "a") as f:
            await f.write(json.dumps(entry) + "\n")
    
    async def recover_from_crash(self) -> list[ExternalEvent]:
        """Recover unprocessed events after crash.
        
        Called on startup to find events that were received but not processed.
        """
        if not self._wal_path.exists():
            return []
        
        # Read WAL and find unprocessed events
        events_status: dict[str, str] = {}  # event_id → last status
        
        async with aiofiles.open(self._wal_path) as f:
            async for line in f:
                entry = json.loads(line)
                events_status[entry["event_id"]] = entry.get("status", "unknown")
        
        # Find events that were received but not processed/failed
        unprocessed = [
            eid for eid, status in events_status.items()
            if status == "received"
        ]
        
        logger.info(f"Crash recovery: {len(unprocessed)} unprocessed events")
        return unprocessed  # Caller should re-fetch and reprocess
    
    async def compact_wal(self) -> None:
        """Compact WAL by removing processed/old entries.
        
        Called periodically (e.g., daily) to prevent unbounded growth.
        """
        if not self._wal_path.exists():
            return
        
        cutoff = datetime.now(UTC) - timedelta(days=7)
        kept_lines = []
        
        async with aiofiles.open(self._wal_path) as f:
            async for line in f:
                entry = json.loads(line)
                entry_time = datetime.fromisoformat(entry["timestamp"])
                
                # Keep recent entries or unprocessed ones
                if entry_time > cutoff or entry.get("status") == "received":
                    kept_lines.append(line)
        
        # Rewrite WAL with kept lines
        async with aiofiles.open(self._wal_path, "w") as f:
            for line in kept_lines:
                await f.write(line)
```

**Startup recovery flow**:

```python
# In CLI: sunwell external start

async def start_external_integration():
    processor = EventProcessor(root, ...)
    
    # 1. Check for crash recovery
    unprocessed = await processor.recover_from_crash()
    if unprocessed:
        logger.warning(f"Found {len(unprocessed)} unprocessed events from previous session")
        # Re-poll to get fresh event data (WAL only stores IDs)
        await processor.reprocess_events(unprocessed)
    
    # 2. Start normal operation
    await processor.start()
```

---

## Testing Strategy

### Unit Tests

```python
class TestGitHubAdapter:
    def test_normalizes_ci_failure(self):
        """CI failure webhook becomes correct event."""
        adapter = GitHubAdapter(token="fake")
        payload = {
            "action": "completed",
            "workflow_run": {
                "id": 12345,
                "name": "test",
                "conclusion": "failure",
                "head_branch": "main",
                "head_sha": "abc123",
                "html_url": "https://github.com/...",
                "updated_at": "2026-01-19T12:00:00Z",
            },
        }
        
        event = adapter.normalize_webhook("workflow_run", payload)
        
        assert event is not None
        assert event.event_type == EventType.CI_FAILURE
        assert event.data["workflow_name"] == "test"
        assert event.priority_hint == 0.95
    
    def test_verifies_webhook_signature(self):
        """Webhook signature verification works."""
        adapter = GitHubAdapter(
            token="fake",
            webhook_secret="secret123",
        )
        
        payload = b'{"action": "completed"}'
        valid_sig = "sha256=" + hmac.new(
            b"secret123", payload, hashlib.sha256
        ).hexdigest()
        
        assert asyncio.run(adapter.verify_webhook(payload, valid_sig))
        assert not asyncio.run(adapter.verify_webhook(payload, "sha256=wrong"))


class TestEventProcessor:
    async def test_creates_goal_from_ci_failure(self, mock_backlog):
        """CI failure event becomes a goal."""
        processor = EventProcessor(
            backlog_manager=mock_backlog,
            goal_policy=ExternalGoalPolicy(),
        )
        
        event = ExternalEvent(
            id="test-1",
            source=EventSource.GITHUB,
            event_type=EventType.CI_FAILURE,
            timestamp=datetime.now(UTC),
            data={"workflow_name": "test", "run_id": 123},
        )
        
        goal = await processor.process_event(event)
        
        assert goal is not None
        assert "CI failure" in goal.title
        assert goal.category == "fix"
        mock_backlog.add_external_goal.assert_called_once()
    
    async def test_filters_by_policy(self, mock_backlog):
        """Events filtered by policy don't create goals."""
        processor = EventProcessor(
            backlog_manager=mock_backlog,
            goal_policy=ExternalGoalPolicy(
                enabled_event_types=frozenset({EventType.CI_FAILURE}),
            ),
        )
        
        event = ExternalEvent(
            id="test-1",
            source=EventSource.GITHUB,
            event_type=EventType.PUSH,  # Not enabled
            timestamp=datetime.now(UTC),
            data={},
        )
        
        goal = await processor.process_event(event)
        
        assert goal is None
        mock_backlog.add_external_goal.assert_not_called()
    
    async def test_deduplicates_events(self, mock_backlog):
        """Duplicate external refs don't create multiple goals."""
        processor = EventProcessor(
            backlog_manager=mock_backlog,
            goal_policy=ExternalGoalPolicy(),
        )
        mock_backlog.get_goals_by_external_ref.return_value = [Goal(...)]
        
        event = ExternalEvent(
            id="test-1",
            source=EventSource.GITHUB,
            event_type=EventType.CI_FAILURE,
            timestamp=datetime.now(UTC),
            data={},
            external_ref="github:workflow_run:123",
        )
        
        goal = await processor.process_event(event)
        
        assert goal is None  # Duplicate
```

### Integration Tests

```python
class TestExternalIntegration:
    async def test_webhook_to_goal_pipeline(self, test_server):
        """Full pipeline: webhook → event → goal → backlog."""
        # Send webhook
        response = await test_server.post(
            "/webhook/github",
            json={
                "action": "completed",
                "workflow_run": {"conclusion": "failure", ...},
            },
            headers={"X-Hub-Signature-256": "sha256=..."},
        )
        assert response.status_code == 200
        
        # Check goal created
        backlog = await test_server.app.state.backlog_manager.get_backlog()
        assert any("CI failure" in g.title for g in backlog.goals.values())
    
    async def test_feedback_posted_to_github(self, mock_github_api):
        """Completion feedback is posted back to GitHub."""
        # Process event
        # Execute goal
        # Check GitHub API was called with comment
        ...
```

---

## Implementation Plan

### Phase 1: Core Event System (Week 1)

- [ ] `ExternalEvent`, `EventType`, `EventSource` types → `src/sunwell/external/types.py`
- [ ] `EventAdapter` protocol → `src/sunwell/external/adapters/base.py`
- [ ] `EventProcessor` with goal translation → `src/sunwell/external/processor.py`
- [ ] `ExternalGoalPolicy` configuration → `src/sunwell/external/policy.py`
- [ ] `RateLimiter` with sliding window → `src/sunwell/external/ratelimit.py`
- [ ] `ExternalEventStore` (WAL + persistence) → `src/sunwell/external/store.py`
- [ ] Unit tests for event types

### Phase 2: Goal Integration (Week 2)

- [ ] Add `external_ref` field to `Goal` dataclass
- [ ] Add `add_external_goal()` to `BacklogManager`
- [ ] Add `get_goals_by_external_ref()` to `BacklogManager`
- [ ] Update backlog persistence (schema v2)
- [ ] Backlog file locking for process safety
- [ ] Integration tests for goal creation

### Phase 3: GitHub Adapter (Week 3)

- [ ] `GitHubAdapter` with polling support → `src/sunwell/external/adapters/github.py`
- [ ] Webhook normalization for CI, Issues, PRs
- [ ] Webhook signature verification (HMAC-SHA256)
- [ ] Feedback posting (commit comments, issue comments)
- [ ] CLI: `sunwell external poll github`

### Phase 4: Webhook Server (Week 4)

- [ ] FastAPI webhook server → `src/sunwell/external/server.py`
- [ ] Endpoint routing with signature verification
- [ ] IP allowlisting middleware
- [ ] Health checks endpoint
- [ ] Write-ahead logging for crash recovery
- [ ] CLI: `sunwell external start`

### Phase 5: Additional Adapters (Week 5)

- [ ] `LinearAdapter` (issue tracking) → `src/sunwell/external/adapters/linear.py`
- [ ] `SentryAdapter` (error monitoring) → `src/sunwell/external/adapters/sentry.py`
- [ ] `GitLabAdapter` (CI/issues) → `src/sunwell/external/adapters/gitlab.py`
- [ ] Adapter tests

### Phase 6: Scheduling & Guardrails (Week 6)

- [ ] `ExternalScheduler` with APScheduler → `src/sunwell/external/scheduler.py`
- [ ] Cron job configuration
- [ ] Default schedules (nightly, weekly)
- [ ] Add `can_auto_approve_external()` to `GuardrailSystem`
- [ ] Add `ExternalContext` for RFC-042 integration
- [ ] CLI: `sunwell external schedules`

### Phase 7: Integration & Polish (Week 7)

- [ ] Configuration file support (`sunwell.yaml`)
- [ ] WAL compaction scheduled job
- [ ] End-to-end tests (webhook → goal → execution → feedback)
- [ ] Documentation
- [ ] Performance benchmarks (event throughput)

---

## Success Criteria

| Metric | Target | Measurement |
|--------|--------|-------------|
| Event latency (webhook) | < 5s | Time from webhook to goal created |
| Event latency (polling) | < 2 min | Time from external event to goal created |
| Goal accuracy | > 90% | External events produce relevant goals |
| Feedback delivery | > 99% | Acknowledgments posted to source |
| False positive rate | < 10% | Irrelevant events filtered by policy |
| Uptime (server mode) | > 99.9% | Webhook server availability |

---

## Open Questions Resolved

This section documents design decisions for questions raised during RFC review.

### Q1: Should ExternalEvent be stored in Goal?

**Decision**: No. Store `external_ref: str | None` on Goal, store full `ExternalEvent` separately.

**Rationale**:
- Goal is `frozen=True` and serializes to JSON
- ExternalEvent contains `raw_payload` which may be large/sensitive
- Deduplication only needs the ref string
- Separate store allows independent retention policies

### Q2: How does webhook server coexist with CLI?

**Decision**: Separate processes with shared file-based backlog.

**Rationale**:
- Webhook server must stay running continuously
- CLI is interactive and on-demand
- File locking provides process safety
- Simpler than threading/IPC

### Q3: What happens to in-flight events if server crashes?

**Decision**: Write-ahead log (WAL) for event durability.

**Rationale**:
- WAL records "received" status before processing
- On startup, recover unprocessed events from WAL
- Periodic compaction prevents unbounded growth
- Simple file-based, no external dependencies

### Q4: How to integrate with AdaptiveSignals without breaking changes?

**Decision**: Composition via `ExternalContext` wrapper.

**Rationale**:
- AdaptiveSignals is stable across many modules
- External context is optional (most goals don't have it)
- Wrapper pattern avoids modifying core dataclass
- Can extend context without touching AdaptiveSignals

---

## Future Work

1. **Slack/Discord integration** — Chat-based event triggers
2. **Custom webhook format** — Support for arbitrary webhooks
3. **GraphQL subscriptions** — Real-time for services that support it
4. **Multi-repo support** — Monitor multiple repositories
5. **Event replay** — Re-process historical events
6. **Metrics dashboard** — External event analytics
7. **Smart deduplication** — ML-based duplicate detection

---

## Summary

External Integration connects Sunwell to the outside world through:

| Component | Purpose | Implementation |
|-----------|---------|----------------|
| **Event Adapters** | Normalize events from different sources | GitHub, GitLab, Linear, Sentry |
| **Webhook Server** | Receive real-time events | FastAPI with signature verification |
| **Event Processor** | Translate events to goals | Policy-based filtering, deduplication |
| **Scheduler** | Trigger scheduled events | Cron-based (nightly, weekly) |
| **Feedback System** | Report status back to source | Comments, status updates |

### The Complete Loop

```
External Event → Adapter → Processor → Goal → Backlog → Guardrails → Agent → Code
      ↑                                                                        │
      └────────────────────── Feedback ────────────────────────────────────────┘
```

### Integration Points

- **RFC-046**: External events become goals in the autonomous backlog
- **RFC-048**: External goals respect guardrails (never auto-approve by default)
- **RFC-042**: CI context informs adaptive technique selection

**The result**: Sunwell monitors your CI, reads your issues, and gets to work — even when you're not there.

---

## References

### RFCs

- RFC-042: Adaptive Agent — `src/sunwell/adaptive/`
- RFC-046: Autonomous Backlog — `src/sunwell/backlog/`
- RFC-048: Autonomy Guardrails — `src/sunwell/guardrails/`

### Implementation Files (to be created)

```
src/sunwell/external/
├── __init__.py
├── types.py           # ExternalEvent, EventType, EventSource, EventFeedback
├── adapters/
│   ├── __init__.py
│   ├── base.py        # EventAdapter protocol
│   ├── github.py      # GitHubAdapter
│   ├── gitlab.py      # GitLabAdapter
│   ├── linear.py      # LinearAdapter
│   └── sentry.py      # SentryAdapter
├── processor.py       # EventProcessor (event → goal translation)
├── policy.py          # ExternalGoalPolicy (filtering, rate limits)
├── ratelimit.py       # RateLimiter (sliding window, per-source buckets)
├── store.py           # ExternalEventStore (WAL + persistence)
├── context.py         # ExternalContext (RFC-042 integration)
├── server.py          # WebhookServer (FastAPI + signature verification)
├── scheduler.py       # ExternalScheduler (APScheduler integration)
└── config.py          # Configuration loading from sunwell.yaml
```

### Modified Files

```
src/sunwell/backlog/goals.py      # Add external_ref field to Goal
src/sunwell/backlog/manager.py    # Add add_external_goal(), get_goals_by_external_ref()
src/sunwell/guardrails/system.py  # Add can_auto_approve_external()
src/sunwell/guardrails/config.py  # Add trusted_external_sources, external_policy
src/sunwell/cli/main.py           # Add 'external' command group
```

### External Documentation

- [GitHub Webhooks](https://docs.github.com/en/webhooks)
- [GitLab Webhooks](https://docs.gitlab.com/ee/user/project/integrations/webhooks.html)
- [Linear Webhooks](https://developers.linear.app/docs/webhooks)
- [Sentry Webhooks](https://docs.sentry.io/product/integrations/integration-platform/webhooks/)

---

## Changelog

### Revision 2 (2026-01-19)

**Added**:
- Backwards Compatibility section with migration strategy
- Goal dataclass uses `external_ref: str` instead of embedding `ExternalEvent`
- `ExternalEventStore` for full event persistence (separate from backlog)
- `ExternalContext` for RFC-042 integration (composition over modification)
- Rate limiter implementation with sliding window and per-source buckets
- Webhook verification sequence diagram
- Crash recovery via write-ahead log (WAL)
- Process architecture diagram (webhook server + CLI coexistence)
- Dependency version constraints table
- Open Questions Resolved section
- Modified Files list in implementation plan
- File locking for process-safe backlog access

**Changed**:
- Implementation plan expanded from 6 to 7 phases
- Phase 2 now dedicated to Goal integration (previously mixed)
- Implementation files list updated with new components

---

*Last updated: 2026-01-19 (Revision 2)*

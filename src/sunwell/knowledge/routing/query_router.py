"""Query router for multi-project workspaces.

Determines which projects a query relates to before performing retrieval.
Uses:
1. Explicit project mentions ("in frontend", "the API")
2. L1 signature index for semantic routing
3. Project role hints for common patterns

This avoids loading all project indexes for every query.
"""

import re
from dataclasses import dataclass, field

from sunwell.knowledge.workspace.types import (
    ProjectRole,
    Workspace,
    WorkspaceProject,
)

__all__ = [
    "QueryRouter",
    "RouteResult",
    "route_query",
]


@dataclass(frozen=True, slots=True)
class RouteResult:
    """Result of query routing.

    Indicates which projects should be searched and why.
    """

    projects: tuple[WorkspaceProject, ...]
    """Projects to search, in priority order."""

    reason: str
    """Why these projects were selected."""

    confidence: float
    """Routing confidence (0.0-1.0)."""

    include_dependencies: bool = False
    """Whether shared dependencies should also be included."""


@dataclass(slots=True)
class QueryRouter:
    """Routes queries to relevant projects in a workspace.

    Uses multiple signals to determine which projects a query relates to:
    1. Explicit mentions: "in frontend", "the API", project names
    2. Role-based keywords: "UI", "database", "auth" → infer project role
    3. L1 signature index: semantic search over public APIs
    4. Workspace dependencies: include shared dependencies

    Example:
        >>> router = QueryRouter(workspace)
        >>> result = await router.route("how does user authentication work?")
        >>> result.projects  # [backend, shared]
        >>> result.reason    # "keyword 'authentication' suggests backend"
    """

    workspace: Workspace
    """The workspace to route within."""

    # L1 signature index for semantic routing (optional, lazy loaded)
    _signature_index: object | None = field(default=None, init=False)

    # Role keywords mapping
    _role_keywords: dict[ProjectRole, tuple[str, ...]] = field(init=False)

    def __post_init__(self) -> None:
        """Initialize role keywords."""
        self._role_keywords = {
            ProjectRole.FRONTEND: (
                "ui", "frontend", "component", "react", "vue", "svelte",
                "css", "style", "button", "form", "page", "layout", "view",
            ),
            ProjectRole.BACKEND: (
                "api", "backend", "server", "endpoint", "route", "handler",
                "database", "db", "query", "auth", "authentication", "session",
                "middleware", "controller", "service",
            ),
            ProjectRole.API: (
                "api", "rest", "graphql", "grpc", "endpoint", "schema",
                "request", "response", "client", "openapi", "swagger",
            ),
            ProjectRole.SHARED: (
                "shared", "common", "util", "utility", "helper", "types",
                "interface", "model", "constant", "config",
            ),
            ProjectRole.INFRA: (
                "deploy", "docker", "kubernetes", "k8s", "terraform", "ci",
                "cd", "pipeline", "infra", "infrastructure", "devops",
            ),
            ProjectRole.DOCS: (
                "docs", "documentation", "readme", "guide", "tutorial",
            ),
            ProjectRole.CLI: (
                "cli", "command", "terminal", "shell", "argparse", "click",
            ),
            ProjectRole.LIBRARY: (
                "library", "lib", "package", "module", "sdk",
            ),
        }

    async def route(self, query: str) -> RouteResult:
        """Route a query to relevant projects.

        Args:
            query: The user's query.

        Returns:
            RouteResult indicating which projects to search.
        """
        # Empty workspace
        if not self.workspace.projects:
            return RouteResult(
                projects=(),
                reason="workspace has no projects",
                confidence=1.0,
            )

        # Single project workspace - always search it
        if len(self.workspace.projects) == 1:
            return RouteResult(
                projects=self.workspace.projects,
                reason="single project workspace",
                confidence=1.0,
            )

        # 1. Check for explicit project mentions
        mentioned = self._extract_project_mentions(query)
        if mentioned:
            return RouteResult(
                projects=tuple(mentioned),
                reason=f"explicit mention: {', '.join(p.id for p in mentioned)}",
                confidence=0.95,
                include_dependencies=len(mentioned) > 1,
            )

        # 2. Check for role-based keywords
        role_matches = self._match_role_keywords(query)
        if role_matches:
            matched_projects = self._get_projects_by_roles(role_matches)
            if matched_projects:
                return RouteResult(
                    projects=tuple(matched_projects),
                    reason=f"keyword suggests: {', '.join(r.value for r in role_matches)}",
                    confidence=0.8,
                    include_dependencies=True,
                )

        # 3. Try L1 signature index (if available)
        # signature_matches = await self._search_signatures(query)
        # if signature_matches:
        #     return RouteResult(
        #         projects=tuple(signature_matches),
        #         reason="signature index match",
        #         confidence=0.7,
        #         include_dependencies=True,
        #     )

        # 4. Fallback: search all projects (with primary first)
        return self._fallback_all_projects()

    def _extract_project_mentions(self, query: str) -> list[WorkspaceProject]:
        """Extract explicitly mentioned projects from query.

        Detects patterns like:
        - "in the frontend"
        - "the backend API"
        - "myapp-frontend project"
        - Project IDs mentioned directly
        """
        query_lower = query.lower()
        mentioned: list[WorkspaceProject] = []

        for project in self.workspace.projects:
            # Check for project ID mention
            if project.id.lower() in query_lower:
                mentioned.append(project)
                continue

            # Check for role mention (e.g., "in the frontend")
            role_name = project.role.value.lower()
            patterns = [
                rf"\b{role_name}\b",
                rf"\bthe\s+{role_name}\b",
                rf"\bin\s+{role_name}\b",
            ]
            for pattern in patterns:
                if re.search(pattern, query_lower):
                    mentioned.append(project)
                    break

        return mentioned

    def _match_role_keywords(self, query: str) -> list[ProjectRole]:
        """Match query against role keywords."""
        query_lower = query.lower()
        words = set(re.findall(r"\w+", query_lower))

        matched_roles: list[tuple[ProjectRole, int]] = []

        for role, keywords in self._role_keywords.items():
            # Count keyword matches
            matches = sum(1 for kw in keywords if kw in words)
            if matches > 0:
                matched_roles.append((role, matches))

        # Sort by match count, take top roles
        matched_roles.sort(key=lambda x: x[1], reverse=True)

        # Return roles with at least 1 match, up to 2 roles
        return [role for role, _ in matched_roles[:2] if _ > 0]

    def _get_projects_by_roles(self, roles: list[ProjectRole]) -> list[WorkspaceProject]:
        """Get projects matching the given roles."""
        projects: list[WorkspaceProject] = []

        for role in roles:
            role_projects = self.workspace.get_projects_by_role(role)
            projects.extend(p for p in role_projects if p not in projects)

        return projects

    def _fallback_all_projects(self) -> RouteResult:
        """Fallback: search all projects with primary first."""
        # Order: primary first, then by role priority
        projects: list[WorkspaceProject] = []

        # Primary project first
        primary = self.workspace.primary_project
        if primary:
            projects.append(primary)

        # Then other projects
        for project in self.workspace.projects:
            if project not in projects:
                projects.append(project)

        return RouteResult(
            projects=tuple(projects),
            reason="no specific project identified, searching all",
            confidence=0.5,
            include_dependencies=False,
        )

    def expand_with_dependencies(self, result: RouteResult) -> RouteResult:
        """Expand route result to include shared dependencies.

        Args:
            result: Initial route result.

        Returns:
            Expanded result including dependencies.
        """
        if not result.include_dependencies:
            return result

        project_ids = [p.id for p in result.projects]
        shared_deps = self.workspace.dependencies.get_shared_dependencies(project_ids)

        if not shared_deps:
            return result

        # Add dependency projects
        expanded: list[WorkspaceProject] = list(result.projects)
        for dep_id in shared_deps:
            dep_project = self.workspace.get_project(dep_id)
            if dep_project and dep_project not in expanded:
                expanded.append(dep_project)

        return RouteResult(
            projects=tuple(expanded),
            reason=f"{result.reason} + dependencies",
            confidence=result.confidence,
            include_dependencies=False,  # Already expanded
        )


async def route_query(query: str, workspace: Workspace) -> RouteResult:
    """Route a query to relevant projects.

    Convenience function for one-off routing.

    Args:
        query: The user's query.
        workspace: Workspace to route within.

    Returns:
        RouteResult indicating which projects to search.
    """
    router = QueryRouter(workspace)
    result = await router.route(query)

    if result.include_dependencies:
        result = router.expand_with_dependencies(result)

    return result

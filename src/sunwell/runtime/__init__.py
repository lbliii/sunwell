"""Runtime utilities.

RFC-110: Most runtime functionality moved to Agent.
Remaining components:
- model_router: Model selection and routing
- parallel: Parallel execution utilities
- episode: Execution episode management
- handoff: Model handoff handling
"""

# Minimal exports - most functionality now in Agent
__all__: list[str] = []

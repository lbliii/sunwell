"""Backlog event schemas."""

from typing import TypedDict


class BacklogGoalAddedData(TypedDict, total=False):
    """Data for backlog_goal_added event."""
    goal_id: str  # Required
    title: str  # Required


class BacklogGoalStartedData(TypedDict, total=False):
    """Data for backlog_goal_started event."""
    goal_id: str  # Required


class BacklogGoalCompletedData(TypedDict, total=False):
    """Data for backlog_goal_completed event."""
    goal_id: str  # Required


class BacklogGoalFailedData(TypedDict, total=False):
    """Data for backlog_goal_failed event."""
    goal_id: str  # Required
    error: str  # Required


class BacklogRefreshedData(TypedDict, total=False):
    """Data for backlog_refreshed event."""
    goal_count: int  # Required

"""E2E Behavioral Testing Framework for Sunwell.

Tests AI agent behavior through observable outcomes rather than exact text matching.
Supports single-turn and multi-turn journeys with behavioral assertions.

Key concepts:
- Journeys: Test scenarios (single-turn or multi-turn conversations)
- Expectations: What behaviors to check (intent, signals, tools, state, output)
- Assertions: Behavioral checks that allow ranges and patterns
- EventRecorder: Captures all agent events for assertion

Example:
    >>> from sunwell.benchmark.journeys import JourneyRunner, load_journey
    >>> journey = load_journey("benchmark/journeys/single-turn/create-app.yaml")
    >>> runner = JourneyRunner()
    >>> result = await runner.run(journey)
    >>> assert result.passed
"""

from sunwell.benchmark.journeys.assertions import BehavioralAssertions
from sunwell.benchmark.journeys.recorder import EventRecorder
from sunwell.benchmark.journeys.runner import JourneyResult, JourneyRunner
from sunwell.benchmark.journeys.types import (
    Expectation,
    FileExpectation,
    Journey,
    JourneyType,
    MultiTurnJourney,
    Setup,
    SignalExpectation,
    SingleTurnJourney,
    ToolExpectation,
    Turn,
    load_journey,
    load_journeys_from_directory,
)

__all__ = [
    # Types
    "Journey",
    "JourneyType",
    "SingleTurnJourney",
    "MultiTurnJourney",
    "Turn",
    "Setup",
    "Expectation",
    "SignalExpectation",
    "ToolExpectation",
    "FileExpectation",
    # Runner
    "JourneyRunner",
    "JourneyResult",
    # Recorder
    "EventRecorder",
    # Assertions
    "BehavioralAssertions",
    # Loaders
    "load_journey",
    "load_journeys_from_directory",
]

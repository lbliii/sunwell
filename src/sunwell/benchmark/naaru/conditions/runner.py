"""Condition runner that routes to appropriate condition implementations."""

from dataclasses import dataclass
from typing import TYPE_CHECKING

from sunwell.benchmark.naaru.conditions.baseline import run_baseline, run_baseline_lens
from sunwell.benchmark.naaru.conditions.harmonic import run_harmonic, run_harmonic_divergent, run_harmonic_lens
from sunwell.benchmark.naaru.conditions.naaru_full import run_naaru_full, run_naaru_full_lens
from sunwell.benchmark.naaru.conditions.resonance import run_resonance
from sunwell.benchmark.naaru.conditions.rotation_conditions import run_rotation, run_rotation_lens
from sunwell.benchmark.naaru.types import NaaruCondition, NaaruConditionOutput

if TYPE_CHECKING:
    from sunwell.benchmark.types import BenchmarkTask
    from sunwell.foundation.core.lens import Lens
    from sunwell.models.protocol import ModelProtocol


@dataclass
class ConditionRunner:
    """Runs conditions for the Naaru benchmark.

    Example:
        >>> runner = ConditionRunner(model=model, judge_model=judge)
        >>> output = await runner.run(NaaruCondition.HARMONIC, task)
    """

    model: ModelProtocol
    judge_model: ModelProtocol
    max_resonance_attempts: int = 2

    async def run(
        self,
        condition: NaaruCondition,
        task: BenchmarkTask,
        lens: Lens | None = None,
    ) -> NaaruConditionOutput:
        """Run a specific condition on a task."""
        match condition:
            case NaaruCondition.BASELINE:
                return await run_baseline(self.model, task)

            case NaaruCondition.BASELINE_LENS:
                if lens is None:
                    raise ValueError("BASELINE_LENS requires a lens")
                return await run_baseline_lens(self.model, task, lens)

            case NaaruCondition.HARMONIC:
                return await run_harmonic(self.model, task)

            case NaaruCondition.HARMONIC_LENS:
                if lens is None:
                    raise ValueError("HARMONIC_LENS requires a lens")
                return await run_harmonic_lens(self.model, task, lens)

            case NaaruCondition.RESONANCE:
                return await run_resonance(
                    self.model, self.judge_model, task, self.max_resonance_attempts
                )

            case NaaruCondition.NAARU_FULL:
                return await run_naaru_full(
                    self.model, self.judge_model, task, self.max_resonance_attempts
                )

            case NaaruCondition.NAARU_FULL_LENS:
                if lens is None:
                    raise ValueError("NAARU_FULL_LENS requires a lens")
                return await run_naaru_full_lens(
                    self.model, self.judge_model, task, lens, self.max_resonance_attempts
                )

            case NaaruCondition.ROTATION:
                return await run_rotation(self.model, task, divergent=False)

            case NaaruCondition.ROTATION_LENS:
                if lens is None:
                    raise ValueError("ROTATION_LENS requires a lens")
                return await run_rotation_lens(self.model, task, lens, divergent=False)

            case NaaruCondition.HARMONIC_DIVERGENT:
                return await run_harmonic_divergent(self.model, task)

            case NaaruCondition.ROTATION_DIVERGENT:
                return await run_rotation(self.model, task, divergent=True)

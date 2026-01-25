"""Validation worker - tiered validation with FunctionGemma → Full LLM cascade."""


import asyncio
import json
import re
from collections import deque

from sunwell.naaru.core.bus import MessageType, NaaruRegion
from sunwell.naaru.core.worker import RegionWorker
from sunwell.types.config import NaaruConfig


class ValidationWorker(RegionWorker):
    """Validation region with Tiered Validation.

    Tiered Validation:
    1. Structural checks (no LLM) - catch syntax errors, missing imports
    2. FunctionGemma (270M) - fast approve/reject for clear cases
    3. Full LLM judge - only for borderline/uncertain cases
    """

    def __init__(
        self,
        *args,
        model=None,
        config: NaaruConfig | None = None,
        resonance=None,
        **kwargs,
    ):
        super().__init__(NaaruRegion.VALIDATION, *args, **kwargs)
        self.model = model
        self.config = config or NaaruConfig()
        self.resonance = resonance
        self.approved_count = 0
        self.rejected_count = 0
        self.refined_count = 0
        # Bounded deque to prevent memory leak (keeps last 10000 scores)
        self.quality_scores: deque[float] = deque(maxlen=10000)
        self.lightweight_decisions = 0
        self.escalated_to_llm = 0

        self._discernment = None
        if self.config.discernment:
            try:
                from sunwell.naaru.discernment import Discernment
                self._discernment = Discernment()
            except ImportError:
                pass

    async def process(self) -> None:
        """Validate proposals using tiered validation."""
        while not self._stop_event.is_set():
            msg = await self.bus.receive(self.region)

            if msg and msg.type == MessageType.VALIDATE_REQUEST:
                proposal = msg.payload.get("proposal", {})

                if self._discernment:
                    is_valid, reason, score, issues = await self._validate_tiered(proposal)
                elif self.model:
                    is_valid, reason, score, issues = await self._validate_with_llm(proposal)
                    self.quality_scores.append(score)
                else:
                    is_valid, reason = self._validate_basic(proposal)
                    score = 10.0 if is_valid else 0.0
                    issues = []

                current_attempt = proposal.get("refinement_attempt", 0)

                if is_valid:
                    await self.send_message(
                        MessageType.VALIDATION_RESULT,
                        NaaruRegion.EXECUTIVE,
                        {
                            "proposal_id": proposal.get("proposal_id"),
                            "valid": True,
                            "reason": reason,
                            "quality_score": score,
                            "refinement_attempts": current_attempt,
                        },
                    )
                    self.approved_count += 1
                    if current_attempt > 0:
                        self.refined_count += 1

                elif current_attempt < self.config.resonance:
                    # Resonance: Send back for refinement
                    await self.send_message(
                        MessageType.REFINE_REQUEST,
                        NaaruRegion.SYNTHESIS,
                        {
                            "proposal_id": proposal.get("proposal_id"),
                            "original_code": proposal.get("diff", ""),
                            "feedback": reason,
                            "issues": issues,
                            "score": score,
                            "category": proposal.get("summary", {}).get("category", "code_quality"),
                            "attempt": current_attempt + 1,
                        },
                    )
                    self.stats["resonance_requests"] = self.stats.get("resonance_requests", 0) + 1

                else:
                    # Final rejection
                    await self.send_message(
                        MessageType.VALIDATION_RESULT,
                        NaaruRegion.EXECUTIVE,
                        {
                            "proposal_id": proposal.get("proposal_id"),
                            "valid": False,
                            "reason": f"Rejected after {current_attempt} refinement attempts: {reason}",
                            "quality_score": score,
                            "refinement_attempts": current_attempt,
                        },
                    )
                    self.rejected_count += 1

                self.stats["tasks_completed"] += 1

            elif msg and msg.type == MessageType.SHUTDOWN:
                break

            await asyncio.sleep(0.01)

    async def _validate_tiered(self, proposal: dict) -> tuple[bool, str, float, list[str]]:
        """Tiered validation: FunctionGemma first, escalate if uncertain."""
        from sunwell.naaru.discernment import DiscernmentVerdict

        result = await self._discernment.evaluate(proposal)

        if result.confident:
            self.lightweight_decisions += 1
            self.quality_scores.append(result.score)

            if result.verdict == DiscernmentVerdict.APPROVE:
                return True, result.reason, result.score, result.issues
            elif result.verdict in (DiscernmentVerdict.REJECT, DiscernmentVerdict.NEEDS_REFINEMENT):
                return False, result.reason, result.score, result.issues

        # Escalate to full LLM
        self.escalated_to_llm += 1

        if self.model:
            return await self._validate_with_llm(proposal)
        else:
            is_valid = result.score >= self.config.purity_threshold
            return is_valid, result.reason, result.score, result.issues

    async def _validate_with_llm(self, proposal: dict) -> tuple[bool, str, float, list[str]]:
        """Full LLM judge validation."""
        diff = proposal.get("diff", "")
        rationale = proposal.get("summary", {}).get("rationale", "")
        category = proposal.get("summary", {}).get("category", "code_quality")

        judge_prompt = f"""You are an expert code reviewer. Evaluate this code:

INTENT: {rationale}
CATEGORY: {category}

CODE:
```python
{diff[:2500]}
```

CRITERIA (score each):
1. CORRECTNESS (0-3): Does it work?
2. CODE QUALITY (0-3): Is it idiomatic?
3. SAFETY (0-2): Any vulnerabilities?
4. COMPLETENESS (0-2): Is it complete?

Score >= 6 = production-ready.

Respond with ONLY JSON:
{{"score": <0-10>, "issues": ["issue1", "issue2"], "verdict": "approve" or "reject"}}"""

        try:
            from sunwell.models.protocol import GenerateOptions

            result = await self.model.generate(
                judge_prompt,
                options=GenerateOptions(temperature=0.1, max_tokens=500),
            )

            response_text = result.content or ""

            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]

            json_match = re.search(r'\{.*\}', response_text, re.DOTALL)
            if json_match:
                judge_result = json.loads(json_match.group())
                score = float(judge_result.get("score", 0))
                issues = judge_result.get("issues", [])
                verdict = judge_result.get("verdict", "reject")

                is_valid = score >= self.config.purity_threshold and verdict == "approve"
                reason = f"Score: {score}/10" + (f" Issues: {', '.join(issues[:2])}" if issues else "")

                return is_valid, reason, score, issues
            else:
                return True, "Judge parse error - defaulting to approve", 7.0, []

        except Exception as e:
            is_valid, reason = self._validate_basic(proposal)
            return is_valid, f"LLM error ({e}) - basic validation: {reason}", 5.0, []

    def _validate_basic(self, proposal: dict) -> tuple[bool, str]:
        """Basic structural validation (fallback)."""
        if "error" in proposal:
            return False, proposal["error"]
        if not proposal.get("proposal_id"):
            return False, "No proposal ID"
        return True, "OK"

    def get_quality_stats(self) -> dict:
        """Get quality scoring statistics."""
        if not self.quality_scores:
            return {"avg_score": 0, "min_score": 0, "max_score": 0, "count": 0}

        return {
            "avg_score": sum(self.quality_scores) / len(self.quality_scores),
            "min_score": min(self.quality_scores),
            "max_score": max(self.quality_scores),
            "count": len(self.quality_scores),
        }

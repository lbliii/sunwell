"""Confidence Triangulator for Deep Verification (RFC-047).

Cross-check verification signals to compute final confidence.
"""


from sunwell.quality.verification.types import (
    BehavioralExecutionResult,
    DeepVerificationResult,
    GeneratedTest,
    PerspectiveResult,
    SemanticIssue,
    Specification,
)


class ConfidenceTriangulator:
    """Cross-check verification signals to compute final confidence.

    Triangulation strategy:
    1. Test pass rate: Hard evidence from execution (40% weight)
    2. Perspective consensus: Agreement across reviewers (30% weight)
    3. Average confidence: How confident are perspectives? (20% weight)
    4. Spec confidence: How good is our specification? (10% weight)
    """

    def triangulate(
        self,
        spec: Specification,
        execution_results: BehavioralExecutionResult | None,
        perspective_results: list[PerspectiveResult],
        generated_tests: list[GeneratedTest] | None = None,
    ) -> DeepVerificationResult:
        """Compute final verification result via triangulation.

        Args:
            spec: Extracted specification
            execution_results: Results from test execution
            perspective_results: Results from each verification perspective
            generated_tests: Optional list of generated tests

        Returns:
            Final DeepVerificationResult with confidence score
        """
        # Signal 1: Test execution (40% weight)
        if execution_results and execution_results.total_tests > 0:
            test_score = execution_results.pass_rate
            test_weight = 0.4
        else:
            test_score = 0.5  # Neutral if no tests
            test_weight = 0.1  # Reduce weight if no tests

        # Signal 2: Perspective consensus (30% weight)
        if perspective_results:
            verdicts = [p.verdict for p in perspective_results]
            correct_count = sum(1 for v in verdicts if v == "correct")
            incorrect_count = sum(1 for v in verdicts if v == "incorrect")

            # Score: 1.0 if all correct, 0.0 if all incorrect, linear in between
            perspective_score = correct_count / len(verdicts)

            # Extra penalty for any "incorrect" verdict
            if incorrect_count > 0:
                perspective_score *= 0.7

            perspective_weight = 0.3
        else:
            perspective_score = 0.5
            perspective_weight = 0.1

        # Signal 3: Average perspective confidence (20% weight)
        if perspective_results:
            avg_confidence = sum(p.confidence for p in perspective_results) / len(
                perspective_results
            )
            confidence_weight = 0.2
        else:
            avg_confidence = 0.5
            confidence_weight = 0.1

        # Signal 4: Spec confidence (10% weight)
        spec_score = spec.confidence
        spec_weight = 0.1

        # Normalize weights to sum to 1.0
        total_weight = test_weight + perspective_weight + confidence_weight + spec_weight
        if total_weight > 0:
            test_weight /= total_weight
            perspective_weight /= total_weight
            confidence_weight /= total_weight
            spec_weight /= total_weight

        # Weighted average
        raw_confidence = (
            test_score * test_weight
            + perspective_score * perspective_weight
            + avg_confidence * confidence_weight
            + spec_score * spec_weight
        )

        # Check for contradictions (reduces confidence)
        has_contradiction = self._detect_contradictions(
            perspective_results, execution_results
        )
        if has_contradiction:
            raw_confidence *= 0.8  # 20% penalty for contradictions

        # Collect all issues
        issues = self._collect_issues(perspective_results, execution_results)

        # Determine pass/fail
        has_critical_issues = any(i.severity == "critical" for i in issues)
        tests_pass_threshold = (
            execution_results is None
            or execution_results.total_tests == 0
            or execution_results.pass_rate >= 0.8
        )

        passed = (
            raw_confidence >= 0.7
            and not has_critical_issues
            and tests_pass_threshold
        )

        # Collect recommendations
        recommendations = self._collect_recommendations(perspective_results, issues)

        return DeepVerificationResult(
            passed=passed,
            confidence=raw_confidence,
            issues=tuple(issues),
            generated_tests=tuple(generated_tests) if generated_tests else (),
            test_results=execution_results,
            perspective_results=tuple(perspective_results),
            recommendations=tuple(recommendations),
            duration_ms=0,  # Filled by caller
        )

    def _detect_contradictions(
        self,
        perspectives: list[PerspectiveResult],
        execution: BehavioralExecutionResult | None,
    ) -> bool:
        """Detect contradicting signals.

        Contradictions indicate high uncertainty and reduce confidence.
        """
        # Contradiction: Tests pass but reviewers say incorrect
        if (
            execution
            and execution.pass_rate > 0.9
            and any(p.verdict == "incorrect" for p in perspectives)
        ):
            return True

        # Contradiction: Tests fail but reviewers say correct
        if (
            execution
            and execution.total_tests > 0
            and execution.pass_rate < 0.5
            and all(p.verdict == "correct" for p in perspectives)
        ):
            return True

        # Contradiction: Reviewers strongly disagree
        verdicts = [p.verdict for p in perspectives]
        return "correct" in verdicts and "incorrect" in verdicts

    def _collect_issues(
        self,
        perspectives: list[PerspectiveResult],
        execution: BehavioralExecutionResult | None,
    ) -> list[SemanticIssue]:
        """Collect all issues from all sources."""
        issues: list[SemanticIssue] = []

        # Issues from perspective analysis
        for perspective in perspectives:
            if perspective.verdict == "incorrect":
                severity = "critical"
            elif perspective.verdict == "suspicious":
                severity = "high"
            else:
                severity = "low"

            for issue_text in perspective.issues:
                # Categorize the issue
                category = self._categorize_issue(issue_text)

                issues.append(
                    SemanticIssue(
                        severity=severity if perspective.verdict != "correct" else "low",  # type: ignore
                        category=category,
                        description=issue_text,
                        evidence=f"From {perspective.perspective}",
                        suggested_fix=None,
                    )
                )

        # Issues from test failures
        if execution:
            for test_result in execution.test_results:
                if not test_result.passed and test_result.error_message:
                    issues.append(
                        SemanticIssue(
                            severity="high",
                            category="wrong_output",
                            description=f"Test {test_result.test_id} failed: {test_result.error_message}",
                            evidence=test_result.stderr or test_result.stdout or "",
                            suggested_fix=None,
                        )
                    )

        # Deduplicate similar issues
        seen: set[str] = set()
        unique_issues: list[SemanticIssue] = []
        for issue in issues:
            key = issue.description.lower()[:50]
            if key not in seen:
                seen.add(key)
                unique_issues.append(issue)

        return unique_issues

    def _categorize_issue(self, issue_text: str) -> str:
        """Categorize an issue based on its description."""
        text_lower = issue_text.lower()

        if any(kw in text_lower for kw in ["wrong", "incorrect", "returns", "output"]):
            return "wrong_output"
        elif any(kw in text_lower for kw in ["edge", "empty", "null", "none", "zero"]):
            return "missing_edge_case"
        elif any(kw in text_lower for kw in ["logic", "algorithm", "off-by", "boundary"]):
            return "logic_error"
        elif any(kw in text_lower for kw in ["contract", "spec", "should", "expected"]):
            return "contract_violation"
        elif any(kw in text_lower for kw in ["api", "dependency", "import", "call"]):
            return "integration_issue"
        elif any(kw in text_lower for kw in ["regress", "break", "change", "remove"]):
            return "regression"
        else:
            return "logic_error"  # Default

    def _collect_recommendations(
        self,
        perspectives: list[PerspectiveResult],
        issues: list[SemanticIssue],
    ) -> list[str]:
        """Collect and prioritize recommendations."""
        seen: set[str] = set()
        recommendations: list[str] = []

        # From perspectives
        for perspective in perspectives:
            for rec in perspective.recommendations:
                if rec not in seen:
                    seen.add(rec)
                    recommendations.append(rec)

        # From issues (suggested fixes)
        for issue in issues:
            if issue.suggested_fix and issue.suggested_fix not in seen:
                seen.add(issue.suggested_fix)
                recommendations.append(issue.suggested_fix)

        # Add generic recommendations based on issue categories
        categories = {i.category for i in issues}

        if "missing_edge_case" in categories:
            rec = "Add input validation for edge cases (empty, null, boundary values)"
            if rec not in recommendations:
                recommendations.append(rec)

        if "logic_error" in categories:
            rec = "Review algorithm logic and add more unit tests"
            if rec not in recommendations:
                recommendations.append(rec)

        if "integration_issue" in categories:
            rec = "Verify API usage against documentation"
            if rec not in recommendations:
                recommendations.append(rec)

        # Limit to top 5 recommendations
        return recommendations[:5]

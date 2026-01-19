"""Test: Thought Rotation / The Prism (RFC-028).

Tests the prism hypothesis: smaller models benefit more from structured
perspective rotation than larger models.

Usage:
    # Test with default model
    python examples/test_thought_rotation.py
    
    # Test with specific model
    python examples/test_thought_rotation.py --model llama3.2:1b
    
    # Test multiple models to see the prism effect
    python examples/test_thought_rotation.py --model tinyllama
    python examples/test_thought_rotation.py --model llama3.2:1b
    python examples/test_thought_rotation.py --model llama3.2:3b

The prism hypothesis: smaller models should show larger quality improvements
from thought rotation because they need the structure to access their latent
multi-perspective capabilities.
"""

import asyncio
import argparse
from dataclasses import dataclass


# The security review task (from benchmark/tasks/review/security-001.yaml)
TASK = """Review this code for security vulnerabilities:

```python
def login(request):
    username = request.POST.get('username')
    password = request.POST.get('password')
    
    query = f"SELECT * FROM users WHERE username='{username}' AND password='{password}'"
    user = db.execute(query).fetchone()
    
    if user:
        session['user_id'] = user['id']
        return redirect('/dashboard')
    return render('login.html', error="Invalid credentials")
```

Identify security issues and provide fixes.
"""

# Ground truth issues to check for
GROUND_TRUTH_ISSUES = [
    ("SQL injection", ["sql injection", "sql-injection", "sqli"]),
    ("Password handling", ["plain text", "plaintext", "hash", "bcrypt", "argon"]),
    ("Parameterized queries", ["parameterized", "prepared statement", "placeholder", "bind"]),
    ("CSRF", ["csrf", "cross-site request"]),
    ("Session fixation", ["session fixation", "regenerate session"]),
]


@dataclass
class TestResult:
    condition: str
    model: str
    output: str
    detected_issues: list[str]
    frame_usage: dict[str, int]
    word_count: int
    task_type: str = ""
    model_size: str = ""


def count_frames(text: str) -> dict[str, int]:
    """Count frame marker usage."""
    from sunwell.naaru.rotation import Frame
    
    counts = {}
    text_lower = text.lower()
    for frame in Frame:
        counts[frame.value] = text_lower.count(f"<{frame.value}>")
    return counts


def check_issues(text: str) -> list[str]:
    """Check which ground truth issues were detected."""
    text_lower = text.lower()
    detected = []
    
    for issue_name, keywords in GROUND_TRUTH_ISSUES:
        if any(kw in text_lower for kw in keywords):
            detected.append(issue_name)
    
    return detected


async def run_test(model_name: str) -> tuple[TestResult, TestResult]:
    """Run baseline and rotation conditions."""
    
    try:
        from sunwell.models.ollama import OllamaModel
        from sunwell.models.protocol import Message
        from sunwell.naaru.rotation import (
            ThoughtLexer,
            ModelSize,
            create_rotation_prompt,
        )
    except ImportError as e:
        print(f"Import error: {e}")
        print("Sunwell not installed. Using mock for demo.")
        return await run_mock_test(model_name)
    
    model = OllamaModel(model_name)
    
    # Infer model size
    model_size = ModelSize.from_model_name(model_name)
    
    print(f"\n{'='*60}")
    print(f"🔮 THE PRISM TEST")
    print(f"{'='*60}")
    print(f"Model: {model_name}")
    print(f"Inferred size: {model_size.value}")
    print(f"{'='*60}")
    
    # === BASELINE ===
    print("\n[1/3] Running BASELINE (no rotation)...")
    baseline_response = await model.generate(
        (Message(role="user", content=TASK),)
    )
    baseline_output = baseline_response.content
    
    # === ROTATION with ThoughtLexer ===
    print("[2/3] Analyzing task with ThoughtLexer...")
    
    # Use functiongemma or fall back to the test model for lexing
    try:
        lexer_model = OllamaModel("functiongemma")
    except Exception:
        lexer_model = model  # Fall back to same model
    
    lexer = ThoughtLexer(tiny_model=lexer_model, default_model_size=model_size)
    rotation_plan = await lexer.lex(TASK, model_size=model_size)
    
    print(f"    Task type: {rotation_plan.task_type}")
    print(f"    Frames: {[f.value for f in rotation_plan.frames]}")
    print(f"    Emphasized: {[f.value for f in rotation_plan.composition.get_emphasized_frames()]}")
    
    # Generate rotation prompt
    rotation_prompt = rotation_plan.to_system_prompt()
    
    print("[3/3] Running ROTATION (with frame markers)...")
    rotation_response = await model.generate(
        (
            Message(role="system", content=rotation_prompt),
            Message(role="user", content=TASK),
        )
    )
    rotation_output = rotation_response.content
    
    # Analyze results
    baseline_result = TestResult(
        condition="baseline",
        model=model_name,
        output=baseline_output,
        detected_issues=check_issues(baseline_output),
        frame_usage=count_frames(baseline_output),
        word_count=len(baseline_output.split()),
        model_size=model_size.value,
    )
    
    rotation_result = TestResult(
        condition="rotation",
        model=model_name,
        output=rotation_output,
        detected_issues=check_issues(rotation_output),
        frame_usage=count_frames(rotation_output),
        word_count=len(rotation_output.split()),
        task_type=rotation_plan.task_type,
        model_size=model_size.value,
    )
    
    return baseline_result, rotation_result


async def run_mock_test(model_name: str) -> tuple[TestResult, TestResult]:
    """Mock test for when Sunwell isn't installed."""
    print("\n[MOCK MODE] Simulating results...")
    
    baseline_result = TestResult(
        condition="baseline",
        model=model_name,
        output="[Mock baseline output - SQL injection found]",
        detected_issues=["SQL injection"],
        frame_usage={},
        word_count=150,
    )
    
    rotation_result = TestResult(
        condition="rotation", 
        model=model_name,
        output="<think>...</think><adversary>...</adversary><synthesize>SQL injection + password hashing</synthesize>",
        detected_issues=["SQL injection", "Password handling", "Parameterized queries"],
        frame_usage={"think": 1, "adversary": 1, "synthesize": 1},
        word_count=250,
    )
    
    return baseline_result, rotation_result


def print_results(baseline: TestResult, rotation: TestResult):
    """Print comparison results."""
    
    print(f"\n{'='*60}")
    print("📊 RESULTS COMPARISON")
    print(f"{'='*60}")
    
    if rotation.task_type:
        print(f"Task classified as: {rotation.task_type}")
    if rotation.model_size:
        print(f"Model size category: {rotation.model_size}")
    
    print(f"\n{'Metric':<25} {'Baseline':>15} {'Rotation':>15} {'Delta':>10}")
    print("-" * 65)
    
    # Issues detected
    b_issues = len(baseline.detected_issues)
    r_issues = len(rotation.detected_issues)
    delta = r_issues - b_issues
    delta_str = f"+{delta}" if delta > 0 else str(delta)
    print(f"{'Issues Detected':<25} {b_issues:>15} {r_issues:>15} {delta_str:>10}")
    
    # Word count
    print(f"{'Word Count':<25} {baseline.word_count:>15} {rotation.word_count:>15}")
    
    # Frame usage
    total_frames = sum(rotation.frame_usage.values())
    print(f"{'Frames Used':<25} {0:>15} {total_frames:>15}")
    
    print(f"\n{'='*60}")
    print("🔍 ISSUES DETECTED")
    print(f"{'='*60}")
    
    print(f"\nBaseline: {', '.join(baseline.detected_issues) or 'None'}")
    print(f"Rotation: {', '.join(rotation.detected_issues) or 'None'}")
    
    # Show which issues rotation found that baseline missed
    rotation_only = set(rotation.detected_issues) - set(baseline.detected_issues)
    baseline_only = set(baseline.detected_issues) - set(rotation.detected_issues)
    
    if rotation_only:
        print(f"\n✅ Rotation found (baseline missed): {', '.join(rotation_only)}")
    if baseline_only:
        print(f"\n⚠️ Baseline found (rotation missed): {', '.join(baseline_only)}")
    
    # Frame breakdown
    if any(rotation.frame_usage.values()):
        print(f"\n{'='*60}")
        print("🌈 FRAME USAGE (Wavelengths)")
        print(f"{'='*60}")
        for frame, count in rotation.frame_usage.items():
            if count > 0:
                bar = "█" * count
                print(f"  <{frame}>: {bar} ({count})")
        
        # Check for synthesis (Naaru emergence point)
        if rotation.frame_usage.get("synthesize", 0) > 0:
            print("\n  🌟 Synthesis frame used — Naaru emergence point!")
    
    # Output samples
    print(f"\n{'='*60}")
    print("📝 BASELINE OUTPUT (first 400 chars)")
    print(f"{'='*60}")
    print(baseline.output[:400] + ("..." if len(baseline.output) > 400 else ""))
    
    print(f"\n{'='*60}")
    print("📝 ROTATION OUTPUT (first 400 chars)")
    print(f"{'='*60}")
    print(rotation.output[:400] + ("..." if len(rotation.output) > 400 else ""))
    
    # Verdict
    print(f"\n{'='*60}")
    print("🎯 VERDICT")
    print(f"{'='*60}")
    
    if r_issues > b_issues:
        improvement = ((r_issues - b_issues) / max(b_issues, 1)) * 100
        print(f"✅ Rotation found {r_issues - b_issues} more issue(s) (+{improvement:.0f}%)")
        print(f"   The prism revealed latent capability!")
    elif r_issues < b_issues:
        print(f"⚠️ Baseline found {b_issues - r_issues} more issue(s)")
        print(f"   Rotation may need tuning for this model")
    else:
        print("➡️ Same issue count — compare explanation quality manually")
    
    # Prism theory check
    print(f"\n{'='*60}")
    print("🔮 PRISM THEORY CHECK")
    print(f"{'='*60}")
    
    size = rotation.model_size or "unknown"
    expected_gain = {
        "tiny": "30-50%",
        "small": "25-40%", 
        "medium": "15-25%",
        "large": "5-10%",
    }.get(size, "unknown")
    
    actual_gain = ((r_issues - b_issues) / max(b_issues, 1)) * 100 if b_issues > 0 else 0
    
    print(f"Model size: {size}")
    print(f"Expected gain (theory): {expected_gain}")
    print(f"Actual gain: {actual_gain:.0f}%")
    
    if size in ("tiny", "small") and actual_gain >= 25:
        print("\n✨ Strong prism effect confirmed!")
    elif size in ("medium", "large") and actual_gain <= 15:
        print("\n✨ Expected modest effect for larger model")
    elif actual_gain > 0:
        print("\n✨ Positive prism effect observed")


async def main():
    parser = argparse.ArgumentParser(
        description="Test thought rotation (the prism principle)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Test with tinyllama (should show strong prism effect)
    python examples/test_thought_rotation.py --model tinyllama
    
    # Test with 3B model (should show modest effect)
    python examples/test_thought_rotation.py --model llama3.2:3b
    
    # Compare multiple to see the effect scale with model size
    for m in tinyllama llama3.2:1b llama3.2:3b; do
        python examples/test_thought_rotation.py --model $m
    done
        """
    )
    parser.add_argument("--model", default="llama3.2:1b", help="Ollama model to test")
    args = parser.parse_args()
    
    baseline, rotation = await run_test(args.model)
    print_results(baseline, rotation)


if __name__ == "__main__":
    asyncio.run(main())

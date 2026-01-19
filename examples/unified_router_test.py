"""Quick test: Can one tiny model handle ALL routing tasks?

Tests whether a single qwen2.5:1.5b can replace:
- ModelRouter.stupid_model (tier classification)
- CognitiveRouter (intent + lens)
- Discernment (quick validation gate)
- Mirror sensing (user mood/expertise)
"""

import asyncio
import json
from sunwell.models.ollama import OllamaModel

UNIFIED_PROMPT = """You are a universal router. Analyze this user request and respond with JSON only.

User request: "{request}"

Respond with this exact JSON structure:
{{
  "intent": "code|explain|debug|chat|search",
  "complexity": "trivial|standard|complex",
  "lens": "coder|writer|reviewer|helper",
  "tools_needed": ["file_read", "file_write", "search", "terminal"] or [],
  "user_mood": "neutral|frustrated|curious|rushed",
  "confidence": 0.0-1.0
}}

JSON only, no explanation:"""


async def test_unified_router():
    """Test single model handling all routing tasks."""
    
    model = OllamaModel(model="qwen2.5:1.5b", use_native_api=False)
    
    test_cases = [
        "fix the bug in auth.py line 45",
        "what is dependency injection?",
        "THIS IS BROKEN AGAIN help me debug NOW",
        "hey how's it going",
        "refactor the entire authentication module to use OAuth2",
    ]
    
    print("=" * 60)
    print("UNIFIED ROUTER TEST - One Model, All Decisions")
    print("=" * 60)
    
    for request in test_cases:
        prompt = UNIFIED_PROMPT.format(request=request)
        
        try:
            result = await model.generate(prompt)
            content = result.content.strip()
            
            # Try to parse JSON
            try:
                # Handle markdown code blocks if present
                if "```" in content:
                    content = content.split("```")[1]
                    if content.startswith("json"):
                        content = content[4:]
                
                parsed = json.loads(content)
                
                print(f"\n📝 Request: {request[:50]}...")
                print(f"   Intent: {parsed.get('intent', '?')}")
                print(f"   Complexity: {parsed.get('complexity', '?')}")
                print(f"   Lens: {parsed.get('lens', '?')}")
                print(f"   Tools: {parsed.get('tools_needed', [])}")
                print(f"   Mood: {parsed.get('user_mood', '?')}")
                print(f"   Confidence: {parsed.get('confidence', '?')}")
                
            except json.JSONDecodeError:
                print(f"\n❌ Request: {request[:50]}...")
                print(f"   Failed to parse: {content[:100]}")
                
        except Exception as e:
            print(f"\n❌ Request: {request[:50]}...")
            print(f"   Error: {e}")
    
    print("\n" + "=" * 60)
    print("✓ Test complete")


if __name__ == "__main__":
    asyncio.run(test_unified_router())

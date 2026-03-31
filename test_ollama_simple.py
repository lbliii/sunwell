#!/usr/bin/env python
"""Simple test to verify Ollama model works."""

async def test_ollama():
    """Test that Ollama model can generate text."""
    from sunwell.interface.cli.helpers.models import create_model

    print("🧪 Testing Ollama Model\n")

    # Create Ollama model
    print("Creating model: ollama/gemma3:4b")
    model = create_model("ollama", "gemma3:4b")
    print("✅ Model created\n")

    # Test generation
    print("Testing generation...")
    messages = [
        {"role": "user", "content": "Say 'Hello from Ollama!' and nothing else."}
    ]

    response = await model.generate(messages)
    print(f"✅ Response: {response.content}\n")

    if "ollama" in response.content.lower() or "hello" in response.content.lower():
        print("✅ Ollama is working correctly!")
        return True
    else:
        print("⚠️  Got response but unexpected content")
        return False

if __name__ == "__main__":
    import asyncio
    try:
        asyncio.run(test_ollama())
    except Exception as e:
        print(f"❌ Error: {e}")
        import traceback
        traceback.print_exc()

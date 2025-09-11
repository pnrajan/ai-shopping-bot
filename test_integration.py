#!/usr/bin/env python3
"""Test script to verify Query Understanding integration."""

import os
import sys
from pathlib import Path

# Add the project root to sys.path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from inflection_curator import ShoppingOrchestrator


def test_qu_integration():
    """Test that Query Understanding is properly integrated."""
    print("🧪 Testing Query Understanding Integration")
    print("=" * 50)

    # Initialize orchestrator
    try:
        orch = ShoppingOrchestrator()
        print(f"✅ Orchestrator initialized")
        print(f"   Current persona: {orch.get_current_persona_info()['full_name']}")
        print(f"   Execution mode: {orch.execution_mode}")

        # Check if QU is initialized
        if hasattr(orch, "query_understander") and orch.query_understander:
            print(f"✅ Query Understanding component loaded")
        else:
            print(f"❌ Query Understanding component not initialized")
            return False

    except Exception as e:
        print(f"❌ Failed to initialize orchestrator: {e}")
        return False

    # Test queries
    test_queries = [
        "I need wireless headphones under $100",
        "Show me gaming laptops",
        "Find me a blue winter jacket in size medium",
    ]

    print(f"\n🧪 Testing Query Processing")
    print("-" * 30)

    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Testing: '{query}'")

        try:
            # Test QU directly first
            qu_result = orch.query_understander.analyze_query(query)
            if qu_result:
                print(
                    f"   🧠 QU Analysis: {qu_result.intent} (confidence: {qu_result.confidence:.2f})"
                )
                if qu_result.products:
                    print(f"   🛍️  Products: {qu_result.products}")
                if qu_result.category:
                    print(f"   📂 Category: {qu_result.category}")
            else:
                print(f"   ⚠️  QU Analysis failed - will use fallback")

            # Test full orchestrator flow
            result = orch.handle(query)

            if result.get("error"):
                print(f"   ❌ Orchestrator error: {result['error']}")
            else:
                qu_data = result.get("query_understanding")
                if qu_data:
                    print(f"   ✅ Full flow completed with QU data")
                else:
                    print(f"   ⚠️  Full flow completed without QU data (fallback used)")

        except Exception as e:
            print(f"   ❌ Error processing query: {e}")
            return False

    print(f"\n🎉 Integration test completed successfully!")
    return True


if __name__ == "__main__":
    # Check environment variables
    if not os.getenv("OPENAI_API_KEY"):
        print("⚠️  Warning: OPENAI_API_KEY not set - QU may not work properly")
        print("   Set your OpenAI API key: export OPENAI_API_KEY='your-key-here'")
        print()

    success = test_qu_integration()
    sys.exit(0 if success else 1)

#!/usr/bin/env python3
"""Main entry point for the Inflection Curator.

This module provides a command-line interface (CLI) for the shopping assistant,
as well as a demonstration of its capabilities.
"""

import json
import sys
from pathlib import Path

# Add the project root to sys.path for development
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

from inflection_curator import ShoppingOrchestrator, ShoppingMode


def cli() -> None:
    """Runs the command-line interface for the Inflection Curator."""
    print("🛍️  Inflection Curator - AI Personal Shopping Assistant")
    print("=" * 70)

    # Initialize the shopping orchestrator
    orch = ShoppingOrchestrator()

    print(f"\nAvailable Shopping Personas: {', '.join(orch.list_personas())}")
    print(f"Current Persona: {orch.get_current_persona_info()['full_name']}")
    print(f"Execution Mode: {orch.execution_mode}")

    print("\n" + "=" * 70)

    # Interactive mode
    print("\n🎯 Interactive Shopping Assistant")
    print("Type 'quit' to exit, 'help' for commands")
    print("-" * 50)

    while True:
        try:
            user_input = input("\n🛍️  What are you looking for? ").strip()

            if user_input.lower() in ["quit", "exit", "q"]:
                print("👋 Goodbye! Happy shopping!")
                break

            if user_input.lower() == "help":
                print("\nAvailable commands:")
                print("  help - Show this help message")
                print("  quit/exit/q - Exit the application")
                print(
                    "  set persona <name> - Change persona (default, budget_hunter, expert)"
                )
                print("  set mode <mode> - Change execution mode")
                print("  status - Show current configuration")
                continue

            if user_input.lower().startswith("set persona "):
                persona_name = user_input[12:].strip()
                try:
                    orch.set_persona(persona_name)
                    print(
                        f"✅ Switched to persona: {orch.get_current_persona_info()['full_name']}"
                    )
                except Exception as e:
                    print(f"❌ Error: {e}")
                continue

            if user_input.lower().startswith("set mode "):
                mode = user_input[9:].strip()
                try:
                    orch.set_mode(mode)
                    print(f"✅ Switched to mode: {orch.execution_mode}")
                except Exception as e:
                    print(f"❌ Error: {e}")
                continue

            if user_input.lower() == "status":
                info = orch.get_current_persona_info()
                print(f"\n📊 Current Configuration:")
                print(f"  Persona: {info['full_name']}")
                print(f"  Mode: {info['execution_mode']}")
                print(f"  Available Tools: {', '.join(info['available_tools'])}")
                continue

            if not user_input:
                print("Please enter a shopping request or command.")
                continue

            # Process shopping request
            print("\n🤔 Processing your request...")
            result = orch.handle(user_input)

            # Display results in a user-friendly format
            print("\n📋 Results:")
            if result.get("error"):
                print(f"❌ Error: {result['error']}")
            else:
                # Show Query Understanding insights
                qu_data = result.get("query_understanding")
                if qu_data:
                    print(f"🧠 Query Analysis:")
                    print(
                        f"   Intent: {qu_data.get('intent')} (confidence: {qu_data.get('confidence', 0):.2f})"
                    )
                    if qu_data.get("products"):
                        print(f"   Products: {', '.join(qu_data['products'])}")
                    if qu_data.get("category"):
                        print(f"   Category: {qu_data['category']}")
                    if qu_data.get("budget"):
                        budget = qu_data["budget"]
                        if budget.get("max"):
                            print(f"   Budget: Up to ${budget['max']}")

                execution = result.get("execution", {})
                if execution.get("clarify"):
                    print(f"❓ {execution['clarify']}")
                elif execution.get("output"):
                    output = execution["output"]
                    if isinstance(output, dict) and "message" in output:
                        print(f"💬 {output['message']}")
                    elif isinstance(output, dict) and "candidates" in output:
                        candidates = output["candidates"]
                        print(f"🛍️  Found {len(candidates)} products:")
                        for i, product in enumerate(candidates[:3], 1):
                            title = product.get("title", "Unknown product")
                            price = product.get("price", "N/A")
                            print(f"   {i}. {title} - ${price}")
                    else:
                        print(f"📦 {output}")
                else:
                    print("🤷 No specific results available.")

        except KeyboardInterrupt:
            print("\n\n👋 Goodbye! Happy shopping!")
            break
        except Exception as e:
            print(f"❌ Unexpected error: {e}")


def main() -> None:
    """Runs a demonstration of the Inflection Curator."""
    print("🛍️  Inflection Curator - AI Personal Shopping Assistant")
    print("=" * 70)

    # Initialize the shopping orchestrator
    orch = ShoppingOrchestrator()

    print(f"\nAvailable Shopping Personas: {', '.join(orch.list_personas())}")
    print(f"Current Persona: {orch.get_current_persona_info()['full_name']}")
    print(f"Execution Mode: {orch.execution_mode}")

    print("\n" + "=" * 70)

    # Demo queries
    demo_queries = [
        "Looking for wireless headphones under $100",
        "I need a laptop for gaming",
        "Show me reviews for the iPhone 15 Pro",
    ]

    for i, query in enumerate(demo_queries, 1):
        print(f"\n🎯 DEMO {i}: {query}")
        print("-" * 50)

        result = orch.handle(query)

        # Show structured results instead of raw JSON
        print("📋 Response Summary:")
        if result.get("error"):
            print(f"   ❌ Error: {result['error']}")
        else:
            qu_data = result.get("query_understanding")
            if qu_data:
                print(
                    f"   🧠 Intent: {qu_data.get('intent')} (confidence: {qu_data.get('confidence', 0):.2f})"
                )
                if qu_data.get("products"):
                    print(f"   🛍️  Products: {', '.join(qu_data['products'])}")
                if qu_data.get("category"):
                    print(f"   📂 Category: {qu_data['category']}")

            execution = result.get("execution", {})
            if execution.get("output"):
                print(f"   ✅ Execution: Success")
            elif execution.get("clarify"):
                print(f"   ❓ Needs clarification: {execution['clarify']}")

        if i < len(demo_queries):
            input("\nPress Enter to continue to next demo...")


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--cli":
        cli()
    else:
        main()

#!/usr/bin/env python3
"""Startup script for Inflection Curator FastAPI service.

This script provides various ways to start the FastAPI service with
different configurations for development and production.

Example:
    # Development mode with auto-reload
    python start_service.py --dev

    # Production mode
    python start_service.py --prod

    # Custom host and port
    python start_service.py --host 0.0.0.0 --port 8080
"""

import argparse
import os
import sys
import uvicorn
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def check_environment():
    """Check if required environment variables are set."""
    required_vars = ["OPENAI_API_KEY", "UNWRANGLE_APIKEY"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        print(f"⚠️  Warning: Missing environment variables: {', '.join(missing_vars)}")
        print("   The service will run but some features may not work properly.")
        print("   Set them in a .env file or export them directly:")
        for var in missing_vars:
            print(f"   export {var}='your-key-here'")
        print()
    else:
        print("✅ All required environment variables are set")


def start_development_server(host: str = "127.0.0.1", port: int = 8000):
    """Start the development server with auto-reload."""
    print("🚀 Starting Inflection Curator API in Development Mode")
    print(f"   📍 Server: http://{host}:{port}")
    print(f"   📚 API Docs: http://{host}:{port}/docs")
    print(f"   📖 ReDoc: http://{host}:{port}/redoc")
    print("   🔄 Auto-reload: Enabled")
    print()

    check_environment()

    uvicorn.run(
        "inflection_curator.service.api:app",
        host=host,
        port=port,
        reload=True,
        reload_dirs=[str(project_root / "inflection_curator")],
        log_level="info",
        access_log=True,
    )


def start_production_server(host: str = "0.0.0.0", port: int = 8000, workers: int = 1):
    """Start the production server."""
    print("🏭 Starting Inflection Curator API in Production Mode")
    print(f"   📍 Server: http://{host}:{port}")
    print(f"   👥 Workers: {workers}")
    print("   🔄 Auto-reload: Disabled")
    print()

    check_environment()

    uvicorn.run(
        "inflection_curator.service.api:app",
        host=host,
        port=port,
        workers=workers,
        log_level="info",
        access_log=True,
    )


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Start the Inflection Curator FastAPI service",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python start_service.py --dev                    # Development mode
  python start_service.py --prod                   # Production mode
  python start_service.py --host 0.0.0.0 --port 8080  # Custom host/port
  python start_service.py --prod --workers 4       # Production with 4 workers
        """,
    )

    parser.add_argument(
        "--dev", action="store_true", help="Start in development mode with auto-reload"
    )
    parser.add_argument("--prod", action="store_true", help="Start in production mode")
    parser.add_argument(
        "--host", default="127.0.0.1", help="Host to bind to (default: 127.0.0.1)"
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port to bind to (default: 8000)"
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=1,
        help="Number of worker processes (production only)",
    )

    args = parser.parse_args()

    # Check for conflicting arguments
    if args.dev and args.prod:
        print("❌ Error: Cannot specify both --dev and --prod")
        sys.exit(1)

    # Default to development mode if neither specified
    if not args.dev and not args.prod:
        args.dev = True

    try:
        if args.dev:
            start_development_server(args.host, args.port)
        else:
            start_production_server(args.host, args.port, args.workers)

    except KeyboardInterrupt:
        print("\n👋 Shutting down Inflection Curator API service")
    except Exception as e:
        print(f"❌ Failed to start service: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()

"""
Uvicorn entry point for surogate-agent-api.

Usage:
    surogate-agent-api                 # default: 127.0.0.1:8000
    surogate-agent-api --host 0.0.0.0 --port 9000
    python -m surogate_agent.api.server
"""

from __future__ import annotations

import argparse
import sys


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        prog="surogate-agent-api",
        description="Start the surogate-agent FastAPI server.",
    )
    parser.add_argument("--host", default="127.0.0.1", help="Bind host (default: 127.0.0.1)")
    parser.add_argument("--port", type=int, default=8000, help="Bind port (default: 8000)")
    parser.add_argument("--reload", action="store_true", help="Enable auto-reload (development)")
    args = parser.parse_args(argv)

    try:
        import uvicorn
    except ImportError:
        print(
            "uvicorn is required. Install it with: pip install 'surogate-agent[api]'",
            file=sys.stderr,
        )
        sys.exit(1)

    uvicorn.run(
        "surogate_agent.api.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()

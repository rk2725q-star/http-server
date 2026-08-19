#!/usr/bin/env python3
"""
NetServe - Intelligent HTTP Web Server and Network Monitoring System
CLI Entry Point.
"""

import argparse
import os
import sys
from pathlib import Path

# Add netserve root directory to sys.path
root_dir = Path(__file__).resolve().parent
if str(root_dir) not in sys.path:
    sys.path.insert(0, str(root_dir))

from server.config import config
from server.server import run_server


def main():
    """Main CLI entrypoint for NetServe."""
    parser = argparse.ArgumentParser(
        description="NetServe - Intelligent HTTP Web Server and Network Monitoring System",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run.py                                # Start on 127.0.0.1:8080 with 8 workers
  python run.py --host 0.0.0.0 --port 8080     # Listen on all network interfaces
  python run.py --host 127.0.0.1 --port 3000 --workers 16
        """
    )

    parser.add_argument(
        "--host",
        default=config.HOST,
        help=f"Host address to bind to (default: {config.HOST})"
    )

    parser.add_argument(
        "--port", "-p",
        type=int,
        default=config.PORT,
        help=f"TCP port to listen on (default: {config.PORT})"
    )

    parser.add_argument(
        "--workers", "-w",
        type=int,
        default=config.MAX_WORKERS,
        help=f"Number of worker threads (default: {config.MAX_WORKERS})"
    )

    parser.add_argument(
        "--version", "-v",
        action="version",
        version=f"NetServe v{config.SERVER_VERSION} ({config.PROTOCOL})"
    )

    args = parser.parse_args()

    # Validate argument ranges
    if not (1 <= args.port <= 65535):
        print(f"[Error] Port must be between 1 and 65535 (received: {args.port})", file=sys.stderr)
        sys.exit(1)

    if args.workers < 1:
        print(f"[Error] Workers must be at least 1 (received: {args.workers})", file=sys.stderr)
        sys.exit(1)

    # Launch server
    try:
        run_server(host=args.host, port=args.port, workers=args.workers)
    except KeyboardInterrupt:
        print("\n[NetServe] Server terminated by user.")
    except Exception as e:
        print(f"[Error] Fatal server exception: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
"""``whisper-hub`` console script."""

from __future__ import annotations

import argparse
import logging
import sys
from dataclasses import replace

from .app import run
from .config import Config


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="whisper-hub",
        description="Self-hosted Whisper gateway with per-device keys and shared history.",
    )
    parser.add_argument("--host", help="listen address (overrides WHUB_HOST)")
    parser.add_argument("--port", type=int, help="listen port (overrides WHUB_PORT)")
    args = parser.parse_args(argv)

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    try:
        config = Config.from_env()
    except ValueError as exc:
        print(f"whisper-hub: configuration error: {exc}", file=sys.stderr)
        return 2
    overrides = {}
    if args.host:
        overrides["host"] = args.host
    if args.port:
        overrides["port"] = args.port
    if overrides:
        config = replace(config, **overrides)
    try:
        run(config)
    except ValueError as exc:
        # Out-of-range WHUB_* values (beam size 50, a malformed URL, ...) fail settings
        # validation inside create_app; report them like any other configuration error.
        print(f"whisper-hub: configuration error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

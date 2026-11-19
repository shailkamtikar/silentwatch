"""Command-line entry point."""

from __future__ import annotations

import argparse
import sys

from silentwatch import __version__


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="silentwatch", description="SILENTWATCH laptop protection")
    p.add_argument("--version", action="store_true", help="print version and exit")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.version:
        print(__version__)
        return 0
    print("silentwatch: nothing to run yet (see docs/PLAYBOOK.md)", file=sys.stderr)
    return 0

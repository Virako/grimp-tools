"""Main CLI entry point with subcommands."""

import argparse
import sys


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="grimp-tools",
        description="Dependency analysis and coupling enforcement for Django/Python projects.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # Placeholder subcommands — will be wired in subsequent phases
    subparsers.add_parser("analyze", help="Module/app dependency analysis and cycles")

    snapshot_parser = subparsers.add_parser("snapshot", help="Save/diff/summary of dependency snapshots")
    snapshot_parser.add_argument("action", choices=["save", "diff", "summary"])

    subparsers.add_parser("focus-graph", help="Focused mermaid graph from git diff")
    subparsers.add_parser("contracts-graph", help="Visualize import-linter contracts")
    subparsers.add_parser("check-names", help="File naming convention checker")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    print(f"grimp-tools {args.command}: not yet implemented")
    sys.exit(1)

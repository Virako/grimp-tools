"""Main CLI entry point with subcommands."""

import argparse
import sys

from grimp_tools import snapshot
from grimp_tools.analyze import run as run_analyze
from grimp_tools.check_names import run as run_check_names


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="grimp-tools",
        description="Dependency analysis and coupling enforcement for Django/Python projects.",
    )
    subparsers = parser.add_subparsers(dest="command")

    # analyze
    analyze_parser = subparsers.add_parser(
        "analyze", help="Module/app dependency analysis and cycles"
    )
    analyze_parser.add_argument(
        "--skip",
        help="Comma-separated module parts to skip (overrides pyproject.toml config)",
    )
    analyze_parser.add_argument(
        "--extra-packages",
        default="",
        help="Comma-separated extra packages beyond pyproject.toml root_packages",
    )
    analyze_parser.add_argument(
        "--exit-on-cycles",
        action="store_true",
        help="Exit with code 1 if cycles are found (useful for CI)",
    )
    analyze_parser.add_argument(
        "--history",
        help="Path to append analysis snapshot with commit hash",
    )

    # snapshot
    snapshot_parser = subparsers.add_parser(
        "snapshot", help="Save/diff/summary of dependency snapshots"
    )
    snapshot_parser.add_argument("action", choices=["save", "diff", "summary"])
    snapshot_parser.add_argument(
        "--ref",
        help="Git ref to compare against (branch, tag, or commit hash)",
    )

    # check-names
    check_names_parser = subparsers.add_parser(
        "check-names", help="File naming convention checker"
    )
    check_names_parser.add_argument(
        "--ref",
        help="Only check files changed vs this git ref",
    )

    # placeholders
    subparsers.add_parser("focus-graph", help="Focused mermaid graph from git diff")
    subparsers.add_parser("contracts-graph", help="Visualize import-linter contracts")

    args = parser.parse_args()
    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "analyze":
        skip = None
        if args.skip:
            skip = {s.strip() for s in args.skip.split(",")}
        extra = (
            [p.strip() for p in args.extra_packages.split(",") if p.strip()]
            if args.extra_packages
            else None
        )
        run_analyze(
            skip=skip,
            extra_packages=extra,
            exit_on_cycles=args.exit_on_cycles,
            history=args.history,
        )
    elif args.command == "snapshot":
        if args.action == "save":
            snapshot.cmd_save()
        elif args.action == "diff":
            snapshot.cmd_diff(ref=args.ref)
        else:
            snapshot.cmd_summary()
    elif args.command == "check-names":
        run_check_names(ref=args.ref)
    else:
        print(f"grimp-tools {args.command}: not yet implemented")
        sys.exit(1)

"""Main CLI entry point with subcommands."""

import argparse
import os
import sys

from grimp_tools import snapshot
from grimp_tools.analyze import run as run_analyze
from grimp_tools.check_names import run as run_check_names
from grimp_tools.contracts_graph import run as run_contracts_graph
from grimp_tools.focus import run as run_focus_graph


def main() -> None:
    # Add current directory to the path, as this doesn't happen automatically.
    sys.path.insert(0, os.getcwd())
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

    # contracts-graph
    contracts_graph_parser = subparsers.add_parser(
        "contracts-graph", help="Visualize import-linter contracts"
    )
    contracts_graph_parser.add_argument("-o", "--output", help="Output file path")

    # focus-graph
    focus_parser = subparsers.add_parser(
        "focus-graph", help="Focused mermaid graph from git diff"
    )
    focus_parser.add_argument(
        "--new", default="HEAD", help="New ref to compare (default: HEAD)"
    )
    focus_parser.add_argument(
        "--old", default=None, help="Old ref to compare against (default: NEW~1)"
    )
    focus_parser.add_argument("-o", "--output", help="Output file path")

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
    elif args.command == "contracts-graph":
        run_contracts_graph(output=args.output)
    elif args.command == "focus-graph":
        run_focus_graph(new_ref=args.new, old_ref=args.old, output=args.output)

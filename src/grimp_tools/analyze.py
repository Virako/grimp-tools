"""Module and app-level dependency analysis with cycle detection."""

import subprocess
from datetime import UTC, datetime
from pathlib import Path

from grimp_tools.config import get_skip_modules, load_root_packages
from grimp_tools.graph import (
    aggregate_apps,
    build_edge_set,
    build_graph,
    build_graph_stats,
    find_cycles,
)


def analyze(edges: set[tuple[str, str]]) -> tuple[bool, str]:
    """Run the full analysis and return (has_cycles, report_text)."""
    nodes, in_deg, out_deg, adj = build_graph_stats(edges)
    lines: list[str] = []

    def out(text: str = "") -> None:
        print(text)
        lines.append(text)

    # Module-level cycles
    mod_cycles = find_cycles(adj)
    out("=== MODULE CYCLES ===")
    if mod_cycles:
        for c in mod_cycles:
            out(f"  CYCLE: {' -> '.join(c)}")
    else:
        out("  No cycles found")

    # App-level
    app_edges, app_adj = aggregate_apps(edges)

    out("\n=== APP DEPENDENCIES ===")
    for (src, dst), count in sorted(app_edges.items(), key=lambda x: -x[1]):
        out(f"  {src} -> {dst} ({count} imports)")

    app_cycles = find_cycles(app_adj)
    out()
    if app_cycles:
        out("  APP CYCLES:")
        for c in app_cycles:
            out(f"    CYCLE: {' -> '.join(c)}")
    else:
        out("  No cycles between apps")

    # Coupling table
    out("\n=== COUPLING (by total dependencies) ===")
    coupled = [
        (n, out_deg.get(n, 0), in_deg.get(n, 0))
        for n in sorted(nodes)
        if out_deg.get(n, 0) + in_deg.get(n, 0) > 0
    ]
    coupled.sort(key=lambda x: x[1] + x[2], reverse=True)
    out(f"  {'Module':<40} {'Out':>4} {'In':>4} {'Total':>6}")
    out(f"  {'─' * 40} {'─' * 4} {'─' * 4} {'─' * 6}")
    for name, o, i in coupled:
        out(f"  {name:<40} {o:>4} {i:>4} {o + i:>6}")

    # Summary
    out("\n=== SUMMARY ===")
    out(
        f"  Modules: {len(nodes)}, Edges: {len(edges)}, "
        f"Module cycles: {len(mod_cycles)}, App cycles: {len(app_cycles)}"
    )

    return bool(mod_cycles or app_cycles), "\n".join(lines)


def save_history(history_path: str, report: str) -> None:
    """Append a timestamped snapshot to the history file."""
    commit = _git_short_hash()
    timestamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    header = f"--- {timestamp} | commit {commit} ---"

    path = Path(history_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a") as f:
        f.write(f"\n{header}\n{report}\n")

    print(f"\nHistory appended to {history_path}")


def _git_short_hash() -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def run(
    skip: set[str] | None = None,
    extra_packages: list[str] | None = None,
    exit_on_cycles: bool = False,
    history: str | None = None,
) -> None:
    """Entry point for the analyze subcommand."""
    packages = load_root_packages()
    if extra_packages:
        packages = sorted(set(packages + extra_packages))
    if skip is None:
        skip = get_skip_modules()

    print(f"Building import graph for {len(packages)} packages...")
    graph = build_graph(packages)
    print(f"Graph built: {len(graph.modules)} modules, {graph.count_imports()} imports")
    print()

    root_set = set(packages)
    edges = build_edge_set(graph, root_set, skip)
    has_cycles, report = analyze(edges)

    if history:
        save_history(history, report)

    if exit_on_cycles and has_cycles:
        raise SystemExit(1)

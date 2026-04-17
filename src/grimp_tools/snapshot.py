"""Save and compare dependency snapshots."""

import json
import subprocess
import sys
from collections import defaultdict
from datetime import UTC, datetime
from pathlib import Path

from grimp_tools.config import get_skip_modules, get_snapshot_path, load_root_packages
from grimp_tools.graph import build_edge_set, build_graph, compute_metrics


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


def _git_show_file(ref: str, path: str) -> str | None:
    """Read a file from a git ref without checking out."""
    try:
        result = subprocess.run(
            ["git", "show", f"{ref}:{path}"],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout
    except subprocess.CalledProcessError:
        return None


def _build_current_edges() -> set[tuple[str, str]]:
    """Build edge set from the current codebase."""
    packages = load_root_packages()
    skip = get_skip_modules()
    print(f"Building import graph for {len(packages)} packages...")
    graph = build_graph(packages)
    return build_edge_set(graph, set(packages), skip)


def _load_snapshot(ref: str | None, snapshot_path: Path) -> dict | None:
    """Load snapshot from disk or from a git ref."""
    if ref:
        content = _git_show_file(ref, str(snapshot_path))
        if content is None:
            print(f"No snapshot found at {ref}:{snapshot_path}")
            return None
        return json.loads(content)

    if not snapshot_path.exists():
        print(f"No snapshot found at {snapshot_path}. Run 'save' first.")
        return None
    return json.loads(snapshot_path.read_text())


def _print_diff(
    snapshot: dict,
    new_edges: set[tuple[str, str]],
    ref_label: str,
) -> None:
    """Print the diff between a snapshot and current edges."""
    old_edges = {tuple(e.split(" -> ")) for e in snapshot["edges"]}

    added = new_edges - old_edges
    removed = old_edges - new_edges

    old_metrics = snapshot["metrics"]
    new_metrics = compute_metrics(new_edges)

    print(f"\nComparing against {ref_label}")
    print()

    for key in ["edges", "cross_app_edges", "modules"]:
        old_val = old_metrics[key]
        new_val = new_metrics[key]
        delta = new_val - old_val
        sign = "+" if delta > 0 else ""
        marker = " *" if delta != 0 else ""
        print(f"  {key:<25} {old_val:>6} -> {new_val:>6}  ({sign}{delta}){marker}")

    if not added and not removed:
        print("\n  No changes in dependencies.")
        return

    if added:
        by_apps: dict[tuple[str, str], list[str]] = defaultdict(list)
        for src, dst in sorted(added):
            by_apps[(src.split(".")[0], dst.split(".")[0])].append(f"{src} -> {dst}")

        print(f"\n  ADDED ({len(added)} edges):")
        for (src_app, dst_app), items in sorted(by_apps.items()):
            cross = " [cross-app]" if src_app != dst_app else ""
            print(f"    {src_app} -> {dst_app}{cross}:")
            for item in items:
                print(f"      {item}")

    if removed:
        by_apps_r: dict[tuple[str, str], list[str]] = defaultdict(list)
        for src, dst in sorted(removed):
            by_apps_r[(src.split(".")[0], dst.split(".")[0])].append(f"{src} -> {dst}")

        print(f"\n  REMOVED ({len(removed)} edges):")
        for (src_app, dst_app), items in sorted(by_apps_r.items()):
            cross = " [cross-app]" if src_app != dst_app else ""
            print(f"    {src_app} -> {dst_app}{cross}:")
            for item in items:
                print(f"      {item}")


def cmd_save() -> None:
    """Save current snapshot to disk."""
    snapshot_path = get_snapshot_path()
    edges = _build_current_edges()
    metrics = compute_metrics(edges)

    snapshot = {
        "timestamp": datetime.now(UTC).isoformat(),
        "commit": _git_short_hash(),
        "metrics": metrics,
        "edges": sorted(f"{src} -> {dst}" for src, dst in edges),
    }

    snapshot_path.parent.mkdir(parents=True, exist_ok=True)
    snapshot_path.write_text(json.dumps(snapshot, indent=2) + "\n")
    print(f"Snapshot saved to {snapshot_path}")
    print(
        f"  Edges: {metrics['edges']}, "
        f"Cross-app: {metrics['cross_app_edges']}, "
        f"Modules: {metrics['modules']}"
    )


def cmd_diff(ref: str | None = None) -> None:
    """Compare current state against a snapshot."""
    snapshot_path = get_snapshot_path()
    snapshot = _load_snapshot(ref, snapshot_path)
    if snapshot is None:
        sys.exit(1)

    new_edges = _build_current_edges()

    if ref:
        ref_label = f"snapshot at {ref} (commit {snapshot['commit']})"
    else:
        ref_label = (
            f"snapshot from {snapshot['timestamp']} (commit {snapshot['commit']})"
        )
    _print_diff(snapshot, new_edges, ref_label)


def cmd_summary() -> None:
    """Print current summary without saving."""
    edges = _build_current_edges()
    metrics = compute_metrics(edges)

    app_out: dict[str, int] = defaultdict(int)
    for src, dst in edges:
        src_app, dst_app = src.split(".")[0], dst.split(".")[0]
        if src_app != dst_app:
            app_out[src_app] += 1

    print(
        f"\nEdges: {metrics['edges']}, "
        f"Cross-app: {metrics['cross_app_edges']}, "
        f"Modules: {metrics['modules']}"
    )
    print("\nCross-app edges by source app:")
    for app, count in sorted(app_out.items(), key=lambda x: -x[1]):
        print(f"  {app:<25} {count}")

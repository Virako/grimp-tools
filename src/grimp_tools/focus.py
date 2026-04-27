"""Generate a focused Mermaid dependency graph from a git diff.

Uses two git worktrees to build clean import graphs (no untracked files),
compares edges, and shows only what changed with cycle detection and
cross-app coupling metrics.
"""

import json
import shutil
import subprocess
import sys
import tempfile
from collections import defaultdict
from dataclasses import dataclass, field
from pathlib import Path

from grimp_tools.config import get_skip_modules, load_root_packages
from grimp_tools.html import render_page

ADDED = "added"
MODIFIED = "modified"
RENAMED = "renamed"
DELETED = "deleted"
NEIGHBOR = "neighbor"


@dataclass
class EdgeDelta:
    """Edge classification between two snapshots."""

    new_edges: set[tuple[str, str]] = field(default_factory=set)
    removed_edges: set[tuple[str, str]] = field(default_factory=set)

    @property
    def new_cross(self) -> int:
        return sum(1 for s, d in self.new_edges if s.split(".")[0] != d.split(".")[0])

    @property
    def new_intra(self) -> int:
        return len(self.new_edges) - self.new_cross

    @property
    def removed_cross(self) -> int:
        return sum(
            1 for s, d in self.removed_edges if s.split(".")[0] != d.split(".")[0]
        )

    @property
    def removed_intra(self) -> int:
        return len(self.removed_edges) - self.removed_cross

    @property
    def cross_app_delta(self) -> int:
        return self.new_cross - self.removed_cross


def _git_short_hash(ref: str) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", ref],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ref


def _git_commit_subject(ref: str) -> str:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s", ref],
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except subprocess.CalledProcessError:
        return ""


def _git_diff_classified(
    new_ref: str,
    old_ref: str,
) -> tuple[dict[str, str], dict[str, str]]:
    """Return ({filepath: change_type}, {new_path: old_path for renames})."""
    result_map: dict[str, str] = {}
    renames: dict[str, str] = {}
    try:
        result = subprocess.run(
            [
                "git",
                "diff",
                "--name-status",
                "--diff-filter=ACMRD",
                old_ref,
                new_ref,
                "--",
                "*.py",
            ],
            capture_output=True,
            text=True,
            check=True,
        )
    except subprocess.CalledProcessError:
        return result_map, renames

    status_map = {"A": ADDED, "M": MODIFIED, "D": DELETED}
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if not parts:
            continue
        status_code = parts[0]
        if status_code.startswith("R"):
            if len(parts) >= 3:
                old_path, new_path = parts[1], parts[2]
                result_map[old_path] = DELETED
                result_map[new_path] = RENAMED
                renames[new_path] = old_path
        elif status_code in status_map and len(parts) >= 2:
            result_map[parts[1]] = status_map[status_code]

    return result_map, renames


def file_to_module(filepath: str, root_packages: set[str]) -> str | None:
    """Convert a file path to a Python module name."""
    path = Path(filepath)
    parts = list(path.with_suffix("").parts)
    if not parts or parts[0] not in root_packages:
        return None
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts) if parts else None


def _build_edges_in_worktree(
    ref: str, tmp_base: str, skip: set[str]
) -> set[tuple[str, str]]:
    """Create a worktree at ref, build grimp graph, return edges, cleanup."""
    sha = subprocess.run(
        ["git", "rev-parse", ref],
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    wt_dir = str(Path(tmp_base) / f"wt-{_git_short_hash(ref)}")

    subprocess.run(
        ["git", "worktree", "add", wt_dir, sha],
        capture_output=True,
        text=True,
        check=True,
    )

    skip_json = json.dumps(list(skip))
    try:
        result = subprocess.run(
            [
                sys.executable,
                "-c",
                f"""
import sys, json, tomllib
sys.path.insert(0, {wt_dir!r})

import grimp

with open({wt_dir!r} + '/pyproject.toml', 'rb') as f:
    data = tomllib.load(f)
packages = data['tool']['importlinter']['root_packages']
skip = set(json.loads({skip_json!r}))
root_set = set(packages)

graph = grimp.build_graph(packages[0], *packages[1:], exclude_type_checking_imports=True)

edges = []
for mod in graph.modules:
    parts = mod.split('.')
    if any(p in skip for p in parts) or parts[0] not in root_set:
        continue
    for imp in graph.find_modules_directly_imported_by(mod):
        iparts = imp.split('.')
        if any(p in skip for p in iparts) or iparts[0] not in root_set:
            continue
        edges.append([mod, imp])

print(json.dumps(edges))
""",
            ],
            capture_output=True,
            text=True,
            check=True,
            cwd=wt_dir,
        )
        edges_list = json.loads(result.stdout)
        return {(s, d) for s, d in edges_list}
    finally:
        subprocess.run(
            ["git", "worktree", "remove", wt_dir, "--force"],
            capture_output=True,
            text=True,
        )


def find_cycles_in_new_edges(
    new_edges: set[tuple[str, str]],
    all_current_edges: set[tuple[str, str]],
) -> list[list[str]]:
    """Find cycles that pass through at least one new edge."""
    if not new_edges:
        return []

    adj: dict[str, list[str]] = defaultdict(list)
    for src, dst in all_current_edges:
        adj[src].append(dst)

    new_edge_nodes = {n for edge in new_edges for n in edge}
    visited: set[str] = set()
    in_stack: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        in_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor in in_stack:
                idx = path.index(neighbor)
                cycle = path[idx:] + [neighbor]
                for i in range(len(cycle) - 1):
                    if (cycle[i], cycle[i + 1]) in new_edges:
                        cycles.append(cycle)
                        break
            elif neighbor not in visited:
                dfs(neighbor, [*path, neighbor])
        in_stack.remove(node)

    for node in sorted(new_edge_nodes):
        if node not in visited:
            dfs(node, [node])

    return cycles


def render_mermaid(
    module_types: dict[str, str],
    rename_labels: dict[str, str],
    edge_delta: EdgeDelta,
    cycles: list[list[str]],
) -> str:
    """Render a Mermaid flowchart showing only changed edges."""
    lines = ["graph TD"]

    changed_edges = edge_delta.new_edges | edge_delta.removed_edges
    if not changed_edges and not module_types:
        lines.append("    no_deps[No dependency changes]")
        return "\n".join(lines)

    all_nodes = set(module_types.keys())
    for s, d in changed_edges:
        all_nodes.add(s)
        all_nodes.add(d)

    cycle_edge_set: set[tuple[str, str]] = set()
    for cycle in cycles:
        for i in range(len(cycle) - 1):
            cycle_edge_set.add((cycle[i], cycle[i + 1]))

    node_id = {mod: f"n{i}" for i, mod in enumerate(sorted(all_nodes))}

    icons = {
        ADDED: "+",
        MODIFIED: "~",
        RENAMED: "&#8594;",
        DELETED: "-",
        NEIGHBOR: "",
    }

    apps: dict[str, list[str]] = defaultdict(list)
    for mod in sorted(all_nodes):
        apps[mod.split(".")[0]].append(mod)

    for app in sorted(apps):
        lines.append(f"    subgraph {app}")
        for mod in apps[app]:
            nid = node_id[mod]
            ct = module_types.get(mod, NEIGHBOR)
            icon = icons.get(ct, "")
            prefix = f"{icon} " if icon else ""
            short = mod.split(".", 1)[1] if "." in mod else mod

            if ct == RENAMED and mod in rename_labels:
                old_short = (
                    rename_labels[mod].split(".", 1)[1]
                    if "." in rename_labels[mod]
                    else rename_labels[mod]
                )
                lines.append(f'        {nid}["{prefix}{old_short} &#8594; {short}"]')
            elif ct == DELETED and mod in rename_labels:
                continue
            else:
                lines.append(f'        {nid}["{prefix}{short}"]')
        lines.append("    end")

    lines.append("")

    sorted_edges = sorted(changed_edges)
    for src, dst in sorted_edges:
        if src not in node_id or dst not in node_id:
            continue
        cross = src.split(".")[0] != dst.split(".")[0]
        sid, did = node_id[src], node_id[dst]
        is_new = (src, dst) in edge_delta.new_edges
        label = "+new" if is_new else "-removed"
        if cross:
            lines.append(f"    {sid} -. {label} .-> {did}")
        else:
            lines.append(f"    {sid} -- {label} --> {did}")

    # Style nodes
    style_map = {
        ADDED: "fill:#c8e6c9,stroke:#2e7d32,stroke-width:2px",
        MODIFIED: "fill:#fff9c4,stroke:#f9a825,stroke-width:2px",
        RENAMED: "fill:#bbdefb,stroke:#1565c0,stroke-width:2px",
        DELETED: "fill:#ffcdd2,stroke:#c62828,stroke-width:2px,stroke-dasharray:5",
        NEIGHBOR: "fill:#f5f5f5,stroke:#999,stroke-width:1px",
    }
    lines.append("")
    for ct, style in style_map.items():
        for m in sorted(all_nodes):
            if module_types.get(m, NEIGHBOR) == ct and m in node_id:
                lines.append(f"    style {node_id[m]} {style}")

    # Style edges
    for link_idx, (src, dst) in enumerate(sorted_edges):
        if src not in node_id or dst not in node_id:
            continue
        is_cycle = (src, dst) in cycle_edge_set
        if (src, dst) in edge_delta.new_edges:
            extra = ",stroke-width:3px" if is_cycle else ""
            lines.append(f"    linkStyle {link_idx} stroke:#2e7d32{extra}")
        else:
            lines.append(f"    linkStyle {link_idx} stroke:#c62828,stroke-dasharray:5")

    return "\n".join(lines)


_EXTRA_CSS = """
  .added { background: #c8e6c9; border: 1px solid #2e7d32; }
  .modified { background: #fff9c4; border: 1px solid #f9a825; }
  .renamed { background: #bbdefb; border: 1px solid #1565c0; }
  .deleted { background: #ffcdd2; border: 1px solid #c62828; }
  .neighbor { background: #f5f5f5; border: 1px solid #999; }
  .edge-new { background: #2e7d32; }
  .edge-removed { background: repeating-linear-gradient(90deg, #c62828 0 4px, transparent 4px 8px); }
  #summary { padding: 12px 20px; font-size: 13px; color: #333; border-bottom: 1px solid #eee;
              white-space: pre; }
  #graph { width: 100%; overflow: auto; padding: 20px; box-sizing: border-box; }
"""


def render_html(mermaid_code: str, summary: str) -> str:
    """Render standalone HTML with mermaid graph and summary."""
    summary_html = summary.replace("\n", "<br>")
    body = f"""<div class="toolbar">
  <div class="legend">
    <span><span class="swatch added"></span> + Added</span>
    <span><span class="swatch modified"></span> ~ Modified</span>
    <span><span class="swatch renamed"></span> &rarr; Renamed</span>
    <span><span class="swatch deleted"></span> - Deleted</span>
    <span><span class="swatch neighbor"></span> Neighbor</span>
    <span>|</span>
    <span><span class="edge-sample edge-new"></span> +new edge</span>
    <span><span class="edge-sample edge-removed"></span> -removed edge</span>
    <span>|</span>
    <span>A &rarr; B = A imports B</span>
  </div>
  <button onclick="downloadSvg()">Download SVG</button>
</div>
<div id="summary">{summary_html}</div>
<div id="graph"></div>"""

    scripts = (
        "<script>"
        "mermaid.initialize({ startOnLoad: false, theme: 'default', securityLevel: 'loose' });"
        "(async function() {"
        "const container = document.getElementById('graph');"
        f"const {{ svg }} = await mermaid.render('focus-graph', `{mermaid_code}`);"
        "container.innerHTML = svg;"
        "})();"
        "function downloadSvg() {"
        "const svg = document.querySelector('#graph svg');"
        "if (!svg) { alert('Graph not rendered yet'); return; }"
        "const data = new XMLSerializer().serializeToString(svg);"
        "const blob = new Blob([data], { type: 'image/svg+xml' });"
        "const a = document.createElement('a');"
        "a.href = URL.createObjectURL(blob);"
        "a.download = 'focus-graph.svg';"
        "a.click();"
        "}"
        "</script>"
    )
    return render_page(
        title="Focus Dependency Graph",
        body=body,
        extra_css=_EXTRA_CSS,
        scripts=scripts,
    )


def build_summary(
    new_ref: str,
    old_ref: str,
    new_total: int,
    new_cross: int,
    old_total: int,
    old_cross: int,
    module_types: dict[str, str],
    edge_delta: EdgeDelta,
    cycles: list[list[str]],
) -> str:
    """Build a text summary of the focus graph diff."""
    new_hash = _git_short_hash(new_ref)
    old_hash = _git_short_hash(old_ref)
    new_subject = _git_commit_subject(new_ref)

    counts: dict[str, int] = defaultdict(int)
    for ct in module_types.values():
        counts[ct] += 1

    parts = []
    if counts[ADDED]:
        parts.append(f"+{counts[ADDED]} added")
    if counts[MODIFIED]:
        parts.append(f"~{counts[MODIFIED]} modified")
    if counts[RENAMED]:
        parts.append(f"->{counts[RENAMED]} renamed")
    if counts[DELETED]:
        parts.append(f"-{counts[DELETED]} deleted")

    changes_line = ", ".join(parts) if parts else "no changes"
    apps_touched = sorted({m.split(".")[0] for m in module_types})

    lines = [
        f"Commit: {new_hash} {new_subject}",
        f"Compared: {new_hash} vs {old_hash}",
        f"Edges: {old_total} -> {new_total} ({new_total - old_total:+d})  "
        f"Cross-app: {old_cross} -> {new_cross} ({new_cross - old_cross:+d})",
        "",
        f"Modules: {changes_line}",
        f"Apps touched: {', '.join(apps_touched)}",
    ]

    if edge_delta.new_edges or edge_delta.removed_edges:
        lines.append("")
        if edge_delta.new_edges:
            lines.append(
                f"  +{len(edge_delta.new_edges)} new edges "
                f"(+{edge_delta.new_cross} cross-app, +{edge_delta.new_intra} intra-app)"
            )
        if edge_delta.removed_edges:
            lines.append(
                f"  -{len(edge_delta.removed_edges)} removed edges "
                f"(-{edge_delta.removed_cross} cross-app, -{edge_delta.removed_intra} intra-app)"
            )
    else:
        lines.append("")
        lines.append("No edge changes")

    if cycles:
        lines.append("")
        lines.append(f"WARNING: {len(cycles)} new cycle(s) detected:")
        for cycle in cycles:
            lines.append(f"  CYCLE: {' -> '.join(cycle)}")

    return "\n".join(lines)


def run(
    new_ref: str = "HEAD",
    old_ref: str | None = None,
    output: str | None = None,
) -> None:
    """Entry point for the focus-graph subcommand."""
    old_ref = old_ref or f"{new_ref}~1"
    skip = get_skip_modules()

    new_hash = _git_short_hash(new_ref)
    old_hash = _git_short_hash(old_ref)
    new_subject = _git_commit_subject(new_ref)
    print(
        f"Comparing {new_hash} ({new_subject}) vs {old_hash}",
        file=sys.stderr,
    )

    root_packages = load_root_packages()
    root_set = set(root_packages)
    file_types, renames = _git_diff_classified(new_ref, old_ref)

    if not file_types:
        print("No Python files changed.", file=sys.stderr)
        return

    module_types: dict[str, str] = {}
    rename_labels: dict[str, str] = {}
    for filepath, change_type in file_types.items():
        mod = file_to_module(filepath, root_set)
        if mod:
            module_types[mod] = change_type
            if change_type == RENAMED and filepath in renames:
                old_mod = file_to_module(renames[filepath], root_set)
                if old_mod:
                    rename_labels[mod] = old_mod

    icon_map = {ADDED: "+", MODIFIED: "~", RENAMED: "->", DELETED: "-"}
    print(f"\nModules ({len(module_types)}):", file=sys.stderr)
    for m in sorted(module_types):
        icon = icon_map.get(module_types[m], "?")
        extra = f" (was {rename_labels[m]})" if m in rename_labels else ""
        print(f"  [{icon}] {m}{extra}", file=sys.stderr)

    tmp_base = tempfile.mkdtemp(prefix="focus-mermaid-")
    try:
        print(f"\nBuilding graph at {new_hash}...", file=sys.stderr)
        new_edges = _build_edges_in_worktree(new_ref, tmp_base, skip)
        new_cross = sum(1 for s, d in new_edges if s.split(".")[0] != d.split(".")[0])
        print(f"  {len(new_edges)} edges ({new_cross} cross-app)", file=sys.stderr)

        print(f"Building graph at {old_hash}...", file=sys.stderr)
        old_edges = _build_edges_in_worktree(old_ref, tmp_base, skip)
        old_cross = sum(1 for s, d in old_edges if s.split(".")[0] != d.split(".")[0])
        print(f"  {len(old_edges)} edges ({old_cross} cross-app)", file=sys.stderr)
    finally:
        shutil.rmtree(tmp_base, ignore_errors=True)
        subprocess.run(
            ["git", "worktree", "prune"],
            capture_output=True,
            text=True,
        )

    edge_delta = EdgeDelta(
        new_edges=new_edges - old_edges,
        removed_edges=old_edges - new_edges,
    )

    cycles = find_cycles_in_new_edges(edge_delta.new_edges, new_edges)

    summary = build_summary(
        new_ref,
        old_ref,
        len(new_edges),
        new_cross,
        len(old_edges),
        old_cross,
        module_types,
        edge_delta,
        cycles,
    )
    print(f"\n{summary}", file=sys.stderr)

    mermaid = render_mermaid(module_types, rename_labels, edge_delta, cycles)
    md_text = f"```mermaid\n{mermaid}\n```\n"

    if output:
        Path(output).write_text(md_text)
        print(f"\nWritten to {output}", file=sys.stderr)

        html_path = Path(output).with_suffix(".html")
        html_path.write_text(render_html(mermaid, summary))
        print(f"Open in browser: {html_path}", file=sys.stderr)
    else:
        print()
        print(md_text)

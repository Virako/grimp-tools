"""Shared grimp graph building and edge extraction."""

from collections import defaultdict

import grimp


def build_graph(packages: list[str]) -> grimp.ImportGraph:
    """Build a grimp ImportGraph for the given packages."""
    return grimp.build_graph(
        packages[0],
        *packages[1:],
        exclude_type_checking_imports=True,
    )


def build_edge_set(
    graph: grimp.ImportGraph,
    root_packages: set[str],
    skip: set[str],
) -> set[tuple[str, str]]:
    """Extract all direct import edges, filtering skipped and external modules."""
    edges: set[tuple[str, str]] = set()
    for module in graph.modules:
        parts = module.split(".")
        if any(p in skip for p in parts):
            continue
        if parts[0] not in root_packages:
            continue
        for imported in graph.find_modules_directly_imported_by(module):
            iparts = imported.split(".")
            if any(p in skip for p in iparts):
                continue
            if iparts[0] not in root_packages:
                continue
            edges.add((module, imported))
    return edges


def compute_metrics(edges: set[tuple[str, str]]) -> dict[str, int]:
    """Compute summary metrics from a set of edges."""
    cross_app = sum(1 for src, dst in edges if src.split(".")[0] != dst.split(".")[0])
    modules = {m for edge in edges for m in edge}
    return {
        "edges": len(edges),
        "cross_app_edges": cross_app,
        "modules": len(modules),
    }


def find_cycles(adj: dict[str, list[str]]) -> list[list[str]]:
    """Find all elementary cycles using DFS."""
    visited: set[str] = set()
    in_stack: set[str] = set()
    cycles: list[list[str]] = []

    def dfs(node: str, path: list[str]) -> None:
        visited.add(node)
        in_stack.add(node)
        for neighbor in adj.get(node, []):
            if neighbor in in_stack:
                idx = path.index(neighbor)
                cycles.append(path[idx:] + [neighbor])
            elif neighbor not in visited:
                dfs(neighbor, [*path, neighbor])
        in_stack.remove(node)

    for node in sorted(adj):
        if node not in visited:
            dfs(node, [node])
    return cycles


def aggregate_apps(
    edges: set[tuple[str, str]],
) -> tuple[dict[tuple[str, str], int], dict[str, list[str]]]:
    """Aggregate edges at the app level (first component of module name)."""
    app_edges: dict[tuple[str, str], int] = defaultdict(int)
    for src, dst in edges:
        src_app = src.split(".")[0]
        dst_app = dst.split(".")[0]
        if src_app != dst_app:
            app_edges[(src_app, dst_app)] += 1

    app_adj: dict[str, list[str]] = defaultdict(list)
    for src_app, dst_app in app_edges:
        app_adj[src_app].append(dst_app)

    return dict(app_edges), dict(app_adj)


def build_graph_stats(
    edges: set[tuple[str, str]],
) -> tuple[set[str], dict[str, int], dict[str, int], dict[str, list[str]]]:
    """Build node set, in/out degree dicts, and adjacency list."""
    nodes: set[str] = set()
    in_deg: dict[str, int] = defaultdict(int)
    out_deg: dict[str, int] = defaultdict(int)
    adj: dict[str, list[str]] = defaultdict(list)
    for src, dst in edges:
        nodes.add(src)
        nodes.add(dst)
        out_deg[src] += 1
        in_deg[dst] += 1
        adj[src].append(dst)
    return nodes, dict(in_deg), dict(out_deg), dict(adj)

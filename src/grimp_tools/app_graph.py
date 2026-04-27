"""Generate a doughnut graph for a single app: detailed internal edges
plus aggregated cross-app counts."""

import sys
from collections import defaultdict
from pathlib import Path

from grimp_tools.config import get_skip_modules, load_root_packages
from grimp_tools.graph import build_graph
from grimp_tools.html import render_page


def _module_id(module: str) -> str:
    """Mermaid/DOT-safe identifier derived from a dotted module path."""
    return module.replace(".", "_")


def _module_label(module: str, app: str, strip_prefix: bool) -> str:
    """Display label for a module node."""
    if strip_prefix and module.startswith(f"{app}."):
        return module[len(app) + 1 :]
    return module


def _internal_nodes(edges: set[tuple[str, str]]) -> list[str]:
    """Return sorted list of unique modules participating in internal edges."""
    nodes: set[str] = set()
    for src, dst in edges:
        nodes.add(src)
        nodes.add(dst)
    return sorted(nodes)


def _collect_edges(
    graph, app: str, packages: set[str], skip: set[str]
) -> tuple[set[tuple[str, str]], dict[str, int], dict[str, int]]:
    """Return (internal_edges, external_in, external_out)."""
    internal_edges: set[tuple[str, str]] = set()
    external_in: dict[str, int] = defaultdict(int)
    external_out: dict[str, int] = defaultdict(int)

    for src in graph.modules:
        sparts = src.split(".")
        if any(p in skip for p in sparts):
            continue
        src_app = sparts[0]
        if src_app not in packages:
            continue
        for tgt in graph.find_modules_directly_imported_by(src):
            tparts = tgt.split(".")
            if any(p in skip for p in tparts):
                continue
            tgt_app = tparts[0]
            if tgt_app not in packages:
                continue
            if src_app == app and tgt_app == app:
                internal_edges.add((src, tgt))
            elif src_app == app and tgt_app != app:
                external_out[tgt_app] += 1
            elif src_app != app and tgt_app == app:
                external_in[src_app] += 1

    return internal_edges, dict(external_in), dict(external_out)


def _apply_top(
    external_in: dict[str, int], external_out: dict[str, int], top: int
) -> tuple[dict[str, int], dict[str, int]]:
    """Keep only the top-N external apps by total edges (in + out)."""
    combined: dict[str, int] = defaultdict(int)
    for name, n in external_in.items():
        combined[name] += n
    for name, n in external_out.items():
        combined[name] += n
    top_apps = sorted(combined, key=lambda a: (-combined[a], a))[:top]
    top_set = set(top_apps)
    return (
        {a: n for a, n in external_in.items() if a in top_set},
        {a: n for a, n in external_out.items() if a in top_set},
    )


def _render_mermaid(
    app: str,
    internal: set[tuple[str, str]],
    ext_in: dict[str, int],
    ext_out: dict[str, int],
    strip_prefix: bool = True,
) -> str:
    """Mermaid render: when an internal subgraph exists, its id is `<app>`,
    so cross-app edges (`<other> --> <app>`, `<app> --> <other>`) attach to
    the subgraph border instead of materialising a separate bare node."""
    lines: list[str] = ["graph LR"]

    if internal:
        lines.append(f'  subgraph {app} ["{app} (focal app)"]')
        for mod in _internal_nodes(internal):
            lines.append(
                f'    {_module_id(mod)}["{_module_label(mod, app, strip_prefix)}"]'
            )
        lines.append("")
        for src, dst in sorted(internal):
            lines.append(f"    {_module_id(src)} --> {_module_id(dst)}")
        lines.append("  end")

    if ext_in or ext_out:
        if internal:
            lines.append("")
        for other in sorted(ext_in):
            lines.append(f"  {other} -.->|{ext_in[other]}| {app}")
        for other in sorted(ext_out):
            lines.append(f"  {app} -.->|{ext_out[other]}| {other}")

    return "\n".join(lines)


def _render_dot(
    app: str,
    internal: set[tuple[str, str]],
    ext_in: dict[str, int],
    ext_out: dict[str, int],
    strip_prefix: bool = True,
) -> str:
    """DOT render: when the focal cluster is present, declare `compound=true`,
    emit an invisible anchor inside it, and route cross-app edges through the
    anchor with `lhead`/`ltail` so the arrowheads land on the cluster border."""
    lines: list[str] = [f"digraph {app} {{", "  rankdir=LR;"]
    if internal:
        lines.append("  compound=true;")
    lines.append("")

    anchor = f"{app}_anchor"
    cluster = f"cluster_{app}"

    if internal:
        lines.append(f"  subgraph {cluster} {{")
        lines.append(f'    label="{app} (focal app)";')
        lines.append("    style=rounded;")
        lines.append("")
        lines.append(f"    {anchor} [shape=point, style=invis, width=0, height=0];")
        for mod in _internal_nodes(internal):
            label = _module_label(mod, app, strip_prefix)
            lines.append(f'    "{mod}" [label="{label}"];')
        lines.append("")
        for src, dst in sorted(internal):
            lines.append(f'    "{src}" -> "{dst}";')
        lines.append("  }")

    if ext_in or ext_out:
        if internal:
            lines.append("")
            for other in sorted(ext_in):
                lines.append(
                    f'  "{other}" -> {anchor} '
                    f'[lhead={cluster}, label="{ext_in[other]}", style=dashed];'
                )
            for other in sorted(ext_out):
                lines.append(
                    f'  {anchor} -> "{other}" '
                    f'[ltail={cluster}, label="{ext_out[other]}", style=dashed];'
                )
        else:
            for other in sorted(ext_in):
                lines.append(
                    f'  "{other}" -> "{app}" [label="{ext_in[other]}", style=dashed];'
                )
            for other in sorted(ext_out):
                lines.append(
                    f'  "{app}" -> "{other}" [label="{ext_out[other]}", style=dashed];'
                )

    lines.append("}")
    return "\n".join(lines)


def build_summary(
    app: str,
    internal: set[tuple[str, str]],
    ext_in: dict[str, int],
    ext_out: dict[str, int],
) -> str:
    """Plain-text summary of the doughnut graph."""
    modules = len({m for edge in internal for m in edge})
    in_total = sum(ext_in.values())
    out_total = sum(ext_out.values())

    lines = [
        f"App: {app}",
        f"Internal: {modules} modules, {len(internal)} edges",
        f"Cross-app: {in_total} inbound from {len(ext_in)} apps, "
        f"{out_total} outbound to {len(ext_out)} apps",
    ]
    if ext_in:
        lines.append("")
        lines.append("Inbound:")
        for other in sorted(ext_in, key=lambda a: (-ext_in[a], a)):
            lines.append(f"  {other} -> {app}: {ext_in[other]}")
    if ext_out:
        lines.append("")
        lines.append("Outbound:")
        for other in sorted(ext_out, key=lambda a: (-ext_out[a], a)):
            lines.append(f"  {app} -> {other}: {ext_out[other]}")
    return "\n".join(lines)


_EXTRA_CSS = """
  .edge-internal { background: #1565c0; }
  .edge-external { background: repeating-linear-gradient(90deg, #555 0 4px, transparent 4px 8px); }
  #summary { padding: 12px 20px; font-size: 13px; color: #333;
              border-bottom: 1px solid #eee; white-space: pre-wrap; }
  .mermaid { padding: 16px 20px; }
"""


def render_html(app: str, mermaid_code: str, summary: str) -> str:
    """Render standalone HTML embedding the mermaid graph and a summary."""
    summary_html = summary.replace("\n", "<br>")
    body = f"""<div class="toolbar">
  <div class="legend">
    <span><span class="edge-sample edge-internal"></span> Internal edge (module &rarr; module)</span>
    <span><span class="edge-sample edge-external"></span> Cross-app edge (count)</span>
  </div>
</div>
<div id="summary">{summary_html}</div>
<pre class="mermaid">{mermaid_code}</pre>"""
    return render_page(
        title=f"app-graph: {app}",
        body=body,
        extra_css=_EXTRA_CSS,
    )


def run(args) -> None:
    """Entry point for the app-graph subcommand."""
    packages = load_root_packages()
    extra_pkgs_raw = getattr(args, "extra_packages", "") or ""
    extras = [p.strip() for p in extra_pkgs_raw.split(",") if p.strip()]
    if extras:
        packages = sorted(set(packages) | set(extras))

    if args.app not in packages:
        sys.exit(
            f"App '{args.app}' not in root_packages. "
            f"Available: {', '.join(sorted(packages))}. "
            f"If '{args.app}' is a Django app missing from "
            f"[tool.importlinter].root_packages, pass --extra-packages {args.app}."
        )

    skip = get_skip_modules()
    extra_exclude = getattr(args, "exclude", "") or ""
    skip |= {p.strip() for p in extra_exclude.split(",") if p.strip()}
    graph = build_graph(packages)

    internal_edges, external_in, external_out = _collect_edges(
        graph, args.app, set(packages), skip
    )

    if args.top:
        external_in, external_out = _apply_top(external_in, external_out, args.top)

    internal = set() if args.no_internal else internal_edges
    ext_in = {} if args.no_external else external_in
    ext_out = {} if args.no_external else external_out

    if args.format == "mermaid":
        output = _render_mermaid(
            args.app, internal, ext_in, ext_out, strip_prefix=args.strip_prefix
        )
    else:
        output = _render_dot(
            args.app, internal, ext_in, ext_out, strip_prefix=args.strip_prefix
        )

    summary = build_summary(args.app, internal, ext_in, ext_out)
    print(summary, file=sys.stderr)

    if args.output:
        out_path = Path(args.output)
        out_path.write_text(output)
        print(f"Written to {out_path}", file=sys.stderr)

        if args.format == "mermaid":
            html_path = out_path.with_suffix(".html")
            html_path.write_text(render_html(args.app, output, summary))
            print(f"Open in browser: {html_path}", file=sys.stderr)
    else:
        print(output)

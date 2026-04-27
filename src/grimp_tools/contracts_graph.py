"""Generate Mermaid graphs visualizing import-linter contracts."""

import sys
from collections import defaultdict
from pathlib import Path

from grimp_tools.config import load_root_packages
from grimp_tools.html import render_page

# --- Mermaid styling constants ---

ALLOWED_COLOR = "#2e7d32"
FORBIDDEN_COLOR = "#c62828"
PRIMARY_FILL = "fill:#e3f2fd,stroke:#1565c0"
ALLOWED_FILL = "fill:#c8e6c9,stroke:#2e7d32"
FORBIDDEN_FILL = "fill:#ffcdd2,stroke:#c62828"
NEUTRAL_FILL = "fill:#fff9c4,stroke:#f9a825"
DEBT_NODE_STYLE = "fill:#ffcdd2,stroke:#c62828,stroke-width:1px"


def _link_allowed(idx: int) -> str:
    return f"    linkStyle {idx} stroke:{ALLOWED_COLOR},stroke-width:2px"


def _link_forbidden(idx: int, width: int = 2) -> str:
    return f"    linkStyle {idx} stroke:{FORBIDDEN_COLOR},stroke-width:{width}px"


def _style_node(node_id: str, fill: str) -> str:
    return f"    style {node_id} {fill}"


# --- Helpers ---


def _parse_edge(edge: str) -> tuple[str, str]:
    parts = edge.split(" -> ")
    return parts[0].strip(), parts[1].strip()


def _is_wildcard(mod: str) -> bool:
    return "*" in mod


def _split_ignores(ignores: list[str]) -> tuple[list[str], list[tuple[str, str]]]:
    """Split ignores into valid wildcards and debt (specific violations)."""
    valid: list[str] = []
    debt: list[tuple[str, str]] = []
    for ig in ignores:
        if ig.startswith("#"):
            continue
        if _is_wildcard(ig):
            valid.append(ig)
        else:
            debt.append(_parse_edge(ig))
    return valid, debt


def _is_app_isolation(contract: dict, root_packages: set[str]) -> bool:
    """Check if this is an app-level isolation contract (e.g. core vs business).

    True when both source and forbidden are concrete app names (no wildcards).
    Wildcard patterns like *.models indicate layer-level rules, not app isolation.
    """
    sources = contract.get("source_modules", [])
    forbidden = contract.get("forbidden_modules", [])
    if not sources or not forbidden:
        return False
    all_concrete = all(not _is_wildcard(m) for m in sources + forbidden)
    if not all_concrete:
        return False
    return any(m in root_packages for m in sources)


# --- Rule renderers per contract type ---


def render_rule_shared(contract: dict) -> str:
    """Core apps must not import business apps."""
    core = contract.get("source_modules", [])
    forbidden = contract.get("forbidden_modules", [])

    lines = ["graph LR"]
    lines.append('    subgraph core["CORE"]')
    lines.append("        direction LR")
    for app in sorted(core):
        lines.append(f'        c_{app}["{app}"]')
    lines.append("    end")
    lines.append("")
    lines.append('    subgraph business["BUSINESS"]')
    lines.append("        direction LR")
    for app in sorted(forbidden):
        lines.append(f'        b_{app}["{app}"]')
    lines.append("    end")
    lines.append("")
    lines.append("    business -- can import --> core")
    lines.append("    core -.-x business")
    lines.append("")
    lines.append(_link_allowed(0))
    lines.append(_link_forbidden(1))
    lines.append(_style_node("core", ALLOWED_FILL))
    lines.append(_style_node("business", NEUTRAL_FILL))
    return "\n".join(lines)


def render_rule_forbidden(contract: dict, valid_patterns: list[str]) -> str:
    """Forbidden contract: source cannot import forbidden, with valid exceptions."""
    sources = contract.get("source_modules", [])
    forbidden = contract.get("forbidden_modules", [])

    lines = ["graph TD"]
    lines.append('    subgraph rule["Rule"]')
    lines.append("        direction TB")

    src_label = " / ".join(s.replace("*.", "") for s in sources)
    lines.append(f'        src["{src_label}"]')

    for i, vp in enumerate(valid_patterns):
        _, dst = _parse_edge(vp)
        lines.append(f'        v{i}["{dst.replace("*.", "")}"]')

    for i, f in enumerate(forbidden):
        lines.append(f'        f{i}["{f.replace("*.", "")}"]')

    lines.append("    end")
    lines.append("")

    link_idx = 0
    style_lines = []

    for i in range(len(valid_patterns)):
        lines.append(f"    src -- can import --> v{i}")
        style_lines.append(_link_allowed(link_idx))
        link_idx += 1

    for i in range(len(forbidden)):
        lines.append(f"    src -.-x f{i}")
        style_lines.append(_link_forbidden(link_idx))
        link_idx += 1

    lines.append("")
    lines.extend(style_lines)

    for i in range(len(valid_patterns)):
        lines.append(_style_node(f"v{i}", ALLOWED_FILL))
    for i in range(len(forbidden)):
        lines.append(_style_node(f"f{i}", FORBIDDEN_FILL))
    lines.append(_style_node("src", PRIMARY_FILL))

    return "\n".join(lines)


def render_rule_external(contract: dict, valid_patterns: list[str]) -> str:
    """External libs: which layers can/cannot use external packages."""
    sources = contract.get("source_modules", [])
    forbidden = contract.get("forbidden_modules", [])

    lines = ["graph LR"]
    lines.append('    subgraph internal["Internal Layers"]')
    lines.append("        direction TB")
    for i, s in enumerate(sources):
        lines.append(f'        s{i}["{s.replace("*.", "")}"]')
    lines.append("    end")
    lines.append("")
    lines.append('    subgraph external["External Libs"]')
    lines.append("        direction TB")
    for i, f in enumerate(forbidden):
        lines.append(f'        ext{i}["{f}"]')
    lines.append("    end")
    lines.append("")

    link_idx = 0
    style_lines = []

    for i in range(len(sources)):
        for j in range(len(forbidden)):
            lines.append(f"    s{i} -.-x ext{j}")
            style_lines.append(_link_forbidden(link_idx, width=1))
            link_idx += 1

    for vp in valid_patterns:
        src, dst = _parse_edge(vp)
        src_label = src.replace("*.", "")
        lines.append(
            f'    vp_{src_label}["{src_label}"] -- allowed --> ext_valid["{dst}"]'
        )
        style_lines.append(_link_allowed(link_idx))
        lines.append(_style_node(f"vp_{src_label}", ALLOWED_FILL))
        link_idx += 1

    lines.append("")
    lines.extend(style_lines)
    lines.append(_style_node("internal", PRIMARY_FILL))
    lines.append(_style_node("external", FORBIDDEN_FILL))

    return "\n".join(lines)


def render_rule_acyclic(valid_patterns: list[str]) -> str:
    """Acyclic: no dependency cycles between apps."""
    lines = ["graph LR"]
    lines.append('    A["app A"] --> B["app B"] --> C["app C"]')
    lines.append("    C -.-x A")
    lines.append("")
    lines.append(_link_allowed(0))
    lines.append(_link_allowed(1))
    lines.append(_link_forbidden(2))

    if valid_patterns:
        lines.append("")
        for vp in valid_patterns:
            src, dst = _parse_edge(vp)
            lines.append(f"    %% Exception: {src} -> {dst}")

    return "\n".join(lines)


def render_rule_layers(contract: dict) -> str:
    """Layers contract: render the layer hierarchy as a vertical flow."""
    layers = contract.get("layers", [])
    containers = contract.get("containers", [])

    lines = ["graph TD"]

    for i, layer_str in enumerate(layers):
        is_independent = "|" in layer_str
        sep = "|" if is_independent else ":"
        parts = [p.strip().strip("()") for p in layer_str.split(sep)]
        label = " | ".join(parts) if is_independent else " : ".join(parts)
        lines.append(f'    L{i}["{label}"]')

    lines.append("")

    link_idx = 0
    for i in range(len(layers) - 1):
        lines.append(f"    L{i} --> L{i + 1}")
        link_idx += 1

    lines.append("")

    for i in range(len(layers)):
        if i == 0:
            fill = PRIMARY_FILL
        elif i == len(layers) - 1:
            fill = ALLOWED_FILL
        else:
            fill = NEUTRAL_FILL
        lines.append(_style_node(f"L{i}", fill))

    for i in range(link_idx):
        lines.append(_link_allowed(i))

    if containers:
        lines.append(f"    %% Applied to {len(containers)} containers (apps)")

    return "\n".join(lines)


MAX_DEBT_EDGES = 30


def render_debt_mermaid(debt: list[tuple[str, str]]) -> str | None:
    """Render violations for a contract.

    When there are too many edges, aggregates at the app level
    with edge labels showing the count.
    """
    if not debt:
        return None

    if len(debt) > MAX_DEBT_EDGES:
        return _render_debt_aggregated(debt)
    return _render_debt_detailed(debt)


def _render_debt_detailed(debt: list[tuple[str, str]]) -> str:
    """Render each violation as an individual edge."""
    lines = ["graph LR"]

    all_nodes: set[str] = set()
    for src, dst in debt:
        all_nodes.add(src)
        all_nodes.add(dst)

    node_id = {mod: f"n{i}" for i, mod in enumerate(sorted(all_nodes))}

    apps: dict[str, list[str]] = defaultdict(list)
    for mod in sorted(all_nodes):
        apps[mod.split(".")[0]].append(mod)

    for app in sorted(apps):
        lines.append(f"    subgraph {app}")
        for mod in apps[app]:
            short = mod.split(".", 1)[1] if "." in mod else mod
            lines.append(f'        {node_id[mod]}["{short}"]')
        lines.append("    end")

    lines.append("")

    for src, dst in sorted(debt):
        lines.append(f"    {node_id[src]} -.-x {node_id[dst]}")

    lines.append("")
    for i in range(len(debt)):
        lines.append(_link_forbidden(i))
    for mod in sorted(all_nodes):
        lines.append(_style_node(node_id[mod], DEBT_NODE_STYLE))

    return "\n".join(lines)


def _render_debt_aggregated(debt: list[tuple[str, str]]) -> str:
    """Render violations aggregated at app level with counts."""
    lines = ["graph LR"]

    app_edges: dict[tuple[str, str], int] = defaultdict(int)
    for src, dst in debt:
        src_app = src.split(".")[0]
        dst_app = dst.split(".")[0]
        app_edges[(src_app, dst_app)] += 1

    all_apps = sorted({a for pair in app_edges for a in pair})
    node_id = {app: f"a{i}" for i, app in enumerate(all_apps)}

    for app in all_apps:
        lines.append(f'    {node_id[app]}["{app}"]')

    lines.append("")

    link_idx = 0
    for (src_app, dst_app), count in sorted(app_edges.items()):
        lines.append(f"    {node_id[src_app]} -.-x|{count}| {node_id[dst_app]}")
        link_idx += 1

    lines.append("")
    for i in range(link_idx):
        lines.append(_link_forbidden(i))
    for app in all_apps:
        lines.append(_style_node(node_id[app], DEBT_NODE_STYLE))

    return "\n".join(lines)


# --- Renderer dispatch ---


def _select_renderer(
    contract: dict, root_packages: set[str], valid_patterns: list[str]
) -> str:
    """Select and call the appropriate renderer based on contract type."""
    ctype = contract.get("type", "")

    if ctype == "acyclic_siblings":
        return render_rule_acyclic(valid_patterns)
    if ctype == "layers":
        return render_rule_layers(contract)
    if ctype == "independence":
        return render_rule_acyclic(valid_patterns)
    if ctype == "forbidden":
        if _is_app_isolation(contract, root_packages):
            return render_rule_shared(contract)
        return render_rule_external(contract, valid_patterns)
    return render_rule_forbidden(contract, valid_patterns)


# --- HTML output ---


_EXTRA_CSS = f"""
  .edge-allowed {{ background: {ALLOWED_COLOR}; }}
  .edge-debt {{ background: repeating-linear-gradient(90deg, {FORBIDDEN_COLOR} 0 4px, transparent 4px 8px); }}
  .section {{ padding: 16px 20px; border-bottom: 1px solid #eee; }}
  .section h3 {{ margin: 0 0 12px; font-size: 15px; color: #333; }}
  .text-block {{ font-size: 13px; color: #666; padding: 4px 0; }}
"""


def render_html(sections: list[tuple[str, str]]) -> str:
    """Render HTML with multiple sections (pairs of heading + mermaid)."""
    body_parts = [
        """<div class="toolbar">
  <div class="legend">
    <span><span class="edge-sample edge-allowed"></span> Allowed</span>
    <span><span class="edge-sample edge-debt"></span> Forbidden / Debt</span>
  </div>
</div>"""
    ]
    for title, content in sections:
        if content.startswith("graph ") or content.startswith("flowchart "):
            body_parts.append(
                f"""<div class="section">
  <h3>{title}</h3>
  <pre class="mermaid">{content}</pre>
</div>"""
            )
        else:
            body_parts.append(
                f"""<div class="section">
  <div class="text-block">{title}: {content}</div>
</div>"""
            )

    return render_page(
        title="Architectural Contracts",
        body="\n".join(body_parts),
        extra_css=_EXTRA_CSS,
    )


# --- Entry point ---


def run(output: str | None = None) -> None:
    """Entry point for the contracts-graph subcommand."""
    root_packages_list = load_root_packages()
    root_packages = set(root_packages_list)

    import tomllib

    with open("pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    contracts = data["tool"]["importlinter"].get("contracts", [])

    sections: list[tuple[str, str]] = []
    md_parts: list[str] = []

    for contract in contracts:
        name = contract.get("name", contract.get("id", "?"))
        ctype = contract.get("type", "?")
        ignores = contract.get("ignore_imports", [])
        valid_patterns, debt = _split_ignores(ignores)

        if ctype == "coupling_metrics":
            continue

        rule_mermaid = _select_renderer(contract, root_packages, valid_patterns)
        sections.append((f"Rule: {name}", rule_mermaid))
        md_parts.append(f"## Rule: {name}\n\n```mermaid\n{rule_mermaid}\n```\n")

        if debt:
            debt_mermaid = render_debt_mermaid(debt)
            if debt_mermaid:
                sections.append((f"Violations: {name} ({len(debt)})", debt_mermaid))
                md_parts.append(
                    f"### Violations ({len(debt)})\n\n```mermaid\n{debt_mermaid}\n```\n"
                )
        else:
            sections.append((f"Violations: {name}", "Clean - no violations"))
            md_parts.append("### Violations\n\nClean - no violations\n")

    total_debt = sum(
        len(_split_ignores(c.get("ignore_imports", []))[1]) for c in contracts
    )
    print(f"Total debt: {total_debt} ignore_imports to fix", file=sys.stderr)

    if output:
        Path(output).write_text("\n".join(md_parts))
        print(f"Written to {output}", file=sys.stderr)

        html_path = Path(output).replace(Path(output).with_suffix(".html"))
        html_path.write_text(render_html(sections))
        print(f"Open in browser: {html_path}", file=sys.stderr)
    else:
        print("\n".join(md_parts))

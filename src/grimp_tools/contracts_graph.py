"""Generate Mermaid graphs visualizing import-linter contracts."""

import sys
from collections import defaultdict
from pathlib import Path

from grimp_tools.config import load_root_packages


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


def _is_internal_forbidden(contract: dict, root_packages: set[str]) -> bool:
    """Check if forbidden_modules are internal (root packages) vs external."""
    forbidden = contract.get("forbidden_modules", [])
    for mod in forbidden:
        clean = mod.replace("*.", "").split(".")[0]
        if clean in root_packages:
            return True
    return False


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
    lines.append("    linkStyle 0 stroke:#2e7d32,stroke-width:2px")
    lines.append("    linkStyle 1 stroke:#c62828,stroke-width:2px")
    lines.append("    style core fill:#c8e6c9,stroke:#2e7d32")
    lines.append("    style business fill:#fff9c4,stroke:#f9a825")
    return "\n".join(lines)


def render_rule_layers(contract: dict, valid_patterns: list[str]) -> str:
    """Layer isolation: source cannot import forbidden, with valid exceptions."""
    sources = contract.get("source_modules", [])
    forbidden = contract.get("forbidden_modules", [])

    lines = ["graph TD"]
    lines.append('    subgraph rule["Rule"]')
    lines.append("        direction TB")

    src_label = " / ".join(s.replace("*.", "") for s in sources)
    lines.append(f'        src["{src_label}"]')

    if valid_patterns:
        for i, vp in enumerate(valid_patterns):
            _, dst = _parse_edge(vp)
            dst_label = dst.replace("*.", "")
            lines.append(f'        v{i}["{dst_label}"]')

    for i, f in enumerate(forbidden):
        f_label = f.replace("*.", "")
        lines.append(f'        f{i}["{f_label}"]')

    lines.append("    end")
    lines.append("")

    link_idx = 0
    style_lines = []

    for i, vp in enumerate(valid_patterns):
        lines.append(f"    src -- can import --> v{i}")
        style_lines.append(f"    linkStyle {link_idx} stroke:#2e7d32,stroke-width:2px")
        link_idx += 1

    for i, f in enumerate(forbidden):
        lines.append(f"    src -.-x f{i}")
        style_lines.append(f"    linkStyle {link_idx} stroke:#c62828,stroke-width:2px")
        link_idx += 1

    lines.append("")
    lines.extend(style_lines)

    for i in range(len(valid_patterns)):
        lines.append(f"    style v{i} fill:#c8e6c9,stroke:#2e7d32")
    for i in range(len(forbidden)):
        lines.append(f"    style f{i} fill:#ffcdd2,stroke:#c62828")
    lines.append("    style src fill:#e3f2fd,stroke:#1565c0")

    return "\n".join(lines)


def render_rule_external(contract: dict, valid_patterns: list[str]) -> str:
    """External libs: which layers can/cannot use external packages."""
    sources = contract.get("source_modules", [])
    forbidden = contract.get("forbidden_modules", [])

    lines = ["graph LR"]
    lines.append('    subgraph internal["Internal Layers"]')
    lines.append("        direction TB")
    for i, s in enumerate(sources):
        label = s.replace("*.", "")
        lines.append(f'        s{i}["{label}"]')
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

    for i, s in enumerate(sources):
        for j, f in enumerate(forbidden):
            lines.append(f"    s{i} -.-x ext{j}")
            style_lines.append(
                f"    linkStyle {link_idx} stroke:#c62828,stroke-width:1px"
            )
            link_idx += 1

    for vp in valid_patterns:
        src, dst = _parse_edge(vp)
        src_label = src.replace("*.", "")
        lines.append(
            f'    vp_{src_label}["{src_label}"] -- allowed --> ext_valid["{dst}"]'
        )
        style_lines.append(f"    linkStyle {link_idx} stroke:#2e7d32,stroke-width:2px")
        lines.append(f"    style vp_{src_label} fill:#c8e6c9,stroke:#2e7d32")
        link_idx += 1

    lines.append("")
    lines.extend(style_lines)
    lines.append("    style internal fill:#e3f2fd,stroke:#1565c0")
    lines.append("    style external fill:#ffcdd2,stroke:#c62828")

    return "\n".join(lines)


def render_rule_cycles(contract: dict, valid_patterns: list[str]) -> str:
    """Acyclic: no dependency cycles between apps."""
    lines = ["graph LR"]
    lines.append('    A["app A"] --> B["app B"] --> C["app C"]')
    lines.append("    C -.-x A")
    lines.append("")
    lines.append("    linkStyle 0 stroke:#2e7d32,stroke-width:2px")
    lines.append("    linkStyle 1 stroke:#2e7d32,stroke-width:2px")
    lines.append("    linkStyle 2 stroke:#c62828,stroke-width:2px")

    if valid_patterns:
        lines.append("")
        for vp in valid_patterns:
            src, dst = _parse_edge(vp)
            lines.append(f"    %% Exception: {src} -> {dst}")

    return "\n".join(lines)


def render_debt_mermaid(debt: list[tuple[str, str]]) -> str | None:
    """Render violations for a contract."""
    if not debt:
        return None

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
        lines.append(f"    linkStyle {i} stroke:#c62828,stroke-width:2px")
    for mod in sorted(all_nodes):
        lines.append(
            f"    style {node_id[mod]} fill:#ffcdd2,stroke:#c62828,stroke-width:1px"
        )

    return "\n".join(lines)


def render_html(sections: list[tuple[str, str]]) -> str:
    """Render HTML with multiple sections (pairs of heading + mermaid)."""
    body = ""
    for title, content in sections:
        if content.startswith("graph ") or content.startswith("flowchart "):
            body += f"""
<div class="section">
  <h3>{title}</h3>
  <pre class="mermaid">{content}</pre>
</div>"""
        else:
            body += f"""
<div class="section">
  <div class="text-block">{title}: {content}</div>
</div>"""

    return f"""\
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Architectural Contracts</title>
<style>
  body {{ margin: 0; background: #fff; font-family: monospace; padding-bottom: 40px; }}
  .toolbar {{ display: flex; gap: 12px; align-items: center; padding: 12px 20px;
              border-bottom: 1px solid #ddd; flex-wrap: wrap; }}
  .legend {{ display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; }}
  .legend span {{ display: flex; align-items: center; gap: 4px; }}
  .edge-sample {{ display: inline-block; width: 40px; height: 2px; vertical-align: middle; }}
  .edge-allowed {{ background: #2e7d32; }}
  .edge-debt {{ background: repeating-linear-gradient(90deg, #c62828 0 4px, transparent 4px 8px); }}
  .section {{ padding: 16px 20px; border-bottom: 1px solid #eee; }}
  .section h3 {{ margin: 0 0 12px; font-size: 15px; color: #333; }}
  .text-block {{ font-size: 13px; color: #666; padding: 4px 0; }}
  .mermaid {{ overflow: auto; }}
</style>
</head>
<body>
<div class="toolbar">
  <div class="legend">
    <span><span class="edge-sample edge-allowed"></span> Allowed</span>
    <span><span class="edge-sample edge-debt"></span> Forbidden / Debt</span>
  </div>
</div>
{body}
<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>
<script>
  mermaid.initialize({{ startOnLoad: true, theme: 'default', securityLevel: 'loose' }});
</script>
</body>
</html>"""


def _select_renderer(
    contract: dict, root_packages: set[str], valid_patterns: list[str]
) -> str:
    """Select and call the appropriate renderer based on contract type."""
    ctype = contract.get("type", "")

    if ctype == "independence":
        return render_rule_cycles(contract, valid_patterns)
    if ctype == "layers":
        return render_rule_layers(contract, valid_patterns)
    if ctype == "forbidden":
        if _is_internal_forbidden(contract, root_packages):
            return render_rule_shared(contract)
        return render_rule_external(contract, valid_patterns)
    # Fallback for unknown types
    return render_rule_layers(contract, valid_patterns)


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

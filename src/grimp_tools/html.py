"""Shared HTML page template for commands that render mermaid graphs."""

from importlib.resources import files
from string import Template

MERMAID_CDN = (
    '<script src="https://cdn.jsdelivr.net/npm/mermaid@11/dist/mermaid.min.js"></script>'
)

DEFAULT_MERMAID_INIT = (
    "<script>"
    "mermaid.initialize({ startOnLoad: true, theme: 'default', securityLevel: 'loose' });"
    "</script>"
)

COMMON_CSS = """
  body { margin: 0; background: #fff; font-family: monospace; padding-bottom: 40px; }
  .toolbar { display: flex; gap: 12px; align-items: center; padding: 12px 20px;
              border-bottom: 1px solid #ddd; flex-wrap: wrap; }
  .legend { display: flex; gap: 16px; flex-wrap: wrap; font-size: 13px; }
  .legend span { display: flex; align-items: center; gap: 4px; }
  .legend .swatch { width: 14px; height: 14px; border-radius: 3px; display: inline-block; }
  .edge-sample { display: inline-block; width: 40px; height: 2px; vertical-align: middle; }
  button { padding: 6px 14px; cursor: pointer; font-size: 13px; border: 1px solid #ccc;
           border-radius: 4px; background: #f9f9f9; }
  button:hover { background: #eee; }
  .mermaid { overflow: auto; }
"""

_PAGE_TEMPLATE = Template(
    files("grimp_tools").joinpath("templates/page.html").read_text(encoding="utf-8")
)


def render_page(
    title: str,
    body: str,
    extra_css: str = "",
    scripts: str = DEFAULT_MERMAID_INIT,
) -> str:
    """Standalone HTML page wrapping `body` with shared CSS and the mermaid CDN.

    `extra_css` is appended to the shared stylesheet for command-specific rules.
    `scripts` is rendered after the mermaid CDN; defaults to auto-init for
    `<pre class="mermaid">` blocks. Pass a custom string to render manually
    (e.g. `mermaid.render(...)` plus interaction code).
    """
    return _PAGE_TEMPLATE.substitute(
        title=title,
        common_css=COMMON_CSS,
        extra_css=extra_css,
        body=body,
        mermaid_cdn=MERMAID_CDN,
        scripts=scripts,
    )

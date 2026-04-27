"""Tests for the shared HTML page template."""

from grimp_tools.html import COMMON_CSS, MERMAID_CDN, render_page


class TestRenderPage:
    def test_doctype_and_title(self) -> None:
        result = render_page(title="My Page", body="<p>hi</p>")
        assert result.startswith("<!DOCTYPE html>")
        assert "<title>My Page</title>" in result

    def test_includes_common_css(self) -> None:
        result = render_page(title="X", body="")
        assert COMMON_CSS.strip() in result

    def test_includes_mermaid_cdn(self) -> None:
        result = render_page(title="X", body="")
        assert MERMAID_CDN in result

    def test_default_init_script_present(self) -> None:
        result = render_page(title="X", body="")
        assert "mermaid.initialize" in result
        assert "startOnLoad: true" in result

    def test_extra_css_appended(self) -> None:
        result = render_page(
            title="X", body="", extra_css="  .custom { color: red; }"
        )
        assert ".custom { color: red; }" in result

    def test_body_inserted(self) -> None:
        result = render_page(title="X", body="<div id='content'>hello</div>")
        assert "<div id='content'>hello</div>" in result

    def test_custom_scripts_replace_default(self) -> None:
        result = render_page(
            title="X", body="", scripts="<script>console.log('custom')</script>"
        )
        assert "console.log('custom')" in result
        assert "startOnLoad" not in result

    def test_template_substitutes_all_placeholders(self) -> None:
        result = render_page(title="X", body="")
        assert "$title" not in result
        assert "$body" not in result
        assert "$common_css" not in result
        assert "$extra_css" not in result
        assert "$mermaid_cdn" not in result
        assert "$scripts" not in result

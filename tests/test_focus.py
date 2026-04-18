"""Tests for focus module (pure logic, no git/grimp needed)."""

from grimp_tools.focus import (
    ADDED,
    DELETED,
    MODIFIED,
    NEIGHBOR,
    RENAMED,
    EdgeDelta,
    file_to_module,
    find_cycles_in_new_edges,
    render_html,
    render_mermaid,
)


class TestEdgeDelta:
    def test_new_cross(self) -> None:
        delta = EdgeDelta(
            new_edges={("api.views", "game.models"), ("api.views", "api.models")}
        )
        assert delta.new_cross == 1
        assert delta.new_intra == 1

    def test_removed_cross(self) -> None:
        delta = EdgeDelta(removed_edges={("api.views", "game.models")})
        assert delta.removed_cross == 1
        assert delta.removed_intra == 0

    def test_cross_app_delta(self) -> None:
        delta = EdgeDelta(
            new_edges={("api.views", "game.models")},
            removed_edges={("game.views", "api.models")},
        )
        assert delta.cross_app_delta == 0

    def test_empty(self) -> None:
        delta = EdgeDelta()
        assert delta.new_cross == 0
        assert delta.new_intra == 0
        assert delta.removed_cross == 0
        assert delta.removed_intra == 0
        assert delta.cross_app_delta == 0


class TestFileToModule:
    def test_standard(self) -> None:
        assert file_to_module("api/views.py", {"api"}) == "api.views"

    def test_nested(self) -> None:
        assert file_to_module("api/sub/views.py", {"api"}) == "api.sub.views"

    def test_init(self) -> None:
        assert file_to_module("api/__init__.py", {"api"}) == "api"

    def test_external_package(self) -> None:
        assert file_to_module("django/views.py", {"api"}) is None

    def test_root_file(self) -> None:
        assert file_to_module("setup.py", {"api"}) is None


class TestFindCyclesInNewEdges:
    def test_no_new_edges(self) -> None:
        assert find_cycles_in_new_edges(set(), {("a", "b")}) == []

    def test_cycle_through_new_edge(self) -> None:
        new_edges = {("a", "b")}
        all_edges = {("a", "b"), ("b", "c"), ("c", "a")}
        cycles = find_cycles_in_new_edges(new_edges, all_edges)
        assert len(cycles) == 1

    def test_no_cycle_through_new_edge(self) -> None:
        new_edges = {("d", "e")}
        all_edges = {("a", "b"), ("b", "c"), ("d", "e")}
        cycles = find_cycles_in_new_edges(new_edges, all_edges)
        assert cycles == []

    def test_self_loop(self) -> None:
        new_edges = {("a", "a")}
        all_edges = {("a", "a")}
        cycles = find_cycles_in_new_edges(new_edges, all_edges)
        assert len(cycles) == 1


class TestRenderMermaid:
    def test_empty_graph(self) -> None:
        result = render_mermaid({}, {}, EdgeDelta(), [])
        assert "No dependency changes" in result

    def test_new_edges(self) -> None:
        module_types = {"api.views": ADDED, "api.models": NEIGHBOR}
        delta = EdgeDelta(new_edges={("api.views", "api.models")})
        result = render_mermaid(module_types, {}, delta, [])
        assert "graph TD" in result
        assert "+new" in result
        assert "subgraph api" in result

    def test_removed_edges(self) -> None:
        module_types = {"api.views": DELETED}
        delta = EdgeDelta(removed_edges={("api.views", "api.models")})
        result = render_mermaid(module_types, {}, delta, [])
        assert "-removed" in result

    def test_cross_app_edges_dashed(self) -> None:
        module_types = {"api.views": MODIFIED, "game.models": NEIGHBOR}
        delta = EdgeDelta(new_edges={("api.views", "game.models")})
        result = render_mermaid(module_types, {}, delta, [])
        assert "-." in result  # dashed edge for cross-app

    def test_renamed_module(self) -> None:
        module_types = {"api.services": RENAMED}
        rename_labels = {"api.services": "api.old_services"}
        delta = EdgeDelta(new_edges={("api.services", "api.models")})
        result = render_mermaid(module_types, rename_labels, delta, [])
        assert "old_services" in result

    def test_node_styles(self) -> None:
        module_types = {
            "api.views": ADDED,
            "api.models": MODIFIED,
            "api.old": DELETED,
        }
        delta = EdgeDelta(new_edges={("api.views", "api.models")})
        result = render_mermaid(module_types, {}, delta, [])
        assert "#c8e6c9" in result  # added style
        assert "#fff9c4" in result  # modified style
        assert "#ffcdd2" in result  # deleted style

    def test_cycle_edges_bold(self) -> None:
        module_types = {"a": ADDED, "b": NEIGHBOR}
        delta = EdgeDelta(new_edges={("a", "b")})
        cycles = [["a", "b", "a"]]
        result = render_mermaid(module_types, {}, delta, cycles)
        assert "stroke-width:3px" in result


class TestRenderHtml:
    def test_contains_structure(self) -> None:
        html = render_html("graph TD\n    A --> B", "Test summary")
        assert "<!DOCTYPE html>" in html
        assert "mermaid" in html
        assert "Test summary" in html
        assert "Download SVG" in html

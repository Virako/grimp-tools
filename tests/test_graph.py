"""Tests for graph utilities (no grimp dependency needed — test pure logic)."""

from grimp_tools.graph import (
    aggregate_apps,
    build_graph_stats,
    compute_metrics,
    find_cycles,
)


class TestFindCycles:
    def test_no_cycles(self) -> None:
        adj = {"a": ["b"], "b": ["c"]}
        assert find_cycles(adj) == []

    def test_simple_cycle(self) -> None:
        adj = {"a": ["b"], "b": ["a"]}
        cycles = find_cycles(adj)
        assert len(cycles) == 1
        assert cycles[0][0] == cycles[0][-1]  # cycle closes

    def test_self_loop(self) -> None:
        adj = {"a": ["a"]}
        cycles = find_cycles(adj)
        assert len(cycles) == 1

    def test_multiple_cycles(self) -> None:
        adj = {"a": ["b"], "b": ["c"], "c": ["a", "b"]}
        cycles = find_cycles(adj)
        assert len(cycles) >= 2


class TestComputeMetrics:
    def test_basic(self) -> None:
        edges = {("api.views", "api.models"), ("game.views", "api.models")}
        metrics = compute_metrics(edges)
        assert metrics["edges"] == 2
        assert metrics["cross_app_edges"] == 1
        assert metrics["modules"] == 3

    def test_empty(self) -> None:
        metrics = compute_metrics(set())
        assert metrics == {"edges": 0, "cross_app_edges": 0, "modules": 0}


class TestAggregateApps:
    def test_aggregation(self) -> None:
        edges = {
            ("api.views", "game.models"),
            ("api.serializers", "game.models"),
            ("game.views", "game.models"),  # same app — excluded
        }
        app_edges, app_adj = aggregate_apps(edges)
        assert app_edges[("api", "game")] == 2
        assert ("game", "game") not in app_edges
        assert "game" in app_adj["api"]

    def test_empty(self) -> None:
        app_edges, app_adj = aggregate_apps(set())
        assert app_edges == {}
        assert app_adj == {}


class TestBuildGraphStats:
    def test_degrees(self) -> None:
        edges = {("a", "b"), ("a", "c"), ("b", "c")}
        nodes, in_deg, out_deg, adj = build_graph_stats(edges)
        assert nodes == {"a", "b", "c"}
        assert out_deg["a"] == 2
        assert in_deg["c"] == 2
        assert in_deg.get("a", 0) == 0

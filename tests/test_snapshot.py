"""Tests for snapshot module."""

import json

from grimp_tools.snapshot import _load_snapshot, _print_diff


class TestLoadSnapshot:
    def test_loads_from_disk(self, tmp_path) -> None:
        snapshot = {
            "timestamp": "2025-01-01T00:00:00",
            "commit": "abc1234",
            "metrics": {"edges": 5, "cross_app_edges": 2, "modules": 4},
            "edges": ["api.views -> api.models", "game.views -> api.models"],
        }
        path = tmp_path / "snapshot.json"
        path.write_text(json.dumps(snapshot))
        result = _load_snapshot(None, path)
        assert result is not None
        assert result["commit"] == "abc1234"

    def test_returns_none_when_missing(self, tmp_path) -> None:
        result = _load_snapshot(None, tmp_path / "nonexistent.json")
        assert result is None


class TestPrintDiff:
    def test_no_changes(self, capsys) -> None:
        snapshot = {
            "metrics": {"edges": 2, "cross_app_edges": 1, "modules": 3},
            "edges": ["api.views -> api.models", "game.views -> api.models"],
        }
        current_edges = {
            ("api.views", "api.models"),
            ("game.views", "api.models"),
        }
        _print_diff(snapshot, current_edges, "test ref")
        output = capsys.readouterr().out
        assert "No changes" in output

    def test_added_edges(self, capsys) -> None:
        snapshot = {
            "metrics": {"edges": 1, "cross_app_edges": 0, "modules": 2},
            "edges": ["api.views -> api.models"],
        }
        current_edges = {
            ("api.views", "api.models"),
            ("game.views", "api.models"),
        }
        _print_diff(snapshot, current_edges, "test ref")
        output = capsys.readouterr().out
        assert "ADDED" in output
        assert "game.views -> api.models" in output

    def test_removed_edges(self, capsys) -> None:
        snapshot = {
            "metrics": {"edges": 2, "cross_app_edges": 1, "modules": 3},
            "edges": ["api.views -> api.models", "game.views -> api.models"],
        }
        current_edges = {("api.views", "api.models")}
        _print_diff(snapshot, current_edges, "test ref")
        output = capsys.readouterr().out
        assert "REMOVED" in output

    def test_metrics_delta(self, capsys) -> None:
        snapshot = {
            "metrics": {"edges": 1, "cross_app_edges": 0, "modules": 2},
            "edges": ["api.views -> api.models"],
        }
        current_edges = {
            ("api.views", "api.models"),
            ("api.views", "api.serializers"),
        }
        _print_diff(snapshot, current_edges, "test ref")
        output = capsys.readouterr().out
        assert "+1" in output

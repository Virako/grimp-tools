"""Tests for analyze module."""

from grimp_tools.analyze import _git_short_hash, analyze, save_history


class TestAnalyze:
    def test_no_cycles(self) -> None:
        edges = {("api.views", "api.models"), ("game.views", "game.models")}
        has_cycles, report = analyze(edges)
        assert has_cycles is False
        assert "No cycles found" in report
        assert "No cycles between apps" in report

    def test_module_cycle_detected(self) -> None:
        edges = {("api.views", "api.models"), ("api.models", "api.views")}
        has_cycles, report = analyze(edges)
        assert has_cycles is True
        assert "CYCLE:" in report

    def test_app_cycle_detected(self) -> None:
        edges = {("api.views", "game.models"), ("game.views", "api.models")}
        has_cycles, report = analyze(edges)
        assert has_cycles is True
        assert "APP CYCLES:" in report

    def test_report_contains_summary(self) -> None:
        edges = {("api.views", "api.models")}
        _, report = analyze(edges)
        assert "SUMMARY" in report
        assert "Modules: 2" in report
        assert "Edges: 1" in report

    def test_coupling_table(self) -> None:
        edges = {("api.views", "api.models"), ("api.serializers", "api.models")}
        _, report = analyze(edges)
        assert "COUPLING" in report
        assert "api.models" in report

    def test_app_dependencies(self) -> None:
        edges = {
            ("api.views", "game.models"),
            ("api.serializers", "game.models"),
        }
        _, report = analyze(edges)
        assert "api -> game (2 imports)" in report


class TestSaveHistory:
    def test_creates_file_and_appends(self, tmp_path) -> None:
        history_path = str(tmp_path / "subdir" / "history.log")
        save_history(history_path, "test report")
        content = (tmp_path / "subdir" / "history.log").read_text()
        assert "test report" in content
        assert "---" in content

    def test_appends_to_existing(self, tmp_path) -> None:
        history_file = tmp_path / "history.log"
        history_file.write_text("existing content\n")
        save_history(str(history_file), "new report")
        content = history_file.read_text()
        assert "existing content" in content
        assert "new report" in content


class TestGitShortHash:
    def test_returns_string(self) -> None:
        result = _git_short_hash()
        assert isinstance(result, str)
        assert len(result) > 0

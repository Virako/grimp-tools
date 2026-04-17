"""Tests for CouplingMetricsContract."""

from unittest.mock import MagicMock, patch


from grimp_tools.coupling_contract import CouplingMetricsContract, _check_threshold


class TestCheckThreshold:
    def test_none_expected_is_noop(self) -> None:
        errors: list[str] = []
        warnings: list[str] = []
        _check_threshold("x", 10, None, errors, warnings)
        assert errors == []
        assert warnings == []

    def test_increase_is_error(self) -> None:
        errors: list[str] = []
        warnings: list[str] = []
        _check_threshold("exact_edges", 50, 40, errors, warnings)
        assert len(errors) == 1
        assert "increased" in errors[0]

    def test_decrease_is_warning(self) -> None:
        errors: list[str] = []
        warnings: list[str] = []
        _check_threshold("exact_edges", 30, 40, errors, warnings)
        assert len(warnings) == 1
        assert "decreased" in warnings[0]

    def test_equal_is_ok(self) -> None:
        errors: list[str] = []
        warnings: list[str] = []
        _check_threshold("exact_edges", 40, 40, errors, warnings)
        assert errors == []
        assert warnings == []


def _make_graph(modules: list[str], imports: dict[str, list[str]]) -> MagicMock:
    graph = MagicMock()
    graph.modules = modules
    graph.find_modules_directly_imported_by = lambda m: imports.get(m, [])
    return graph


def _make_contract(
    skip_modules: str = "migrations",
    top_n: int = 30,
    exact_edges: int | None = None,
    exact_cross_app_edges: int | None = None,
) -> CouplingMetricsContract:
    contract = CouplingMetricsContract.__new__(CouplingMetricsContract)
    contract.skip_modules = skip_modules
    contract.top_n = top_n
    contract.exact_edges = exact_edges
    contract.exact_cross_app_edges = exact_cross_app_edges
    return contract


class TestCouplingMetricsContract:
    @patch(
        "grimp_tools.coupling_contract.load_root_packages", return_value=["api", "game"]
    )
    def test_check_kept_when_no_thresholds(self, mock_load: MagicMock) -> None:
        graph = _make_graph(
            ["api.views", "api.models", "game.views"],
            {"api.views": ["api.models"], "game.views": ["api.models"]},
        )
        contract = _make_contract()
        result = contract.check(graph, verbose=False)
        assert result.kept is True
        assert result.metadata["total_edges"] == 2

    @patch(
        "grimp_tools.coupling_contract.load_root_packages", return_value=["api", "game"]
    )
    def test_check_breaks_on_increase(self, mock_load: MagicMock) -> None:
        graph = _make_graph(
            ["api.views", "api.models", "game.views"],
            {"api.views": ["api.models"], "game.views": ["api.models"]},
        )
        contract = _make_contract(exact_edges=1)  # actual is 2 -> breaks
        result = contract.check(graph, verbose=False)
        assert result.kept is False
        assert any("increased" in e for e in result.metadata["errors"])

    @patch(
        "grimp_tools.coupling_contract.load_root_packages", return_value=["api", "game"]
    )
    def test_check_warns_on_decrease(self, mock_load: MagicMock) -> None:
        graph = _make_graph(
            ["api.views", "api.models"],
            {"api.views": ["api.models"]},
        )
        contract = _make_contract(exact_edges=5)  # actual is 1 -> warns
        result = contract.check(graph, verbose=False)
        assert result.kept is True
        assert len(result.warnings) > 0

    @patch(
        "grimp_tools.coupling_contract.load_root_packages", return_value=["api", "game"]
    )
    def test_skips_filtered_modules(self, mock_load: MagicMock) -> None:
        graph = _make_graph(
            ["api.views", "api.migrations.001", "api.models"],
            {"api.views": ["api.models", "api.migrations.001"]},
        )
        contract = _make_contract(skip_modules="migrations")
        result = contract.check(graph, verbose=False)
        assert result.metadata["total_edges"] == 1

    @patch(
        "grimp_tools.coupling_contract.load_root_packages", return_value=["api", "game"]
    )
    def test_cross_app_edges_counted(self, mock_load: MagicMock) -> None:
        graph = _make_graph(
            ["api.views", "game.models"],
            {"api.views": ["game.models"]},
        )
        contract = _make_contract()
        result = contract.check(graph, verbose=False)
        assert result.metadata["cross_app_edges"] == 1

    @patch("grimp_tools.coupling_contract.load_root_packages", return_value=["api"])
    def test_render_broken_contract(self, mock_load: MagicMock) -> None:
        graph = _make_graph(
            ["api.views", "api.models"],
            {"api.views": ["api.models"]},
        )
        contract = _make_contract(exact_edges=0)
        result = contract.check(graph, verbose=False)
        assert result.kept is False
        # Just ensure render doesn't raise
        contract.render_broken_contract(result)

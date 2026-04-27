"""Tests for app_graph module."""

from argparse import Namespace
from unittest.mock import MagicMock, patch

import pytest

from grimp_tools.app_graph import (
    _apply_top,
    _collect_edges,
    _internal_nodes,
    _module_id,
    _module_label,
    _render_dot,
    _render_mermaid,
    run,
)


def _make_graph(modules: list[str], imports: dict[str, list[str]]) -> MagicMock:
    graph = MagicMock()
    graph.modules = modules
    graph.find_modules_directly_imported_by = lambda m: imports.get(m, [])
    return graph


class TestModuleId:
    def test_simple(self) -> None:
        assert _module_id("contest.models") == "contest_models"

    def test_nested(self) -> None:
        assert _module_id("contest.services.report") == "contest_services_report"


class TestModuleLabel:
    def test_strip(self) -> None:
        assert _module_label("contest.models", "contest", strip_prefix=True) == "models"

    def test_no_strip(self) -> None:
        assert (
            _module_label("contest.models", "contest", strip_prefix=False)
            == "contest.models"
        )

    def test_nested_strip(self) -> None:
        assert (
            _module_label("contest.services.report", "contest", strip_prefix=True)
            == "services.report"
        )

    def test_other_app_unchanged(self) -> None:
        assert _module_label("videos.views", "contest", strip_prefix=True) == "videos.views"


class TestInternalNodes:
    def test_unique_sorted(self) -> None:
        edges = {("a.x", "a.y"), ("a.y", "a.z"), ("a.x", "a.z")}
        assert _internal_nodes(edges) == ["a.x", "a.y", "a.z"]

    def test_empty(self) -> None:
        assert _internal_nodes(set()) == []


class TestCollectEdges:
    def test_internal_only(self) -> None:
        graph = _make_graph(
            ["contest.views", "contest.models"],
            {"contest.views": ["contest.models"]},
        )
        internal, ext_in, ext_out = _collect_edges(
            graph, "contest", {"contest", "videos"}, set()
        )
        assert internal == {("contest.views", "contest.models")}
        assert ext_in == {}
        assert ext_out == {}

    def test_bidirectional_cross_app(self) -> None:
        graph = _make_graph(
            ["contest.views", "videos.models", "videos.views", "contest.models"],
            {
                "contest.views": ["videos.models"],
                "videos.views": ["contest.models"],
                "videos.models": [],
                "contest.models": [],
            },
        )
        internal, ext_in, ext_out = _collect_edges(
            graph, "contest", {"contest", "videos"}, set()
        )
        assert internal == set()
        assert ext_in == {"videos": 1}
        assert ext_out == {"videos": 1}

    def test_aggregates_external_counts(self) -> None:
        graph = _make_graph(
            [
                "contest.a",
                "contest.b",
                "videos.x",
                "videos.y",
                "horse.z",
            ],
            {
                "contest.a": ["videos.x", "videos.y"],
                "contest.b": ["videos.x"],
                "horse.z": ["contest.a"],
            },
        )
        _, ext_in, ext_out = _collect_edges(
            graph, "contest", {"contest", "videos", "horse"}, set()
        )
        assert ext_out == {"videos": 3}
        assert ext_in == {"horse": 1}

    def test_skip_modules_filters_both_sides(self) -> None:
        graph = _make_graph(
            [
                "contest.views",
                "contest.migrations.0001",
                "contest.models",
                "contest.admin",
            ],
            {
                "contest.views": ["contest.models", "contest.migrations.0001"],
                "contest.migrations.0001": ["contest.models"],
                "contest.admin": ["contest.models"],
            },
        )
        internal = _collect_edges(
            graph, "contest", {"contest"}, {"migrations", "admin"}
        )[0]
        assert internal == {("contest.views", "contest.models")}

    def test_external_libs_excluded(self) -> None:
        graph = _make_graph(
            ["contest.views", "django.db"],
            {"contest.views": ["django.db"]},
        )
        internal, ext_in, ext_out = _collect_edges(
            graph, "contest", {"contest"}, set()
        )
        assert internal == set()
        assert ext_in == {}
        assert ext_out == {}

    def test_non_focal_to_non_focal_ignored(self) -> None:
        graph = _make_graph(
            ["videos.views", "horse.models"],
            {"videos.views": ["horse.models"]},
        )
        internal, ext_in, ext_out = _collect_edges(
            graph, "contest", {"contest", "videos", "horse"}, set()
        )
        assert internal == set()
        assert ext_in == {}
        assert ext_out == {}


class TestApplyTop:
    def test_keeps_top_by_combined(self) -> None:
        ext_in = {"a": 5, "b": 1, "c": 2}
        ext_out = {"a": 0, "b": 0, "c": 1}
        new_in, new_out = _apply_top(ext_in, ext_out, top=2)
        assert set(new_in) == {"a", "c"}
        assert set(new_out) == {"a", "c"}

    def test_top_larger_than_pool(self) -> None:
        ext_in = {"a": 1}
        ext_out = {"b": 2}
        new_in, new_out = _apply_top(ext_in, ext_out, top=10)
        assert new_in == {"a": 1}
        assert new_out == {"b": 2}

    def test_deterministic_tiebreak(self) -> None:
        ext_in = {"alpha": 1, "beta": 1, "gamma": 1}
        ext_out: dict[str, int] = {}
        new_in, _ = _apply_top(ext_in, ext_out, top=2)
        assert set(new_in) == {"alpha", "beta"}


class TestRenderMermaid:
    def test_basic_structure(self) -> None:
        internal = {("contest.views", "contest.models")}
        ext_in = {"horse": 5}
        ext_out = {"videos": 2}
        result = _render_mermaid("contest", internal, ext_in, ext_out)
        assert "graph LR" in result
        assert 'subgraph contest ["contest (focal app)"]' in result
        assert 'contest_models["models"]' in result
        assert 'contest_views["views"]' in result
        assert "contest_views --> contest_models" in result
        assert "horse -.->|5| contest" in result
        assert "contest -.->|2| videos" in result
        assert "  end" in result

    def test_bidirectional_external_when_both_exist(self) -> None:
        internal = {("contest.views", "contest.models")}
        ext_in = {"videos": 3}
        ext_out = {"videos": 2}
        result = _render_mermaid("contest", internal, ext_in, ext_out)
        assert "videos -.->|3| contest" in result
        assert "contest -.->|2| videos" in result

    def test_unidirectional_external_only_one_line(self) -> None:
        internal: set[tuple[str, str]] = set()
        result = _render_mermaid("contest", internal, {}, {"videos": 2})
        assert "contest -.->|2| videos" in result
        assert "videos -.->" not in result

    def test_no_internal(self) -> None:
        result = _render_mermaid("contest", set(), {"horse": 1}, {})
        assert "subgraph" not in result
        assert "horse -.->|1| contest" in result

    def test_no_external(self) -> None:
        internal = {("contest.views", "contest.models")}
        result = _render_mermaid("contest", internal, {}, {})
        assert 'subgraph contest ["contest (focal app)"]' in result
        assert "-.->" not in result

    def test_strip_prefix_off(self) -> None:
        internal = {("contest.views", "contest.models")}
        result = _render_mermaid(
            "contest", internal, {}, {}, strip_prefix=False
        )
        assert 'contest_models["contest.models"]' in result
        assert 'contest_views["contest.views"]' in result

    def test_nested_module_id_and_label(self) -> None:
        internal = {("contest.services.report", "contest.models")}
        result = _render_mermaid("contest", internal, {}, {})
        assert "contest_services_report" in result
        assert '"services.report"' in result

    def test_empty(self) -> None:
        result = _render_mermaid("contest", set(), {}, {})
        assert result == "graph LR"


class TestRenderDot:
    def test_basic_structure_uses_compound_anchor(self) -> None:
        internal = {("contest.views", "contest.models")}
        ext_in = {"horse": 5}
        ext_out = {"videos": 2}
        result = _render_dot("contest", internal, ext_in, ext_out)
        assert result.startswith("digraph contest {")
        assert "rankdir=LR;" in result
        assert "compound=true;" in result
        assert "subgraph cluster_contest {" in result
        assert 'label="contest (focal app)";' in result
        assert "style=rounded;" in result
        assert "contest_anchor [shape=point, style=invis" in result
        assert '"contest.models" [label="models"];' in result
        assert '"contest.views" -> "contest.models";' in result
        assert (
            '"horse" -> contest_anchor [lhead=cluster_contest, label="5", style=dashed];'
            in result
        )
        assert (
            'contest_anchor -> "videos" [ltail=cluster_contest, label="2", style=dashed];'
            in result
        )
        assert result.endswith("}")

    def test_no_internal_uses_bare_node(self) -> None:
        result = _render_dot("contest", set(), {"horse": 1}, {})
        assert "cluster_contest" not in result
        assert "compound=true" not in result
        assert "contest_anchor" not in result
        assert '"horse" -> "contest" [label="1", style=dashed];' in result

    def test_no_external(self) -> None:
        internal = {("contest.views", "contest.models")}
        result = _render_dot("contest", internal, {}, {})
        assert "cluster_contest" in result
        assert "style=dashed" not in result

    def test_strip_prefix_off(self) -> None:
        internal = {("contest.views", "contest.models")}
        result = _render_dot("contest", internal, {}, {}, strip_prefix=False)
        assert '"contest.models" [label="contest.models"];' in result


class TestRunIntegration:
    def _args(self, **overrides) -> Namespace:
        defaults = dict(
            app="contest",
            output=None,
            format="mermaid",
            top=None,
            no_internal=False,
            no_external=False,
            strip_prefix=True,
            exclude="",
            extra_packages="",
        )
        defaults.update(overrides)
        return Namespace(**defaults)

    def test_app_not_in_root_packages(self) -> None:
        with patch("grimp_tools.app_graph.load_root_packages", return_value=["videos"]):
            with pytest.raises(SystemExit) as exc:
                run(self._args(app="contest"))
            msg = str(exc.value)
            assert "contest" in msg
            assert "videos" in msg
            assert "--extra-packages" in msg

    def test_extra_packages_extends_root_packages(self) -> None:
        graph = _make_graph(
            ["old.views", "old.models", "contest.foo"],
            {"old.views": ["old.models", "contest.foo"]},
        )
        with (
            patch(
                "grimp_tools.app_graph.load_root_packages", return_value=["contest"]
            ),
            patch("grimp_tools.app_graph.get_skip_modules", return_value=set()),
            patch("grimp_tools.app_graph.build_graph", return_value=graph),
        ):
            run(self._args(app="old", extra_packages="old"))
        # No SystemExit -> validation passed; the focal app 'old' was accepted.

    def test_writes_to_output_file(self, tmp_path) -> None:
        graph = _make_graph(
            ["contest.views", "contest.models"],
            {"contest.views": ["contest.models"]},
        )
        out = tmp_path / "out.md"
        with (
            patch(
                "grimp_tools.app_graph.load_root_packages", return_value=["contest"]
            ),
            patch("grimp_tools.app_graph.get_skip_modules", return_value=set()),
            patch("grimp_tools.app_graph.build_graph", return_value=graph),
        ):
            run(self._args(output=str(out)))
        content = out.read_text()
        assert "graph LR" in content
        assert "contest_views --> contest_models" in content

    def test_prints_to_stdout(self, capsys) -> None:
        graph = _make_graph(
            ["contest.views", "contest.models"],
            {"contest.views": ["contest.models"]},
        )
        with (
            patch(
                "grimp_tools.app_graph.load_root_packages", return_value=["contest"]
            ),
            patch("grimp_tools.app_graph.get_skip_modules", return_value=set()),
            patch("grimp_tools.app_graph.build_graph", return_value=graph),
        ):
            run(self._args())
        out = capsys.readouterr().out
        assert "graph LR" in out

    def test_top_filters_externals_by_total(self, capsys) -> None:
        # Each app imports contest with a different number of distinct modules:
        # app0 -> 1 edge, app1 -> 2 edges, ..., app4 -> 5 edges. Top-2 keeps app3, app4.
        modules: list[str] = ["contest.a"]
        imports: dict[str, list[str]] = {"contest.a": []}
        for i in range(5):
            for j in range(i + 1):
                src = f"app{i}.m{j}"
                modules.append(src)
                imports[src] = ["contest.a"]
        graph = _make_graph(modules, imports)
        packages = ["contest"] + [f"app{i}" for i in range(5)]
        with (
            patch("grimp_tools.app_graph.load_root_packages", return_value=packages),
            patch("grimp_tools.app_graph.get_skip_modules", return_value=set()),
            patch("grimp_tools.app_graph.build_graph", return_value=graph),
        ):
            run(self._args(top=2))
        out = capsys.readouterr().out
        assert "app3 -.->" in out
        assert "app4 -.->" in out
        assert "app0 -.->" not in out
        assert "app1 -.->" not in out
        assert "app2 -.->" not in out

    def test_format_dot(self, capsys) -> None:
        graph = _make_graph(
            ["contest.views", "contest.models"],
            {"contest.views": ["contest.models"]},
        )
        with (
            patch(
                "grimp_tools.app_graph.load_root_packages", return_value=["contest"]
            ),
            patch("grimp_tools.app_graph.get_skip_modules", return_value=set()),
            patch("grimp_tools.app_graph.build_graph", return_value=graph),
        ):
            run(self._args(format="dot"))
        out = capsys.readouterr().out
        assert "digraph contest {" in out
        assert "subgraph cluster_contest" in out

    def test_no_internal_flag(self, capsys) -> None:
        graph = _make_graph(
            ["contest.views", "contest.models", "videos.x"],
            {"contest.views": ["contest.models"], "videos.x": ["contest.models"]},
        )
        with (
            patch(
                "grimp_tools.app_graph.load_root_packages",
                return_value=["contest", "videos"],
            ),
            patch("grimp_tools.app_graph.get_skip_modules", return_value=set()),
            patch("grimp_tools.app_graph.build_graph", return_value=graph),
        ):
            run(self._args(no_internal=True))
        out = capsys.readouterr().out
        assert "subgraph" not in out
        assert "videos -.->|1| contest" in out

    def test_no_external_flag(self, capsys) -> None:
        graph = _make_graph(
            ["contest.views", "contest.models", "videos.x"],
            {"contest.views": ["contest.models"], "videos.x": ["contest.models"]},
        )
        with (
            patch(
                "grimp_tools.app_graph.load_root_packages",
                return_value=["contest", "videos"],
            ),
            patch("grimp_tools.app_graph.get_skip_modules", return_value=set()),
            patch("grimp_tools.app_graph.build_graph", return_value=graph),
        ):
            run(self._args(no_external=True))
        out = capsys.readouterr().out
        assert "subgraph" in out
        assert "-.->" not in out

    def test_exclude_flag_adds_to_skip(self, capsys) -> None:
        graph = _make_graph(
            [
                "contest.views",
                "contest.models",
                "contest.tests.test_views",
                "contest.factories",
            ],
            {
                "contest.views": ["contest.models"],
                "contest.tests.test_views": ["contest.views", "contest.factories"],
                "contest.factories": ["contest.models"],
            },
        )
        with (
            patch(
                "grimp_tools.app_graph.load_root_packages", return_value=["contest"]
            ),
            patch("grimp_tools.app_graph.get_skip_modules", return_value=set()),
            patch("grimp_tools.app_graph.build_graph", return_value=graph),
        ):
            run(self._args(exclude="tests,factories"))
        out = capsys.readouterr().out
        assert "tests" not in out
        assert "factories" not in out
        assert "contest_views --> contest_models" in out

    def test_exclude_extends_pyproject_skip(self, capsys) -> None:
        graph = _make_graph(
            ["contest.views", "contest.migrations.0001", "contest.tests.test_x"],
            {
                "contest.views": [
                    "contest.migrations.0001",
                    "contest.tests.test_x",
                ],
            },
        )
        with (
            patch(
                "grimp_tools.app_graph.load_root_packages", return_value=["contest"]
            ),
            patch(
                "grimp_tools.app_graph.get_skip_modules",
                return_value={"migrations"},
            ),
            patch("grimp_tools.app_graph.build_graph", return_value=graph),
        ):
            run(self._args(exclude="tests"))
        out = capsys.readouterr().out
        # Both default skip (migrations) and CLI exclude (tests) honoured.
        assert "migrations" not in out
        assert "tests" not in out

    def test_strip_prefix_flag_off(self, capsys) -> None:
        graph = _make_graph(
            ["contest.views", "contest.models"],
            {"contest.views": ["contest.models"]},
        )
        with (
            patch(
                "grimp_tools.app_graph.load_root_packages", return_value=["contest"]
            ),
            patch("grimp_tools.app_graph.get_skip_modules", return_value=set()),
            patch("grimp_tools.app_graph.build_graph", return_value=graph),
        ):
            run(self._args(strip_prefix=False))
        out = capsys.readouterr().out
        assert 'contest_models["contest.models"]' in out

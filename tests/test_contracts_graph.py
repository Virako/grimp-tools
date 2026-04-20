"""Tests for contracts_graph module."""

from grimp_tools.contracts_graph import (
    _is_app_isolation,
    _parse_edge,
    _render_debt_aggregated,
    _render_debt_detailed,
    _select_renderer,
    _split_ignores,
    render_debt_mermaid,
    render_html,
    render_rule_acyclic,
    render_rule_external,
    render_rule_forbidden,
    render_rule_layers,
    render_rule_shared,
)


class TestParseEdge:
    def test_simple(self) -> None:
        assert _parse_edge("api.views -> game.models") == ("api.views", "game.models")

    def test_with_spaces(self) -> None:
        assert _parse_edge("  api.views  ->  game.models  ") == (
            "api.views",
            "game.models",
        )


class TestSplitIgnores:
    def test_wildcards_and_debt(self) -> None:
        ignores = [
            "*.views -> *.models",
            "api.views -> game.models",
            "# comment",
        ]
        valid, debt = _split_ignores(ignores)
        assert valid == ["*.views -> *.models"]
        assert debt == [("api.views", "game.models")]

    def test_empty(self) -> None:
        valid, debt = _split_ignores([])
        assert valid == []
        assert debt == []

    def test_comments_skipped(self) -> None:
        valid, debt = _split_ignores(["# this is a comment"])
        assert valid == []
        assert debt == []


class TestIsAppIsolation:
    def test_concrete_app_names(self) -> None:
        contract = {
            "source_modules": ["shared"],
            "forbidden_modules": ["api", "game"],
        }
        assert _is_app_isolation(contract, {"api", "game", "shared"}) is True

    def test_wildcard_patterns(self) -> None:
        contract = {
            "source_modules": ["*.views"],
            "forbidden_modules": ["*.models"],
        }
        assert _is_app_isolation(contract, {"api", "game"}) is False

    def test_external_packages(self) -> None:
        contract = {
            "source_modules": ["*.views"],
            "forbidden_modules": ["django", "rest_framework"],
        }
        assert _is_app_isolation(contract, {"api", "game"}) is False

    def test_empty(self) -> None:
        contract = {"source_modules": [], "forbidden_modules": []}
        assert _is_app_isolation(contract, {"api"}) is False

    def test_source_not_in_root(self) -> None:
        contract = {
            "source_modules": ["external"],
            "forbidden_modules": ["api"],
        }
        assert _is_app_isolation(contract, {"api"}) is False


class TestRenderRuleShared:
    def test_output_structure(self) -> None:
        contract = {
            "source_modules": ["shared"],
            "forbidden_modules": ["api", "game"],
        }
        result = render_rule_shared(contract)
        assert "graph LR" in result
        assert "CORE" in result
        assert "BUSINESS" in result
        assert "can import" in result
        assert "shared" in result
        assert "api" in result


class TestRenderRuleForbidden:
    def test_with_valid_patterns(self) -> None:
        contract = {
            "source_modules": ["*.views"],
            "forbidden_modules": ["*.models"],
        }
        result = render_rule_forbidden(contract, ["*.views -> *.serializers"])
        assert "graph TD" in result
        assert "can import" in result

    def test_without_valid_patterns(self) -> None:
        contract = {
            "source_modules": ["*.views"],
            "forbidden_modules": ["*.models"],
        }
        result = render_rule_forbidden(contract, [])
        assert "graph TD" in result
        assert "can import" not in result


class TestRenderRuleExternal:
    def test_output_structure(self) -> None:
        contract = {
            "source_modules": ["*.views"],
            "forbidden_modules": ["django", "rest_framework"],
        }
        result = render_rule_external(contract, [])
        assert "Internal Layers" in result
        assert "External Libs" in result
        assert "django" in result

    def test_with_exceptions(self) -> None:
        contract = {
            "source_modules": ["*.views"],
            "forbidden_modules": ["django"],
        }
        result = render_rule_external(contract, ["*.adapters -> django"])
        assert "allowed" in result


class TestRenderRuleAcyclic:
    def test_basic(self) -> None:
        result = render_rule_acyclic([])
        assert "graph LR" in result
        assert "app A" in result
        assert "app B" in result

    def test_with_exceptions(self) -> None:
        result = render_rule_acyclic(["api.views -> game.models"])
        assert "Exception:" in result


class TestRenderRuleLayers:
    def test_renders_hierarchy(self) -> None:
        contract = {
            "layers": [
                "(urls)",
                "(views) | (admin)",
                "(services)",
                "(models) : (managers)",
            ],
            "containers": ["api", "game"],
        }
        result = render_rule_layers(contract)
        assert "graph TD" in result
        assert "urls" in result
        assert "views | admin" in result
        assert "services" in result
        assert "models : managers" in result
        assert "-->" in result

    def test_without_containers(self) -> None:
        contract = {
            "layers": ["(views)", "(models)"],
        }
        result = render_rule_layers(contract)
        assert "Applied to" not in result

    def test_with_containers(self) -> None:
        contract = {
            "layers": ["(views)", "(models)"],
            "containers": ["api", "game"],
        }
        result = render_rule_layers(contract)
        assert "Applied to 2 containers" in result


class TestRenderDebtMermaid:
    def test_returns_none_when_empty(self) -> None:
        assert render_debt_mermaid([]) is None

    def test_renders_detailed_for_small_debt(self) -> None:
        debt = [("api.views", "game.models"), ("api.serializers", "game.views")]
        result = render_debt_mermaid(debt)
        assert result is not None
        assert "subgraph api" in result
        assert "subgraph game" in result

    def test_renders_aggregated_for_large_debt(self) -> None:
        debt = [(f"app{i}.views", f"app{i}.models") for i in range(31)]
        result = render_debt_mermaid(debt)
        assert result is not None
        assert "subgraph" not in result


class TestRenderDebtDetailed:
    def test_renders_violations(self) -> None:
        debt = [("api.views", "game.models")]
        result = _render_debt_detailed(debt)
        assert "graph LR" in result
        assert "subgraph api" in result
        assert "-.-x" in result

    def test_single_app_violation(self) -> None:
        debt = [("api.views", "api.models")]
        result = _render_debt_detailed(debt)
        assert "subgraph api" in result


class TestRenderDebtAggregated:
    def test_aggregates_by_app(self) -> None:
        debt = [
            ("api.views", "game.models"),
            ("api.serializers", "game.models"),
            ("api.views", "game.views"),
        ]
        result = _render_debt_aggregated(debt)
        assert "graph LR" in result
        assert "|3|" in result
        assert "subgraph" not in result

    def test_multiple_app_pairs(self) -> None:
        debt = [
            ("api.views", "game.models"),
            ("engine.views", "game.models"),
        ]
        result = _render_debt_aggregated(debt)
        assert "|1|" in result


class TestRenderHtml:
    def test_mermaid_section(self) -> None:
        sections = [("Rule: Test", "graph LR\n    A --> B")]
        html = render_html(sections)
        assert "<!DOCTYPE html>" in html
        assert "mermaid" in html
        assert "Rule: Test" in html

    def test_text_section(self) -> None:
        sections = [("Violations: Test", "Clean - no violations")]
        html = render_html(sections)
        assert "text-block" in html
        assert "Clean - no violations" in html


class TestSelectRenderer:
    def test_acyclic_siblings(self) -> None:
        contract = {"type": "acyclic_siblings"}
        result = _select_renderer(contract, set(), [])
        assert "app A" in result

    def test_independence(self) -> None:
        contract = {"type": "independence"}
        result = _select_renderer(contract, set(), [])
        assert "app A" in result

    def test_layers(self) -> None:
        contract = {
            "type": "layers",
            "layers": ["(views)", "(models)"],
            "containers": ["api"],
        }
        result = _select_renderer(contract, set(), [])
        assert "graph TD" in result
        assert "views" in result
        assert "models" in result

    def test_forbidden_app_isolation(self) -> None:
        contract = {
            "type": "forbidden",
            "source_modules": ["shared"],
            "forbidden_modules": ["api"],
        }
        result = _select_renderer(contract, {"api", "shared"}, [])
        assert "CORE" in result

    def test_forbidden_external(self) -> None:
        contract = {
            "type": "forbidden",
            "source_modules": ["*.views"],
            "forbidden_modules": ["django"],
        }
        result = _select_renderer(contract, {"api"}, [])
        assert "External Libs" in result

    def test_forbidden_wildcard_internal(self) -> None:
        """Forbidden with wildcard patterns should NOT use shared renderer."""
        contract = {
            "type": "forbidden",
            "source_modules": ["*.views"],
            "forbidden_modules": ["*.models"],
        }
        result = _select_renderer(contract, {"api"}, [])
        assert "CORE" not in result
        assert "External Libs" in result

    def test_unknown_fallback(self) -> None:
        contract = {
            "type": "unknown",
            "source_modules": ["*.views"],
            "forbidden_modules": ["*.models"],
        }
        result = _select_renderer(contract, set(), [])
        assert "graph TD" in result

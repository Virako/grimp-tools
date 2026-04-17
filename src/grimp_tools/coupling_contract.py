"""
Custom import-linter contract that reports dependency coupling metrics.

Provides:
- App-level dependency counts (which app imports which, and how many times)
- Coupling table (in/out degree per module)
- Summary statistics
- Threshold control via exact_edges and exact_cross_app_edges

The metrics are printed during the check phase using verbose_print,
so they appear when running `lint-imports --verbose`.

For each threshold (exact_edges, exact_cross_app_edges):
- BREAKS if the value goes UP (coupling increased)
- WARNS if the value goes DOWN (coupling improved, update the config)

Register in pyproject.toml:

    [tool.importlinter]
    contract_types = [
      "coupling_metrics: grimp_tools.coupling_contract.CouplingMetricsContract",
    ]

    [[tool.importlinter.contracts]]
    id = "coupling"
    name = "Coupling metrics report"
    type = "coupling_metrics"
    skip_modules = "migrations,admin,apps,management"
    top_n = 30
    exact_edges = 42
    exact_cross_app_edges = 18
"""

from grimp import ImportGraph
from importlinter import Contract, ContractCheck
from importlinter.application import output
from importlinter.domain import fields

from grimp_tools.config import load_root_packages
from grimp_tools.graph import aggregate_apps, build_edge_set, build_graph_stats


def _check_threshold(
    name: str,
    actual: int,
    expected: int | None,
    errors: list[str],
    warnings: list[str],
) -> None:
    """Check a metric against its expected value. Appends to errors/warnings."""
    if expected is None:
        return
    if actual > expected:
        errors.append(f"{name} increased: {actual} (expected {expected}).")
    elif actual < expected:
        warnings.append(
            f"{name} decreased from {expected} to {actual}. "
            f"Update {name} in pyproject.toml to lock in the improvement."
        )


class CouplingMetricsContract(Contract):
    """Report dependency coupling metrics between apps and modules."""

    type_name = "coupling_metrics"

    skip_modules = fields.StringField(default="migrations,admin,apps,management")
    top_n = fields.IntegerField(default=30)
    exact_edges = fields.IntegerField(required=False)
    exact_cross_app_edges = fields.IntegerField(required=False)

    def check(self, graph: ImportGraph, verbose: bool) -> ContractCheck:
        skip_parts: set[str] = {
            s.strip()
            for s in self.skip_modules.split(",")  # type: ignore[union-attr]
        }
        root_packages = set(load_root_packages())

        edges = build_edge_set(graph, root_packages, skip_parts)
        nodes, in_deg, out_deg, _adj = build_graph_stats(edges)
        app_edges, _app_adj = aggregate_apps(edges)

        total_edges = sum(out_deg.values())
        cross_app_total = sum(app_edges.values())

        # Coupling table
        coupled = [
            (m, out_deg.get(m, 0), in_deg.get(m, 0))
            for m in sorted(nodes)
            if out_deg.get(m, 0) + in_deg.get(m, 0) > 0
        ]
        coupled.sort(key=lambda x: x[1] + x[2], reverse=True)

        top_n: int = self.top_n  # type: ignore[assignment]

        self._print_metrics(
            verbose, app_edges, coupled, nodes, total_edges, cross_app_total, top_n
        )

        # Check thresholds
        errors: list[str] = []
        warnings: list[str] = []
        _check_threshold(
            "exact_edges",
            total_edges,
            self.exact_edges,
            errors,
            warnings,  # type: ignore[arg-type]
        )
        _check_threshold(
            "exact_cross_app_edges",
            cross_app_total,
            self.exact_cross_app_edges,
            errors,
            warnings,  # type: ignore[arg-type]
        )

        return ContractCheck(
            kept=not errors,
            warnings=warnings,
            metadata={
                "app_edges": dict(app_edges),
                "coupled": coupled,
                "total_modules": len(nodes),
                "total_edges": total_edges,
                "cross_app_edges": cross_app_total,
                "errors": errors,
            },
        )

    def _print_metrics(
        self,
        verbose: bool,
        app_edges: dict[tuple[str, str], int],
        coupled: list[tuple[str, int, int]],
        all_modules: set[str],
        total_edges: int,
        cross_app_edges: int,
        top_n: int,
    ) -> None:
        output.verbose_print(verbose, "")
        output.verbose_print(verbose, "APP DEPENDENCIES:")
        for (src, dst), count in sorted(app_edges.items(), key=lambda x: -x[1]):
            output.verbose_print(verbose, f"  {src} -> {dst} ({count} imports)")

        output.verbose_print(verbose, "")
        output.verbose_print(verbose, f"COUPLING (top {top_n} by total dependencies):")
        header = f"  {'Module':<40} {'Out':>4} {'In':>4} {'Total':>6}"
        output.verbose_print(verbose, header)
        output.verbose_print(verbose, f"  {'─' * 40} {'─' * 4} {'─' * 4} {'─' * 6}")
        for name, o, i in coupled[:top_n]:
            output.verbose_print(verbose, f"  {name:<40} {o:>4} {i:>4} {o + i:>6}")

        output.verbose_print(verbose, "")
        output.verbose_print(
            verbose,
            f"SUMMARY: Modules: {len(all_modules)}, "
            f"Edges: {total_edges}, Cross-app edges: {cross_app_edges}",
        )

    def render_broken_contract(self, check: ContractCheck) -> None:
        for error in check.metadata["errors"]:
            output.print_error(error)
        output.new_line()
        output.print_error(
            "Reduce coupling by refactoring imports or update the threshold "
            "in pyproject.toml if the increase is intentional.",
            bold=False,
        )

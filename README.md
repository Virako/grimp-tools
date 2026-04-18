# grimp-tools

Dependency analysis, coupling enforcement, and architectural contract visualization for Django/Python projects.

Reads configuration from the consumer project's `pyproject.toml`. Zero config needed if you already use `import-linter`.

## Installation

```bash
uv add --dev grimp-tools
```

Requires Python 3.11+.

## Prerequisites

Your project must have `import-linter` configured with `root_packages`:

```toml
# pyproject.toml
[tool.importlinter]
root_packages = ["api", "game", "engine", "authentication"]
```

## Commands

### analyze

Module and app-level dependency analysis with cycle detection.

```bash
grimp-tools analyze
grimp-tools analyze --exit-on-cycles          # exit 1 if cycles found (CI)
grimp-tools analyze --history docs/deps.log   # append timestamped report
grimp-tools analyze --skip migrations,admin   # override skip modules
grimp-tools analyze --extra-packages celery   # add packages beyond root_packages
```

### snapshot

Save and compare dependency snapshots over time.

```bash
grimp-tools snapshot save                     # save to docs/deps-snapshot.json
grimp-tools snapshot diff                     # compare current vs saved
grimp-tools snapshot diff --ref master        # compare current vs snapshot at git ref
grimp-tools snapshot summary                  # print metrics without saving
```

Track `docs/deps-snapshot.json` in git to see how dependencies evolve across commits.

### focus-graph

Focused Mermaid graph showing only what changed between two git refs. Uses worktrees for clean builds.

```bash
grimp-tools focus-graph                              # HEAD vs HEAD~1
grimp-tools focus-graph --new main --old main~1      # specific refs
grimp-tools focus-graph -o docs/focus-graph.md       # save .md + .html
```

### contracts-graph

Visualize `import-linter` contracts as Mermaid diagrams.

```bash
grimp-tools contracts-graph                          # print to stdout
grimp-tools contracts-graph -o docs/contracts.md     # save .md + .html
```

### check-names

Validate that Python files follow naming conventions.

```bash
grimp-tools check-names                              # check all tracked .py files
grimp-tools check-names --ref master                 # only files changed vs ref
```

## Coupling contract (import-linter plugin)

A custom `import-linter` contract that enforces coupling thresholds as a ratchet: coupling can decrease (warns to update config) but not increase (breaks the contract).

```toml
# pyproject.toml
[tool.importlinter]
contract_types = [
  "coupling_metrics: grimp_tools.coupling_contract.CouplingMetricsContract",
]

[[tool.importlinter.contracts]]
id = "coupling"
name = "Coupling metrics"
type = "coupling_metrics"
skip_modules = "migrations,admin,apps,management"
top_n = 30
exact_edges = 42
exact_cross_app_edges = 18
```

Run with `lint-imports --verbose` to see the full coupling report.

## Configuration

All configuration is optional. If `[tool.grimp-tools]` is absent, defaults are used.

```toml
# pyproject.toml
[tool.grimp-tools]
# Modules to skip in analysis (default: migrations, admin, apps, management)
skip_modules = ["migrations", "admin", "apps", "management"]

# Snapshot output path (default: docs/deps-snapshot.json)
snapshot_path = "docs/deps-snapshot.json"

# File naming conventions for check-names
standard_names = [
  "models", "managers", "views", "serializers", "services", "urls",
  "admin", "apps", "forms", "signals", "tasks", "choices", "fields",
  "widgets", "middleware", "decorators", "exceptions", "types",
  "perms", "filters", "queries", "factories", "report", "adapters",
  "validators", "defaults", "enums", "mixins", "contexts", "caches",
  "actions", "tags", "pagination", "storage", "config", "help_texts",
  "conftest", "router", "settings", "wsgi", "manage",
]

exempt_dirs = [
  "migrations", "management", "commands", "scripts", "docs",
  "templatetags",
]
```

## Makefile integration

```makefile
deps:
	grimp-tools analyze --history docs/deps-history.log

snapshot:
	grimp-tools snapshot save

focus-graph:
	grimp-tools focus-graph --new main --old main~1 -o docs/focus-graph.md

check:
	lint-imports
	grimp-tools check-names
```

## Releasing

Publishing is automated via GitHub Actions with [Trusted Publishers](https://docs.pypi.org/trusted-publishers/) (OIDC, no tokens needed).

To publish a new version:

1. Update `version` in `pyproject.toml`
2. Commit and push to `main`
3. Create a git tag: `git tag v0.2.0 && git push origin v0.2.0`
4. Go to GitHub > Releases > "Draft a new release", select the tag, and click "Publish release"

The workflow (`.github/workflows/publish.yml`) builds and uploads to PyPI automatically via Trusted Publishers.

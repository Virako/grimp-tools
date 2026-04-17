"""Shared configuration loading from pyproject.toml."""

import tomllib
from pathlib import Path


DEFAULT_SKIP_MODULES = frozenset({"migrations", "admin", "apps", "management"})
DEFAULT_SNAPSHOT_PATH = Path("docs/deps-snapshot.json")
DEFAULT_STANDARD_NAMES = frozenset(
    {
        "models",
        "managers",
        "views",
        "serializers",
        "services",
        "urls",
        "admin",
        "apps",
        "forms",
        "signals",
        "tasks",
        "choices",
        "fields",
        "widgets",
        "middleware",
        "decorators",
        "exceptions",
        "types",
        "perms",
        "filters",
        "queries",
        "factories",
        "report",
        "adapters",
        "validators",
        "defaults",
        "enums",
        "mixins",
        "contexts",
        "caches",
        "actions",
        "tags",
        "pagination",
        "storage",
        "config",
        "help_texts",
        "conftest",
        "router",
        "settings",
        "wsgi",
        "manage",
    }
)
DEFAULT_EXEMPT_DIRS = frozenset(
    {
        "migrations",
        "management",
        "commands",
        "scripts",
        "docs",
        "templatetags",
    }
)


def _load_pyproject(path: Path | None = None) -> dict:
    """Load and return the parsed pyproject.toml."""
    pyproject = path or Path("pyproject.toml")
    with open(pyproject, "rb") as f:
        return tomllib.load(f)


def load_root_packages(pyproject_path: Path | None = None) -> list[str]:
    """Load root_packages from [tool.importlinter]."""
    data = _load_pyproject(pyproject_path)
    return data["tool"]["importlinter"]["root_packages"]


def load_grimp_tools_config(pyproject_path: Path | None = None) -> dict:
    """Load [tool.grimp-tools] section, returning empty dict if absent."""
    data = _load_pyproject(pyproject_path)
    return data.get("tool", {}).get("grimp-tools", {})


def get_skip_modules(pyproject_path: Path | None = None) -> set[str]:
    """Return the set of module name parts to skip during analysis."""
    config = load_grimp_tools_config(pyproject_path)
    custom = config.get("skip_modules")
    if custom is not None:
        return set(custom)
    return set(DEFAULT_SKIP_MODULES)


def get_snapshot_path(pyproject_path: Path | None = None) -> Path:
    """Return the path for dependency snapshots."""
    config = load_grimp_tools_config(pyproject_path)
    custom = config.get("snapshot_path")
    if custom is not None:
        return Path(custom)
    return DEFAULT_SNAPSHOT_PATH


def get_standard_names(pyproject_path: Path | None = None) -> set[str]:
    """Return the set of standard file names for check-names."""
    config = load_grimp_tools_config(pyproject_path)
    custom = config.get("standard_names")
    if custom is not None:
        return set(custom)
    return set(DEFAULT_STANDARD_NAMES)


def get_exempt_dirs(pyproject_path: Path | None = None) -> set[str]:
    """Return the set of directory names exempt from naming checks."""
    config = load_grimp_tools_config(pyproject_path)
    custom = config.get("exempt_dirs")
    if custom is not None:
        return set(custom)
    return set(DEFAULT_EXEMPT_DIRS)

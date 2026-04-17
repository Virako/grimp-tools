"""Tests for config loading from pyproject.toml."""

import textwrap
from pathlib import Path

import pytest

from grimp_tools.config import (
    DEFAULT_EXEMPT_DIRS,
    DEFAULT_SKIP_MODULES,
    DEFAULT_SNAPSHOT_PATH,
    DEFAULT_STANDARD_NAMES,
    get_exempt_dirs,
    get_skip_modules,
    get_snapshot_path,
    get_standard_names,
    load_grimp_tools_config,
    load_root_packages,
)


@pytest.fixture()
def pyproject_file(tmp_path: Path) -> Path:
    """Create a minimal pyproject.toml for testing."""
    content = textwrap.dedent("""\
        [tool.importlinter]
        root_packages = ["api", "game", "engine"]
    """)
    path = tmp_path / "pyproject.toml"
    path.write_text(content)
    return path


@pytest.fixture()
def pyproject_with_config(tmp_path: Path) -> Path:
    """Create a pyproject.toml with [tool.grimp-tools] section."""
    content = textwrap.dedent("""\
        [tool.importlinter]
        root_packages = ["api", "game"]

        [tool.grimp-tools]
        skip_modules = ["migrations", "tests"]
        snapshot_path = "output/snapshot.json"
        standard_names = ["models", "views", "urls"]
        exempt_dirs = ["migrations", "scripts"]
    """)
    path = tmp_path / "pyproject.toml"
    path.write_text(content)
    return path


class TestLoadRootPackages:
    def test_loads_packages(self, pyproject_file: Path) -> None:
        result = load_root_packages(pyproject_file)
        assert result == ["api", "game", "engine"]

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(FileNotFoundError):
            load_root_packages(tmp_path / "nonexistent.toml")

    def test_missing_section_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "pyproject.toml"
        path.write_text("[project]\nname = 'foo'\n")
        with pytest.raises(KeyError):
            load_root_packages(path)


class TestLoadGrimpToolsConfig:
    def test_returns_config(self, pyproject_with_config: Path) -> None:
        config = load_grimp_tools_config(pyproject_with_config)
        assert config["skip_modules"] == ["migrations", "tests"]
        assert config["snapshot_path"] == "output/snapshot.json"

    def test_returns_empty_when_absent(self, pyproject_file: Path) -> None:
        config = load_grimp_tools_config(pyproject_file)
        assert config == {}


class TestDefaults:
    def test_skip_modules_default(self, pyproject_file: Path) -> None:
        result = get_skip_modules(pyproject_file)
        assert result == set(DEFAULT_SKIP_MODULES)

    def test_skip_modules_custom(self, pyproject_with_config: Path) -> None:
        result = get_skip_modules(pyproject_with_config)
        assert result == {"migrations", "tests"}

    def test_snapshot_path_default(self, pyproject_file: Path) -> None:
        result = get_snapshot_path(pyproject_file)
        assert result == DEFAULT_SNAPSHOT_PATH

    def test_snapshot_path_custom(self, pyproject_with_config: Path) -> None:
        result = get_snapshot_path(pyproject_with_config)
        assert result == Path("output/snapshot.json")

    def test_standard_names_default(self, pyproject_file: Path) -> None:
        result = get_standard_names(pyproject_file)
        assert result == set(DEFAULT_STANDARD_NAMES)

    def test_standard_names_custom(self, pyproject_with_config: Path) -> None:
        result = get_standard_names(pyproject_with_config)
        assert result == {"models", "views", "urls"}

    def test_exempt_dirs_default(self, pyproject_file: Path) -> None:
        result = get_exempt_dirs(pyproject_file)
        assert result == set(DEFAULT_EXEMPT_DIRS)

    def test_exempt_dirs_custom(self, pyproject_with_config: Path) -> None:
        result = get_exempt_dirs(pyproject_with_config)
        assert result == {"migrations", "scripts"}

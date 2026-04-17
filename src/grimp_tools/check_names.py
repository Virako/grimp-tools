"""File naming convention checker for Django/Python projects."""

import subprocess
import sys
from pathlib import Path

from grimp_tools.config import get_exempt_dirs, get_standard_names


ALLOWED_PATTERNS = {
    "__init__",
    "conftest",
    "test_settings",
    "local_settings",
    "custom_settings",
}


def is_standard(filename: str, standard_names: set[str]) -> bool:
    """Check if a filename (without .py) follows conventions."""
    if filename in ALLOWED_PATTERNS:
        return True
    if filename in standard_names:
        return True
    if (
        filename == "tests"
        or filename.startswith("tests_")
        or filename.startswith("test_")
    ):
        return True
    return False


def is_in_allowed_location(filepath: str, exempt_dirs: set[str]) -> bool:
    """Files in certain directories are exempt."""
    parts = Path(filepath).parts
    if set(parts) & exempt_dirs:
        return True
    # Root-level files (not inside an app)
    if len(parts) == 1:
        return True
    return False


def get_files(ref: str | None) -> list[str]:
    """Get files to check: all .py or only changed vs ref."""
    if ref:
        try:
            result = subprocess.run(
                ["git", "diff", "--name-only", "--diff-filter=ACR", ref, "--", "*.py"],
                capture_output=True,
                text=True,
                check=True,
            )
            return [f.strip() for f in result.stdout.splitlines() if f.strip()]
        except subprocess.CalledProcessError:
            return []

    result = subprocess.run(
        ["git", "ls-files", "--others", "--cached", "--exclude-standard", "*.py"],
        capture_output=True,
        text=True,
    )
    return [f.strip() for f in result.stdout.splitlines() if f.strip()]


def check(
    files: list[str], standard_names: set[str], exempt_dirs: set[str]
) -> list[tuple[str, str]]:
    """Return list of (filepath, stem) for files violating naming conventions."""
    violations: list[tuple[str, str]] = []
    for filepath in files:
        if is_in_allowed_location(filepath, exempt_dirs):
            continue
        name = Path(filepath).stem
        if not is_standard(name, standard_names):
            violations.append((filepath, name))
    return violations


def run(ref: str | None = None) -> None:
    """Entry point for the check-names subcommand."""
    standard_names = get_standard_names()
    exempt_dirs = get_exempt_dirs()

    files = get_files(ref)
    violations = check(files, standard_names, exempt_dirs)

    if violations:
        print(f"Found {len(violations)} file(s) with non-standard names:\n")
        for filepath, _name in sorted(violations):
            print(f"  {filepath}")
        print(f"\nAllowed names: {', '.join(sorted(standard_names))}")
        print(
            "\nRename the file or add it to [tool.grimp-tools].standard_names "
            "in pyproject.toml"
        )
        sys.exit(1)
    else:
        print(f"All {len(files)} files follow naming conventions.")

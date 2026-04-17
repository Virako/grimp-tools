"""Tests for check_names module."""

from grimp_tools.check_names import check, is_in_allowed_location, is_standard


NAMES = {"models", "views", "serializers", "services", "urls"}
EXEMPT = {"migrations", "management", "scripts"}


class TestIsStandard:
    def test_standard_name(self) -> None:
        assert is_standard("models", NAMES) is True

    def test_non_standard_name(self) -> None:
        assert is_standard("helpers", NAMES) is False

    def test_init(self) -> None:
        assert is_standard("__init__", NAMES) is True

    def test_conftest(self) -> None:
        assert is_standard("conftest", NAMES) is True

    def test_test_prefix(self) -> None:
        assert is_standard("test_models", NAMES) is True

    def test_tests(self) -> None:
        assert is_standard("tests", NAMES) is True

    def test_tests_prefix(self) -> None:
        assert is_standard("tests_integration", NAMES) is True

    def test_test_settings(self) -> None:
        assert is_standard("test_settings", NAMES) is True

    def test_local_settings(self) -> None:
        assert is_standard("local_settings", NAMES) is True


class TestIsInAllowedLocation:
    def test_exempt_dir(self) -> None:
        assert is_in_allowed_location("api/migrations/0001.py", EXEMPT) is True

    def test_root_level(self) -> None:
        assert is_in_allowed_location("manage.py", EXEMPT) is True

    def test_app_level(self) -> None:
        assert is_in_allowed_location("api/helpers.py", EXEMPT) is False

    def test_nested_exempt(self) -> None:
        assert is_in_allowed_location("api/management/commands/foo.py", EXEMPT) is True

    def test_scripts_dir(self) -> None:
        assert is_in_allowed_location("scripts/deploy.py", EXEMPT) is True


class TestCheck:
    def test_no_violations(self) -> None:
        files = ["api/models.py", "api/views.py", "api/__init__.py"]
        violations = check(files, NAMES, EXEMPT)
        assert violations == []

    def test_violations_detected(self) -> None:
        files = ["api/models.py", "api/helpers.py", "api/utils.py"]
        violations = check(files, NAMES, EXEMPT)
        assert len(violations) == 2
        stems = {v[1] for v in violations}
        assert stems == {"helpers", "utils"}

    def test_exempt_dirs_skipped(self) -> None:
        files = ["api/migrations/0001_initial.py", "api/helpers.py"]
        violations = check(files, NAMES, EXEMPT)
        assert len(violations) == 1
        assert violations[0][1] == "helpers"

    def test_root_files_skipped(self) -> None:
        files = ["setup.py", "conftest.py"]
        violations = check(files, NAMES, EXEMPT)
        assert violations == []

    def test_test_files_allowed(self) -> None:
        files = ["api/test_models.py", "api/tests_integration.py"]
        violations = check(files, NAMES, EXEMPT)
        assert violations == []

    def test_empty_files(self) -> None:
        violations = check([], NAMES, EXEMPT)
        assert violations == []

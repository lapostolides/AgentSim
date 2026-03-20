"""Tests for environment discovery."""

from agentsim.environment.discovery import (
    discover_environment,
    format_environment_for_prompt,
)
from agentsim.state.models import AvailablePackage, EnvironmentInfo


class TestDiscoverEnvironment:
    def test_finds_numpy(self):
        env = discover_environment()
        names = [p.name for p in env.packages]
        # numpy is installed in our test environment
        assert "numpy" in names

    def test_has_python_version(self):
        env = discover_environment()
        assert env.python_version  # e.g. "3.12.1"
        assert "." in env.python_version

    def test_extra_packages(self):
        # "json" is a stdlib module, should be findable
        env = discover_environment(extra_packages={"json-stdlib": "json"})
        names = [p.name for p in env.packages]
        assert "json-stdlib" in names

    def test_missing_package_not_included(self):
        env = discover_environment(
            extra_packages={"nonexistent_pkg_xyz": "nonexistent_pkg_xyz"}
        )
        names = [p.name for p in env.packages]
        assert "nonexistent_pkg_xyz" not in names


class TestFormatEnvironmentForPrompt:
    def test_with_packages(self):
        env = EnvironmentInfo(
            packages=(
                AvailablePackage(name="mitsuba", version="3.5.0", import_name="mitsuba"),
                AvailablePackage(name="numpy", version="1.26.0", import_name="numpy"),
                AvailablePackage(name="opencv", version="4.9.0", import_name="cv2"),
            ),
            python_version="3.12.1",
        )
        result = format_environment_for_prompt(env)
        assert "Python 3.12.1" in result
        assert "mitsuba" in result
        assert "numpy" in result
        assert "cv2" in result  # import note for opencv

    def test_no_packages(self):
        env = EnvironmentInfo(packages=(), python_version="3.12.1")
        result = format_environment_for_prompt(env)
        assert "No simulation packages" in result

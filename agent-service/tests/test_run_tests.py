"""
test_run_tests.py
=================
Unit tests for the run_tests LangChain tool.

These tests mock subprocess.run so no real test suite is executed.
The detection logic is tested with real files in tmp_path.
"""

import json
from unittest.mock import MagicMock, patch
import pytest


def invoke(timeout: int = 30) -> dict:
    from app.tools.run_tests import run_tests
    return json.loads(run_tests.invoke({"timeout": timeout}))


# ---------------------------------------------------------------------------
# Framework detection tests
# ---------------------------------------------------------------------------

class TestFrameworkDetection:
    def test_detects_pytest_via_config(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "pytest.ini").write_text("[pytest]\n")

        from app.tools.run_tests import _detect_framework
        assert _detect_framework(tmp) == "pytest"

    def test_detects_pytest_via_pyproject(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "pyproject.toml").write_text('[tool.pytest.ini_options]\ntestpaths = ["tests"]\n')

        from app.tools.run_tests import _detect_framework
        assert _detect_framework(tmp) == "pytest"

    def test_detects_pytest_via_test_files(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "test_something.py").write_text("def test_foo(): pass\n")

        from app.tools.run_tests import _detect_framework
        assert _detect_framework(tmp) == "pytest"

    def test_detects_jest_via_package_json(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "package.json").write_text('{"devDependencies": {"jest": "^29.0.0"}}')

        from app.tools.run_tests import _detect_framework
        assert _detect_framework(tmp) == "jest"

    def test_detects_jest_via_config_file(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "jest.config.js").write_text("module.exports = {};\n")

        from app.tools.run_tests import _detect_framework
        assert _detect_framework(tmp) == "jest"

    def test_detects_jest_via_spec_files(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "app.test.ts").write_text("test('x', () => {})\n")

        from app.tools.run_tests import _detect_framework
        assert _detect_framework(tmp) == "jest"

    def test_returns_none_when_no_framework(self, set_repo_root):
        from app.tools.run_tests import _detect_framework
        assert _detect_framework(set_repo_root) is None


# ---------------------------------------------------------------------------
# Tool-invocation tests (subprocess mocked)
# ---------------------------------------------------------------------------

class TestRunTestsTool:
    def _mock_proc(self, stdout="", stderr="", returncode=0):
        proc = MagicMock()
        proc.stdout = stdout
        proc.stderr = stderr
        proc.returncode = returncode
        return proc

    def test_pytest_passed(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "pytest.ini").write_text("[pytest]\n")

        output = "5 passed in 1.23s"
        with patch("subprocess.run", return_value=self._mock_proc(stdout=output)):
            result = invoke()

        assert result["success"] is True
        assert result["framework"] == "pytest"
        assert result["status"] == "passed"
        assert "pytest" in result["command"]
        assert result["exit_code"] == 0

    def test_pytest_failed(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "pytest.ini").write_text("[pytest]\n")

        output = "2 failed, 3 passed in 0.8s"
        with patch("subprocess.run", return_value=self._mock_proc(stdout=output, returncode=1)):
            result = invoke()

        assert result["success"] is True
        assert result["status"] == "failed"

    def test_jest_passed(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "jest.config.js").write_text("module.exports = {};\n")

        output = "Tests: 18 passed, 18 total\nTest Suites: 3 passed, 3 total"
        with patch("subprocess.run", return_value=self._mock_proc(stdout=output)):
            result = invoke()

        assert result["success"] is True
        assert result["framework"] == "jest"
        assert result["status"] == "passed"
        assert "npm" in result["command"]

    def test_timeout_returns_timeout_status(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "pytest.ini").write_text("[pytest]\n")

        import subprocess
        with patch("subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="pytest", timeout=30)):
            result = invoke(timeout=30)

        assert result["success"] is True
        assert result["status"] == "timeout"
        assert "timed out" in result["summary"].lower()

    def test_no_framework_detected(self, set_repo_root):
        # Empty tmp dir — no test files, no config
        result = invoke()

        assert result["success"] is False
        assert "No supported test framework" in result["error"]

    def test_no_repo_root(self, monkeypatch):
        monkeypatch.delenv("REPO_ROOT", raising=False)

        result = invoke()

        assert result["success"] is False
        assert "REPO_ROOT" in result["error"]

    def test_command_not_found(self, set_repo_root):
        tmp = set_repo_root
        (tmp / "pytest.ini").write_text("[pytest]\n")

        with patch("subprocess.run", side_effect=FileNotFoundError("pytest not found")):
            result = invoke()

        assert result["success"] is False
        assert "not found" in result["error"].lower()

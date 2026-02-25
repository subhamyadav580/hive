"""
Tests for Browser-Use MCP tool.

Covers:
- Input validation (task, max_steps, timeout)
- Provider + model resolution
- API key resolution
- Auth credential flow
- Vision mode
- run_browser_task execution
- All 3 MCP tools
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from aden_tools.tools.browser_use_tool.registration import (
    MAX_STEPS_MAX,
    MAX_STEPS_MIN,
    TIMEOUT_MAX_MS,
    TIMEOUT_MIN_MS,
    register_tools,
)

# ─────────────────────────────────────────
# Base Test Setup
# ─────────────────────────────────────────


class BaseBrowserToolTest:
    def setup_method(self):
        self.mcp = MagicMock()
        self.fns = []
        self.mcp.tool.return_value = lambda fn: self.fns.append(fn) or fn

        credentials = MagicMock()
        register_tools(self.mcp, credentials=credentials)

    def _fn(self, name):
        return next(f for f in self.fns if f.__name__ == name)


# ─────────────────────────────────────────
# browser_use_task Tests
# ─────────────────────────────────────────


class TestBrowserUseTask(BaseBrowserToolTest):

    @patch("aden_tools.tools.browser_use_tool.registration.run_browser_task")
    @patch("aden_tools.tools.browser_use_tool.registration.CredentialResolver")
    def test_success(self, mock_resolver_cls, mock_run):
        mock_resolver = MagicMock()
        mock_resolver.resolve_provider_and_model.return_value = ("openai", "gpt-4")
        mock_resolver.resolve_api_key.return_value = "test-key"
        mock_resolver_cls.return_value = mock_resolver

        mock_run.return_value = {
            "success": True,
            "result": "Done",
            "execution_time_ms": 1234,
        }

        result = self._fn("browser_use_task")(task="Open google")

        assert result["success"] is True
        mock_run.assert_called_once()

    def test_empty_task(self):
        result = self._fn("browser_use_task")(task="")
        assert result["success"] is False
        assert result["status"] == "configuration_error"
        assert "task cannot be empty" in result["error"]

    def test_invalid_max_steps_low(self):
        result = self._fn("browser_use_task")(
            task="test",
            max_steps=MAX_STEPS_MIN - 1,
        )
        assert result["success"] is False
        assert "max_steps" in result["error"]

    def test_invalid_max_steps_high(self):
        result = self._fn("browser_use_task")(
            task="test",
            max_steps=MAX_STEPS_MAX + 1,
        )
        assert result["success"] is False
        assert "max_steps" in result["error"]

    def test_invalid_timeout_low(self):
        result = self._fn("browser_use_task")(
            task="test",
            timeout_ms=TIMEOUT_MIN_MS - 1,
        )
        assert result["success"] is False
        assert "timeout_ms" in result["error"]

    def test_invalid_timeout_high(self):
        result = self._fn("browser_use_task")(
            task="test",
            timeout_ms=TIMEOUT_MAX_MS + 1,
        )
        assert result["success"] is False
        assert "timeout_ms" in result["error"]

    @patch("aden_tools.tools.browser_use_tool.registration.run_browser_task")
    @patch("aden_tools.tools.browser_use_tool.registration.CredentialResolver")
    def test_api_key_resolution_error(self, mock_resolver_cls, mock_run):
        # Arrange resolver to raise
        mock_resolver = MagicMock()
        mock_resolver.resolve_provider_and_model.return_value = ("openai", "gpt-4")
        mock_resolver.resolve_api_key.side_effect = ValueError("No API key found")
        mock_resolver_cls.return_value = mock_resolver

        # IMPORTANT: register tools AFTER patching
        mcp = MagicMock()
        fns = []
        mcp.tool.return_value = lambda fn: fns.append(fn) or fn

        register_tools(mcp, credentials=MagicMock())

        browser_fn = next(f for f in fns if f.__name__ == "browser_use_task")

        # Act
        result = browser_fn(task="Open site")

        # Assert
        assert result["success"] is False
        assert result["status"] == "configuration_error"
        assert "No API key found" in result["error"]

        mock_run.assert_not_called()

# ─────────────────────────────────────────
# browser_use_auth_task Tests
# ─────────────────────────────────────────


class TestBrowserUseAuthTask(BaseBrowserToolTest):

    def test_mutually_exclusive_credentials(self):
        result = self._fn("browser_use_auth_task")(
            task="Login",
            credential_ref="ref",
            explicit_credentials={"u": "x"},
        )
        assert result["success"] is False
        assert "either credential_ref OR explicit_credentials" in result["error"]

    @patch("aden_tools.tools.browser_use_tool.registration.AuthCredentialResolver")
    def test_no_credentials(self, mock_auth_cls):
        mock_auth = MagicMock()
        mock_auth.resolve_credentials.return_value = None
        mock_auth_cls.return_value = mock_auth

        result = self._fn("browser_use_auth_task")(task="Login")

        assert result["success"] is False
        assert result["status"] == "configuration_error"

    @patch("aden_tools.tools.browser_use_tool.registration.run_browser_task")
    @patch("aden_tools.tools.browser_use_tool.registration.AuthCredentialResolver")
    @patch("aden_tools.tools.browser_use_tool.registration.CredentialResolver")
    def test_auth_success(
        self,
        mock_resolver_cls,
        mock_auth_cls,
        mock_run,
    ):
        mock_resolver = MagicMock()
        mock_resolver.resolve_provider_and_model.return_value = ("openai", "gpt-4")
        mock_resolver.resolve_api_key.return_value = "key"
        mock_resolver_cls.return_value = mock_resolver

        mock_auth = MagicMock()
        mock_auth.resolve_credentials.return_value = {"username": "u"}
        mock_auth.inject_credentials_into_task.return_value = "Injected task"
        mock_auth_cls.return_value = mock_auth

        mock_run.return_value = {"success": True}

        result = self._fn("browser_use_auth_task")(
            task="Login",
            credential_ref="ref",
        )

        assert result["success"] is True
        mock_run.assert_called_once()


# ─────────────────────────────────────────
# browser_use_vision_task Tests
# ─────────────────────────────────────────


class TestBrowserUseVisionTask(BaseBrowserToolTest):

    @patch("aden_tools.tools.browser_use_tool.registration.run_browser_task")
    @patch("aden_tools.tools.browser_use_tool.registration.CredentialResolver")
    def test_vision_enabled(
        self,
        mock_resolver_cls,
        mock_run,
    ):
        mock_resolver = MagicMock()
        mock_resolver.resolve_provider_and_model.return_value = (
            "openai",
            "gpt-4-vision",
        )
        mock_resolver.resolve_api_key.return_value = "key"
        mock_resolver_cls.return_value = mock_resolver

        mock_run.return_value = {"success": True}

        result = self._fn("browser_use_vision_task")(task="Check image")

        assert result["success"] is True
        mock_run.assert_called_once()


# ─────────────────────────────────────────
# Tool Registration Tests
# ─────────────────────────────────────────


class TestToolRegistration:
    def test_all_tools_registered(self):
        mcp = MagicMock()
        fns = []
        mcp.tool.return_value = lambda fn: fns.append(fn) or fn

        register_tools(mcp, credentials=MagicMock())

        names = {fn.__name__ for fn in fns}

        assert "browser_use_task" in names
        assert "browser_use_auth_task" in names
        assert "browser_use_vision_task" in names
        assert len(names) == 3

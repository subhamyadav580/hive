"""
Integration tests for browser automation tools.
"""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastmcp import FastMCP

from aden_tools.credentials import CredentialStoreAdapter
from aden_tools.credentials.auth_store import AuthCredentialStore
from aden_tools.tools.browser_use_tool import register_tools

# ============================================================================
# FIXTURES
# ============================================================================


@pytest.fixture
def mcp():
    """Create a fresh FastMCP instance."""
    return FastMCP("test-browser-automation")


@pytest.fixture
def mock_llm_credentials():
    """Mock LLM provider credentials."""
    mock_store = MagicMock(spec=CredentialStoreAdapter)

    def mock_get(provider: str):
        return {
            "anthropic": "sk-ant-test-key",
            "openai": "sk-test-key",
            "groq": "gsk_test-key",
        }.get(provider.lower())

    def mock_is_available(provider: str):
        return provider.lower() in ["anthropic", "openai", "groq"]

    mock_store.get.side_effect = mock_get
    mock_store.is_available.side_effect = mock_is_available
    mock_store.get_key.return_value = None

    return mock_store


@pytest.fixture
def mock_auth_credentials():
    """Mock website authentication credentials."""
    mock_store = MagicMock(spec=AuthCredentialStore)

    # Use a class to maintain state across calls
    class CredentialDB:
        def __init__(self):
            self.db = {
                "gmail_work": {
                    "username": "test@company.com",
                    "password": "TestPass123!",
                    "two_factor_secret": "TOTP_SECRET"
                },
                "github": {
                    "username": "testuser",
                    "password": "GithubPass456!"
                },
            }

    db = CredentialDB()

    mock_store.get_auth_credential.side_effect = lambda ref_id: db.db.get(ref_id)
    mock_store.list_auth_credentials.side_effect = lambda: list(db.db.keys())

    def mock_save(ref_id, username, password, metadata=None):
        db.db[ref_id] = {
            "username": username,
            "password": password,
            **(metadata or {})
        }

    def mock_delete(ref_id):
        return db.db.pop(ref_id, None) is not None

    mock_store.save_auth_credential.side_effect = mock_save
    mock_store.delete_auth_credential.side_effect = mock_delete

    return mock_store


@pytest.fixture
def mock_browser_execution():
    """Mock the actual browser execution at the correct import location."""
    # CRITICAL: Patch where it's USED, not where it's DEFINED
    with patch(
        "aden_tools.tools.browser_use_tool.registration.run_browser_task",
        new_callable=AsyncMock,
    ) as mock:
        mock.return_value = {
            "success": True,
            "result": "Task completed successfully",
            "steps_taken": 5,
            "execution_time_ms": 1234,
            "model_used": "claude-3-5-sonnet-20241022",
            "provider_used": "anthropic",
        }
        yield mock


# ============================================================================
# TOOL REGISTRATION TESTS
# ============================================================================


def test_register_tools_creates_all_tools(mcp, mock_llm_credentials, mock_auth_credentials):
    """Test that all expected tools are registered."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=mock_auth_credentials)

    expected_tools = [
        "browser_use_task",
        "browser_use_auth_task",
        "browser_use_vision_task",
        "save_auth_credential",
        "list_auth_credentials",
        "delete_auth_credential",
        "get_auth_credential_info",
    ]

    registered_tools = list(mcp._tool_manager._tools.keys())

    for tool_name in expected_tools:
        assert tool_name in registered_tools, f"Tool '{tool_name}' not registered"


# ============================================================================
# CREDENTIAL RESOLUTION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_api_key_from_credential_store(
    mcp, mock_llm_credentials, mock_browser_execution
):
    """Test API key is resolved from credential store."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_task"].fn

    result = await tool_fn(
        task="Search for FastAPI documentation",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022"
    )

    assert result["success"] is True
    # Verify the mock was called with correct API key
    call_kwargs = mock_browser_execution.call_args.kwargs
    assert call_kwargs["api_key"] == "sk-ant-test-key"
    assert call_kwargs["provider"] == "anthropic"


@pytest.mark.asyncio
async def test_api_key_from_environment(mcp, mock_browser_execution):
    """Test API key resolution from environment variable."""
    register_tools(mcp, credentials=None, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_task"].fn

    with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-test-key"}):
        result = await tool_fn(
            task="Search for FastAPI documentation",
            provider="openai",
            model="gpt-4o-mini"
        )

    assert result["success"] is True
    call_kwargs = mock_browser_execution.call_args.kwargs
    assert call_kwargs["api_key"] == "sk-env-test-key"


@pytest.mark.asyncio
async def test_explicit_api_key_takes_priority(
    mcp, mock_llm_credentials, mock_browser_execution
):
    """Test that explicit api_key parameter takes highest priority."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_task"].fn

    result = await tool_fn(
        task="Search for FastAPI documentation",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022",
        api_key="sk-explicit-override-key"
    )

    assert result["success"] is True
    call_kwargs = mock_browser_execution.call_args.kwargs
    assert call_kwargs["api_key"] == "sk-explicit-override-key"


@pytest.mark.asyncio
async def test_missing_api_key_error(mcp):
    """Test error when no API key is available."""
    register_tools(mcp, credentials=None, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_task"].fn

    with patch.dict(os.environ, {}, clear=True):
        result = await tool_fn(
            task="Search for FastAPI documentation",
            provider="anthropic"
        )

    assert result["success"] is False
    assert "No API key found" in result["error"]
    assert "ANTHROPIC_API_KEY" in result["error"]


# ============================================================================
# PROVIDER AUTO-DETECTION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_provider_auto_detection_from_store(
    mcp, mock_llm_credentials, mock_browser_execution
):
    """Test provider is auto-detected from credential store."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_task"].fn

    result = await tool_fn(task="Search for FastAPI documentation")

    assert result["success"] is True
    call_kwargs = mock_browser_execution.call_args.kwargs
    assert call_kwargs["provider"] == "anthropic"


@pytest.mark.asyncio
async def test_provider_auto_detection_from_env(mcp, mock_browser_execution):
    """Test provider auto-detection from environment variables."""
    register_tools(mcp, credentials=None, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_task"].fn

    # Clear ALL other env vars
    with patch.dict(os.environ, {"GROQ_API_KEY": "gsk_env_key"}, clear=True):
        result = await tool_fn(task="Search for FastAPI documentation")

    assert result["success"] is True
    call_kwargs = mock_browser_execution.call_args.kwargs
    assert call_kwargs["provider"] == "groq"



@pytest.mark.asyncio
async def test_no_provider_configured_error(mcp, mock_browser_execution):
    """Test error when no provider is configured."""
    register_tools(mcp, credentials=None, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_task"].fn

    with patch.dict(os.environ, {}, clear=True):
        with pytest.raises(ValueError) as exc_info:
            await tool_fn(task="Search for FastAPI documentation")

    assert "No LLM provider configured" in str(exc_info.value)


# ============================================================================
# INPUT VALIDATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_empty_task_validation(mcp, mock_llm_credentials):
    """Test validation rejects empty tasks."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_task"].fn

    result = await tool_fn(task="")

    assert result["success"] is False
    assert "task cannot be empty" in result["error"]


@pytest.mark.asyncio
async def test_max_steps_validation(mcp, mock_llm_credentials, mock_browser_execution):
    """Test max_steps bounds checking."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_task"].fn

    # Too low
    result = await tool_fn(task="test", max_steps=0)
    assert result["success"] is False
    assert "max_steps must be between 1 and 50" in result["error"]

    # Too high
    result = await tool_fn(task="test", max_steps=100)
    assert result["success"] is False
    assert "max_steps must be between 1 and 50" in result["error"]

    # Valid
    result = await tool_fn(task="test", max_steps=25)
    assert result["success"] is True


@pytest.mark.asyncio
async def test_timeout_validation(mcp, mock_llm_credentials):
    """Test timeout_ms bounds checking."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_task"].fn

    # Too low
    result = await tool_fn(task="test", timeout_ms=1000)
    assert result["success"] is False
    assert "timeout_ms must be between 5000 and 300000" in result["error"]

    # Too high
    result = await tool_fn(task="test", timeout_ms=500000)
    assert result["success"] is False
    assert "timeout_ms must be between 5000 and 300000" in result["error"]


# ============================================================================
# AUTH CREDENTIAL TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_auth_task_with_credential_ref(
    mcp, mock_llm_credentials, mock_auth_credentials, mock_browser_execution
):
    """Test auth task using credential reference (secure method)."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=mock_auth_credentials)
    tool_fn = mcp._tool_manager._tools["browser_use_auth_task"].fn

    result = await tool_fn(
        task="Log into {username} with password {password}",
        credential_ref="gmail_work",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022"
    )

    assert result["success"] is True
    mock_auth_credentials.get_auth_credential.assert_called_once_with("gmail_work")

    call_kwargs = mock_browser_execution.call_args.kwargs
    assert "test@company.com" in call_kwargs["task"]
    assert "TestPass123!" in call_kwargs["task"]


@pytest.mark.asyncio
async def test_auth_task_with_explicit_credentials(
    mcp, mock_llm_credentials, mock_browser_execution
):
    """Test auth task with explicit username/password."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_auth_task"].fn

    result = await tool_fn(
        task="Log into {username} with {password}",
        username="direct@example.com",
        password="DirectPass123!",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022"
    )

    assert result["success"] is True
    call_kwargs = mock_browser_execution.call_args.kwargs
    assert "direct@example.com" in call_kwargs["task"]
    assert "DirectPass123!" in call_kwargs["task"]


@pytest.mark.asyncio
async def test_auth_task_no_credentials_error(mcp, mock_llm_credentials):
    """Test error when no credentials provided."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_auth_task"].fn

    result = await tool_fn(
        task="Log into website",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022"
    )

    assert result["success"] is False
    assert "No credentials provided" in result["error"]


@pytest.mark.asyncio
async def test_auth_task_ambiguous_credentials_error(
    mcp, mock_llm_credentials, mock_auth_credentials
):
    """Test error when both credential_ref and username/password provided."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=mock_auth_credentials)
    tool_fn = mcp._tool_manager._tools["browser_use_auth_task"].fn

    result = await tool_fn(
        task="Log into website",
        credential_ref="gmail_work",
        username="user@example.com",
        password="pass123",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022"
    )

    assert result["success"] is False
    assert "not both" in result["error"].lower()


# ============================================================================
# VISION TASK TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_vision_task_selects_vision_model(
    mcp, mock_llm_credentials, mock_browser_execution
):
    """Test vision task automatically selects vision-capable model."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=None)
    tool_fn = mcp._tool_manager._tools["browser_use_vision_task"].fn

    result = await tool_fn(
        task="Click the red button",
        provider="openai"
    )

    assert result["success"] is True
    call_kwargs = mock_browser_execution.call_args.kwargs
    assert call_kwargs["use_vision"] is True
    assert call_kwargs["model"] == "gpt-4o"


# ============================================================================
# CREDENTIAL MANAGEMENT TESTS
# ============================================================================


def test_save_auth_credential(mcp, mock_auth_credentials):
    """Test saving auth credentials."""
    register_tools(mcp, credentials=None, auth_store=mock_auth_credentials)
    tool_fn = mcp._tool_manager._tools["save_auth_credential"].fn

    result = tool_fn(
        ref_id="new_service",
        username="newuser@example.com",
        password="NewPass789!",
        two_factor_secret="TOTP123",
        notes="Test account"
    )

    assert result["success"] is True
    assert result["ref_id"] == "new_service"


def test_list_auth_credentials(mcp, mock_auth_credentials):
    """Test listing auth credentials."""
    register_tools(mcp, credentials=None, auth_store=mock_auth_credentials)
    tool_fn = mcp._tool_manager._tools["list_auth_credentials"].fn

    result = tool_fn()

    assert result["success"] is True
    assert result["count"] == 2
    assert "gmail_work" in result["credentials"]
    assert "github" in result["credentials"]


def test_delete_auth_credential_success(mcp, mock_auth_credentials):
    """Test deleting existing credential."""
    register_tools(mcp, credentials=None, auth_store=mock_auth_credentials)
    tool_fn = mcp._tool_manager._tools["delete_auth_credential"].fn

    result = tool_fn(ref_id="gmail_work")

    assert result["success"] is True
    assert "deleted" in result["message"].lower()


def test_get_auth_credential_info(mcp, mock_auth_credentials):
    """Test getting credential info (without password)."""
    register_tools(mcp, credentials=None, auth_store=mock_auth_credentials)
    tool_fn = mcp._tool_manager._tools["get_auth_credential_info"].fn

    result = tool_fn(ref_id="gmail_work")

    assert result["success"] is True
    assert result["info"]["username"] == "test@company.com"
    assert "password" not in result["info"]


# ============================================================================
# INTEGRATION TESTS
# ============================================================================


@pytest.mark.asyncio
async def test_full_workflow_save_and_use_credential(
    mcp, mock_llm_credentials, mock_auth_credentials, mock_browser_execution
):
    """Test complete workflow: save credential -> list -> use in task."""
    register_tools(mcp, credentials=mock_llm_credentials, auth_store=mock_auth_credentials)

    # 1. Save a new credential
    save_fn = mcp._tool_manager._tools["save_auth_credential"].fn
    save_result = save_fn(
        ref_id="test_service",
        username="test@service.com",
        password="TestPass123!"
    )
    assert save_result["success"] is True

    # 2. Verify it's listed
    list_fn = mcp._tool_manager._tools["list_auth_credentials"].fn
    list_result = list_fn()
    assert "test_service" in list_result["credentials"]

    # 3. Use it in an auth task
    task_fn = mcp._tool_manager._tools["browser_use_auth_task"].fn
    task_result = await task_fn(
        task="Log into the service",
        credential_ref="test_service",
        provider="anthropic",
        model="claude-3-5-sonnet-20241022"
    )
    assert task_result["success"] is True

    # 4. Delete it
    delete_fn = mcp._tool_manager._tools["delete_auth_credential"].fn
    delete_result = delete_fn(ref_id="test_service")
    assert delete_result["success"] is True

    # 5. Verify it's gone
    list_result = list_fn()
    assert "test_service" not in list_result["credentials"]

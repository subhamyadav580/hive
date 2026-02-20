"""
LLM provider credentials.

Contains credentials for language model providers like Anthropic, OpenAI, etc.
"""

from .base import CredentialSpec

LLM_CREDENTIALS = {
    "anthropic": CredentialSpec(
        env_var="ANTHROPIC_API_KEY",
        tools=["browser_use_task", "browser_use_auth_task", "browser_use_vision_task"],
        node_types=["llm_generate", "llm_tool_use"],
        required=False,  # Not required - agents can use other providers via LiteLLM
        startup_required=False,  # MCP server doesn't need LLM credentials
        help_url="https://console.anthropic.com/settings/keys",
        description="API key for Anthropic Claude models",
        # Auth method support
        direct_api_key_supported=True,
        api_key_instructions="""To get an Anthropic API key:
1. Go to https://console.anthropic.com/settings/keys
2. Sign in or create an Anthropic account
3. Click "Create Key"
4. Give your key a descriptive name (e.g., "Hive Agent" or "Browser Automation")
5. Copy the API key (starts with sk-ant-)
6. Store it securely - you won't be able to see the full key again!""",
        # Health check configuration
        health_check_endpoint="https://api.anthropic.com/v1/messages",
        health_check_method="POST",
        # Credential store mapping
        credential_id="anthropic",
        credential_key="api_key",
    ),
    "openai": CredentialSpec(
        env_var="OPENAI_API_KEY",
        tools=["browser_use_task", "browser_use_auth_task", "browser_use_vision_task"],
        node_types=["llm_generate", "llm_tool_use"],
        required=False,
        startup_required=False,
        help_url="https://platform.openai.com/api-keys",
        description="API key for OpenAI GPT models",
        # Auth method support
        direct_api_key_supported=True,
        api_key_instructions="""To get an OpenAI API key:
1. Go to https://platform.openai.com/api-keys
2. Sign in or create an OpenAI account
3. Click "Create new secret key"
4. Give your key a name (e.g., "Hive Agent" or "Browser Automation")
5. Copy the API key (starts with sk-)
6. Store it securely - you won't be able to see it again!""",
        # Health check configuration
        health_check_endpoint="https://api.openai.com/v1/models",
        health_check_method="GET",
        # Credential store mapping
        credential_id="openai",
        credential_key="api_key",
    ),
    "groq": CredentialSpec(
        env_var="GROQ_API_KEY",
        tools=["browser_use_task", "browser_use_auth_task", "browser_use_vision_task"],
        node_types=["llm_generate", "llm_tool_use"],
        required=False,
        startup_required=False,
        help_url="https://console.groq.com/keys",
        description="API key for Groq LLM models (fast inference)",
        # Auth method support
        direct_api_key_supported=True,
        api_key_instructions="""To get a Groq API key:
1. Go to https://console.groq.com/keys
2. Sign in or create a Groq account
3. Click "Create API Key"
4. Give your key a name (e.g., "Hive Agent" or "Browser Automation")
5. Copy the API key (starts with gsk_)
6. Store it securely!""",
        # Health check configuration
        health_check_endpoint="https://api.groq.com/openai/v1/models",
        health_check_method="GET",
        # Credential store mapping
        credential_id="groq",
        credential_key="api_key",
    ),
    "azure_openai": CredentialSpec(
        env_var="AZURE_OPENAI_API_KEY",
        tools=["browser_use_task", "browser_use_auth_task", "browser_use_vision_task"],
        node_types=["llm_generate", "llm_tool_use"],
        required=False,
        startup_required=False,
        help_url="https://portal.azure.com/",
        description="API key for Azure OpenAI Service",
        # Auth method support
        direct_api_key_supported=True,
        api_key_instructions="""To get an Azure OpenAI API key:
1. Go to Azure Portal (https://portal.azure.com/)
2. Navigate to your Azure OpenAI resource
3. Go to "Keys and Endpoint" in the left menu
4. Copy either KEY 1 or KEY 2
5. Also set AZURE_OPENAI_ENDPOINT environment variable with your endpoint URL
6. Note your deployment name (this becomes your model parameter)

Example:
  export AZURE_OPENAI_API_KEY="your-key-here"
  export AZURE_OPENAI_ENDPOINT="https://your-resource.openai.azure.com/"

Then use your deployment name as the model parameter.""",
        # Health check configuration
        health_check_endpoint="",  # Varies by deployment
        health_check_method="GET",
        # Credential store mapping
        credential_id="azure_openai",
        credential_key="api_key",
    )
}

"""
================================================================================
DIFY API CONFIGURATION
================================================================================

Configuration file for real Dify API endpoints and credentials.
Using the actual Dify workflow applications for the Actionable Tasks panel.

================================================================================
"""

import os
from typing import Dict, Any

# ============================================================================
# DIFY API ENDPOINTS
# ============================================================================

# Base URL for Dify API
DIFY_BASE_URL = os.getenv("DIFY_BASE_URL", "http://171.88.165.251:40800/v1")

# Workflow Application API Keys
DIFY_WORKFLOW_KEYS = {
    "prompt_generator": os.getenv("DIFY_PROMPT_GENERATOR_KEY", ""),
    "auto_suggestion": os.getenv("DIFY_AUTO_SUGGESTION_KEY", ""),
    "insight_app": os.getenv("DIFY_INSIGHT_APP_KEY", ""),
    "feishu_todo_demo": os.getenv("DIFY_FEISHU_TODO_DEMO_KEY", ""),  # New Feishu Demo App
    "feishu_executor": os.getenv("DIFY_FEISHU_EXECUTOR_KEY", ""),
    "email_executor": os.getenv("DIFY_EMAIL_EXECUTOR_KEY", ""),
    "docFeishu_executor": os.getenv("DIFY_DOCFEISHU_EXECUTOR_KEY", ""),
    "sop_generator": os.getenv("DIFY_SOP_GENERATOR_KEY", "")
}

# Chat Application API Keys (for conversation-based APIs)
# Note: Agent type apps also use chat-messages endpoint
DIFY_CHAT_KEYS = {
    "hippo_chat": os.getenv("DIFY_HIPPO_CHAT_KEY", ""),
    "hippo_agent": os.getenv("DIFY_HIPPO_AGENT_KEY", "")
}

# NOTE: Workflow Application IDs are NOT needed for API calls.
# Dify's workflow API uses the API key (in DIFY_WORKFLOW_KEYS above) to identify
# which workflow to execute. The /workflows/run endpoint with Bearer token authentication
# automatically routes to the correct workflow based on the API key used.
#
# The workflow IDs below are kept for reference/documentation purposes only:
# - prompt_generator: c5ea5d79-e06d-479c-aa0e-95142e724769
# - auto_suggestion: 31d3715d-f1f2-4fc9-a550-bab801c8b8cf
# - insight_app: 1d103dfe-da2f-4dae-b85a-a5c54bca1723
# - feishu_todo_demo: 702f080a-ee48-40d7-a1fd-51bd0fd21d35
# - feishu_executor: 54244b8d-e17c-462e-8537-8d15eef22db8
# - email_executor: 7096c794-d6e8-471f-8693-d8a3b4e3c475
# - docFeishu_executor: 488020da-2ba5-4e4b-91ff-56c1887b8a79

# Specific workflow endpoints 
DIFY_ENDPOINTS = {
    # Main workflow execution endpoint
    "workflow_run": f"{DIFY_BASE_URL}/workflows/run",
    "workflow_run_specific": f"{DIFY_BASE_URL}/workflows/{{workflow_id}}/run",
    "workflow_status": f"{DIFY_BASE_URL}/workflows/run/{{workflow_run_id}}",
    "workflow_stop": f"{DIFY_BASE_URL}/workflows/tasks/{{task_id}}/stop",
    
    # Chat application endpoints
    "chat_messages": f"{DIFY_BASE_URL}/chat-messages",
    "chat_messages_stop": f"{DIFY_BASE_URL}/chat-messages/{{task_id}}/stop",
    "chat_conversations": f"{DIFY_BASE_URL}/conversations",
    
    # File upload endpoint
    "file_upload": f"{DIFY_BASE_URL}/files/upload",
    
    # Info endpoints
    "app_info": f"{DIFY_BASE_URL}/info",
    "app_parameters": f"{DIFY_BASE_URL}/parameters",
}

# ============================================================================
# REQUEST CONFIGURATION
# ============================================================================

# Timeout settings (in seconds)
DIFY_TIMEOUT_START = 30  # Timeout for starting recording
DIFY_TIMEOUT_STOP = 120  # Timeout for stopping and processing (longer due to AI processing)
DIFY_TIMEOUT_STATUS = 10  # Timeout for status checks

# Retry configuration
DIFY_MAX_RETRIES = 3
DIFY_RETRY_DELAY = 1  # Initial delay in seconds (will use exponential backoff)

# ============================================================================
# RESPONSE FORMAT CONFIGURATION
# ============================================================================

# Expected response format from Dify (for validation)
EXPECTED_RESPONSE_FIELDS = {
    "start": ["session_id", "status", "start_time"],
    "stop": ["session_id", "user_context", "prompt_suggestions", "summary_feed"],
    "status": ["session_id", "status", "is_recording"]
}

# ============================================================================
# DEVELOPMENT/TESTING
# ============================================================================

# Use mock responses for development (set to False when Dify APIs are ready)
USE_MOCK_RESPONSES = os.getenv("USE_MOCK_DIFY", "true").lower() == "true"

# Enable detailed logging
ENABLE_DIFY_LOGGING = os.getenv("ENABLE_DIFY_LOGGING", "true").lower() == "true"

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_dify_headers(workflow_key: str = None, content_type: str = "application/json") -> Dict[str, str]:
    """
    Get headers for Dify API requests
    
    Args:
        workflow_key: The specific workflow key to use (e.g., 'prompt_generator', 'insight_app')
        content_type: The content type for the request (default: 'application/json')
    
    Returns:
        Headers dictionary for the API request
    """
    api_key = DIFY_WORKFLOW_KEYS.get(workflow_key) if workflow_key else None
    
    if not api_key:
        raise ValueError(f"No API key found for workflow: {workflow_key}")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    if content_type:
        headers["Content-Type"] = content_type
    
    return headers


def get_chat_headers(chat_key: str = None, content_type: str = "application/json") -> Dict[str, str]:
    """
    Get headers for Dify Chat API requests
    
    Args:
        chat_key: The specific chat app key to use (e.g., 'hippo_chat')
        content_type: The content type for the request (default: 'application/json')
    
    Returns:
        Headers dictionary for the API request
    """
    api_key = DIFY_CHAT_KEYS.get(chat_key) if chat_key else None
    
    if not api_key:
        raise ValueError(f"No API key found for chat app: {chat_key}")
    
    headers = {
        "Authorization": f"Bearer {api_key}",
    }
    
    if content_type:
        headers["Content-Type"] = content_type
    
    return headers

def validate_dify_config():
    """
    Validate that Dify configuration is properly set
    Returns: (is_valid, error_message)
    """
    if not DIFY_BASE_URL:
        return False, "Dify base URL is not configured"
    
    # Check if at least one workflow key is configured
    if not any(DIFY_WORKFLOW_KEYS.values()):
        return False, "No Dify workflow API keys are configured"
    
    return True, None

def get_endpoint(operation: str, **kwargs) -> str:
    """
    Get the endpoint URL for a specific operation
    
    Args:
        operation: The operation name (e.g., 'workflow_run', 'file_upload')
        **kwargs: Additional parameters to format the URL (e.g., workflow_id, task_id)
    
    Returns:
        The full endpoint URL
    """
    endpoint = DIFY_ENDPOINTS.get(operation, f"{DIFY_BASE_URL}/{operation}")
    
    # Format the endpoint with any provided parameters
    if kwargs:
        endpoint = endpoint.format(**kwargs)
    
    return endpoint

# ============================================================================
# EXAMPLE USAGE
# ============================================================================

"""
Example of how to use this configuration:

```python
from dify_config import (
    DIFY_API_KEY,
    DIFY_BASE_URL,
    get_dify_headers,
    get_endpoint,
    validate_dify_config
)

# Validate configuration
is_valid, error = validate_dify_config()
if not is_valid:
    print(f"Configuration error: {error}")
    exit(1)

# Use in API calls
import httpx

async def call_dify_api():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            get_endpoint("start_recording"),
            headers=get_dify_headers(),
            json={"user_id": "123"},
            timeout=30.0
        )
        return response.json()
```
"""

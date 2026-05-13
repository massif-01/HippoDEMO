"""
================================================================================
CONFIGURATION FILE FOR API INTEGRATIONS
================================================================================

This file manages all API configurations and credentials.
Copy config.example.py to config.py and fill in your actual API keys.

SECURITY NOTE: Never commit this file with real API keys to version control!
Add 'backend/config.py' to your .gitignore file.
================================================================================
"""

import os
from typing import Optional

# ============================================================================
# API KEYS - Set these as environment variables or directly here
# ============================================================================

# OpenAI Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_API_ENDPOINT = os.getenv("OPENAI_API_ENDPOINT", "https://api.openai.com/v1")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4-turbo-preview")
OPENAI_VISION_MODEL = os.getenv("OPENAI_VISION_MODEL", "gpt-4-vision-preview")

# Anthropic Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_API_ENDPOINT = os.getenv("ANTHROPIC_API_ENDPOINT", "https://api.anthropic.com/v1")
ANTHROPIC_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-3-opus-20240229")

# Google Cloud Configuration
GOOGLE_CLOUD_KEY = os.getenv("GOOGLE_CLOUD_KEY", "")
GOOGLE_CLOUD_PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")

# AWS Configuration (for Textract, Rekognition, etc.)
AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID", "")
AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY", "")
AWS_REGION = os.getenv("AWS_REGION", "us-east-1")

# Azure Configuration
AZURE_SUBSCRIPTION_KEY = os.getenv("AZURE_SUBSCRIPTION_KEY", "")
AZURE_ENDPOINT = os.getenv("AZURE_ENDPOINT", "")

# Local LLM Configuration (Ollama, LM Studio, etc.)
LOCAL_LLM_ENDPOINT = os.getenv("LOCAL_LLM_ENDPOINT", "http://localhost:11434")
LOCAL_LLM_MODEL = os.getenv("LOCAL_LLM_MODEL", "llama2")

# ============================================================================
# FEATURE FLAGS - Enable/disable specific features
# ============================================================================

# Which AI provider to use for vision processing
VISION_PROVIDER = os.getenv("VISION_PROVIDER", "openai")  # Options: openai, anthropic, google, azure, aws

# Which AI provider to use for text generation
TEXT_PROVIDER = os.getenv("TEXT_PROVIDER", "openai")  # Options: openai, anthropic, local

# Enable real screen recording (requires additional setup)
ENABLE_REAL_RECORDING = os.getenv("ENABLE_REAL_RECORDING", "false").lower() == "true"

# Enable caching of AI responses (recommended for development)
ENABLE_CACHE = os.getenv("ENABLE_CACHE", "true").lower() == "true"

# ============================================================================
# RECORDING CONFIGURATION
# ============================================================================

# Screen recording settings
RECORDING_FPS = int(os.getenv("RECORDING_FPS", "1"))  # Frames per second for screen capture
RECORDING_QUALITY = int(os.getenv("RECORDING_QUALITY", "80"))  # JPEG quality (1-100)
MAX_RECORDING_DURATION = int(os.getenv("MAX_RECORDING_DURATION", "300"))  # Maximum recording duration in seconds

# Processing settings
MAX_SCREENSHOTS_PER_SESSION = int(os.getenv("MAX_SCREENSHOTS_PER_SESSION", "10"))
PROCESS_EVERY_N_FRAMES = int(os.getenv("PROCESS_EVERY_N_FRAMES", "5"))  # Process every Nth frame to save API calls

# ============================================================================
# PROMPT TEMPLATES
# ============================================================================

VISION_ANALYSIS_PROMPT = """Analyze this screenshot and extract:
1. All visible text content
2. The application or website being used
3. What the user appears to be doing
4. Any code snippets visible
5. Important UI elements, data, or information
6. The overall context of the activity

Format your response as structured text with clear sections."""

CONTEXT_GENERATION_PROMPT = """Based on these screen recording observations, create a comprehensive markdown summary:

{observations}

Structure the output as:
# Screen Recording Summary

## Activities Captured
- List main activities observed

## Key Information Extracted  
- Important data, URLs, resources

## Code Snippets Observed
- Any code that was visible

## Context and Insights
- What the user was working on
- Key patterns or workflows observed

## Recommendations
- Suggestions based on observed activities"""

PROMPT_SUGGESTION_PROMPT = """Based on this screen recording context, generate 5 highly relevant and specific prompt suggestions that would help the user with their current work:

{context}

Make the prompts:
1. Specific to what the user was doing
2. Actionable and helpful
3. Varied in scope (some focused, some broader)
4. Related to observed problems or tasks

Return as a JSON array with 'id' and 'text' fields."""

TASK_EXTRACTION_PROMPT = """Analyze this screen recording context and extract:

{context}

1. Key insights about the work being done
2. Actionable tasks the user should complete
3. Potential issues or improvements

Return as JSON with 'insights' (markdown string) and 'tasks' (array of objects with id, text, completed fields)."""

# ============================================================================
# DATABASE CONFIGURATION (if using persistent storage)
# ============================================================================

DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./recording_sessions.db")
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")

# ============================================================================
# HELPER FUNCTIONS
# ============================================================================

def get_vision_api_config():
    """Get configuration for the selected vision provider"""
    configs = {
        "openai": {
            "api_key": OPENAI_API_KEY,
            "endpoint": OPENAI_API_ENDPOINT,
            "model": OPENAI_VISION_MODEL
        },
        "anthropic": {
            "api_key": ANTHROPIC_API_KEY,
            "endpoint": ANTHROPIC_API_ENDPOINT,
            "model": ANTHROPIC_MODEL
        },
        "google": {
            "api_key": GOOGLE_CLOUD_KEY,
            "project": GOOGLE_CLOUD_PROJECT
        },
        "azure": {
            "subscription_key": AZURE_SUBSCRIPTION_KEY,
            "endpoint": AZURE_ENDPOINT
        },
        "aws": {
            "access_key": AWS_ACCESS_KEY_ID,
            "secret_key": AWS_SECRET_ACCESS_KEY,
            "region": AWS_REGION
        }
    }
    return configs.get(VISION_PROVIDER, configs["openai"])

def get_text_api_config():
    """Get configuration for the selected text generation provider"""
    configs = {
        "openai": {
            "api_key": OPENAI_API_KEY,
            "endpoint": OPENAI_API_ENDPOINT,
            "model": OPENAI_MODEL
        },
        "anthropic": {
            "api_key": ANTHROPIC_API_KEY,
            "endpoint": ANTHROPIC_API_ENDPOINT,
            "model": ANTHROPIC_MODEL
        },
        "local": {
            "endpoint": LOCAL_LLM_ENDPOINT,
            "model": LOCAL_LLM_MODEL
        }
    }
    return configs.get(TEXT_PROVIDER, configs["openai"])

def validate_configuration() -> tuple[bool, list[str]]:
    """
    Validate that required configuration is present
    Returns: (is_valid, list_of_errors)
    """
    errors = []
    
    # Check vision provider configuration
    vision_config = get_vision_api_config()
    if VISION_PROVIDER == "openai" and not vision_config.get("api_key"):
        errors.append("OpenAI API key is required for vision processing")
    elif VISION_PROVIDER == "anthropic" and not vision_config.get("api_key"):
        errors.append("Anthropic API key is required for vision processing")
    elif VISION_PROVIDER == "google" and not vision_config.get("api_key"):
        errors.append("Google Cloud API key is required for vision processing")
    
    # Check text provider configuration
    text_config = get_text_api_config()
    if TEXT_PROVIDER == "openai" and not text_config.get("api_key"):
        errors.append("OpenAI API key is required for text generation")
    elif TEXT_PROVIDER == "anthropic" and not text_config.get("api_key"):
        errors.append("Anthropic API key is required for text generation")
    
    return (len(errors) == 0, errors)

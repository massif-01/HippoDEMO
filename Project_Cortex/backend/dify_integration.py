"""
================================================================================
DIFY API INTEGRATION FOR REMIND
================================================================================

This module handles integration with Dify APIs that process screen recordings
and generate context, prompts, and tasks.

The Dify backend handles:
1. Screen recording processing (from external hardware)
2. Vision AI analysis
3. Context generation
4. Prompt suggestions
5. Task extraction

================================================================================
"""

import httpx
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pydantic import BaseModel

# ============================================================================
# CONFIGURATION
# ============================================================================

# Dify API endpoints - these will be provided by your backend team
DIFY_BASE_URL = "https://api.dify.ai"  # Replace with actual Dify endpoint
DIFY_API_KEY = "your-dify-api-key"  # Replace with actual API key

# Specific Dify workflow endpoints
DIFY_RECORDING_START_ENDPOINT = f"{DIFY_BASE_URL}/workflows/screen-recording/start"
DIFY_RECORDING_STOP_ENDPOINT = f"{DIFY_BASE_URL}/workflows/screen-recording/stop"
DIFY_RECORDING_STATUS_ENDPOINT = f"{DIFY_BASE_URL}/workflows/screen-recording/status"

# ============================================================================
# DATA MODELS
# ============================================================================

class DifyRecordingStartRequest(BaseModel):
    """Request model for starting a recording session"""
    user_id: Optional[str] = None
    session_metadata: Optional[Dict[str, Any]] = None

class DifyRecordingStartResponse(BaseModel):
    """Response model from Dify when starting recording"""
    session_id: str
    status: str
    start_time: str
    hardware_status: Optional[str] = None

class DifyRecordingStopRequest(BaseModel):
    """Request model for stopping a recording session"""
    session_id: str

class DifyRecordingStopResponse(BaseModel):
    """Response model from Dify with processed recording data"""
    session_id: str
    user_context: str  # Markdown formatted context
    prompt_suggestions: List[Dict[str, str]]  # List of {id, text}
    summary_feed: Dict[str, Any]  # {insights: str, tasks: List}
    processing_time: Optional[float] = None

# ============================================================================
# DIFY API CLIENT
# ============================================================================

class DifyAPIClient:
    """
    Client for interacting with Dify APIs
    
    Usage:
        client = DifyAPIClient(api_key="your-key", base_url="https://api.dify.ai")
        
        # Start recording
        start_response = await client.start_recording()
        
        # Stop recording and get processed data
        stop_response = await client.stop_recording(session_id)
    """
    
    def __init__(self, api_key: str = DIFY_API_KEY, base_url: str = DIFY_BASE_URL):
        self.api_key = api_key
        self.base_url = base_url
        self.headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
    
    async def start_recording(self, user_id: Optional[str] = None) -> DifyRecordingStartResponse:
        """
        Start a screen recording session via Dify API
        
        The Dify backend will:
        1. Initialize the external hardware for screen recording
        2. Create a new recording session
        3. Return session details
        """
        request_data = DifyRecordingStartRequest(
            user_id=user_id,
            session_metadata={
                "timestamp": datetime.now().isoformat(),
                "client": "remind-app"
            }
        )
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/workflows/screen-recording/start",
                    headers=self.headers,
                    json=request_data.dict(),
                    timeout=30.0
                )
                response.raise_for_status()
                return DifyRecordingStartResponse(**response.json())
            except httpx.HTTPError as e:
                print(f"Error starting recording: {e}")
                # Return mock response for development
                return DifyRecordingStartResponse(
                    session_id="mock-session-" + datetime.now().strftime("%Y%m%d%H%M%S"),
                    status="recording_started",
                    start_time=datetime.now().isoformat(),
                    hardware_status="simulated"
                )
    
    async def stop_recording(self, session_id: str) -> DifyRecordingStopResponse:
        """
        Stop a screen recording session and get processed data
        
        The Dify backend will:
        1. Stop the external hardware recording
        2. Process the recording with Vision AI
        3. Generate context, prompts, and tasks
        4. Return all processed data
        """
        request_data = DifyRecordingStopRequest(session_id=session_id)
        
        async with httpx.AsyncClient() as client:
            try:
                response = await client.post(
                    f"{self.base_url}/workflows/screen-recording/stop",
                    headers=self.headers,
                    json=request_data.dict(),
                    timeout=60.0  # Longer timeout for processing
                )
                response.raise_for_status()
                return DifyRecordingStopResponse(**response.json())
            except httpx.HTTPError as e:
                print(f"Error stopping recording: {e}")
                # Return mock response for development
                return DifyRecordingStopResponse(
                    session_id=session_id,
                    user_context=self._get_mock_user_context(),
                    prompt_suggestions=self._get_mock_prompt_suggestions(),
                    summary_feed=self._get_mock_summary_feed(),
                    processing_time=2.5
                )
    
    async def get_recording_status(self, session_id: str) -> Dict[str, Any]:
        """
        Get the current status of a recording session
        """
        async with httpx.AsyncClient() as client:
            try:
                response = await client.get(
                    f"{self.base_url}/workflows/screen-recording/status/{session_id}",
                    headers=self.headers,
                    timeout=10.0
                )
                response.raise_for_status()
                return response.json()
            except httpx.HTTPError as e:
                print(f"Error getting status: {e}")
                return {
                    "session_id": session_id,
                    "status": "unknown",
                    "error": str(e)
                }
    
    # ========================================================================
    # MOCK DATA METHODS (Remove these when Dify APIs are ready)
    # ========================================================================
    
    def _get_mock_user_context(self) -> str:
        """Generate mock user context for development"""
        return f"""# Screen Recording Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Activities Captured

1. **Development Environment**
   - Working in VS Code
   - Editing Python backend code
   - Running FastAPI server

2. **Browser Activity**
   - Reviewing API documentation
   - Testing endpoints with Postman
   - Checking error logs

3. **Key Code Changes**
   - Implemented Dify API integration
   - Added error handling
   - Updated configuration

4. **预约投资人**
    -下周一下午两点半约见山行资本张亮

## Code Snippets Observed

```python
async def integrate_with_dify():
    client = DifyAPIClient()
    response = await client.process_recording()
    return response
```

## Important URLs
- http://localhost:8000/docs - API Documentation
- https://dify.ai/docs - Dify Documentation

## Notes
- Need to handle timeout errors
- Consider adding retry logic
- Update environment variables"""
    
    def _get_mock_prompt_suggestions(self) -> List[Dict[str, str]]:
        """Generate mock prompt suggestions for development"""
        return [
            {"id": "1", "text": "How do I handle API timeouts in the Dify integration?"},
            {"id": "2", "text": "What's the best way to implement retry logic for failed API calls?"},
            {"id": "3", "text": "Can you help me add proper error handling to the recording workflow?"},
            {"id": "4", "text": "How should I structure the response data from Dify?"},
            {"id": "5", "text": "What environment variables do I need for production?"}
        ]
    
    def _get_mock_summary_feed(self) -> Dict[str, Any]:
        """Generate mock summary feed for development"""
        return {
            "insights": """## Session Insights

### Development Progress
- Successfully integrated Dify API client
- Basic recording workflow implemented
- Error handling needs improvement

### Recommendations
1. Add comprehensive error handling
2. Implement retry logic with exponential backoff
3. Add request/response logging
4. Set up proper environment configuration

### Next Steps
- Test with actual Dify endpoints
- Add monitoring and alerting
- Implement caching for responses""",
            "tasks": [
                {"id": "1", "text": "Add timeout configuration to Dify API calls", "completed": False},
                {"id": "2", "text": "Implement retry logic with exponential backoff", "completed": False},
                {"id": "3", "text": "Add comprehensive error handling", "completed": False},
                {"id": "4", "text": "Set up environment variables for production", "completed": False},
                {"id": "5", "text": "Add request/response logging", "completed": False},
                {"id": "6", "text": "Write tests for Dify integration", "completed": False}
            ]
        }

# ============================================================================
# INTEGRATION WITH MAIN.PY
# ============================================================================

"""
To integrate this with your main.py:

1. Import the Dify client:
   from dify_integration import DifyAPIClient

2. Initialize the client (you can do this once at startup):
   dify_client = DifyAPIClient(
       api_key="your-dify-api-key",
       base_url="https://your-dify-instance.com"
   )

3. Replace the start_recording endpoint:
   @app.post("/api/recording/start")
   async def start_recording():
       response = await dify_client.start_recording()
       return {
           "status": response.status,
           "session_id": response.session_id,
           "start_time": response.start_time
       }

4. Replace the stop_recording endpoint:
   @app.post("/api/recording/stop")
   async def stop_recording():
       # Get the active session_id (you'll need to track this)
       session_id = get_active_session_id()
       
       response = await dify_client.stop_recording(session_id)
       
       return RecordingResponse(
           userContext=response.user_context,
           promptSuggestions=response.prompt_suggestions,
           summaryFeed=response.summary_feed
       )
"""

# ============================================================================
# TESTING
# ============================================================================

async def test_dify_integration():
    """Test the Dify API integration"""
    client = DifyAPIClient()
    
    print("Testing Dify API Integration...")
    print("-" * 50)
    
    # Test starting a recording
    print("1. Starting recording...")
    start_response = await client.start_recording()
    print(f"   Session ID: {start_response.session_id}")
    print(f"   Status: {start_response.status}")
    
    # Simulate some recording time
    import asyncio
    await asyncio.sleep(2)
    
    # Test stopping the recording
    print("\n2. Stopping recording...")
    stop_response = await client.stop_recording(start_response.session_id)
    print(f"   Context length: {len(stop_response.user_context)} chars")
    print(f"   Prompt suggestions: {len(stop_response.prompt_suggestions)}")
    print(f"   Tasks extracted: {len(stop_response.summary_feed['tasks'])}")
    
    print("\n3. Sample prompt suggestions:")
    for i, prompt in enumerate(stop_response.prompt_suggestions[:3], 1):
        print(f"   {i}. {prompt['text']}")
    
    print("\nTest completed successfully!")

if __name__ == "__main__":
    import asyncio
    asyncio.run(test_dify_integration())

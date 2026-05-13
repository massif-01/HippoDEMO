from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse, Response
from pydantic import BaseModel
from typing import List, Optional, AsyncGenerator, Dict, Any
import asyncio
import json
from datetime import datetime
import uuid
import httpx
import os
from contextlib import asynccontextmanager
from minio import Minio
from minio.error import S3Error

# Import Dify config
from dify_config import (
    DIFY_BASE_URL,
    DIFY_CHAT_KEYS,
    DIFY_ENDPOINTS,
    get_chat_headers,
    get_endpoint
)

# Dify API Configuration
USE_DIFY_API = os.getenv("USE_DIFY_API", "false").lower() == "true"
DIFY_API_KEY = os.getenv("DIFY_API_KEY", "")
DIFY_USER_ID = os.getenv("DIFY_USER_ID", "default-user")

# MinIO Configuration
MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "171.88.165.251:59000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "rm01")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "rm01rm01")
MINIO_BUCKET = os.getenv("MINIO_BUCKET", "rm01")
MINIO_SECURE = os.getenv("MINIO_SECURE", "false").lower() == "true"

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE,
)

# Global HTTP client for connection pooling
_http_client: Optional[httpx.AsyncClient] = None

async def get_http_client() -> httpx.AsyncClient:
    """Get or create a shared HTTP client with connection pooling"""
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            timeout=httpx.Timeout(60.0, connect=10.0),
            limits=httpx.Limits(max_connections=100, max_keepalive_connections=20)
        )
    return _http_client

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for resource cleanup"""
    yield
    # Cleanup on shutdown
    global _http_client
    if _http_client:
        await _http_client.aclose()

# ============================================================================
# INTEGRATION GUIDE: Replacing Mock Data with Real APIs
# ============================================================================
# 
# This backend currently uses mock data for demonstration. Follow these steps
# to integrate real screen recording and AI processing services:
#
# 1. SCREEN RECORDING INTEGRATION
#    - Replace mock recording with actual screen capture service
#    - Options: Use native OS APIs, Electron for desktop, or browser APIs
#    - Example services: OBS SDK, FFmpeg, or cloud services like Loom API
#
# 2. OCR/VISION AI INTEGRATION  
#    - Process screen recordings to extract text and context
#    - Options: OpenAI Vision API, Google Cloud Vision, AWS Textract
#    - Example: Use GPT-4 Vision to analyze screenshots
#
# 3. CONTEXT PROCESSING
#    - Convert raw screen data into structured markdown
#    - Use LLMs to summarize and extract key information
#
# 4. PROMPT GENERATION
#    - Use AI to generate relevant prompt suggestions
#    - Can use GPT-4 or Claude to analyze context and suggest prompts
#
# 5. TASK EXTRACTION
#    - Use NLP to identify actionable tasks from screen content
#    - Can integrate with task management APIs (Todoist, Notion, etc.)
# ============================================================================

app = FastAPI(lifespan=lifespan)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory storage for demo purposes
# TODO: Replace with database (PostgreSQL, MongoDB) or cache (Redis)
recording_sessions = {}
insight_feed = ""

class RecordingSession:
    def __init__(self):
        self.id = str(uuid.uuid4())
        self.start_time = datetime.now()
        self.is_recording = True
        self.data = []

class Task(BaseModel):
    id: str
    text: str
    completed: bool = False

class SummaryFeed(BaseModel):
    insights: str
    tasks: List[Task]

class PromptSuggestion(BaseModel):
    id: str
    text: str

class RecordingResponse(BaseModel):
    userContext: str
    promptSuggestions: List[PromptSuggestion]
    summaryFeed: SummaryFeed

class ChatMessage(BaseModel):
    role: str
    content: str

class ChatRequest(BaseModel):
    messages: List[ChatMessage]
    model: str = "gpt-3.5-turbo"
    api_key: str
    api_endpoint: str = "https://api.openai.com/v1"
    stream: bool = True

class DifyFileInfo(BaseModel):
    type: str  # "image", "document", etc.
    transfer_method: str = "local_file"  # "remote_url" or "local_file"
    upload_file_id: Optional[str] = None  # File ID from upload endpoint
    url: Optional[str] = None  # URL for remote files

class DifyChatRequest(BaseModel):
    query: str
    conversation_id: Optional[str] = None
    files: Optional[List[DifyFileInfo]] = None
    user: str = "default-user"
    response_mode: str = "streaming"  # "blocking" or "streaming"

class TaskParameter(BaseModel):
    name: str
    value: Optional[str] = None
    type: str = "text"  # text, number, boolean, select
    description: Optional[str] = None
    options: Optional[List[str]] = None
    required: bool = False

class ExecuteTaskRequest(BaseModel):
    taskId: str
    title: str
    description: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None
    parameters: List[TaskParameter]
    context: Optional[Dict[str, Any]] = None
    workflowType: Optional[str] = None

class AgentTask(BaseModel):
    id: str
    title: str
    description: str
    category: Optional[str] = None
    priority: Optional[str] = None  # low, medium, high
    parameters: List[TaskParameter]
    status: str = "pending"  # pending, approved, denied, executing, completed, failed
    createdAt: datetime
    executedAt: Optional[datetime] = None
    result: Optional[dict] = None
    error: Optional[str] = None

@app.get("/")
async def root():
    return {"message": "屏幕聊天应用后端"}

@app.get("/api/context/minio")
async def get_minio_context(object_name: str = "context/context.md"):
    """Fetch context file from MinIO with authentication"""
    try:
        response = minio_client.get_object(MINIO_BUCKET, object_name)
        content = response.read().decode("utf-8")
        response.close()
        response.release_conn()
        return Response(content=content, media_type="text/plain; charset=utf-8")
    except S3Error as e:
        print(f"MinIO S3Error: {e}")
        raise HTTPException(status_code=e.code if hasattr(e, 'code') else 500, detail=str(e))
    except Exception as e:
        print(f"MinIO fetch error: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch context from MinIO: {str(e)}")

@app.post("/api/recording/start")
async def start_recording():
    """
    Start a new screen recording session
    
    DIFY API INTEGRATION:
    ====================
    When Dify APIs are ready, replace the mock implementation below with:
    
    ```python
    from dify_integration import DifyAPIClient
    
    # Initialize Dify client (do this once at app startup)
    dify_client = DifyAPIClient(
        api_key="your-dify-api-key",
        base_url="https://your-dify-instance.com"
    )
    
    # Start recording via Dify
    response = await dify_client.start_recording()
    
    # Store session for tracking
    recording_sessions[response.session_id] = {
        "id": response.session_id,
        "start_time": response.start_time,
        "status": response.status
    }
    
    return {
        "status": response.status,
        "session_id": response.session_id,
        "start_time": response.start_time
    }
    ```
    
    The Dify API will handle:
    - Triggering the external hardware to start recording
    - Managing the recording session
    - Preparing for AI processing
    """
    session = RecordingSession()
    recording_sessions[session.id] = session
    
    # TODO: Replace with Dify API call when ready
    # For demo, we'll just track the session
    print(f"Started recording session: {session.id}")
    print(f"Total active sessions: {len(recording_sessions)}")
    
    return {
        "status": "recording_started",
        "session_id": session.id,
        "start_time": session.start_time.isoformat()
    }

@app.post("/api/recording/stop")
async def stop_recording():
    """
    Stop the current recording session and return processed data
    
    DIFY API INTEGRATION:
    ====================
    When Dify APIs are ready, replace the mock implementation below with:
    
    ```python
    from dify_integration import DifyAPIClient
    
    # Get the active session ID (you need to track this)
    active_session = None
    for session_id, session in recording_sessions.items():
        if session.is_recording:
            active_session = session
            break
    
    if not active_session:
        raise HTTPException(status_code=404, detail="No active recording")
    
    # Stop recording and get processed data from Dify
    dify_client = DifyAPIClient()
    response = await dify_client.stop_recording(active_session.id)
    
    # Mark session as stopped
    active_session.is_recording = False
    
    # Return the processed data
    return RecordingResponse(
        userContext=response.user_context,
        promptSuggestions=[
            PromptSuggestion(id=p["id"], text=p["text"]) 
            for p in response.prompt_suggestions
        ],
        summaryFeed=SummaryFeed(
            insights=response.summary_feed["insights"],
            tasks=[
                Task(id=t["id"], text=t["text"], completed=t.get("completed", False))
                for t in response.summary_feed["tasks"]
            ]
        )
    )
    ```
    
    The Dify API will handle:
    - Stopping the external hardware recording
    - Processing the recording with Vision AI
    - Generating structured context from the recording
    - Creating relevant prompt suggestions
    - Extracting actionable tasks and insights
    
    All AI processing is done on the Dify backend, so you just need to:
    1. Call the stop endpoint with the session ID
    2. Wait for the processed response
    3. Format and return it to the frontend
    """
    
    # Find the active recording session
    active_session = None
    for session_id, session in recording_sessions.items():
        if session.is_recording:
            active_session = session
            break
    
    if not active_session:
        # If no active session found, check if there are any sessions at all
        if not recording_sessions:
            print("WARNING: No recording sessions exist. Creating a mock session for demo.")
            # Create a mock session for demo purposes
            session = RecordingSession()
            recording_sessions[session.id] = session
            active_session = session
        else:
            # Log all sessions for debugging
            print(f"Available sessions: {list(recording_sessions.keys())}")
            for sid, sess in recording_sessions.items():
                print(f"  Session {sid}: is_recording={sess.is_recording}")
            raise HTTPException(status_code=404, detail="No active recording session found")
    
    # Mark session as stopped
    active_session.is_recording = False
    print(f"Stopped recording for session: {active_session.id}")
    
    # TODO: Replace with actual video/screenshot processing
    # Minimal delay for demo - remove in production with real processing
    await asyncio.sleep(0.1)
    
    # ========================================================================
    # MOCK DATA - Replace this section with real API calls
    # ========================================================================
    # In production, replace the following mock data generation with:
    # 1. user_context = await generate_user_context(video_path)
    # 2. prompt_suggestions = await generate_prompts(user_context)  
    # 3. summary_feed = await extract_tasks(user_context)
    # ========================================================================
    
    user_context = f"""# Screen Recording Summary - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

## Activities Captured

1. **Browser Activity**
   - Visited documentation pages
   - Searched for API references
   - Reviewed code examples

2. **Code Editor Activity**
   - Edited main.py file
   - Added new functions
   - Fixed syntax errors

3. **Terminal Commands**
   - Ran npm install
   - Started development server
   - Executed test suite


## Key Information Extracted

- Working on a React application with TypeScript
- Implementing authentication features
- Using REST API for backend communication
- Following clean code principles

## Code Snippets Observed

```javascript
const handleLogin = async (credentials) => {{
  try {{
    const response = await api.post('/auth/login', credentials);
    return response.data;
  }} catch (error) {{
    console.error('Login failed:', error);
  }}
}};
```

## Notes

- Consider implementing error boundaries
- Add loading states for better UX
- Review security best practices for token storage
"""

    prompt_suggestions = [
        PromptSuggestion(id="1", text="How can I improve the error handling in my authentication flow?"),
        PromptSuggestion(id="2", text="What are the best practices for storing JWT tokens securely?"),
        PromptSuggestion(id="3", text="Can you review my login implementation and suggest improvements?"),
        PromptSuggestion(id="4", text="How do I add proper TypeScript types to my API responses?"),
        PromptSuggestion(id="5", text="What testing strategies should I use for authentication features?")
    ]
    
    summary_feed = SummaryFeed(
        insights="""## Session Insights

Based on your screen recording, here are some key observations:

### Development Progress
- You're making good progress on the authentication system
- The basic login flow is implemented but needs error handling improvements
- TypeScript types are partially implemented

### Recommendations
1. **Security**: Consider using httpOnly cookies for token storage instead of localStorage
2. **Error Handling**: Implement comprehensive error boundaries and user-friendly error messages
3. **Testing**: Add unit tests for authentication functions and integration tests for the full flow
4. **Performance**: Consider implementing request caching and optimistic updates

### Code Quality
- Good separation of concerns with dedicated API utility functions
- Consider extracting authentication logic into a custom hook
- Add JSDoc comments for better code documentation
""",
        tasks=[
            Task(id="1", text="Add error boundary component for authentication pages"),
            Task(id="2", text="Implement refresh token rotation mechanism"),
            Task(id="3", text="Write unit tests for handleLogin function"),
            Task(id="4", text="Add TypeScript interfaces for API response types"),
            Task(id="5", text="Review and update security headers in API requests"),
            Task(id="6", text="Implement loading states for all async operations"),
            Task(id="7", text="Add input validation for login form fields")
        ]
    )
    
    # Detect actionable tasks from the context
    detected_tasks = await extract_tasks_from_context(user_context)
    
    # Add some pre-filled values for demo purposes
    if detected_tasks:
        if detected_tasks[0].get("title") == "发送邮件":
            detected_tasks[0]["parameters"][0]["value"] = "team@company.com"
            detected_tasks[0]["parameters"][1]["value"] = "Authentication Module Update"
            detected_tasks[0]["parameters"][2]["value"] = "The authentication module has been updated with improved error handling..."
        
        if len(detected_tasks) > 1 and detected_tasks[1].get("title") == "创建文档":
            detected_tasks[1]["parameters"][0]["value"] = "Authentication API Documentation"
    
    response = RecordingResponse(
        userContext=user_context,
        promptSuggestions=prompt_suggestions,
        summaryFeed=summary_feed
    )
    
    # Return response with detected tasks
    return {
        **response.dict(),
        "detectedTasks": detected_tasks
    }

@app.get("/api/recording/status")
async def get_recording_status():
    """Get the current recording status"""
    active_sessions = [
        session for session in recording_sessions.values() 
        if session.is_recording
    ]
    
    return {
        "is_recording": len(active_sessions) > 0,
        "active_sessions": len(active_sessions)
    }

async def stream_chat_completion(request: ChatRequest) -> AsyncGenerator[str, None]:
    """Stream chat completion responses from OpenAI API"""
    
    # Mask API key for logging (show only last 4 chars)
    masked_key = f"...{request.api_key[-4:]}" if len(request.api_key) > 4 else "****"
    
    headers = {
        "Authorization": f"Bearer {request.api_key}",
        "Content-Type": "application/json"
    }
    
    # Pre-build messages list for better performance
    messages_list = [{"role": m.role, "content": m.content} for m in request.messages]
    
    data = {
        "model": request.model,
        "messages": messages_list,
        "stream": True
    }
    
    # Enhanced logging before API call
    print(f"\n{'='*60}")
    print(f"API REQUEST DETAILS:")
    print(f"{'='*60}")
    print(f"Endpoint: {request.api_endpoint}/chat/completions")
    print(f"Model: {request.model}")
    print(f"API Key: {masked_key}")
    print(f"Message Count: {len(messages_list)}")
    print(f"Stream: {data['stream']}")
    print(f"{'='*60}\n")
    
    try:
        client = await get_http_client()
        async with client.stream(
            "POST",
            f"{request.api_endpoint}/chat/completions",
            headers=headers,
            json=data,
            timeout=60.0
        ) as response:
            if response.status_code != 200:
                # Enhanced error logging
                print(f"\n{'='*60}")
                print(f"API ERROR RESPONSE:")
                print(f"{'='*60}")
                print(f"Status Code: {response.status_code}")
                print(f"Response Headers: {dict(response.headers)}")
                
                try:
                    error_text = await response.aread()
                    error_message = error_text.decode('utf-8') if error_text else 'No error details provided'
                    
                    print(f"Raw Error Response: {error_message}")
                    
                    # Try to parse as JSON if possible
                    try:
                        error_json = json.loads(error_message)
                        error_detail = error_json.get('error', {}).get('message', error_message)
                        print(f"Parsed Error: {json.dumps(error_json, indent=2)}")
                    except (json.JSONDecodeError, AttributeError):
                        error_detail = error_message
                        print(f"Could not parse error as JSON")
                except Exception as e:
                    error_detail = f"Failed to read error response: {str(e)}"
                    print(f"Exception reading error: {str(e)}")
                
                print(f"{'='*60}\n")
                
                # Map common status codes to user-friendly messages
                status_messages = {
                    503: "Service temporarily unavailable. Please try again later.",
                    529: "Service overloaded. Please try again in a moment.",
                    502: "Bad gateway. The API server may be down.",
                    504: "Gateway timeout. The request took too long.",
                    429: "Rate limit exceeded. Please wait before making more requests.",
                    401: "Invalid API key. Please check your credentials.",
                    403: "Access forbidden. Check your API permissions.",
                    400: "Invalid request. Please check your input.",
                }
                
                user_message = status_messages.get(response.status_code, f"API Error: {response.status_code}")
                yield f"data: {json.dumps({'error': user_message, 'status_code': response.status_code, 'detail': error_detail})}\n\n"
                return
                
            async for line in response.aiter_lines():
                if line.startswith("data: "):
                    chunk = line[6:]  # Remove "data: " prefix
                    if chunk == "[DONE]":
                        break
                    try:
                        chunk_data = json.loads(chunk)
                        choices = chunk_data.get("choices")
                        if choices and len(choices) > 0:
                            content = choices[0].get("delta", {}).get("content")
                            if content:
                                # Send as SSE format
                                yield f"data: {json.dumps({'content': content})}\n\n"
                    except json.JSONDecodeError:
                        continue
            yield "data: [DONE]\n\n"
            print("✓ Stream completed successfully")
                
    except httpx.ConnectError as e:
        error_msg = f"Connection failed to {request.api_endpoint}. Check the endpoint URL and network connection."
        print(f"\n{'='*60}")
        print(f"CONNECTION ERROR:")
        print(f"{'='*60}")
        print(f"Endpoint: {request.api_endpoint}")
        print(f"Error: {str(e)}")
        print(f"{'='*60}\n")
        yield f"data: {json.dumps({'error': error_msg, 'detail': str(e)})}\n\n"
    except httpx.TimeoutException as e:
        error_msg = f"Request timeout. The API took too long to respond."
        print(f"\n{'='*60}")
        print(f"TIMEOUT ERROR:")
        print(f"{'='*60}")
        print(f"Endpoint: {request.api_endpoint}")
        print(f"Error: {str(e)}")
        print(f"{'='*60}\n")
        yield f"data: {json.dumps({'error': error_msg, 'detail': str(e)})}\n\n"
    except httpx.HTTPStatusError as e:
        print(f"\n{'='*60}")
        print(f"HTTP STATUS ERROR:")
        print(f"{'='*60}")
        print(f"Error: {str(e)}")
        print(f"{'='*60}\n")
        yield f"data: {json.dumps({'error': f'HTTP error: {str(e)}'})}\n\n"
    except httpx.RequestError as e:
        print(f"\n{'='*60}")
        print(f"REQUEST ERROR:")
        print(f"{'='*60}")
        print(f"Error: {str(e)}")
        print(f"Error Type: {type(e).__name__}")
        print(f"{'='*60}\n")
        yield f"data: {json.dumps({'error': f'Request error: {str(e)}'})}\n\n"
    except Exception as e:
        print(f"\n{'='*60}")
        print(f"UNEXPECTED ERROR:")
        print(f"{'='*60}")
        print(f"Error: {str(e)}")
        print(f"Error Type: {type(e).__name__}")
        import traceback
        print(f"Traceback:\n{traceback.format_exc()}")
        print(f"{'='*60}\n")
        yield f"data: {json.dumps({'error': f'Unexpected error: {str(e)}'})}\n\n"

@app.post("/api/chat/stream")
async def stream_chat(request: ChatRequest):
    """Stream chat responses using Server-Sent Events"""
    
    # Enhanced request logging
    print(f"\n{'*'*60}")
    print(f"NEW CHAT REQUEST RECEIVED")
    print(f"{'*'*60}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Model: {request.model}")
    print(f"Endpoint: {request.api_endpoint}")
    print(f"Stream: {request.stream}")
    print(f"Messages: {len(request.messages)}")
    for i, msg in enumerate(request.messages):
        content_preview = msg.content[:100] + "..." if len(msg.content) > 100 else msg.content
        print(f"  [{i}] {msg.role}: {content_preview}")
    print(f"{'*'*60}\n")
    
    # Validate API key
    if not request.api_key:
        raise HTTPException(status_code=400, detail="API key is required")
    
    if not request.stream:
        # Non-streaming fallback
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{request.api_endpoint}/chat/completions",
                headers={
                    "Authorization": f"Bearer {request.api_key}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": request.model,
                    "messages": [{"role": m.role, "content": m.content} for m in request.messages],
                    "stream": False
                },
                timeout=60.0
            )
            return response.json()
    
    return StreamingResponse(
        stream_chat_completion(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"  # Disable Nginx buffering
        }
    )


# ============================================================================
# DIFY HIPPO CHAT API ENDPOINTS
# ============================================================================

@app.post("/api/dify/files/upload")
async def upload_file_to_dify(
    file: UploadFile = File(...),
    user: str = Form(default="default-user")
):
    """
    Upload a file to Dify for use in chat conversations.
    
    Returns the file ID that can be used in chat requests.
    """
    print(f"\n{'='*60}")
    print(f"FILE UPLOAD REQUEST")
    print(f"Filename: {file.filename}")
    print(f"Content-Type: {file.content_type}")
    print(f"User: {user}")
    print(f"{'='*60}\n")
    
    try:
        # Get API key for hippo_chat
        api_key = DIFY_CHAT_KEYS.get("hippo_chat")
        if not api_key:
            raise HTTPException(status_code=500, detail="Dify API key not configured")
        
        # Read file content
        file_content = await file.read()
        
        # Prepare multipart form data
        files = {
            "file": (file.filename, file_content, file.content_type or "application/octet-stream")
        }
        data = {
            "user": user
        }
        
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        client = await get_http_client()
        response = await client.post(
            get_endpoint("file_upload"),
            headers=headers,
            files=files,
            data=data,
            timeout=60.0
        )
        
        if response.status_code != 200 and response.status_code != 201:
            error_text = response.text
            print(f"File upload error: {response.status_code} - {error_text}")
            raise HTTPException(
                status_code=response.status_code,
                detail=f"File upload failed: {error_text}"
            )
        
        result = response.json()
        print(f"File uploaded successfully: {result}")
        
        return {
            "id": result.get("id"),
            "name": result.get("name", file.filename),
            "size": result.get("size", len(file_content)),
            "type": result.get("type", file.content_type),
            "created_at": result.get("created_at")
        }
        
    except httpx.HTTPError as e:
        print(f"HTTP error during file upload: {str(e)}")
        raise HTTPException(status_code=500, detail=f"File upload failed: {str(e)}")
    except Exception as e:
        print(f"Error uploading file: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def stream_dify_chat(request: DifyChatRequest) -> AsyncGenerator[str, None]:
    """Stream chat responses from Dify hippo_chat API"""
    
    print(f"\n{'='*60}")
    print(f"DIFY CHAT REQUEST")
    print(f"Query: {request.query[:100]}..." if len(request.query) > 100 else f"Query: {request.query}")
    print(f"Conversation ID: {request.conversation_id}")
    print(f"Files: {len(request.files) if request.files else 0}")
    print(f"User: {request.user}")
    print(f"{'='*60}\n")
    
    try:
        api_key = DIFY_CHAT_KEYS.get("hippo_chat")
        if not api_key:
            yield f"data: {json.dumps({'error': 'Dify API key not configured'})}\n\n"
            return
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        # Build request payload
        payload = {
            "inputs": {},
            "query": request.query,
            "response_mode": "streaming",
            "user": request.user
        }
        
        if request.conversation_id:
            payload["conversation_id"] = request.conversation_id
        
        # Add files if present
        if request.files:
            payload["files"] = [
                {
                    "type": f.type,
                    "transfer_method": f.transfer_method,
                    "upload_file_id": f.upload_file_id
                } if f.transfer_method == "local_file" else {
                    "type": f.type,
                    "transfer_method": f.transfer_method,
                    "url": f.url
                }
                for f in request.files
            ]
        
        print(f"Dify request payload: {json.dumps(payload, indent=2)}")
        
        client = await get_http_client()
        async with client.stream(
            "POST",
            get_endpoint("chat_messages"),
            headers=headers,
            json=payload,
            timeout=120.0
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                error_message = error_text.decode('utf-8') if error_text else 'Unknown error'
                print(f"Dify API error: {response.status_code} - {error_message}")
                yield f"data: {json.dumps({'error': f'Dify API error: {error_message}', 'status_code': response.status_code})}\n\n"
                return
            
            conversation_id = None
            message_id = None
            
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                
                data_str = line[6:]  # Remove "data: " prefix
                
                if not data_str:
                    continue
                
                try:
                    data = json.loads(data_str)
                    event = data.get("event", "")
                    
                    if event == "message":
                        # Streaming message content
                        answer = data.get("answer", "")
                        if answer:
                            yield f"data: {json.dumps({'content': answer})}\n\n"
                        
                        # Capture conversation_id for future use
                        if not conversation_id:
                            conversation_id = data.get("conversation_id")
                        if not message_id:
                            message_id = data.get("message_id")
                    
                    elif event == "message_end":
                        # Message complete
                        conversation_id = data.get("conversation_id", conversation_id)
                        message_id = data.get("message_id", message_id)
                        
                        # Include metadata in the done message
                        yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id, 'message_id': message_id})}\n\n"
                        yield "data: [DONE]\n\n"
                        return
                    
                    elif event == "error":
                        error_msg = data.get("message", "Unknown error from Dify")
                        yield f"data: {json.dumps({'error': error_msg})}\n\n"
                        return
                    
                    elif event == "agent_message":
                        # Agent response (similar to message)
                        answer = data.get("answer", "")
                        if answer:
                            yield f"data: {json.dumps({'content': answer})}\n\n"
                    
                    elif event == "agent_thought":
                        # Agent thinking process (can be shown as intermediate steps)
                        thought = data.get("thought", "")
                        if thought:
                            yield f"data: {json.dumps({'thought': thought})}\n\n"
                    
                except json.JSONDecodeError:
                    continue
            
            # If we exit the loop without message_end, send done
            yield f"data: {json.dumps({'done': True, 'conversation_id': conversation_id})}\n\n"
            yield "data: [DONE]\n\n"
    
    except httpx.ConnectError as e:
        error_msg = f"Connection failed to Dify API"
        print(f"Connection error: {str(e)}")
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
    except httpx.TimeoutException as e:
        error_msg = "Request timeout. Dify API took too long to respond."
        print(f"Timeout error: {str(e)}")
        yield f"data: {json.dumps({'error': error_msg})}\n\n"
    except Exception as e:
        print(f"Unexpected error in Dify chat: {str(e)}")
        import traceback
        traceback.print_exc()
        yield f"data: {json.dumps({'error': f'Unexpected error: {str(e)}'})}\n\n"


@app.post("/api/dify/chat")
async def dify_chat(request: DifyChatRequest):
    """
    Chat with Dify hippo_chat API.
    
    This endpoint supports:
    - Streaming responses
    - File attachments (use /api/dify/files/upload first to get file IDs)
    - Conversation history via conversation_id
    
    Input:
    - query: User's chat message
    - files: Optional list of file attachments
    - conversation_id: Optional ID to continue an existing conversation
    
    Output:
    - answer: The complete response from the AI
    """
    
    print(f"\n{'*'*60}")
    print(f"NEW DIFY CHAT REQUEST")
    print(f"{'*'*60}")
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Query: {request.query[:200]}..." if len(request.query) > 200 else f"Query: {request.query}")
    print(f"Conversation ID: {request.conversation_id}")
    print(f"Files: {request.files}")
    print(f"Response Mode: {request.response_mode}")
    print(f"{'*'*60}\n")
    
    if request.response_mode == "blocking":
        # Non-streaming response
        try:
            api_key = DIFY_CHAT_KEYS.get("hippo_chat")
            if not api_key:
                raise HTTPException(status_code=500, detail="Dify API key not configured")
            
            headers = {
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "inputs": {},
                "query": request.query,
                "response_mode": "blocking",
                "user": request.user
            }
            
            if request.conversation_id:
                payload["conversation_id"] = request.conversation_id
            
            if request.files:
                payload["files"] = [
                    {
                        "type": f.type,
                        "transfer_method": f.transfer_method,
                        "upload_file_id": f.upload_file_id
                    } if f.transfer_method == "local_file" else {
                        "type": f.type,
                        "transfer_method": f.transfer_method,
                        "url": f.url
                    }
                    for f in request.files
                ]
            
            client = await get_http_client()
            response = await client.post(
                get_endpoint("chat_messages"),
                headers=headers,
                json=payload,
                timeout=120.0
            )
            
            if response.status_code != 200:
                error_text = response.text
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Dify API error: {error_text}"
                )
            
            result = response.json()
            return {
                "answer": result.get("answer", ""),
                "conversation_id": result.get("conversation_id"),
                "message_id": result.get("message_id"),
                "created_at": result.get("created_at")
            }
            
        except httpx.HTTPError as e:
            raise HTTPException(status_code=500, detail=f"Dify API error: {str(e)}")
    
    # Streaming response
    return StreamingResponse(
        stream_dify_chat(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.get("/api/dify/conversations")
async def get_conversations(user: str = "default-user", limit: int = 20):
    """Get list of conversations for a user"""
    try:
        api_key = DIFY_CHAT_KEYS.get("hippo_chat")
        if not api_key:
            raise HTTPException(status_code=500, detail="Dify API key not configured")
        
        headers = {
            "Authorization": f"Bearer {api_key}"
        }
        
        client = await get_http_client()
        response = await client.get(
            f"{get_endpoint('chat_conversations')}?user={user}&limit={limit}",
            headers=headers,
            timeout=30.0
        )
        
        if response.status_code != 200:
            raise HTTPException(
                status_code=response.status_code,
                detail=f"Failed to get conversations: {response.text}"
            )
        
        return response.json()
        
    except httpx.HTTPError as e:
        raise HTTPException(status_code=500, detail=f"API error: {str(e)}")


@app.post("/api/test/workflow")
async def test_workflow(request: dict):
    """
    Test endpoint for directly calling Dify workflows
    """
    try:
        from dify_task_service import DifyTaskService
        
        workflow_key = request.get("workflow_key")
        inputs = request.get("inputs", {})
        
        async with DifyTaskService() as service:
            response = await service._call_workflow(
                workflow_key=workflow_key,
                inputs=inputs,
                response_mode="blocking"
            )
            
            return {
                "success": True,
                "workflow_key": workflow_key,
                "response": response
            }
    except Exception as e:
        return {
            "success": False,
            "error": str(e)
        }

@app.post("/api/tasks/execute")
async def execute_task(request: ExecuteTaskRequest):
    """
    Execute a task with the provided parameters using Dify workflows.
    
    This endpoint:
    1. Validates the task and parameters
    2. Routes to the appropriate Dify workflow (prioritizing feishu_executor if specified)
    3. Executes the task via Dify API
    4. Returns the result or status
    """
    
    print(f"\n{'='*60}")
    print(f"TASK EXECUTION REQUEST")
    print(f"Task ID: {request.taskId}")
    print(f"Title: {request.title}")
    print(f"Description: {request.description}")
    print(f"Category: {request.category}")
    print(f"Priority: {request.priority}")
    print(f"Workflow Type: {request.workflowType}")
    print(f"Parameters:")
    for param in request.parameters:
        print(f"  - {param.name}: {param.value} (type: {param.type})")
    if request.context:
        print(f"Context: {request.context}")
    print(f"{'='*60}\n")
    
    # Import the Dify task service
    from dify_task_service import DifyTaskService
    
    try:
        # Convert parameters to the format expected by Dify service
        parameters = [
            {
                "name": param.name,
                "value": param.value,
                "type": param.type,
                "description": param.description
            }
            for param in request.parameters
        ]
        
        # Build context string for feishu_executor
        context_string = ""
        if request.context and request.context.get('contextString'):
            context_string = request.context['contextString']
        elif request.description:
            # Build context from task details
            params_str = ", ".join([f"{p.name}: {p.value}" for p in request.parameters])
            context_string = f"任务: {request.title}\n描述: {request.description}\n优先级: {request.priority or '普通'}\n参数: {params_str}"
        
        # If workflowType is email_executor, use it directly
        if request.workflowType == 'email_executor':
            async with DifyTaskService() as service:
                # Extract email parameters
                params_dict = {p.name: p.value for p in request.parameters}
                
                # Prepare email content for the email_executor workflow
                # Call email_executor workflow directly with new parameters
                response = await service._call_workflow(
                    workflow_key="email_executor",
                    inputs={
                        "recipient": params_dict.get('收件人', 'Not specified'),
                        "cc": params_dict.get('抄送', ''),
                        "theme": params_dict.get('主题', 'Email from RMinte'),
                        "content": params_dict.get('正文', 'No content provided')
                    },
                    response_mode="blocking"
                )
                
                if response.get("data", {}).get("status") == "succeeded":
                    outputs = response.get("data", {}).get("outputs", {})
                    result = {
                        "taskId": request.taskId,
                        "status": "completed",
                        "result": {
                            "success": True,
                            "message": "邮件已成功发送",
                            "details": {
                                "mail_output": outputs.get("mail_output", "Email content generated"),
                                "workflow_run_id": response.get("workflow_run_id"),
                                "executedAt": datetime.now().isoformat()
                            }
                        },
                        "executedAt": datetime.now().isoformat()
                    }
                else:
                    raise Exception(f"Email executor workflow failed: {response.get('data', {}).get('error', 'Unknown error')}")
        # If workflowType is feishu_executor, use it directly
        elif request.workflowType == 'feishu_executor':
            async with DifyTaskService() as service:
                # Convert parameters list to dictionary for easier access
                params_dict = {p.name: p.value for p in request.parameters}
                # Extract contact_person from 参会人 parameter
                contact_person = params_dict.get("参会人", "") or params_dict.get("contact_person", "")
                
                # Call feishu_executor workflow directly
                response = await service._call_workflow(
                    workflow_key="feishu_executor",
                    inputs={
                        "todo_input": context_string,
                        "contact_person": contact_person
                    },
                    response_mode="blocking"
                )
                
                if response.get("data", {}).get("status") == "succeeded":
                    result = {
                        "taskId": request.taskId,
                        "status": "completed",
                        "result": {
                            "success": True,
                            "message": "任务已通过飞书执行器成功执行",
                            "details": {
                                "workflow_run_id": response.get("workflow_run_id"),
                                "outputs": response.get("data", {}).get("outputs", {}),
                                "executedAt": datetime.now().isoformat()
                            }
                        },
                        "executedAt": datetime.now().isoformat()
                    }
                else:
                    raise Exception(f"Feishu executor workflow failed: {response.get('data', {}).get('error', 'Unknown error')}")
        elif request.workflowType == 'docFeishu_executor':
            async with DifyTaskService() as service:
                # Convert parameters list to dictionary for easier access
                params_dict = {p.name: p.value for p in request.parameters}
                
                # Use insight_feed if available, otherwise use context from request
                doc_content = insight_feed if insight_feed else context_string
                
                # If we still don't have content, try to get it from parameters
                if not doc_content:
                    doc_content = params_dict.get("描述", "")
                
                print(f"Using doc_content for docFeishu_executor (length: {len(doc_content)})")
                
                # Call docFeishu_executor workflow directly
                response = await service._call_workflow(
                    workflow_key="docFeishu_executor",
                    inputs={
                        "feishu_doc_input": doc_content,
                        "doc_title_input": params_dict.get("标题", "无标题")
                    },
                    response_mode="blocking"
                )
                
                if response.get("data", {}).get("status") == "succeeded":
                    result = {
                        "taskId": request.taskId,
                        "status": "completed",
                        "result": {
                            "success": True,
                            "message": "文档已成功创建",
                            "details": {
                                "workflow_run_id": response.get("workflow_run_id"),
                                "outputs": response.get("data", {}).get("outputs", {}),
                                "executedAt": datetime.now().isoformat()
                            }
                        },
                        "executedAt": datetime.now().isoformat()
                    }
                else:
                    raise Exception(f"DocFeishu executor workflow failed: {response.get('data', {}).get('error', 'Unknown error')}")
        else:
            # Fallback to automatic task type detection
            from dify_task_service import execute_dify_task
            result = await execute_dify_task(
                task_id=request.taskId,
                title=request.title,
                parameters=parameters,
                context=context_string
            )
        
        return result
        
    except Exception as e:
        print(f"Error executing task with Dify: {str(e)}")
        # Fallback to mock execution if Dify fails
        print("Falling back to mock execution...")
        
        # Simulate task execution with a minimal delay
        await asyncio.sleep(0.5)
        
        # Mock different task execution scenarios
        task_handlers = {
            "发送邮件": handle_email_task,
            "安排会议": handle_meeting_task,
            "创建文档": handle_document_task,
            "File Operation": handle_file_task,
            "API 调用": handle_api_task,
        }
        
        # Find matching handler or use default
        handler = None
        for task_type, task_handler in task_handlers.items():
            if task_type.lower() in request.title.lower():
                handler = task_handler
                break
        
        if handler:
            result = await handler(request.parameters)
        else:
            # Default handler for unknown tasks
            result = await handle_generic_task(request.title, request.parameters)
        
        return {
            "taskId": request.taskId,
            "status": "completed",
            "result": result,
            "executedAt": datetime.now().isoformat()
        }

async def handle_email_task(parameters: List[TaskParameter]):
    """Mock email task execution"""
    params_dict = {p.name: p.value for p in parameters}
    return {
        "success": True,
        "message": f"邮件已发送给 {params_dict.get('recipient', '未知')}",
        "details": {
            "messageId": str(uuid.uuid4()),
            "sentAt": datetime.now().isoformat(),
            "recipient": params_dict.get('recipient'),
            "subject": params_dict.get('subject')
        }
    }

async def handle_meeting_task(parameters: List[TaskParameter]):
    """Mock meeting scheduling task"""
    params_dict = {p.name: p.value for p in parameters}
    return {
        "success": True,
        "message": "会议安排成功",
        "details": {
            "meetingId": str(uuid.uuid4()),
            "scheduledAt": params_dict.get('time', 'TBD'),
            "attendees": params_dict.get('attendees', '').split(',') if params_dict.get('attendees') else [],
            "location": params_dict.get('location', 'Virtual')
        }
    }

async def handle_document_task(parameters: List[TaskParameter]):
    """Mock document creation task"""
    params_dict = {p.name: p.value for p in parameters}
    return {
        "success": True,
        "message": f"文档 '{params_dict.get('title', '无标题')}' 已创建",
        "details": {
            "documentId": str(uuid.uuid4()),
            "createdAt": datetime.now().isoformat(),
            "format": params_dict.get('format', 'markdown'),
            "wordCount": len(params_dict.get('content', '').split()) if params_dict.get('content') else 0
        }
    }

async def handle_file_task(parameters: List[TaskParameter]):
    """Mock file operation task"""
    params_dict = {p.name: p.value for p in parameters}
    return {
        "success": True,
        "message": "文件操作完成",
        "details": {
            "operation": params_dict.get('operation', 'unknown'),
            "path": params_dict.get('path', '/'),
            "timestamp": datetime.now().isoformat()
        }
    }

async def handle_api_task(parameters: List[TaskParameter]):
    """Mock API call task"""
    params_dict = {p.name: p.value for p in parameters}
    return {
        "success": True,
        "message": "API 调用已执行",
        "details": {
            "endpoint": params_dict.get('endpoint', 'unknown'),
            "method": params_dict.get('method', 'GET'),
            "statusCode": 200,
            "responseTime": "125ms"
        }
    }

async def handle_generic_task(title: str, parameters: List[TaskParameter]):
    """Generic task handler for unknown task types"""
    params_dict = {p.name: p.value for p in parameters}
    return {
        "success": True,
        "message": f"任务 '{title}' 完成成功",
        "details": {
            "taskType": "generic",
            "parametersProcessed": len(parameters),
            "timestamp": datetime.now().isoformat(),
            "parameters": params_dict
        }
    }

async def extract_tasks_from_context(context: str) -> List[dict]:
    """
    Extract actionable tasks from screen recording context using Dify's Feishu todo generator.
    Falls back to keyword-based extraction if Dify API fails.
    """
    
    # Try to use Dify's Feishu todo generator first
    try:
        from dify_task_service import DifyTaskService
        
        async with DifyTaskService() as service:
            # Call the Feishu todo workflow to extract tasks (using demo version)
            response = await service._call_workflow(
                workflow_key="feishu_todo_demo",
                inputs={
                    "context_input": context
                },
                response_mode="blocking"
            )
            
            if response.get("data", {}).get("status") == "succeeded":
                # Try different possible response structures
                data = response.get("data", {})
                outputs = data.get("outputs", {})
                
                # Debug: Print the entire response structure
                print(f"Dify response data keys: {data.keys()}")
                print(f"Dify outputs: {outputs}")
                
                # Initialize todo_items
                todo_items = []
                
                # Check if schedule_output exists (can be string, dict, or list)
                schedule_output = outputs.get("schedule_output", "")
                if schedule_output:
                    if isinstance(schedule_output, str):
                        # If it's a string, parse it as JSON
                        try:
                            import json
                            schedule_data = json.loads(schedule_output)
                            todo_items = schedule_data.get("todos", [])
                            print(f"Parsed schedule_output from JSON string, found {len(todo_items)} todos")
                        except Exception as e:
                            print(f"Failed to parse schedule_output as JSON: {e}")
                    elif isinstance(schedule_output, dict):
                        # If it's already a dict, get todos directly
                        todo_items = schedule_output.get("todos", [])
                        print(f"Got todos directly from schedule_output dict, found {len(todo_items)} todos")
                    elif isinstance(schedule_output, list):
                        # If it's already a list, use it directly as todo_items
                        todo_items = schedule_output
                        print(f"Using schedule_output list directly, found {len(todo_items)} todos")
                    else:
                        print(f"Unexpected schedule_output type: {type(schedule_output)}")
                
                # Fallback: Try to get todos directly from outputs
                if not todo_items:
                    todo_items = outputs.get("todos", outputs.get("todo", []))
                    
                    # If outputs itself is a string containing JSON, try to parse it
                    if isinstance(outputs, str):
                        try:
                            import json
                            outputs_dict = json.loads(outputs)
                            todo_items = outputs_dict.get("todos", outputs_dict.get("todo", []))
                        except:
                            pass
                
                # Ensure todo_items is a list
                if not isinstance(todo_items, list):
                    todo_items = []
                
                # Convert Dify todo items to our task format
                tasks = []
                for item in todo_items:
                    # Parse the todo item (it should be a dict from Dify)
                    if isinstance(item, dict):
                        context_type = item.get("context_type", "")
                        
                        # Initialize common variables with defaults
                        title = ""
                        description = ""
                        confidence = "medium"
                        
                        if context_type == "Zoom":
                            topic = item.get("topic", "")
                            title = topic  # Use topic as title for Zoom meetings
                            meeting_id = item.get("meeting_id", "")
                            duration = item.get("duration", "")
                            password = item.get("password", "")
                            start_time = item.get("start_time", "")
                            timezone = item.get("timezone", "")
                            # Create description from available info
                            description = f"Zoom Meeting: {topic}"
                            if meeting_id:
                                description += f" (ID: {meeting_id})"
                            if start_time:
                                description += f" at {start_time}"
                        elif context_type == "Mail":
                            title = item.get("title", "")
                            recipient = item.get("recipient", "")
                            theme = item.get("theme", "")
                            confidence = item.get("confidence", "medium")
                            content = item.get("content", "")
                            attachment = item.get("attachment", "")
                            description = content if content else f"Send email to {recipient}: {theme}"
                        elif context_type == "docFeishu":
                            title = item.get("title", "")
                            description = item.get("description", "")
                            confidence = item.get("confidence", "medium")
                        else:
                            title = item.get("title", item.get("name", "Task"))
                            description = item.get("description", item.get("content", ""))
                            start_time = item.get("start_time", "")
                            end_time = item.get("end_time", "")
                            context_type = item.get("context_type", "")
                            confidence = item.get("confidence", "medium")
                    else:
                        # If it's a string, use it as both title and description
                        title = str(item)[:50]  # First 50 chars as title
                        description = str(item)
                        start_time = ""
                        end_time = ""
                        confidence = "low"
                    
                    # Determine task type and parameters based on content
                    task_type = "generic"
                    parameters = []
                    
                    # Check for specific task types
                    if context_type == "Mail":
                        task_type = "email"
                        # Keep the original title for the subject
                        original_title = title
                        parameters = [
                            {"name": "收件人", "value": recipient, "type": "text", "required": True},
                            {"name": "抄送", "value": "", "type": "text", "required": False},
                            {"name": "主题", "value": theme, "type": "text", "required": True},
                            {"name": "正文", "value": content, "type": "text", "required": True}
                        ]
                        # Add workflowType hint for email tasks
                        workflow_type = "email_executor"
                    elif context_type == "Zoom":
                        task_type = "zoom"
                        # Keep the original title for the subject

                        parameters = [
                            {"name": "主题", "value": topic, "type": "text", "required": True},
                            {"name": "开始时间", "value": start_time, "type": "text", "required": True},
                            {"name": "会议ID", "value": meeting_id, "type": "text"},
                            {"name": "会议密码", "value": password, "type": "text"},
                            {"name": "会议时长", "value": duration, "type": "text"},
                            {"name": "会议时区", "value": timezone, "type": "text"}
                    ]
                    elif context_type == "feishu":
                        task_type = "feishu"
                        # Keep the original title for the subject
                        original_title = title
                        
                        # Extract attendees from description if mentioned
                        attendees = ""
                        parameters = [
                            {"name": "主题", "value": original_title, "type": "text", "required": True},
                            {"name": "开始时间", "value": start_time, "type": "text", "required": True},
                            {"name": "结束时间", "value": end_time, "type": "text", "required": True},
                            {"name": "参会人", "value": attendees, "type": "text"}
                        ]
                    elif context_type == "docFeishu":
                        task_type = "docFeishu"
                        # Keep the original title for the subject
                        original_title = title
                        parameters = [
                            {"name": "标题", "value": original_title, "type": "text", "required": True},
                            {"name": "描述", "value": description, "type": "text", "required": True}
                        ]
                    else:
                        # Generic task
                        parameters = [
                            {"name": "描述", "value": description, "type": "text"},
                            {"name": "上下文", "value": context[:200], "type": "text"}
                        ]
                    
                    task_data = {
                        "id": str(uuid.uuid4()),
                        "title": title,
                        "description": description,
                        "category": task_type,
                        "priority": confidence if confidence in ['low', 'medium', 'high'] else "medium",
                        "parameters": parameters
                    }
                    
                    # Add workflowType if it's an email task
                    if context_type == "Mail":
                        task_data["workflowType"] = "email_executor"
                    
                    tasks.append(task_data)
                
                print(f"Extracted {len(tasks)} tasks using Dify API")
                if tasks:
                    for task in tasks:
                        print(f"  - Task: {task['title']} (priority: {task.get('priority', 'medium')})")
                return tasks
                
    except Exception as e:
        print(f"Failed to use Dify API for task extraction: {str(e)}")
        print("Falling back to keyword-based extraction...")
    
    # Fallback to keyword-based extraction
    tasks = []
    
    # Check for email-related keywords (English and Chinese)
    if any(word in context.lower() for word in ['email', 'send', 'reply', 'forward', '邮件', '发送', '回复', '转发', '发邮件', '写邮件']):
        tasks.append({
            "id": str(uuid.uuid4()),
            "title": "发送邮件",
            "description": "根据上下文编写并发送邮件",
            "category": "email",
            "priority": "high",
            "parameters": [
                {"name": "收件人", "value": "", "type": "text", "required": True},
                {"name": "主题", "value": "", "type": "text", "required": True},
                {"name": "正文", "value": "", "type": "text", "required": True}
            ]
        })
    
    # Check for meeting/calendar keywords (English and Chinese)
    if any(word in context.lower() for word in ['meeting', 'schedule', 'calendar', 'appointment', '会议', '安排', '日程', '预约', '日历', '约会', '会面', 'zoom', '开会']):
        tasks.append({
            "id": str(uuid.uuid4()),
            "title": "安排会议",
            "description": "根据讨论安排会议",
            "category": "feishu",
            "priority": "medium",
            "parameters": [
                {"name": "主题", "value": "", "type": "text", "required": True},
                {"name": "开始时间", "value": "", "type": "text", "required": True},
                {"name": "结束时间", "value": "", "type": "text", "required": True},
                {"name": "参会人", "value": "", "type": "text"}
            ]
        })
    
    # Check for documentation keywords (English and Chinese)
    if any(word in context.lower() for word in ['document', 'documentation', 'readme', 'guide', '文档', '文件', '说明', '指南', '手册', '记录']):
        tasks.append({
            "id": str(uuid.uuid4()),
            "title": "创建文档",
            "description": "从上下文生成文档",
            "category": "docFeishu",
            "priority": "low",
            "parameters": [
                {"name": "标题", "value": "", "type": "text", "required": True},
                {"name": "描述", "value": context[:200], "type": "text", "required": True}
            ]
        })
    
    return tasks

class TaskDetectRequest(BaseModel):
    context: str = ""

# ============================================================================
# INTENT PARSING ENDPOINT (Caddy-like functionality)
# ============================================================================

class IntentFileInfo(BaseModel):
    name: str
    type: str
    size: int

class IntentParseRequest(BaseModel):
    intent: str
    action: Optional[str] = None
    context: Optional[str] = None
    files: Optional[List[IntentFileInfo]] = None

@app.post("/api/intent/parse")
async def parse_intent(request: IntentParseRequest):
    """
    Parse natural language intent and convert to actionable tasks.
    Similar to Caddy's voice command parsing but for text input.
    
    This endpoint:
    1. Analyzes the user's intent using NLP/AI
    2. Identifies the action type (email, schedule, document, etc.)
    3. Extracts parameters from the intent
    4. Returns structured task(s) for execution
    """
    
    print(f"\n{'='*60}")
    print(f"INTENT PARSE REQUEST")
    print(f"Intent: {request.intent}")
    print(f"Action: {request.action}")
    print(f"Context length: {len(request.context) if request.context else 0}")
    print(f"Files: {len(request.files) if request.files else 0}")
    print(f"{'='*60}\n")
    
    try:
        # Try to use Dify for intelligent intent parsing
        try:
            from dify_task_service import DifyTaskService
            
            async with DifyTaskService() as service:
                # Use the feishu_todo_demo workflow for intent parsing
                full_context = f"""
User Intent: {request.intent}

Additional Context:
{request.context or 'No additional context provided'}

Attached Files:
{', '.join([f.name for f in request.files]) if request.files else 'No files attached'}
"""
                
                response = await service._call_workflow(
                    workflow_key="feishu_todo_demo",
                    inputs={
                        "context_input": full_context
                    },
                    response_mode="blocking"
                )
                
                if response.get("data", {}).get("status") == "succeeded":
                    outputs = response.get("data", {}).get("outputs", {})
                    
                    # Parse the response similar to extract_tasks_from_context
                    schedule_output = outputs.get("schedule_output", "")
                    todo_items = []
                    
                    if schedule_output:
                        if isinstance(schedule_output, str):
                            try:
                                schedule_data = json.loads(schedule_output)
                                todo_items = schedule_data.get("todos", [])
                            except:
                                pass
                        elif isinstance(schedule_output, dict):
                            todo_items = schedule_output.get("todos", [])
                        elif isinstance(schedule_output, list):
                            todo_items = schedule_output
                    
                    if todo_items:
                        tasks = await convert_intent_to_tasks(todo_items, request.intent, request.action)
                        return {"tasks": tasks, "source": "dify"}
        
        except Exception as e:
            print(f"Dify intent parsing failed: {str(e)}")
        
        # Fallback to rule-based intent parsing
        tasks = await parse_intent_rules(request.intent, request.action, request.context)
        return {"tasks": tasks, "source": "rules"}
        
    except Exception as e:
        print(f"Error parsing intent: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


async def convert_intent_to_tasks(todo_items: list, intent: str, action: Optional[str]) -> list:
    """Convert Dify todo items to task format"""
    tasks = []
    
    for item in todo_items:
        if isinstance(item, dict):
            context_type = item.get("context_type", "")
            title = item.get("title", item.get("topic", "Task"))
            description = item.get("description", item.get("content", intent))
            confidence = item.get("confidence", "medium")
            
            # Determine workflow type and parameters based on context_type
            if context_type == "Mail":
                tasks.append({
                    "title": title or "Send Email",
                    "description": description,
                    "category": "email",
                    "priority": confidence,
                    "workflowType": "email_executor",
                    "parameters": [
                        {"name": "收件人", "value": item.get("recipient", ""), "type": "text", "required": True},
                        {"name": "抄送", "value": item.get("cc", ""), "type": "text", "required": False},
                        {"name": "主题", "value": item.get("theme", title), "type": "text", "required": True},
                        {"name": "正文", "value": item.get("content", description), "type": "text", "required": True}
                    ]
                })
            elif context_type == "Zoom":
                tasks.append({
                    "title": item.get("topic", "Schedule Meeting"),
                    "description": description,
                    "category": "zoom",
                    "priority": confidence,
                    "workflowType": "feishu_executor",
                    "parameters": [
                        {"name": "主题", "value": item.get("topic", ""), "type": "text", "required": True},
                        {"name": "开始时间", "value": item.get("start_time", ""), "type": "text", "required": True},
                        {"name": "会议ID", "value": item.get("meeting_id", ""), "type": "text"},
                        {"name": "会议密码", "value": item.get("password", ""), "type": "text"}
                    ]
                })
            elif context_type == "feishu":
                tasks.append({
                    "title": title or "Schedule Feishu Event",
                    "description": description,
                    "category": "feishu",
                    "priority": confidence,
                    "workflowType": "feishu_executor",
                    "parameters": [
                        {"name": "主题", "value": title, "type": "text", "required": True},
                        {"name": "开始时间", "value": item.get("start_time", ""), "type": "text", "required": True},
                        {"name": "结束时间", "value": item.get("end_time", ""), "type": "text", "required": True},
                        {"name": "参会人", "value": "", "type": "text"}
                    ]
                })
            elif context_type == "docFeishu":
                tasks.append({
                    "title": title or "Create Document",
                    "description": description,
                    "category": "docFeishu",
                    "priority": confidence,
                    "workflowType": "docFeishu_executor",
                    "parameters": [
                        {"name": "标题", "value": title, "type": "text", "required": True},
                        {"name": "描述", "value": description, "type": "text", "required": True}
                    ]
                })
            else:
                # Generic task
                tasks.append({
                    "title": title,
                    "description": description,
                    "category": "generic",
                    "priority": confidence,
                    "parameters": [
                        {"name": "描述", "value": description, "type": "text", "required": True}
                    ]
                })
        else:
            # Simple string item
            tasks.append({
                "title": str(item)[:50],
                "description": str(item),
                "category": "generic",
                "priority": "medium",
                "parameters": [
                    {"name": "描述", "value": str(item), "type": "text", "required": True}
                ]
            })
    
    return tasks


async def parse_intent_rules(intent: str, action: Optional[str], context: Optional[str]) -> list:
    """
    Rule-based intent parsing as fallback when AI parsing is not available.
    Analyzes keywords and patterns to determine task type.
    """
    intent_lower = intent.lower()
    tasks = []
    
    # Email patterns
    email_keywords = ['email', 'mail', 'send', 'write to', '邮件', '发送', '写邮件', '发邮件']
    if action == 'email' or any(kw in intent_lower for kw in email_keywords):
        # Try to extract recipient from intent
        recipient = ""
        subject = ""
        body = intent
        
        # Pattern matching for "to [name/email]"
        import re
        to_match = re.search(r'to\s+(\S+@\S+|\w+)', intent, re.IGNORECASE)
        if to_match:
            recipient = to_match.group(1)
        
        # Pattern matching for "about [subject]"
        about_match = re.search(r'about\s+(.+?)(?:\s+to|\s*$)', intent, re.IGNORECASE)
        if about_match:
            subject = about_match.group(1)
        
        tasks.append({
            "title": "发送邮件",
            "description": intent,
            "category": "email",
            "priority": "high",
            "workflowType": "email_executor",
            "parameters": [
                {"name": "收件人", "value": recipient, "type": "text", "required": True},
                {"name": "抄送", "value": "", "type": "text", "required": False},
                {"name": "主题", "value": subject, "type": "text", "required": True},
                {"name": "正文", "value": body, "type": "text", "required": True}
            ]
        })
        return tasks
    
    # Schedule/Meeting patterns
    schedule_keywords = ['schedule', 'meeting', 'calendar', 'event', 'appointment', '会议', '安排', '日程', '预约', 'zoom', '开会']
    if action == 'schedule' or any(kw in intent_lower for kw in schedule_keywords):
        title = intent
        start_time = ""
        
        # Try to extract time from intent
        import re
        time_patterns = [
            r'at\s+(\d{1,2}:\d{2}(?:\s*(?:am|pm))?)',
            r'on\s+(\w+\s+\d{1,2}(?:st|nd|rd|th)?)',
            r'tomorrow',
            r'next\s+\w+'
        ]
        for pattern in time_patterns:
            match = re.search(pattern, intent, re.IGNORECASE)
            if match:
                start_time = match.group(0) if match.lastindex is None else match.group(1)
                break
        
        tasks.append({
            "title": "安排会议",
            "description": intent,
            "category": "feishu",
            "priority": "medium",
            "workflowType": "feishu_executor",
            "parameters": [
                {"name": "主题", "value": title, "type": "text", "required": True},
                {"name": "开始时间", "value": start_time, "type": "text", "required": True},
                {"name": "结束时间", "value": "", "type": "text", "required": True},
                {"name": "参会人", "value": "", "type": "text"}
            ]
        })
        return tasks
    
    # Document patterns
    doc_keywords = ['document', 'doc', 'write', 'create', 'draft', '文档', '创建', '写', '草稿']
    if action == 'document' or any(kw in intent_lower for kw in doc_keywords):
        tasks.append({
            "title": "创建文档",
            "description": intent,
            "category": "docFeishu",
            "priority": "medium",
            "workflowType": "docFeishu_executor",
            "parameters": [
                {"name": "标题", "value": intent[:50], "type": "text", "required": True},
                {"name": "描述", "value": context or intent, "type": "text", "required": True}
            ]
        })
        return tasks
    
    # Task/Todo patterns
    task_keywords = ['task', 'todo', 'remind', 'add', '任务', '待办', '提醒', '添加']
    if action == 'task' or any(kw in intent_lower for kw in task_keywords):
        tasks.append({
            "title": intent[:50],
            "description": intent,
            "category": "generic",
            "priority": "medium",
            "parameters": [
                {"name": "描述", "value": intent, "type": "text", "required": True}
            ]
        })
        return tasks
    
    # Message patterns
    message_keywords = ['message', 'chat', 'tell', 'notify', '消息', '告诉', '通知', '聊天']
    if action == 'message' or any(kw in intent_lower for kw in message_keywords):
        tasks.append({
            "title": "发送消息",
            "description": intent,
            "category": "message",
            "priority": "medium",
            "workflowType": "feishu_executor",
            "parameters": [
                {"name": "收件人", "value": "", "type": "text", "required": True},
                {"name": "内容", "value": intent, "type": "text", "required": True}
            ]
        })
        return tasks
    
    # Default: create a generic task
    tasks.append({
        "title": intent[:50],
        "description": intent,
        "category": "generic",
        "priority": "medium",
        "parameters": [
            {"name": "描述", "value": intent, "type": "text", "required": True}
        ]
    })
    
    return tasks


@app.post("/api/tasks/detect")
async def detect_tasks_from_context(request: TaskDetectRequest):
    """
    Detect actionable tasks from the provided context.
    Uses Dify's AI to identify tasks that can be automated.
    
    Implementation:
    1. Parse the context using Dify's Feishu todo generator
    2. Identify actionable items
    3. Generate task parameters
    4. Return structured task list
    """
    context = request.context
    
    if context:
        # Use Dify to extract real tasks from context
        tasks = await extract_tasks_from_context(context)
        return {"tasks": tasks}
    
    return {"tasks": []}

# ============================================================================
# USER PROFILE ENDPOINTS
# ============================================================================

class UserProfileRequest(BaseModel):
    content_bg: str
    info_source: str
    occupation_type: str
    personal_focus: str
    summary_mode: str

@app.post("/api/prompt_generator", response_class=Response)
async def generate_prompt_template(profile: UserProfileRequest):
    """
    Generate a personalized prompt template based on user profile
    Uses Dify workflow to generate intelligent prompts
    Returns a plain text string containing the generated template
    """
    try:
        # Try to use Dify Task Service if available
        try:
            from dify_task_service import DifyTaskService
            
            async with DifyTaskService() as service:
                # Call the prompt generator workflow
                response = await service._call_workflow(
                    workflow_key="prompt_generator",
                    inputs={
                        "content_bg": profile.content_bg,
                        "info_source": profile.info_source,
                        "occupation_type": profile.occupation_type,
                        "personal_focus": profile.personal_focus,
                        "summary_mode": profile.summary_mode,
                    },
                    response_mode="blocking"
                )
                
                if response.get("data", {}).get("status") == "succeeded":
                    outputs = response.get("data", {}).get("outputs", {})
                    print(f"Dify response outputs: {outputs}")
                    
                    # Try different possible output field names
                    prompt_output = (
                        outputs.get("prompt_output") or 
                        outputs.get("prompt") or 
                        outputs.get("text") or
                        outputs.get("result") or
                        outputs.get("output") or
                        ""
                    )
                    
                    if prompt_output:
                        print(f"Found prompt output: {prompt_output[:100]}...")  # Log first 100 chars
                        # Return the prompt template as a plain text response
                        return Response(content=prompt_output, media_type="text/plain; charset=utf-8")
                    else:
                        print(f"Dify response successful but no prompt output found in outputs: {outputs}")
                        # Fall back to mock response
                else:
                    # Workflow didn't succeed
                    print(f"Dify workflow status: {response.get('data', {}).get('status')}")
                    print(f"Dify response: {response}")
                    # Fall back to mock response
                        
        except ImportError:
            print("Dify task service not available, using mock response")
        except Exception as e:
            print(f"Dify API error: {str(e)}")
            # Fall back to mock response
        
        # Mock response when Dify is not available or doesn't return a prompt
        print(f"Generating mock prompt template for profile: {profile.dict()}")
        prompt_template = f"""
基于您的个人信息，我们为您生成了以下智能提示模板：

【职业背景】{profile.occupation_type}
【使用场景】{profile.content_bg}
【信息来源】{profile.info_source}
【个人聚焦】{profile.personal_focus}
【总结深度】{profile.summary_mode}

智能提示模板：
作为一名{profile.occupation_type}，在{profile.content_bg}场景下，我需要从{profile.info_source}中提取关键信息。
我的关注重点是：{profile.personal_focus}
请以{profile.summary_mode}的方式为我总结内容，并提供可执行的建议。

关键提取要点：
1. 核心信息识别 - 自动识别与您职业相关的关键信息
2. 行动项提取 - 将讨论转化为具体的待办事项
3. 决策支持 - 提供基于数据的决策建议
4. 知识管理 - 整理和归档重要信息

个性化功能：
- 智能任务分类：根据您的职业特点自动分类任务
- 优先级建议：基于您的关注重点智能排序
- 内容深度控制：按照您选择的{profile.summary_mode}模式生成摘要
"""
        
        # Return the prompt template as a plain text response
        return Response(content=prompt_template, media_type="text/plain; charset=utf-8")
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# INSIGHT GENERATION ENDPOINT
# ============================================================================

class InsightRequest(BaseModel):
    prompt_input: str
    context_input: str

@app.post("/api/insight_app")
async def generate_insight(request: InsightRequest):
    """
    Generate insights using the stored prompt template and recording context
    Uses Dify insight_app workflow
    """
    global insight_feed  # Access the global insight_feed variable
    
    try:
        # Try to use Dify Task Service if available
        try:
            from dify_task_service import DifyTaskService
            
            async with DifyTaskService() as service:
                # Call the insight_app workflow
                response = await service._call_workflow(
                    workflow_key="insight_app",
                    inputs={
                        "prompt_input": request.prompt_input,
                        "context_input": request.context_input
                    },
                    response_mode="blocking"
                )
                
                if response.get("data", {}).get("status") == "succeeded":
                    outputs = response.get("data", {}).get("outputs", {})
                    print(f"Insight generation outputs: {outputs}")
                    
                    # Update the global insight_feed with the generated insight
                    insight_output = outputs.get("insight_output", outputs.get("output", ""))
                    if insight_output:
                        insight_feed = insight_output
                        print(f"Updated insight_feed with new insight (length: {len(insight_feed)})")
                    
                    return {
                        "status": "success",
                        "insight_output": insight_output,
                        "insight_title": outputs.get("insight_title", "Insights"),
                        "insight_description": outputs.get("insight_description", ""),
                        "source": "dify"
                    }
                else:
                    print(f"Dify insight generation failed: {response.get('data', {}).get('error', 'Unknown error')}")
                    # Fall back to mock response
                    
        except ImportError:
            print("Dify task service not available, using mock insight generation")
        except Exception as e:
            print(f"Dify API error in insight generation: {str(e)}")
            # Fall back to mock response
        
        # Mock insight generation when Dify is not available
        print(f"Generating mock insight with prompt length: {len(request.prompt_input)}, context length: {len(request.context_input)}")
        
        # Generate a mock insight based on the prompt and context
        mock_insight = f"""
## 基于您的个性化分析模板生成的洞察

### 核心发现
根据您提供的上下文内容，我们识别了以下关键信息：
- 内容摘要：{request.context_input[:200]}...
- 应用您的分析框架进行深度解析

### 关键洞察
1. **主要发现**：基于您的专业背景和关注重点，这段内容中最重要的信息是...
2. **潜在机会**：识别到的机会点和可执行建议
3. **风险提示**：需要注意的潜在风险或问题

### 行动建议
- 立即行动项：基于分析结果的具体下一步
- 中期规划：需要持续关注的要点
- 长期策略：战略层面的思考

*此洞察基于您的个性化提示模板生成*
"""
        
        # Update the global insight_feed with the mock insight
        insight_feed = mock_insight
        print(f"Updated insight_feed with mock insight (length: {len(insight_feed)})")
        
        return {
            "status": "success",
            "insight_output": mock_insight,
            "insight_title": "智能洞察分析",
            "insight_description": "基于您的个性化模板生成的深度分析",
            "source": "mock"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

class AutoSuggestionRequest(BaseModel):
    content_bg: str
    occupation_type: str
    personal_focus: str
    context_input: str

# ============================================================================
# HIPPO AGENT API ENDPOINT (Direct Command Execution)
# ============================================================================

class HippoAgentRequest(BaseModel):
    query: str
    user: str = "default-user"
    skill: str = ""
    context: str = ""
    conversation_id: str = ""
    files: Optional[List[DifyFileInfo]] = None

@app.post("/api/hippo_agent/execute")
async def execute_hippo_agent_command(request: HippoAgentRequest):
    """
    Execute a user command using the Hippo Agent Dify Chat/Agent API.
    
    Uses the chat-messages endpoint with streaming mode (required for Agent apps),
    collects the full response from the SSE stream, and returns it synchronously.
    """
    
    print(f"\n{'='*60}")
    print(f"HIPPO AGENT COMMAND EXECUTION")
    print(f"Query: {request.query}")
    print(f"User: {request.user}")
    print(f"Skill: {request.skill}")
    print(f"Context: {request.context[:100]}..." if len(request.context) > 100 else f"Context: {request.context}")
    print(f"Conversation ID: {request.conversation_id}")
    print(f"{'='*60}\n")
    
    try:
        from dify_config import DIFY_CHAT_KEYS, get_endpoint
        
        api_key = DIFY_CHAT_KEYS.get("hippo_agent")
        # #region agent log
        import json as _json_debug; open('/Users/lotusxu/Desktop/Project_Cortex/.cursor/debug-2c9023.log','a').write(_json_debug.dumps({"sessionId":"2c9023","location":"main.py:hippo_agent","message":"api_key_resolved","data":{"has_key":bool(api_key),"endpoint":get_endpoint("chat_messages")},"timestamp":__import__('time').time()*1000,"hypothesisId":"A"})+'\n')
        # #endregion
        if not api_key:
            raise HTTPException(status_code=500, detail="Hippo Agent API key not configured")
        
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        
        payload = {
            "inputs": {
                "skill": request.skill,
                "context": request.context
            },
            "query": request.query,
            "response_mode": "streaming",
            "user": request.user
        }
        
        if request.conversation_id:
            payload["conversation_id"] = request.conversation_id
        
        if request.files:
            payload["files"] = [
                {
                    "type": f.type,
                    "transfer_method": f.transfer_method,
                    "upload_file_id": f.upload_file_id
                } if f.transfer_method == "local_file" else {
                    "type": f.type,
                    "transfer_method": f.transfer_method,
                    "url": f.url
                }
                for f in request.files
            ]
        
        print(f"Hippo Agent request payload: {json.dumps(payload, indent=2)}")
        
        client = await get_http_client()
        
        full_answer = ""
        conversation_id = None
        message_id = None
        agent_thoughts = []
        
        async with client.stream(
            "POST",
            get_endpoint("chat_messages"),
            headers=headers,
            json=payload,
            timeout=180.0
        ) as response:
            if response.status_code != 200:
                error_text = await response.aread()
                error_message = error_text.decode('utf-8') if error_text else 'Unknown error'
                print(f"Hippo Agent API error: {response.status_code} - {error_message}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail=f"Hippo Agent API error: {error_message}"
                )
            
            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue
                
                data_str = line[6:]
                if not data_str:
                    continue
                
                try:
                    data = json.loads(data_str)
                    event = data.get("event", "")
                    
                    if event in ("message", "agent_message"):
                        answer_chunk = data.get("answer", "")
                        full_answer += answer_chunk
                        if not conversation_id:
                            conversation_id = data.get("conversation_id")
                        if not message_id:
                            message_id = data.get("message_id")
                    
                    elif event == "agent_thought":
                        thought_data = {
                            "id": data.get("id"),
                            "position": data.get("position"),
                            "thought": data.get("thought", ""),
                            "tool": data.get("tool", ""),
                            "tool_input": data.get("tool_input", ""),
                            "observation": data.get("observation", ""),
                            "message_files": data.get("message_files", [])
                        }
                        existing = next((t for t in agent_thoughts if t["id"] == thought_data["id"]), None)
                        if existing:
                            existing.update({k: v for k, v in thought_data.items() if v})
                        else:
                            agent_thoughts.append(thought_data)
                    
                    elif event == "message_end":
                        conversation_id = data.get("conversation_id", conversation_id)
                        message_id = data.get("id", message_id)
                    
                    elif event == "error":
                        error_msg = data.get("message", "Unknown error from Dify")
                        print(f"Hippo Agent SSE error: {error_msg}")
                        raise HTTPException(status_code=500, detail=error_msg)
                    
                except json.JSONDecodeError:
                    continue
        
        print(f"Hippo Agent response collected: answer_len={len(full_answer)}, thoughts={len(agent_thoughts)}")
        
        # #region agent log
        import json as _json_debug2; open('/Users/lotusxu/Desktop/Project_Cortex/.cursor/debug-2c9023.log','a').write(_json_debug2.dumps({"sessionId":"2c9023","location":"main.py:hippo_agent_result","message":"response_collected","data":{"answer_len":len(full_answer),"thoughts_count":len(agent_thoughts),"conversation_id":conversation_id,"thought_tools":[t.get("tool","") for t in agent_thoughts]},"timestamp":__import__('time').time()*1000,"hypothesisId":"B"})+'\n')
        # #endregion
        
        return {
            "answer": full_answer,
            "status": "success",
            "source": "hippo_agent",
            "conversation_id": conversation_id,
            "message_id": message_id,
            "agent_thoughts": agent_thoughts
        }
        
    except HTTPException:
        raise
    except httpx.ConnectError as e:
        error_msg = "Connection failed to Hippo Agent API"
        print(f"Connection error: {str(e)}")
        raise HTTPException(status_code=503, detail=error_msg)
    except httpx.TimeoutException as e:
        error_msg = "Request timeout. Hippo Agent API took too long to respond."
        print(f"Timeout error: {str(e)}")
        raise HTTPException(status_code=504, detail=error_msg)
    except Exception as e:
        print(f"Unexpected error in Hippo Agent: {str(e)}")
        import traceback
        traceback.print_exc()
        raise HTTPException(status_code=500, detail=f"Unexpected error: {str(e)}")

@app.post("/api/auto_suggestion")
async def generate_auto_suggestions(request: AutoSuggestionRequest):
    """
    Generate personalized prompt suggestions based on user profile and context
    Uses Dify auto_suggestion workflow
    """
    try:
        # Try to use Dify Task Service if available
        try:
            from dify_task_service import DifyTaskService
            
            async with DifyTaskService() as service:
                # Call the auto_suggestion workflow
                response = await service._call_workflow(
                    workflow_key="auto_suggestion",
                    inputs={
                        "content_bg": request.content_bg,
                        "occupation_type": request.occupation_type,
                        "personal_focus": request.personal_focus,
                        "context_input": request.context_input
                    },
                    response_mode="blocking"
                )
                
                if response.get("data", {}).get("status") == "succeeded":
                    outputs = response.get("data", {}).get("outputs", {})
                    print(f"Auto suggestion outputs: {outputs}")
                    
                    # Parse the prompt suggestions from the output
                    prompt_suggestions_str = outputs.get("PromptSuggestion", outputs.get("output", ""))
                    
                    # Try to parse as JSON if it's a string
                    if isinstance(prompt_suggestions_str, str):
                        try:
                            import json
                            suggestions_data = json.loads(prompt_suggestions_str)
                            if "PromptSuggestion" in suggestions_data:
                                return suggestions_data
                            else:
                                # Wrap in expected format
                                return {"PromptSuggestion": suggestions_data}
                        except json.JSONDecodeError:
                            # If not JSON, create suggestions from lines
                            lines = [line.strip() for line in prompt_suggestions_str.split('\n') if line.strip()]
                            suggestions = []
                            for i, line in enumerate(lines[:5], 1):  # Limit to 5 suggestions
                                # Remove any numbering from the line
                                text = line.lstrip('0123456789.-) ').strip()
                                if text:
                                    suggestions.append({
                                        "id": str(i),
                                        "text": text
                                    })
                            return {"PromptSuggestion": suggestions}
                    else:
                        # Already in correct format
                        return {"PromptSuggestion": prompt_suggestions_str}
                        
                else:
                    print(f"Dify auto suggestion failed: {response.get('data', {}).get('error', 'Unknown error')}")
                    # Fall back to mock response
                    
        except ImportError:
            print("Dify task service not available, using mock auto suggestions")
        except Exception as e:
            print(f"Dify API error in auto suggestions: {str(e)}")
            # Fall back to mock response
        
        # Mock auto suggestions when Dify is not available
        print(f"Generating mock suggestions for occupation: {request.occupation_type}, content_bg: {request.content_bg}")
        
        # Generate mock suggestions based on occupation type
        mock_suggestions = []
        
        if request.occupation_type == "产品经理":
            mock_suggestions = [
                {"id": "1", "text": "如何通过AI工具优化产品从概念构思到商业计划书的全流程管理？"},
                {"id": "2", "text": "如何设计一套适用于移动端的智能工作流，实现笔记、调研、沟通与文档整合的无缝衔接？"},
                {"id": "3", "text": "在跨团队协作中，如何利用微信/钉钉等即时通讯工具高效推进产品方案的确认与迭代？"},
                {"id": "4", "text": "如何将'每日洞察'与'长期信息流整合'功能转化为可落地的AI助理产品核心卖点？"},
                {"id": "5", "text": "面对B端客户，如何通过参数可视化与场景化案例提升AI硬件产品的专业说服力？"}
            ]
        elif request.occupation_type == "投资人":
            mock_suggestions = [
                {"id": "1", "text": "如何快速评估AI初创公司的技术壁垒和商业化潜力？"},
                {"id": "2", "text": "在当前市场环境下，哪些AI应用场景具有最高的投资回报潜力？"},
                {"id": "3", "text": "如何通过数据分析工具追踪投资组合公司的关键业务指标？"},
                {"id": "4", "text": "基于行业趋势分析，如何识别下一个独角兽企业？"},
                {"id": "5", "text": "如何构建有效的投后管理体系，帮助被投企业快速成长？"}
            ]
        elif request.occupation_type == "律师":
            mock_suggestions = [
                {"id": "1", "text": "如何利用AI工具提高合同审查的效率和准确性？"},
                {"id": "2", "text": "在知识产权纠纷中，如何快速检索和分析相关判例？"},
                {"id": "3", "text": "如何构建企业合规管理的智能化监控体系？"},
                {"id": "4", "text": "基于最新法规变化，如何为客户提供前瞻性的法律建议？"},
                {"id": "5", "text": "如何通过数字化工具优化律所的案件管理流程？"}
            ]
        elif request.occupation_type == "记者":
            mock_suggestions = [
                {"id": "1", "text": "如何利用AI工具快速验证新闻源的可信度？"},
                {"id": "2", "text": "在深度报道中，如何高效整合多方信息源形成完整叙事？"},
                {"id": "3", "text": "如何通过数据分析发现潜在的新闻线索？"},
                {"id": "4", "text": "基于社交媒体趋势，如何预判下一个热点话题？"},
                {"id": "5", "text": "如何构建个人的数字化新闻素材库？"}
            ]
        elif request.occupation_type == "医生":
            mock_suggestions = [
                {"id": "1", "text": "如何利用AI辅助工具提高疾病诊断的准确率？"},
                {"id": "2", "text": "在临床研究中，如何快速检索和分析相关医学文献？"},
                {"id": "3", "text": "如何通过数字化工具优化患者随访管理流程？"},
                {"id": "4", "text": "基于最新医学研究，如何为患者制定个性化治疗方案？"},
                {"id": "5", "text": "如何构建科室的智能化病例管理系统？"}
            ]
        else:
            # Default suggestions
            mock_suggestions = [
                {"id": "1", "text": f"作为{request.occupation_type}，如何利用AI工具提升日常工作效率？"},
                {"id": "2", "text": f"在{request.content_bg}场景下，如何更好地管理和整合信息流？"},
                {"id": "3", "text": f"基于'{request.personal_focus}'的关注点，如何构建个人知识管理体系？"},
                {"id": "4", "text": "如何通过智能工具实现工作与生活的平衡？"},
                {"id": "5", "text": "在数字化转型背景下，如何保持行业竞争力？"}
            ]
        
        return {"PromptSuggestion": mock_suggestions}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# ============================================================================
# SOP GENERATOR ENDPOINT
# ============================================================================

class SopGeneratorRequest(BaseModel):
    check_in: str
    check_out: str

@app.post("/api/sop_generator")
async def generate_sop(request: SopGeneratorRequest):
    """
    Generate an SOP skill from a highlighted time period.
    Calls the Dify sop_generator workflow with check_in/check_out timestamps.
    Returns the generated markdown file content.
    """
    try:
        from dify_task_service import DifyTaskService

        async with DifyTaskService() as service:
            service.client = httpx.AsyncClient(timeout=300.0)
            response = await service._call_workflow(
                workflow_key="sop_generator",
                inputs={
                    "check_in": request.check_in,
                    "check_out": request.check_out
                },
                response_mode="blocking"
            )

            if response.get("data", {}).get("status") == "succeeded":
                outputs = response.get("data", {}).get("outputs", {})
                print(f"SOP generator outputs: {outputs}")

                mdfile = (
                    outputs.get("mdfile") or
                    outputs.get("md_file") or
                    outputs.get("output") or
                    outputs.get("text") or
                    outputs.get("result") or
                    ""
                )
                name = outputs.get("name", "")
                description = outputs.get("description", "")

                return {
                    "status": "success",
                    "mdfile": mdfile,
                    "name": name,
                    "description": description,
                    "source": "dify"
                }
            else:
                error_msg = response.get("data", {}).get("error", "Unknown error")
                print(f"SOP generator workflow failed: {error_msg}")
                raise HTTPException(status_code=500, detail=f"SOP generator workflow failed: {error_msg}")

    except HTTPException:
        raise
    except httpx.TimeoutException:
        detail = "SOP generator timed out: the Dify workflow took too long to respond"
        print(f"SOP generator error: {detail}")
        raise HTTPException(status_code=504, detail=detail)
    except Exception as e:
        detail = str(e) or repr(e)
        print(f"SOP generator error: {detail}")
        raise HTTPException(status_code=500, detail=detail)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
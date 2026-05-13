# Backend API Server

## Overview
FastAPI backend server for the ReMind application, providing APIs for:
- Screen recording context processing
- Chat interactions with AI
- Task management and execution
- Summary generation
- Integration with Dify workflow engine

## Setup

### Requirements
- Python 3.9+
- FastAPI
- Uvicorn

### Installation
```bash
pip install -r requirements.txt
```

### Configuration
Create a `.env` file in the backend directory:
```env
# Dify API Configuration (Optional)
USE_DIFY_API=false
DIFY_API_KEY=your_api_key_here
DIFY_USER_ID=default-user

# Dify Workflow IDs
DIFY_CHAT_WORKFLOW_ID=your_chat_workflow_id
DIFY_FEISHU_WORKFLOW_ID=your_feishu_workflow_id
```

### Running the Server
```bash
python main.py
```
The server will start on http://localhost:8000

## API Endpoints

### Core Endpoints
- `GET /health` - Health check
- `POST /api/record/start` - Start screen recording
- `POST /api/record/stop` - Stop screen recording
- `POST /api/context/process` - Process screen context
- `POST /api/chat` - Chat with AI (streaming)
- `POST /api/tasks/execute` - Execute tasks
- `POST /api/summary/generate` - Generate summary
- `POST /api/prompts/suggest` - Get prompt suggestions

### Dify Integration
When `USE_DIFY_API=true`, the backend integrates with Dify workflows for:
- Advanced chat processing
- Task automation via Feishu
- Workflow-based task execution

## Architecture

### Main Components
- `main.py` - FastAPI application and route handlers
- `dify_config.py` - Dify API configuration
- `dify_integration.py` - Dify workflow integration
- `dify_task_service.py` - Task execution service
- `config.py` - General configuration

### Data Flow
1. Frontend sends requests to backend API
2. Backend processes requests (mock or via Dify)
3. Responses streamed back to frontend
4. Tasks executed through appropriate workflows

## Development

### Mock Mode
By default, the backend runs in mock mode with simulated responses. This is useful for frontend development without external dependencies.

### Production Mode
Set `USE_DIFY_API=true` and configure API keys to enable real integrations.

## Integration Points

### Screen Recording
Currently uses mock data. Can be integrated with:
- Native OS screen capture APIs
- Electron for desktop apps
- Browser screen capture APIs
- Third-party services (Loom, etc.)

### AI Processing
Supports integration with:
- OpenAI GPT models
- Anthropic Claude
- Google Gemini
- Custom LLM deployments via Dify

### Task Automation
Extensible to integrate with:
- Feishu/Lark
- Slack
- Microsoft Teams
- Email services
- Calendar applications

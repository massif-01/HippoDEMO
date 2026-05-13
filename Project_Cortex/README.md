# ReMind - AI-Powered Screen Context Assistant

## 🚀 Overview
ReMind is an intelligent assistant that captures screen context and helps you manage tasks, generate summaries, and interact with AI based on what you're working on. It features a modern SvelteKit frontend with a FastAPI backend.

## ✨ Features
- **Screen Context Recording**: Capture and process screen content
- **AI Chat Interface**: Interactive chat with context awareness
- **Task Management**: Automatic task extraction and execution
- **Smart Summaries**: Generate summaries from your work context
- **Prompt Suggestions**: Context-aware prompt recommendations
- **User Profiles**: Personalized onboarding and settings
- **Dark Mode**: Full dark mode support

## 🛠 Tech Stack
- **Frontend**: SvelteKit, TypeScript, Tailwind CSS
- **Backend**: FastAPI (Python), Uvicorn
- **AI Integration**: Support for OpenAI, Anthropic, Dify workflows
- **Task Automation**: Feishu/Lark integration ready

## 📦 Installation

### Prerequisites
- Node.js 18+ and npm
- Python 3.9+
- Git

### Frontend Setup
```bash
# Install dependencies
npm install

# Run development server
npm run dev
```
Frontend will be available at http://localhost:5173

### Backend Setup
```bash
# Navigate to backend directory
cd backend

# Install Python dependencies
pip install -r requirements.txt

# Run the server
python main.py
```
Backend API will be available at http://localhost:8000

## 🚀 Quick Start

### Using the Start Script
```bash
# Make the script executable
chmod +x start.sh

# Run both frontend and backend
./start.sh
```

### Manual Start
1. Start the backend server:
   ```bash
   cd backend && python main.py
   ```

2. In a new terminal, start the frontend:
   ```bash
   npm run dev
   ```

3. Open http://localhost:5173 in your browser

## 🔧 Configuration

### Environment Variables
Create a `.env` file in the backend directory:
```env
# Optional: Dify API Integration
USE_DIFY_API=false
DIFY_API_KEY=your_api_key
DIFY_USER_ID=default-user
```

### Development Mode
The app includes a development mode that clears localStorage on refresh. Toggle this in `src/routes/+page.svelte`:
```javascript
const DEV_MODE = false; // Set to false for production
```

## 📁 Project Structure
```
Project_Cortex/
├── src/                    # Frontend source code
│   ├── lib/               
│   │   ├── components/    # Svelte components
│   │   ├── stores/        # Svelte stores
│   │   └── utils/         # Utility functions
│   └── routes/            # SvelteKit routes
├── backend/               # Backend API server
│   ├── main.py           # FastAPI application
│   ├── dify_*.py         # Dify integration modules
│   └── requirements.txt  # Python dependencies
├── static/                # Static assets
└── package.json          # Node.js dependencies
```

## 🎯 Key Components

### Frontend Components
- **ChatPanel**: Main chat interface
- **TaskPanel**: Task management and execution
- **SummaryPanel**: Context summaries
- **OnboardingModal**: User onboarding flow
- **ProfileSettings**: User profile management
- **RecordingIndicator**: Screen recording status

### Backend Endpoints
- `/api/record/*` - Screen recording control
- `/api/context/*` - Context processing
- `/api/chat` - AI chat interaction
- `/api/tasks/*` - Task management
- `/api/summary/*` - Summary generation
- `/api/prompts/*` - Prompt suggestions

## 🔌 Integration Points

### AI Services
- OpenAI GPT models
- Anthropic Claude
- Google Gemini
- Custom LLMs via Dify

### Task Automation
- Feishu/Lark
- Email services
- Calendar applications
- Custom webhooks

## 🧪 Development

### Build for Production
```bash
# Build frontend
npm run build

# Preview production build
npm run preview
```

### Type Checking
```bash
npm run check
```

### Code Quality
```bash
# Run type checking in watch mode
npm run check:watch
```

## 📝 License
MIT

## 🤝 Contributing
Contributions are welcome! Please feel free to submit a Pull Request.

## 🐛 Known Issues
- Mock data is used by default (configure Dify for real integrations)
- Screen recording requires platform-specific implementation

## 📮 Support
For issues and questions, please use the GitHub issues tracker.
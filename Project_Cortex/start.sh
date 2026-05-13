#!/bin/bash

# Start the backend server in the background
echo "Starting backend server..."
cd backend
python3 main.py &
BACKEND_PID=$!
cd ..

# Wait a moment for the backend to start
sleep 2

# Start the frontend development server
echo "Starting frontend server..."
npm run dev &
FRONTEND_PID=$!

# Function to kill both processes on exit
cleanup() {
    echo "Shutting down servers..."
    kill $BACKEND_PID $FRONTEND_PID 2>/dev/null
    exit
}

# Set up trap to call cleanup on script exit
trap cleanup EXIT INT TERM

echo "Both servers are running!"
echo "Frontend: http://localhost:5173"
echo "Backend: http://localhost:8000"
echo "Press Ctrl+C to stop both servers"

# Wait for both processes
wait

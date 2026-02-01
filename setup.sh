#!/bin/bash
# Quick setup script for Simple RMM

echo "🚀 Simple RMM Setup Script"
echo "=========================="

# Check if we're in the right directory
if [ ! -f "server/server.js" ]; then
    echo "❌ Error: Please run this script from the simple-rmm directory"
    exit 1
fi

echo ""
echo "📦 Setting up server..."
cd server
if command -v npm &> /dev/null; then
    npm install
    echo "✅ Server dependencies installed"
else
    echo "❌ npm not found. Please install Node.js first"
    exit 1
fi
cd ..

echo ""
echo "🐍 Checking Python for agents..."
if command -v python3 &> /dev/null; then
    echo "✅ Python3 found"
    echo "📝 To install agent dependencies, run:"
    echo "   pip3 install websockets psutil Pillow"
    echo "   (On Windows: pip install websockets psutil Pillow pyautogui)"
else
    echo "⚠️  Python3 not found. Agents require Python 3.7+"
fi

echo ""
echo "🔧 Configuration"
echo "----------------"
echo "Before starting, you should:"
echo "1. Edit server/server.js and change VALID_AGENT_TOKEN for security"
echo "2. Edit agent/agent.py and update SERVER_URL to your server's IP"
echo "3. Update AGENT_TOKEN in agent.py to match the server"
echo ""

echo "🚀 Starting server..."
echo "Access the WebUI at: http://localhost:3000"
cd server
npm start

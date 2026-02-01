@echo off
REM Quick setup script for Simple RMM (Windows)

echo 🚀 Simple RMM Setup Script
echo ==========================

REM Check if we're in the right directory
if not exist "server\server.js" (
    echo ❌ Error: Please run this script from the simple-rmm directory
    exit /b 1
)

echo.
echo 📦 Setting up server...
cd server
if exist "C:\Program Files\nodejs\npm.cmd" (
    call npm install
    echo ✅ Server dependencies installed
) else (
    echo ❌ npm not found. Please install Node.js first from https://nodejs.org
    exit /b 1
)
cd ..

echo.
echo 🐍 Checking Python for agents...
python --version >nul 2>&1
if %errorlevel% == 0 (
    echo ✅ Python found
    echo 📝 Installing agent dependencies...
    pip install websockets psutil Pillow pyautogui
    echo ✅ Agent dependencies installed
) else (
    echo ⚠️  Python not found. Agents require Python 3.7+
    echo Download from: https://python.org
)

echo.
echo 🔧 Configuration
echo ----------------
echo Before starting, you should:
echo 1. Edit server\server.js and change VALID_AGENT_TOKEN for security
echo 2. Edit agent\agent.py and update SERVER_URL to your server's IP
echo 3. Update AGENT_TOKEN in agent.py to match the server
echo.

echo 🚀 To start the server:
echo    cd server
echo    npm start
echo.
echo 🌐 Then open: http://localhost:3000
pause

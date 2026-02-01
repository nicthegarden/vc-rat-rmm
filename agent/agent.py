#!/usr/bin/env python3
"""
Simple RMM Agent
Compatible with Windows and Linux
"""

import asyncio
import json
import platform
import socket
import subprocess
import sys
import threading
import time
import uuid
import os
import io
import base64
from pathlib import Path

def install_dependencies():
    """Check and install dependencies with platform-specific handling"""
    missing = []
    
    try:
        import websockets
    except ImportError:
        missing.append('websockets')
    
    try:
        import psutil
    except ImportError:
        missing.append('psutil')
    
    try:
        import PIL.Image as Image
        import PIL.ImageGrab as ImageGrab
    except ImportError:
        missing.append('Pillow')
    
    if missing:
        print(f"Missing dependencies: {', '.join(missing)}")
        print("Attempting to install...")
        
        if platform.system() == 'Linux':
            print("\n" + "="*60)
            print("Linux Prerequisites Required")
            print("="*60)
            distro = detect_linux_distro()
            
            if distro in ['debian', 'ubuntu']:
                print("\nFor Debian/Ubuntu, run these commands first:")
                print("  sudo apt update")
                print("  sudo apt install -y python3-pip python3-venv python3-dev gcc libjpeg-dev zlib1g-dev")
            elif distro in ['rhel', 'centos', 'fedora', 'rocky', 'almalinux']:
                print("\nFor RHEL/CentOS/Fedora, run these commands first:")
                print("  sudo dnf install -y python3-pip python3-devel gcc libjpeg-devel zlib-devel")
                print("  # or: sudo yum install -y python3-pip python3-devel gcc")
            elif distro in ['arch', 'manjaro']:
                print("\nFor Arch Linux, run these commands first:")
                print("  sudo pacman -Sy python-pip python-virtualenv gcc libjpeg-turbo zlib")
            else:
                print("\nPlease install these system packages manually:")
                print("  - python3-pip")
                print("  - gcc")
                print("  - Python development headers (python3-dev or python3-devel)")
                print("  - libjpeg and zlib libraries")
            
            print("\nThen install Python packages:")
            print("  pip3 install " + " ".join(missing))
            print("\nOr use the install script:")
            print("  python3 install_linux.py")
            print("="*60 + "\n")
            
            # Still try to install Python packages
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
                print("✅ Python packages installed successfully!")
            except subprocess.CalledProcessError as e:
                print(f"\n❌ Failed to install dependencies: {e}")
                print("Please install the system packages listed above first.")
                sys.exit(1)
        else:
            # Windows - just try pip install
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install"] + missing)
                if 'Pillow' in missing:
                    # Also install pyautogui for Windows
                    subprocess.check_call([sys.executable, "-m", "pip", "install", "pyautogui"])
                print("✅ Dependencies installed successfully!")
            except subprocess.CalledProcessError as e:
                print(f"\n❌ Failed to install dependencies: {e}")
                sys.exit(1)

def detect_linux_distro():
    """Detect Linux distribution"""
    if os.path.exists('/etc/os-release'):
        with open('/etc/os-release') as f:
            for line in f:
                if line.startswith('ID='):
                    return line.split('=')[1].strip().strip('"').lower()
    return 'unknown'

# Install dependencies if missing
install_dependencies()

# Now import dependencies
import websockets
import psutil
import PIL.Image as Image
import PIL.ImageGrab as ImageGrab
import select as select_module  # For tunnel I/O multiplexing

# Configuration - Change these to match your server
SERVER_URL = "ws://localhost:3000"
AGENT_TOKEN = "your-secret-agent-token-change-this"
CUSTOMER = "Default"
SITE = "Default"

class RMMClient:
    def __init__(self):
        self.agent_id = str(uuid.uuid4())
        self.hostname = socket.gethostname()
        self.os = platform.system()
        self.version = platform.version()
        self.websocket = None
        self.connected = False
        self.vnc_running = False
        self.vnc_thread = None
        self.shell_processes = {}
        
    def get_system_info(self):
        """Get current system information"""
        try:
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            disk = psutil.disk_usage('/')
            
            return {
                "cpu_percent": cpu_percent,
                "memory_percent": memory.percent,
                "memory_used_gb": round(memory.used / (1024**3), 2),
                "memory_total_gb": round(memory.total / (1024**3), 2),
                "disk_percent": disk.percent,
                "disk_used_gb": round(disk.used / (1024**3), 2),
                "disk_total_gb": round(disk.total / (1024**3), 2),
                "boot_time": psutil.boot_time(),
                "ip_address": self.get_ip_address()
            }
        except Exception as e:
            return {"error": str(e)}
    
    def get_ip_address(self):
        """Get the primary IP address"""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"
    
    async def connect(self):
        """Connect to the RMM server"""
        while True:
            try:
                print(f"Connecting to {SERVER_URL}...")
                async with websockets.connect(SERVER_URL) as websocket:
                    self.websocket = websocket
                    self.connected = True
                    
                    # Authenticate
                    await websocket.send(json.dumps({
                        "type": "auth",
                        "token": AGENT_TOKEN,
                        "agentId": self.agent_id,
                        "hostname": self.hostname,
                        "os": self.os,
                        "version": self.version,
                        "customer": CUSTOMER,
                        "site": SITE,
                        "systemInfo": self.get_system_info()
                    }))
                    
                    print(f"Connected to server as {self.agent_id}")
                    
                    # Start heartbeat
                    heartbeat_task = asyncio.create_task(self.heartbeat())
                    
                    # Handle messages
                    try:
                        async for message in websocket:
                            await self.handle_message(json.loads(message))
                    except websockets.exceptions.ConnectionClosed:
                        print("Connection closed")
                    finally:
                        heartbeat_task.cancel()
                        
            except Exception as e:
                print(f"Connection error: {e}")
                self.connected = False
                await asyncio.sleep(5)
    
    async def heartbeat(self):
        """Send periodic heartbeat"""
        while True:
            try:
                await asyncio.sleep(30)
                if self.websocket and self.connected:
                    await self.websocket.send(json.dumps({
                        "type": "heartbeat",
                        "agentId": self.agent_id,
                        "systemInfo": self.get_system_info()
                    }))
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"Heartbeat error: {e}")
    
    async def handle_message(self, data):
        """Handle incoming messages from server"""
        msg_type = data.get("type")
        
        if msg_type == "auth_success":
            print("Authentication successful")
            self.agent_id = data.get("agentId", self.agent_id)
            
        elif msg_type == "shell_exec":
            await self.handle_shell_command(data)
            
        elif msg_type == "check_updates":
            await self.check_updates()
            
        elif msg_type == "install_updates":
            await self.install_updates(data.get("updateIds", []))
            
        elif msg_type == "vnc_start":
            await self.start_vnc(data.get("quality", "medium"), data.get("fps", 15))
            
        elif msg_type == "vnc_stop":
            await self.stop_vnc()
            
        elif msg_type == "vnc_input":
            await self.handle_vnc_input(data.get("input", {}))
            
        elif msg_type == "command_result":
            # Handle command results if needed
            pass
    
    async def handle_shell_command(self, data):
        """Execute shell command"""
        command = data.get("command", "")
        session_id = data.get("sessionId", str(uuid.uuid4()))
        
        def run_command():
            try:
                if self.os == "Windows":
                    process = subprocess.Popen(
                        command,
                        shell=True,
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.PIPE,
                        text=True
                    )
                else:
                    process = subprocess.Popen(
                        ["/bin/bash", "-c", command],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        stdin=subprocess.PIPE,
                        text=True
                    )
                
                self.shell_processes[session_id] = process
                
                for line in iter(process.stdout.readline, ''):
                    if line:
                        asyncio.run_coroutine_threadsafe(
                            self.send_shell_output(session_id, line),
                            asyncio.get_event_loop()
                        )
                
                process.wait()
                asyncio.run_coroutine_threadsafe(
                    self.send_shell_exit(session_id, process.returncode),
                    asyncio.get_event_loop()
                )
                
            except Exception as e:
                asyncio.run_coroutine_threadsafe(
                    self.send_shell_output(session_id, f"Error: {str(e)}\n"),
                    asyncio.get_event_loop()
                )
                asyncio.run_coroutine_threadsafe(
                    self.send_shell_exit(session_id, 1),
                    asyncio.get_event_loop()
                )
            finally:
                if session_id in self.shell_processes:
                    del self.shell_processes[session_id]
        
        thread = threading.Thread(target=run_command)
        thread.daemon = True
        thread.start()
    
    async def send_shell_output(self, session_id, output):
        """Send shell output to server"""
        if self.websocket and self.connected:
            await self.websocket.send(json.dumps({
                "type": "shell_output",
                "agentId": self.agent_id,
                "sessionId": session_id,
                "output": output
            }))
    
    async def send_shell_exit(self, session_id, exit_code):
        """Send shell exit code to server"""
        if self.websocket and self.connected:
            await self.websocket.send(json.dumps({
                "type": "shell_exit",
                "agentId": self.agent_id,
                "sessionId": session_id,
                "exitCode": exit_code
            }))
    
    async def check_updates(self):
        """Check for available updates"""
        try:
            if self.os == "Windows":
                updates = await self.check_windows_updates()
            else:
                updates = await self.check_linux_updates()
            
            if self.websocket and self.connected:
                await self.websocket.send(json.dumps({
                    "type": "updates_list",
                    "agentId": self.agent_id,
                    "os": self.os,
                    "updates": updates
                }))
        except Exception as e:
            print(f"Error checking updates: {e}")
    
    async def check_windows_updates(self):
        """Check for Windows updates using PowerShell"""
        try:
            ps_command = """
            $UpdateSession = New-Object -ComObject Microsoft.Update.Session
            $UpdateSearcher = $UpdateSession.CreateUpdateSearcher()
            $SearchResult = $UpdateSearcher.Search("IsInstalled=0")
            $Updates = @()
            foreach ($Update in $SearchResult.Updates) {
                $Updates += @{
                    "Title" = $Update.Title
                    "Description" = $Update.Description
                    "KB" = ($Update.KBArticleIDs -join ", ")
                    "Size" = [math]::Round($Update.MaxDownloadSize / 1MB, 2)
                    "IsImportant" = $Update.IsImportant
                    "IsCritical" = $Update.IsCritical
                }
            }
            ConvertTo-Json -InputObject $Updates -Depth 3
            """
            
            result = subprocess.run(
                ["powershell", "-Command", ps_command],
                capture_output=True,
                text=True,
                timeout=60
            )
            
            if result.returncode == 0:
                updates = json.loads(result.stdout)
                if not isinstance(updates, list):
                    updates = [updates] if updates else []
                return updates
            return []
        except Exception as e:
            print(f"Error checking Windows updates: {e}")
            return []
    
    async def check_linux_updates(self):
        """Check for Linux updates"""
        try:
            updates = []
            
            # Try apt (Debian/Ubuntu)
            if os.path.exists("/usr/bin/apt"):
                subprocess.run(["apt", "update"], capture_output=True, timeout=120)
                result = subprocess.run(
                    ["apt", "list", "--upgradable"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if 'upgradable' in line and '/' in line:
                            parts = line.split()
                            if parts:
                                package = parts[0].split('/')[0]
                                version = parts[1] if len(parts) > 1 else "unknown"
                                updates.append({
                                    "Title": package,
                                    "Description": f"Version {version} available",
                                    "KB": "",
                                    "Size": 0,
                                    "IsImportant": False,
                                    "IsCritical": False
                                })
            
            # Try yum/dnf (RHEL/CentOS/Fedora)
            elif os.path.exists("/usr/bin/yum") or os.path.exists("/usr/bin/dnf"):
                cmd = "dnf" if os.path.exists("/usr/bin/dnf") else "yum"
                result = subprocess.run(
                    [cmd, "check-update"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 100:  # 100 means updates available
                    for line in result.stdout.split('\n'):
                        if line and not line.startswith('Last metadata') and not line.startswith('*'):
                            parts = line.split()
                            if len(parts) >= 2:
                                updates.append({
                                    "Title": parts[0],
                                    "Description": f"Version {parts[1]} available",
                                    "KB": "",
                                    "Size": 0,
                                    "IsImportant": False,
                                    "IsCritical": False
                                })
            
            # Try pacman (Arch Linux)
            elif os.path.exists("/usr/bin/pacman"):
                # Sync package database first
                subprocess.run(["pacman", "-Sy"], capture_output=True, timeout=60)
                result = subprocess.run(
                    ["pacman", "-Qu"],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                if result.returncode == 0:
                    for line in result.stdout.split('\n'):
                        if line:
                            parts = line.split()
                            if len(parts) >= 2:
                                updates.append({
                                    "Title": parts[0],
                                    "Description": f"Update to version {parts[1]}",
                                    "KB": "",
                                    "Size": 0,
                                    "IsImportant": False,
                                    "IsCritical": False
                                })
            
            return updates[:50]  # Limit to first 50 updates
        except Exception as e:
            print(f"Error checking Linux updates: {e}")
            return []
    
    async def install_updates(self, update_ids):
        """Install updates"""
        try:
            if self.os == "Windows":
                # Install all important updates
                ps_command = """
                $UpdateSession = New-Object -ComObject Microsoft.Update.Session
                $UpdateSearcher = $UpdateSession.CreateUpdateSearcher()
                $SearchResult = $UpdateSearcher.Search("IsInstalled=0")
                $Updates = $SearchResult.Updates | Where-Object { $_.IsImportant -or $_.IsCritical }
                if ($Updates.Count -gt 0) {
                    $Installer = $UpdateSession.CreateUpdateInstaller()
                    $Installer.Updates = $Updates
                    $InstallationResult = $Installer.Install()
                    "Installed {0} updates. Reboot required: {1}" -f $Updates.Count, $InstallationResult.RebootRequired
                } else {
                    "No important updates to install"
                }
                """
                subprocess.run(["powershell", "-Command", ps_command], check=True)
            else:
                # Linux update
                if os.path.exists("/usr/bin/apt"):
                    subprocess.run(["apt", "upgrade", "-y"], check=True)
                elif os.path.exists("/usr/bin/dnf"):
                    subprocess.run(["dnf", "update", "-y"], check=True)
                elif os.path.exists("/usr/bin/yum"):
                    subprocess.run(["yum", "update", "-y"], check=True)
                elif os.path.exists("/usr/bin/pacman"):
                    subprocess.run(["pacman", "-Su", "--noconfirm"], check=True)
            
            # Notify server of completion
            if self.websocket and self.connected:
                await self.websocket.send(json.dumps({
                    "type": "command_result",
                    "agentId": self.agent_id,
                    "result": "Updates installed successfully"
                }))
        except Exception as e:
            if self.websocket and self.connected:
                await self.websocket.send(json.dumps({
                    "type": "command_result",
                    "agentId": self.agent_id,
                    "error": str(e)
                }))
    
    async def start_vnc(self, quality="medium", fps=15):
        """Start VNC screen sharing"""
        if self.vnc_running:
            return
        
        self.vnc_running = True
        quality_settings = {
            "low": (30, 50),
            "medium": (50, 30),
            "high": (75, 15)
        }
        
        resize_percent, interval = quality_settings.get(quality, (50, 30))
        
        def capture_screen():
            while self.vnc_running:
                try:
                    # Capture screen
                    screenshot = ImageGrab.grab()
                    
                    # Resize based on quality
                    width, height = screenshot.size
                    new_size = (int(width * resize_percent / 100), int(height * resize_percent / 100))
                    screenshot = screenshot.resize(new_size, Image.Resampling.LANCZOS)
                    
                    # Convert to base64
                    buffer = io.BytesIO()
                    screenshot.save(buffer, format='JPEG', quality=70, optimize=True)
                    img_base64 = base64.b64encode(buffer.getvalue()).decode()
                    
                    # Send to server
                    if self.websocket and self.connected:
                        asyncio.run_coroutine_threadsafe(
                            self.websocket.send(json.dumps({
                                "type": "vnc_frame",
                                "agentId": self.agent_id,
                                "frame": img_base64,
                                "timestamp": time.time()
                            })),
                            asyncio.get_event_loop()
                        )
                    
                    time.sleep(1 / fps)
                except Exception as e:
                    print(f"VNC capture error: {e}")
                    time.sleep(1)
        
        self.vnc_thread = threading.Thread(target=capture_screen)
        self.vnc_thread.daemon = True
        self.vnc_thread.start()
        print(f"VNC started at {fps} FPS, {quality} quality")
    
    async def stop_vnc(self):
        """Stop VNC screen sharing"""
        self.vnc_running = False
        if self.vnc_thread:
            self.vnc_thread.join(timeout=2)
        print("VNC stopped")
    
    async def handle_vnc_input(self, input_data):
        """Handle VNC input (mouse/keyboard)"""
        try:
            if self.os == "Windows":
                import pyautogui
                
                input_type = input_data.get("type")
                if input_type == "mouse_move":
                    x, y = input_data.get("x", 0), input_data.get("y", 0)
                    pyautogui.moveTo(x, y)
                elif input_type == "mouse_click":
                    x, y = input_data.get("x", 0), input_data.get("y", 0)
                    button = input_data.get("button", "left")
                    pyautogui.click(x, y, button=button)
                elif input_type == "key":
                    key = input_data.get("key")
                    pyautogui.press(key)
        except Exception as e:
            print(f"VNC input error: {e}")

class VNCTunnelClient:
    """
    VNC Tunnel Client - Creates reverse tunnel to central server
    
    This allows VNC connections from behind NAT/firewalls by initiating
    an outbound connection to the server that acts as a relay.
    """
    
    def __init__(self, server_host, server_port, agent_id, auth_token):
        self.server_host = server_host
        self.server_port = server_port
        self.agent_id = agent_id
        self.auth_token = auth_token
        self.tunnel_socket = None
        self.vnc_server_socket = None
        self.running = False
        self.thread = None
        
    def start(self, local_vnc_port=5900):
        """Start the tunnel client"""
        if self.running:
            print("Tunnel already running")
            return
            
        self.running = True
        self.thread = threading.Thread(target=self._tunnel_loop, args=(local_vnc_port,))
        self.thread.daemon = True
        self.thread.start()
        print(f"VNC tunnel client started for port {local_vnc_port}")
        
    def stop(self):
        """Stop the tunnel client"""
        self.running = False
        if self.tunnel_socket:
            try:
                self.tunnel_socket.close()
            except:
                pass
        if self.vnc_server_socket:
            try:
                self.vnc_server_socket.close()
            except:
                pass
        if self.thread:
            self.thread.join(timeout=2)
        print("VNC tunnel client stopped")
        
    def _tunnel_loop(self, local_vnc_port):
        """Main tunnel loop"""
        while self.running:
            try:
                # Connect to central server tunnel port
                self.tunnel_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.tunnel_socket.connect((self.server_host, self.server_port))
                
                # Send authentication
                auth_msg = f"TUNNEL_AUTH:{self.agent_id}:{self.auth_token}\n"
                self.tunnel_socket.send(auth_msg.encode())
                
                print(f"Connected to tunnel server at {self.server_host}:{self.server_port}")
                
                # Connect to local VNC server (or create one)
                self.vnc_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                self.vnc_server_socket.connect(('127.0.0.1', local_vnc_port))
                
                print(f"Connected to local VNC server on port {local_vnc_port}")
                
                # Start bidirectional relay
                self._relay_data()
                
            except ConnectionRefusedError:
                print(f"Cannot connect to server {self.server_host}:{self.server_port}, retrying in 5s...")
                time.sleep(5)
            except Exception as e:
                print(f"Tunnel error: {e}")
                time.sleep(5)
            finally:
                if self.tunnel_socket:
                    try:
                        self.tunnel_socket.close()
                    except:
                        pass
                    self.tunnel_socket = None
                if self.vnc_server_socket:
                    try:
                        self.vnc_server_socket.close()
                    except:
                        pass
                    self.vnc_server_socket = None
                    
    def _relay_data(self):
        """Relay data between tunnel and VNC server"""
        import select
        
        while self.running:
            try:
                # Use select for non-blocking I/O
                readable, _, _ = select.select(
                    [self.tunnel_socket, self.vnc_server_socket], 
                    [], [], 
                    1.0
                )
                
                for sock in readable:
                    if sock == self.tunnel_socket:
                        # Data from tunnel -> VNC server
                        data = self.tunnel_socket.recv(4096)
                        if not data:
                            print("Tunnel disconnected")
                            return
                        self.vnc_server_socket.send(data)
                        
                    elif sock == self.vnc_server_socket:
                        # Data from VNC server -> tunnel
                        data = self.vnc_server_socket.recv(4096)
                        if not data:
                            print("VNC server disconnected")
                            return
                        self.tunnel_socket.send(data)
                        
            except socket.error as e:
                print(f"Relay socket error: {e}")
                return
            except Exception as e:
                print(f"Relay error: {e}")
                return

async def main():
    client = RMMClient()
    await client.connect()

if __name__ == "__main__":
    # Allow configuration via environment variables
    SERVER_URL = os.environ.get("RMM_SERVER", SERVER_URL)
    AGENT_TOKEN = os.environ.get("RMM_TOKEN", AGENT_TOKEN)
    CUSTOMER = os.environ.get("RMM_CUSTOMER", CUSTOMER)
    SITE = os.environ.get("RMM_SITE", SITE)
    
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nAgent stopped")

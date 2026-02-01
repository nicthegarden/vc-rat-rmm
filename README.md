# Simple RMM (Remote Monitoring and Management)

A lightweight, open-source RMM solution for managing Windows and Linux computer fleets. Perfect for MSPs, IT departments, and system administrators who need to monitor and manage multiple computers remotely.

## Features

### Core Features
- ✅ **Cross-platform agents** - Supports Windows and Linux
- ✅ **Real-time monitoring** - CPU, memory, disk usage, and system info
- ✅ **Remote shell access** - Execute commands on managed computers
- ✅ **Remote desktop (VNC)** - View and control remote desktops via WebUI
- ✅ **Patch management** - Check and install Windows/Linux updates
- ✅ **Organizational structure** - Categorize computers by customer and site
- ✅ **Web-based console** - Manage everything from a browser
- ✅ **VNC Reverse Tunneling** - Access agents behind NAT/firewalls via reverse tunnels

### Management Capabilities
- Organize computers by customer/site hierarchy
- Filter and search computers by various criteria
- Real-time system metrics dashboard
- Update management for Windows and Linux systems
- Interactive remote terminal access
- Screen sharing and remote control

## Quick Start

### 1. Install the Server

```bash
# Clone or download the project
cd simple-rmm/server

# Install dependencies
npm install

# Start the server
npm start
```

The server will start on port 3000 by default. Access the WebUI at `http://localhost:3000`

### 2. Install Agents

#### Windows
```powershell
# Install Python dependencies
pip install websockets psutil Pillow pyautogui

# Set environment variables
set RMM_SERVER=ws://your-server-ip:3000
set RMM_TOKEN=your-secret-agent-token-change-this
set RMM_CUSTOMER=CustomerName
set RMM_SITE=SiteName

# Run the agent
python agent.py
```

#### Linux (Debian/Ubuntu/RHEL/CentOS/Fedora/Arch)

**Option 1: Using the installer script (Recommended)**
```bash
cd agent
python3 install_linux.py
```

**Option 2: Manual installation**
```bash
# Debian/Ubuntu
sudo apt update
sudo apt install -y python3-pip python3-dev gcc libjpeg-dev zlib1g-dev

# RHEL/CentOS/Fedora/Rocky/AlmaLinux
sudo dnf install -y python3-pip python3-devel gcc libjpeg-devel zlib-devel

# Arch Linux/Manjaro
sudo pacman -Sy python-pip python-virtualenv gcc libjpeg-turbo zlib

# Install Python packages
cd agent
pip3 install -r requirements.txt
```

**Run the agent:**
```bash
export RMM_SERVER=ws://your-server-ip:3000
export RMM_TOKEN=your-secret-agent-token-change-this
export RMM_CUSTOMER=CustomerName
export RMM_SITE=SiteName

python3 agent.py
```

📖 See [docs/INSTALL_LINUX.md](docs/INSTALL_LINUX.md) for detailed Linux installation guide.

### 3. Access the Web Console

Open your browser and navigate to `http://your-server-ip:3000`

## Configuration

### Server Configuration

The server can be configured using environment variables:

- `PORT` - Server port (default: 3000)
- Change `VALID_AGENT_TOKEN` in `server.js` for security

### Agent Configuration

Agents can be configured via environment variables:

- `RMM_SERVER` - WebSocket URL of the server (default: ws://localhost:3000)
- `RMM_TOKEN` - Authentication token (must match server)
- `RMM_CUSTOMER` - Customer/organization name for grouping
- `RMM_SITE` - Site location for grouping

Or edit the defaults directly in `agent.py`:
```python
SERVER_URL = "ws://your-server:3000"
AGENT_TOKEN = "your-secret-token"
CUSTOMER = "YourCustomer"
SITE = "YourSite"
```

## Architecture

```
simple-rmm/
├── server/           # Node.js WebSocket server + WebUI
│   ├── server.js     # Main server with REST API
│   └── package.json
├── agent/            # Python agent for Windows/Linux
│   └── agent.py      # Agent with monitoring & remote control
└── webui/            # Web interface (served by server)
    └── index.html    # Single-page application
```

### Communication Flow

1. **Agent** connects to **Server** via WebSocket
2. **Agent** authenticates with token and sends system info
3. **Agent** sends periodic heartbeats with metrics
4. **WebUI** receives real-time updates via WebSocket
5. **Admin** issues commands through WebUI → Server → Agent
6. **Agent** executes commands and returns results

**Note:** Agents behind NAT or firewalls can connect to the server via reverse tunnels, enabling remote management even without direct inbound access.

## Security Considerations

⚠️ **IMPORTANT**: This is a basic RMM implementation. For production use:

1. **Change the default agent token** in `server.js`
2. **Use HTTPS/WSS** in production (configure reverse proxy)
3. **Add authentication** to the WebUI (add login system)
4. **Use strong firewall rules** - restrict agent connections
5. **Enable logging** for audit trails
6. **Regular security updates** to all components

## Requirements

### Server
- Node.js 14+ 
- npm or yarn

### Agent (Windows)
- Python 3.7+
- pip
- Windows 10/11 or Windows Server 2016+

### Agent (Linux)
- Python 3.7+
- pip3
- System packages: gcc, python3-dev/devel, libjpeg, zlib
- **Supported distributions:**
  - Debian/Ubuntu (apt)
  - RHEL/CentOS/Fedora/Rocky/AlmaLinux (yum/dnf)
  - Arch Linux/Manjaro/EndeavourOS (pacman)
- X11 display server (for VNC/screenshot features - optional)

## Troubleshooting

### Agent won't connect
- Check firewall rules allow port 3000
- Verify server URL is correct
- Ensure agent token matches server configuration

### VNC not working
- On Linux: Ensure X11 is running
- On Windows: No additional requirements
- Check that pyautogui is installed (Windows only)

### Updates not showing
- Windows: Requires PowerShell and Windows Update service
- Linux: Requires apt/yum/dnf and appropriate permissions

## Production Deployment

### Using systemd (Linux)

Create `/etc/systemd/system/rmm-server.service`:
```ini
[Unit]
Description=RMM Server
After=network.target

[Service]
Type=simple
User=rmm
WorkingDirectory=/opt/simple-rmm/server
ExecStart=/usr/bin/node server.js
Restart=always

[Install]
WantedBy=multi-user.target
```

### Using NSSM (Windows)

```powershell
# Install agent as Windows service
nssm install RMM-Agent "C:\Python39\python.exe" "C:\simple-rmm\agent\agent.py"
nssm start RMM-Agent
```

## API Endpoints

### Agents
- `GET /api/agents` - List all agents
- `GET /api/agents/:id` - Get specific agent
- `GET /api/agents/by-customer/:customer` - Filter by customer
- `GET /api/agents/by-site/:site` - Filter by site
- `PATCH /api/agents/:id` - Update agent metadata

### Remote Control
- `POST /api/agents/:id/shell` - Execute shell command
- `POST /api/agents/:id/vnc/start` - Start remote desktop
- `POST /api/agents/:id/vnc/stop` - Stop remote desktop
- `POST /api/agents/:id/vnc/input` - Send input events

### Updates
- `POST /api/agents/:id/updates` - Check for updates
- `POST /api/agents/:id/updates/install` - Install updates

### Organization
- `GET /api/organizations` - Get customers and sites

## Development

### Adding New Features

1. **Agent Features**: Modify `agent.py` to add new capabilities
2. **Server Features**: Extend `server.js` with new endpoints
3. **UI Features**: Update `webui/index.html` with new interfaces

### Testing

```bash
# Test server
cd server
npm install
npm start

# Test agent (in another terminal)
cd agent
pip install websockets psutil Pillow
python agent.py
```

## License

MIT License - Free for personal and commercial use

## Contributing

Contributions welcome! Please:
1. Fork the repository
2. Create a feature branch
3. Submit a pull request

## Support

For issues and questions:
- Check the troubleshooting section
- Review the code for your specific use case
- Consider the architecture for your environment

---

**Note**: This is a simplified RMM for demonstration and small-scale use. For enterprise deployments, consider:
- Adding proper authentication/authorization
- Implementing database persistence
- Adding SSL/TLS encryption
- Setting up monitoring and alerting
- Creating automated deployment scripts

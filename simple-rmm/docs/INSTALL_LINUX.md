# Installing the Agent on Linux

This guide covers installing the Simple RMM agent on various Linux distributions.

## Quick Install

### Option 1: Using the Installer Script (Recommended)

```bash
cd agent
python3 install_linux.py
```

This script will:
- Detect your Linux distribution
- Install system dependencies (pip, gcc, development headers)
- Install Python packages (websockets, psutil, Pillow)

### Option 2: Manual Installation

#### Debian/Ubuntu
```bash
# Install system dependencies
sudo apt update
sudo apt install -y python3-pip python3-venv python3-dev gcc libjpeg-dev zlib1g-dev

# Install Python packages
cd agent
pip3 install -r requirements.txt
```

#### RHEL/CentOS/Fedora/Rocky/AlmaLinux
```bash
# Install system dependencies (use dnf for newer distros, yum for older)
sudo dnf install -y python3-pip python3-devel gcc libjpeg-devel zlib-devel
# OR for older systems:
# sudo yum install -y python3-pip python3-devel gcc

# Install Python packages
cd agent
pip3 install -r requirements.txt
```

#### Arch Linux / Manjaro / EndeavourOS
```bash
# Install system dependencies
sudo pacman -Sy python-pip python-virtualenv gcc libjpeg-turbo zlib

# Install Python packages
cd agent
pip3 install -r requirements.txt
```

## Running the Agent

### Basic Usage
```bash
python3 agent.py
```

### With Environment Variables
```bash
export RMM_SERVER=ws://your-server-ip:3000
export RMM_TOKEN=your-secret-token
export RMM_CUSTOMER=YourCompany
export RMM_SITE=MainOffice

python3 agent.py
```

### Using systemd (Auto-start on boot)

Create `/etc/systemd/system/rmm-agent.service`:
```ini
[Unit]
Description=RMM Agent
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/opt/simple-rmm/agent
Environment="RMM_SERVER=ws://your-server-ip:3000"
Environment="RMM_TOKEN=your-secret-token"
Environment="RMM_CUSTOMER=YourCompany"
Environment="RMM_SITE=MainOffice"
ExecStart=/usr/bin/python3 /opt/simple-rmm/agent/agent.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl daemon-reload
sudo systemctl enable rmm-agent
sudo systemctl start rmm-agent
sudo systemctl status rmm-agent
```

## Troubleshooting

### Import Errors

If you see import errors when running the agent, the dependencies are not installed:
```
ModuleNotFoundError: No module named 'websockets'
```

**Solution**: Run the installer script or install manually as shown above.

### Permission Denied on Package Installation

If pip fails with permission errors:
```
Permission denied: '/usr/local/lib/python3.x/dist-packages/'
```

**Solutions**:
1. Use `--user` flag: `pip3 install --user -r requirements.txt`
2. Or use sudo: `sudo pip3 install -r requirements.txt` (not recommended)
3. Or use a virtual environment (recommended for production)

### Screenshot/VNC Not Working

On Linux, the agent needs a display server (X11 or Wayland) to capture screenshots.

**For headless servers**:
- VNC will not work (this is expected)
- Shell commands and monitoring will still work
- To enable VNC, install a desktop environment or VNC server

### Connection Issues

If the agent can't connect to the server:
1. Check firewall rules: `sudo ufw allow 3000` or `sudo firewall-cmd --add-port=3000/tcp`
2. Verify server URL is correct
3. Check that the agent token matches the server configuration

## Distribution-Specific Notes

### Arch Linux
- Uses `pacman` for system updates
- Screenshot support requires `scrot` or `maim` for better compatibility

### RHEL/CentOS 7
- Uses `yum` instead of `dnf`
- May need EPEL repository: `sudo yum install -y epel-release`

### Ubuntu Server
- Minimal installs may need additional packages: `sudo apt install -y python3-venv`
- Desktop features require installing a desktop environment

## Security Considerations

1. **Change the default token** in both `agent.py` and `server.js`
2. **Use HTTPS/WSS** in production (configure reverse proxy with nginx)
3. **Limit agent permissions** - run as non-root when possible (some features may require root)
4. **Firewall rules** - only allow agent connections from trusted IPs
5. **Regular updates** - keep the system and agent updated

## Auto-Installation Feature

The agent has built-in auto-installation that will:
- Detect missing Python packages
- Display distribution-specific instructions
- Attempt to install packages automatically

However, on Linux, system packages (gcc, development headers) must be installed first using your package manager.

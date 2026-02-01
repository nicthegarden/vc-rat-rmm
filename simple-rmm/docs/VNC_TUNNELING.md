# VNC Reverse Tunneling Feature

This feature allows VNC connections to agents behind NAT/firewalls by creating a reverse tunnel from the agent to the central server.

## How It Works

### Architecture

```
┌─────────────┐         ┌──────────────┐         ┌─────────────┐
│   Admin     │────────▶│   Server     │◀────────│   Agent     │
│ (VNC Client)│  TCP    │ (Port 5900+) │  Tunnel │ (Outbound)  │
└─────────────┘         └──────────────┘         └─────────────┘
```

1. **Agent initiates** an outbound TCP connection to the server's tunnel port (default: 5900)
2. **Server assigns** a unique local port for this tunnel
3. **Admin connects** to the server's assigned port with a VNC client
4. **Server relays** traffic between the admin and the agent through the tunnel

This approach works even when:
- Agents are behind NAT
- Agents are behind firewalls
- Agents don't have public IP addresses
- Only outbound connections are allowed

## Server Configuration

### Environment Variables

```bash
# Base port for tunnel allocation (default: 5900)
VNC_TUNNEL_PORT=5900

# Server will allocate ports from VNC_TUNNEL_PORT to VNC_TUNNEL_PORT+1000
```

### Starting the Server

The VNC tunnel manager starts automatically with the server:

```bash
cd simple-rmm/server
npm install
npm start
```

You'll see:
```
VNC Tunnel Admin server listening on port 5900
RMM Server running on port 3000
WebUI available at http://localhost:3000
```

## Agent Configuration

### Starting the Tunnel Client

The agent needs a local VNC server running (e.g., TightVNC, RealVNC, TigerVNC, or the built-in Windows VNC).

Edit `agent.py` and set your VNC server port (default is 5900):

```python
# In the agent configuration section
VNC_SERVER_PORT = 5900  # Your local VNC server port
```

Or use the WebUI to request a tunnel, and the agent will:
1. Receive the tunnel request from the server
2. Start connecting to the server's tunnel port
3. Connect to the local VNC server
4. Relay traffic between them

### Manual Tunnel Start

For advanced use, you can start the tunnel manually in the agent:

```python
from agent import VNCTunnelClient

# Create tunnel client
tunnel = VNCTunnelClient(
    server_host='your-server.com',
    server_port=5900,
    agent_id='your-agent-id',
    auth_token='your-token'
)

# Start tunnel (connects local VNC on port 5900)
tunnel.start(local_vnc_port=5900)
```

## Using the WebUI

### Creating a Tunnel

1. Open the WebUI and click on an agent
2. Go to the **Remote Desktop** tab
3. Click **"Create VNC Tunnel"** button
4. Wait for tunnel to be established
5. Note the connection details shown (hostname:port)

### Connecting via VNC Client

Use any VNC client (TightVNC Viewer, RealVNC, etc.):

```
Server: your-rmm-server.com
Port: 5900-6900 (assigned port shown in WebUI)
```

The WebUI will display:
- Tunnel status (active/inactive)
- Connection endpoint (hostname:port)
- Connection time
- Data transferred

### Closing a Tunnel

1. In the WebUI, click **"Close VNC Tunnel"**
2. Or disconnect from the agent side
3. Tunnels automatically close when the agent disconnects

## API Endpoints

### Get Tunnel Status
```http
GET /api/agents/:id/vnc-tunnel
```

Response:
```json
{
  "active": true,
  "tunnelId": "uuid",
  "localPort": 5901,
  "host": "localhost",
  "hasAdmin": true,
  "createdAt": "2024-01-15T10:30:00Z",
  "bytesTransferred": {
    "toAgent": 1024000,
    "toAdmin": 2048000
  }
}
```

### Create Tunnel
```http
POST /api/agents/:id/vnc-tunnel/create
```

Response:
```json
{
  "success": true,
  "message": "Tunnel creation requested"
}
```

### Close Tunnel
```http
POST /api/agents/:id/vnc-tunnel/close
```

### List All Tunnels
```http
GET /api/vnc-tunnels
```

## Security Considerations

⚠️ **Important Security Notes:**

1. **Change Default Token**: Update `VALID_AGENT_TOKEN` in both server and agent
2. **Use Firewall Rules**: Restrict access to tunnel ports (5900-6900) to trusted IPs
3. **Enable VNC Authentication**: Configure your local VNC server with strong passwords
4. **Use VPN**: For production, consider VPN access to the RMM server
5. **Monitor Connections**: Review active tunnels regularly in the WebUI
6. **Set Port Range**: Adjust `VNC_TUNNEL_PORT` to use non-standard ports

### Authentication Flow

1. Agent authenticates with token when requesting tunnel
2. Server validates token and creates tunnel
3. Admin connects with VNC client to server's assigned port
4. Server sends auth handshake: `TUNNEL_AUTH:<agentId>:<token>`
5. Tunnel only accepts traffic after successful authentication

## Troubleshooting

### Tunnel Won't Connect

**Check server logs:**
```bash
# Server should show:
# "VNC Tunnel Admin server listening on port 5900"
```

**Verify port availability:**
```bash
# Check if port is in use
netstat -tlnp | grep 5900
```

**Check firewall:**
```bash
# Linux
sudo ufw allow 5900:6900/tcp

# Or iptables
sudo iptables -A INPUT -p tcp --dport 5900:6900 -j ACCEPT
```

### Agent Can't Create Tunnel

**Check agent connection:**
- Verify agent is online in WebUI
- Check WebSocket connection is active
- Review agent logs for errors

**Test connectivity:**
```bash
# From agent machine
telnet your-server.com 5900
```

### VNC Client Can't Connect

**Verify tunnel is active:**
- Check WebUI shows tunnel status as "active"
- Check server logs for connection attempts

**Test with netcat:**
```bash
# Test if port is open
nc -zv your-server.com 5901
```

### Connection Drops

**Check timeout settings:**
- Tunnels stay open for reconnection by default
- Agent automatically reconnects on disconnect
- Monitor with: `watch -n 1 'netstat -an | grep 5900'`

## Comparison: Push VNC vs Tunnel VNC

| Feature | Push VNC | Tunnel VNC |
|---------|----------|------------|
| Works behind NAT | ✅ Yes | ✅ Yes |
| Firewall friendly | ✅ Outbound only | ✅ Outbound only |
| Requires local VNC | ❌ No | ✅ Yes |
| Performance | 📊 Good | 📊 Excellent |
| Any VNC client | ❌ Web only | ✅ Any client |
| Setup complexity | 🟢 Easy | 🟡 Medium |
| Best for | Quick view | Full control |

## Examples

### Example 1: Access Remote Server Behind NAT

**Scenario**: Linux server in remote office, no public IP

**Solution**:
1. Install agent on remote server
2. Install TigerVNC: `sudo apt install tigervnc-standalone-server`
3. Start VNC server: `vncserver :1 -geometry 1920x1080`
4. In WebUI, click agent → Create VNC Tunnel
5. Connect with VNC client to `your-rmm-server.com:5901`
6. Enter VNC password when prompted

### Example 2: Support Remote Windows User

**Scenario**: Windows 10 user needs IT support

**Solution**:
1. Install agent on Windows PC
2. Enable Windows built-in VNC or install TightVNC
3. Create tunnel via WebUI
4. Connect with VNC viewer
5. Control desktop and assist user

### Example 3: Managing Multiple Servers

**Scenario**: 50 Linux servers in data center

**Solution**:
1. Deploy agent to all servers with Ansible/Puppet
2. Install VNC server on each
3. Use WebUI to create tunnels on-demand
4. Each gets unique port (5901, 5902, etc.)
5. Document port assignments

## Advanced Configuration

### Custom Port Range

```javascript
// In server.js, modify VNCTunnelManager
const vncTunnelManager = new VNCTunnelManager();
vncTunnelManager.minPort = 15000;
vncTunnelManager.maxPort = 16000;
```

### Using with Reverse Proxy

For production with nginx:

```nginx
stream {
    server {
        listen 5900;
        proxy_pass localhost:5900;
    }
}
```

### SSL/TLS for Tunnel

For encrypted tunnels, wrap with stunnel or use VPN:

```bash
# Using SSH tunnel as wrapper
ssh -L 5900:localhost:5900 user@rmm-server.com
```

## Integration with Existing Tools

### Connect from Mobile

Use VNC clients like:
- **iOS**: Screens, Jump Desktop
- **Android**: VNC Viewer (RealVNC), bVNC

Connect to `your-server.com:assigned-port`

### Automation Scripts

```bash
#!/bin/bash
# Auto-connect to agent tunnel

AGENT_ID=$1
SERVER="rmm.example.com"

# Get tunnel info via API
TUNNEL_INFO=$(curl -s "http://${SERVER}/api/agents/${AGENT_ID}/vnc-tunnel")
PORT=$(echo $TUNNEL_INFO | jq -r '.localPort')

# Connect with vncviewer
vncviewer ${SERVER}:${PORT}
```

## Future Enhancements

Potential improvements:
- [ ] Built-in VNC server in agent (no external VNC needed)
- [ ] Web-based VNC client (noVNC integration)
- [ ] Recording/playback of sessions
- [ ] Multi-user support with permissions
- [ ] Clipboard synchronization
- [ ] File transfer over tunnel
- [ ] Audio forwarding

---

**Note**: This tunneling feature complements the existing push-based VNC. Use push VNC for quick checks and tunnel VNC for extended sessions or when you need full VNC client features.

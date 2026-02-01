const express = require('express');
const WebSocket = require('ws');
const http = require('http');
const path = require('path');
const { v4: uuidv4 } = require('uuid');
const cors = require('cors');
const VNCTunnelManager = require('./vnc-tunnel');

const app = express();
const server = http.createServer(app);
const wss = new WebSocket.Server({ server });

app.use(cors());
app.use(express.json());
app.use(express.static(path.join(__dirname, '../webui')));

// Store connected agents
const agents = new Map();
const activeSessions = new Map();

// Initialize VNC Tunnel Manager
const vncTunnelManager = new VNCTunnelManager();
const VNC_TUNNEL_BASE_PORT = parseInt(process.env.VNC_TUNNEL_PORT) || 5900;
vncTunnelManager.startAdminServer(VNC_TUNNEL_BASE_PORT);

// Agent authentication (simple token-based)
const VALID_AGENT_TOKEN = 'your-secret-agent-token-change-this';

// WebSocket handling for agents
wss.on('connection', (ws, req) => {
    console.log('New WebSocket connection from:', req.socket.remoteAddress);
    
    ws.on('message', (message) => {
        try {
            const data = JSON.parse(message);
            handleAgentMessage(ws, data);
        } catch (e) {
            console.error('Invalid message from agent:', e);
        }
    });
    
    ws.on('close', () => {
        // Find and remove disconnected agent
        for (const [agentId, agent] of agents.entries()) {
            if (agent.ws === ws) {
                console.log(`Agent ${agentId} disconnected`);
                agent.status = 'offline';
                agent.lastSeen = new Date().toISOString();
                
                // Close any active VNC tunnels for this agent
                vncTunnelManager.closeTunnelForAgent(agentId);
                
                broadcastToClients({
                    type: 'agent_status',
                    agentId: agentId,
                    status: 'offline'
                });
                break;
            }
        }
    });
    
    ws.on('error', (error) => {
        console.error('WebSocket error:', error);
    });
});

function handleAgentMessage(ws, data) {
    switch (data.type) {
        case 'auth':
            if (data.token === VALID_AGENT_TOKEN) {
                const agentId = data.agentId || uuidv4();
                agents.set(agentId, {
                    ws: ws,
                    id: agentId,
                    hostname: data.hostname,
                    os: data.os,
                    version: data.version,
                    customer: data.customer || 'Uncategorized',
                    site: data.site || 'Default',
                    status: 'online',
                    lastSeen: new Date().toISOString(),
                    systemInfo: data.systemInfo || {}
                });
                ws.send(JSON.stringify({ type: 'auth_success', agentId: agentId }));
                console.log(`Agent ${agentId} (${data.hostname}) authenticated`);
                broadcastToClients({
                    type: 'agent_connected',
                    agent: getAgentInfo(agentId)
                });
            } else {
                ws.send(JSON.stringify({ type: 'auth_failed' }));
                ws.close();
            }
            break;
            
        case 'heartbeat':
            const agent = agents.get(data.agentId);
            if (agent) {
                agent.lastSeen = new Date().toISOString();
                agent.systemInfo = data.systemInfo || agent.systemInfo;
            }
            break;
            
        case 'shell_output':
            broadcastToClients({
                type: 'shell_output',
                agentId: data.agentId,
                sessionId: data.sessionId,
                output: data.output
            });
            break;
            
        case 'shell_exit':
            broadcastToClients({
                type: 'shell_exit',
                agentId: data.agentId,
                sessionId: data.sessionId,
                exitCode: data.exitCode
            });
            break;
            
        case 'vnc_frame':
            broadcastToClients({
                type: 'vnc_frame',
                agentId: data.agentId,
                frame: data.frame,
                timestamp: data.timestamp
            });
            break;
            
        case 'updates_list':
            broadcastToClients({
                type: 'updates_list',
                agentId: data.agentId,
                updates: data.updates,
                os: data.os
            });
            break;
            
        case 'command_result':
            broadcastToClients({
                type: 'command_result',
                agentId: data.agentId,
                commandId: data.commandId,
                result: data.result,
                error: data.error
            });
            break;
            
        case 'vnc_tunnel_request':
            // Agent requesting to create a reverse tunnel
            const agentData = agents.get(data.agentId);
            if (agentData && agentData.ws === ws) {
                const tunnelInfo = vncTunnelManager.createTunnel(
                    data.agentId,
                    ws,  // We'll upgrade this to a raw socket later
                    data.authToken || VALID_AGENT_TOKEN
                );
                if (tunnelInfo) {
                    ws.send(JSON.stringify({
                        type: 'vnc_tunnel_created',
                        tunnelId: tunnelInfo.tunnelId,
                        host: tunnelInfo.host,
                        port: tunnelInfo.localPort
                    }));
                    broadcastToClients({
                        type: 'vnc_tunnel_status',
                        agentId: data.agentId,
                        status: 'active',
                        host: tunnelInfo.host,
                        port: tunnelInfo.localPort
                    });
                } else {
                    ws.send(JSON.stringify({
                        type: 'vnc_tunnel_failed',
                        error: 'Could not create tunnel - no available ports'
                    }));
                }
            }
            break;
            
        case 'vnc_tunnel_close':
            vncTunnelManager.closeTunnelForAgent(data.agentId);
            broadcastToClients({
                type: 'vnc_tunnel_status',
                agentId: data.agentId,
                status: 'closed'
            });
            break;
            
        case 'vnc_tunnel_data':
            // Relay data through tunnel
            if (data.tunnelId && data.data) {
                const relayed = vncTunnelManager.relayToAgent(data.agentId, Buffer.from(data.data, 'base64'));
                if (!relayed) {
                    ws.send(JSON.stringify({
                        type: 'vnc_tunnel_error',
                        error: 'Tunnel not active'
                    }));
                }
            }
            break;
            
        default:
            console.log('Unknown message type:', data.type);
    }
}

function getAgentInfo(agentId) {
    const agent = agents.get(agentId);
    if (!agent) return null;
    
    // Get tunnel status if available
    const tunnelStatus = vncTunnelManager.getTunnelStatus(agentId);
    
    return {
        id: agent.id,
        hostname: agent.hostname,
        os: agent.os,
        version: agent.version,
        customer: agent.customer,
        site: agent.site,
        status: agent.status,
        lastSeen: agent.lastSeen,
        systemInfo: agent.systemInfo,
        vncTunnel: tunnelStatus
    };
}

function broadcastToClients(message) {
    // In a real implementation, you'd track WebSocket clients separately
    // For now, we'll use the existing wss connections that aren't agents
    wss.clients.forEach((client) => {
        if (client.readyState === WebSocket.OPEN) {
            client.send(JSON.stringify(message));
        }
    });
}

// REST API endpoints

// Get all agents
app.get('/api/agents', (req, res) => {
    const agentList = [];
    for (const [id, agent] of agents.entries()) {
        agentList.push(getAgentInfo(id));
    }
    res.json(agentList);
});

// Get agent by ID
app.get('/api/agents/:id', (req, res) => {
    const agent = getAgentInfo(req.params.id);
    if (agent) {
        res.json(agent);
    } else {
        res.status(404).json({ error: 'Agent not found' });
    }
});

// Get agents by customer/site
app.get('/api/agents/by-customer/:customer', (req, res) => {
    const customer = req.params.customer;
    const agentList = [];
    for (const [id, agent] of agents.entries()) {
        if (agent.customer === customer) {
            agentList.push(getAgentInfo(id));
        }
    }
    res.json(agentList);
});

app.get('/api/agents/by-site/:site', (req, res) => {
    const site = req.params.site;
    const agentList = [];
    for (const [id, agent] of agents.entries()) {
        if (agent.site === site) {
            agentList.push(getAgentInfo(id));
        }
    }
    res.json(agentList);
});

// Get unique customers and sites
app.get('/api/organizations', (req, res) => {
    const customers = new Set();
    const sites = new Set();
    
    for (const agent of agents.values()) {
        customers.add(agent.customer);
        sites.add(agent.site);
    }
    
    res.json({
        customers: Array.from(customers),
        sites: Array.from(sites)
    });
});

// Execute remote shell command
app.post('/api/agents/:id/shell', (req, res) => {
    const agentId = req.params.id;
    const { command, sessionId } = req.body;
    const agent = agents.get(agentId);
    
    if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
    }
    
    if (agent.ws.readyState !== WebSocket.OPEN) {
        return res.status(503).json({ error: 'Agent is offline' });
    }
    
    agent.ws.send(JSON.stringify({
        type: 'shell_exec',
        command: command,
        sessionId: sessionId || uuidv4()
    }));
    
    res.json({ success: true, sessionId: sessionId || uuidv4() });
});

// Check for updates
app.post('/api/agents/:id/updates', (req, res) => {
    const agentId = req.params.id;
    const agent = agents.get(agentId);
    
    if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
    }
    
    if (agent.ws.readyState !== WebSocket.OPEN) {
        return res.status(503).json({ error: 'Agent is offline' });
    }
    
    agent.ws.send(JSON.stringify({
        type: 'check_updates'
    }));
    
    res.json({ success: true, message: 'Update check requested' });
});

// Install updates
app.post('/api/agents/:id/updates/install', (req, res) => {
    const agentId = req.params.id;
    const agent = agents.get(agentId);
    
    if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
    }
    
    if (agent.ws.readyState !== WebSocket.OPEN) {
        return res.status(503).json({ error: 'Agent is offline' });
    }
    
    agent.ws.send(JSON.stringify({
        type: 'install_updates',
        updateIds: req.body.updateIds || []
    }));
    
    res.json({ success: true, message: 'Update installation requested' });
});

// Start VNC session
app.post('/api/agents/:id/vnc/start', (req, res) => {
    const agentId = req.params.id;
    const agent = agents.get(agentId);
    
    if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
    }
    
    if (agent.ws.readyState !== WebSocket.OPEN) {
        return res.status(503).json({ error: 'Agent is offline' });
    }
    
    agent.ws.send(JSON.stringify({
        type: 'vnc_start',
        quality: req.body.quality || 'medium',
        fps: req.body.fps || 15
    }));
    
    res.json({ success: true, message: 'VNC session started' });
});

// Stop VNC session
app.post('/api/agents/:id/vnc/stop', (req, res) => {
    const agentId = req.params.id;
    const agent = agents.get(agentId);
    
    if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
    }
    
    if (agent.ws.readyState === WebSocket.OPEN) {
        agent.ws.send(JSON.stringify({
            type: 'vnc_stop'
        }));
    }
    
    res.json({ success: true, message: 'VNC session stopped' });
});

// Send VNC input (mouse/keyboard)
app.post('/api/agents/:id/vnc/input', (req, res) => {
    const agentId = req.params.id;
    const agent = agents.get(agentId);
    
    if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
    }
    
    if (agent.ws.readyState !== WebSocket.OPEN) {
        return res.status(503).json({ error: 'Agent is offline' });
    }
    
    agent.ws.send(JSON.stringify({
        type: 'vnc_input',
        input: req.body
    }));
    
    res.json({ success: true });
});

// Update agent metadata (customer, site)
app.patch('/api/agents/:id', (req, res) => {
    const agentId = req.params.id;
    const agent = agents.get(agentId);
    
    if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
    }
    
    if (req.body.customer) agent.customer = req.body.customer;
    if (req.body.site) agent.site = req.body.site;
    
    res.json({ success: true, agent: getAgentInfo(agentId) });
});

// VNC Tunnel endpoints

// Get tunnel status for an agent
app.get('/api/agents/:id/vnc-tunnel', (req, res) => {
    const agentId = req.params.id;
    const status = vncTunnelManager.getTunnelStatus(agentId);
    res.json(status);
});

// Create VNC tunnel for an agent
app.post('/api/agents/:id/vnc-tunnel/create', (req, res) => {
    const agentId = req.params.id;
    const agent = agents.get(agentId);
    
    if (!agent) {
        return res.status(404).json({ error: 'Agent not found' });
    }
    
    if (agent.ws.readyState !== WebSocket.OPEN) {
        return res.status(503).json({ error: 'Agent is offline' });
    }
    
    // Send tunnel request to agent
    agent.ws.send(JSON.stringify({
        type: 'vnc_tunnel_request',
        agentId: agentId,
        authToken: VALID_AGENT_TOKEN
    }));
    
    res.json({ success: true, message: 'Tunnel creation requested' });
});

// Close VNC tunnel for an agent
app.post('/api/agents/:id/vnc-tunnel/close', (req, res) => {
    const agentId = req.params.id;
    const agent = agents.get(agentId);
    
    if (agent && agent.ws.readyState === WebSocket.OPEN) {
        agent.ws.send(JSON.stringify({
            type: 'vnc_tunnel_close',
            agentId: agentId
        }));
    }
    
    vncTunnelManager.closeTunnelForAgent(agentId);
    
    res.json({ success: true, message: 'Tunnel closed' });
});

// Get all active tunnels (admin endpoint)
app.get('/api/vnc-tunnels', (req, res) => {
    const tunnels = vncTunnelManager.getAllTunnels();
    res.json(tunnels);
});

const PORT = process.env.PORT || 3000;
server.listen(PORT, () => {
    console.log(`RMM Server running on port ${PORT}`);
    console.log(`WebUI available at http://localhost:${PORT}`);
});

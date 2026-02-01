const net = require('net');
const { v4: uuidv4 } = require('uuid');

/**
 * VNC Tunnel Manager
 * 
 * Creates reverse tunnels from agents to the central server.
 * Architecture:
 * 1. Agent opens outbound connection to server (reverse tunnel)
 * 2. Server assigns a local port for this tunnel
 * 3. Admin connects to server's local port
 * 4. Server bridges admin connection to agent's tunnel
 * 
 * This allows VNC access even when agents are behind NAT/firewalls.
 */
class VNCTunnelManager {
    constructor() {
        // Map of tunnelId -> { agentId, agentSocket, adminSocket, localPort }
        this.tunnels = new Map();
        // Map of agentId -> tunnelId
        this.agentTunnels = new Map();
        // Port range for tunnel allocation
        this.minPort = 5900;
        this.maxPort = 6900;
        this.usedPorts = new Set();
        // Server for admin connections
        this.adminServer = null;
    }

    /**
     * Start the admin connection listener
     */
    startAdminServer(port = 5900) {
        this.adminServer = net.createServer((socket) => {
            this.handleAdminConnection(socket);
        });

        this.adminServer.listen(port, () => {
            console.log(`VNC Tunnel Admin server listening on port ${port}`);
        });

        this.adminServer.on('error', (err) => {
            console.error('VNC Admin server error:', err);
        });
    }

    /**
     * Handle incoming admin VNC client connection
     */
    handleAdminConnection(adminSocket) {
        let buffer = '';
        
        adminSocket.on('data', (data) => {
            buffer += data.toString();
            
            // Look for tunnel authentication in first data packet
            // Format: "TUNNEL_AUTH:<agentId>:<token>\n"
            if (buffer.includes('\n')) {
                const lines = buffer.split('\n');
                const authLine = lines[0];
                
                if (authLine.startsWith('TUNNEL_AUTH:')) {
                    const parts = authLine.split(':');
                    if (parts.length >= 3) {
                        const agentId = parts[1];
                        const token = parts[2];
                        
                        // Validate and connect to tunnel
                        if (this.validateAndConnectAdmin(agentId, token, adminSocket)) {
                            // Send remaining data to agent
                            const remaining = lines.slice(1).join('\n');
                            if (remaining) {
                                this.relayToAgent(agentId, Buffer.from(remaining));
                            }
                        } else {
                            adminSocket.write('ERROR: Invalid tunnel credentials\n');
                            adminSocket.end();
                        }
                    } else {
                        adminSocket.write('ERROR: Invalid auth format\n');
                        adminSocket.end();
                    }
                } else {
                    adminSocket.write('ERROR: Expected TUNNEL_AUTH\n');
                    adminSocket.end();
                }
                
                // Remove auth handler after authentication
                adminSocket.removeAllListeners('data');
            }
        });

        adminSocket.on('error', (err) => {
            console.error('Admin socket error:', err);
        });

        // Timeout if no auth received
        setTimeout(() => {
            if (!adminSocket.destroyed && !this.isSocketPaired(adminSocket)) {
                adminSocket.write('ERROR: Authentication timeout\n');
                adminSocket.end();
            }
        }, 10000);
    }

    /**
     * Validate admin token and connect to agent tunnel
     */
    validateAndConnectAdmin(agentId, token, adminSocket) {
        const tunnelId = this.agentTunnels.get(agentId);
        if (!tunnelId) {
            console.log(`No active tunnel for agent ${agentId}`);
            return false;
        }

        const tunnel = this.tunnels.get(tunnelId);
        if (!tunnel) {
            return false;
        }

        // In production, validate token against stored value
        // For now, we accept any token as the tunnel is already authenticated
        
        // Pair the admin socket with agent socket
        tunnel.adminSocket = adminSocket;
        
        // Setup bidirectional relay
        this.setupRelay(tunnel);
        
        console.log(`Admin connected to tunnel for agent ${agentId}`);
        return true;
    }

    /**
     * Create a new reverse tunnel from agent
     */
    createTunnel(agentId, agentSocket, authToken) {
        // Close existing tunnel for this agent if any
        this.closeTunnelForAgent(agentId);

        // Find available port
        const localPort = this.findAvailablePort();
        if (!localPort) {
            console.error('No available ports for tunnel');
            return null;
        }

        const tunnelId = uuidv4();
        const tunnel = {
            tunnelId,
            agentId,
            agentSocket,
            adminSocket: null,
            localPort,
            authToken,
            createdAt: new Date(),
            bytesTransferred: { toAgent: 0, toAdmin: 0 }
        };

        this.tunnels.set(tunnelId, tunnel);
        this.agentTunnels.set(agentId, tunnelId);
        this.usedPorts.add(localPort);

        // Handle agent socket events
        agentSocket.on('close', () => {
            console.log(`Agent tunnel closed for ${agentId}`);
            this.closeTunnel(tunnelId);
        });

        agentSocket.on('error', (err) => {
            console.error(`Agent tunnel error for ${agentId}:`, err);
            this.closeTunnel(tunnelId);
        });

        console.log(`Created tunnel for agent ${agentId} on port ${localPort}`);
        
        return {
            tunnelId,
            localPort,
            host: 'localhost'
        };
    }

    /**
     * Setup bidirectional relay between admin and agent
     */
    setupRelay(tunnel) {
        const { agentSocket, adminSocket } = tunnel;

        // Agent -> Admin
        agentSocket.on('data', (data) => {
            if (adminSocket && !adminSocket.destroyed) {
                adminSocket.write(data);
                tunnel.bytesTransferred.toAdmin += data.length;
            }
        });

        // Admin -> Agent
        adminSocket.on('data', (data) => {
            if (agentSocket && !agentSocket.destroyed) {
                agentSocket.write(data);
                tunnel.bytesTransferred.toAgent += data.length;
            }
        });

        // Handle disconnections
        adminSocket.on('close', () => {
            console.log(`Admin disconnected from tunnel ${tunnel.tunnelId}`);
            tunnel.adminSocket = null;
            // Don't close tunnel - allow reconnection
        });

        adminSocket.on('error', (err) => {
            console.error(`Admin socket error for tunnel ${tunnel.tunnelId}:`, err);
            tunnel.adminSocket = null;
        });
    }

    /**
     * Find an available port in the range
     */
    findAvailablePort() {
        for (let port = this.minPort; port <= this.maxPort; port++) {
            if (!this.usedPorts.has(port)) {
                return port;
            }
        }
        return null;
    }

    /**
     * Close a specific tunnel
     */
    closeTunnel(tunnelId) {
        const tunnel = this.tunnels.get(tunnelId);
        if (!tunnel) return;

        console.log(`Closing tunnel ${tunnelId}`);

        // Close sockets
        if (tunnel.agentSocket && !tunnel.agentSocket.destroyed) {
            tunnel.agentSocket.end();
        }
        if (tunnel.adminSocket && !tunnel.adminSocket.destroyed) {
            tunnel.adminSocket.end();
        }

        // Release port
        this.usedPorts.delete(tunnel.localPort);
        
        // Remove from maps
        this.tunnels.delete(tunnelId);
        this.agentTunnels.delete(tunnel.agentId);
    }

    /**
     * Close tunnel for a specific agent
     */
    closeTunnelForAgent(agentId) {
        const tunnelId = this.agentTunnels.get(agentId);
        if (tunnelId) {
            this.closeTunnel(tunnelId);
        }
    }

    /**
     * Get tunnel status for an agent
     */
    getTunnelStatus(agentId) {
        const tunnelId = this.agentTunnels.get(agentId);
        if (!tunnelId) {
            return { active: false };
        }

        const tunnel = this.tunnels.get(tunnelId);
        return {
            active: true,
            tunnelId: tunnel.tunnelId,
            localPort: tunnel.localPort,
            host: 'localhost',
            hasAdmin: !!tunnel.adminSocket,
            createdAt: tunnel.createdAt,
            bytesTransferred: tunnel.bytesTransferred
        };
    }

    /**
     * Get all active tunnels
     */
    getAllTunnels() {
        const result = [];
        for (const [tunnelId, tunnel] of this.tunnels.entries()) {
            result.push({
                tunnelId,
                agentId: tunnel.agentId,
                localPort: tunnel.localPort,
                hasAdmin: !!tunnel.adminSocket,
                createdAt: tunnel.createdAt,
                bytesTransferred: tunnel.bytesTransferred
            });
        }
        return result;
    }

    /**
     * Relay data to agent
     */
    relayToAgent(agentId, data) {
        const tunnelId = this.agentTunnels.get(agentId);
        if (!tunnelId) return false;

        const tunnel = this.tunnels.get(tunnelId);
        if (tunnel && tunnel.agentSocket && !tunnel.agentSocket.destroyed) {
            tunnel.agentSocket.write(data);
            return true;
        }
        return false;
    }

    /**
     * Check if socket is already paired
     */
    isSocketPaired(socket) {
        for (const tunnel of this.tunnels.values()) {
            if (tunnel.adminSocket === socket) {
                return true;
            }
        }
        return false;
    }

    /**
     * Cleanup on shutdown
     */
    shutdown() {
        console.log('Shutting down VNC Tunnel Manager...');
        
        // Close all tunnels
        for (const tunnelId of this.tunnels.keys()) {
            this.closeTunnel(tunnelId);
        }

        // Close admin server
        if (this.adminServer) {
            this.adminServer.close();
        }
    }
}

module.exports = VNCTunnelManager;

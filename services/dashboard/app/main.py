"""
StrikePackageGPT Dashboard
Web interface for security analysis and LLM-powered penetration testing assistant.
"""
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import httpx
import os
import json

app = FastAPI(
    title="StrikePackageGPT Dashboard",
    description="Web interface for AI-powered security analysis",
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
HACKGPT_API_URL = os.getenv("HACKGPT_API_URL", "http://strikepackage-hackgpt-api:8001")
LLM_ROUTER_URL = os.getenv("LLM_ROUTER_URL", "http://strikepackage-llm-router:8000")
KALI_EXECUTOR_URL = os.getenv("KALI_EXECUTOR_URL", "http://strikepackage-kali-executor:8002")

# Static files
app.mount("/static", StaticFiles(directory="static"), name="static")

# Templates
templates = Jinja2Templates(directory="templates")


class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    provider: str = "ollama"
    model: str = "llama3.2"
    context: Optional[str] = None


class PhaseChatMessage(BaseModel):
    message: str
    phase: str
    provider: str = "ollama"
    model: str = "llama3.2"
    findings: List[Dict[str, Any]] = Field(default_factory=list)


class AttackChainRequest(BaseModel):
    findings: List[Dict[str, Any]]
    provider: str = "ollama"
    model: str = "llama3.2"


class CommandRequest(BaseModel):
    command: str
    timeout: int = Field(default=300, ge=1, le=3600)
    working_dir: str = "/workspace"


class ScanRequest(BaseModel):
    tool: str
    target: str
    scan_type: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class NetworkScanRequest(BaseModel):
    target: str
    scan_type: str = "os"  # ping, quick, os, full


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "dashboard"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse("index.html", {"request": request})


@app.get("/terminal", response_class=HTMLResponse)
async def terminal_page(request: Request):
    """Terminal page"""
    return templates.TemplateResponse("terminal.html", {"request": request})


@app.get("/api/status")
async def get_services_status():
    """Get status of all backend services"""
    services = {}
    
    service_checks = [
        ("llm-router", f"{LLM_ROUTER_URL}/health"),
        ("hackgpt-api", f"{HACKGPT_API_URL}/health"),
        ("kali-executor", f"{KALI_EXECUTOR_URL}/health"),
    ]
    
    async with httpx.AsyncClient() as client:
        for name, url in service_checks:
            try:
                response = await client.get(url, timeout=5.0)
                services[name] = response.status_code == 200
            except:
                services[name] = False
    
    return {"services": services}


@app.get("/api/processes")
async def get_running_processes():
    """Get running security processes in Kali container"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{KALI_EXECUTOR_URL}/processes", timeout=10.0)
            if response.status_code == 200:
                return response.json()
            return {"running_processes": [], "count": 0}
    except:
        return {"running_processes": [], "count": 0}


@app.get("/api/providers")
async def get_providers():
    """Get available LLM providers"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{LLM_ROUTER_URL}/providers", timeout=10.0)
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail="Failed to get providers")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="LLM Router not available")


@app.get("/api/tools")
async def get_tools():
    """Get available security tools"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{HACKGPT_API_URL}/tools", timeout=10.0)
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail="Failed to get tools")
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")


@app.post("/api/chat")
async def chat(message: ChatMessage):
    """Send chat message to HackGPT API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/chat",
                json=message.model_dump(),
                timeout=120.0
            )
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")


@app.post("/api/chat/phase")
async def phase_chat(message: PhaseChatMessage):
    """Send phase-aware chat message to HackGPT API"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/chat/phase",
                json=message.model_dump(),
                timeout=120.0
            )
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")


@app.post("/api/attack-chains")
async def analyze_attack_chains(request: AttackChainRequest):
    """Analyze findings to identify attack chains"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/attack-chains",
                json=request.model_dump(),
                timeout=120.0
            )
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")


@app.post("/api/analyze")
async def analyze(request: Request):
    """Start security analysis"""
    data = await request.json()
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/analyze",
                json=data,
                timeout=30.0
            )
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")


@app.get("/api/task/{task_id}")
async def get_task(task_id: str):
    """Get task status"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{HACKGPT_API_URL}/task/{task_id}", timeout=10.0)
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")


@app.post("/api/suggest-command")
async def suggest_command(message: ChatMessage):
    """Get AI-suggested security commands"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/suggest-command",
                json=message.model_dump(),
                timeout=60.0
            )
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")


# ============== Command Execution ==============

@app.post("/api/execute")
async def execute_command(request: CommandRequest):
    """Execute a command in the Kali container"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/execute",
                json=request.model_dump(),
                timeout=float(request.timeout + 30)
            )
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")
    except httpx.TimeoutException:
        raise HTTPException(status_code=504, detail="Command execution timed out")


# ============== Scan Management ==============

@app.post("/api/scan")
async def start_scan(request: ScanRequest):
    """Start a security scan"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/scan",
                json=request.model_dump(),
                timeout=30.0
            )
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")


@app.get("/api/scan/{scan_id}")
async def get_scan_result(scan_id: str):
    """Get scan results"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{HACKGPT_API_URL}/scan/{scan_id}", timeout=10.0)
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")


@app.get("/api/scans")
async def list_scans():
    """List all scans"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{HACKGPT_API_URL}/scans", timeout=10.0)
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")


@app.post("/api/ai-scan")
async def ai_scan(message: ChatMessage):
    """AI-assisted scanning"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/ai-scan",
                json=message.model_dump(),
                timeout=120.0
            )
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="HackGPT API not available")


# ============== Kali Container Info ==============

@app.get("/api/kali/info")
async def get_kali_info():
    """Get Kali container information"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{KALI_EXECUTOR_URL}/container/info", timeout=10.0)
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Kali executor not available")


@app.get("/api/kali/tools")
async def get_kali_tools():
    """Get installed tools in Kali container"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{KALI_EXECUTOR_URL}/tools", timeout=30.0)
            if response.status_code == 200:
                return response.json()
            raise HTTPException(status_code=response.status_code, detail=response.text)
    except httpx.ConnectError:
        raise HTTPException(status_code=503, detail="Kali executor not available")


# ============== Network Map Endpoints ==============

# In-memory store for network scan results
network_scans = {}
network_hosts = []

@app.post("/api/network/scan")
async def start_network_scan(request: NetworkScanRequest):
    """Start a network range scan for OS detection"""
    import uuid
    scan_id = str(uuid.uuid4())[:8]
    
    # Build nmap command based on scan type
    scan_commands = {
        "ping": f"nmap -sn {request.target} -oX -",
        "quick": f"nmap -T4 -F -O --osscan-limit {request.target} -oX -",
        "os": f"nmap -O -sV --version-light {request.target} -oX -",
        "full": f"nmap -sS -sV -O -p- --version-all {request.target} -oX -"
    }
    
    command = scan_commands.get(request.scan_type, scan_commands["os"])
    
    network_scans[scan_id] = {
        "scan_id": scan_id,
        "target": request.target,
        "scan_type": request.scan_type,
        "status": "running",
        "hosts": [],
        "command": command
    }
    
    # Execute scan asynchronously
    import asyncio
    asyncio.create_task(execute_network_scan(scan_id, command))
    
    return {"scan_id": scan_id, "status": "running"}


async def execute_network_scan(scan_id: str, command: str):
    """Execute network scan and parse results"""
    global network_hosts
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/execute",
                json={"command": command, "timeout": 600},
                timeout=610.0
            )
            
            if response.status_code == 200:
                result = response.json()
                stdout = result.get("stdout", "")
                
                # Parse nmap XML output
                hosts = parse_nmap_xml(stdout)
                
                network_scans[scan_id]["status"] = "completed"
                network_scans[scan_id]["hosts"] = hosts
                
                # Update global host list
                for host in hosts:
                    existing = next((h for h in network_hosts if h["ip"] == host["ip"]), None)
                    if existing:
                        existing.update(host)
                    else:
                        network_hosts.append(host)
            else:
                network_scans[scan_id]["status"] = "failed"
                network_scans[scan_id]["error"] = response.text
                
    except Exception as e:
        network_scans[scan_id]["status"] = "failed"
        network_scans[scan_id]["error"] = str(e)


def parse_nmap_xml(xml_output: str) -> List[Dict[str, Any]]:
    """Parse nmap XML output to extract hosts with OS info"""
    import re
    hosts = []
    
    # Try XML parsing first
    try:
        import xml.etree.ElementTree as ET
        
        # Handle case where XML might have non-XML content before it
        xml_start = xml_output.find('<?xml')
        if xml_start == -1:
            xml_start = xml_output.find('<nmaprun')
        if xml_start != -1:
            xml_output = xml_output[xml_start:]
        
        root = ET.fromstring(xml_output)
        
        for host_elem in root.findall('.//host'):
            if host_elem.find("status").get("state") != "up":
                continue
                
            host = {
                "ip": "",
                "hostname": "",
                "mac": "",
                "vendor": "",
                "os_type": "",
                "os_details": "",
                "ports": []
            }
            
            # Get IP address
            addr = host_elem.find("address[@addrtype='ipv4']")
            if addr is not None:
                host["ip"] = addr.get("addr", "")
            
            # Get MAC address
            mac = host_elem.find("address[@addrtype='mac']")
            if mac is not None:
                host["mac"] = mac.get("addr", "")
                host["vendor"] = mac.get("vendor", "")
            
            # Get hostname
            hostname = host_elem.find(".//hostname")
            if hostname is not None:
                host["hostname"] = hostname.get("name", "")
            
            # Get OS info
            os_elem = host_elem.find(".//osmatch")
            if os_elem is not None:
                os_name = os_elem.get("name", "")
                host["os_details"] = os_name
                host["os_type"] = detect_os_type(os_name)
            else:
                # Try osclass
                osclass = host_elem.find(".//osclass")
                if osclass is not None:
                    osfamily = osclass.get("osfamily", "")
                    host["os_type"] = detect_os_type(osfamily)
                    host["os_details"] = f"{osfamily} {osclass.get('osgen', '')}"
            
            # Get ports
            for port_elem in host_elem.findall(".//port"):
                port_info = {
                    "port": int(port_elem.get("portid", 0)),
                    "protocol": port_elem.get("protocol", "tcp"),
                    "state": port_elem.find("state").get("state", "") if port_elem.find("state") is not None else "",
                    "service": ""
                }
                service = port_elem.find("service")
                if service is not None:
                    port_info["service"] = service.get("name", "")
                    port_info["product"] = service.get("product", "")
                    port_info["version"] = service.get("version", "")
                    
                    # Use service info to help detect OS
                    if not host["os_type"]:
                        product = service.get("product", "").lower()
                        if "microsoft" in product or "windows" in product:
                            host["os_type"] = "Windows"
                        elif "apache" in product or "nginx" in product:
                            if not host["os_type"]:
                                host["os_type"] = "Linux"
                
                if port_info["state"] == "open":
                    host["ports"].append(port_info)
            
            # Infer OS from ports if still unknown
            if not host["os_type"]:
                host["os_type"] = infer_os_from_ports(host["ports"])
            
            if host["ip"]:
                hosts.append(host)
                
    except Exception as e:
        # Fallback: parse text output
        print(f"XML parsing failed: {e}, falling back to text parsing")
        hosts = parse_nmap_text(xml_output)
    
    return hosts


def detect_os_type(os_string: str) -> str:
    """Detect OS type from nmap OS string"""
    if not os_string:
        return ""
    os_lower = os_string.lower()
    
    if "windows" in os_lower:
        return "Windows"
    elif "linux" in os_lower or "ubuntu" in os_lower or "debian" in os_lower or "centos" in os_lower or "red hat" in os_lower:
        return "Linux"
    elif "mac os" in os_lower or "darwin" in os_lower or "apple" in os_lower or "ios" in os_lower:
        return "macOS"
    elif "cisco" in os_lower:
        return "Cisco Router"
    elif "juniper" in os_lower:
        return "Juniper Router"
    elif "fortinet" in os_lower or "fortigate" in os_lower:
        return "Fortinet"
    elif "vmware" in os_lower or "esxi" in os_lower:
        return "VMware Server"
    elif "freebsd" in os_lower:
        return "FreeBSD"
    elif "android" in os_lower:
        return "Android"
    elif "printer" in os_lower or "hp" in os_lower:
        return "Printer"
    elif "switch" in os_lower:
        return "Network Switch"
    elif "router" in os_lower:
        return "Router"
    
    return ""


def infer_os_from_ports(ports: List[Dict]) -> str:
    """Infer OS type from open ports"""
    port_nums = [p["port"] for p in ports]
    services = [p.get("service", "").lower() for p in ports]
    products = [p.get("product", "").lower() for p in ports]
    
    # Windows indicators
    windows_ports = {135, 139, 445, 3389, 5985, 5986}
    if windows_ports & set(port_nums):
        return "Windows"
    if any("microsoft" in p or "windows" in p for p in products):
        return "Windows"
    
    # Linux indicators
    if 22 in port_nums and "ssh" in services:
        return "Linux"
    
    # Network device indicators
    if 161 in port_nums or 162 in port_nums:  # SNMP
        return "Network Device"
    
    # Printer
    if 9100 in port_nums or 631 in port_nums:
        return "Printer"
    
    return ""


def parse_nmap_text(output: str) -> List[Dict[str, Any]]:
    """Parse nmap text output as fallback"""
    import re
    hosts = []
    current_host = None
    
    for line in output.split('\n'):
        # Match host line
        host_match = re.search(r'Nmap scan report for (?:(\S+) \()?(\d+\.\d+\.\d+\.\d+)', line)
        if host_match:
            if current_host and current_host.get("ip"):
                hosts.append(current_host)
            current_host = {
                "ip": host_match.group(2),
                "hostname": host_match.group(1) or "",
                "os_type": "",
                "os_details": "",
                "ports": [],
                "mac": "",
                "vendor": ""
            }
            continue
        
        if current_host:
            # Match MAC
            mac_match = re.search(r'MAC Address: ([0-9A-F:]+) \(([^)]+)\)', line)
            if mac_match:
                current_host["mac"] = mac_match.group(1)
                current_host["vendor"] = mac_match.group(2)
            
            # Match port
            port_match = re.search(r'(\d+)/(tcp|udp)\s+(\w+)\s+(\S+)', line)
            if port_match:
                current_host["ports"].append({
                    "port": int(port_match.group(1)),
                    "protocol": port_match.group(2),
                    "state": port_match.group(3),
                    "service": port_match.group(4)
                })
            
            # Match OS
            os_match = re.search(r'OS details?: (.+)', line)
            if os_match:
                current_host["os_details"] = os_match.group(1)
                current_host["os_type"] = detect_os_type(os_match.group(1))
    
    if current_host and current_host.get("ip"):
        hosts.append(current_host)
    
    return hosts


@app.get("/api/network/scan/{scan_id}")
async def get_network_scan(scan_id: str):
    """Get network scan status and results"""
    if scan_id not in network_scans:
        raise HTTPException(status_code=404, detail="Scan not found")
    return network_scans[scan_id]


@app.get("/api/network/hosts")
async def get_network_hosts():
    """Get all discovered network hosts"""
    return {"hosts": network_hosts}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
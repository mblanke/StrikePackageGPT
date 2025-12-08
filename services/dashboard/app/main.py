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
    model: str = "llama3.1:latest"
    context: Optional[str] = None


class PhaseChatMessage(BaseModel):
    message: str
    phase: str
    provider: str = "ollama"
    model: str = "llama3.1:latest"
    findings: List[Dict[str, Any]] = Field(default_factory=list)


class AttackChainRequest(BaseModel):
    findings: List[Dict[str, Any]]
    provider: str = "ollama"
    model: str = "llama3.1:latest"


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


class TerminalScanRecord(BaseModel):
    tool: str
    target: str
    command: str
    output: str
    source: str = "terminal"


# Local storage for terminal scans
terminal_scans: List[Dict[str, Any]] = []


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
    """List all scans (from hackgpt-api and terminal)"""
    all_scans = list(terminal_scans)  # Start with terminal scans
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{HACKGPT_API_URL}/scans", timeout=10.0)
            if response.status_code == 200:
                api_scans = response.json()
                all_scans.extend(api_scans)
    except httpx.ConnectError:
        pass  # Return terminal scans even if API is down
    return all_scans


@app.post("/api/scans/terminal")
async def record_terminal_scan(scan: TerminalScanRecord):
    """Record a scan run from the terminal"""
    import uuid
    from datetime import datetime
    
    scan_id = str(uuid.uuid4())
    
    # Parse target from command if not provided
    target = scan.target
    if target == "unknown" and scan.command:
        parts = scan.command.split()
        # Try to find target (usually last non-flag argument)
        for part in reversed(parts):
            if not part.startswith('-') and '/' not in part:
                target = part
                break
    
    scan_record = {
        "scan_id": scan_id,
        "tool": scan.tool,
        "target": target,
        "scan_type": "terminal",
        "command": scan.command,
        "status": "completed",
        "started_at": datetime.utcnow().isoformat(),
        "completed_at": datetime.utcnow().isoformat(),
        "result": {
            "stdout": scan.output,
            "stderr": "",
            "exit_code": 0
        },
        "source": scan.source,
        "parsed": None
    }
    
    # Parse the output for common tools
    if scan.tool == "nmap":
        scan_record["parsed"] = parse_nmap_normal(scan.output)
    
    terminal_scans.append(scan_record)
    
    # Keep only last 100 terminal scans
    if len(terminal_scans) > 100:
        terminal_scans.pop(0)
    
    return {"status": "recorded", "scan_id": scan_id}


@app.delete("/api/scans/clear")
async def clear_scans():
    """Clear all scan history"""
    global terminal_scans
    terminal_scans = []  # Clear local terminal scans
    try:
        async with httpx.AsyncClient() as client:
            response = await client.delete(f"{HACKGPT_API_URL}/scans/clear", timeout=10.0)
            if response.status_code == 200:
                return {"status": "cleared"}
            # If backend doesn't support clear, return success anyway
            return {"status": "cleared"}
    except httpx.ConnectError:
        # Return success even if backend is unavailable
        return {"status": "cleared"}


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
    
    # Calculate total hosts in target range
    total_hosts = calculate_target_hosts(request.target)
    
    # Build nmap command based on scan type
    # Use -T4 for faster timing, --stats-every for progress, --min-hostgroup for parallel scanning
    scan_commands = {
        "ping": f"nmap -sn -T4 --min-hostgroup 64 {request.target} -oX - --stats-every 1s",
        "quick": f"nmap -T4 -F --top-ports 100 --min-hostgroup 32 {request.target} -oX - --stats-every 1s",
        "os": f"nmap -T4 -O --osscan-guess --max-os-tries 1 --min-hostgroup 16 {request.target} -oX - --stats-every 2s",
        "full": f"nmap -T4 -sS -sV -O --version-light -p- --min-hostgroup 8 {request.target} -oX - --stats-every 2s"
    }
    
    command = scan_commands.get(request.scan_type, scan_commands["quick"])
    
    network_scans[scan_id] = {
        "scan_id": scan_id,
        "target": request.target,
        "scan_type": request.scan_type,
        "status": "running",
        "hosts": [],
        "command": command,
        "progress": {
            "total": total_hosts,
            "scanned": 0,
            "current_ip": "",
            "hosts_found": 0,
            "percent": 0
        }
    }
    
    # Execute scan asynchronously with progress tracking
    import asyncio
    asyncio.create_task(execute_network_scan_with_progress(scan_id, command, request.target))
    
    return {"scan_id": scan_id, "status": "running", "total_hosts": total_hosts}


def calculate_target_hosts(target: str) -> int:
    """Calculate the number of hosts in a target specification"""
    import ipaddress
    
    # Handle CIDR notation
    if '/' in target:
        try:
            network = ipaddress.ip_network(target, strict=False)
            return network.num_addresses - 2  # Subtract network and broadcast
        except ValueError:
            pass
    
    # Handle range notation (e.g., 192.168.1.1-50)
    if '-' in target:
        try:
            parts = target.rsplit('.', 1)
            if len(parts) == 2:
                range_part = parts[1]
                if '-' in range_part:
                    start, end = range_part.split('-')
                    return int(end) - int(start) + 1
        except (ValueError, IndexError):
            pass
    
    # Single host
    return 1


async def execute_network_scan_with_progress(scan_id: str, command: str, target: str):
    """Execute network scan with progress tracking"""
    global network_hosts
    
    try:
        # Use streaming execution if available, otherwise batch
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/execute",
                json={"command": command, "timeout": 600},
                timeout=610.0
            )
            
            if response.status_code == 200:
                result = response.json()
                stdout = result.get("stdout", "")
                
                # Parse progress from nmap stats output
                progress_info = parse_nmap_progress(stdout)
                if progress_info:
                    network_scans[scan_id]["progress"].update(progress_info)
                
                # Parse nmap XML output for hosts
                hosts = parse_nmap_xml(stdout)
                
                network_scans[scan_id]["status"] = "completed"
                network_scans[scan_id]["hosts"] = hosts
                network_scans[scan_id]["progress"]["scanned"] = network_scans[scan_id]["progress"]["total"]
                network_scans[scan_id]["progress"]["hosts_found"] = len(hosts)
                network_scans[scan_id]["progress"]["percent"] = 100
                
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


def parse_nmap_progress(output: str) -> dict:
    """Parse nmap stats output for progress information"""
    import re
    
    progress = {}
    
    # Look for stats lines like: "Stats: 0:00:45 elapsed; 50 hosts completed (10 up), 5 undergoing..."
    stats_pattern = r'Stats:.*?(\d+)\s+hosts?\s+completed.*?(\d+)\s+up'
    match = re.search(stats_pattern, output, re.IGNORECASE)
    if match:
        progress['scanned'] = int(match.group(1))
        progress['hosts_found'] = int(match.group(2))
    
    # Look for percentage: "About 45.00% done"
    percent_pattern = r'About\s+([\d.]+)%\s+done'
    match = re.search(percent_pattern, output, re.IGNORECASE)
    if match:
        progress['percent'] = float(match.group(1))
    
    # Look for current scan target
    current_pattern = r'Scanning\s+([^\s\[]+)'
    match = re.search(current_pattern, output)
    if match:
        progress['current_ip'] = match.group(1)
    
    return progress


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


class HostData(BaseModel):
    ip: str
    hostname: Optional[str] = None
    mac: Optional[str] = None
    vendor: Optional[str] = None
    os: Optional[str] = None
    os_accuracy: Optional[int] = None
    device_type: Optional[str] = None
    ports: List[Dict[str, Any]] = Field(default_factory=list)
    status: str = "up"
    source: str = "terminal"


class NmapResultData(BaseModel):
    """Accept raw nmap output for parsing"""
    output: str
    source: str = "terminal"


@app.post("/api/network/hosts")
async def add_network_host(host: HostData):
    """Add a single host to the network map (from terminal scans)"""
    global network_hosts
    
    host_dict = host.dict()
    existing = next((h for h in network_hosts if h["ip"] == host.ip), None)
    if existing:
        existing.update(host_dict)
    else:
        network_hosts.append(host_dict)
    
    return {"status": "added", "host": host_dict}


@app.post("/api/network/hosts/bulk")
async def add_network_hosts_bulk(hosts: List[HostData]):
    """Add multiple hosts to the network map"""
    global network_hosts
    
    added = 0
    updated = 0
    for host in hosts:
        host_dict = host.dict()
        existing = next((h for h in network_hosts if h["ip"] == host.ip), None)
        if existing:
            existing.update(host_dict)
            updated += 1
        else:
            network_hosts.append(host_dict)
            added += 1
    
    return {"status": "success", "added": added, "updated": updated, "total": len(network_hosts)}


@app.post("/api/network/nmap-results")
async def add_nmap_results(data: NmapResultData):
    """Parse and add nmap output to network map (supports both XML and grepable formats)"""
    global network_hosts
    
    hosts = parse_nmap_xml(data.output)
    
    # If XML parsing didn't work, try parsing grepable/normal output
    if not hosts:
        hosts = parse_nmap_normal(data.output)
    
    added = 0
    updated = 0
    for host in hosts:
        host["source"] = data.source
        existing = next((h for h in network_hosts if h["ip"] == host["ip"]), None)
        if existing:
            existing.update(host)
            updated += 1
        else:
            network_hosts.append(host)
            added += 1
    
    return {"status": "success", "added": added, "updated": updated, "hosts_parsed": len(hosts), "total": len(network_hosts)}


def parse_nmap_normal(output: str) -> List[Dict[str, Any]]:
    """Parse normal nmap output (non-XML)"""
    import re
    hosts = []
    current_host = None
    
    for line in output.split('\n'):
        # Match "Nmap scan report for hostname (ip)" or "Nmap scan report for ip"
        report_match = re.match(r'Nmap scan report for (?:([^\s(]+)\s+\()?([0-9.]+)\)?', line)
        if report_match:
            if current_host:
                # Determine OS type before saving
                current_host["os_type"] = determine_os_type(
                    current_host.get("os", ""), 
                    current_host.get("ports", []),
                    current_host.get("mac", ""),
                    current_host.get("vendor", "")
                )
                hosts.append(current_host)
            hostname = report_match.group(1) or ""
            ip = report_match.group(2)
            current_host = {
                "ip": ip,
                "hostname": hostname,
                "status": "up",
                "ports": [],
                "os": "",
                "os_type": "",
                "device_type": ""
            }
            continue
        
        # Match "Host is up" 
        if current_host and "Host is up" in line:
            current_host["status"] = "up"
            continue
            
        # Match port lines like "80/tcp   open  http    Apache httpd"
        port_match = re.match(r'(\d+)/(tcp|udp)\s+(\w+)\s+(\S+)(?:\s+(.*))?', line)
        if port_match and current_host:
            port_info = {
                "port": int(port_match.group(1)),
                "protocol": port_match.group(2),
                "state": port_match.group(3),
                "service": port_match.group(4),
                "version": (port_match.group(5) or "").strip()
            }
            current_host["ports"].append(port_info)
            continue
        
        # Match MAC address
        mac_match = re.match(r'MAC Address:\s+([0-9A-F:]+)\s*(?:\((.+)\))?', line, re.IGNORECASE)
        if mac_match and current_host:
            current_host["mac"] = mac_match.group(1)
            current_host["vendor"] = mac_match.group(2) or ""
            continue
        
        # Match OS detection - multiple patterns
        os_match = re.match(r'(?:OS details|Running|OS):\s+(.+)', line)
        if os_match and current_host:
            os_info = os_match.group(1).strip()
            if os_info and not current_host["os"]:
                current_host["os"] = os_info
            elif os_info:
                current_host["os"] += "; " + os_info
            continue
        
        # Match smb-os-discovery OS line
        smb_os_match = re.match(r'\|\s+OS:\s+(.+)', line)
        if smb_os_match and current_host:
            os_info = smb_os_match.group(1).strip()
            if not current_host["os"]:
                current_host["os"] = os_info
            elif os_info not in current_host["os"]:
                current_host["os"] += "; " + os_info
            continue
        
        # Match device type
        device_match = re.match(r'Device type:\s+(.+)', line)
        if device_match and current_host:
            current_host["device_type"] = device_match.group(1)
            continue
    
    # Don't forget the last host
    if current_host:
        current_host["os_type"] = determine_os_type(
            current_host.get("os", ""), 
            current_host.get("ports", []),
            current_host.get("mac", ""),
            current_host.get("vendor", "")
        )
        hosts.append(current_host)
    
    return hosts


def determine_os_type(os_string: str, ports: List[Dict], mac: str = "", vendor: str = "") -> str:
    """Determine OS type from OS string, open ports, MAC address, and vendor"""
    os_lower = os_string.lower()
    vendor_lower = vendor.lower() if vendor else ""
    
    # Check OS string for keywords
    if any(kw in os_lower for kw in ['windows', 'microsoft', 'win32', 'win64']):
        return 'windows'
    if any(kw in os_lower for kw in ['linux', 'ubuntu', 'debian', 'centos', 'fedora', 'redhat', 'kali']):
        return 'linux'
    if any(kw in os_lower for kw in ['mac os', 'macos', 'darwin', 'apple']):
        return 'macos'
    if any(kw in os_lower for kw in ['cisco', 'router', 'switch', 'juniper', 'mikrotik']):
        return 'router'
    if any(kw in os_lower for kw in ['unix', 'freebsd', 'openbsd', 'solaris']):
        return 'linux'  # Close enough for icon purposes
    
    # Check MAC address OUI for manufacturer hints
    mac_vendor = get_mac_vendor_hint(mac, vendor)
    if mac_vendor:
        return mac_vendor
    
    # Infer from ports if OS string didn't help
    port_nums = [p.get('port') for p in ports if p.get('state') == 'open']
    services = [p.get('service', '').lower() for p in ports]
    versions = [p.get('version', '').lower() for p in ports]
    
    # Windows indicators
    windows_ports = {135, 139, 445, 3389, 5985, 5986}
    if windows_ports & set(port_nums):
        # Check if it's actually Samba on Linux
        if any('samba' in v for v in versions):
            return 'linux'
        return 'windows'
    
    # Check service versions for OS hints
    for version in versions:
        if 'windows' in version or 'microsoft' in version:
            return 'windows'
        if 'ubuntu' in version or 'debian' in version or 'linux' in version:
            return 'linux'
    
    # Linux indicators
    if 22 in port_nums and any(s in services for s in ['ssh', 'openssh']):
        return 'linux'
    
    # Router/network device indicators
    if any(s in services for s in ['telnet', 'snmp']) and 80 in port_nums:
        return 'router'
    
    return 'unknown'


def get_mac_vendor_hint(mac: str, vendor: str = "") -> Optional[str]:
    """Get OS type hint from MAC address OUI or vendor string"""
    if not mac and not vendor:
        return None
    
    vendor_lower = vendor.lower() if vendor else ""
    
    # Check vendor string first (nmap often provides this)
    # Apple devices
    if any(kw in vendor_lower for kw in ['apple', 'iphone', 'ipad', 'macbook']):
        return 'macos'
    
    # Network equipment
    if any(kw in vendor_lower for kw in ['cisco', 'juniper', 'netgear', 'linksys', 'tp-link', 'ubiquiti', 'mikrotik', 'd-link', 'asus router', 'arris', 'netcomm']):
        return 'router'
    
    # VM/Hypervisor (likely running any OS, but probably server/linux)
    if any(kw in vendor_lower for kw in ['vmware', 'virtualbox', 'hyper-v', 'microsoft hyper', 'xen', 'qemu', 'kvm']):
        return 'server'
    
    # Raspberry Pi
    if 'raspberry' in vendor_lower:
        return 'linux'
    
    # Known PC/laptop manufacturers (could be Windows or Linux)
    pc_vendors = ['dell', 'hewlett', 'lenovo', 'asus', 'acer', 'msi', 'gigabyte', 'intel', 'realtek', 'broadcom', 'qualcomm', 'mediatek']
    if any(kw in vendor_lower for kw in pc_vendors):
        # Most likely Windows for consumer PCs, but we can't be certain
        # Return None to let other detection methods decide
        return None
    
    # MAC OUI lookup for common prefixes
    if mac:
        mac_upper = mac.upper().replace(':', '').replace('-', '')[:6]
        
        # VMware
        if mac_upper.startswith(('005056', '000C29', '000569')):
            return 'server'
        
        # Microsoft Hyper-V
        if mac_upper.startswith('00155D'):
            return 'server'
        
        # Apple
        if mac_upper.startswith(('A4B197', '3C0754', '009027', 'ACDE48', 'F0B479', '70CD60', '00A040', '000A27', '000393', '001CB3', '001D4F', '001E52', '001F5B', '001FF3', '0021E9', '002241', '002312', '002332', '002436', '00254B', '0025BC', '002608', '00264A', '0026B0', '0026BB')):
            return 'macos'
        
        # Raspberry Pi Foundation
        if mac_upper.startswith(('B827EB', 'DCA632', 'E45F01', 'DC2632')):
            return 'linux'
        
        # Cisco
        if mac_upper.startswith(('001121', '00166D', '001819', '001832', '00186B', '00187D', '0018B9', '0018F3', '00195E', '001A2F', '001A6C', '001A6D', '001B2A', '001BD4', '001C01', '001C0E', '001CE6', '001E13', '001E49', '001EBD', '001F27', '001F6C', '001F9D', '00212F', '002155', '0021A0', '0021BE', '0021D7', '002216', '00223A', '002255', '00226B', '002275', '0023AB', '0023AC', '0023BE', '0023EA', '00240A', '002414', '002436', '00248C', '0024F7', '00250B', '002583', '0025B4', '0026CB', '0027DC', '002841', '0029C2', '002A10', '002A6A', '002CC8', '0030A3', '003080', '0030B6', '00400B', '004096', '005000', '005014', '00501E', '00503E', '005050', '00505F', '005073', '0050A2', '0050D1', '0050E2', '0050F0', '006009', '00602F', '006047', '006052', '00606D', '00607B', '006083', '00609E', '0060B0', '00908F', '0090A6', '009092')):
            return 'router'
    
    return None


@app.delete("/api/network/hosts")
async def clear_network_hosts():
    """Clear all network hosts"""
    global network_hosts
    network_hosts = []
    return {"status": "cleared"}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
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


@app.websocket("/ws/terminal")
async def websocket_terminal(websocket: WebSocket):
    """WebSocket endpoint for streaming terminal output from Kali executor"""
    import websockets
    import asyncio
    
    await websocket.accept()
    print("Client WebSocket connected")
    
    kali_ws = None
    try:
        # Wait for command from client
        data = await websocket.receive_text()
        print(f"Received command request: {data}")
        
        # Connect to kali-executor WebSocket with extended timeouts for long scans
        kali_ws_url = "ws://strikepackage-kali-executor:8002/ws/execute"
        print(f"Connecting to kali-executor at {kali_ws_url}")
        
        # Set ping_interval=30s and ping_timeout=3600s (1 hour) for long-running scans
        kali_ws = await websockets.connect(
            kali_ws_url,
            ping_interval=30,
            ping_timeout=3600,
            close_timeout=10
        )
        print("Connected to kali-executor")
        
        # Send command to kali
        await kali_ws.send(data)
        print("Command sent to kali-executor")
        
        # Stream responses back to client with keepalive
        last_activity = asyncio.get_event_loop().time()
        
        async for message in kali_ws:
            last_activity = asyncio.get_event_loop().time()
            print(f"Received from kali: {message[:100]}...")
            await websocket.send_text(message)
            
            # Check if complete
            try:
                import json
                msg_data = json.loads(message)
                if msg_data.get("type") == "complete":
                    print("Command complete")
                    break
            except:
                pass
                
    except WebSocketDisconnect:
        print("Client disconnected")
    except Exception as e:
        print(f"WebSocket terminal error: {type(e).__name__}: {e}")
        try:
            import json
            await websocket.send_text(json.dumps({"type": "error", "message": str(e)}))
        except:
            pass
    finally:
        if kali_ws:
            await kali_ws.close()


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


@app.delete("/api/scans/clear")
async def clear_scans():
    """Clear all scan history"""
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


class HostDiscoveryRequest(BaseModel):
    """Request to add discovered hosts from terminal commands"""
    hosts: List[Dict[str, Any]]
    source: str = "terminal"  # terminal, scan, import


@app.post("/api/network/hosts/discover")
async def discover_hosts(request: HostDiscoveryRequest):
    """Add hosts discovered from terminal commands (e.g., nmap scans)"""
    global network_hosts
    
    added = 0
    updated = 0
    
    for host in request.hosts:
        if not host.get("ip"):
            continue
            
        # Ensure host has required fields
        host.setdefault("hostname", "")
        host.setdefault("mac", "")
        host.setdefault("vendor", "")
        host.setdefault("os_type", "")
        host.setdefault("os_details", "")
        host.setdefault("ports", [])
        host.setdefault("source", request.source)
        
        # Check if host already exists
        existing = next((h for h in network_hosts if h["ip"] == host["ip"]), None)
        if existing:
            # Update existing host - merge ports
            existing_ports = {(p["port"], p.get("protocol", "tcp")) for p in existing.get("ports", [])}
            for port in host.get("ports", []):
                port_key = (port["port"], port.get("protocol", "tcp"))
                if port_key not in existing_ports:
                    existing["ports"].append(port)
            
            # Update other fields if they have new info
            for field in ["hostname", "mac", "vendor", "os_type", "os_details"]:
                if host.get(field) and not existing.get(field):
                    existing[field] = host[field]
            
            updated += 1
        else:
            network_hosts.append(host)
            added += 1
    
    return {
        "status": "success",
        "added": added,
        "updated": updated,
        "total_hosts": len(network_hosts)
    }


@app.delete("/api/network/hosts")
async def clear_network_hosts():
    """Clear all discovered network hosts"""
    global network_hosts
    count = len(network_hosts)
    network_hosts = []
    return {"status": "success", "cleared": count}


@app.delete("/api/network/hosts/{ip}")
async def delete_network_host(ip: str):
    """Delete a specific network host by IP"""
    global network_hosts
    original_count = len(network_hosts)
    network_hosts = [h for h in network_hosts if h.get("ip") != ip]
    
    if len(network_hosts) == original_count:
        raise HTTPException(status_code=404, detail="Host not found")
    
    return {"status": "success", "deleted": ip}


# ===========================================
# Explain API
# ===========================================
class ExplainRequest(BaseModel):
    type: str  # port, service, tool, finding
    context: Dict[str, Any] = Field(default_factory=dict)


@app.post("/api/explain")
async def explain_context(request: ExplainRequest):
    """Get AI explanation for security concepts"""
    try:
        # Build explanation prompt
        prompt = build_explain_prompt(request.type, request.context)
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/chat",
                json={
                    "message": prompt,
                    "provider": "ollama",
                    "model": "llama3.2",
                    "context": "explain"
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                # Parse the response into structured format
                return parse_explain_response(request.type, request.context, data.get("response", ""))
            
            # Fallback to local explanation
            return get_local_explanation(request.type, request.context)
    except Exception as e:
        return get_local_explanation(request.type, request.context)


def build_explain_prompt(type: str, context: Dict[str, Any]) -> str:
    """Build an explanation prompt for the LLM"""
    prompts = {
        "port": f"Explain port {context.get('port', 'unknown')}/{context.get('protocol', 'tcp')} for penetration testing. Include: what service typically runs on it, common vulnerabilities, and recommended enumeration commands.",
        "service": f"Explain the {context.get('service', 'unknown')} service for penetration testing. Include: purpose, common vulnerabilities, and exploitation techniques.",
        "tool": f"Explain the {context.get('tool', 'unknown')} penetration testing tool. Include: purpose, key features, common usage, and example commands.",
        "finding": f"Explain this security finding: {context.get('title', 'Unknown')}. Context: {context.get('description', 'N/A')}. Include: impact, remediation, and exploitation potential."
    }
    return prompts.get(type, f"Explain: {context}")


def parse_explain_response(type: str, context: Dict[str, Any], response: str) -> Dict[str, Any]:
    """Parse LLM response into structured explanation"""
    return {
        "title": get_explain_title(type, context),
        "description": response,
        "recommendations": extract_recommendations(response),
        "warnings": extract_warnings(type, context),
        "example": extract_example(response)
    }


def get_explain_title(type: str, context: Dict[str, Any]) -> str:
    """Get title for explanation"""
    if type == "port":
        return f"Port {context.get('port', '?')}/{context.get('protocol', 'tcp')}"
    elif type == "service":
        return f"Service: {context.get('service', 'Unknown')}"
    elif type == "tool":
        return f"Tool: {context.get('tool', 'Unknown')}"
    elif type == "finding":
        return context.get('title', 'Security Finding')
    return "Explanation"


def extract_recommendations(response: str) -> List[str]:
    """Extract recommendations from response"""
    recs = []
    lines = response.split('\n')
    in_recs = False
    
    for line in lines:
        line = line.strip()
        if any(word in line.lower() for word in ['recommend', 'suggestion', 'should', 'try']):
            in_recs = True
        if in_recs and line.startswith(('-', '*', '•', '1', '2', '3')):
            recs.append(line.lstrip('-*•123456789. '))
            if len(recs) >= 5:
                break
    
    if not recs:
        return ["Check for known vulnerabilities", "Look for default credentials", "Document findings"]
    return recs


def extract_warnings(type: str, context: Dict[str, Any]) -> List[str]:
    """Extract or generate warnings"""
    warnings = []
    
    if type == "finding" and context.get("severity") in ["critical", "high"]:
        warnings.append("This is a high-severity finding - proceed with caution")
    
    if type == "port":
        port = context.get("port")
        if port in [21, 23, 445]:
            warnings.append("This port is commonly targeted in attacks")
        if port == 3389:
            warnings.append("Check for BlueKeep (CVE-2019-0708) vulnerability")
    
    return warnings


def extract_example(response: str) -> Optional[str]:
    """Extract example commands from response"""
    import re
    
    # Look for code blocks
    code_match = re.search(r'```(?:\w+)?\n(.*?)```', response, re.DOTALL)
    if code_match:
        return code_match.group(1).strip()
    
    # Look for command-like lines
    for line in response.split('\n'):
        line = line.strip()
        if line.startswith(('$', '#', 'nmap', 'nikto', 'gobuster', 'sqlmap')):
            return line.lstrip('$# ')
    
    return None


def get_local_explanation(type: str, context: Dict[str, Any]) -> Dict[str, Any]:
    """Get local fallback explanation"""
    port_info = {
        21: ("FTP - File Transfer Protocol", "Anonymous access, weak credentials, version exploits"),
        22: ("SSH - Secure Shell", "Brute force, key-based exploits, old versions"),
        23: ("Telnet", "Clear text credentials, always a finding"),
        25: ("SMTP", "Open relay, user enumeration"),
        53: ("DNS", "Zone transfers, cache poisoning"),
        80: ("HTTP", "Web vulnerabilities, directory enum"),
        443: ("HTTPS", "Same as HTTP + SSL/TLS issues"),
        445: ("SMB", "EternalBlue, null sessions, share enum"),
        3306: ("MySQL", "Default creds, SQL injection"),
        3389: ("RDP", "BlueKeep, credential attacks"),
        5432: ("PostgreSQL", "Default creds, trust auth"),
        6379: ("Redis", "No auth by default, RCE possible")
    }
    
    if type == "port":
        port = context.get("port")
        info = port_info.get(port, ("Unknown Service", "Fingerprint and enumerate"))
        return {
            "title": f"Port {port}/{context.get('protocol', 'tcp')}",
            "description": f"**{info[0]}**\n\n{info[1]}",
            "recommendations": ["Enumerate service version", "Check for default credentials", "Search for CVEs"],
            "example": f"nmap -sV -sC -p {port} TARGET"
        }
    
    return {
        "title": get_explain_title(type, context),
        "description": "Information not available. Try asking in the chat.",
        "recommendations": ["Use the AI chat for detailed help"]
    }


# ===========================================
# Help API
# ===========================================
class HelpRequest(BaseModel):
    question: str


@app.post("/api/help")
async def help_chat(request: HelpRequest):
    """AI-powered help chat"""
    try:
        # Build help-focused prompt
        prompt = f"""You are a helpful assistant for GooseStrike, an AI-powered penetration testing platform.
Answer this user question concisely and helpfully. Focus on practical guidance.

Question: {request.question}

Provide a clear, helpful response. Use markdown formatting."""

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/chat",
                json={
                    "message": prompt,
                    "provider": "ollama",
                    "model": "llama3.2",
                    "context": "help"
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {"answer": data.get("response", "I can help with that!")}
            
            return {"answer": get_local_help(request.question)}
    except Exception:
        return {"answer": get_local_help(request.question)}


def get_local_help(question: str) -> str:
    """Get local fallback help"""
    q = question.lower()
    
    if "scan" in q and "network" in q:
        return """To scan a network:

1. Go to the **Recon** phase in the sidebar
2. Click **Quick Port Scan** or use the terminal
3. Example command: `nmap -sV 10.10.10.0/24`

You can also ask in the main chat for AI-powered guidance!"""
    
    if "c2" in q or "command and control" in q:
        return """The **C2 tab** provides:

- **Listeners**: Create HTTP/HTTPS/TCP listeners
- **Agents**: Manage connected reverse shells  
- **Payloads**: Generate various reverse shell payloads
- **Tasks**: Queue commands for agents

Click the C2 tab to get started!"""
    
    if "payload" in q or "shell" in q:
        return """To generate payloads:

1. Go to **C2 tab** → **Payloads** panel
2. Set your LHOST (your IP) and LPORT
3. Choose target OS and format
4. Click **Generate Payload**

Quick Payloads section has one-click common shells!"""
    
    return """I'm here to help with GooseStrike!

I can assist with:
- **Network scanning** and enumeration
- **Vulnerability assessment** techniques
- **C2 framework** usage
- **Payload generation**
- **Attack methodology** guidance

What would you like to know?"""


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
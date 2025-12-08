"""
Kali Executor Service
Executes commands in the Kali container via Docker SDK.
"""
from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List
import docker
import asyncio
from concurrent.futures import ThreadPoolExecutor
import os
import uuid
import json
import re
import httpx
import xml.etree.ElementTree as ET
from datetime import datetime
from contextlib import asynccontextmanager

# Allowed command prefixes (security whitelist)
# Expanded to support all Kali tools
ALLOWED_COMMANDS = {
    # Reconnaissance
    "nmap", "masscan", "amass", "theharvester", "whatweb", "dnsrecon", "fierce",
    "dig", "nslookup", "host", "whois", "recon-ng", "maltego", "dmitry", "dnsenum",
    "enum4linux", "nbtscan", "onesixtyone", "smbclient", "snmp-check", "wafw00f",
    # Web testing
    "nikto", "gobuster", "dirb", "sqlmap", "wpscan", "curl", "wget", "burpsuite",
    "zaproxy", "zap-cli", "wfuzz", "ffuf", "dirbuster", "cadaver", "davtest",
    "skipfish", "uniscan", "whatweb", "wapiti", "commix", "joomscan", "droopescan",
    # Wireless
    "aircrack-ng", "airodump-ng", "aireplay-ng", "airmon-ng", "airbase-ng",
    "wifite", "reaver", "bully", "kismet", "fern-wifi-cracker", "wash", "cowpatty",
    "mdk3", "mdk4", "pixiewps", "wifiphisher", "eaphammer", "hostapd-wpe",
    # Password attacks
    "hydra", "medusa", "john", "hashcat", "ncrack", "patator", "ophcrack",
    "crunch", "cewl", "rsmangler", "hashid", "hash-identifier",
    # Network utilities
    "ping", "traceroute", "netcat", "nc", "tcpdump", "wireshark", "tshark",
    "ettercap", "bettercap", "responder", "arpspoof", "dnsspoof", "macchanger",
    "hping3", "arping", "fping", "masscan-web", "unicornscan",
    # Exploitation
    "searchsploit", "msfconsole", "msfvenom", "exploit", "armitage",
    "beef-xss", "set", "setoolkit", "backdoor-factory", "shellnoob",
    "commix", "routersploit", "linux-exploit-suggester",
    # Post-exploitation
    "mimikatz", "powersploit", "empire", "covenant", "crackmapexec", "cme",
    "impacket-smbserver", "impacket-psexec", "evil-winrm", "bloodhound",
    "sharphound", "powershell", "pwsh",
    # Forensics
    "autopsy", "volatility", "sleuthkit", "foremost", "binwalk", "bulk-extractor",
    "scalpel", "dc3dd", "guymager", "chkrootkit", "rkhunter",
    # Reverse engineering
    "ghidra", "radare2", "r2", "gdb", "objdump", "strings", "ltrace", "strace",
    "hexdump", "xxd", "file", "readelf", "checksec", "pwntools",
    # Sniffing
    "dsniff", "tcpflow", "tcpreplay", "tcpick", "ngrep", "p0f", "ssldump",
    # System info
    "ls", "cat", "head", "tail", "grep", "find", "pwd", "whoami", "id",
    "uname", "hostname", "ip", "ifconfig", "netstat", "ss", "route",
    # Analysis tools
    "exiftool", "pdfid", "pdf-parser", "peepdf", "oletools", "olevba",
    # VPN/Tunneling
    "openvpn", "ssh", "sshuttle", "proxychains", "tor", "socat",
    # Misc security tools
    "openssl", "gpg", "steghide", "outguess", "covert", "stegosuite",
    "yersinia", "responder", "chisel", "ligolo", "sliver",
    # Python scripts
    "python", "python3", "python2",
}

# Blocked patterns (dangerous commands)
BLOCKED_PATTERNS = [
    r"rm\s+-rf\s+/",  # Prevent recursive deletion of root
    r"mkfs",  # Prevent formatting
    r"dd\s+if=",  # Prevent disk operations
    r">\s*/dev/",  # Prevent writing to devices
    r"chmod\s+777\s+/",  # Prevent dangerous permission changes
    r"shutdown", r"reboot", r"halt",  # Prevent system control
    r"kill\s+-9\s+-1",  # Prevent killing all processes
]


def validate_command(command: str) -> tuple[bool, str]:
    """Validate command against whitelist and blocked patterns."""
    # Get the base command (first word)
    parts = command.strip().split()
    if not parts:
        return False, "Empty command"
    
    base_cmd = parts[0].split("/")[-1]  # Handle full paths
    
    # Check blocked patterns first
    for pattern in BLOCKED_PATTERNS:
        if re.search(pattern, command, re.IGNORECASE):
            return False, f"Blocked pattern detected: {pattern}"
    
    # Check if command is in whitelist
    if base_cmd not in ALLOWED_COMMANDS:
        return False, f"Command '{base_cmd}' not in allowed list"
    
    return True, "OK"


# Dashboard URL for sending discovered hosts
DASHBOARD_URL = os.getenv("DASHBOARD_URL", "http://dashboard:8080")


def is_nmap_command(command: str) -> bool:
    """Check if command is an nmap scan that might discover hosts."""
    parts = command.strip().split()
    if not parts:
        return False
    base_cmd = parts[0].split("/")[-1]
    return base_cmd == "nmap" or base_cmd == "masscan"


def detect_os_type(os_string: str) -> str:
    """Detect OS type from nmap OS string."""
    if not os_string:
        return ""
    os_lower = os_string.lower()
    
    if "windows" in os_lower:
        return "Windows"
    elif any(x in os_lower for x in ["linux", "ubuntu", "debian", "centos", "red hat"]):
        return "Linux"
    elif any(x in os_lower for x in ["mac os", "darwin", "apple", "ios"]):
        return "macOS"
    elif "cisco" in os_lower:
        return "Cisco Router"
    elif "juniper" in os_lower:
        return "Juniper Router"
    elif any(x in os_lower for x in ["fortinet", "fortigate"]):
        return "Fortinet"
    elif any(x in os_lower for x in ["vmware", "esxi"]):
        return "VMware Server"
    elif "freebsd" in os_lower:
        return "FreeBSD"
    elif "android" in os_lower:
        return "Android"
    elif any(x in os_lower for x in ["printer", "hp"]):
        return "Printer"
    elif "switch" in os_lower:
        return "Network Switch"
    elif "router" in os_lower:
        return "Router"
    return ""


def infer_os_from_ports(ports: List[Dict]) -> str:
    """Infer OS type from open ports.
    
    Uses a scoring system to handle hosts running multiple services
    (e.g., Linux with Samba looks like Windows on port 445).
    """
    port_nums = {p["port"] for p in ports}
    services = {p.get("service", "").lower() for p in ports}
    products = [p.get("product", "").lower() for p in ports]
    
    # Score-based detection to handle mixed indicators
    linux_score = 0
    windows_score = 0
    
    # Strong Linux indicators
    if 22 in port_nums:  # SSH is strongly Linux/Unix
        linux_score += 3
    if any("openssh" in p or "linux" in p for p in products):
        linux_score += 5
    if any("apache" in p or "nginx" in p for p in products):
        linux_score += 2
    
    # Strong Windows indicators  
    if 135 in port_nums:  # MSRPC is Windows-only
        windows_score += 5
    if 3389 in port_nums:  # RDP is Windows
        windows_score += 3
    if 5985 in port_nums or 5986 in port_nums:  # WinRM is Windows-only
        windows_score += 5
    if any("microsoft" in p or "windows" in p for p in products):
        windows_score += 5
    
    # Weak indicators (could be either)
    if 445 in port_nums:  # SMB - could be Samba on Linux or Windows
        windows_score += 1  # Slight Windows bias but not definitive
    if 139 in port_nums:  # NetBIOS - same as above
        windows_score += 1
    
    # Decide based on score
    if linux_score > windows_score:
        return "Linux"
    if windows_score > linux_score:
        return "Windows"
    
    # Network device indicators
    if 161 in port_nums or 162 in port_nums:
        return "Network Device"
    
    # Printer
    if 9100 in port_nums or 631 in port_nums:
        return "Printer"
    
    return ""


def parse_nmap_output(stdout: str) -> List[Dict[str, Any]]:
    """Parse nmap output (XML or text) and extract discovered hosts."""
    hosts = []
    
    # Try XML parsing first (if -oX - was used or combined with other options)
    if '<?xml' in stdout or '<nmaprun' in stdout:
        try:
            xml_start = stdout.find('<?xml')
            if xml_start == -1:
                xml_start = stdout.find('<nmaprun')
            if xml_start != -1:
                xml_output = stdout[xml_start:]
                hosts = parse_nmap_xml(xml_output)
                if hosts:
                    return hosts
        except Exception as e:
            print(f"XML parsing failed: {e}")
    
    # Fallback to text parsing
    hosts = parse_nmap_text(stdout)
    return hosts


def parse_nmap_xml(xml_output: str) -> List[Dict[str, Any]]:
    """Parse nmap XML output to extract hosts."""
    hosts = []
    try:
        root = ET.fromstring(xml_output)
        
        for host_elem in root.findall('.//host'):
            status = host_elem.find("status")
            if status is None or status.get("state") != "up":
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
            
            # Get ports
            for port_elem in host_elem.findall(".//port"):
                state_elem = port_elem.find("state")
                port_info = {
                    "port": int(port_elem.get("portid", 0)),
                    "protocol": port_elem.get("protocol", "tcp"),
                    "state": state_elem.get("state", "") if state_elem is not None else "",
                    "service": ""
                }
                service = port_elem.find("service")
                if service is not None:
                    port_info["service"] = service.get("name", "")
                    port_info["product"] = service.get("product", "")
                    port_info["version"] = service.get("version", "")
                
                if port_info["state"] == "open":
                    host["ports"].append(port_info)
            
            # Infer OS from ports if still unknown
            if not host["os_type"] and host["ports"]:
                host["os_type"] = infer_os_from_ports(host["ports"])
            
            # Only include hosts that have either:
            # 1. At least one open port (proves real service)
            # 2. A valid MAC address (proves real local device)
            # This filters out false positives from router proxy ARP
            if host["ip"] and (host["ports"] or host["mac"]):
                hosts.append(host)
                
    except ET.ParseError as e:
        print(f"XML parse error: {e}")
    
    return hosts


def parse_nmap_text(output: str) -> List[Dict[str, Any]]:
    """Parse nmap text output as fallback.
    
    Only returns hosts that have at least one OPEN port.
    Hosts that respond to ping/ARP but have no open ports are filtered out.
    """
    hosts = []
    current_host = None
    
    def save_host_if_has_open_ports(host):
        """Only save host if it has at least one open port."""
        if host and host.get("ip") and host.get("ports"):
            # Infer OS before saving
            if not host["os_type"]:
                host["os_type"] = infer_os_from_ports(host["ports"])
            hosts.append(host)
    
    for line in output.split('\n'):
        # Match host line: "Nmap scan report for hostname (IP)" or "Nmap scan report for IP"
        host_match = re.search(r'Nmap scan report for (?:(\S+) \()?(\d+\.\d+\.\d+\.\d+)', line)
        if host_match:
            # Save previous host only if it has open ports
            save_host_if_has_open_ports(current_host)
            
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
            # Match MAC: "MAC Address: XX:XX:XX:XX:XX:XX (Vendor Name)"
            mac_match = re.search(r'MAC Address: ([0-9A-Fa-f:]+)(?: \(([^)]+)\))?', line)
            if mac_match:
                current_host["mac"] = mac_match.group(1)
                current_host["vendor"] = mac_match.group(2) or ""
            
            # Match port: "80/tcp   open  http    Apache httpd"
            port_match = re.search(r'(\d+)/(tcp|udp)\s+(\w+)\s+(\S+)(?:\s+(.*))?', line)
            if port_match and port_match.group(3) == "open":
                port_info = {
                    "port": int(port_match.group(1)),
                    "protocol": port_match.group(2),
                    "state": "open",
                    "service": port_match.group(4),
                    "product": port_match.group(5) or ""
                }
                current_host["ports"].append(port_info)
            
            # Match OS: "OS details: Linux 4.15 - 5.6" or "Running: Linux"
            os_match = re.search(r'(?:OS details?|Running):\s*(.+)', line)
            if os_match:
                current_host["os_details"] = os_match.group(1)
                current_host["os_type"] = detect_os_type(os_match.group(1))
            
            # Match "Service Info: OS: Linux" style
            service_os_match = re.search(r'Service Info:.*OS:\s*([^;,]+)', line)
            if service_os_match and not current_host["os_type"]:
                current_host["os_type"] = detect_os_type(service_os_match.group(1))
            
            # Match "Aggressive OS guesses: Linux 5.4 (98%)" - take first high confidence
            aggressive_match = re.search(r'Aggressive OS guesses:\s*([^(]+)\s*\((\d+)%\)', line)
            if aggressive_match and not current_host["os_details"]:
                confidence = int(aggressive_match.group(2))
                if confidence >= 85:
                    current_host["os_details"] = aggressive_match.group(1).strip()
                    current_host["os_type"] = detect_os_type(aggressive_match.group(1))
    
    # Don't forget the last host - only if it has open ports
    save_host_if_has_open_ports(current_host)
    
    return hosts


async def send_hosts_to_dashboard(hosts: List[Dict[str, Any]]):
    """Send discovered hosts to the dashboard for network map update."""
    if not hosts:
        return
    
    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            response = await client.post(
                f"{DASHBOARD_URL}/api/network/hosts/discover",
                json={"hosts": hosts, "source": "terminal"}
            )
            if response.status_code == 200:
                result = response.json()
                print(f"Sent {len(hosts)} hosts to dashboard: added={result.get('added')}, updated={result.get('updated')}")
            else:
                print(f"Failed to send hosts to dashboard: {response.status_code}")
    except Exception as e:
        print(f"Error sending hosts to dashboard: {e}")


# Docker client
docker_client = None
kali_container = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for the FastAPI app."""
    global docker_client, kali_container
    
    try:
        docker_client = docker.from_env()
        kali_container = docker_client.containers.get(
            os.getenv("KALI_CONTAINER_NAME", "strikepackage-kali")
        )
        print(f"Connected to Kali container: {kali_container.name}")
    except docker.errors.NotFound:
        print("Warning: Kali container not found. Command execution will fail.")
    except docker.errors.DockerException as e:
        print(f"Warning: Docker not available: {e}")
    
    yield
    
    if docker_client:
        docker_client.close()


app = FastAPI(
    title="Kali Executor",
    description="Execute commands in the Kali container",
    version="0.1.0",
    lifespan=lifespan
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Store running commands
running_commands: Dict[str, Dict[str, Any]] = {}


class CommandRequest(BaseModel):
    command: str
    timeout: int = Field(default=300, ge=1, le=3600)
    working_dir: str = "/workspace"
    stream: bool = False


class CommandResult(BaseModel):
    command_id: str
    command: str
    status: str
    exit_code: Optional[int] = None
    stdout: str = ""
    stderr: str = ""
    started_at: datetime
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[float] = None


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    kali_status = "disconnected"
    
    if kali_container:
        try:
            kali_container.reload()
            kali_status = kali_container.status
        except:
            kali_status = "error"
    
    return {
        "status": "healthy",
        "service": "kali-executor",
        "kali_container": kali_status
    }


@app.get("/processes")
async def get_running_processes():
    """Get list of running security tool processes in Kali container."""
    global kali_container
    
    if not kali_container:
        raise HTTPException(status_code=503, detail="Kali container not available")
    
    try:
        # Get process list
        loop = asyncio.get_event_loop()
        exit_code, output = await loop.run_in_executor(
            executor,
            lambda: kali_container.exec_run(
                cmd=["ps", "aux", "--sort=-start_time"],
                demux=True
            )
        )
        
        stdout = output[0].decode('utf-8', errors='replace') if output[0] else ""
        
        # Parse processes and filter for security tools
        security_tools = ["nmap", "nikto", "gobuster", "sqlmap", "hydra", "masscan", 
                          "amass", "theharvester", "dirb", "wpscan", "searchsploit", "msfconsole"]
        
        processes = []
        for line in stdout.split('\n')[1:]:  # Skip header
            parts = line.split(None, 10)
            if len(parts) >= 11:
                cmd = parts[10]
                pid = parts[1]
                cpu = parts[2]
                mem = parts[3]
                time_running = parts[9]
                
                # Check if it's a security tool
                is_security_tool = any(tool in cmd.lower() for tool in security_tools)
                
                if is_security_tool:
                    processes.append({
                        "pid": pid,
                        "cpu": cpu,
                        "mem": mem,
                        "time": time_running,
                        "command": cmd[:200]  # Truncate long commands
                    })
        
        return {
            "running_processes": processes,
            "count": len(processes)
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


# Thread pool for blocking Docker operations
executor = ThreadPoolExecutor(max_workers=10)

def _run_command_sync(container, command, working_dir):
    """Synchronous command execution for thread pool."""
    full_command = f"cd {working_dir} && {command}"
    return container.exec_run(
        cmd=["bash", "-c", full_command],
        demux=True,
        workdir=working_dir
    )

@app.post("/execute", response_model=CommandResult)
async def execute_command(request: CommandRequest):
    """Execute a command in the Kali container."""
    global kali_container
    
    if not kali_container:
        raise HTTPException(status_code=503, detail="Kali container not available")
    
    # Validate command against whitelist
    is_valid, message = validate_command(request.command)
    if not is_valid:
        raise HTTPException(status_code=403, detail=f"Command blocked: {message}")
    
    command_id = str(uuid.uuid4())
    started_at = datetime.utcnow()
    
    try:
        # Refresh container state
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(executor, kali_container.reload)
        
        if kali_container.status != "running":
            raise HTTPException(status_code=503, detail="Kali container is not running")
        
        # Execute command in thread pool to avoid blocking
        exit_code, output = await loop.run_in_executor(
            executor,
            _run_command_sync,
            kali_container,
            request.command,
            request.working_dir
        )
        
        completed_at = datetime.utcnow()
        duration = (completed_at - started_at).total_seconds()
        
        stdout = output[0].decode('utf-8', errors='replace') if output[0] else ""
        stderr = output[1].decode('utf-8', errors='replace') if output[1] else ""
        
        # Parse nmap output and send hosts to dashboard for network map
        if is_nmap_command(request.command) and stdout:
            try:
                hosts = parse_nmap_output(stdout)
                if hosts:
                    asyncio.create_task(send_hosts_to_dashboard(hosts))
            except Exception as e:
                print(f"Error parsing nmap output: {e}")
        
        return CommandResult(
            command_id=command_id,
            command=request.command,
            status="completed",
            exit_code=exit_code,
            stdout=stdout,
            stderr=stderr,
            started_at=started_at,
            completed_at=completed_at,
            duration_seconds=duration
        )
        
    except docker.errors.APIError as e:
        raise HTTPException(status_code=500, detail=f"Docker error: {str(e)}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Execution error: {str(e)}")


@app.post("/execute/async")
async def execute_command_async(request: CommandRequest):
    """Execute a command asynchronously and return immediately."""
    global kali_container
    
    if not kali_container:
        raise HTTPException(status_code=503, detail="Kali container not available")
    
    # Validate command against whitelist
    is_valid, message = validate_command(request.command)
    if not is_valid:
        raise HTTPException(status_code=403, detail=f"Command blocked: {message}")
    
    command_id = str(uuid.uuid4())
    started_at = datetime.utcnow()
    
    running_commands[command_id] = {
        "command": request.command,
        "status": "running",
        "started_at": started_at,
        "stdout": "",
        "stderr": ""
    }
    
    # Start background execution
    asyncio.create_task(_run_command_background(
        command_id, request.command, request.working_dir, request.timeout
    ))
    
    return {"command_id": command_id, "status": "running"}


async def _run_command_background(command_id: str, command: str, working_dir: str, timeout: int):
    """Run command in background."""
    global kali_container
    
    try:
        kali_container.reload()
        
        full_command = f"cd {working_dir} && timeout {timeout} {command}"
        
        exit_code, output = kali_container.exec_run(
            cmd=["bash", "-c", full_command],
            demux=True,
            workdir=working_dir
        )
        
        running_commands[command_id].update({
            "status": "completed",
            "exit_code": exit_code,
            "stdout": output[0].decode('utf-8', errors='replace') if output[0] else "",
            "stderr": output[1].decode('utf-8', errors='replace') if output[1] else "",
            "completed_at": datetime.utcnow()
        })
        
    except Exception as e:
        running_commands[command_id].update({
            "status": "failed",
            "error": str(e),
            "completed_at": datetime.utcnow()
        })


@app.get("/execute/{command_id}")
async def get_command_status(command_id: str):
    """Get status of an async command."""
    if command_id not in running_commands:
        raise HTTPException(status_code=404, detail="Command not found")
    
    return running_commands[command_id]


@app.websocket("/ws/execute")
async def websocket_execute(websocket: WebSocket):
    """WebSocket endpoint for streaming command output."""
    global kali_container
    
    await websocket.accept()
    
    try:
        while True:
            data = await websocket.receive_json()
            command = data.get("command")
            working_dir = data.get("working_dir", "/workspace")
            
            if not command:
                await websocket.send_json({"error": "No command provided"})
                continue
            
            # Validate command against whitelist
            is_valid, message = validate_command(command)
            if not is_valid:
                await websocket.send_json({"error": f"Command blocked: {message}"})
                continue
            
            if not kali_container:
                await websocket.send_json({"error": "Kali container not available"})
                continue
            
            try:
                kali_container.reload()
                
                # Use exec_run with stream=True for real-time output
                exec_result = kali_container.exec_run(
                    cmd=["bash", "-c", f"cd {working_dir} && {command}"],
                    stream=True,
                    demux=True,
                    workdir=working_dir
                )
                
                # Collect output for nmap parsing
                full_stdout = []
                is_nmap = is_nmap_command(command)
                
                # Stream output with keepalive for long-running commands
                last_output_time = asyncio.get_event_loop().time()
                output_queue = asyncio.Queue()
                stream_complete = asyncio.Event()
                
                # Synchronous function to read from Docker stream (runs in thread)
                def read_docker_output_sync(queue: asyncio.Queue, loop, complete_event):
                    try:
                        for stdout, stderr in exec_result.output:
                            if stdout:
                                asyncio.run_coroutine_threadsafe(
                                    queue.put(("stdout", stdout.decode('utf-8', errors='replace'))),
                                    loop
                                )
                            if stderr:
                                asyncio.run_coroutine_threadsafe(
                                    queue.put(("stderr", stderr.decode('utf-8', errors='replace'))),
                                    loop
                                )
                    except Exception as e:
                        asyncio.run_coroutine_threadsafe(
                            queue.put(("error", str(e))),
                            loop
                        )
                    finally:
                        loop.call_soon_threadsafe(complete_event.set)
                
                # Start reading in background thread
                loop = asyncio.get_event_loop()
                read_future = loop.run_in_executor(
                    executor, 
                    read_docker_output_sync, 
                    output_queue, 
                    loop, 
                    stream_complete
                )
                
                # Send output and keepalives
                keepalive_interval = 25  # seconds
                while not stream_complete.is_set() or not output_queue.empty():
                    try:
                        # Wait for output with timeout for keepalive
                        try:
                            msg_type, msg_data = await asyncio.wait_for(
                                output_queue.get(), 
                                timeout=keepalive_interval
                            )
                            last_output_time = asyncio.get_event_loop().time()
                            
                            if msg_type == "stdout":
                                if is_nmap:
                                    full_stdout.append(msg_data)
                                await websocket.send_json({"type": "stdout", "data": msg_data})
                            elif msg_type == "stderr":
                                await websocket.send_json({"type": "stderr", "data": msg_data})
                            elif msg_type == "error":
                                await websocket.send_json({"type": "error", "message": msg_data})
                                
                        except asyncio.TimeoutError:
                            # No output for a while, send keepalive
                            elapsed = asyncio.get_event_loop().time() - last_output_time
                            await websocket.send_json({
                                "type": "keepalive", 
                                "elapsed": int(elapsed),
                                "message": f"Scan in progress ({int(elapsed)}s)..."
                            })
                    except Exception as e:
                        print(f"Error in output loop: {e}")
                        break
                
                # Wait for read thread to complete
                await read_future
                
                # Parse nmap output and send hosts to dashboard
                if is_nmap and full_stdout:
                    try:
                        combined_output = "".join(full_stdout)
                        hosts = parse_nmap_output(combined_output)
                        if hosts:
                            asyncio.create_task(send_hosts_to_dashboard(hosts))
                    except Exception as e:
                        print(f"Error parsing nmap output: {e}")
                
                await websocket.send_json({
                    "type": "complete",
                    "exit_code": exec_result.exit_code if hasattr(exec_result, 'exit_code') else 0
                })
                
            except Exception as e:
                await websocket.send_json({"type": "error", "message": str(e)})
                
    except WebSocketDisconnect:
        pass


@app.get("/container/info")
async def get_container_info():
    """Get Kali container information."""
    global kali_container
    
    if not kali_container:
        raise HTTPException(status_code=503, detail="Kali container not available")
    
    try:
        kali_container.reload()
        
        return {
            "id": kali_container.short_id,
            "name": kali_container.name,
            "status": kali_container.status,
            "image": kali_container.image.tags[0] if kali_container.image.tags else "unknown",
            "created": kali_container.attrs.get("Created"),
            "network": list(kali_container.attrs.get("NetworkSettings", {}).get("Networks", {}).keys())
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/tools")
async def list_installed_tools():
    """List security tools installed in Kali container."""
    global kali_container
    
    if not kali_container:
        raise HTTPException(status_code=503, detail="Kali container not available")
    
    tools_to_check = [
        "nmap", "masscan", "nikto", "sqlmap", "gobuster", "dirb",
        "hydra", "amass", "theharvester", "whatweb", "wpscan",
        "searchsploit", "msfconsole", "netcat", "curl", "wget"
    ]
    
    installed = []
    
    for tool in tools_to_check:
        try:
            exit_code, _ = kali_container.exec_run(
                cmd=["which", tool],
                demux=True
            )
            if exit_code == 0:
                installed.append(tool)
        except:
            pass
    
    return {"installed_tools": installed}


@app.get("/captured_commands")
async def get_captured_commands(limit: int = 50, since: Optional[str] = None):
    """
    Get commands that were captured from interactive shell sessions in the Kali container.
    These are commands run directly by users via docker exec or SSH.
    """
    global kali_container
    
    if not kali_container:
        raise HTTPException(status_code=503, detail="Kali container not available")
    
    try:
        kali_container.reload()
        
        # Read command history from the shared volume
        cmd = ["bash", "-c", "cd /workspace/.command_history && ls -t *.json 2>/dev/null | head -n {}".format(limit)]
        exit_code, output = kali_container.exec_run(cmd=cmd, demux=True)
        
        if exit_code != 0 or not output[0]:
            return {"commands": [], "count": 0}
        
        # Get list of log files
        log_files = output[0].decode('utf-8', errors='replace').strip().split('\n')
        log_files = [f for f in log_files if f.strip()]
        
        commands = []
        for log_file in log_files:
            try:
                # Read each JSON log file
                read_cmd = ["cat", f"/workspace/.command_history/{log_file}"]
                exit_code, output = kali_container.exec_run(cmd=read_cmd, demux=True)
                
                if exit_code == 0 and output[0]:
                    cmd_data = json.loads(output[0].decode('utf-8', errors='replace'))
                    
                    # Filter by timestamp if requested
                    if since:
                        cmd_timestamp = cmd_data.get("timestamp", "")
                        if cmd_timestamp < since:
                            continue
                    
                    commands.append(cmd_data)
                    
            except json.JSONDecodeError:
                continue
            except Exception:
                continue
        
        return {
            "commands": commands,
            "count": len(commands),
            "source": "interactive_shell_capture"
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error reading captured commands: {str(e)}")


@app.delete("/captured_commands/clear")
async def clear_captured_commands():
    """Clear all captured command history."""
    global kali_container
    
    if not kali_container:
        raise HTTPException(status_code=503, detail="Kali container not available")
    
    try:
        kali_container.reload()
        
        # Clear the command history directory
        cmd = ["bash", "-c", "rm -f /workspace/.command_history/*.json"]
        exit_code, _ = kali_container.exec_run(cmd=cmd)
        
        if exit_code == 0:
            return {"status": "cleared", "message": "All captured command history cleared"}
        else:
            raise HTTPException(status_code=500, detail="Failed to clear history")
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/allowed-commands")
async def get_allowed_commands():
    """Get list of allowed commands for security validation."""
    return {
        "allowed_commands": sorted(list(ALLOWED_COMMANDS)),
        "blocked_patterns": BLOCKED_PATTERNS
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8002)

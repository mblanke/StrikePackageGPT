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
                
                # Stream output
                for stdout, stderr in exec_result.output:
                    if stdout:
                        await websocket.send_json({
                            "type": "stdout",
                            "data": stdout.decode('utf-8', errors='replace')
                        })
                    if stderr:
                        await websocket.send_json({
                            "type": "stderr", 
                            "data": stderr.decode('utf-8', errors='replace')
                        })
                
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

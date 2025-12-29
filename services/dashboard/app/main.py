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
import uuid
from datetime import datetime
from pathlib import Path

# Project data storage
PROJECTS_DIR = Path("/app/data/projects")
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)

# In-memory project cache (loaded from disk)
projects_db: Dict[str, Dict] = {}
current_project_id: Optional[str] = None


def load_projects():
    """Load all projects from disk on startup"""
    global projects_db
    for project_file in PROJECTS_DIR.glob("*.json"):
        try:
            with open(project_file, 'r') as f:
                project = json.load(f)
                projects_db[project['id']] = project
        except Exception as e:
            print(f"Failed to load project {project_file}: {e}")


def save_project(project_id: str):
    """Save a project to disk"""
    if project_id in projects_db:
        project_file = PROJECTS_DIR / f"{project_id}.json"
        with open(project_file, 'w') as f:
            json.dump(projects_db[project_id], f, indent=2, default=str)


def get_current_project() -> Optional[Dict]:
    """Get the current active project"""
    if current_project_id and current_project_id in projects_db:
        return projects_db[current_project_id]
    return None


def add_to_project(category: str, data: Dict):
    """Add data to the current project"""
    project = get_current_project()
    if project:
        if category not in project:
            project[category] = []
        data['timestamp'] = datetime.now().isoformat()
        project[category].append(data)
        project['updated_at'] = datetime.now().isoformat()
        save_project(project['id'])


# Load existing projects on startup
load_projects()

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


# Project Management Models
class ProjectCreate(BaseModel):
    name: str
    description: Optional[str] = ""
    target_network: Optional[str] = None
    scope: Optional[List[str]] = Field(default_factory=list)
    
    
class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    target_network: Optional[str] = None
    scope: Optional[List[str]] = None
    notes: Optional[str] = None


class CredentialCreate(BaseModel):
    username: str
    password: Optional[str] = None
    hash: Optional[str] = None
    hash_type: Optional[str] = None
    domain: Optional[str] = None
    host: Optional[str] = None
    service: Optional[str] = None
    source: Optional[str] = None
    valid: Optional[bool] = None
    notes: Optional[str] = None


class FindingCreate(BaseModel):
    title: str
    severity: str = "info"  # critical, high, medium, low, info
    host: Optional[str] = None
    port: Optional[int] = None
    service: Optional[str] = None
    description: Optional[str] = None
    evidence: Optional[str] = None
    recommendation: Optional[str] = None
    cve: Optional[str] = None
    cvss: Optional[float] = None
    tool: Optional[str] = None


class NoteCreate(BaseModel):
    title: str
    content: str
    category: Optional[str] = "general"  # general, recon, exploitation, post-exploit, loot
    host: Optional[str] = None


# ============= PROJECT MANAGEMENT ENDPOINTS =============

@app.get("/api/projects")
async def list_projects():
    """List all projects"""
    return {
        "projects": list(projects_db.values()),
        "current_project_id": current_project_id
    }


@app.post("/api/projects")
async def create_project(project: ProjectCreate):
    """Create a new project"""
    global current_project_id
    
    project_id = str(uuid.uuid4())[:8]
    now = datetime.now().isoformat()
    
    new_project = {
        "id": project_id,
        "name": project.name,
        "description": project.description,
        "target_network": project.target_network,
        "scope": project.scope,
        "created_at": now,
        "updated_at": now,
        "hosts": [],
        "credentials": [],
        "findings": [],
        "scans": [],
        "notes": [],
        "sessions": [],
        "evidence": [],
        "attack_chains": []
    }
    
    projects_db[project_id] = new_project
    save_project(project_id)
    
    # Auto-select new project
    current_project_id = project_id
    
    return {"status": "success", "project": new_project}


@app.get("/api/projects/{project_id}")
async def get_project(project_id: str):
    """Get a specific project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    return projects_db[project_id]


@app.put("/api/projects/{project_id}")
async def update_project(project_id: str, update: ProjectUpdate):
    """Update a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects_db[project_id]
    update_data = update.dict(exclude_unset=True)
    
    for key, value in update_data.items():
        if value is not None:
            project[key] = value
    
    project['updated_at'] = datetime.now().isoformat()
    save_project(project_id)
    
    return {"status": "success", "project": project}


@app.delete("/api/projects/{project_id}")
async def delete_project(project_id: str):
    """Delete a project"""
    global current_project_id
    
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    # Remove from memory
    del projects_db[project_id]
    
    # Remove from disk
    project_file = PROJECTS_DIR / f"{project_id}.json"
    if project_file.exists():
        project_file.unlink()
    
    # Update current project if needed
    if current_project_id == project_id:
        current_project_id = next(iter(projects_db), None)
    
    return {"status": "success", "message": "Project deleted"}


@app.post("/api/projects/{project_id}/select")
async def select_project(project_id: str):
    """Select active project"""
    global current_project_id
    
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    current_project_id = project_id
    return {"status": "success", "current_project_id": current_project_id}


@app.get("/api/projects/current")
async def get_current_project_api():
    """Get the currently selected project"""
    if not current_project_id or current_project_id not in projects_db:
        return {"project": None}
    return {"project": projects_db[current_project_id]}


# Project Data Endpoints
@app.post("/api/projects/{project_id}/credentials")
async def add_credential(project_id: str, cred: CredentialCreate):
    """Add a credential to a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects_db[project_id]
    cred_data = cred.dict()
    cred_data['id'] = str(uuid.uuid4())[:8]
    cred_data['created_at'] = datetime.now().isoformat()
    
    project['credentials'].append(cred_data)
    project['updated_at'] = datetime.now().isoformat()
    save_project(project_id)
    
    return {"status": "success", "credential": cred_data}


@app.get("/api/projects/{project_id}/credentials")
async def list_credentials(project_id: str):
    """List all credentials in a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"credentials": projects_db[project_id].get('credentials', [])}


@app.delete("/api/projects/{project_id}/credentials/{cred_id}")
async def delete_credential(project_id: str, cred_id: str):
    """Delete a credential from a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects_db[project_id]
    project['credentials'] = [c for c in project.get('credentials', []) if c.get('id') != cred_id]
    project['updated_at'] = datetime.now().isoformat()
    save_project(project_id)
    
    return {"status": "success"}


@app.post("/api/projects/{project_id}/findings")
async def add_finding(project_id: str, finding: FindingCreate):
    """Add a finding to a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects_db[project_id]
    finding_data = finding.dict()
    finding_data['id'] = str(uuid.uuid4())[:8]
    finding_data['created_at'] = datetime.now().isoformat()
    
    project['findings'].append(finding_data)
    project['updated_at'] = datetime.now().isoformat()
    save_project(project_id)
    
    return {"status": "success", "finding": finding_data}


@app.get("/api/projects/{project_id}/findings")
async def list_findings(project_id: str):
    """List all findings in a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"findings": projects_db[project_id].get('findings', [])}


@app.delete("/api/projects/{project_id}/findings/{finding_id}")
async def delete_finding(project_id: str, finding_id: str):
    """Delete a finding from a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects_db[project_id]
    project['findings'] = [f for f in project.get('findings', []) if f.get('id') != finding_id]
    project['updated_at'] = datetime.now().isoformat()
    save_project(project_id)
    
    return {"status": "success"}


@app.post("/api/projects/{project_id}/notes")
async def add_note(project_id: str, note: NoteCreate):
    """Add a note to a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects_db[project_id]
    note_data = note.dict()
    note_data['id'] = str(uuid.uuid4())[:8]
    note_data['created_at'] = datetime.now().isoformat()
    
    project['notes'].append(note_data)
    project['updated_at'] = datetime.now().isoformat()
    save_project(project_id)
    
    return {"status": "success", "note": note_data}


@app.get("/api/projects/{project_id}/notes")
async def list_notes(project_id: str):
    """List all notes in a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    return {"notes": projects_db[project_id].get('notes', [])}


@app.delete("/api/projects/{project_id}/notes/{note_id}")
async def delete_note(project_id: str, note_id: str):
    """Delete a note from a project"""
    if project_id not in projects_db:
        raise HTTPException(status_code=404, detail="Project not found")
    
    project = projects_db[project_id]
    project['notes'] = [n for n in project.get('notes', []) if n.get('id') != note_id]
    project['updated_at'] = datetime.now().isoformat()
    save_project(project_id)
    
    return {"status": "success"}


# ============= END PROJECT MANAGEMENT =============


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "dashboard"}


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Main dashboard page"""
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "HACKGPT_API_URL": HACKGPT_API_URL,
            "LLM_ROUTER_URL": LLM_ROUTER_URL,
            "KALI_EXECUTOR_URL": KALI_EXECUTOR_URL,
        },
    )


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

@app.get("/api/stream/processes")
async def stream_running_processes():
    """Server-Sent Events stream proxy that emits running processes periodically."""

    async def event_generator():
        while True:
            try:
                async with httpx.AsyncClient() as client:
                    response = await client.get(f"{KALI_EXECUTOR_URL}/processes", timeout=10.0)
                    data = response.json() if response.status_code == 200 else {"running_processes": [], "count": 0}
                yield f"data: {json.dumps(data)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'error': str(e)})}\n\n"
            await asyncio.sleep(5)

    return StreamingResponse(event_generator(), media_type="text/event-stream")


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

# ============= PREFERENCES ENDPOINTS =============

PREFERENCES_PATH = Path("/app/data/preferences.json")

def load_preferences() -> Dict[str, Any]:
    if PREFERENCES_PATH.exists():
        try:
            with open(PREFERENCES_PATH, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_preferences(prefs: Dict[str, Any]):
    PREFERENCES_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(PREFERENCES_PATH, "w") as f:
        json.dump(prefs, f, indent=2)

class Preferences(BaseModel):
    provider: Optional[str] = None
    model: Optional[str] = None
    project_id: Optional[str] = None

@app.get("/api/preferences")
async def get_preferences(project_id: Optional[str] = None):
    prefs = load_preferences()
    if project_id and project_id in prefs:
        return prefs[project_id]
    return prefs.get("global", {})

@app.post("/api/preferences")
async def set_preferences(preferences: Preferences):
    prefs = load_preferences()
    key = preferences.project_id or "global"
    prefs[key] = {"provider": preferences.provider, "model": preferences.model}
    save_preferences(prefs)
    return {"status": "saved"}


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
    # --disable-arp-ping prevents false positives from routers with proxy ARP
    # MAC addresses are collected automatically in XML output for local network scans
    scan_commands = {
        "ping": f"nmap -sn -T4 --disable-arp-ping --min-hostgroup 64 {request.target} -oX - --stats-every 1s",
        "quick": f"nmap -T4 -sS -Pn --disable-arp-ping -F --top-ports 100 --min-hostgroup 32 {request.target} -oX - --stats-every 1s",
        "os": f"nmap -T4 -sS -Pn --disable-arp-ping -O --osscan-guess --max-os-tries 1 --min-hostgroup 16 {request.target} -oX - --stats-every 2s",
        "full": f"nmap -T4 -sS -Pn --disable-arp-ping -sV -O --version-light -p- --min-hostgroup 8 {request.target} -oX - --stats-every 2s"
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
    """Get all discovered network hosts (from current project if selected)"""
    project = get_current_project()
    if project:
        return {"hosts": project.get('hosts', []), "project_id": project['id']}
    return {"hosts": network_hosts}


class HostDiscoveryRequest(BaseModel):
    """Request to add discovered hosts from terminal commands"""
    hosts: List[Dict[str, Any]]
    source: str = "terminal"  # terminal, scan, import


@app.post("/api/network/hosts/discover")
async def discover_hosts(request: HostDiscoveryRequest):
    """Add hosts discovered from terminal commands (e.g., nmap scans)"""
    global network_hosts
    
    project = get_current_project()
    hosts_list = project.get('hosts', []) if project else network_hosts
    
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
        existing = next((h for h in hosts_list if h["ip"] == host["ip"]), None)
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
            hosts_list.append(host)
            if not project:
                network_hosts.append(host)
            added += 1
    
    # Save to project if active
    if project:
        project['hosts'] = hosts_list
        project['updated_at'] = datetime.now().isoformat()
        save_project(project['id'])
    
    return {
        "status": "success",
        "added": added,
        "updated": updated,
        "total_hosts": len(hosts_list),
        "project_id": project['id'] if project else None
    }


@app.delete("/api/network/hosts")
async def clear_network_hosts():
    """Clear all discovered network hosts"""
    global network_hosts
    
    project = get_current_project()
    if project:
        count = len(project.get('hosts', []))
        project['hosts'] = []
        project['updated_at'] = datetime.now().isoformat()
        save_project(project['id'])
        return {"status": "success", "cleared": count, "project_id": project['id']}
    
    count = len(network_hosts)
    network_hosts = []
    return {"status": "success", "cleared": count}


@app.delete("/api/network/hosts/{ip}")
async def delete_network_host(ip: str):
    """Delete a specific network host by IP"""
    global network_hosts
    
    project = get_current_project()
    if project:
        hosts = project.get('hosts', [])
        original_count = len(hosts)
        project['hosts'] = [h for h in hosts if h.get("ip") != ip]
        
        if len(project['hosts']) < original_count:
            project['updated_at'] = datetime.now().isoformat()
            save_project(project['id'])
            return {"status": "success", "deleted": ip}
        raise HTTPException(status_code=404, detail=f"Host {ip} not found")
    
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
# Exploit Suggestion Engine
# ===========================================
class ExploitSuggestionRequest(BaseModel):
    host_ip: Optional[str] = None
    service: Optional[str] = None
    version: Optional[str] = None
    port: Optional[int] = None
    os_type: Optional[str] = None
    all_hosts: bool = False  # If true, suggest for all project hosts


@app.post("/api/exploits/suggest")
async def suggest_exploits(request: ExploitSuggestionRequest):
    """Get AI-powered exploit suggestions based on discovered services"""
    project = get_current_project()
    
    suggestions = []
    
    # Build target list
    targets = []
    if request.all_hosts and project:
        targets = project.get('hosts', [])
    elif request.host_ip and project:
        targets = [h for h in project.get('hosts', []) if h.get('ip') == request.host_ip]
    elif request.service or request.version:
        # Create synthetic target for service-based query
        targets = [{
            'ip': request.host_ip or 'target',
            'ports': [{'port': request.port or 0, 'service': request.service, 'version': request.version}],
            'os_type': request.os_type or ''
        }]
    
    for host in targets:
        host_suggestions = await get_exploit_suggestions_for_host(host)
        if host_suggestions:
            suggestions.extend(host_suggestions)
    
    # Deduplicate and sort by severity
    seen = set()
    unique_suggestions = []
    for s in suggestions:
        key = (s.get('exploit_name', ''), s.get('target', ''))
        if key not in seen:
            seen.add(key)
            unique_suggestions.append(s)
    
    severity_order = {'critical': 0, 'high': 1, 'medium': 2, 'low': 3, 'info': 4}
    unique_suggestions.sort(key=lambda x: severity_order.get(x.get('severity', 'info'), 4))
    
    return {
        "suggestions": unique_suggestions[:20],  # Top 20
        "total": len(unique_suggestions),
        "hosts_analyzed": len(targets)
    }


async def get_exploit_suggestions_for_host(host: Dict) -> List[Dict]:
    """Get exploit suggestions for a specific host"""
    suggestions = []
    host_ip = host.get('ip', 'unknown')
    os_type = host.get('os_type', '').lower()
    
    for port_info in host.get('ports', []):
        port = port_info.get('port')
        service = port_info.get('service', '').lower()
        version = port_info.get('version', '')
        product = port_info.get('product', '')
        
        # Get known exploits for this service
        port_exploits = get_known_exploits(port, service, version, product, os_type)
        for exploit in port_exploits:
            exploit['target'] = host_ip
            exploit['target_port'] = port
            exploit['target_service'] = service
            suggestions.append(exploit)
    
    return suggestions


def get_known_exploits(port: int, service: str, version: str, product: str, os_type: str) -> List[Dict]:
    """Return known exploits for service/version combinations"""
    exploits = []
    
    # SMB Exploits
    if port == 445 or 'smb' in service or 'microsoft-ds' in service:
        exploits.extend([
            {
                'exploit_name': 'EternalBlue (MS17-010)',
                'cve': 'CVE-2017-0144',
                'severity': 'critical',
                'description': 'Remote code execution in SMBv1. Devastating for Windows 7/Server 2008.',
                'msf_module': 'exploit/windows/smb/ms17_010_eternalblue',
                'manual_check': 'nmap -p445 --script smb-vuln-ms17-010 TARGET',
                'conditions': 'Windows systems with SMBv1 enabled'
            },
            {
                'exploit_name': 'SMB Ghost (CVE-2020-0796)',
                'cve': 'CVE-2020-0796',
                'severity': 'critical',
                'description': 'RCE in SMBv3 compression. Affects Windows 10 1903/1909.',
                'msf_module': 'auxiliary/scanner/smb/smb_ms17_010',
                'manual_check': 'nmap -p445 --script smb-vuln-cve-2020-0796 TARGET',
                'conditions': 'Windows 10 version 1903 or 1909'
            },
            {
                'exploit_name': 'SMB Null Session Enumeration',
                'cve': None,
                'severity': 'medium',
                'description': 'Anonymous access to enumerate users, shares, and policies.',
                'msf_module': 'auxiliary/scanner/smb/smb_enumshares',
                'manual_check': 'enum4linux -a TARGET',
                'conditions': 'Misconfigured SMB allowing null sessions'
            }
        ])
    
    # SSH Exploits
    if port == 22 or 'ssh' in service:
        if 'openssh' in product.lower():
            if version:
                try:
                    ver_num = float(version.split('.')[0] + '.' + version.split('.')[1].split('p')[0])
                    if ver_num < 7.7:
                        exploits.append({
                            'exploit_name': 'OpenSSH User Enumeration',
                            'cve': 'CVE-2018-15473',
                            'severity': 'low',
                            'description': f'OpenSSH {version} may be vulnerable to user enumeration.',
                            'msf_module': 'auxiliary/scanner/ssh/ssh_enumusers',
                            'manual_check': 'nmap -p22 --script ssh-auth-methods TARGET',
                            'conditions': 'OpenSSH < 7.7'
                        })
                except: pass
        
        exploits.append({
            'exploit_name': 'SSH Credential Brute Force',
            'cve': None,
            'severity': 'info',
            'description': 'Attempt common username/password combinations.',
            'msf_module': 'auxiliary/scanner/ssh/ssh_login',
            'manual_check': 'hydra -L users.txt -P passwords.txt ssh://TARGET',
            'conditions': 'Weak or default credentials'
        })
    
    # HTTP/HTTPS Exploits
    if port in [80, 443, 8080, 8443] or 'http' in service:
        exploits.extend([
            {
                'exploit_name': 'Web Application Scanning',
                'cve': None,
                'severity': 'info',
                'description': 'Automated scan for common web vulnerabilities.',
                'msf_module': None,
                'manual_check': 'nikto -h TARGET:' + str(port),
                'conditions': 'Web application present'
            },
            {
                'exploit_name': 'Directory Enumeration',
                'cve': None,
                'severity': 'info',
                'description': 'Find hidden directories and files.',
                'msf_module': None,
                'manual_check': f'gobuster dir -u http://TARGET:{port} -w /usr/share/wordlists/dirb/common.txt',
                'conditions': 'Web server responding'
            }
        ])
        
        # Apache/nginx specific
        if 'apache' in product.lower():
            exploits.append({
                'exploit_name': 'Apache mod_cgi RCE (Shellshock)',
                'cve': 'CVE-2014-6271',
                'severity': 'critical',
                'description': 'Remote code execution via CGI scripts if Bash is vulnerable.',
                'msf_module': 'exploit/multi/http/apache_mod_cgi_bash_env_exec',
                'manual_check': 'nmap -p' + str(port) + ' --script http-shellshock TARGET',
                'conditions': 'Apache with CGI and vulnerable Bash'
            })
    
    # FTP Exploits
    if port == 21 or 'ftp' in service:
        exploits.extend([
            {
                'exploit_name': 'FTP Anonymous Access',
                'cve': None,
                'severity': 'medium',
                'description': 'Anonymous FTP login may expose sensitive files.',
                'msf_module': 'auxiliary/scanner/ftp/anonymous',
                'manual_check': 'nmap -p21 --script ftp-anon TARGET',
                'conditions': 'Anonymous access enabled'
            }
        ])
        
        if 'vsftpd' in product.lower() and '2.3.4' in version:
            exploits.append({
                'exploit_name': 'vsFTPd 2.3.4 Backdoor',
                'cve': 'CVE-2011-2523',
                'severity': 'critical',
                'description': 'Backdoor command execution in vsFTPd 2.3.4.',
                'msf_module': 'exploit/unix/ftp/vsftpd_234_backdoor',
                'manual_check': 'Connect to FTP with username containing :)',
                'conditions': 'vsFTPd version 2.3.4 exactly'
            })
    
    # RDP Exploits  
    if port == 3389 or 'rdp' in service or 'ms-wbt-server' in service:
        exploits.extend([
            {
                'exploit_name': 'BlueKeep (CVE-2019-0708)',
                'cve': 'CVE-2019-0708',
                'severity': 'critical',
                'description': 'Pre-authentication RCE in RDP. Wormable vulnerability.',
                'msf_module': 'exploit/windows/rdp/cve_2019_0708_bluekeep_rce',
                'manual_check': 'nmap -p3389 --script rdp-vuln-ms12-020 TARGET',
                'conditions': 'Windows 7, Server 2008, Server 2008 R2'
            },
            {
                'exploit_name': 'RDP Credential Brute Force',
                'cve': None,
                'severity': 'info',
                'description': 'Attempt common credentials against RDP.',
                'msf_module': 'auxiliary/scanner/rdp/rdp_scanner',
                'manual_check': 'hydra -L users.txt -P passwords.txt rdp://TARGET',
                'conditions': 'Weak or default credentials'
            }
        ])
    
    # MySQL
    if port == 3306 or 'mysql' in service:
        exploits.extend([
            {
                'exploit_name': 'MySQL Default/Weak Credentials',
                'cve': None,
                'severity': 'high',
                'description': 'Check for root with no password or common credentials.',
                'msf_module': 'auxiliary/scanner/mysql/mysql_login',
                'manual_check': 'mysql -h TARGET -u root',
                'conditions': 'Weak authentication configuration'
            },
            {
                'exploit_name': 'MySQL UDF for Command Execution',
                'cve': None,
                'severity': 'high',
                'description': 'If we have MySQL root, can potentially execute OS commands.',
                'msf_module': 'exploit/multi/mysql/mysql_udf_payload',
                'manual_check': 'After auth: SELECT sys_exec("whoami")',
                'conditions': 'MySQL root access with FILE privilege'
            }
        ])
    
    # PostgreSQL
    if port == 5432 or 'postgresql' in service:
        exploits.append({
            'exploit_name': 'PostgreSQL Default/Trust Authentication',
            'cve': None,
            'severity': 'high',
            'description': 'Check for default credentials or trust authentication.',
            'msf_module': 'auxiliary/scanner/postgres/postgres_login',
            'manual_check': 'psql -h TARGET -U postgres',
            'conditions': 'Default or trust authentication'
        })
    
    # Redis
    if port == 6379 or 'redis' in service:
        exploits.append({
            'exploit_name': 'Redis Unauthenticated Access',
            'cve': None,
            'severity': 'critical',
            'description': 'Redis often runs without auth, allowing RCE via various techniques.',
            'msf_module': 'auxiliary/scanner/redis/redis_server',
            'manual_check': 'redis-cli -h TARGET INFO',
            'conditions': 'No authentication required'
        })
    
    # Telnet
    if port == 23 or 'telnet' in service:
        exploits.append({
            'exploit_name': 'Telnet Service Active',
            'cve': None,
            'severity': 'medium',
            'description': 'Telnet transmits credentials in cleartext. Finding by itself.',
            'msf_module': 'auxiliary/scanner/telnet/telnet_login',
            'manual_check': 'telnet TARGET',
            'conditions': 'Telnet service running'
        })
    
    return exploits


@app.get("/api/exploits/search/{query}")
async def search_exploits(query: str):
    """Search for exploits using searchsploit"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{KALI_EXECUTOR_URL}/execute",
                json={
                    "command": f"searchsploit --json '{query}'",
                    "timeout": 30
                },
                timeout=35.0
            )
            
            if response.status_code == 200:
                data = response.json()
                output = data.get('output', '')
                
                # Try to parse JSON output
                try:
                    import json as json_module
                    # searchsploit --json output
                    exploits_data = json_module.loads(output)
                    return {
                        "query": query,
                        "results": exploits_data.get('RESULTS_EXPLOIT', [])[:20],
                        "total": len(exploits_data.get('RESULTS_EXPLOIT', []))
                    }
                except:
                    # Return raw output if not JSON
                    return {
                        "query": query,
                        "raw_output": output,
                        "results": []
                    }
    except Exception as e:
        return {"query": query, "error": str(e), "results": []}


# ===========================================
# Automated Recon Pipeline
# ===========================================
class ReconPipelineRequest(BaseModel):
    target: str  # IP, range, or hostname
    pipeline: str = "standard"  # standard, quick, full, stealth
    include_vuln_scan: bool = False
    include_web_enum: bool = False


# Store active pipelines
active_pipelines: Dict[str, Dict] = {}


@app.post("/api/recon/pipeline")
async def start_recon_pipeline(request: ReconPipelineRequest):
    """Start an automated recon pipeline"""
    import asyncio
    
    pipeline_id = str(uuid.uuid4())[:8]
    
    # Define pipeline stages based on type
    stages = []
    
    if request.pipeline == "quick":
        stages = [
            {"name": "Host Discovery", "command": f"nmap -sn -T4 --disable-arp-ping {request.target}", "timeout": 120},
            {"name": "Quick Port Scan", "command": f"nmap -sS -T4 -Pn --disable-arp-ping -F {request.target}", "timeout": 300},
        ]
    elif request.pipeline == "stealth":
        stages = [
            {"name": "Stealth Discovery", "command": f"nmap -sn -T2 {request.target}", "timeout": 300},
            {"name": "Slow Port Scan", "command": f"nmap -sS -T2 -Pn -p 21,22,23,25,80,443,445,3389 {request.target}", "timeout": 600},
        ]
    elif request.pipeline == "full":
        stages = [
            {"name": "Host Discovery", "command": f"nmap -sn -T4 --disable-arp-ping {request.target}", "timeout": 120},
            {"name": "Full Port Scan", "command": f"nmap -sS -T4 -Pn --disable-arp-ping -p- {request.target}", "timeout": 1800},
            {"name": "Service Detection", "command": f"nmap -sV -sC -T4 -Pn --disable-arp-ping -p- {request.target}", "timeout": 2400},
            {"name": "OS Detection", "command": f"nmap -O -T4 -Pn --disable-arp-ping {request.target}", "timeout": 600},
        ]
    else:  # standard
        stages = [
            {"name": "Host Discovery", "command": f"nmap -sn -T4 --disable-arp-ping {request.target}", "timeout": 120},
            {"name": "Top Ports Scan", "command": f"nmap -sS -T4 -Pn --disable-arp-ping --top-ports 1000 {request.target}", "timeout": 600},
            {"name": "Service Detection", "command": f"nmap -sV -T4 -Pn --disable-arp-ping --top-ports 1000 {request.target}", "timeout": 900},
            {"name": "OS Detection", "command": f"nmap -O -T4 -Pn --disable-arp-ping {request.target}", "timeout": 600},
        ]
    
    # Add optional stages
    if request.include_vuln_scan:
        stages.append({
            "name": "Vulnerability Scan",
            "command": f"nmap --script vuln -T4 -Pn --disable-arp-ping {request.target}",
            "timeout": 1800
        })
    
    if request.include_web_enum:
        stages.append({
            "name": "Web Enumeration",
            "command": f"nikto -h {request.target} -Format txt 2>/dev/null || echo 'Nikto scan complete'",
            "timeout": 900
        })
    
    # Initialize pipeline tracking
    active_pipelines[pipeline_id] = {
        "id": pipeline_id,
        "target": request.target,
        "pipeline": request.pipeline,
        "stages": stages,
        "current_stage": 0,
        "status": "running",
        "started_at": datetime.now().isoformat(),
        "results": [],
        "hosts_discovered": []
    }
    
    # Start pipeline execution in background
    asyncio.create_task(execute_pipeline(pipeline_id))
    
    return {
        "status": "started",
        "pipeline_id": pipeline_id,
        "stages": len(stages),
        "estimated_time": sum(s["timeout"] for s in stages) // 60,
        "message": f"Pipeline '{request.pipeline}' started with {len(stages)} stages"
    }


async def execute_pipeline(pipeline_id: str):
    """Execute pipeline stages sequentially"""
    pipeline = active_pipelines.get(pipeline_id)
    if not pipeline:
        return
    
    for i, stage in enumerate(pipeline["stages"]):
        pipeline["current_stage"] = i
        pipeline["current_stage_name"] = stage["name"]
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{KALI_EXECUTOR_URL}/execute",
                    json={
                        "command": stage["command"],
                        "timeout": stage["timeout"],
                        "parse_output": True
                    },
                    timeout=float(stage["timeout"] + 30)
                )
                
                if response.status_code == 200:
                    data = response.json()
                    result = {
                        "stage": stage["name"],
                        "command": stage["command"],
                        "success": True,
                        "output": data.get("output", ""),
                        "parsed": data.get("parsed", {}),
                        "completed_at": datetime.now().isoformat()
                    }
                    
                    # Extract hosts from parsed data
                    if data.get("parsed", {}).get("hosts"):
                        for host in data["parsed"]["hosts"]:
                            if host not in pipeline["hosts_discovered"]:
                                pipeline["hosts_discovered"].append(host)
                                
                                # Add to current project if selected
                                project = get_current_project()
                                if project:
                                    existing = next((h for h in project.get('hosts', []) if h.get('ip') == host.get('ip')), None)
                                    if not existing:
                                        project['hosts'].append(host)
                    
                    pipeline["results"].append(result)
                else:
                    pipeline["results"].append({
                        "stage": stage["name"],
                        "success": False,
                        "error": f"Request failed: {response.status_code}"
                    })
                    
        except Exception as e:
            pipeline["results"].append({
                "stage": stage["name"],
                "success": False,
                "error": str(e)
            })
    
    # Mark pipeline complete
    pipeline["status"] = "completed"
    pipeline["completed_at"] = datetime.now().isoformat()
    
    # Save project if active
    project = get_current_project()
    if project:
        project['updated_at'] = datetime.now().isoformat()
        save_project(project['id'])


@app.get("/api/recon/pipeline/{pipeline_id}")
async def get_pipeline_status(pipeline_id: str):
    """Get status of a recon pipeline"""
    if pipeline_id not in active_pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    pipeline = active_pipelines[pipeline_id]
    return {
        "id": pipeline["id"],
        "target": pipeline["target"],
        "status": pipeline["status"],
        "current_stage": pipeline["current_stage"],
        "current_stage_name": pipeline.get("current_stage_name", ""),
        "total_stages": len(pipeline["stages"]),
        "progress": (pipeline["current_stage"] + 1) / len(pipeline["stages"]) * 100 if pipeline["stages"] else 0,
        "hosts_discovered": len(pipeline["hosts_discovered"]),
        "started_at": pipeline["started_at"],
        "completed_at": pipeline.get("completed_at"),
        "results": pipeline["results"]
    }


@app.get("/api/recon/pipelines")
async def list_pipelines():
    """List all recon pipelines"""
    return {
        "pipelines": [
            {
                "id": p["id"],
                "target": p["target"],
                "pipeline": p["pipeline"],
                "status": p["status"],
                "progress": (p["current_stage"] + 1) / len(p["stages"]) * 100 if p["stages"] else 0,
                "hosts_discovered": len(p["hosts_discovered"]),
                "started_at": p["started_at"]
            }
            for p in active_pipelines.values()
        ]
    }


@app.delete("/api/recon/pipeline/{pipeline_id}")
async def cancel_pipeline(pipeline_id: str):
    """Cancel a running pipeline"""
    if pipeline_id not in active_pipelines:
        raise HTTPException(status_code=404, detail="Pipeline not found")
    
    active_pipelines[pipeline_id]["status"] = "cancelled"
    return {"status": "cancelled", "pipeline_id": pipeline_id}


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


# ===========================================
# CTF AI Agent
# ===========================================
class CTFAgentRequest(BaseModel):
    message: str
    category: str = "general"  # web, crypto, forensics, pwn, reversing, misc, general
    context: Optional[str] = None  # Additional context like challenge description
    hints_used: int = 0
    provider: str = "ollama"
    model: str = "llama3.2"


class CTFHintRequest(BaseModel):
    challenge_name: str
    challenge_description: str
    category: str
    what_tried: Optional[str] = None
    hint_level: int = 1  # 1=subtle, 2=moderate, 3=direct


# CTF conversation history per session
ctf_sessions: Dict[str, List[Dict]] = {}


@app.post("/api/ctf/agent")
async def ctf_agent_chat(request: CTFAgentRequest):
    """AI agent specialized for CTF challenges"""
    
    # Build specialized CTF prompt based on category
    system_prompt = get_ctf_system_prompt(request.category)
    
    # Build the full prompt
    full_prompt = f"""{system_prompt}

User's question/request:
{request.message}

{"Additional context: " + request.context if request.context else ""}

Provide helpful, educational guidance. Focus on teaching the methodology rather than giving direct answers.
If they seem stuck, offer progressive hints. Use markdown formatting."""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/chat",
                json={
                    "message": full_prompt,
                    "provider": request.provider,
                    "model": request.model,
                    "context": "ctf_agent"
                },
                timeout=90.0
            )
            
            if response.status_code == 200:
                data = response.json()
                ai_response = data.get("response", "")
                
                # Extract any tool suggestions from response
                tools = extract_ctf_tools(ai_response, request.category)
                
                return {
                    "response": ai_response,
                    "category": request.category,
                    "suggested_tools": tools,
                    "follow_up_questions": get_follow_up_questions(request.category)
                }
            
            return {"response": get_ctf_fallback(request.category, request.message), "category": request.category}
    except Exception as e:
        return {"response": get_ctf_fallback(request.category, request.message), "error": str(e)}


@app.post("/api/ctf/hint")
async def get_ctf_hint(request: CTFHintRequest):
    """Get progressive hints for a CTF challenge"""
    
    hint_prompts = {
        1: "Give a very subtle hint that points them in the right direction without revealing the solution. Be cryptic but helpful.",
        2: "Give a moderate hint that identifies the general technique or vulnerability type they should look for.",
        3: "Give a direct hint that explains the specific approach needed, but still let them figure out the exact implementation."
    }
    
    prompt = f"""You are a CTF mentor helping with a {request.category} challenge.

Challenge: {request.challenge_name}
Description: {request.challenge_description}
{"What they've tried: " + request.what_tried if request.what_tried else ""}

{hint_prompts.get(request.hint_level, hint_prompts[2])}

Format your hint as:
💡 **Hint Level {request.hint_level}**
[Your hint here]

{"🔧 **Suggested Tool/Command**" if request.hint_level >= 2 else ""}"""

    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{HACKGPT_API_URL}/chat",
                json={
                    "message": prompt,
                    "provider": "ollama",
                    "model": "llama3.2",
                    "context": "ctf_hint"
                },
                timeout=60.0
            )
            
            if response.status_code == 200:
                data = response.json()
                return {
                    "hint": data.get("response", ""),
                    "level": request.hint_level,
                    "next_level_available": request.hint_level < 3
                }
    except Exception:
        pass
    
    # Fallback hints
    return {
        "hint": get_fallback_hint(request.category, request.hint_level),
        "level": request.hint_level,
        "next_level_available": request.hint_level < 3
    }


@app.post("/api/ctf/analyze")
async def analyze_ctf_data(data: Dict[str, Any]):
    """Analyze CTF data (encoded strings, hashes, files, etc.)"""
    
    input_data = data.get("input", "")
    analysis_type = data.get("type", "auto")  # auto, encoding, hash, cipher, binary
    
    results = {
        "input": input_data[:500],  # Truncate for display
        "detections": [],
        "suggestions": []
    }
    
    # Auto-detect data type
    if analysis_type == "auto" or analysis_type == "encoding":
        # Check for Base64
        import base64
        import re
        
        if re.match(r'^[A-Za-z0-9+/]+=*$', input_data) and len(input_data) % 4 == 0:
            try:
                decoded = base64.b64decode(input_data).decode('utf-8', errors='ignore')
                if decoded.isprintable() or len([c for c in decoded if c.isprintable()]) > len(decoded) * 0.7:
                    results["detections"].append({
                        "type": "Base64",
                        "decoded": decoded[:500],
                        "confidence": "high"
                    })
            except:
                pass
        
        # Check for Hex
        if re.match(r'^[0-9a-fA-F]+$', input_data) and len(input_data) % 2 == 0:
            try:
                decoded = bytes.fromhex(input_data).decode('utf-8', errors='ignore')
                results["detections"].append({
                    "type": "Hex",
                    "decoded": decoded[:500],
                    "confidence": "high"
                })
            except:
                pass
        
        # Check for ROT13
        import codecs
        rot13 = codecs.decode(input_data, 'rot_13')
        if rot13 != input_data:
            results["detections"].append({
                "type": "ROT13 (possible)",
                "decoded": rot13[:500],
                "confidence": "medium"
            })
    
    # Check for hash patterns
    if analysis_type == "auto" or analysis_type == "hash":
        hash_patterns = {
            r'^[a-f0-9]{32}$': "MD5",
            r'^[a-f0-9]{40}$': "SHA1",
            r'^[a-f0-9]{64}$': "SHA256",
            r'^[a-f0-9]{128}$': "SHA512",
            r'^\$2[ayb]\$.{56}$': "bcrypt",
            r'^[a-f0-9]{32}:[a-f0-9]+$': "MD5 with salt",
        }
        
        for pattern, hash_type in hash_patterns.items():
            if re.match(pattern, input_data.lower()):
                results["detections"].append({
                    "type": f"Hash: {hash_type}",
                    "suggestion": f"Try cracking with hashcat or john. Mode for {hash_type}",
                    "confidence": "high"
                })
                results["suggestions"].append(f"hashcat -m <mode> '{input_data}' wordlist.txt")
    
    # Suggest tools based on input
    if not results["detections"]:
        results["suggestions"] = [
            "Try CyberChef for multi-layer encoding",
            "Check for custom/proprietary encoding",
            "Look for patterns or repeated sequences",
            "Try frequency analysis if it might be a cipher"
        ]
    
    return results


@app.get("/api/ctf/tools/{category}")
async def get_ctf_tools(category: str):
    """Get recommended tools for a CTF category"""
    
    tools = {
        "web": [
            {"name": "Burp Suite", "command": "burpsuite", "description": "Web proxy and scanner"},
            {"name": "SQLMap", "command": "sqlmap -u 'URL' --dbs", "description": "SQL injection automation"},
            {"name": "Nikto", "command": "nikto -h URL", "description": "Web vulnerability scanner"},
            {"name": "Gobuster", "command": "gobuster dir -u URL -w wordlist", "description": "Directory brute-force"},
            {"name": "WFuzz", "command": "wfuzz -c -w wordlist -u URL/FUZZ", "description": "Web fuzzer"},
            {"name": "XXEinjector", "command": "xxeinjector", "description": "XXE injection tool"},
        ],
        "crypto": [
            {"name": "CyberChef", "command": "https://gchq.github.io/CyberChef/", "description": "Encoding/decoding swiss army knife"},
            {"name": "John the Ripper", "command": "john --wordlist=rockyou.txt hash.txt", "description": "Password cracker"},
            {"name": "Hashcat", "command": "hashcat -m 0 hash.txt wordlist.txt", "description": "GPU password cracker"},
            {"name": "RsaCtfTool", "command": "rsactftool -n N -e E --uncipher C", "description": "RSA attack tool"},
            {"name": "xortool", "command": "xortool -l LENGTH file", "description": "XOR analysis"},
        ],
        "forensics": [
            {"name": "Volatility", "command": "volatility -f dump.raw imageinfo", "description": "Memory forensics"},
            {"name": "Binwalk", "command": "binwalk -e file", "description": "Firmware/file extraction"},
            {"name": "Foremost", "command": "foremost -i image -o output", "description": "File carving"},
            {"name": "Exiftool", "command": "exiftool file", "description": "Metadata extraction"},
            {"name": "Steghide", "command": "steghide extract -sf image.jpg", "description": "Steganography"},
            {"name": "Strings", "command": "strings file | grep -i flag", "description": "Extract strings"},
        ],
        "pwn": [
            {"name": "GDB + Pwndbg", "command": "gdb ./binary", "description": "Debugger with pwn extensions"},
            {"name": "Pwntools", "command": "python3 -c 'from pwn import *'", "description": "CTF exploitation library"},
            {"name": "ROPgadget", "command": "ROPgadget --binary ./binary", "description": "ROP chain builder"},
            {"name": "Checksec", "command": "checksec --file=./binary", "description": "Binary security checks"},
            {"name": "One_gadget", "command": "one_gadget libc.so.6", "description": "Find one-shot RCE gadgets"},
        ],
        "reversing": [
            {"name": "Ghidra", "command": "ghidra", "description": "NSA reverse engineering tool"},
            {"name": "IDA Free", "command": "ida", "description": "Interactive disassembler"},
            {"name": "Radare2", "command": "r2 -A ./binary", "description": "Reverse engineering framework"},
            {"name": "Objdump", "command": "objdump -d ./binary", "description": "Disassembler"},
            {"name": "Ltrace/Strace", "command": "ltrace ./binary", "description": "Library/system call tracer"},
        ],
        "misc": [
            {"name": "CyberChef", "command": "https://gchq.github.io/CyberChef/", "description": "Swiss army knife"},
            {"name": "dCode", "command": "https://www.dcode.fr/", "description": "Cipher identifier"},
            {"name": "Wireshark", "command": "wireshark capture.pcap", "description": "Network analysis"},
            {"name": "Sonic Visualiser", "command": "sonic-visualiser", "description": "Audio analysis"},
        ]
    }
    
    return {"category": category, "tools": tools.get(category, tools["misc"])}


def get_ctf_system_prompt(category: str) -> str:
    """Get specialized system prompt for CTF category"""
    
    base_prompt = """You are an expert CTF (Capture The Flag) mentor and security researcher. 
You help players learn and improve their skills through educational guidance.
Never give direct flag answers, but help them understand the methodology."""

    category_prompts = {
        "web": f"""{base_prompt}

SPECIALTY: Web Security & Application Exploitation

You're an expert in:
- SQL Injection (SQLi), XSS, CSRF, SSRF, XXE
- Authentication bypasses and session management
- File upload vulnerabilities and LFI/RFI
- Server-side template injection (SSTI)
- JWT vulnerabilities and OAuth attacks
- HTTP request smuggling
- WebSocket vulnerabilities

Always suggest checking: robots.txt, source code comments, HTTP headers, cookies.""",

        "crypto": f"""{base_prompt}

SPECIALTY: Cryptography & Code Breaking

You're an expert in:
- Classical ciphers (Caesar, Vigenere, substitution)
- Modern crypto attacks (RSA, AES, DES weaknesses)
- Hash cracking and rainbow tables
- Encoding detection (Base64, hex, URL encoding)
- Padding oracle attacks
- XOR analysis and known-plaintext attacks
- Elliptic curve cryptography

Suggest tools: CyberChef, hashcat, john, RsaCtfTool, xortool.""",

        "forensics": f"""{base_prompt}

SPECIALTY: Digital Forensics & Incident Response

You're an expert in:
- Memory forensics (Volatility framework)
- Disk image analysis
- File carving and recovery
- Network packet analysis (Wireshark)
- Steganography detection
- Metadata analysis
- Log analysis and timeline reconstruction

Always check: file signatures, hidden data, deleted files, metadata.""",

        "pwn": f"""{base_prompt}

SPECIALTY: Binary Exploitation & Pwn

You're an expert in:
- Buffer overflows (stack, heap)
- Format string vulnerabilities
- Return-oriented programming (ROP)
- Shellcode development
- ASLR/NX/PIE/Stack canary bypasses
- Use-after-free and double-free
- Race conditions

Check protections first with checksec. Understand the binary before exploiting.""",

        "reversing": f"""{base_prompt}

SPECIALTY: Reverse Engineering

You're an expert in:
- Static analysis (Ghidra, IDA, radare2)
- Dynamic analysis and debugging (GDB)
- Decompilation and code reconstruction  
- Malware analysis techniques
- Obfuscation and anti-debugging bypasses
- Protocol reverse engineering
- Patching binaries

Start with strings, file type, and basic static analysis before dynamic.""",

        "misc": f"""{base_prompt}

SPECIALTY: Miscellaneous CTF Challenges

You're versatile in:
- OSINT (Open Source Intelligence)
- Trivia and research challenges
- Programming and scripting puzzles
- Audio/image analysis
- QR codes and barcodes
- Esoteric programming languages
- Social engineering concepts

Think outside the box. Check for hidden messages in unusual places."""
    }
    
    return category_prompts.get(category, base_prompt)


def extract_ctf_tools(response: str, category: str) -> List[Dict]:
    """Extract tool suggestions from AI response"""
    tools = []
    
    # Common tool patterns to look for
    tool_patterns = {
        "sqlmap": {"name": "SQLMap", "category": "web"},
        "burp": {"name": "Burp Suite", "category": "web"},
        "gobuster": {"name": "Gobuster", "category": "web"},
        "nikto": {"name": "Nikto", "category": "web"},
        "hashcat": {"name": "Hashcat", "category": "crypto"},
        "john": {"name": "John the Ripper", "category": "crypto"},
        "cyberchef": {"name": "CyberChef", "category": "crypto"},
        "volatility": {"name": "Volatility", "category": "forensics"},
        "binwalk": {"name": "Binwalk", "category": "forensics"},
        "wireshark": {"name": "Wireshark", "category": "forensics"},
        "ghidra": {"name": "Ghidra", "category": "reversing"},
        "gdb": {"name": "GDB", "category": "pwn"},
        "pwntools": {"name": "Pwntools", "category": "pwn"},
        "checksec": {"name": "Checksec", "category": "pwn"},
    }
    
    response_lower = response.lower()
    for pattern, tool_info in tool_patterns.items():
        if pattern in response_lower:
            tools.append(tool_info)
    
    return tools[:5]  # Return top 5


def get_follow_up_questions(category: str) -> List[str]:
    """Get relevant follow-up questions for a category"""
    
    questions = {
        "web": [
            "What HTTP methods does the endpoint accept?",
            "Have you checked for hidden parameters?",
            "What does the source code reveal?",
        ],
        "crypto": [
            "What's the key length or block size?",
            "Do you see any patterns in the ciphertext?",
            "Is this a known algorithm or custom?",
        ],
        "forensics": [
            "What file type is it really (check magic bytes)?",
            "Have you looked at the metadata?",
            "Are there any hidden or deleted files?",
        ],
        "pwn": [
            "What protections are enabled (checksec)?",
            "Is there a stack canary leak possible?",
            "What libc version is being used?",
        ],
        "reversing": [
            "What's the program's main functionality?",
            "Are there any anti-debugging tricks?",
            "Have you identified the key functions?",
        ],
    }
    
    return questions.get(category, ["What have you tried so far?", "Can you share more details?"])


def get_ctf_fallback(category: str, message: str) -> str:
    """Fallback response when AI is unavailable"""
    
    fallbacks = {
        "web": """For web challenges, start with:

1. **Reconnaissance**: Check robots.txt, sitemap.xml, source comments
2. **Identify the stack**: Server headers, error messages, file extensions
3. **Test inputs**: Try SQLi, XSS, command injection on all inputs
4. **Check auth**: Test for auth bypasses, weak sessions, JWT issues

🔧 Tools: Burp Suite, SQLMap, Gobuster, dirb""",

        "crypto": """For crypto challenges:

1. **Identify the cipher**: Pattern analysis, key indicators
2. **Check encoding**: Base64? Hex? Multiple layers?
3. **Look for weaknesses**: Small keys, reused IVs, weak algorithms
4. **Use tools**: CyberChef for quick decoding

🔧 Tools: CyberChef, hashcat, john, dCode.fr""",

        "forensics": """For forensics challenges:

1. **File analysis**: `file`, `binwalk`, `strings`, `xxd`
2. **Check metadata**: `exiftool`, hidden fields
3. **Steganography**: `steghide`, `zsteg`, `stegsolve`
4. **Memory/Disk**: Volatility, Autopsy, FTK

🔧 Tools: binwalk, foremost, volatility, Wireshark""",

        "pwn": """For pwn challenges:

1. **Check protections**: `checksec ./binary`
2. **Understand the binary**: Run it, analyze with GDB
3. **Find vulnerabilities**: Buffer overflow? Format string?
4. **Build exploit**: Pwntools makes it easier

🔧 Tools: GDB + pwndbg, pwntools, ROPgadget, one_gadget""",

        "reversing": """For reversing challenges:

1. **Static analysis**: `file`, `strings`, Ghidra/IDA
2. **Understand flow**: Find main(), trace execution
3. **Dynamic analysis**: GDB, ltrace, strace
4. **Patch if needed**: Modify jumps, bypass checks

🔧 Tools: Ghidra, IDA Free, radare2, GDB"""
    }
    
    return fallbacks.get(category, """I'm your CTF assistant! 

I can help with:
- 🌐 **Web**: SQLi, XSS, SSRF, auth bypasses
- 🔐 **Crypto**: Encoding, ciphers, hash cracking
- 🔍 **Forensics**: File analysis, memory, steganography
- 💥 **Pwn**: Buffer overflows, ROP chains
- 🔄 **Reversing**: Disassembly, debugging

What category is your challenge?""")


def get_fallback_hint(category: str, level: int) -> str:
    """Get fallback hints when AI unavailable"""
    
    hints = {
        1: "🔍 Look more carefully at the data you're given. There might be something hidden in plain sight.",
        2: f"💡 For {category} challenges, make sure you've tried the standard tools and techniques for this category.",
        3: f"🎯 Focus on the most common vulnerability types for {category}. Check the challenge description for subtle clues."
    }
    
    return hints.get(level, hints[2])


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
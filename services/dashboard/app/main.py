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


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8080)
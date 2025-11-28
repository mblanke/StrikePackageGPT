"""
Shared Pydantic models for StrikePackageGPT services.
"""
from pydantic import BaseModel, Field
from typing import Optional, Literal, List, Dict, Any
from datetime import datetime
from enum import Enum


class TaskState(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ToolCategory(str, Enum):
    RECON = "reconnaissance"
    VULN_SCAN = "vulnerability_scanning"
    EXPLOITATION = "exploitation"
    WEB_TESTING = "web_testing"
    PASSWORD = "password_attacks"
    WIRELESS = "wireless"
    FORENSICS = "forensics"


# ============== Chat Models ==============

class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str
    timestamp: Optional[datetime] = None


class ChatRequest(BaseModel):
    message: str
    session_id: Optional[str] = None
    context: Optional[str] = None
    provider: str = "ollama"
    model: str = "llama3.2"
    temperature: float = 0.7
    max_tokens: int = 2048


class ChatResponse(BaseModel):
    provider: str
    model: str
    content: str
    usage: Optional[Dict[str, int]] = None
    session_id: Optional[str] = None


# ============== Command Execution Models ==============

class CommandRequest(BaseModel):
    command: str
    timeout: int = Field(default=300, ge=1, le=3600)
    working_dir: Optional[str] = "/workspace"
    env: Optional[Dict[str, str]] = None


class CommandResult(BaseModel):
    command: str
    exit_code: int
    stdout: str
    stderr: str
    duration_seconds: float
    timed_out: bool = False


# ============== Task Models ==============

class Task(BaseModel):
    task_id: str
    task_type: str
    status: TaskState = TaskState.PENDING
    created_at: datetime = Field(default_factory=datetime.utcnow)
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    result: Optional[Any] = None
    error: Optional[str] = None
    progress: int = Field(default=0, ge=0, le=100)
    metadata: Dict[str, Any] = Field(default_factory=dict)


# ============== Security Tool Models ==============

class SecurityTool(BaseModel):
    name: str
    description: str
    category: ToolCategory
    command_template: str
    required_args: List[str] = []
    optional_args: List[str] = []
    output_parser: Optional[str] = None


class ScanTarget(BaseModel):
    target: str  # IP, hostname, URL, or CIDR
    target_type: Literal["ip", "hostname", "url", "cidr", "auto"] = "auto"
    ports: Optional[str] = None  # e.g., "22,80,443" or "1-1000"
    options: Dict[str, Any] = Field(default_factory=dict)


class ScanRequest(BaseModel):
    target: ScanTarget
    tool: str
    scan_type: Optional[str] = None
    options: Dict[str, Any] = Field(default_factory=dict)


class ScanResult(BaseModel):
    scan_id: str
    tool: str
    target: str
    status: TaskState
    started_at: datetime
    completed_at: Optional[datetime] = None
    raw_output: Optional[str] = None
    parsed_results: Optional[Dict[str, Any]] = None
    findings: List[Dict[str, Any]] = []


# ============== Session Models ==============

class Session(BaseModel):
    session_id: str
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_activity: datetime = Field(default_factory=datetime.utcnow)
    messages: List[ChatMessage] = []
    context: Dict[str, Any] = Field(default_factory=dict)
    active_scans: List[str] = []


# ============== Finding Models ==============

class Severity(str, Enum):
    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Finding(BaseModel):
    finding_id: str
    title: str
    description: str
    severity: Severity
    category: str
    target: str
    evidence: Optional[str] = None
    remediation: Optional[str] = None
    references: List[str] = []
    cve_ids: List[str] = []
    detected_at: datetime = Field(default_factory=datetime.utcnow)
    tool: Optional[str] = None

# StrikePackageGPT - Development Guidelines

## Project Overview

StrikePackageGPT is an AI-powered security analysis platform combining LLM capabilities with professional penetration testing tools. It provides a web interface for security researchers and penetration testers to interact with AI assistants specialized in cybersecurity.

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         Dashboard (8080)                        │
│                    FastAPI + Jinja2 Templates                   │
│              Tabbed UI: Chat | Terminal | Scans                 │
└──────────────────────────┬──────────────────────────────────────┘
                           │
┌──────────────────────────▼──────────────────────────────────────┐
│                      HackGPT API (8001)                         │
│              Security-focused API endpoints                     │
│         Chat, Scans, Execute, Analyze, AI-Scan                  │
└───────────────┬─────────────────────────┬───────────────────────┘
                │                         │
┌───────────────▼──────────┐  ┌───────────▼───────────────────────┐
│    LLM Router (8000)     │  │     Kali Executor (8002)          │
│  OpenAI/Anthropic/Ollama │  │  Docker SDK command execution     │
└───────────────┬──────────┘  └───────────┬───────────────────────┘
                │                         │
┌───────────────▼──────────┐  ┌───────────▼───────────────────────┐
│      Ollama (11434)      │  │       Kali Container              │
│   Local LLM inference    │  │  nmap, nikto, sqlmap, etc.        │
└──────────────────────────┘  └───────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────┐
│                     Shared Library                              │
│            models.py | parsers.py | tools.py                    │
└─────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Chat Flow**: User → Dashboard → HackGPT API → LLM Router → Ollama/OpenAI/Anthropic
2. **Scan Flow**: User → Dashboard → HackGPT API → Kali Executor → Kali Container
3. **AI-Scan Flow**: Combines both - AI plans the scan, Executor runs it, AI analyzes results

## Services

### Dashboard (`services/dashboard/`)
- **Port**: 8080
- **Purpose**: Web UI for interacting with the security AI
- **Tech**: FastAPI, Jinja2, TailwindCSS, Alpine.js
- **Key files**:
  - `app/main.py` - FastAPI application
  - `templates/index.html` - Main dashboard UI

### HackGPT API (`services/hackgpt-api/`)
- **Port**: 8001
- **Purpose**: Security-focused API with specialized prompts
- **Tech**: FastAPI
- **Key endpoints**:
  - `POST /chat` - Security chat interface with session support
  - `POST /analyze` - Start async security analysis tasks
  - `POST /execute` - Execute commands in Kali (proxied)
  - `POST /scan` - Run security scans (nmap, nikto, etc.)
  - `POST /ai-scan` - AI-driven intelligent scanning
  - `GET /scans` - List all scans with status
  - `GET /tools` - List available security tools
  - `POST /suggest-command` - AI-suggested security commands

### LLM Router (`services/llm-router/`)
- **Port**: 8000
- **Purpose**: Route requests to different LLM providers
- **Tech**: FastAPI, httpx
- **Supported providers**:
  - OpenAI (gpt-4o, gpt-4o-mini)
  - Anthropic (Claude Sonnet 4, Claude 3.5 Haiku)
  - Ollama (local models - llama3.2, codellama, mistral)

### Kali (`services/kali/`)
- **Purpose**: Container with security tools
- **Base**: kalilinux/kali-rolling
- **Tools included**:
  - Reconnaissance: nmap, masscan, amass, theHarvester
  - Web: nikto, gobuster, sqlmap
  - Exploitation: metasploit, hydra, searchsploit

### Kali Executor (`services/kali-executor/`)
- **Port**: 8002
- **Purpose**: Execute commands in the Kali container via Docker SDK
- **Tech**: FastAPI, Docker SDK, WebSockets
- **Key endpoints**:
  - `POST /execute` - Execute a command (with whitelist validation)
  - `WS /stream` - WebSocket for real-time command output
  - `GET /jobs` - List running/completed jobs
  - `GET /tools` - List available security tools
- **Security**: Command whitelist restricts executable binaries

### Shared Library (`services/shared/`)
- **Purpose**: Common models and utilities shared across services
- **Files**:
  - `models.py` - Pydantic models (ScanResult, CommandResult, etc.)
  - `parsers.py` - Output parsers for nmap, nikto, etc.
  - `tools.py` - Security tool definitions and templates

## Development Commands

```bash
# Start all services
docker-compose up -d

# Start with build
docker-compose up -d --build

# View logs
docker-compose logs -f

# View specific service logs
docker-compose logs -f dashboard

# Stop all services
docker-compose down

# Rebuild specific service
docker-compose build dashboard

# Access Kali container
docker exec -it strikepackage-kali bash

# Pull Ollama model (run after first start)
docker exec -it strikepackage-ollama ollama pull llama3.2
```

## Environment Variables

Copy `.env.example` to `.env` and configure:

```bash
# Optional - Ollama works without these
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...

# Ollama (default works for Docker network)
OLLAMA_BASE_URL=http://ollama:11434
```

## Code Style Guidelines

### Python
- Use type hints for all function parameters and returns
- Use Pydantic models for request/response validation
- Async functions for I/O operations
- Follow PEP 8 naming conventions
- Use docstrings for public functions

### API Design
- RESTful endpoints with clear naming
- Health check endpoint at `/health` for each service
- Consistent error responses with HTTPException
- CORS enabled for all services

### Frontend
- Alpine.js for reactivity
- TailwindCSS for styling
- Marked.js for Markdown rendering
- Responsive design

## Adding New Features

### New LLM Provider
1. Add configuration to `LLM_ROUTER_URL` in `llm-router/app/main.py`
2. Implement `_call_<provider>` async function
3. Add provider to `/providers` endpoint
4. Update `ChatRequest` model if needed

### New Security Tool
1. Install in `kali/Dockerfile`
2. Add to tool list in `hackgpt-api/app/main.py` `/tools` endpoint
3. Add relevant prompts to `SECURITY_PROMPTS` dict

### New Analysis Type
1. Add prompt to `SECURITY_PROMPTS` in `hackgpt-api/app/main.py`
2. Add button in `dashboard/templates/index.html`
3. Update `SecurityAnalysisRequest` model if needed

## Security Considerations

- This platform is for **authorized security testing only**
- Always obtain proper authorization before testing
- The Kali container has elevated network capabilities
- API keys are passed via environment variables
- No authentication is implemented by default (add for production)

## Troubleshooting

### Ollama not responding
```bash
# Check if Ollama is running
docker-compose logs ollama

# Pull a model if none exist
docker exec -it strikepackage-ollama ollama pull llama3.2
```

### Service connection issues
```bash
# Check network
docker network ls
docker network inspect strikepackagegpt_strikepackage-net

# Check service health
curl http://localhost:8000/health
curl http://localhost:8001/health
curl http://localhost:8080/health
```

### Build issues
```bash
# Clean rebuild
docker-compose down
docker-compose build --no-cache
docker-compose up -d
```
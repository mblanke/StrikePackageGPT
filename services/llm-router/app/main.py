"""
LLM Router Service
Routes requests to different LLM providers (OpenAI, Anthropic, Ollama)
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal
import httpx
import os

app = FastAPI(
    title="LLM Router",
    description="Routes requests to multiple LLM providers",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Configuration from environment
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OLLAMA_BASE_URL = os.getenv("OLLAMA_BASE_URL", "http://192.168.1.50:11434")


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    provider: Literal["openai", "anthropic", "ollama"] = "ollama"
    model: str = "llama3.2"
    messages: list[ChatMessage]
    temperature: float = 0.7
    max_tokens: int = 2048


class ChatResponse(BaseModel):
    provider: str
    model: str
    content: str
    usage: Optional[dict] = None


@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "llm-router"}


@app.get("/providers")
async def list_providers():
    """List available LLM providers and their status"""
    # Dynamically fetch Ollama models
    ollama_models = []
    ollama_available = False
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{OLLAMA_BASE_URL}/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                ollama_models = [m["name"] for m in data.get("models", [])]
                ollama_available = True
    except Exception:
        ollama_models = ["llama3", "mistral", "codellama"]  # fallback
    
    providers = {
        "openai": {"available": bool(OPENAI_API_KEY), "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]},
        "anthropic": {"available": bool(ANTHROPIC_API_KEY), "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"]},
        "ollama": {"available": ollama_available, "base_url": OLLAMA_BASE_URL, "models": ollama_models}
    }
    return providers


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Route chat request to specified LLM provider"""
    
    if request.provider == "openai":
        return await _call_openai(request)
    elif request.provider == "anthropic":
        return await _call_anthropic(request)
    elif request.provider == "ollama":
        return await _call_ollama(request)
    else:
        raise HTTPException(status_code=400, detail=f"Unknown provider: {request.provider}")


async def _call_openai(request: ChatRequest) -> ChatResponse:
    """Call OpenAI API"""
    if not OPENAI_API_KEY:
        raise HTTPException(status_code=503, detail="OpenAI API key not configured")
    
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://api.openai.com/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": request.model,
                "messages": [m.model_dump() for m in request.messages],
                "temperature": request.temperature,
                "max_tokens": request.max_tokens
            },
            timeout=60.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        data = response.json()
        return ChatResponse(
            provider="openai",
            model=request.model,
            content=data["choices"][0]["message"]["content"],
            usage=data.get("usage")
        )


async def _call_anthropic(request: ChatRequest) -> ChatResponse:
    """Call Anthropic API"""
    if not ANTHROPIC_API_KEY:
        raise HTTPException(status_code=503, detail="Anthropic API key not configured")
    
    # Extract system message if present
    system_msg = ""
    messages = []
    for msg in request.messages:
        if msg.role == "system":
            system_msg = msg.content
        else:
            messages.append({"role": msg.role, "content": msg.content})
    
    async with httpx.AsyncClient() as client:
        payload = {
            "model": request.model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature
        }
        if system_msg:
            payload["system"] = system_msg
            
        response = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers={
                "x-api-key": ANTHROPIC_API_KEY,
                "Content-Type": "application/json",
                "anthropic-version": "2023-06-01"
            },
            json=payload,
            timeout=60.0
        )
        
        if response.status_code != 200:
            raise HTTPException(status_code=response.status_code, detail=response.text)
        
        data = response.json()
        return ChatResponse(
            provider="anthropic",
            model=request.model,
            content=data["content"][0]["text"],
            usage=data.get("usage")
        )


async def _call_ollama(request: ChatRequest) -> ChatResponse:
    """Call Ollama API (local models)"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{OLLAMA_BASE_URL}/api/chat",
                json={
                    "model": request.model,
                    "messages": [m.model_dump() for m in request.messages],
                    "stream": False,
                    "options": {
                        "temperature": request.temperature,
                        "num_predict": request.max_tokens
                    }
                },
                timeout=120.0
            )
            
            if response.status_code != 200:
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            data = response.json()
            return ChatResponse(
                provider="ollama",
                model=request.model,
                content=data["message"]["content"],
                usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0)
                }
            )
        except httpx.ConnectError:
            raise HTTPException(status_code=503, detail="Ollama service not available")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
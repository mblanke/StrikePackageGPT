"""
LLM Router Service
Routes requests to different LLM providers (OpenAI, Anthropic, Ollama)
Supports multiple Ollama endpoints with load balancing
"""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, Literal
import httpx
import os
import random
import asyncio
from dataclasses import dataclass
from datetime import datetime, timedelta

app = FastAPI(
    title="LLM Router",
    description="Routes requests to multiple LLM providers with load balancing",
    version="0.2.0"
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

# Separate local and networked Ollama endpoints
OLLAMA_LOCAL_URL = os.getenv("OLLAMA_LOCAL_URL", "http://localhost:11434")
OLLAMA_NETWORK_URLS_STR = os.getenv("OLLAMA_NETWORK_URLS", os.getenv("OLLAMA_ENDPOINTS", os.getenv("OLLAMA_BASE_URL", "")))
OLLAMA_NETWORK_URLS = [url.strip() for url in OLLAMA_NETWORK_URLS_STR.split(",") if url.strip()]

# Legacy support: if only OLLAMA_ENDPOINTS is set, use it for network
LOAD_BALANCE_STRATEGY = os.getenv("LOAD_BALANCE_STRATEGY", "round-robin")  # round-robin, random, failover

@dataclass
class EndpointHealth:
    url: str
    healthy: bool = True
    last_check: datetime = None
    failure_count: int = 0
    models: list = None

# Track endpoint health for both local and network
all_ollama_endpoints = [OLLAMA_LOCAL_URL] + OLLAMA_NETWORK_URLS if OLLAMA_LOCAL_URL else OLLAMA_NETWORK_URLS
endpoint_health: dict[str, EndpointHealth] = {url: EndpointHealth(url=url, models=[]) for url in all_ollama_endpoints}
current_network_endpoint_index = 0


class ChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    provider: Literal["openai", "anthropic", "ollama", "ollama-local", "ollama-network"] = "ollama-local"
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
    return {
        "status": "healthy", 
        "service": "llm-router", 
        "local_endpoint": OLLAMA_LOCAL_URL,
        "network_endpoints": len(OLLAMA_NETWORK_URLS)
    }


async def check_endpoint_health(url: str) -> tuple[bool, list]:
    """Check if an Ollama endpoint is healthy and get its models"""
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url}/api/tags", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                models = [m["name"] for m in data.get("models", [])]
                return True, models
    except Exception:
        pass
    return False, []


async def get_healthy_endpoint(endpoints: list[str]) -> Optional[str]:
    """Get a healthy Ollama endpoint from the given list based on load balancing strategy"""
    global current_network_endpoint_index
    
    if not endpoints:
        return None
    
    # Refresh health status for stale checks (older than 30 seconds)
    now = datetime.now()
    for url in endpoints:
        if url not in endpoint_health:
            endpoint_health[url] = EndpointHealth(url=url, models=[])
        health = endpoint_health[url]
        if health.last_check is None or (now - health.last_check) > timedelta(seconds=30):
            is_healthy, models = await check_endpoint_health(url)
            health.healthy = is_healthy
            health.models = models
            health.last_check = now
            if is_healthy:
                health.failure_count = 0
    
    healthy_endpoints = [url for url in endpoints if endpoint_health.get(url, EndpointHealth(url=url)).healthy]
    
    if not healthy_endpoints:
        return None
    
    if LOAD_BALANCE_STRATEGY == "random":
        return random.choice(healthy_endpoints)
    elif LOAD_BALANCE_STRATEGY == "failover":
        # Always use first available healthy endpoint
        return healthy_endpoints[0]
    else:  # round-robin (default)
        # Find next healthy endpoint in rotation
        for _ in range(len(endpoints)):
            current_network_endpoint_index = (current_network_endpoint_index + 1) % len(endpoints)
            url = endpoints[current_network_endpoint_index]
            if url in healthy_endpoints:
                return url
        return healthy_endpoints[0]


@app.get("/providers")
async def list_providers():
    """List available LLM providers and their status"""
    providers = {
        "openai": {"available": bool(OPENAI_API_KEY), "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo"]},
        "anthropic": {"available": bool(ANTHROPIC_API_KEY), "models": ["claude-sonnet-4-20250514", "claude-3-5-haiku-20241022"]},
    }
    
    # Check local Ollama endpoint
    if OLLAMA_LOCAL_URL:
        is_healthy, models = await check_endpoint_health(OLLAMA_LOCAL_URL)
        endpoint_health[OLLAMA_LOCAL_URL] = EndpointHealth(
            url=OLLAMA_LOCAL_URL, 
            healthy=is_healthy, 
            models=models,
            last_check=datetime.now()
        )
        providers["ollama-local"] = {
            "available": is_healthy,
            "endpoint": OLLAMA_LOCAL_URL,
            "models": models if models else ["llama3", "mistral", "codellama"]
        }
    else:
        providers["ollama-local"] = {"available": False, "models": []}
    
    # Check networked Ollama endpoints
    network_info = []
    network_models = set()
    any_network_available = False
    
    for url in OLLAMA_NETWORK_URLS:
        is_healthy, models = await check_endpoint_health(url)
        endpoint_health[url] = EndpointHealth(
            url=url,
            healthy=is_healthy,
            models=models,
            last_check=datetime.now()
        )
        network_info.append({
            "url": url,
            "available": is_healthy,
            "models": models
        })
        if is_healthy:
            any_network_available = True
            network_models.update(models)
    
    providers["ollama-network"] = {
        "available": any_network_available,
        "endpoints": network_info,
        "load_balance_strategy": LOAD_BALANCE_STRATEGY,
        "models": list(network_models) if network_models else ["llama3", "mistral", "codellama"]
    }
    
    # Legacy: also provide combined "ollama" for backward compatibility
    all_ollama_models = set()
    if providers["ollama-local"]["available"]:
        all_ollama_models.update(providers["ollama-local"]["models"])
    if providers["ollama-network"]["available"]:
        all_ollama_models.update(providers["ollama-network"]["models"])
    
    providers["ollama"] = {
        "available": providers["ollama-local"]["available"] or providers["ollama-network"]["available"],
        "models": list(all_ollama_models) if all_ollama_models else ["llama3", "mistral", "codellama"]
    }
    
    return providers


@app.get("/endpoints")
async def list_endpoints():
    """List all Ollama endpoints with detailed status"""
    results = {
        "local": None,
        "network": []
    }
    
    # Local endpoint
    if OLLAMA_LOCAL_URL:
        is_healthy, models = await check_endpoint_health(OLLAMA_LOCAL_URL)
        results["local"] = {
            "url": OLLAMA_LOCAL_URL,
            "healthy": is_healthy,
            "models": models,
            "failure_count": endpoint_health.get(OLLAMA_LOCAL_URL, EndpointHealth(url=OLLAMA_LOCAL_URL)).failure_count
        }
    
    # Network endpoints
    for url in OLLAMA_NETWORK_URLS:
        is_healthy, models = await check_endpoint_health(url)
        results["network"].append({
            "url": url,
            "healthy": is_healthy,
            "models": models,
            "failure_count": endpoint_health.get(url, EndpointHealth(url=url)).failure_count
        })
    
    return {
        "strategy": LOAD_BALANCE_STRATEGY,
        "endpoints": results,
        "network_healthy_count": sum(1 for r in results["network"] if r["healthy"]),
        "network_total_count": len(results["network"])
    }


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """Route chat request to specified LLM provider"""
    
    if request.provider == "openai":
        return await _call_openai(request)
    elif request.provider == "anthropic":
        return await _call_anthropic(request)
    elif request.provider == "ollama-local":
        return await _call_ollama_local(request)
    elif request.provider == "ollama-network":
        return await _call_ollama_network(request)
    elif request.provider == "ollama":
        # Legacy: try local first, then network
        if OLLAMA_LOCAL_URL:
            try:
                return await _call_ollama_local(request)
            except HTTPException:
                if OLLAMA_NETWORK_URLS:
                    return await _call_ollama_network(request)
                raise
        elif OLLAMA_NETWORK_URLS:
            return await _call_ollama_network(request)
        else:
            raise HTTPException(status_code=503, detail="No Ollama endpoints configured")
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


async def _call_ollama_endpoint(request: ChatRequest, endpoint: str, provider_label: str) -> ChatResponse:
    """Call a specific Ollama endpoint"""
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(
                f"{endpoint}/api/chat",
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
                # Mark endpoint as failed
                if endpoint in endpoint_health:
                    endpoint_health[endpoint].failure_count += 1
                    if endpoint_health[endpoint].failure_count >= 3:
                        endpoint_health[endpoint].healthy = False
                raise HTTPException(status_code=response.status_code, detail=response.text)
            
            # Reset failure count on success
            if endpoint in endpoint_health:
                endpoint_health[endpoint].failure_count = 0
            
            data = response.json()
            return ChatResponse(
                provider=provider_label,
                model=request.model,
                content=data["message"]["content"],
                usage={
                    "prompt_tokens": data.get("prompt_eval_count", 0),
                    "completion_tokens": data.get("eval_count", 0),
                    "endpoint": endpoint
                }
            )
        except httpx.ConnectError:
            # Mark endpoint as unhealthy
            if endpoint in endpoint_health:
                endpoint_health[endpoint].healthy = False
                endpoint_health[endpoint].failure_count += 1
            raise HTTPException(status_code=503, detail=f"Ollama endpoint unavailable: {endpoint}")


async def _call_ollama_local(request: ChatRequest) -> ChatResponse:
    """Call local Ollama instance"""
    if not OLLAMA_LOCAL_URL:
        raise HTTPException(status_code=503, detail="Local Ollama not configured")
    return await _call_ollama_endpoint(request, OLLAMA_LOCAL_URL, "ollama-local")


async def _call_ollama_network(request: ChatRequest) -> ChatResponse:
    """Call networked Ollama with load balancing across endpoints"""
    if not OLLAMA_NETWORK_URLS:
        raise HTTPException(status_code=503, detail="No networked Ollama endpoints configured")
    
    endpoint = await get_healthy_endpoint(OLLAMA_NETWORK_URLS)
    
    if not endpoint:
        raise HTTPException(status_code=503, detail="No healthy networked Ollama endpoints available")
    
    try:
        return await _call_ollama_endpoint(request, endpoint, "ollama-network")
    except HTTPException:
        # Try another endpoint if available
        other_endpoint = await get_healthy_endpoint(OLLAMA_NETWORK_URLS)
        if other_endpoint and other_endpoint != endpoint:
            return await _call_ollama_endpoint(request, other_endpoint, "ollama-network")
        raise


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
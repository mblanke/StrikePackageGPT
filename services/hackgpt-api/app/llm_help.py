"""
LLM Help Module
Provides LLM-powered assistance including chat help, autocomplete, and config suggestions.
Maintains conversation context for persistent help sessions.
"""

from typing import Dict, Any, List, Optional
import os
import httpx
import json


# Store conversation history per session
# Note: In production, use Redis or similar with TTL for scalability
# This simple in-memory dict will grow unbounded - implement cleanup as needed
conversation_contexts: Dict[str, List[Dict[str, str]]] = {}
MAX_SESSIONS = 1000  # Limit number of concurrent sessions


async def chat_completion(
    message: str,
    session_id: Optional[str] = None,
    context: Optional[str] = None,
    provider: str = "ollama",
    model: str = "llama3.2",
    system_prompt: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get LLM chat completion with context awareness.
    
    Args:
        message: User message
        session_id: Session ID for maintaining conversation context
        context: Additional context about current page/operation
        provider: LLM provider (ollama, openai, anthropic)
        model: Model name
        system_prompt: Custom system prompt (uses default if not provided)
        
    Returns:
        Dictionary with LLM response and metadata
    """
    # Default system prompt for help
    if not system_prompt:
        system_prompt = """You are a helpful AI assistant for StrikePackageGPT, a security testing platform.
You help users with:
- Understanding security tools and concepts
- Writing and understanding nmap, nikto, and other security tool commands
- Interpreting scan results and vulnerabilities
- Best practices for penetration testing
- Navigation and usage of the platform

Provide clear, concise, and actionable advice. Include command examples when relevant.
Always emphasize ethical hacking practices and legal considerations."""
    
    # Build messages with conversation history
    messages = [{"role": "system", "content": system_prompt}]
    
    # Add conversation history if session_id provided
    if session_id and session_id in conversation_contexts:
        messages.extend(conversation_contexts[session_id][-10:])  # Last 10 messages
    
    # Add context if provided
    if context:
        messages.append({"role": "system", "content": f"Current context: {context}"})
    
    # Add user message
    messages.append({"role": "user", "content": message})
    
    # Get LLM response
    try:
        llm_router_url = os.getenv("LLM_ROUTER_URL", "http://strikepackage-llm-router:8000")
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{llm_router_url}/chat",
                json={
                    "provider": provider,
                    "model": model,
                    "messages": messages,
                    "temperature": 0.7,
                    "max_tokens": 2048
                },
                timeout=120.0
            )
            
            if response.status_code == 200:
                result = response.json()
                assistant_message = result.get("content", "")
                
                # Store in conversation history
                if session_id:
                    if session_id not in conversation_contexts:
                        # Cleanup old sessions if limit reached
                        if len(conversation_contexts) >= MAX_SESSIONS:
                            # Remove oldest session (simple FIFO)
                            oldest_session = next(iter(conversation_contexts))
                            del conversation_contexts[oldest_session]
                        conversation_contexts[session_id] = []
                    conversation_contexts[session_id].append({"role": "user", "content": message})
                    conversation_contexts[session_id].append({"role": "assistant", "content": assistant_message})
                
                return {
                    "message": assistant_message,
                    "session_id": session_id,
                    "provider": provider,
                    "model": model,
                    "success": True
                }
            else:
                return {
                    "message": "I'm having trouble connecting to the LLM service. Please try again.",
                    "error": response.text,
                    "success": False
                }
                
    except httpx.ConnectError:
        return {
            "message": "LLM service is not available. Please check your connection.",
            "error": "Connection failed",
            "success": False
        }
    except Exception as e:
        return {
            "message": "An error occurred while processing your request.",
            "error": str(e),
            "success": False
        }


async def get_autocomplete(
    partial_text: str,
    context_type: str = "command",
    max_suggestions: int = 5
) -> List[Dict[str, str]]:
    """
    Get autocomplete suggestions for commands or configurations.
    
    Args:
        partial_text: Partial text entered by user
        context_type: Type of autocomplete (command, config, target)
        max_suggestions: Maximum number of suggestions to return
        
    Returns:
        List of suggestion dictionaries with text and description
    """
    suggestions = []
    
    if context_type == "command":
        suggestions = _get_command_suggestions(partial_text)
    elif context_type == "config":
        suggestions = _get_config_suggestions(partial_text)
    elif context_type == "target":
        suggestions = _get_target_suggestions(partial_text)
    
    return suggestions[:max_suggestions]


def _get_command_suggestions(partial_text: str) -> List[Dict[str, str]]:
    """Get command autocomplete suggestions."""
    # Common security tool commands
    commands = [
        {"text": "nmap -sV -sC", "description": "Service version detection with default scripts"},
        {"text": "nmap -p- -T4", "description": "Scan all ports with aggressive timing"},
        {"text": "nmap -sS -O", "description": "SYN stealth scan with OS detection"},
        {"text": "nmap --script vuln", "description": "Run vulnerability detection scripts"},
        {"text": "nikto -h", "description": "Web server vulnerability scan"},
        {"text": "gobuster dir -u", "description": "Directory brute-forcing"},
        {"text": "sqlmap -u", "description": "SQL injection testing"},
        {"text": "whatweb", "description": "Web technology fingerprinting"},
        {"text": "searchsploit", "description": "Search exploit database"},
        {"text": "hydra -l", "description": "Network login cracking"}
    ]
    
    # Filter based on partial text
    partial_lower = partial_text.lower()
    return [cmd for cmd in commands if cmd["text"].lower().startswith(partial_lower)]


def _get_config_suggestions(partial_text: str) -> List[Dict[str, str]]:
    """Get configuration autocomplete suggestions."""
    configs = [
        {"text": "timeout", "description": "Command execution timeout in seconds"},
        {"text": "max_workers", "description": "Maximum parallel workers"},
        {"text": "scan_intensity", "description": "Scan aggressiveness (1-5)"},
        {"text": "rate_limit", "description": "Requests per second limit"},
        {"text": "default_ports", "description": "Default ports to scan"},
        {"text": "output_format", "description": "Output format (json, xml, text)"},
        {"text": "log_level", "description": "Logging verbosity (debug, info, warning, error)"},
        {"text": "retry_count", "description": "Number of retries on failure"}
    ]
    
    partial_lower = partial_text.lower()
    return [cfg for cfg in configs if cfg["text"].lower().startswith(partial_lower)]


def _get_target_suggestions(partial_text: str) -> List[Dict[str, str]]:
    """Get target specification autocomplete suggestions."""
    suggestions = [
        {"text": "192.168.1.0/24", "description": "Scan entire /24 subnet"},
        {"text": "192.168.1.1-50", "description": "Scan IP range"},
        {"text": "10.0.0.0/8", "description": "Scan entire /8 network"},
        {"text": "localhost", "description": "Scan local machine"},
        {"text": "example.com", "description": "Scan domain name"}
    ]
    
    return suggestions


async def explain_anything(
    item: str,
    item_type: str = "auto",
    context: Optional[Dict] = None
) -> Dict[str, Any]:
    """
    Explain anything using LLM - commands, configs, errors, concepts.
    
    Args:
        item: The item to explain
        item_type: Type of item (auto, command, config, error, concept)
        context: Additional context
        
    Returns:
        Dictionary with explanation
    """
    # Auto-detect type if not specified
    if item_type == "auto":
        item_type = _detect_item_type(item)
    
    # Build appropriate prompt based on type
    prompts = {
        "command": f"Explain this security command in plain English:\n{item}\n\nInclude: what it does, any flags/options, expected output, and safety considerations.",
        "config": f"Explain this configuration setting:\n{item}\n\nInclude: purpose, typical values, and recommendations.",
        "error": f"Explain this error message:\n{item}\n\nInclude: what went wrong, likely causes, and how to fix it.",
        "concept": f"Explain this security concept:\n{item}\n\nProvide a clear, beginner-friendly explanation with examples.",
        "scan_result": f"Explain this scan result:\n{item}\n\nInclude: significance, risk level, and recommended actions."
    }
    
    prompt = prompts.get(item_type, f"Explain: {item}")
    
    # Get explanation from LLM
    result = await chat_completion(
        message=prompt,
        system_prompt="You are a security education assistant. Provide clear, concise explanations suitable for both beginners and experts. Use plain English and include practical examples."
    )
    
    return {
        "item": item,
        "item_type": item_type,
        "explanation": result.get("message", ""),
        "success": result.get("success", False)
    }


def _detect_item_type(item: str) -> str:
    """Detect what type of item is being explained."""
    item_lower = item.lower()
    
    # Check for command patterns
    if any(tool in item_lower for tool in ['nmap', 'nikto', 'gobuster', 'sqlmap', 'hydra']):
        return "command"
    
    # Check for error patterns
    if any(word in item_lower for word in ['error', 'exception', 'failed', 'denied']):
        return "error"
    
    # Check for config patterns
    if '=' in item or ':' in item or 'config' in item_lower:
        return "config"
    
    # Check for scan result patterns
    if any(word in item_lower for word in ['open', 'closed', 'filtered', 'vulnerability', 'port']):
        return "scan_result"
    
    # Default to concept
    return "concept"


async def suggest_config(
    config_type: str,
    current_values: Optional[Dict] = None,
    use_case: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get LLM-powered configuration suggestions.
    
    Args:
        config_type: Type of configuration (scan, system, security)
        current_values: Current configuration values
        use_case: Specific use case or scenario
        
    Returns:
        Dictionary with configuration suggestions
    """
    prompt_parts = [f"Suggest optimal configuration for {config_type}."]
    
    if current_values:
        prompt_parts.append(f"\nCurrent configuration:\n{json.dumps(current_values, indent=2)}")
    
    if use_case:
        prompt_parts.append(f"\nUse case: {use_case}")
    
    prompt_parts.append("\nProvide recommended values with explanations. Format as JSON if possible.")
    
    result = await chat_completion(
        message="\n".join(prompt_parts),
        system_prompt="You are a security configuration expert. Provide optimal, secure, and practical configuration recommendations."
    )
    
    # Try to extract JSON from response
    response_text = result.get("message", "")
    suggested_config = _extract_json_from_text(response_text)
    
    return {
        "config_type": config_type,
        "suggestions": suggested_config or {},
        "explanation": response_text,
        "success": result.get("success", False)
    }


def _extract_json_from_text(text: str) -> Optional[Dict]:
    """Try to extract JSON object from text."""
    try:
        # Look for JSON object in text
        start = text.find('{')
        end = text.rfind('}')
        if start != -1 and end != -1:
            json_str = text[start:end+1]
            return json.loads(json_str)
    except json.JSONDecodeError:
        pass
    return None


async def get_step_by_step(
    task: str,
    skill_level: str = "intermediate"
) -> Dict[str, Any]:
    """
    Get step-by-step instructions for a task.
    
    Args:
        task: The task to get instructions for
        skill_level: User skill level (beginner, intermediate, advanced)
        
    Returns:
        Dictionary with step-by-step instructions
    """
    skill_context = {
        "beginner": "Explain in simple terms, avoid jargon, include screenshots references",
        "intermediate": "Provide clear steps with command examples",
        "advanced": "Be concise, focus on efficiency and best practices"
    }
    
    context = skill_context.get(skill_level, skill_context["intermediate"])
    
    prompt = f"""Provide step-by-step instructions for: {task}

User skill level: {skill_level}
{context}

Format as numbered steps with clear actions. Include any commands to run."""
    
    result = await chat_completion(
        message=prompt,
        system_prompt="You are an expert security instructor. Provide clear, actionable step-by-step guidance."
    )
    
    # Parse steps from response
    steps = _parse_steps_from_text(result.get("message", ""))
    
    return {
        "task": task,
        "skill_level": skill_level,
        "steps": steps,
        "full_explanation": result.get("message", ""),
        "success": result.get("success", False)
    }


def _parse_steps_from_text(text: str) -> List[Dict[str, str]]:
    """Parse numbered steps from text."""
    steps = []
    lines = text.split('\n')
    
    for line in lines:
        # Match patterns like "1.", "Step 1:", "1)"
        import re
        match = re.match(r'^(?:Step\s+)?(\d+)[.):]\s*(.+)$', line.strip(), re.IGNORECASE)
        if match:
            step_num = int(match.group(1))
            step_text = match.group(2).strip()
            steps.append({
                "number": step_num,
                "instruction": step_text
            })
    
    return steps


def clear_conversation_context(session_id: str) -> bool:
    """
    Clear conversation context for a session.
    
    Args:
        session_id: Session ID to clear
        
    Returns:
        True if cleared, False if session didn't exist
    """
    if session_id in conversation_contexts:
        del conversation_contexts[session_id]
        return True
    return False


def get_conversation_summary(session_id: str) -> Dict[str, Any]:
    """
    Get summary of conversation for a session.
    
    Args:
        session_id: Session ID
        
    Returns:
        Dictionary with conversation summary
    """
    if session_id not in conversation_contexts:
        return {
            "session_id": session_id,
            "exists": False,
            "message_count": 0
        }
    
    messages = conversation_contexts[session_id]
    user_messages = [m for m in messages if m["role"] == "user"]
    
    return {
        "session_id": session_id,
        "exists": True,
        "message_count": len(messages),
        "user_message_count": len(user_messages),
        "last_messages": messages[-5:] if messages else []
    }

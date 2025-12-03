"""
Voice Control Module
Handles speech-to-text and text-to-speech functionality, plus voice command routing.
Supports local Whisper (preferred) and OpenAI API as fallback.
"""

import os
import tempfile
from typing import Dict, Any, Optional, Tuple
import json
import re


def transcribe_audio(audio_data: bytes, format: str = "wav") -> Dict[str, Any]:
    """
    Transcribe audio to text using Whisper (local preferred) or OpenAI API.
    
    Args:
        audio_data: Raw audio bytes
        format: Audio format (wav, mp3, webm, etc.)
        
    Returns:
        Dictionary with transcription result and metadata
        {
            "text": "transcribed text",
            "language": "en",
            "confidence": 0.95,
            "method": "whisper-local" or "openai"
        }
    """
    # Try local Whisper first
    try:
        return _transcribe_with_local_whisper(audio_data, format)
    except Exception as e:
        print(f"Local Whisper failed: {e}, falling back to OpenAI API")
    
    # Fallback to OpenAI API if configured
    if os.getenv("OPENAI_API_KEY"):
        try:
            return _transcribe_with_openai(audio_data, format)
        except Exception as e:
            print(f"OpenAI transcription failed: {e}")
            return {
                "text": "",
                "error": f"Transcription failed: {str(e)}",
                "method": "none"
            }
    
    return {
        "text": "",
        "error": "No transcription service available. Install Whisper or configure OPENAI_API_KEY.",
        "method": "none"
    }


def _transcribe_with_local_whisper(audio_data: bytes, format: str) -> Dict[str, Any]:
    """
    Transcribe using local Whisper model.
    
    Args:
        audio_data: Raw audio bytes
        format: Audio format
        
    Returns:
        Transcription result dictionary
    """
    try:
        import whisper
        
        # Save audio to temporary file
        with tempfile.NamedTemporaryFile(suffix=f".{format}", delete=False) as temp_audio:
            temp_audio.write(audio_data)
            temp_audio_path = temp_audio.name
        
        try:
            # Load model (use base model by default for speed/accuracy balance)
            model_size = os.getenv("WHISPER_MODEL", "base")
            model = whisper.load_model(model_size)
            
            # Transcribe
            result = model.transcribe(temp_audio_path)
            
            return {
                "text": result["text"].strip(),
                "language": result.get("language", "unknown"),
                "confidence": 1.0,  # Whisper doesn't provide confidence scores
                "method": "whisper-local",
                "model": model_size
            }
        finally:
            # Clean up temp file
            try:
                os.unlink(temp_audio_path)
            except (OSError, FileNotFoundError) as e:
                print(f"Warning: Could not delete temp file: {e}")
                
    except ImportError:
        raise Exception("Whisper not installed. Install with: pip install openai-whisper")


def _transcribe_with_openai(audio_data: bytes, format: str) -> Dict[str, Any]:
    """
    Transcribe using OpenAI Whisper API.
    
    Args:
        audio_data: Raw audio bytes
        format: Audio format
        
    Returns:
        Transcription result dictionary
    """
    try:
        import httpx
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise Exception("OPENAI_API_KEY not configured")
        
        # Prepare multipart form data
        files = {
            'file': (f'audio.{format}', audio_data, f'audio/{format}')
        }
        data = {
            'model': 'whisper-1',
            'language': 'en'  # Can be auto-detected by omitting this
        }
        
        # Make API request
        with httpx.Client() as client:
            response = client.post(
                'https://api.openai.com/v1/audio/transcriptions',
                headers={'Authorization': f'Bearer {api_key}'},
                files=files,
                data=data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                result = response.json()
                return {
                    "text": result.get("text", "").strip(),
                    "language": "en",
                    "confidence": 1.0,
                    "method": "openai"
                }
            else:
                raise Exception(f"OpenAI API error: {response.status_code} - {response.text}")
                
    except ImportError:
        raise Exception("httpx not installed")


def speak_text(text: str, voice: str = "alloy", format: str = "mp3") -> Optional[bytes]:
    """
    Convert text to speech using OpenAI TTS, Coqui, or browser fallback.
    
    Args:
        text: Text to convert to speech
        voice: Voice selection (depends on TTS engine)
        format: Audio format (mp3, wav, opus)
        
    Returns:
        Audio bytes or None if TTS not available
    """
    # Try OpenAI TTS if configured
    if os.getenv("OPENAI_API_KEY"):
        try:
            return _tts_with_openai(text, voice, format)
        except Exception as e:
            print(f"OpenAI TTS failed: {e}")
    
    # Try local Coqui TTS
    try:
        return _tts_with_coqui(text)
    except Exception as e:
        print(f"Coqui TTS failed: {e}")
    
    # Return None to signal browser should handle TTS
    return None


def _tts_with_openai(text: str, voice: str, format: str) -> bytes:
    """
    Text-to-speech using OpenAI TTS API.
    
    Args:
        text: Text to speak
        voice: Voice name (alloy, echo, fable, onyx, nova, shimmer)
        format: Audio format
        
    Returns:
        Audio bytes
    """
    try:
        import httpx
        
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise Exception("OPENAI_API_KEY not configured")
        
        # Valid voices for OpenAI TTS
        valid_voices = ["alloy", "echo", "fable", "onyx", "nova", "shimmer"]
        if voice not in valid_voices:
            voice = "alloy"
        
        # Valid formats
        valid_formats = ["mp3", "opus", "aac", "flac"]
        if format not in valid_formats:
            format = "mp3"
        
        with httpx.Client() as client:
            response = client.post(
                'https://api.openai.com/v1/audio/speech',
                headers={
                    'Authorization': f'Bearer {api_key}',
                    'Content-Type': 'application/json'
                },
                json={
                    'model': 'tts-1',  # or 'tts-1-hd' for higher quality
                    'input': text[:4096],  # Max 4096 characters
                    'voice': voice,
                    'response_format': format
                },
                timeout=30.0
            )
            
            if response.status_code == 200:
                return response.content
            else:
                raise Exception(f"OpenAI TTS error: {response.status_code} - {response.text}")
                
    except ImportError:
        raise Exception("httpx not installed")


def _tts_with_coqui(text: str) -> bytes:
    """
    Text-to-speech using Coqui TTS (local).
    
    Args:
        text: Text to speak
        
    Returns:
        Audio bytes (WAV format)
    """
    try:
        from TTS.api import TTS
        import numpy as np
        import io
        import wave
        
        # Initialize TTS with a fast model
        tts = TTS(model_name="tts_models/en/ljspeech/tacotron2-DDC", progress_bar=False)
        
        # Generate speech
        wav = tts.tts(text)
        
        # Convert to WAV bytes
        wav_io = io.BytesIO()
        with wave.open(wav_io, 'wb') as wav_file:
            wav_file.setnchannels(1)
            wav_file.setsampwidth(2)
            wav_file.setframerate(22050)
            wav_file.writeframes(np.array(wav * 32767, dtype=np.int16).tobytes())
        
        return wav_io.getvalue()
        
    except ImportError:
        raise Exception("Coqui TTS not installed. Install with: pip install TTS")


def parse_voice_command(text: str) -> Dict[str, Any]:
    """
    Parse voice command text to extract intent and parameters.
    
    Args:
        text: Transcribed voice command text
        
    Returns:
        Dictionary with command intent and parameters
        {
            "intent": "list_agents" | "summarize" | "deploy_agent" | "run_scan" | "unknown",
            "parameters": {...},
            "confidence": 0.0-1.0
        }
    """
    text_lower = text.lower().strip()
    
    # Command patterns
    patterns = [
        # List commands
        (r'\b(list|show|display)\s+(agents|scans|findings|results)\b', 'list', lambda m: {'target': m.group(2)}),
        
        # Summarize commands
        (r'\b(summarize|summary of|sum up)\s+(findings|results|scan)\b', 'summarize', lambda m: {'target': m.group(2)}),
        
        # Deploy/start commands
        (r'\b(deploy|start|launch|run)\s+agent\s+(?:on\s+)?(.+)', 'deploy_agent', lambda m: {'target': m.group(2).strip()}),
        
        # Scan commands
        (r'\b(scan|nmap|enumerate)\s+(.+?)(?:\s+(?:using|with)\s+(\w+))?$', 'run_scan', 
         lambda m: {'target': m.group(2).strip(), 'tool': m.group(3) if m.group(3) else 'nmap'}),
        
        # Status commands
        (r'\b(status|what\'?s\s+(?:the\s+)?status)\b', 'get_status', lambda m: {}),
        
        # Help commands
        (r'\b(help|how\s+do\s+i|assist)\b', 'help', lambda m: {'query': text}),
        
        # Clear/stop commands
        (r'\b(stop|cancel|clear)\s+(scan|all|everything)\b', 'stop', lambda m: {'target': m.group(2)}),
        
        # Navigate commands
        (r'\b(go\s+to|open|navigate\s+to)\s+(.+)', 'navigate', lambda m: {'destination': m.group(2).strip()}),
    ]
    
    # Try to match patterns
    for pattern, intent, param_func in patterns:
        match = re.search(pattern, text_lower)
        if match:
            try:
                parameters = param_func(match)
                return {
                    "intent": intent,
                    "parameters": parameters,
                    "confidence": 0.85,
                    "raw_text": text
                }
            except Exception as e:
                print(f"Error parsing command parameters: {e}")
    
    # No pattern matched
    return {
        "intent": "unknown",
        "parameters": {},
        "confidence": 0.0,
        "raw_text": text
    }


def route_command(command_result: Dict[str, Any]) -> Dict[str, Any]:
    """
    Route a parsed voice command to the appropriate action.
    
    Args:
        command_result: Result from parse_voice_command()
        
    Returns:
        Dictionary with routing information
        {
            "action": "api_call" | "navigate" | "notify" | "error",
            "endpoint": "/api/...",
            "method": "GET" | "POST",
            "data": {...},
            "message": "Human-readable action description"
        }
    """
    intent = command_result.get("intent")
    params = command_result.get("parameters", {})
    
    if intent == "list":
        target = params.get("target", "")
        endpoint_map = {
            "agents": "/api/agents",
            "scans": "/api/scans",
            "findings": "/api/findings",
            "results": "/api/results"
        }
        endpoint = endpoint_map.get(target, "/api/scans")
        return {
            "action": "api_call",
            "endpoint": endpoint,
            "method": "GET",
            "data": {},
            "message": f"Fetching {target}..."
        }
    
    elif intent == "summarize":
        target = params.get("target", "findings")
        return {
            "action": "api_call",
            "endpoint": "/api/summarize",
            "method": "POST",
            "data": {"target": target},
            "message": f"Summarizing {target}..."
        }
    
    elif intent == "deploy_agent":
        target = params.get("target", "")
        return {
            "action": "api_call",
            "endpoint": "/api/agents/deploy",
            "method": "POST",
            "data": {"target": target},
            "message": f"Deploying agent to {target}..."
        }
    
    elif intent == "run_scan":
        target = params.get("target", "")
        tool = params.get("tool", "nmap")
        return {
            "action": "api_call",
            "endpoint": "/api/scan",
            "method": "POST",
            "data": {
                "tool": tool,
                "target": target,
                "scan_type": "quick"
            },
            "message": f"Starting {tool} scan of {target}..."
        }
    
    elif intent == "get_status":
        return {
            "action": "api_call",
            "endpoint": "/api/status",
            "method": "GET",
            "data": {},
            "message": "Checking system status..."
        }
    
    elif intent == "help":
        query = params.get("query", "")
        return {
            "action": "api_call",
            "endpoint": "/api/llm/chat",
            "method": "POST",
            "data": {"message": query, "context": "help_request"},
            "message": "Getting help..."
        }
    
    elif intent == "stop":
        target = params.get("target", "all")
        return {
            "action": "api_call",
            "endpoint": "/api/scans/clear" if target in ["all", "everything"] else "/api/scan/stop",
            "method": "DELETE",
            "data": {},
            "message": f"Stopping {target}..."
        }
    
    elif intent == "navigate":
        destination = params.get("destination", "")
        # Map common destinations
        destination_map = {
            "dashboard": "/",
            "home": "/",
            "terminal": "/terminal",
            "scans": "/scans",
            "settings": "/settings"
        }
        path = destination_map.get(destination, f"/{destination}")
        return {
            "action": "navigate",
            "endpoint": path,
            "method": "GET",
            "data": {},
            "message": f"Navigating to {destination}..."
        }
    
    else:
        # Unknown intent - return error
        return {
            "action": "error",
            "endpoint": "",
            "method": "",
            "data": {},
            "message": "I didn't understand that command. Try 'help' for available commands.",
            "error": "unknown_intent"
        }


def get_voice_command_help() -> Dict[str, list]:
    """
    Get list of available voice commands.
    
    Returns:
        Dictionary categorized by command type
    """
    return {
        "navigation": [
            "Go to dashboard",
            "Open terminal",
            "Navigate to scans"
        ],
        "scanning": [
            "Scan 192.168.1.1",
            "Run nmap scan on example.com",
            "Start scan of 10.0.0.0/24"
        ],
        "information": [
            "List scans",
            "Show agents",
            "Display findings",
            "What's the status"
        ],
        "actions": [
            "Deploy agent on target.com",
            "Stop all scans",
            "Clear everything",
            "Summarize findings"
        ],
        "help": [
            "Help me with nmap",
            "How do I scan a network",
            "Assist with reconnaissance"
        ]
    }

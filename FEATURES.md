# StrikePackageGPT - New Features Documentation

This document describes the newly added features to StrikePackageGPT, including voice control, interactive network mapping, beginner onboarding, LLM-driven help, and workflow integration.

---

## 📋 Table of Contents

1. [Backend Modules](#backend-modules)
2. [Frontend Components](#frontend-components)
3. [API Endpoints](#api-endpoints)
4. [Setup & Configuration](#setup--configuration)
5. [Usage Examples](#usage-examples)
6. [Integration Guide](#integration-guide)

---

## Backend Modules

### 1. Nmap Parser (`nmap_parser.py`)

**Purpose:** Parse Nmap XML or JSON output to extract detailed host information.

**Features:**
- Parse Nmap XML and JSON formats
- Extract IP addresses, hostnames, OS detection
- Device type classification (server, workstation, network device, etc.)
- MAC address and vendor information
- Port and service enumeration
- OS icon recommendations

**Functions:**
```python
parse_nmap_xml(xml_content: str) -> List[Dict[str, Any]]
parse_nmap_json(json_content: str) -> List[Dict[str, Any]]
classify_device_type(host: Dict) -> str
detect_os_type(os_string: str) -> str
get_os_icon_name(host: Dict) -> str
```

**Example Usage:**
```python
from app import nmap_parser

# Parse XML output
with open('nmap_scan.xml', 'r') as f:
    xml_data = f.read()
    hosts = nmap_parser.parse_nmap_xml(xml_data)

for host in hosts:
    print(f"IP: {host['ip']}, OS: {host['os_type']}, Device: {host['device_type']}")
```

---

### 2. Voice Control (`voice.py`)

**Purpose:** Speech-to-text, text-to-speech, and voice command routing.

**Features:**
- Speech-to-text using local Whisper (preferred) or OpenAI API
- Text-to-speech using OpenAI TTS, Coqui TTS, or browser fallback
- Voice command parsing and routing
- Support for common commands: list, scan, deploy, status, help

**Functions:**
```python
transcribe_audio(audio_data: bytes, format: str = "wav") -> Dict[str, Any]
speak_text(text: str, voice: str = "alloy") -> Optional[bytes]
parse_voice_command(text: str) -> Dict[str, Any]
route_command(command_result: Dict) -> Dict[str, Any]
get_voice_command_help() -> Dict[str, list]
```

**Supported Commands:**
- "Scan 192.168.1.1"
- "List scans"
- "Show agents"
- "Deploy agent on target.com"
- "What's the status"
- "Help me with nmap"

**Configuration:**
```bash
# Optional: For local Whisper
pip install openai-whisper

# Optional: For OpenAI API
export OPENAI_API_KEY=sk-...

# Optional: For Coqui TTS
pip install TTS
```

---

### 3. Explain Module (`explain.py`)

**Purpose:** Plain-English explanations for configs, logs, and errors.

**Features:**
- Configuration explanations with recommendations
- Error message interpretation with suggested fixes
- Log entry analysis with severity assessment
- Wizard step help for onboarding
- Auto-fix suggestions

**Functions:**
```python
explain_config(config_key: str, config_value: Any, context: Optional[Dict]) -> Dict
explain_error(error_message: str, error_type: Optional[str], context: Optional[Dict]) -> Dict
explain_log_entry(log_entry: str, log_level: Optional[str]) -> Dict
get_wizard_step_help(wizard_type: str, step_number: int) -> Dict
suggest_fix(issue_description: str, context: Optional[Dict]) -> List[str]
```

**Example:**
```python
from app import explain

# Explain a config setting
result = explain.explain_config("timeout", 30)
print(result['description'])
print(result['recommendations'])

# Explain an error
result = explain.explain_error("Connection refused")
print(result['plain_english'])
print(result['suggested_fixes'])
```

---

### 4. LLM Help (`llm_help.py`)

**Purpose:** LLM-powered assistance, autocomplete, and suggestions.

**Features:**
- Context-aware chat completion
- Maintains conversation history per session
- Autocomplete for commands and configurations
- Step-by-step instructions
- Configuration suggestions

**Functions:**
```python
async chat_completion(message: str, session_id: Optional[str], ...) -> Dict
async get_autocomplete(partial_text: str, context_type: str) -> List[Dict]
async explain_anything(item: str, item_type: str) -> Dict
async suggest_config(config_type: str, current_values: Optional[Dict]) -> Dict
async get_step_by_step(task: str, skill_level: str) -> Dict
```

**Example:**
```python
from app import llm_help

# Get chat response
response = await llm_help.chat_completion(
    message="How do I scan a network with nmap?",
    session_id="user-123"
)
print(response['message'])

# Get autocomplete
suggestions = await llm_help.get_autocomplete("nmap -s", "command")
for suggestion in suggestions:
    print(f"{suggestion['text']}: {suggestion['description']}")
```

---

### 5. Config Validator (`config_validator.py`)

**Purpose:** Validate configurations before applying changes.

**Features:**
- Configuration validation with plain-English warnings
- Backup and restore functionality
- Auto-fix suggestions for common errors
- Disk-persisted backups
- Type-specific validation (scan, network, security)

**Functions:**
```python
validate_config(config_data: Dict, config_type: str) -> Dict
backup_config(config_name: str, config_data: Dict, description: str) -> Dict
restore_config(backup_id: str) -> Dict
list_backups(config_name: Optional[str]) -> Dict
suggest_autofix(validation_result: Dict, config_data: Dict) -> Dict
```

**Example:**
```python
from app import config_validator

# Validate configuration
config = {"timeout": 5, "target": "192.168.1.0/24"}
result = config_validator.validate_config(config, "scan")

if not result['valid']:
    print("Errors:", result['errors'])
    print("Warnings:", result['warnings'])

# Backup configuration
backup = config_validator.backup_config("scan_config", config, "Before changes")
print(f"Backed up as: {backup['backup_id']}")

# List backups
backups = config_validator.list_backups("scan_config")
for backup in backups['backups']:
    print(f"{backup['backup_id']} - {backup['timestamp']}")
```

---

## Frontend Components

### 1. NetworkMap.jsx

**Purpose:** Interactive network visualization using Cytoscape.js or Vis.js.

**Features:**
- Displays discovered hosts with OS/device icons
- Hover tooltips with detailed host information
- Filter/search functionality
- Export to PNG or CSV
- Automatic subnet grouping

**Props:**
```javascript
{
  scanId: string,           // ID of scan to visualize
  onNodeClick: function     // Callback when node is clicked
}
```

**Usage:**
```jsx
<NetworkMap 
  scanId="scan-123" 
  onNodeClick={(host) => console.log(host)}
/>
```

**Dependencies:**
```bash
npm install cytoscape  # or vis-network
```

---

### 2. VoiceControls.jsx

**Purpose:** Voice command interface with hotkey support.

**Features:**
- Microphone button with visual feedback
- Hotkey support (hold Space to talk)
- State indicators: idle, listening, processing, speaking
- Pulsing animation while recording
- Browser permission handling
- Transcript display

**Props:**
```javascript
{
  onCommand: function,     // Callback when command is recognized
  hotkey: string          // Hotkey to activate (default: ' ')
}
```

**Usage:**
```jsx
<VoiceControls 
  onCommand={(result) => handleCommand(result)}
  hotkey=" "
/>
```

---

### 3. ExplainButton.jsx

**Purpose:** Reusable inline "Explain" button for contextual help.

**Features:**
- Modal popup with detailed explanations
- Type-specific rendering (config, error, log)
- Loading states
- Styled explanations with recommendations
- Severity indicators

**Props:**
```javascript
{
  type: 'config' | 'log' | 'error' | 'scan_result',
  content: string,
  context: object,
  size: 'small' | 'medium' | 'large',
  style: object
}
```

**Usage:**
```jsx
<ExplainButton 
  type="config"
  content="timeout"
  context={{ current_value: 30 }}
/>

<ExplainButton 
  type="error"
  content="Connection refused"
/>
```

---

### 4. GuidedWizard.jsx

**Purpose:** Multi-step wizard for onboarding and operations.

**Features:**
- Progress indicator
- Field validation
- Help text for each step
- Multiple wizard types (create_operation, run_scan, first_time_setup)
- Review step before completion

**Props:**
```javascript
{
  wizardType: string,      // Type of wizard
  onComplete: function,    // Callback when wizard completes
  onCancel: function,      // Callback when wizard is cancelled
  initialData: object      // Pre-fill data
}
```

**Usage:**
```jsx
<GuidedWizard
  wizardType="run_scan"
  onComplete={(data) => startScan(data)}
  onCancel={() => closeWizard()}
/>
```

**Wizard Types:**
- `create_operation` - Create new security assessment operation
- `run_scan` - Configure and run a security scan
- `first_time_setup` - Initial setup wizard
- `onboard_agent` - Agent onboarding (can be added)

---

### 5. HelpChat.jsx

**Purpose:** Persistent side-panel chat with LLM assistance.

**Features:**
- Context-aware help
- Conversation history
- Code block rendering with copy button
- Quick action buttons
- Collapsible sidebar
- Markdown-like formatting

**Props:**
```javascript
{
  isOpen: boolean,
  onClose: function,
  currentPage: string,
  context: object
}
```

**Usage:**
```jsx
<HelpChat
  isOpen={showHelp}
  onClose={() => setShowHelp(false)}
  currentPage="dashboard"
  context={{ current_scan: scanId }}
/>
```

---

## API Endpoints

### Nmap Parsing

```
POST /api/nmap/parse
Body: { format: "xml"|"json", content: "..." }
Returns: { hosts: [...], count: number }

GET /api/nmap/hosts?scan_id=...
Returns: { hosts: [...] }
```

### Voice Control

```
POST /api/voice/transcribe
Body: FormData with audio file
Returns: { text: string, language: string, method: string }

POST /api/voice/speak
Body: { text: string, voice_name: string }
Returns: Audio MP3 stream

POST /api/voice/command
Body: { text: string }
Returns: { command: {...}, routing: {...}, speak_response: string }
```

### Explanations

```
POST /api/explain
Body: { type: string, content: string, context: {...} }
Returns: Type-specific explanation object

GET /api/wizard/help?type=...&step=...
Returns: { title, description, tips, example }
```

### LLM Help

```
POST /api/llm/chat
Body: { message: string, session_id?: string, context?: string }
Returns: { message: string, success: boolean }

GET /api/llm/autocomplete?partial_text=...&context_type=...
Returns: { suggestions: [...] }

POST /api/llm/explain
Body: { item: string, item_type?: string, context?: {...} }
Returns: { explanation: string, item_type: string }
```

### Config Validation

```
POST /api/config/validate
Body: { config_data: {...}, config_type: string }
Returns: { valid: boolean, warnings: [...], errors: [...], suggestions: [...] }

POST /api/config/backup
Body: { config_name: string, config_data: {...}, description?: string }
Returns: { backup_id: string, timestamp: string }

POST /api/config/restore
Body: { backup_id: string }
Returns: { success: boolean, config_data: {...} }

GET /api/config/backups?config_name=...
Returns: { backups: [...], count: number }

POST /api/config/autofix
Body: { validation_result: {...}, config_data: {...} }
Returns: { has_fixes: boolean, fixes_applied: [...], fixed_config: {...} }
```

### Webhooks & Alerts

```
POST /api/webhook/n8n
Body: { ...workflow data... }
Returns: { status: string, message: string }

POST /api/alerts/push
Body: { title: string, message: string, severity: string }
Returns: { status: string }
```

---

## Setup & Configuration

### Environment Variables

```bash
# Required for OpenAI features (optional if using local alternatives)
export OPENAI_API_KEY=sk-...

# Required for Anthropic Claude (optional)
export ANTHROPIC_API_KEY=...

# Optional: Whisper model size (tiny, base, small, medium, large)
export WHISPER_MODEL=base

# Optional: Config backup directory
export CONFIG_BACKUP_DIR=/workspace/config_backups

# Service URLs (already configured in docker-compose.yml)
export LLM_ROUTER_URL=http://strikepackage-llm-router:8000
export KALI_EXECUTOR_URL=http://strikepackage-kali-executor:8002
```

### Optional Dependencies

For full voice control functionality:

```bash
# In hackgpt-api service
pip install openai-whisper  # For local speech-to-text
pip install TTS             # For local text-to-speech (Coqui)
```

For React components (requires React build setup):

```bash
# In dashboard directory (if React is set up)
npm install cytoscape       # For network visualization
npm install react react-dom # If not already installed
```

---

## Usage Examples

### Example 1: Parse Nmap Scan Results

```bash
# Run nmap scan with XML output
nmap -oX scan.xml -sV 192.168.1.0/24

# Parse via API
curl -X POST http://localhost:8001/api/nmap/parse \
  -H "Content-Type: application/json" \
  -d "{\"format\": \"xml\", \"content\": \"$(cat scan.xml)\"}"
```

### Example 2: Voice Command Workflow

1. User holds Space key and says: "Scan 192.168.1.100"
2. Audio is captured and sent to `/api/voice/transcribe`
3. Transcribed text is sent to `/api/voice/command`
4. System parses command and returns routing info
5. Frontend executes the appropriate action (start scan)
6. Result is spoken back via `/api/voice/speak`

### Example 3: Configuration Validation

```python
# Validate scan configuration
config = {
    "target": "192.168.1.0/24",
    "timeout": 300,
    "scan_type": "full",
    "intensity": 3
}

response = requests.post('http://localhost:8001/api/config/validate', json={
    "config_data": config,
    "config_type": "scan"
})

result = response.json()
if result['valid']:
    # Backup before applying
    backup_response = requests.post('http://localhost:8001/api/config/backup', json={
        "config_name": "scan_config",
        "config_data": config,
        "description": "Before production scan"
    })
    
    # Apply configuration
    apply_config(config)
else:
    print("Errors:", result['errors'])
    print("Warnings:", result['warnings'])
```

### Example 4: LLM Chat Help

```javascript
// Frontend usage
const response = await fetch('/api/llm/chat', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    message: "How do I scan for SQL injection vulnerabilities?",
    session_id: "user-session-123",
    context: "User is on scan configuration page"
  })
});

const data = await response.json();
console.log(data.message);  // LLM's helpful response
```

---

## Integration Guide

### Integrating Network Map

1. Add Cytoscape.js to your project:
   ```bash
   npm install cytoscape
   ```

2. Import and use the NetworkMap component:
   ```jsx
   import NetworkMap from './NetworkMap';
   
   function Dashboard() {
     return (
       <NetworkMap 
         scanId={currentScanId}
         onNodeClick={(host) => showHostDetails(host)}
       />
     );
   }
   ```

3. Ensure your API provides host data at `/api/nmap/hosts`

### Integrating Voice Controls

1. Add VoiceControls as a floating component:
   ```jsx
   import VoiceControls from './VoiceControls';
   
   function App() {
     return (
       <>
         {/* Your app content */}
         <VoiceControls onCommand={handleVoiceCommand} />
       </>
     );
   }
   ```

2. Handle voice commands:
   ```javascript
   function handleVoiceCommand(result) {
     const { routing } = result;
     
     if (routing.action === 'api_call') {
       // Execute API call
       fetch(routing.endpoint, {
         method: routing.method,
         body: JSON.stringify(routing.data)
       });
     } else if (routing.action === 'navigate') {
       // Navigate to page
       navigate(routing.endpoint);
     }
   }
   ```

### Integrating Explain Buttons

Add ExplainButton next to any configuration field, log entry, or error message:

```jsx
import ExplainButton from './ExplainButton';

function ConfigField({ name, value }) {
  return (
    <div>
      <label>{name}: {value}</label>
      <ExplainButton 
        type="config"
        content={name}
        context={{ current_value: value }}
        size="small"
      />
    </div>
  );
}
```

### Integrating Help Chat

1. Add state to control visibility:
   ```javascript
   const [showHelp, setShowHelp] = useState(false);
   ```

2. Add button to open chat:
   ```jsx
   <button onClick={() => setShowHelp(true)}>
     Get Help
   </button>
   ```

3. Include HelpChat component:
   ```jsx
   <HelpChat
     isOpen={showHelp}
     onClose={() => setShowHelp(false)}
     currentPage={currentPage}
     context={{ operation_id: currentOperation }}
   />
   ```

### Integrating Guided Wizard

Use for first-time setup or complex operations:

```jsx
function FirstTimeSetup() {
  const [showWizard, setShowWizard] = useState(true);
  
  return showWizard && (
    <GuidedWizard
      wizardType="first_time_setup"
      onComplete={(data) => {
        saveSettings(data);
        setShowWizard(false);
      }}
      onCancel={() => setShowWizard(false)}
    />
  );
}
```

---

## Feature Integration Flow

```
┌─────────────────────────────────────────────────────────────┐
│                     User Interface                          │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐  │
│  │ Network  │  │  Voice   │  │  Help    │  │  Wizard  │  │
│  │   Map    │  │ Controls │  │  Chat    │  │          │  │
│  └────┬─────┘  └────┬─────┘  └────┬─────┘  └────┬─────┘  │
└───────┼─────────────┼─────────────┼─────────────┼─────────┘
        │             │             │             │
        ▼             ▼             ▼             ▼
┌─────────────────────────────────────────────────────────────┐
│                    API Endpoints                            │
│  /api/nmap/*   /api/voice/*   /api/llm/*   /api/wizard/*  │
└───────┬───────────────┬───────────────┬───────────┬─────────┘
        │               │               │           │
        ▼               ▼               ▼           ▼
┌─────────────────────────────────────────────────────────────┐
│                   Backend Modules                           │
│  nmap_parser   voice   llm_help   explain   config_validator│
└───────┬───────────────┬───────────────┬───────────┬─────────┘
        │               │               │           │
        ▼               ▼               ▼           ▼
┌─────────────────────────────────────────────────────────────┐
│              External Services / Storage                    │
│  Whisper    OpenAI API    LLM Router    File System        │
└─────────────────────────────────────────────────────────────┘
```

---

## Testing the Features

### Test Nmap Parser

```bash
curl -X POST http://localhost:8001/api/nmap/parse \
  -H "Content-Type: application/json" \
  -d '{"format": "xml", "content": "<?xml version=\"1.0\"?>..."}'
```

### Test Voice Transcription

```bash
curl -X POST http://localhost:8001/api/voice/transcribe \
  -F "audio=@recording.wav"
```

### Test Explain Feature

```bash
curl -X POST http://localhost:8001/api/explain \
  -H "Content-Type: application/json" \
  -d '{"type": "error", "content": "Connection refused"}'
```

### Test Config Validation

```bash
curl -X POST http://localhost:8001/api/config/validate \
  -H "Content-Type: application/json" \
  -d '{"config_data": {"timeout": 5}, "config_type": "scan"}'
```

---

## Troubleshooting

### Voice Control Not Working

1. Check microphone permissions in browser
2. Verify Whisper or OpenAI API key is configured
3. Check browser console for errors
4. Test with: `curl -X POST http://localhost:8001/api/voice/transcribe`

### Network Map Not Displaying

1. Ensure Cytoscape.js is installed
2. Check that scan data is available at `/api/nmap/hosts`
3. Verify SVG icons are accessible at `/static/*.svg`
4. Check browser console for errors

### LLM Help Not Responding

1. Verify LLM Router service is running
2. Check LLM_ROUTER_URL environment variable
3. Ensure Ollama or API keys are configured
4. Test with: `curl http://localhost:8000/health`

### Config Backups Not Saving

1. Check CONFIG_BACKUP_DIR is writable
2. Verify directory exists: `mkdir -p /workspace/config_backups`
3. Check disk space: `df -h`

---

## Future Enhancements

Potential additions for future versions:

1. **Advanced Network Visualization**
   - 3D network topology
   - Attack path highlighting
   - Real-time update animations

2. **Voice Control**
   - Multi-language support
   - Custom wake word
   - Voice profiles for different users

3. **LLM Help**
   - RAG (Retrieval-Augmented Generation) for documentation
   - Fine-tuned models for security domain
   - Collaborative learning from user interactions

4. **Config Management**
   - Config diff visualization
   - Scheduled backups
   - Config templates library

5. **Workflow Integration**
   - JIRA integration
   - Slack/Discord notifications
   - Email reporting
   - SOAR platform integration

---

## Support & Contributing

For issues or feature requests, please visit the GitHub repository.

For questions about implementation, consult the inline code documentation or use the built-in Help Chat feature! 😊

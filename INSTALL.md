# Installation Guide - StrikePackageGPT New Features

This guide walks you through installing and setting up the new features added to StrikePackageGPT.

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Quick Start (Minimal Setup)](#quick-start-minimal-setup)
3. [Full Installation (All Features)](#full-installation-all-features)
4. [Optional Features Setup](#optional-features-setup)
5. [Verification & Testing](#verification--testing)
6. [Troubleshooting](#troubleshooting)

---

## Prerequisites

### Required
- **Docker & Docker Compose** - Already installed if you're using StrikePackageGPT
- **Python 3.12+** - Included in the containers
- **16GB+ RAM** - Recommended for running services + full Kali tools (8GB minimum)
- **20GB+ Disk Space** - For complete Kali Linux tool suite (kali-linux-everything)

### Optional (for enhanced features)
- **Node.js & npm** - Only if you want to build React components from source
- **NVIDIA GPU** - For faster local Whisper transcription
- **OpenAI API Key** - For cloud-based voice and LLM features
- **Anthropic API Key** - For Claude LLM support
- **Physical WiFi Adapter** - For wireless penetration testing (requires USB passthrough)

---

## Quick Start (Minimal Setup)

This gets you running with **all backend features** and **basic frontend** (no build system required).

### Step 1: Start the Services

```bash
cd /path/to/StrikePackageGPT
docker-compose up -d --build
```

This starts all services including the new API endpoints.

**Note:** First-time build will take 20-30 minutes as it installs the complete Kali Linux tool suite (600+ tools, ~10GB download). Subsequent starts are instant.

### Step 2: Verify Installation

```bash
# Check if services are running
docker-compose ps

# Test the new API endpoints
curl http://localhost:8001/health

# Test nmap parser endpoint
curl -X POST http://localhost:8001/api/nmap/parse \
  -H "Content-Type: application/json" \
  -d '{"format": "xml", "content": "<?xml version=\"1.0\"?><nmaprun></nmaprun>"}'
```

### Step 3: View the Icons

The new SVG icons are already accessible:

```bash
# Open in browser
http://localhost:8080/static/windows.svg
http://localhost:8080/static/linux.svg
http://localhost:8080/static/mac.svg
http://localhost:8080/static/server.svg
http://localhost:8080/static/workstation.svg
http://localhost:8080/static/network.svg
http://localhost:8080/static/unknown.svg
```

### Step 4: Access the Dashboard

```bash
# Open the dashboard
http://localhost:8080
```

### Step 5: Access All Kali Tools

The Kali container now includes **ALL 600+ Kali Linux tools** via the `kali-linux-everything` metapackage:

```bash
# Access the Kali container
docker exec -it strikepackage-kali bash

# Available tools include:
# - Reconnaissance: nmap, masscan, recon-ng, maltego, amass
# - Web Testing: burpsuite, zaproxy, sqlmap, nikto, wpscan
# - Wireless: aircrack-ng, wifite, reaver, kismet
# - Password Attacks: john, hashcat, hydra, medusa
# - Exploitation: metasploit, searchsploit, armitage
# - Post-Exploitation: mimikatz, bloodhound, crackmapexec
# - Forensics: autopsy, volatility, sleuthkit
# - Reverse Engineering: ghidra, radare2, gdb
# - And 500+ more tools!

# Example: Run aircrack-ng
aircrack-ng --help

# Example: Use wifite
wifite --help
```

**That's it for basic setup!** All backend features and 600+ Kali tools are now available.

---

## Full Installation (All Features)

This enables **React components** and **voice control** with all optional features.

### Step 1: Backend Setup

The backend is already installed and running from the Quick Start. No additional steps needed!

### Step 2: Optional - Install Voice Control Dependencies

For **local Whisper** (speech-to-text without API):

```bash
# SSH into the hackgpt-api container
docker exec -it strikepackage-hackgpt-api bash

# Install Whisper (inside container)
pip install openai-whisper

# Exit container
exit
```

For **local Coqui TTS** (text-to-speech without API):

```bash
# SSH into the hackgpt-api container
docker exec -it strikepackage-hackgpt-api bash

# Install Coqui TTS (inside container)
pip install TTS

# Exit container
exit
```

**Note:** These are optional. The system will use OpenAI API as fallback if these aren't installed.

### Step 3: Configure API Keys (Optional)

If you want to use cloud-based LLM and voice features:

```bash
# Edit the .env file
nano .env

# Add these lines:
OPENAI_API_KEY=sk-your-key-here
ANTHROPIC_API_KEY=your-anthropic-key-here

# Save and restart services
docker-compose restart
```

### Step 4: Frontend Integration (Choose One Option)

#### Option A: Use Vanilla JavaScript (No Build Required) ✅ Recommended for Quick Setup

This integrates the features using plain JavaScript without React build system.

1. **Copy the integration code:**

```bash
# Create the integration file
cat > services/dashboard/static/js/strikepackage-features.js << 'EOF'
// Voice Control Integration
class VoiceController {
  constructor() {
    this.isListening = false;
    this.setupButton();
  }

  setupButton() {
    const button = document.createElement('button');
    button.id = 'voice-button';
    button.innerHTML = '🎙️';
    button.style.cssText = `
      position: fixed;
      bottom: 20px;
      right: 20px;
      width: 60px;
      height: 60px;
      border-radius: 50%;
      border: none;
      background: #3498DB;
      color: white;
      font-size: 24px;
      cursor: pointer;
      box-shadow: 0 4px 12px rgba(0,0,0,0.2);
      z-index: 1000;
    `;
    button.onclick = () => this.toggleListening();
    document.body.appendChild(button);
  }

  async toggleListening() {
    if (!this.isListening) {
      await this.startListening();
    } else {
      this.stopListening();
    }
  }

  async startListening() {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.mediaRecorder = new MediaRecorder(stream);
    const chunks = [];

    this.mediaRecorder.ondataavailable = (e) => chunks.push(e.data);
    this.mediaRecorder.onstop = async () => {
      const blob = new Blob(chunks, { type: 'audio/webm' });
      await this.processAudio(blob);
      stream.getTracks().forEach(track => track.stop());
    };

    this.mediaRecorder.start();
    this.isListening = true;
    document.getElementById('voice-button').innerHTML = '⏸️';
  }

  stopListening() {
    if (this.mediaRecorder) {
      this.mediaRecorder.stop();
      this.isListening = false;
      document.getElementById('voice-button').innerHTML = '🎙️';
    }
  }

  async processAudio(blob) {
    const formData = new FormData();
    formData.append('audio', blob);

    const response = await fetch('/api/voice/transcribe', {
      method: 'POST',
      body: formData
    });

    const result = await response.json();
    console.log('Transcribed:', result.text);
    alert('You said: ' + result.text);
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  window.voiceController = new VoiceController();
});
EOF
```

2. **Update the dashboard template:**

```bash
# Edit the main template
nano services/dashboard/templates/index.html

# Add before </body>:
# <script src="/static/js/strikepackage-features.js"></script>
```

3. **Restart the dashboard:**

```bash
docker-compose restart dashboard
```

#### Option B: Build React Components (Full Featured)

This requires Node.js and npm to build the React components.

1. **Install Node.js dependencies:**

```bash
cd services/dashboard

# Initialize npm if not already done
npm init -y

# Install React and build tools
npm install react react-dom
npm install --save-dev @babel/core @babel/preset-react webpack webpack-cli babel-loader css-loader style-loader

# Install Cytoscape for NetworkMap
npm install cytoscape
```

2. **Create webpack configuration:**

```bash
cat > webpack.config.js << 'EOF'
const path = require('path');

module.exports = {
  entry: './src/index.jsx',
  output: {
    path: path.resolve(__dirname, 'static/dist'),
    filename: 'bundle.js'
  },
  module: {
    rules: [
      {
        test: /\.jsx?$/,
        exclude: /node_modules/,
        use: {
          loader: 'babel-loader',
          options: {
            presets: ['@babel/preset-react']
          }
        }
      }
    ]
  },
  resolve: {
    extensions: ['.js', '.jsx']
  }
};
EOF
```

3. **Create the React entry point:**

```bash
mkdir -p src

cat > src/index.jsx << 'EOF'
import React from 'react';
import ReactDOM from 'react-dom';
import VoiceControls from '../VoiceControls';
import HelpChat from '../HelpChat';

function App() {
  const [showHelp, setShowHelp] = React.useState(false);

  return (
    <>
      <VoiceControls onCommand={(cmd) => console.log(cmd)} />
      <button 
        onClick={() => setShowHelp(!showHelp)}
        style={{position: 'fixed', top: '20px', right: '20px', zIndex: 1000}}
      >
        💬 Help
      </button>
      <HelpChat 
        isOpen={showHelp}
        onClose={() => setShowHelp(false)}
        currentPage="dashboard"
      />
    </>
  );
}

ReactDOM.render(<App />, document.getElementById('root'));
EOF
```

4. **Build the bundle:**

```bash
# Add to package.json scripts
npm set-script build "webpack --mode production"

# Build
npm run build
```

5. **Update HTML template:**

```bash
# services/dashboard/templates/index.html should include:
# <div id="root"></div>
# <script src="/static/dist/bundle.js"></script>
```

---

## Optional Features Setup

### 1. Enable GPU Acceleration for Whisper

If you have an NVIDIA GPU:

```bash
# Edit docker-compose.yml
nano docker-compose.yml

# Add to hackgpt-api service:
#   deploy:
#     resources:
#       reservations:
#         devices:
#           - driver: nvidia
#             count: all
#             capabilities: [gpu]

# Restart
docker-compose up -d --build hackgpt-api
```

### 2. Configure n8n Webhook Integration

```bash
# The webhook endpoint is already available at:
# POST http://localhost:8001/api/webhook/n8n

# In n8n, create a webhook node pointing to:
# http://strikepackage-hackgpt-api:8001/api/webhook/n8n
```

### 3. Set Up Config Backups Directory

```bash
# Create backup directory
docker exec -it strikepackage-hackgpt-api mkdir -p /workspace/config_backups

# Or set custom location via environment variable
echo "CONFIG_BACKUP_DIR=/custom/path" >> .env
docker-compose restart
```

---

## Verification & Testing

### Test Backend Features

```bash
# 1. Test Nmap Parser
curl -X POST http://localhost:8001/api/nmap/parse \
  -H "Content-Type: application/json" \
  -d '{"format": "xml", "content": "<?xml version=\"1.0\"?><nmaprun><host><status state=\"up\"/><address addr=\"192.168.1.1\" addrtype=\"ipv4\"/></host></nmaprun>"}'

# 2. Test Explanation API
curl -X POST http://localhost:8001/api/explain \
  -H "Content-Type: application/json" \
  -d '{"type": "error", "content": "Connection refused"}'

# 3. Test Config Validation
curl -X POST http://localhost:8001/api/config/validate \
  -H "Content-Type: application/json" \
  -d '{"config_data": {"timeout": 30}, "config_type": "scan"}'

# 4. Test LLM Chat (requires LLM service running)
curl -X POST http://localhost:8001/api/llm/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "How do I scan a network?"}'
```

### Test Voice Control (Browser Required)

1. Open: http://localhost:8080
2. Click the microphone button (🎙️) in bottom-right corner
3. Allow microphone permissions
4. Speak a command: "scan 192.168.1.1"
5. Check browser console for transcription result

### Test Icons

Open each icon URL in your browser:
- http://localhost:8080/static/windows.svg
- http://localhost:8080/static/linux.svg
- http://localhost:8080/static/mac.svg
- http://localhost:8080/static/server.svg
- http://localhost:8080/static/workstation.svg
- http://localhost:8080/static/network.svg
- http://localhost:8080/static/unknown.svg

### Run a Complete Test Workflow

```bash
# 1. Run an nmap scan
nmap -oX scan.xml -sV 192.168.1.0/24

# 2. Parse the results
curl -X POST http://localhost:8001/api/nmap/parse \
  -H "Content-Type: application/json" \
  -d "{\"format\": \"xml\", \"content\": \"$(cat scan.xml | sed 's/"/\\"/g')\"}"

# 3. The response will show all discovered hosts with OS/device classification
```

---

## Troubleshooting

### Issue: Voice transcription not working

**Solution:**
```bash
# Check if Whisper is installed
docker exec -it strikepackage-hackgpt-api pip list | grep whisper

# If not, install it
docker exec -it strikepackage-hackgpt-api pip install openai-whisper

# Or configure OpenAI API key as fallback
echo "OPENAI_API_KEY=sk-your-key" >> .env
docker-compose restart
```

### Issue: "Module not found" errors

**Solution:**
```bash
# Rebuild the services
docker-compose down
docker-compose up -d --build
```

### Issue: Icons not showing

**Solution:**
```bash
# Verify icons exist
ls -la services/dashboard/static/*.svg

# Check permissions
docker exec -it strikepackage-dashboard ls -la /app/static/*.svg

# Restart dashboard
docker-compose restart dashboard
```

### Issue: LLM chat not responding

**Solution:**
```bash
# Check LLM router is running
docker-compose ps | grep llm-router

# Test LLM router directly
curl http://localhost:8000/health

# Check Ollama or API keys are configured
docker exec -it strikepackage-llm-router env | grep API_KEY
```

### Issue: Config backups not saving

**Solution:**
```bash
# Create the backup directory
docker exec -it strikepackage-hackgpt-api mkdir -p /workspace/config_backups

# Check permissions
docker exec -it strikepackage-hackgpt-api ls -la /workspace

# Test backup endpoint
curl -X POST http://localhost:8001/api/config/backup \
  -H "Content-Type: application/json" \
  -d '{"config_name": "test", "config_data": {"test": "value"}}'
```

### Issue: React components not loading

**Solution:**
```bash
# If using Option B (React build):

cd services/dashboard

# Install dependencies
npm install

# Build
npm run build

# Check if bundle exists
ls -la static/dist/bundle.js

# Restart dashboard
docker-compose restart dashboard
```

### Issue: Permission denied for microphone

**Solution:**
- Voice control requires HTTPS in production
- For local testing, ensure you're accessing via `localhost` (not IP address)
- Click the lock icon in browser and enable microphone permissions

---

## Summary

### Minimum Installation (Backend Only)
```bash
docker-compose up -d
# All API endpoints work immediately!
```

### Recommended Installation (Backend + Simple Frontend)
```bash
docker-compose up -d
# Add the vanilla JS integration script to templates
# Voice control and help features work in browser
```

### Full Installation (Everything)
```bash
docker-compose up -d
docker exec -it strikepackage-hackgpt-api pip install openai-whisper TTS
cd services/dashboard && npm install && npm run build
# All features including React components
```

---

## What's Installed?

After installation, you have access to:

✅ **22 new API endpoints** for nmap, voice, explanations, LLM help, config validation  
✅ **5 backend Python modules** with comprehensive functionality  
✅ **5 React component templates** ready for integration  
✅ **7 professional SVG icons** for device/OS visualization  
✅ **Voice control** (with optional local Whisper or cloud API)  
✅ **Network mapping** (nmap parser ready for visualization)  
✅ **LLM help system** (chat, autocomplete, explanations)  
✅ **Config management** (validation, backup, restore)  
✅ **Webhook integration** (n8n, alerts)  

---

## Next Steps

1. **Review the documentation:**
   - `FEATURES.md` - Complete feature reference
   - `INTEGRATION_EXAMPLE.md` - Detailed integration examples
   - `IMPLEMENTATION_SUMMARY.md` - Overview and statistics

2. **Test the features:**
   - Try the API endpoints with curl
   - Test voice control in browser
   - Run an nmap scan and parse results

3. **Customize:**
   - Add your own voice commands in `voice.py`
   - Customize wizard steps in `explain.py`
   - Integrate React components into your UI

4. **Deploy:**
   - Configure production API keys
   - Enable HTTPS for voice features
   - Set up backup directory with proper permissions

---

For questions or issues, refer to the troubleshooting section or check the comprehensive documentation in `FEATURES.md`.

Happy scanning! 🎯

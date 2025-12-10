# Integration Example - Adding New Features to Dashboard

This guide shows how to integrate the new React components into the existing StrikePackageGPT dashboard.

## Current Architecture

StrikePackageGPT currently uses:
- **Backend**: FastAPI (Python)
- **Frontend**: HTML templates with Jinja2 (no React build system yet)
- **Static files**: Served from `services/dashboard/static/`

## Integration Options

### Option 1: Add React Build System (Recommended for Production)

This approach sets up a proper React application:

1. **Create React App Structure**

```bash
cd services/dashboard
npm init -y
npm install react react-dom
npm install --save-dev @babel/core @babel/preset-react webpack webpack-cli babel-loader css-loader style-loader
npm install cytoscape  # For NetworkMap
```

2. **Create webpack.config.js**

```javascript
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
      },
      {
        test: /\.css$/,
        use: ['style-loader', 'css-loader']
      }
    ]
  },
  resolve: {
    extensions: ['.js', '.jsx']
  }
};
```

3. **Create src/index.jsx**

```jsx
import React from 'react';
import ReactDOM from 'react-dom';
import App from './App';

ReactDOM.render(<App />, document.getElementById('root'));
```

4. **Create src/App.jsx**

```jsx
import React, { useState } from 'react';
import NetworkMap from '../NetworkMap';
import VoiceControls from '../VoiceControls';
import HelpChat from '../HelpChat';
import GuidedWizard from '../GuidedWizard';

function App() {
  const [showHelp, setShowHelp] = useState(false);
  const [showWizard, setShowWizard] = useState(false);
  const [currentScanId, setCurrentScanId] = useState(null);

  return (
    <div className="app">
      <header>
        <h1>StrikePackageGPT Dashboard</h1>
        <button onClick={() => setShowHelp(!showHelp)}>
          💬 Help
        </button>
      </header>

      <main>
        {currentScanId && (
          <NetworkMap 
            scanId={currentScanId}
            onNodeClick={(host) => console.log('Host clicked:', host)}
          />
        )}
      </main>

      {/* Floating components */}
      <VoiceControls onCommand={handleVoiceCommand} />
      
      <HelpChat
        isOpen={showHelp}
        onClose={() => setShowHelp(false)}
        currentPage="dashboard"
      />

      {showWizard && (
        <GuidedWizard
          wizardType="first_time_setup"
          onComplete={(data) => {
            console.log('Wizard completed:', data);
            setShowWizard(false);
          }}
          onCancel={() => setShowWizard(false)}
        />
      )}
    </div>
  );
}

function handleVoiceCommand(result) {
  console.log('Voice command:', result);
  // Handle voice commands
}

export default App;
```

5. **Update package.json scripts**

```json
{
  "scripts": {
    "build": "webpack --mode production",
    "dev": "webpack --mode development --watch"
  }
}
```

6. **Build and Deploy**

```bash
npm run build
```

7. **Update templates/index.html**

```html
<!DOCTYPE html>
<html>
<head>
    <title>StrikePackageGPT</title>
</head>
<body>
    <div id="root"></div>
    <script src="/static/dist/bundle.js"></script>
</body>
</html>
```

---

### Option 2: Use Components via CDN (Quick Start)

For quick testing without build system:

1. **Create static/js/components.js**

```javascript
// Load React and ReactDOM from CDN
// Then include the component code

// Example: Simple integration
function initStrikePackageGPT() {
  // Initialize voice controls
  const voiceContainer = document.createElement('div');
  voiceContainer.id = 'voice-controls';
  document.body.appendChild(voiceContainer);
  
  // Initialize help chat button
  const helpButton = document.createElement('button');
  helpButton.textContent = '💬 Help';
  helpButton.onclick = () => toggleHelpChat();
  document.body.appendChild(helpButton);
}

document.addEventListener('DOMContentLoaded', initStrikePackageGPT);
```

2. **Update templates/index.html**

```html
<!DOCTYPE html>
<html>
<head>
    <title>StrikePackageGPT</title>
    <script crossorigin src="https://unpkg.com/react@18/umd/react.production.min.js"></script>
    <script crossorigin src="https://unpkg.com/react-dom@18/umd/react-dom.production.min.js"></script>
    <script src="https://unpkg.com/@babel/standalone/babel.min.js"></script>
</head>
<body>
    <div id="root"></div>
    
    <!-- Include components -->
    <script type="text/babel" src="/static/js/components.js"></script>
</body>
</html>
```

---

### Option 3: Progressive Enhancement (Current Setup Compatible)

Use the new features as API endpoints with vanilla JavaScript:

1. **Create static/js/app.js**

```javascript
// Voice Control Integration
class VoiceController {
  constructor() {
    this.isListening = false;
    this.mediaRecorder = null;
    this.setupButton();
  }

  setupButton() {
    const button = document.createElement('button');
    button.id = 'voice-button';
    button.innerHTML = '🎙️';
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
    
    // Route command
    const cmdResponse = await fetch('/api/voice/command', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ text: result.text })
    });
    
    const command = await cmdResponse.json();
    this.executeCommand(command);
  }

  executeCommand(command) {
    // Execute the command based on routing info
    console.log('Command:', command);
  }
}

// Help Chat Integration
class HelpChat {
  constructor() {
    this.isOpen = false;
    this.messages = [];
    this.sessionId = `session-${Date.now()}`;
    this.setupUI();
  }

  setupUI() {
    const container = document.createElement('div');
    container.id = 'help-chat';
    container.style.display = 'none';
    document.body.appendChild(container);

    const button = document.createElement('button');
    button.id = 'help-button';
    button.innerHTML = '💬';
    button.onclick = () => this.toggle();
    document.body.appendChild(button);
  }

  toggle() {
    this.isOpen = !this.isOpen;
    const chat = document.getElementById('help-chat');
    chat.style.display = this.isOpen ? 'block' : 'none';
    
    if (this.isOpen && this.messages.length === 0) {
      this.addMessage('assistant', 'Hi! How can I help you?');
    }
  }

  async sendMessage(text) {
    this.addMessage('user', text);

    const response = await fetch('/api/llm/chat', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message: text,
        session_id: this.sessionId
      })
    });

    const result = await response.json();
    this.addMessage('assistant', result.message);
  }

  addMessage(role, content) {
    this.messages.push({ role, content });
    this.render();
  }

  render() {
    const chat = document.getElementById('help-chat');
    chat.innerHTML = this.messages.map(msg => `
      <div class="message ${msg.role}">
        ${msg.content}
      </div>
    `).join('');
  }
}

// Network Map Integration
class NetworkMapViewer {
  constructor(containerId) {
    this.container = document.getElementById(containerId);
    this.hosts = [];
  }

  async loadScan(scanId) {
    const response = await fetch(`/api/nmap/hosts?scan_id=${scanId}`);
    const data = await response.json();
    this.hosts = data.hosts || [];
    this.render();
  }

  render() {
    this.container.innerHTML = `
      <div class="network-map">
        <div class="toolbar">
          <input type="text" id="filter" placeholder="Filter..." />
          <button onclick="networkMap.exportCSV()">Export CSV</button>
        </div>
        <div class="hosts">
          ${this.hosts.map(host => this.renderHost(host)).join('')}
        </div>
      </div>
    `;
  }

  renderHost(host) {
    const iconUrl = `/static/${this.getIcon(host)}.svg`;
    return `
      <div class="host" onclick="networkMap.showHostDetails('${host.ip}')">
        <img src="${iconUrl}" alt="${host.os_type}" />
        <div class="host-info">
          <strong>${host.ip}</strong>
          <div>${host.hostname || 'Unknown'}</div>
          <div>${host.os_type || 'Unknown OS'}</div>
        </div>
      </div>
    `;
  }

  getIcon(host) {
    const osType = (host.os_type || '').toLowerCase();
    if (osType.includes('windows')) return 'windows';
    if (osType.includes('linux')) return 'linux';
    if (osType.includes('mac')) return 'mac';
    if (host.device_type?.includes('server')) return 'server';
    if (host.device_type?.includes('network')) return 'network';
    return 'unknown';
  }

  exportCSV() {
    const csv = [
      ['IP', 'Hostname', 'OS', 'Device Type', 'Ports'].join(','),
      ...this.hosts.map(h => [
        h.ip,
        h.hostname || '',
        h.os_type || '',
        h.device_type || '',
        (h.ports || []).map(p => p.port).join(';')
      ].join(','))
    ].join('\n');

    const blob = new Blob([csv], { type: 'text/csv' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `network-${Date.now()}.csv`;
    a.click();
  }

  showHostDetails(ip) {
    const host = this.hosts.find(h => h.ip === ip);
    alert(JSON.stringify(host, null, 2));
  }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
  window.voiceController = new VoiceController();
  window.helpChat = new HelpChat();
  window.networkMap = new NetworkMapViewer('network-map-container');
});
```

2. **Add CSS (static/css/components.css)**

```css
/* Voice Button */
#voice-button {
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
}

/* Help Chat */
#help-chat {
  position: fixed;
  right: 20px;
  top: 20px;
  width: 400px;
  height: 600px;
  background: white;
  border-radius: 8px;
  box-shadow: 0 4px 20px rgba(0,0,0,0.2);
  z-index: 999;
  padding: 20px;
  overflow-y: auto;
}

#help-button {
  position: fixed;
  top: 20px;
  right: 20px;
  background: #3498DB;
  color: white;
  border: none;
  padding: 10px 20px;
  border-radius: 4px;
  cursor: pointer;
  z-index: 1001;
}

.message {
  margin: 10px 0;
  padding: 10px;
  border-radius: 8px;
}

.message.user {
  background: #3498DB;
  color: white;
  text-align: right;
}

.message.assistant {
  background: #ECF0F1;
  color: #2C3E50;
}

/* Network Map */
.network-map {
  width: 100%;
  padding: 20px;
}

.hosts {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: 15px;
  margin-top: 20px;
}

.host {
  border: 1px solid #ddd;
  border-radius: 8px;
  padding: 15px;
  cursor: pointer;
  transition: all 0.2s;
}

.host:hover {
  box-shadow: 0 4px 12px rgba(0,0,0,0.1);
  transform: translateY(-2px);
}

.host img {
  width: 48px;
  height: 48px;
}

.host-info {
  margin-top: 10px;
}
```

3. **Update templates/index.html**

```html
<!DOCTYPE html>
<html>
<head>
    <title>StrikePackageGPT</title>
    <link rel="stylesheet" href="/static/css/components.css">
</head>
<body>
    <div id="network-map-container"></div>
    
    <script src="/static/js/app.js"></script>
</body>
</html>
```

---

## Testing the Integration

### Test Voice Control
1. Open browser console
2. Click the mic button
3. Speak a command
4. Check console for transcription result

### Test Help Chat
1. Click the help button
2. Type a message
3. Wait for AI response

### Test Network Map
```javascript
// In browser console
networkMap.loadScan('your-scan-id');
```

---

## Deployment Checklist

- [ ] Choose integration method (build system vs progressive enhancement)
- [ ] Install required npm packages (if using React build)
- [ ] Configure API endpoints in backend
- [ ] Add environment variables for API keys
- [ ] Test voice control permissions
- [ ] Verify LLM service connectivity
- [ ] Test network map with real scan data
- [ ] Configure CORS if needed
- [ ] Add error handling for API failures
- [ ] Test on multiple browsers
- [ ] Document any additional setup steps

---

## Next Steps

1. Choose your integration approach
2. Set up the build system (if needed)
3. Test each component individually
4. Integrate components into main dashboard
5. Add error handling and loading states
6. Style components to match your theme
7. Deploy and test in production environment

For questions or issues, refer to FEATURES.md or use the Help Chat! 😊

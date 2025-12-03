# ⚡ StrikePackageGPT

AI-powered security analysis platform combining LLM capabilities with professional penetration testing tools.

![License](https://img.shields.io/badge/license-MIT-blue.svg)
![Python](https://img.shields.io/badge/python-3.12-blue.svg)
![Docker](https://img.shields.io/badge/docker-ready-blue.svg)

## 🎯 Overview

StrikePackageGPT provides security researchers and penetration testers with an AI assistant specialized in:

- **Reconnaissance** - OSINT, subdomain enumeration, port scanning strategies
- **Vulnerability Analysis** - CVE research, misconfiguration detection
- **Exploit Research** - Safe research and documentation of exploits
- **Report Generation** - Professional security assessment reports

## 🚀 Quick Start

### Prerequisites

- Docker & Docker Compose
- 8GB+ RAM recommended (for local LLM)
- (Optional) OpenAI or Anthropic API key

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/mblanke/StrikePackageGPT.git
   cd StrikePackageGPT
   ```

2. **Configure environment** (optional)
   ```bash
   cp .env.example .env
   # Edit .env to add API keys if using cloud LLMs
   ```

3. **Start the services**
   ```bash
   docker-compose up -d
   ```

4. **Pull a local model** (first time only)
   ```bash
   docker exec -it strikepackage-ollama ollama pull llama3.2
   ```

5. **Access the dashboard**
   
   Open http://localhost:8080 in your browser

## 📦 Services

| Service | Port | Description |
|---------|------|-------------|
| Dashboard | 8080 | Web UI with Chat, Terminal, and Scans tabs |
| HackGPT API | 8001 | Security-focused API with scan management |
| Kali Executor | 8002 | Docker SDK command execution |
| LLM Router | 8000 | Multi-provider LLM gateway |
| Ollama | 11434 | Local LLM inference |
| Kali | - | Security tools container |

## 🛠️ Security Tools

The Kali container includes **ALL Kali Linux tools** via the `kali-linux-everything` metapackage:

- **600+ Security Tools**: Complete Kali Linux arsenal
- **Reconnaissance**: nmap, masscan, amass, theHarvester, whatweb, recon-ng, maltego
- **Web Testing**: nikto, gobuster, dirb, sqlmap, burpsuite, zaproxy, wpscan
- **Exploitation**: metasploit-framework, exploit-db, searchsploit, armitage
- **Password Attacks**: hydra, john, hashcat, medusa, ncrack
- **Wireless**: aircrack-ng, wifite, reaver, bully, kismet, fern-wifi-cracker
- **Sniffing/Spoofing**: wireshark, tcpdump, ettercap, bettercap, responder
- **Post-Exploitation**: mimikatz, powersploit, empire, covenant
- **Forensics**: autopsy, volatility, sleuthkit, foremost
- **Reverse Engineering**: ghidra, radare2, gdb, ollydbg, ida-free
- **Social Engineering**: set (Social Engineering Toolkit)
- **And hundreds more...**

Access the Kali container:
```bash
docker exec -it strikepackage-kali bash
```

## 🤖 LLM Providers

StrikePackageGPT supports multiple LLM providers:

| Provider | Models | API Key Required |
|----------|--------|------------------|
| Ollama | llama3.2, codellama, mistral | No (local) |
| OpenAI | gpt-4o, gpt-4o-mini | Yes |
| Anthropic | claude-sonnet-4-20250514, claude-3-5-haiku | Yes |

## 📖 Usage Examples

### Chat with the AI
Ask security-related questions in natural language:
- "Explain how to use nmap for service detection"
- "What are common web application vulnerabilities?"
- "How do I enumerate subdomains for a target?"

### Terminal Access
Execute commands directly in the Kali container from the Terminal tab:
- Real-time command output
- Command history with up/down arrows
- Whitelisted tools for security

### Security Scans
Launch and monitor scans from the Scans tab:
- **nmap** - Port scanning and service detection
- **nikto** - Web server vulnerability scanning
- **gobuster** - Directory and DNS enumeration
- **sqlmap** - SQL injection testing
- **whatweb** - Web technology fingerprinting

### Quick Analysis
Use the sidebar buttons to start guided analysis:
- 🔍 **Reconnaissance** - Plan your information gathering
- 🛡️ **Vulnerability Scan** - Assess potential weaknesses
- 💉 **Exploit Research** - Research known vulnerabilities
- 📄 **Generate Report** - Create professional documentation

## ⚠️ Legal Disclaimer

This tool is intended for **authorized security testing only**. Always:

- Obtain written permission before testing any systems
- Follow responsible disclosure practices
- Comply with all applicable laws and regulations
- Use in isolated lab environments when learning

The developers are not responsible for misuse of this software.

## 🔧 Development

See [Claude.md](./Claude.md) for development guidelines.

```bash
# Rebuild after changes
docker-compose up -d --build

# View logs
docker-compose logs -f

# Stop all services
docker-compose down
```

## 📄 License

MIT License - See [LICENSE](./LICENSE) for details.

## 🤝 Contributing

Contributions welcome! Please read the development guidelines in Claude.md before submitting PRs.
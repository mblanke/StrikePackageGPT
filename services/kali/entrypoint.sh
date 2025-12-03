#!/bin/bash

# Enable command logging by default for all bash sessions
echo 'source /usr/local/bin/command_logger.sh' >> /root/.bashrc
echo 'export COMMAND_LOG_DIR=/workspace/.command_history' >> /root/.bashrc

# Create convenience aliases for captured execution
cat >> /root/.bashrc << 'ALIASES'
# Convenience alias to run commands with automatic capture
alias run='capture'

# Helper function to show recent commands
recent_commands() {
    echo "Recent commands logged:"
    ls -lt /workspace/.command_history/*.json 2>/dev/null | head -10 | while read line; do
        file=$(echo "$line" | awk '{print $NF}')
        [ -f "$file" ] && jq -r '"\(.timestamp) - \(.command) [\(.status)]"' "$file" 2>/dev/null
    done
}
alias recent='recent_commands'
ALIASES

echo "=================================================="
echo "  StrikePackageGPT - Kali Container"
echo "  Security Tools Ready + Command Capture Enabled"
echo "=================================================="
echo ""
echo "Available tools:"
echo "  - nmap, masscan (port scanning)"
echo "  - amass, theharvester (reconnaissance)"
echo "  - nikto, gobuster (web testing)"
echo "  - sqlmap (SQL injection)"
echo "  - hydra (brute force)"
echo "  - metasploit (exploitation)"
echo "  - searchsploit (exploit database)"
echo "  - aircrack-ng, wifite (wireless)"
echo "  - john, hashcat (password cracking)"
echo "  - and 600+ more Kali tools"
echo ""
echo "🔄 BIDIRECTIONAL CAPTURE ENABLED 🔄"
echo ""
echo "Commands you run here will be captured and visible in:"
echo "  • Dashboard history"
echo "  • API scan results"
echo "  • Network visualization"
echo ""
echo "Usage:"
echo "  • Run commands normally: nmap -sV 192.168.1.1"
echo "  • Use 'capture' prefix for explicit capture: capture nmap -sV 192.168.1.1"
echo "  • View recent: recent"
echo ""
echo "Container is ready for security testing."
echo ""

# Keep container running
exec sleep infinity
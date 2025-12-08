#!/bin/bash

# Enable command logging by default for all bash sessions
echo 'source /usr/local/bin/command_logger.sh' >> /root/.bashrc
echo 'export COMMAND_LOG_DIR=/workspace/.command_history' >> /root/.bashrc
echo 'export DASHBOARD_URL=http://strikepackage-dashboard:8080' >> /root/.bashrc

# Create convenience aliases for captured execution
cat >> /root/.bashrc << 'ALIASES'
# Convenience alias to run commands with automatic capture
alias run='capture'

# Wrap nmap to automatically send results to network map
nmap_wrapper() {
    local output
    local exit_code
    
    # Run nmap and capture output
    output=$(/usr/bin/nmap "$@" 2>&1)
    exit_code=$?
    
    # Display output
    echo "$output"
    
    # If successful, send to dashboard network map
    if [ $exit_code -eq 0 ]; then
        echo "" >&2
        echo "[StrikePackageGPT] Sending nmap results to Network Map..." >&2
        
        # Send to dashboard
        response=$(curl -s -X POST "${DASHBOARD_URL:-http://strikepackage-dashboard:8080}/api/network/nmap-results" \
            -H "Content-Type: application/json" \
            -d "$(jq -n --arg output "$output" --arg source "terminal" '{output: $output, source: $source}')" 2>/dev/null)
        
        added=$(echo "$response" | jq -r '.added // 0' 2>/dev/null)
        updated=$(echo "$response" | jq -r '.updated // 0' 2>/dev/null)
        total=$(echo "$response" | jq -r '.total // 0' 2>/dev/null)
        
        if [ "$added" != "null" ] 2>/dev/null; then
            echo "[StrikePackageGPT] Network Map: $added added, $updated updated (total: $total hosts)" >&2
        fi
    fi
    
    return $exit_code
}
alias nmap='nmap_wrapper'

# Helper function to show recent commands
recent_commands() {
    echo "Recent commands logged:"
    ls -lt /workspace/.command_history/*.json 2>/dev/null | head -10 | while read line; do
        file=$(echo "$line" | awk '{print $NF}')
        [ -f "$file" ] && jq -r '"\(.timestamp) - \(.command) [\(.status)]"' "$file" 2>/dev/null
    done
}
alias recent='recent_commands'

# Show network map hosts
show_hosts() {
    echo "Network Map Hosts:"
    curl -s "${DASHBOARD_URL:-http://strikepackage-dashboard:8080}/api/network/hosts" | jq -r '.hosts[] | "\(.ip)\t\(.hostname // "-")\t\(.os // "-")\tPorts: \(.ports | length)"' 2>/dev/null || echo "No hosts found"
}
alias hosts='show_hosts'

# Clear network map
clear_hosts() {
    curl -s -X DELETE "${DASHBOARD_URL:-http://strikepackage-dashboard:8080}/api/network/hosts" | jq .
    echo "Network map cleared"
}
ALIASES

echo "=================================================="
echo "  StrikePackageGPT - Kali Container"
echo "  Security Tools Ready + Network Map Integration"
echo "=================================================="
echo ""
echo "Available tools:"
echo "  - nmap, masscan (port scanning)"
echo "  - nikto, gobuster (web testing)"
echo "  - sqlmap (SQL injection)"
echo "  - hydra (brute force)"
echo "  - john, hashcat (password cracking)"
echo ""
echo "🗺️  NETWORK MAP INTEGRATION ENABLED 🗺️"
echo ""
echo "nmap scans automatically appear in the Dashboard Network Map!"
echo ""
echo "Commands:"
echo "  • nmap -sV 192.168.1.1    - Scan and auto-add to map"
echo "  • hosts                    - Show network map hosts"
echo "  • clear_hosts             - Clear network map"
echo "  • recent                  - Show recent commands"
echo ""
echo "Container is ready for security testing."
echo ""

# Keep container running
exec sleep infinity
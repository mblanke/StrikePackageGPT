#!/bin/bash
# Output Capture Wrapper for Security Tools
# Wraps command execution to capture stdout/stderr and save results
# Automatically sends nmap results to dashboard network map

COMMAND_LOG_DIR="${COMMAND_LOG_DIR:-/workspace/.command_history}"
DASHBOARD_URL="${DASHBOARD_URL:-http://strikepackage-dashboard:8080}"
mkdir -p "$COMMAND_LOG_DIR"

# Get command from arguments
cmd_string="$@"
[[ -z "$cmd_string" ]] && exit 1

# Generate unique ID
cmd_id=$(uuidgen 2>/dev/null || echo "$(date +%s)-$$")
timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
output_file="$COMMAND_LOG_DIR/${cmd_id}.json"
stdout_file="$COMMAND_LOG_DIR/${cmd_id}.stdout"
stderr_file="$COMMAND_LOG_DIR/${cmd_id}.stderr"

# Create initial log entry
cat > "$output_file" << EOF
{
  "command_id": "$cmd_id",
  "command": $(echo "$cmd_string" | jq -Rs .),
  "timestamp": "$timestamp",
  "user": "$(whoami)",
  "working_dir": "$(pwd)",
  "source": "capture_wrapper",
  "status": "running"
}
EOF

# Execute command and capture output
start_time=$(date +%s)
set +e
eval "$cmd_string" > "$stdout_file" 2> "$stderr_file"
exit_code=$?
set -e
end_time=$(date +%s)
duration=$((end_time - start_time))
completed_at=$(date -u +"%Y-%m-%dT%H:%M:%SZ")

# Read captured output
stdout_content=$(cat "$stdout_file" 2>/dev/null || echo "")
stderr_content=$(cat "$stderr_file" 2>/dev/null || echo "")

# Update log entry with results
cat > "$output_file" << EOF
{
  "command_id": "$cmd_id",
  "command": $(echo "$cmd_string" | jq -Rs .),
  "timestamp": "$timestamp",
  "completed_at": "$completed_at",
  "user": "$(whoami)",
  "working_dir": "$(pwd)",
  "source": "capture_wrapper",
  "status": "$([ $exit_code -eq 0 ] && echo 'completed' || echo 'failed')",
  "exit_code": $exit_code,
  "duration": $duration,
  "stdout": $(echo "$stdout_content" | jq -Rs .),
  "stderr": $(echo "$stderr_content" | jq -Rs .)
}
EOF

# Output results to terminal first
echo "$stdout_content"
[ -n "$stderr_content" ] && echo "$stderr_content" >&2

# Clean up temp files
rm -f "$stdout_file" "$stderr_file"

# If this was an nmap command, send results to dashboard network map
if [[ "$cmd_string" == nmap* ]] && [ $exit_code -eq 0 ]; then
    echo "" >&2
    echo "[StrikePackageGPT] Detected nmap scan, sending to Network Map..." >&2
    
    # Send nmap output to dashboard for parsing
    nmap_json=$(jq -n --arg output "$stdout_content" --arg source "terminal" \
        '{output: $output, source: $source}')
    
    response=$(curl -s -X POST "${DASHBOARD_URL}/api/network/nmap-results" \
        -H "Content-Type: application/json" \
        -d "$nmap_json" 2>/dev/null || echo '{"error":"failed to connect"}')
    
    # Parse response
    added=$(echo "$response" | jq -r '.added // 0' 2>/dev/null)
    updated=$(echo "$response" | jq -r '.updated // 0' 2>/dev/null)
    total=$(echo "$response" | jq -r '.total // 0' 2>/dev/null)
    
    if [ "$added" != "null" ] && [ "$added" != "0" -o "$updated" != "0" ]; then
        echo "[StrikePackageGPT] Network Map updated: $added added, $updated updated (total: $total hosts)" >&2
    fi
fi

echo "" >&2
echo "[StrikePackageGPT] Command captured: $cmd_id" >&2
echo "[StrikePackageGPT] Exit code: $exit_code | Duration: ${duration}s" >&2
echo "[StrikePackageGPT] Results available in dashboard" >&2

exit $exit_code

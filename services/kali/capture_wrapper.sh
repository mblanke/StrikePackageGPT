#!/bin/bash
# Output Capture Wrapper for Security Tools
# Wraps command execution to capture stdout/stderr and save results

COMMAND_LOG_DIR="${COMMAND_LOG_DIR:-/workspace/.command_history}"
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

# Clean up temp files
rm -f "$stdout_file" "$stderr_file"

# Output results to terminal
cat "$stdout_file" 2>/dev/null || true
cat "$stderr_file" >&2 2>/dev/null || true

echo "" >&2
echo "[StrikePackageGPT] Command captured: $cmd_id" >&2
echo "[StrikePackageGPT] Exit code: $exit_code | Duration: ${duration}s" >&2
echo "[StrikePackageGPT] Results available in dashboard" >&2

exit $exit_code

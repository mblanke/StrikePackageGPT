#!/bin/bash
# Command Logger for StrikePackageGPT
# Logs all commands executed in interactive shell sessions
# Results are captured and made available to the API

COMMAND_LOG_DIR="${COMMAND_LOG_DIR:-/workspace/.command_history}"
mkdir -p "$COMMAND_LOG_DIR"

# Function to log command execution
log_command() {
    local cmd="$1"
    local timestamp=$(date -u +"%Y-%m-%dT%H:%M:%SZ")
    local cmd_id=$(uuidgen 2>/dev/null || echo "$(date +%s)-$$")
    local output_file="$COMMAND_LOG_DIR/${cmd_id}.json"
    
    # Skip logging for cd, ls, echo, and other basic commands
    local first_word=$(echo "$cmd" | awk '{print $1}')
    case "$first_word" in
        cd|ls|pwd|echo|exit|clear|history|source|alias|\
        export|unset|env|printenv|which|type|whereis)
            return 0
            ;;
    esac
    
    # Skip empty commands
    [[ -z "$cmd" ]] && return 0
    
    # Create log entry with metadata
    cat > "$output_file" << EOF
{
  "command_id": "$cmd_id",
  "command": $(echo "$cmd" | jq -Rs .),
  "timestamp": "$timestamp",
  "user": "$(whoami)",
  "working_dir": "$(pwd)",
  "source": "interactive_shell",
  "status": "pending"
}
EOF
    
    echo "[StrikePackageGPT] Command logged: $cmd_id" >&2
    echo "[StrikePackageGPT] Results will be visible in dashboard" >&2
}

# PROMPT_COMMAND hook to log each command after execution
export PROMPT_COMMAND='history -a; if [ -n "$LAST_CMD" ]; then log_command "$LAST_CMD"; fi; LAST_CMD=$(history 1 | sed "s/^[ ]*[0-9]*[ ]*//"); '

# Also trap DEBUG for more comprehensive logging
trap 'LAST_EXEC_CMD="$BASH_COMMAND"' DEBUG

echo "[StrikePackageGPT] Command logging enabled"
echo "[StrikePackageGPT] All security tool commands will be captured and visible in the dashboard"
echo ""

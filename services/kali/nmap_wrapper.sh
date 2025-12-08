#!/bin/bash
# StrikePackageGPT nmap wrapper - sends scan results to Network Map and Scan History automatically

DASHBOARD_URL="${DASHBOARD_URL:-http://strikepackage-dashboard:8080}"
REAL_NMAP="/usr/bin/nmap"

# Capture the full command for logging
full_command="nmap $*"

# Determine target (last non-flag argument)
target="unknown"
for arg in "$@"; do
    if [[ ! "$arg" =~ ^- ]]; then
        target="$arg"
    fi
done

# Create temp file for output
tmpfile=$(mktemp)
trap "rm -f $tmpfile" EXIT

# Run the actual nmap and capture output
"$REAL_NMAP" "$@" 2>&1 | tee "$tmpfile"
exit_code=${PIPESTATUS[0]}

# If successful, send to dashboard
if [ $exit_code -eq 0 ]; then
    echo "" >&2
    echo "[StrikePackageGPT] Sending results to Dashboard..." >&2
    
    # Use jq with file input to avoid argument length limits
    # Send to network map
    jq -Rs --arg source "terminal" '{output: ., source: $source}' "$tmpfile" | \
        curl -s -X POST "${DASHBOARD_URL}/api/network/nmap-results" \
            -H "Content-Type: application/json" \
            -d @- >/dev/null 2>&1
    
    # Send to scan history
    response=$(jq -Rs --arg tool "nmap" --arg target "$target" --arg command "$full_command" \
        '{tool: $tool, target: $target, command: $command, output: ., source: "terminal"}' "$tmpfile" | \
        curl -s -X POST "${DASHBOARD_URL}/api/scans/terminal" \
            -H "Content-Type: application/json" \
            -d @- 2>/dev/null)
    
    if [ -n "$response" ]; then
        echo "[StrikePackageGPT] ✓ Results saved to Network Map and Scan History" >&2
    fi
fi

exit $exit_code

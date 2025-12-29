# Bidirectional Command Capture

## Overview

StrikePackageGPT now supports **bidirectional command capture**, enabling commands run directly in the Kali container to be automatically captured and displayed in the dashboard alongside commands executed via the UI/API.

This feature is perfect for advanced users who prefer command-line interfaces but still want visual tracking and historical reference.

## How It Works

```
┌─────────────────────────────────────────────────────────────┐
│                    Two-Way Flow                              │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│  Dashboard UI → HackGPT API → Kali Executor → Kali Container│
│       ↓                                           ↑          │
│  Stored in scan_results  ←────────────────────────          │
│       ↓                                                      │
│  Displayed in Dashboard History                             │
│                                                              │
│  Direct Shell → Command Logger → JSON Files → API Sync      │
│                      ↓                           ↑          │
│              /workspace/.command_history    Auto-Import     │
│                                                              │
└─────────────────────────────────────────────────────────────┘
```

## Features

### Automatic Logging
- All commands run in interactive bash sessions are automatically logged
- Command metadata captured: timestamp, user, working directory, exit code, duration
- Full stdout/stderr captured for commands run with `capture` wrapper

### Unified History
- Commands from both sources (UI and direct shell) appear in the same history
- Consistent format and parsing across all command sources
- Network visualization includes manually-run scans

### Real-Time Sync
- API endpoint to pull latest captured commands
- Background sync every 30 seconds (configurable)
- Manual sync available via `/commands/sync` endpoint

## Usage

### Option 1: Automatic Logging (All Commands)

When you connect to the Kali container, command logging is enabled automatically:

```bash
docker exec -it strikepackage-kali bash
```

Now run any security tool:

```bash
nmap -sV 192.168.1.0/24
sqlmap -u "http://example.com?id=1"
nikto -h http://example.com
```

These commands are logged with basic metadata. Full output capture requires Option 2.

### Option 2: Explicit Capture (With Full Output)

Use the `capture` command prefix for full output capture:

```bash
docker exec -it strikepackage-kali bash
capture nmap -sV 192.168.1.0/24
capture gobuster dir -u http://example.com -w /usr/share/wordlists/dirb/common.txt
```

This captures:
- Full stdout and stderr
- Exit codes
- Execution duration
- All command metadata

### View Recent Commands

Inside the container:

```bash
recent  # Shows last 10 captured commands
```

### Sync to Dashboard

Commands are automatically synced to the dashboard. To manually trigger a sync:

```bash
curl -X POST http://localhost:8001/commands/sync
```

## API Endpoints

### Get Captured Commands

```bash
GET /commands/captured?limit=50&since=2025-12-03T00:00:00Z
```

Returns commands captured from interactive sessions.

**Response:**
```json
{
  "commands": [
    {
      "command_id": "abc-123-def",
      "command": "nmap -sV 192.168.1.0/24",
      "timestamp": "2025-12-03T14:30:00Z",
      "completed_at": "2025-12-03T14:35:00Z",
      "status": "completed",
      "exit_code": 0,
      "duration": 300,
      "stdout": "... nmap output ...",
      "stderr": "",
      "user": "root",
      "working_dir": "/workspace",
      "source": "capture_wrapper"
    }
  ],
  "count": 1,
  "imported_to_history": true
}
```

### Sync Commands to History

```bash
POST /commands/sync
```

Imports all captured commands into the unified scan history, making them visible in the dashboard.

**Response:**
```json
{
  "status": "synced",
  "imported_count": 15,
  "message": "All captured commands are now visible in dashboard history"
}
```

### View Unified History

```bash
GET /scans
```

Returns all commands from both sources (UI and direct shell).

## Dashboard Integration

### Viewing Captured Commands

1. **Scan History Tab**: Shows all commands (UI + captured)
2. **Network Map**: Includes hosts discovered via manual scans
3. **Timeline View**: Shows when commands were executed
4. **Filter by Source**: Filter to show only manually-run or UI-run commands

### Visual Indicators

- 🔷 **UI Commands**: Blue indicator
- 🔶 **Manual Commands**: Orange indicator with "Interactive Shell" badge
- ⚡ **Running**: Animated indicator
- ✅ **Completed**: Green checkmark
- ❌ **Failed**: Red X with error details

## Configuration

### Enable/Disable Automatic Logging

To disable automatic logging in new shell sessions:

```bash
# Inside container
echo 'DISABLE_AUTO_LOGGING=1' >> ~/.bashrc
```

### Change Log Directory

Set a custom log directory:

```bash
# In docker-compose.yml or .env
COMMAND_LOG_DIR=/custom/path/.command_history
```

### Sync Interval

Configure auto-sync interval (default: 30 seconds):

```bash
# In HackGPT API configuration
COMMAND_SYNC_INTERVAL=60  # seconds
```

## Technical Details

### Storage Format

Commands are stored as JSON files in `/workspace/.command_history/`:

```json
{
  "command_id": "unique-uuid",
  "command": "nmap -sV 192.168.1.1",
  "timestamp": "2025-12-03T14:30:00Z",
  "completed_at": "2025-12-03T14:35:00Z",
  "user": "root",
  "working_dir": "/workspace",
  "source": "capture_wrapper",
  "status": "completed",
  "exit_code": 0,
  "duration": 300,
  "stdout": "...",
  "stderr": ""
}
```

### Command Logger (`command_logger.sh`)

- Hooks into `PROMPT_COMMAND` for automatic logging
- Filters out basic commands (cd, ls, etc.)
- Lightweight metadata-only logging
- No performance impact on command execution

### Capture Wrapper (`capture`)

- Full command wrapper for complete output capture
- Uses `eval` with output redirection
- Measures execution time
- Captures exit codes
- Saves results as JSON

### API Integration

1. **Kali Executor** reads JSON files from `/workspace/.command_history/`
2. **HackGPT API** imports them into `scan_results` dict
3. **Dashboard** displays them alongside UI-initiated commands
4. Automatic deduplication prevents duplicates

## Security Considerations

### Command Whitelist

- Command logging respects the existing whitelist
- Only whitelisted tools are executed
- Malicious commands are blocked before logging

### Storage Limits

- Log directory is size-limited (default: 10MB)
- Oldest logs are automatically purged
- Configurable retention period

### Access Control

- Logs are stored in container-specific workspace
- Only accessible via API with authentication (when enabled)
- No cross-container access

## Troubleshooting

### Commands Not Appearing in Dashboard

1. **Check logging is enabled**:
   ```bash
   docker exec -it strikepackage-kali bash -c 'echo $PROMPT_COMMAND'
   ```

2. **Verify log files are created**:
   ```bash
   docker exec -it strikepackage-kali ls -la /workspace/.command_history/
   ```

3. **Manually trigger sync**:
   ```bash
   curl -X POST http://localhost:8001/commands/sync
   ```

### Output Not Captured

- Use `capture` prefix for full output: `capture nmap ...`
- Check log file exists: `ls /workspace/.command_history/`
- Verify command completed: `recent`

### Performance Issues

If logging causes slowdowns:

1. **Disable for current session**:
   ```bash
   unset PROMPT_COMMAND
   ```

2. **Increase sync interval**:
   ```bash
   # In .env
   COMMAND_SYNC_INTERVAL=120
   ```

3. **Clear old logs**:
   ```bash
   curl -X DELETE http://localhost:8001/captured_commands/clear
   ```

## Examples

### Example 1: Network Reconnaissance

```bash
# In Kali container
docker exec -it strikepackage-kali bash

# Run discovery scan (automatically logged)
nmap -sn 192.168.1.0/24

# Run detailed scan with full capture
capture nmap -sV -sC -p- 192.168.1.100

# View in dashboard
# → Go to Scan History
# → See both commands with full results
# → View in Network Map
```

### Example 2: Web Application Testing

```bash
# Directory bruteforce
capture gobuster dir -u http://target.com -w /usr/share/wordlists/dirb/common.txt

# SQL injection testing
capture sqlmap -u "http://target.com?id=1" --batch --dbs

# Vulnerability scanning
capture nikto -h http://target.com

# All results appear in dashboard history
```

### Example 3: Wireless Auditing

```bash
# Put adapter in monitor mode
capture airmon-ng start wlan0

# Scan for networks
capture airodump-ng wlan0mon

# Results visible in dashboard with timestamps
```

## Advantages

### For Advanced Users
- ✅ Use familiar command-line interface
- ✅ Full control over tool parameters
- ✅ Faster than clicking through UI
- ✅ Still get visual tracking and history

### For Teams
- ✅ All team member activity captured
- ✅ Unified view of all scan activity
- ✅ Easy to review what was run
- ✅ Share results without screenshots

### For Reporting
- ✅ Complete audit trail
- ✅ Timestamp all activities
- ✅ Include in final reports
- ✅ Demonstrate thoroughness

## Comparison

| Feature | UI-Only | Bidirectional |
|---------|---------|---------------|
| Run commands via dashboard | ✅ | ✅ |
| Run commands via CLI | ❌ | ✅ |
| Visual history | ✅ | ✅ |
| Network map integration | ✅ | ✅ |
| Advanced tool parameters | Limited | Full |
| Speed for power users | Slow | Fast |
| Learning curve | Low | Medium |

## Future Enhancements

- **Real-time streaming**: See command output as it runs
- **Collaborative mode**: Multiple users see each other's commands
- **Smart suggestions**: AI suggests next commands based on results
- **Template library**: Save common command sequences
- **Report integration**: One-click add to PDF report

## Support

For issues or questions:
- GitHub Issues: https://github.com/mblanke/StrikePackageGPT/issues
- Documentation: See `FEATURES.md` and `INTEGRATION_EXAMPLE.md`
- Examples: Check `examples/` directory

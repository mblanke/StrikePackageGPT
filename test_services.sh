#!/bin/bash
# StrikePackageGPT Service Test Script

echo "=========================================="
echo "  StrikePackageGPT V2.1 Test Suite"
echo "=========================================="
echo ""

# Test 1: Health Endpoints
echo "=== TEST 1: Health Endpoints ==="
echo "LLM Router:"
curl -s http://strikepackage-llm-router:8000/health | jq .
echo ""
echo "HackGPT API:"
curl -s http://strikepackage-hackgpt-api:8001/health | jq .
echo ""
echo "Kali Executor:"
curl -s http://strikepackage-kali-executor:8002/health | jq .
echo ""

# Test 2: LLM Router
echo "=== TEST 2: LLM Router ==="
echo "Providers:"
curl -s http://strikepackage-llm-router:8000/providers | jq -r 'keys[]'
echo ""

echo "Chat Test (llama3.1:latest):"
cat > /tmp/chat.json << 'EOFCHAT'
{"provider":"ollama","model":"llama3.1:latest","messages":[{"role":"user","content":"Say hello in exactly 3 words"}]}
EOFCHAT
RESPONSE=$(curl -s -X POST http://strikepackage-llm-router:8000/chat -H "Content-Type: application/json" -d @/tmp/chat.json)
echo "$RESPONSE" | jq -r '.response // .content // .message // .' | head -c 200
echo ""
echo ""

# Test 3: HackGPT API
echo "=== TEST 3: HackGPT API ==="
echo "Tools available:"
curl -s http://strikepackage-hackgpt-api:8001/tools | jq -r '.[].name' 2>/dev/null || curl -s http://strikepackage-hackgpt-api:8001/tools | head -c 300
echo ""

echo "Scans list:"
curl -s http://strikepackage-hackgpt-api:8001/scans | jq . 2>/dev/null || echo "[]"
echo ""

# Test 4: Kali Executor  
echo "=== TEST 4: Kali Executor ==="
echo "Tools:"
curl -s http://strikepackage-kali-executor:8002/tools | jq -r '.tools[:5][]' 2>/dev/null || curl -s http://strikepackage-kali-executor:8002/tools | head -c 200
echo ""

echo "Execute nmap version:"
cat > /tmp/exec.json << 'EOFEXEC'
{"command":"nmap --version","timeout":30}
EOFEXEC
curl -s -X POST http://strikepackage-kali-executor:8002/execute -H "Content-Type: application/json" -d @/tmp/exec.json | jq -r '.output // .stdout // .' | head -5
echo ""

echo "Jobs:"
curl -s http://strikepackage-kali-executor:8002/jobs | jq -r 'length' 2>/dev/null || echo "0"
echo " jobs recorded"
echo ""

# Test 5: Security Scans from Kali
echo "=== TEST 5: Security Tools in Kali ==="
echo "nmap scan of llm-router:"
nmap -sT -p 8000 strikepackage-llm-router 2>&1 | grep -E "PORT|open|closed"
echo ""

echo "nikto quick test:"
nikto -h http://strikepackage-dashboard:8080 -maxtime 10s 2>&1 | tail -5
echo ""

echo "gobuster test:"
gobuster dir -u http://strikepackage-hackgpt-api:8001 -w /usr/share/dirb/wordlists/common.txt -t 5 --timeout 5s 2>&1 | grep -E "Status|Found|Finished" | head -10
echo ""

# Test 6: Dashboard APIs
echo "=== TEST 6: Dashboard APIs ==="
echo "Status:"
curl -s http://strikepackage-dashboard:8080/api/status | jq . 2>/dev/null || curl -s http://strikepackage-dashboard:8080/api/status
echo ""

echo "Processes:"
curl -s http://strikepackage-dashboard:8080/api/processes | jq -r 'length' 2>/dev/null
echo " processes"
echo ""

# Test 7: End-to-end Chat via Dashboard
echo "=== TEST 7: Dashboard Chat ==="
cat > /tmp/dashchat.json << 'EOFDASH'
{"message":"What is nmap used for? Answer in one sentence."}
EOFDASH
CHATRESP=$(curl -s -X POST http://strikepackage-dashboard:8080/api/chat -H "Content-Type: application/json" -d @/tmp/dashchat.json)
echo "$CHATRESP" | jq -r '.response // .content // .message // .' 2>/dev/null | head -c 300
echo ""
echo ""

# Test 8: Command Execution via Kali Executor
echo "=== TEST 8: Command Execution ==="
cat > /tmp/scanexec.json << 'EOFSCAN'
{"command":"nmap -sT -p 80,443,8000,8080 strikepackage-dashboard","timeout":60}
EOFSCAN
echo "Running: nmap scan of dashboard..."
EXECRESP=$(curl -s -X POST http://strikepackage-kali-executor:8002/execute -H "Content-Type: application/json" -d @/tmp/scanexec.json)
echo "$EXECRESP" | jq -r '.output // .stdout // .' 2>/dev/null | grep -E "PORT|open|closed|filtered" | head -10
echo ""

# Test 9: AI-Assisted Scanning
echo "=== TEST 9: AI Scan Request ==="
cat > /tmp/aiscan.json << 'EOFAI'
{"message":"Scan strikepackage-llm-router for web vulnerabilities"}
EOFAI
AIRESP=$(curl -s -X POST http://strikepackage-dashboard:8080/api/chat -H "Content-Type: application/json" -d @/tmp/aiscan.json)
echo "$AIRESP" | jq -r '.response // .content // .' 2>/dev/null | head -c 400
echo ""
echo ""

echo "=========================================="
echo "  Tests Complete!"
echo "=========================================="

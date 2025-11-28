<#
.SYNOPSIS
    GooseStrike Installation Script
.DESCRIPTION
    Interactive installer for GooseStrike AI-Powered Penetration Testing Platform
    Configures local, networked, and cloud AI backends
#>

param(
    [switch]$Unattended,
    [string]$ConfigFile
)

$ErrorActionPreference = "Stop"

# Colors and formatting
function Write-Header {
    param([string]$Text)
    Write-Host ""
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host "  $Text" -ForegroundColor White
    Write-Host "═══════════════════════════════════════════════════════════════" -ForegroundColor Red
    Write-Host ""
}

function Write-Step {
    param([string]$Text)
    Write-Host "  [*] $Text" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Text)
    Write-Host "  [✓] $Text" -ForegroundColor Green
}

function Write-Warning {
    param([string]$Text)
    Write-Host "  [!] $Text" -ForegroundColor Yellow
}

function Write-Error {
    param([string]$Text)
    Write-Host "  [✗] $Text" -ForegroundColor Red
}

function Get-UserChoice {
    param(
        [string]$Prompt,
        [string[]]$Options,
        [bool]$MultiSelect = $false
    )
    
    Write-Host ""
    Write-Host "  $Prompt" -ForegroundColor White
    Write-Host ""
    
    for ($i = 0; $i -lt $Options.Count; $i++) {
        Write-Host "    [$($i + 1)] $($Options[$i])" -ForegroundColor Gray
    }
    
    if ($MultiSelect) {
        Write-Host ""
        Write-Host "    Enter numbers separated by commas (e.g., 1,2,3) or 'all'" -ForegroundColor DarkGray
        $input = Read-Host "    Selection"
        
        if ($input -eq "all") {
            return (1..$Options.Count)
        }
        
        return $input.Split(",") | ForEach-Object { [int]$_.Trim() }
    } else {
        Write-Host ""
        $choice = Read-Host "    Selection"
        return [int]$choice
    }
}

function Test-OllamaEndpoint {
    param([string]$Url)
    
    try {
        $response = Invoke-WebRequest -Uri "$Url/api/tags" -TimeoutSec 5 -ErrorAction Stop
        return $response.StatusCode -eq 200
    } catch {
        return $false
    }
}

function Get-OllamaModels {
    param([string]$Url)
    
    try {
        $response = Invoke-RestMethod -Uri "$Url/api/tags" -TimeoutSec 10
        return $response.models | ForEach-Object { $_.name }
    } catch {
        return @()
    }
}

# ═══════════════════════════════════════════════════════════════
# MAIN INSTALLATION FLOW
# ═══════════════════════════════════════════════════════════════

Clear-Host
Write-Host @"

    ╔═══════════════════════════════════════════════════════════════╗
    ║                                                               ║
    ║   ██████╗  ██████╗  ██████╗ ███████╗███████╗                 ║
    ║  ██╔════╝ ██╔═══██╗██╔═══██╗██╔════╝██╔════╝                 ║
    ║  ██║  ███╗██║   ██║██║   ██║███████╗█████╗                   ║
    ║  ██║   ██║██║   ██║██║   ██║╚════██║██╔══╝                   ║
    ║  ╚██████╔╝╚██████╔╝╚██████╔╝███████║███████╗                 ║
    ║   ╚═════╝  ╚═════╝  ╚═════╝ ╚══════╝╚══════╝                 ║
    ║                                                               ║
    ║  ███████╗████████╗██████╗ ██╗██╗  ██╗███████╗                ║
    ║  ██╔════╝╚══██╔══╝██╔══██╗██║██║ ██╔╝██╔════╝                ║
    ║  ███████╗   ██║   ██████╔╝██║█████╔╝ █████╗                  ║
    ║  ╚════██║   ██║   ██╔══██╗██║██╔═██╗ ██╔══╝                  ║
    ║  ███████║   ██║   ██║  ██║██║██║  ██╗███████╗                ║
    ║  ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝╚═╝  ╚═╝╚══════╝                ║
    ║                                                               ║
    ║         AI-Powered Penetration Testing Platform               ║
    ║                     Installation Wizard                       ║
    ╚═══════════════════════════════════════════════════════════════╝

"@ -ForegroundColor Red

Write-Host "  Welcome to GooseStrike! This wizard will configure your AI backends." -ForegroundColor White
Write-Host ""

# ═══════════════════════════════════════════════════════════════
# STEP 1: AI PROVIDER SELECTION
# ═══════════════════════════════════════════════════════════════

Write-Header "STEP 1: AI Provider Selection"

$providerOptions = @(
    "Local Only (Ollama on this machine)",
    "Networked Only (Ollama on remote machines)",
    "Cloud Only (OpenAI, Anthropic, etc.)",
    "Hybrid - Local + Networked",
    "Hybrid - Local + Cloud",
    "Hybrid - Networked + Cloud",
    "Full Stack - All providers (Local + Networked + Cloud)"
)

$providerChoice = Get-UserChoice -Prompt "How do you want to run your AI models?" -Options $providerOptions

# Initialize configuration
$config = @{
    local = @{
        enabled = $false
        url = "http://localhost:11434"
        models = @()
    }
    networked = @{
        enabled = $false
        endpoints = @()
    }
    cloud = @{
        enabled = $false
        openai = @{ enabled = $false; api_key = ""; models = @("gpt-4", "gpt-4-turbo", "gpt-3.5-turbo") }
        anthropic = @{ enabled = $false; api_key = ""; models = @("claude-3-opus-20240229", "claude-3-sonnet-20240229") }
        groq = @{ enabled = $false; api_key = ""; models = @("llama-3.1-70b-versatile", "mixtral-8x7b-32768") }
    }
    default_provider = "ollama"
    default_model = "llama3.2"
    load_balancing = "round-robin"
}

# Determine which providers to configure based on selection
$configureLocal = $providerChoice -in @(1, 4, 5, 7)
$configureNetworked = $providerChoice -in @(2, 4, 6, 7)
$configureCloud = $providerChoice -in @(3, 5, 6, 7)

# ═══════════════════════════════════════════════════════════════
# STEP 2: LOCAL OLLAMA CONFIGURATION
# ═══════════════════════════════════════════════════════════════

if ($configureLocal) {
    Write-Header "STEP 2: Local Ollama Configuration"
    
    Write-Step "Checking for local Ollama installation..."
    
    $localUrl = "http://localhost:11434"
    $ollamaRunning = Test-OllamaEndpoint -Url $localUrl
    
    if ($ollamaRunning) {
        Write-Success "Ollama is running at $localUrl"
        
        $models = Get-OllamaModels -Url $localUrl
        if ($models.Count -gt 0) {
            Write-Success "Found $($models.Count) model(s): $($models -join ', ')"
            $config.local.models = $models
        } else {
            Write-Warning "No models found. You may need to pull models with: ollama pull llama3.2"
        }
        
        $config.local.enabled = $true
        $config.local.url = $localUrl
    } else {
        Write-Warning "Ollama not detected at $localUrl"
        
        $installChoice = Read-Host "    Would you like to install Ollama? (y/n)"
        if ($installChoice -eq "y") {
            Write-Step "Opening Ollama download page..."
            Start-Process "https://ollama.com/download"
            Write-Host ""
            Write-Host "    Please install Ollama and run: ollama pull llama3.2" -ForegroundColor Yellow
            Write-Host "    Then re-run this installer." -ForegroundColor Yellow
            Read-Host "    Press Enter to continue anyway, or Ctrl+C to exit"
        }
        
        $config.local.enabled = $false
    }
}

# ═══════════════════════════════════════════════════════════════
# STEP 3: NETWORKED OLLAMA CONFIGURATION
# ═══════════════════════════════════════════════════════════════

if ($configureNetworked) {
    Write-Header "STEP 3: Networked Ollama Configuration"
    
    Write-Host "  Configure remote Ollama endpoints (GPU servers, clusters, etc.)" -ForegroundColor White
    Write-Host ""
    
    $addMore = $true
    $endpointIndex = 1
    
    while ($addMore) {
        Write-Host "  ── Endpoint #$endpointIndex ──" -ForegroundColor Cyan
        Write-Host ""
        
        # Get endpoint details
        $name = Read-Host "    Friendly name (e.g., 'Dell Pro Max GB10')"
        $ip = Read-Host "    IP Address (e.g., 192.168.1.50)"
        $port = Read-Host "    Port (default: 11434)"
        if ([string]::IsNullOrEmpty($port)) { $port = "11434" }
        
        # Network interface selection
        Write-Host ""
        Write-Host "    Network interface options:" -ForegroundColor Gray
        Write-Host "      [1] Primary network (default)" -ForegroundColor Gray
        Write-Host "      [2] High-speed interface (100GbE, etc.)" -ForegroundColor Gray
        $nicChoice = Read-Host "    Selection (default: 1)"
        
        $networkInterface = "primary"
        $altIp = $null
        
        if ($nicChoice -eq "2") {
            $networkInterface = "high-speed"
            $altIp = Read-Host "    High-speed interface IP (e.g., 10.0.0.50)"
        }
        
        # Build endpoint URL
        $endpointUrl = "http://${ip}:${port}"
        
        Write-Step "Testing connection to $endpointUrl..."
        
        $endpoint = @{
            name = $name
            url = $endpointUrl
            ip = $ip
            port = [int]$port
            network_interface = $networkInterface
            alt_ip = $altIp
            alt_url = if ($altIp) { "http://${altIp}:${port}" } else { $null }
            enabled = $false
            models = @()
            priority = $endpointIndex
        }
        
        if (Test-OllamaEndpoint -Url $endpointUrl) {
            Write-Success "Connected to $name at $endpointUrl"
            
            $models = Get-OllamaModels -Url $endpointUrl
            if ($models.Count -gt 0) {
                Write-Success "Available models: $($models -join ', ')"
                $endpoint.models = $models
            }
            
            $endpoint.enabled = $true
            
            # Test alternate interface if configured
            if ($altIp) {
                Write-Step "Testing high-speed interface at $($endpoint.alt_url)..."
                if (Test-OllamaEndpoint -Url $endpoint.alt_url) {
                    Write-Success "High-speed interface reachable"
                    
                    $preferHs = Read-Host "    Prefer high-speed interface when available? (y/n)"
                    if ($preferHs -eq "y") {
                        $endpoint.prefer_high_speed = $true
                    }
                } else {
                    Write-Warning "High-speed interface not reachable (will use primary)"
                }
            }
        } else {
            Write-Warning "Could not connect to $endpointUrl"
            $keepEndpoint = Read-Host "    Add anyway? (y/n)"
            if ($keepEndpoint -eq "y") {
                $endpoint.enabled = $false
            } else {
                $endpoint = $null
            }
        }
        
        if ($endpoint) {
            $config.networked.endpoints += $endpoint
        }
        
        Write-Host ""
        $addMoreChoice = Read-Host "    Add another networked endpoint? (y/n)"
        $addMore = $addMoreChoice -eq "y"
        $endpointIndex++
    }
    
    if ($config.networked.endpoints.Count -gt 0) {
        $config.networked.enabled = $true
        
        # Load balancing configuration
        if ($config.networked.endpoints.Count -gt 1) {
            Write-Host ""
            Write-Host "  Multiple endpoints configured. Select load balancing strategy:" -ForegroundColor White
            
            $lbOptions = @(
                "Round-robin (distribute evenly)",
                "Priority-based (use highest priority first)",
                "Fastest-response (route to quickest endpoint)",
                "Model-based (route by model availability)"
            )
            
            $lbChoice = Get-UserChoice -Prompt "Load balancing strategy:" -Options $lbOptions
            
            $config.load_balancing = switch ($lbChoice) {
                1 { "round-robin" }
                2 { "priority" }
                3 { "fastest" }
                4 { "model-based" }
                default { "round-robin" }
            }
            
            Write-Success "Load balancing set to: $($config.load_balancing)"
        }
    }
}

# ═══════════════════════════════════════════════════════════════
# STEP 4: CLOUD PROVIDER CONFIGURATION
# ═══════════════════════════════════════════════════════════════

if ($configureCloud) {
    Write-Header "STEP 4: Cloud Provider Configuration"
    
    Write-Host "  Configure cloud AI providers (API keys required)" -ForegroundColor White
    Write-Host ""
    
    # OpenAI
    Write-Host "  ── OpenAI ──" -ForegroundColor Cyan
    $useOpenAI = Read-Host "    Enable OpenAI? (y/n)"
    if ($useOpenAI -eq "y") {
        $openaiKey = Read-Host "    OpenAI API Key" -AsSecureString
        $openaiKeyPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($openaiKey))
        
        if ($openaiKeyPlain -match "^sk-") {
            $config.cloud.openai.enabled = $true
            $config.cloud.openai.api_key = $openaiKeyPlain
            Write-Success "OpenAI configured"
        } else {
            Write-Warning "Invalid API key format (should start with 'sk-')"
        }
    }
    
    Write-Host ""
    
    # Anthropic
    Write-Host "  ── Anthropic (Claude) ──" -ForegroundColor Cyan
    $useAnthropic = Read-Host "    Enable Anthropic? (y/n)"
    if ($useAnthropic -eq "y") {
        $anthropicKey = Read-Host "    Anthropic API Key" -AsSecureString
        $anthropicKeyPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($anthropicKey))
        
        if ($anthropicKeyPlain -match "^sk-ant-") {
            $config.cloud.anthropic.enabled = $true
            $config.cloud.anthropic.api_key = $anthropicKeyPlain
            Write-Success "Anthropic configured"
        } else {
            Write-Warning "Invalid API key format (should start with 'sk-ant-')"
        }
    }
    
    Write-Host ""
    
    # Groq
    Write-Host "  ── Groq (Fast inference) ──" -ForegroundColor Cyan
    $useGroq = Read-Host "    Enable Groq? (y/n)"
    if ($useGroq -eq "y") {
        $groqKey = Read-Host "    Groq API Key" -AsSecureString
        $groqKeyPlain = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($groqKey))
        
        $config.cloud.groq.enabled = $true
        $config.cloud.groq.api_key = $groqKeyPlain
        Write-Success "Groq configured"
    }
    
    $config.cloud.enabled = $config.cloud.openai.enabled -or $config.cloud.anthropic.enabled -or $config.cloud.groq.enabled
}

# ═══════════════════════════════════════════════════════════════
# STEP 5: DEFAULT PROVIDER SELECTION
# ═══════════════════════════════════════════════════════════════

Write-Header "STEP 5: Default Provider Selection"

$availableProviders = @()
$providerMap = @{}

if ($config.local.enabled) {
    $availableProviders += "Local Ollama (localhost)"
    $providerMap["Local Ollama (localhost)"] = @{ provider = "ollama"; url = $config.local.url }
}

foreach ($endpoint in $config.networked.endpoints | Where-Object { $_.enabled }) {
    $label = "Networked: $($endpoint.name)"
    $availableProviders += $label
    $providerMap[$label] = @{ provider = "ollama"; url = $endpoint.url; name = $endpoint.name }
}

if ($config.cloud.openai.enabled) {
    $availableProviders += "OpenAI (GPT-4)"
    $providerMap["OpenAI (GPT-4)"] = @{ provider = "openai" }
}

if ($config.cloud.anthropic.enabled) {
    $availableProviders += "Anthropic (Claude)"
    $providerMap["Anthropic (Claude)"] = @{ provider = "anthropic" }
}

if ($config.cloud.groq.enabled) {
    $availableProviders += "Groq (Fast)"
    $providerMap["Groq (Fast)"] = @{ provider = "groq" }
}

if ($availableProviders.Count -gt 0) {
    $defaultChoice = Get-UserChoice -Prompt "Select your default AI provider:" -Options $availableProviders
    $selectedProvider = $availableProviders[$defaultChoice - 1]
    $config.default_provider = $providerMap[$selectedProvider].provider
    
    Write-Success "Default provider: $selectedProvider"
} else {
    Write-Error "No providers configured! At least one provider is required."
    exit 1
}

# ═══════════════════════════════════════════════════════════════
# STEP 6: GENERATE CONFIGURATION FILES
# ═══════════════════════════════════════════════════════════════

Write-Header "STEP 6: Generating Configuration"

$scriptRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $scriptRoot ".env"
$configJsonFile = Join-Path $scriptRoot "config" "ai-providers.json"

# Create config directory if needed
$configDir = Join-Path $scriptRoot "config"
if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
}

# Generate .env file
Write-Step "Generating .env file..."

$envContent = @"
# ═══════════════════════════════════════════════════════════════
# GooseStrike Configuration
# Generated by installer on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# ═══════════════════════════════════════════════════════════════

# Default AI Provider
DEFAULT_PROVIDER=$($config.default_provider)
DEFAULT_MODEL=$($config.default_model)

# Local Ollama
LOCAL_OLLAMA_ENABLED=$($config.local.enabled.ToString().ToLower())
LOCAL_OLLAMA_URL=$($config.local.url)

# Networked Ollama Endpoints
NETWORKED_OLLAMA_ENABLED=$($config.networked.enabled.ToString().ToLower())
LOAD_BALANCING_STRATEGY=$($config.load_balancing)

"@

# Add networked endpoints
$endpointNum = 1
foreach ($endpoint in $config.networked.endpoints) {
    $envContent += @"
# Networked Endpoint $endpointNum - $($endpoint.name)
OLLAMA_ENDPOINT_${endpointNum}_NAME=$($endpoint.name)
OLLAMA_ENDPOINT_${endpointNum}_URL=$($endpoint.url)
OLLAMA_ENDPOINT_${endpointNum}_ENABLED=$($endpoint.enabled.ToString().ToLower())
OLLAMA_ENDPOINT_${endpointNum}_PRIORITY=$($endpoint.priority)

"@
    if ($endpoint.alt_url) {
        $envContent += "OLLAMA_ENDPOINT_${endpointNum}_ALT_URL=$($endpoint.alt_url)`n"
        $envContent += "OLLAMA_ENDPOINT_${endpointNum}_PREFER_ALT=$($endpoint.prefer_high_speed.ToString().ToLower())`n`n"
    }
    $endpointNum++
}

$envContent += "OLLAMA_ENDPOINT_COUNT=$($config.networked.endpoints.Count)`n`n"

# Add cloud providers
$envContent += @"
# Cloud Providers
OPENAI_ENABLED=$($config.cloud.openai.enabled.ToString().ToLower())
OPENAI_API_KEY=$($config.cloud.openai.api_key)

ANTHROPIC_ENABLED=$($config.cloud.anthropic.enabled.ToString().ToLower())
ANTHROPIC_API_KEY=$($config.cloud.anthropic.api_key)

GROQ_ENABLED=$($config.cloud.groq.enabled.ToString().ToLower())
GROQ_API_KEY=$($config.cloud.groq.api_key)
"@

$envContent | Out-File -FilePath $envFile -Encoding UTF8 -Force
Write-Success "Created $envFile"

# Generate JSON config
Write-Step "Generating AI providers config..."

$config | ConvertTo-Json -Depth 10 | Out-File -FilePath $configJsonFile -Encoding UTF8 -Force
Write-Success "Created $configJsonFile"

# ═══════════════════════════════════════════════════════════════
# STEP 7: DOCKER SETUP
# ═══════════════════════════════════════════════════════════════

Write-Header "STEP 7: Docker Setup"

Write-Step "Checking Docker..."

$dockerRunning = $false
try {
    $dockerVersion = docker version --format '{{.Server.Version}}' 2>$null
    if ($dockerVersion) {
        Write-Success "Docker is running (version $dockerVersion)"
        $dockerRunning = $true
    }
} catch {
    Write-Warning "Docker is not running"
}

if ($dockerRunning) {
    $startNow = Read-Host "    Start GooseStrike now? (y/n)"
    
    if ($startNow -eq "y") {
        Write-Step "Building and starting containers..."
        
        Push-Location $scriptRoot
        docker-compose up -d --build
        Pop-Location
        
        Write-Success "GooseStrike is starting!"
        Write-Host ""
        Write-Host "    Dashboard: http://localhost:8080" -ForegroundColor Green
        Write-Host ""
    }
} else {
    Write-Warning "Please start Docker and run: docker-compose up -d --build"
}

# ═══════════════════════════════════════════════════════════════
# COMPLETE
# ═══════════════════════════════════════════════════════════════

Write-Header "Installation Complete!"

Write-Host "  Configuration Summary:" -ForegroundColor White
Write-Host ""

if ($config.local.enabled) {
    Write-Host "    ✓ Local Ollama: $($config.local.url)" -ForegroundColor Green
}

foreach ($endpoint in $config.networked.endpoints | Where-Object { $_.enabled }) {
    Write-Host "    ✓ Networked: $($endpoint.name) @ $($endpoint.url)" -ForegroundColor Green
    if ($endpoint.alt_url) {
        Write-Host "      └─ High-speed: $($endpoint.alt_url)" -ForegroundColor DarkGreen
    }
}

if ($config.cloud.openai.enabled) {
    Write-Host "    ✓ OpenAI: Enabled" -ForegroundColor Green
}
if ($config.cloud.anthropic.enabled) {
    Write-Host "    ✓ Anthropic: Enabled" -ForegroundColor Green
}
if ($config.cloud.groq.enabled) {
    Write-Host "    ✓ Groq: Enabled" -ForegroundColor Green
}

Write-Host ""
Write-Host "  Default Provider: $($config.default_provider)" -ForegroundColor Cyan

if ($config.networked.endpoints.Count -gt 1) {
    Write-Host "  Load Balancing: $($config.load_balancing)" -ForegroundColor Cyan
}

Write-Host ""
Write-Host "  Files created:" -ForegroundColor White
Write-Host "    - $envFile" -ForegroundColor Gray
Write-Host "    - $configJsonFile" -ForegroundColor Gray
Write-Host ""
Write-Host "  To start GooseStrike:" -ForegroundColor White
Write-Host "    cd $scriptRoot" -ForegroundColor Gray
Write-Host "    docker-compose up -d" -ForegroundColor Gray
Write-Host ""
Write-Host "  Dashboard: http://localhost:8080" -ForegroundColor Green
Write-Host ""

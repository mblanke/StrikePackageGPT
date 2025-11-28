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
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host "  $Text" -ForegroundColor White
    Write-Host "======================================================================" -ForegroundColor Red
    Write-Host ""
}

function Write-Step {
    param([string]$Text)
    Write-Host "  [*] $Text" -ForegroundColor Cyan
}

function Write-Success {
    param([string]$Text)
    Write-Host "  [+] $Text" -ForegroundColor Green
}

function Write-Warn {
    param([string]$Text)
    Write-Host "  [!] $Text" -ForegroundColor Yellow
}

function Write-Err {
    param([string]$Text)
    Write-Host "  [-] $Text" -ForegroundColor Red
}

function Get-UserChoice {
    param(
        [string]$Prompt,
        [string[]]$Options
    )
    
    Write-Host ""
    Write-Host "  $Prompt" -ForegroundColor White
    Write-Host ""
    
    for ($i = 0; $i -lt $Options.Count; $i++) {
        Write-Host "    [$($i + 1)] $($Options[$i])" -ForegroundColor Gray
    }
    
    Write-Host ""
    $choice = Read-Host "    Selection"
    return [int]$choice
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

# ======================================================================
# MAIN INSTALLATION FLOW
# ======================================================================

Clear-Host
Write-Host @"

    ================================================================
    
       GOOSE STRIKE
       AI-Powered Penetration Testing Platform
       Installation Wizard
    
    ================================================================

"@ -ForegroundColor Red

Write-Host "  Welcome to GooseStrike! This wizard will configure your AI backends." -ForegroundColor White
Write-Host ""

# ======================================================================
# STEP 1: AI PROVIDER SELECTION
# ======================================================================

Write-Header "STEP 1: AI Provider Selection"

$providerOptions = @(
    "Local Only (Ollama on this machine)",
    "Networked Only (Ollama on remote machines)",
    "Cloud Only (OpenAI or Anthropic)",
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
        openai = @{ enabled = $false; api_key = "" }
        anthropic = @{ enabled = $false; api_key = "" }
    }
    default_provider = "ollama"
    default_model = "llama3.2"
    load_balancing = "round-robin"
}

# Determine which providers to configure based on selection
$configureLocal = $providerChoice -in @(1, 4, 5, 7)
$configureNetworked = $providerChoice -in @(2, 4, 6, 7)
$configureCloud = $providerChoice -in @(3, 5, 6, 7)

# ======================================================================
# STEP 2: LOCAL OLLAMA CONFIGURATION
# ======================================================================

if ($configureLocal) {
    Write-Header "STEP 2: Local Ollama Configuration"
    
    Write-Step "Checking for local Ollama installation..."
    
    $localUrl = "http://localhost:11434"
    $ollamaRunning = Test-OllamaEndpoint -Url $localUrl
    
    if ($ollamaRunning) {
        Write-Success "Ollama is running at $localUrl"
        
        $models = Get-OllamaModels -Url $localUrl
        if ($models.Count -gt 0) {
            $modelList = $models -join ", "
            Write-Success "Found $($models.Count) model(s): $modelList"
            $config.local.models = $models
        } else {
            Write-Warn "No models found. You may need to pull models with: ollama pull llama3.2"
        }
        
        $config.local.enabled = $true
        $config.local.url = $localUrl
    } else {
        Write-Warn "Ollama not detected at $localUrl"
        
        $installChoice = Read-Host "    Would you like to install Ollama? (y/n)"
        if ($installChoice -eq "y") {
            Write-Step "Opening Ollama download page..."
            Start-Process "https://ollama.com/download"
            Write-Host ""
            Write-Host "    Please install Ollama and run: ollama pull llama3.2" -ForegroundColor Yellow
            Write-Host "    Then re-run this installer." -ForegroundColor Yellow
            Read-Host "    Press Enter to continue anyway or Ctrl+C to exit"
        }
        
        $config.local.enabled = $false
    }
}

# ======================================================================
# STEP 3: NETWORKED OLLAMA CONFIGURATION
# ======================================================================

if ($configureNetworked) {
    Write-Header "STEP 3: Networked Ollama Configuration"
    
    Write-Host "  Configure remote Ollama endpoints (GPU servers, clusters, etc.)" -ForegroundColor White
    Write-Host ""
    
    $addMore = $true
    $endpointIndex = 1
    
    while ($addMore) {
        Write-Host "  -- Endpoint #$endpointIndex --" -ForegroundColor Cyan
        Write-Host ""
        
        # Get endpoint details
        $epName = Read-Host "    Friendly name (e.g. Dell Pro Max GB10)"
        $epIp = Read-Host "    IP Address (e.g. 192.168.1.50)"
        $epPort = Read-Host "    Port (default: 11434)"
        if ([string]::IsNullOrEmpty($epPort)) { $epPort = "11434" }
        
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
            $altIp = Read-Host "    High-speed interface IP (e.g. 10.0.0.50)"
        }
        
        # Build endpoint URL
        $endpointUrl = "http://${epIp}:${epPort}"
        
        Write-Step "Testing connection to $endpointUrl..."
        
        $endpoint = @{
            name = $epName
            url = $endpointUrl
            ip = $epIp
            port = [int]$epPort
            network_interface = $networkInterface
            alt_ip = $altIp
            alt_url = if ($altIp) { "http://${altIp}:${epPort}" } else { $null }
            enabled = $false
            models = @()
            priority = $endpointIndex
        }
        
        if (Test-OllamaEndpoint -Url $endpointUrl) {
            Write-Success "Connected to $epName at $endpointUrl"
            
            $models = Get-OllamaModels -Url $endpointUrl
            if ($models.Count -gt 0) {
                $modelList = $models -join ", "
                Write-Success "Available models: $modelList"
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
                    Write-Warn "High-speed interface not reachable (will use primary)"
                }
            }
        } else {
            Write-Warn "Could not connect to $endpointUrl"
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
                "Random (random selection)"
            )
            
            $lbChoice = Get-UserChoice -Prompt "Load balancing strategy:" -Options $lbOptions
            
            $config.load_balancing = switch ($lbChoice) {
                1 { "round-robin" }
                2 { "failover" }
                3 { "random" }
                default { "round-robin" }
            }
            
            Write-Success "Load balancing set to: $($config.load_balancing)"
        }
    }
}

# ======================================================================
# STEP 4: CLOUD PROVIDER CONFIGURATION
# ======================================================================

if ($configureCloud) {
    Write-Header "STEP 4: Cloud Provider Configuration"
    
    Write-Host "  Configure cloud AI providers (API keys required)" -ForegroundColor White
    Write-Host ""
    
    # OpenAI
    Write-Host "  -- OpenAI --" -ForegroundColor Cyan
    $useOpenAI = Read-Host "    Enable OpenAI? (y/n)"
    if ($useOpenAI -eq "y") {
        $openaiKey = Read-Host "    OpenAI API Key"
        
        if ($openaiKey -match "^sk-") {
            $config.cloud.openai.enabled = $true
            $config.cloud.openai.api_key = $openaiKey
            Write-Success "OpenAI configured"
        } else {
            Write-Warn "Invalid API key format (should start with sk-)"
        }
    }
    
    Write-Host ""
    
    # Anthropic
    Write-Host "  -- Anthropic (Claude) --" -ForegroundColor Cyan
    $useAnthropic = Read-Host "    Enable Anthropic? (y/n)"
    if ($useAnthropic -eq "y") {
        $anthropicKey = Read-Host "    Anthropic API Key"
        
        if ($anthropicKey -match "^sk-ant-") {
            $config.cloud.anthropic.enabled = $true
            $config.cloud.anthropic.api_key = $anthropicKey
            Write-Success "Anthropic configured"
        } else {
            Write-Warn "Invalid API key format (should start with sk-ant-)"
        }
    }
    
    $config.cloud.enabled = $config.cloud.openai.enabled -or $config.cloud.anthropic.enabled
}

# ======================================================================
# STEP 5: DEFAULT PROVIDER SELECTION
# ======================================================================

Write-Header "STEP 5: Default Provider Selection"

$availableProviders = @()
$providerMap = @{}

if ($config.local.enabled) {
    $availableProviders += "Local Ollama (localhost)"
    $providerMap["Local Ollama (localhost)"] = @{ provider = "ollama"; url = $config.local.url }
}

foreach ($ep in $config.networked.endpoints) {
    if ($ep.enabled) {
        $label = "Networked: $($ep.name)"
        $availableProviders += $label
        $providerMap[$label] = @{ provider = "ollama"; url = $ep.url; name = $ep.name }
    }
}

if ($config.cloud.openai.enabled) {
    $availableProviders += "OpenAI (GPT-4)"
    $providerMap["OpenAI (GPT-4)"] = @{ provider = "openai" }
}

if ($config.cloud.anthropic.enabled) {
    $availableProviders += "Anthropic (Claude)"
    $providerMap["Anthropic (Claude)"] = @{ provider = "anthropic" }
}

if ($availableProviders.Count -gt 0) {
    $defaultChoice = Get-UserChoice -Prompt "Select your default AI provider:" -Options $availableProviders
    $selectedProvider = $availableProviders[$defaultChoice - 1]
    $config.default_provider = $providerMap[$selectedProvider].provider
    
    Write-Success "Default provider: $selectedProvider"
} else {
    Write-Err "No providers configured! At least one provider is required."
    exit 1
}

# ======================================================================
# STEP 6: GENERATE CONFIGURATION FILES
# ======================================================================

Write-Header "STEP 6: Generating Configuration"

$scriptRoot = Split-Path -Parent $PSScriptRoot
$envFile = Join-Path $scriptRoot ".env"
$configDir = Join-Path $scriptRoot "config"
$configJsonFile = Join-Path $configDir "ai-providers.json"

# Create config directory if needed
if (-not (Test-Path $configDir)) {
    New-Item -ItemType Directory -Path $configDir -Force | Out-Null
}

# Build OLLAMA_LOCAL_URL and OLLAMA_NETWORK_URLS strings
$ollamaLocalUrl = ""
$ollamaNetworkUrls = @()

if ($config.local.enabled) {
    $ollamaLocalUrl = $config.local.url
}

foreach ($ep in $config.networked.endpoints) {
    if ($ep.enabled) {
        if ($ep.prefer_high_speed -and $ep.alt_url) {
            $ollamaNetworkUrls += $ep.alt_url
        } else {
            $ollamaNetworkUrls += $ep.url
        }
    }
}
$ollamaNetworkUrlsStr = $ollamaNetworkUrls -join ","

# Generate .env file
Write-Step "Generating .env file..."

$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$envLines = @(
    "# ======================================================================",
    "# GooseStrike Configuration",
    "# Generated by installer on $timestamp",
    "# ======================================================================",
    "",
    "# Local Ollama (on this machine)",
    "OLLAMA_LOCAL_URL=$ollamaLocalUrl",
    "",
    "# Networked Ollama (comma-separated for load balancing)",
    "OLLAMA_NETWORK_URLS=$ollamaNetworkUrlsStr",
    "",
    "# Load Balancing Strategy: round-robin, failover, random",
    "LOAD_BALANCE_STRATEGY=$($config.load_balancing)",
    "",
    "# Cloud Providers",
    "OPENAI_API_KEY=$($config.cloud.openai.api_key)",
    "ANTHROPIC_API_KEY=$($config.cloud.anthropic.api_key)",
    "",
    "# Default Settings",
    "DEFAULT_PROVIDER=$($config.default_provider)",
    "DEFAULT_MODEL=$($config.default_model)"
)

$envLines -join "`n" | Out-File -FilePath $envFile -Encoding UTF8 -Force
Write-Success "Created $envFile"

# Generate JSON config
Write-Step "Generating AI providers config..."
$config | ConvertTo-Json -Depth 10 | Out-File -FilePath $configJsonFile -Encoding UTF8 -Force
Write-Success "Created $configJsonFile"

# ======================================================================
# STEP 7: DOCKER SETUP
# ======================================================================

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
    Write-Warn "Docker is not running"
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
    Write-Warn "Please start Docker and run: docker-compose up -d --build"
}

# ======================================================================
# COMPLETE
# ======================================================================

Write-Header "Installation Complete!"

Write-Host "  Configuration Summary:" -ForegroundColor White
Write-Host ""

if ($config.local.enabled) {
    Write-Host "    + Local Ollama: $($config.local.url)" -ForegroundColor Green
}

foreach ($ep in $config.networked.endpoints) {
    if ($ep.enabled) {
        Write-Host "    + Networked: $($ep.name) @ $($ep.url)" -ForegroundColor Green
        if ($ep.alt_url) {
            Write-Host "      High-speed: $($ep.alt_url)" -ForegroundColor DarkGreen
        }
    }
}

if ($config.cloud.openai.enabled) {
    Write-Host "    + OpenAI: Enabled" -ForegroundColor Green
}
if ($config.cloud.anthropic.enabled) {
    Write-Host "    + Anthropic: Enabled" -ForegroundColor Green
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

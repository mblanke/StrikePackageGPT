#!/bin/bash
#
# GooseStrike Installation Script
# Interactive installer for AI-Powered Penetration Testing Platform
#

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
WHITE='\033[1;37m'
GRAY='\033[0;90m'
NC='\033[0m' # No Color

# Functions
print_header() {
    echo ""
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo -e "${WHITE}  $1${NC}"
    echo -e "${RED}═══════════════════════════════════════════════════════════════${NC}"
    echo ""
}

print_step() {
    echo -e "${CYAN}  [*] $1${NC}"
}

print_success() {
    echo -e "${GREEN}  [✓] $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}  [!] $1${NC}"
}

print_error() {
    echo -e "${RED}  [✗] $1${NC}"
}

test_ollama_endpoint() {
    local url=$1
    curl -s --connect-timeout 5 "${url}/api/tags" > /dev/null 2>&1
    return $?
}

get_ollama_models() {
    local url=$1
    curl -s --connect-timeout 10 "${url}/api/tags" 2>/dev/null | jq -r '.models[].name' 2>/dev/null || echo ""
}

# Get script directory
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

# Display banner
clear
echo -e "${RED}"
cat << "EOF"
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
EOF
echo -e "${NC}"

echo -e "${WHITE}  Welcome to GooseStrike! This wizard will configure your AI backends.${NC}"
echo ""

# ═══════════════════════════════════════════════════════════════
# STEP 1: AI PROVIDER SELECTION
# ═══════════════════════════════════════════════════════════════

print_header "STEP 1: AI Provider Selection"

echo -e "${WHITE}  How do you want to run your AI models?${NC}"
echo ""
echo -e "${GRAY}    [1] Local Only (Ollama on this machine)${NC}"
echo -e "${GRAY}    [2] Networked Only (Ollama on remote machines)${NC}"
echo -e "${GRAY}    [3] Cloud Only (OpenAI, Anthropic, etc.)${NC}"
echo -e "${GRAY}    [4] Hybrid - Local + Networked${NC}"
echo -e "${GRAY}    [5] Hybrid - Local + Cloud${NC}"
echo -e "${GRAY}    [6] Hybrid - Networked + Cloud${NC}"
echo -e "${GRAY}    [7] Full Stack - All providers${NC}"
echo ""
read -p "    Selection: " provider_choice

# Initialize configuration
LOCAL_ENABLED=false
LOCAL_URL="http://localhost:11434"
NETWORKED_ENABLED=false
NETWORKED_ENDPOINTS=()
CLOUD_ENABLED=false
OPENAI_ENABLED=false
OPENAI_API_KEY=""
ANTHROPIC_ENABLED=false
ANTHROPIC_API_KEY=""
DEFAULT_PROVIDER="ollama"
LOAD_BALANCE_STRATEGY="round-robin"

# Determine what to configure
case $provider_choice in
    1) CONFIGURE_LOCAL=true; CONFIGURE_NETWORKED=false; CONFIGURE_CLOUD=false ;;
    2) CONFIGURE_LOCAL=false; CONFIGURE_NETWORKED=true; CONFIGURE_CLOUD=false ;;
    3) CONFIGURE_LOCAL=false; CONFIGURE_NETWORKED=false; CONFIGURE_CLOUD=true ;;
    4) CONFIGURE_LOCAL=true; CONFIGURE_NETWORKED=true; CONFIGURE_CLOUD=false ;;
    5) CONFIGURE_LOCAL=true; CONFIGURE_NETWORKED=false; CONFIGURE_CLOUD=true ;;
    6) CONFIGURE_LOCAL=false; CONFIGURE_NETWORKED=true; CONFIGURE_CLOUD=true ;;
    7) CONFIGURE_LOCAL=true; CONFIGURE_NETWORKED=true; CONFIGURE_CLOUD=true ;;
    *) CONFIGURE_LOCAL=true; CONFIGURE_NETWORKED=false; CONFIGURE_CLOUD=false ;;
esac

# ═══════════════════════════════════════════════════════════════
# STEP 2: LOCAL OLLAMA CONFIGURATION
# ═══════════════════════════════════════════════════════════════

if [ "$CONFIGURE_LOCAL" = true ]; then
    print_header "STEP 2: Local Ollama Configuration"
    
    print_step "Checking for local Ollama installation..."
    
    if test_ollama_endpoint "$LOCAL_URL"; then
        print_success "Ollama is running at $LOCAL_URL"
        
        models=$(get_ollama_models "$LOCAL_URL")
        if [ -n "$models" ]; then
            print_success "Found models: $(echo $models | tr '\n' ', ')"
        else
            print_warning "No models found. Run: ollama pull llama3.2"
        fi
        
        LOCAL_ENABLED=true
    else
        print_warning "Ollama not detected at $LOCAL_URL"
        
        read -p "    Would you like to install Ollama? (y/n): " install_choice
        if [ "$install_choice" = "y" ]; then
            print_step "Installing Ollama..."
            curl -fsSL https://ollama.com/install.sh | sh
            print_step "Starting Ollama service..."
            ollama serve &
            sleep 3
            
            if test_ollama_endpoint "$LOCAL_URL"; then
                print_success "Ollama installed and running"
                LOCAL_ENABLED=true
            fi
        fi
    fi
fi

# ═══════════════════════════════════════════════════════════════
# STEP 3: NETWORKED OLLAMA CONFIGURATION
# ═══════════════════════════════════════════════════════════════

if [ "$CONFIGURE_NETWORKED" = true ]; then
    print_header "STEP 3: Networked Ollama Configuration"
    
    echo -e "${WHITE}  Configure remote Ollama endpoints${NC}"
    echo ""
    
    add_more=true
    endpoint_num=1
    
    while [ "$add_more" = true ]; do
        echo -e "${CYAN}  ── Endpoint #$endpoint_num ──${NC}"
        echo ""
        
        read -p "    Friendly name (e.g., 'Dell PowerEdge'): " ep_name
        read -p "    IP Address: " ep_ip
        read -p "    Port (default: 11434): " ep_port
        ep_port=${ep_port:-11434}
        
        ep_url="http://${ep_ip}:${ep_port}"
        
        print_step "Testing connection to $ep_url..."
        
        if test_ollama_endpoint "$ep_url"; then
            print_success "Connected to $ep_name"
            NETWORKED_ENDPOINTS+=("$ep_url")
            NETWORKED_ENABLED=true
        else
            print_warning "Could not connect to $ep_url"
            read -p "    Add anyway? (y/n): " keep_ep
            if [ "$keep_ep" = "y" ]; then
                NETWORKED_ENDPOINTS+=("$ep_url")
            fi
        fi
        
        echo ""
        read -p "    Add another endpoint? (y/n): " add_more_choice
        [ "$add_more_choice" != "y" ] && add_more=false
        ((endpoint_num++))
    done
    
    if [ ${#NETWORKED_ENDPOINTS[@]} -gt 1 ]; then
        echo ""
        echo -e "${WHITE}  Load balancing strategy:${NC}"
        echo -e "${GRAY}    [1] Round-robin${NC}"
        echo -e "${GRAY}    [2] Failover (priority-based)${NC}"
        echo -e "${GRAY}    [3] Random${NC}"
        read -p "    Selection: " lb_choice
        
        case $lb_choice in
            1) LOAD_BALANCE_STRATEGY="round-robin" ;;
            2) LOAD_BALANCE_STRATEGY="failover" ;;
            3) LOAD_BALANCE_STRATEGY="random" ;;
        esac
    fi
fi

# ═══════════════════════════════════════════════════════════════
# STEP 4: CLOUD PROVIDER CONFIGURATION
# ═══════════════════════════════════════════════════════════════

if [ "$CONFIGURE_CLOUD" = true ]; then
    print_header "STEP 4: Cloud Provider Configuration"
    
    # OpenAI
    echo -e "${CYAN}  ── OpenAI ──${NC}"
    read -p "    Enable OpenAI? (y/n): " use_openai
    if [ "$use_openai" = "y" ]; then
        read -sp "    OpenAI API Key: " openai_key
        echo ""
        if [[ "$openai_key" == sk-* ]]; then
            OPENAI_ENABLED=true
            OPENAI_API_KEY="$openai_key"
            print_success "OpenAI configured"
        else
            print_warning "Invalid API key format"
        fi
    fi
    
    echo ""
    
    # Anthropic
    echo -e "${CYAN}  ── Anthropic (Claude) ──${NC}"
    read -p "    Enable Anthropic? (y/n): " use_anthropic
    if [ "$use_anthropic" = "y" ]; then
        read -sp "    Anthropic API Key: " anthropic_key
        echo ""
        if [[ "$anthropic_key" == sk-ant-* ]]; then
            ANTHROPIC_ENABLED=true
            ANTHROPIC_API_KEY="$anthropic_key"
            print_success "Anthropic configured"
        else
            print_warning "Invalid API key format"
        fi
    fi
    
    CLOUD_ENABLED=$( [ "$OPENAI_ENABLED" = true ] || [ "$ANTHROPIC_ENABLED" = true ] && echo true || echo false )
fi

# ═══════════════════════════════════════════════════════════════
# STEP 5: GENERATE CONFIGURATION
# ═══════════════════════════════════════════════════════════════

print_header "STEP 5: Generating Configuration"

# Build OLLAMA_ENDPOINTS string
if [ ${#NETWORKED_ENDPOINTS[@]} -gt 0 ]; then
    OLLAMA_ENDPOINTS_STR=$(IFS=,; echo "${NETWORKED_ENDPOINTS[*]}")
elif [ "$LOCAL_ENABLED" = true ]; then
    OLLAMA_ENDPOINTS_STR="$LOCAL_URL"
else
    OLLAMA_ENDPOINTS_STR="http://localhost:11434"
fi

# Generate .env file
print_step "Generating .env file..."

cat > "$PROJECT_ROOT/.env" << EOF
# ═══════════════════════════════════════════════════════════════
# GooseStrike Configuration
# Generated on $(date)
# ═══════════════════════════════════════════════════════════════

# Ollama Configuration
OLLAMA_ENDPOINTS=${OLLAMA_ENDPOINTS_STR}
LOAD_BALANCE_STRATEGY=${LOAD_BALANCE_STRATEGY}

# Cloud Providers
OPENAI_API_KEY=${OPENAI_API_KEY}
ANTHROPIC_API_KEY=${ANTHROPIC_API_KEY}

# Default Settings
DEFAULT_PROVIDER=${DEFAULT_PROVIDER}
DEFAULT_MODEL=llama3.2
EOF

print_success "Created $PROJECT_ROOT/.env"

# ═══════════════════════════════════════════════════════════════
# STEP 6: DOCKER SETUP
# ═══════════════════════════════════════════════════════════════

print_header "STEP 6: Docker Setup"

print_step "Checking Docker..."

if docker version > /dev/null 2>&1; then
    docker_version=$(docker version --format '{{.Server.Version}}')
    print_success "Docker is running (version $docker_version)"
    
    read -p "    Start GooseStrike now? (y/n): " start_now
    if [ "$start_now" = "y" ]; then
        print_step "Building and starting containers..."
        cd "$PROJECT_ROOT"
        docker-compose up -d --build
        
        print_success "GooseStrike is starting!"
        echo ""
        echo -e "${GREEN}    Dashboard: http://localhost:8080${NC}"
        echo ""
    fi
else
    print_warning "Docker is not running"
    echo "    Please start Docker and run: docker-compose up -d --build"
fi

# ═══════════════════════════════════════════════════════════════
# COMPLETE
# ═══════════════════════════════════════════════════════════════

print_header "Installation Complete!"

echo -e "${WHITE}  Configuration Summary:${NC}"
echo ""

if [ "$LOCAL_ENABLED" = true ]; then
    echo -e "${GREEN}    ✓ Local Ollama: $LOCAL_URL${NC}"
fi

for ep in "${NETWORKED_ENDPOINTS[@]}"; do
    echo -e "${GREEN}    ✓ Networked: $ep${NC}"
done

if [ "$OPENAI_ENABLED" = true ]; then
    echo -e "${GREEN}    ✓ OpenAI: Enabled${NC}"
fi

if [ "$ANTHROPIC_ENABLED" = true ]; then
    echo -e "${GREEN}    ✓ Anthropic: Enabled${NC}"
fi

echo ""
echo -e "${CYAN}  Load Balancing: $LOAD_BALANCE_STRATEGY${NC}"
echo ""
echo -e "${WHITE}  To start GooseStrike:${NC}"
echo -e "${GRAY}    cd $PROJECT_ROOT${NC}"
echo -e "${GRAY}    docker-compose up -d${NC}"
echo ""
echo -e "${GREEN}  Dashboard: http://localhost:8080${NC}"
echo ""

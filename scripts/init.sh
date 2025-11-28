#!/bin/bash

echo "=================================================="
echo "  StrikePackageGPT - Initialization Script"
echo "=================================================="
echo ""

# Check for Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    exit 1
fi

if ! command -v docker-compose &> /dev/null; then
    echo "❌ Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

echo "✅ Docker and Docker Compose are installed"

# Create .env if not exists
if [ ! -f .env ]; then
    echo "📄 Creating .env file from template..."
    cp .env.example .env
    echo "✅ Created .env file. Edit it to add API keys if needed."
else
    echo "✅ .env file already exists"
fi

# Create data directory
mkdir -p data
echo "✅ Created data directory"

# Start services
echo ""
echo "🚀 Starting services..."
docker-compose up -d --build

# Wait for services to be ready
echo ""
echo "⏳ Waiting for services to start..."
sleep 10

# Check service health
echo ""
echo "🔍 Checking service health..."

check_service() {
    local url=$1
    local name=$2
    if curl -s "$url" > /dev/null 2>&1; then
        echo "  ✅ $name is healthy"
        return 0
    else
        echo "  ⏳ $name is starting..."
        return 1
    fi
}

check_service "http://localhost:8000/health" "LLM Router"
check_service "http://localhost:8001/health" "HackGPT API"
check_service "http://localhost:8080/health" "Dashboard"

# Pull default Ollama model
echo ""
echo "📥 Pulling default LLM model (llama3.2)..."
echo "   This may take a few minutes on first run..."
docker exec strikepackage-ollama ollama pull llama3.2

echo ""
echo "=================================================="
echo "  ✅ StrikePackageGPT is ready!"
echo "=================================================="
echo ""
echo "  Dashboard: http://localhost:8080"
echo "  API Docs:  http://localhost:8001/docs"
echo "  LLM Router: http://localhost:8000/docs"
echo ""
echo "  To access Kali container:"
echo "    docker exec -it strikepackage-kali bash"
echo ""
echo "  To view logs:"
echo "    docker-compose logs -f"
echo ""
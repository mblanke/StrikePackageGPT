FROM kalilinux/kali-rolling

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update and install essential security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    # Core utilities
    curl \
    wget \
    git \
    vim \
    net-tools \
    iputils-ping \
    dnsutils \
    # Reconnaissance tools
    nmap \
    masscan \
    amass \
    theharvester \
    whatweb \
    dnsrecon \
    fierce \
    # Web testing tools
    nikto \
    gobuster \
    dirb \
    sqlmap \
    # Network tools
    netcat-openbsd \
    tcpdump \
    wireshark-common \
    hydra \
    # Exploitation
    metasploit-framework \
    exploitdb \
    # Scripting
    python3 \
    python3-pip \
    python3-venv \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install additional Python tools
RUN pip3 install --break-system-packages \
    requests \
    beautifulsoup4 \
    shodan \
    censys

# Create workspace directory
WORKDIR /workspace

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

ENTRYPOINT ["/entrypoint.sh"]
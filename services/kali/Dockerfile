FROM kalilinux/kali-rolling

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Configure apt to use direct Kali mirrors (avoid CDN mirrors that get blocked by content filters)
# The mirror.us.cdn-perfprod.com CDN is being blocked by SafeBrowse content filter
RUN echo 'deb http://kali.download/kali kali-rolling main non-free non-free-firmware contrib' > /etc/apt/sources.list && \
    echo 'Acquire::Retries "5";' > /etc/apt/apt.conf.d/80-retries

# Update and install essential security tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    nikto \
    sqlmap \
    gobuster \
    dirb \
    wfuzz \
    hydra \
    john \
    hashcat \
    whois \
    dnsutils \
    net-tools \
    iputils-ping \
    curl \
    wget \
    git \
    vim \
    jq \
    uuid-runtime \
    python3 \
    python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install additional Python tools for command logging and scripting
RUN pip3 install --break-system-packages \
    requests \
    beautifulsoup4 \
    shodan \
    censys

# Create workspace directory
WORKDIR /workspace

# Copy scripts and convert Windows line endings to Unix
COPY entrypoint.sh /entrypoint.sh
COPY command_logger.sh /usr/local/bin/command_logger.sh
COPY capture_wrapper.sh /usr/local/bin/capture
COPY nmap_wrapper.sh /usr/local/bin/nmap

# Convert any Windows line endings (CRLF) to Unix (LF)
RUN sed -i 's/\r$//' /entrypoint.sh /usr/local/bin/command_logger.sh /usr/local/bin/capture /usr/local/bin/nmap
RUN chmod +x /entrypoint.sh /usr/local/bin/command_logger.sh /usr/local/bin/capture /usr/local/bin/nmap

# Create command history directory
RUN mkdir -p /workspace/.command_history

ENTRYPOINT ["/entrypoint.sh"]
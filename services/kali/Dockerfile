FROM kalilinux/kali-rolling

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Configure apt to use reliable mirrors and retry on failure
RUN echo 'Acquire::Retries "3";' > /etc/apt/apt.conf.d/80-retries && \
    echo 'Acquire::http::Timeout "30";' >> /etc/apt/apt.conf.d/80-retries && \
    echo 'deb http://kali.download/kali kali-rolling main non-free non-free-firmware contrib' > /etc/apt/sources.list

# Update and install core Kali tools (smaller, faster, more reliable)
RUN apt-get update && apt-get install -y --no-install-recommends \
    nmap \
    sqlmap \
    hydra \
    john \
    tcpdump \
    netcat-openbsd \
    curl \
    wget \
    git \
    python3 \
    python3-pip \
    whois \
    dnsutils \
    dirb \
    gobuster \
    ffuf \
    seclists \
    smbclient \
    impacket-scripts \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install additional Python tools and utilities for command logging
# Install setuptools first to fix compatibility issues with Python 3.13
RUN pip3 install --break-system-packages setuptools wheel && \
    pip3 install --break-system-packages \
    requests \
    beautifulsoup4 \
    shodan \
    censys

# Install jq and uuid-runtime for command logging
RUN apt-get update && apt-get install -y --no-install-recommends \
    jq \
    uuid-runtime \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Create workspace directory
WORKDIR /workspace

# Copy scripts and fix line endings (in case of Windows CRLF)
COPY entrypoint.sh /entrypoint.sh
COPY command_logger.sh /usr/local/bin/command_logger.sh
COPY capture_wrapper.sh /usr/local/bin/capture
RUN sed -i 's/\r$//' /entrypoint.sh /usr/local/bin/command_logger.sh /usr/local/bin/capture && \
    chmod +x /entrypoint.sh /usr/local/bin/command_logger.sh /usr/local/bin/capture

# Create command history directory
RUN mkdir -p /workspace/.command_history

ENTRYPOINT ["/entrypoint.sh"]
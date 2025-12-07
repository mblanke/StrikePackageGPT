FROM kalilinux/kali-rolling

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update and install ALL Kali tools
# Using kali-linux-everything metapackage for complete tool suite
RUN apt-get update && apt-get install -y --no-install-recommends \
    kali-linux-everything \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install additional Python tools and utilities for command logging
RUN pip3 install --break-system-packages \
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

# Copy scripts
COPY entrypoint.sh /entrypoint.sh
COPY command_logger.sh /usr/local/bin/command_logger.sh
COPY capture_wrapper.sh /usr/local/bin/capture
RUN chmod +x /entrypoint.sh /usr/local/bin/command_logger.sh /usr/local/bin/capture

# Create command history directory
RUN mkdir -p /workspace/.command_history

ENTRYPOINT ["/entrypoint.sh"]
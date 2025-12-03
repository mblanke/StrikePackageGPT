FROM kalilinux/kali-rolling

# Avoid prompts during package installation
ENV DEBIAN_FRONTEND=noninteractive

# Update and install ALL Kali tools
# Using kali-linux-everything metapackage for complete tool suite
RUN apt-get update && apt-get install -y --no-install-recommends \
    kali-linux-everything \
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
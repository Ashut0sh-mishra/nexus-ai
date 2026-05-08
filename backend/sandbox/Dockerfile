# NEXUS sandbox — mirrors the EXACT image used by Manus AI.
# Ubuntu 22.04 + Python 3.10.12 + Node.js 20.18.0
FROM ubuntu:22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    LANG=C.UTF-8 \
    LC_ALL=C.UTF-8

# Base toolchain
RUN apt-get update && apt-get install -y --no-install-recommends \
        software-properties-common \
        build-essential \
        ca-certificates \
        curl \
        wget \
        git \
        unzip \
        gnupg \
        jq \
    && rm -rf /var/lib/apt/lists/*

# Python 3.10.12 (default on Ubuntu 22.04)
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        python3-dev \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && ln -sf /usr/bin/pip3 /usr/local/bin/pip \
    && rm -rf /var/lib/apt/lists/*

# Node.js 20.18.0 via NodeSource
RUN curl -fsSL https://deb.nodesource.com/setup_20.x | bash - \
    && apt-get install -y --no-install-recommends nodejs=20.18.0-1nodesource1 \
        || apt-get install -y --no-install-recommends nodejs \
    && npm install -g npm@10 \
    && rm -rf /var/lib/apt/lists/*

# Common scientific & web libs frequently used by CodeAct snippets
RUN pip install --no-cache-dir \
        numpy==2.1.3 \
        pandas==2.2.3 \
        matplotlib==3.9.2 \
        requests==2.32.3 \
        beautifulsoup4==4.12.3 \
        lxml==5.3.0 \
        pillow==11.0.0

# Locked-down workdir (writable so the agent can scratch files; no network at runtime)
WORKDIR /work
RUN useradd --create-home --uid 1000 sandbox \
    && chown -R sandbox:sandbox /work
USER sandbox

CMD ["python", "-c", "print('nexus-sandbox ready')"]

# Pinned to an exact Python patch + Debian release so rebuilds are reproducible; Dependabot proposes bumps.
FROM python:3.15.0-slim-trixie

# Set environment variables to avoid Python writing .pyc files and to ensure stdout is unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
# - ffmpeg and libopus0: Essential for the future music bot capabilities (voice streaming).
# (No compiler needed: every Python dependency ships as a prebuilt wheel, PyNaCl included.)
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies first to cache this layer
COPY requirements.txt .
# --no-cache-dir: don't keep pip's download cache inside the image (it's never reused there)
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application (owned by root, so the bot itself can't modify its own code)
COPY . .

# Run the bot as an unprivileged user instead of root. UID 1000 is usually the first user on a
# Linux machine, so files the bot writes into the mounted data/ folder belong to you on the host.
# (If `id -u` on your machine isn't 1000: docker compose build --build-arg UID=$(id -u))
ARG UID=1000
RUN useradd --create-home --uid "${UID}" videojoker \
    && mkdir -p /app/data \
    && chown videojoker:videojoker /app/data
USER videojoker

# The release workflow passes the version (e.g. v2026.10.28); local builds say "dev".
# Declared last so changing it never invalidates the cached layers above.
ARG VERSION=dev
ENV VIDEOJOKER_VERSION=${VERSION}

# Start the bot
CMD ["python", "main.py"]

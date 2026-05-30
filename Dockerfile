FROM python:3.11-slim

# Set environment variables to avoid Python writing .pyc files and to ensure stdout is unbuffered
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

WORKDIR /app

# Install system dependencies
# - ffmpeg and libopus0: Essential for the future music bot capabilities (voice streaming).
# - gcc and python3-dev: Often required for compiling python extensions like PyNaCl.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    gcc \
    python3-dev \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install python dependencies first to cache this layer
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install -r requirements.txt

# Copy the rest of the application
COPY . .

# Start the bot
CMD ["python", "main.py"]

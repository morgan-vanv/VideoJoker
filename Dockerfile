FROM python:3.11-slim

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

# Copy the rest of the application
COPY . .

# Start the bot
CMD ["python", "main.py"]

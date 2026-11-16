# The booth's image: a small Python web service, built from the repo root so it can copy booth/:
#   docker build -f booth/Dockerfile -t videojoker-booth .
# Same pinned Python as the bot's image (Dependabot bumps both).
FROM python:3.14.10-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
WORKDIR /app

COPY booth/requirements.txt booth-requirements.txt
RUN pip install --no-cache-dir -r booth-requirements.txt

# Owned by root, run as UID 1000: the booth can't change its own code. It writes nothing to disk at all,
# so it runs fine on a read-only root filesystem.
COPY booth/ booth/
ARG UID=1000
RUN useradd --no-create-home --uid "${UID}" booth
USER booth

ARG VERSION=dev
ENV BOOTH_VERSION=${VERSION}
EXPOSE 8765
CMD ["python", "-m", "booth"]

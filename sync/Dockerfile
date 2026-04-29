FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# Install deps first so source changes don't invalidate the cached layer
COPY requirements.txt .
RUN pip install -r requirements.txt

# Non-root runtime user
RUN adduser --system --group --no-create-home app

# Copy source (bind-mount at /app/src overlays this at runtime)
COPY --chown=app:app . ./src/

USER app

CMD ["python", "src/main.py"]

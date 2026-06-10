# ---------------------------------------------------------------------------
# Gym WhatsApp RAG Agent — Production Image
#
# Build:
#   docker build -t gym-whatsapp-agent .
#
# Run (with .env mounted):
#   docker run -p 8000:8000 --env-file .env gym-whatsapp-agent
#
# Tunnel (Cloudflare):
#   cloudflared tunnel --url http://localhost:8000
# ---------------------------------------------------------------------------

FROM python:3.12-slim

# -- system dependencies ------------------------------------------------
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

# -- application ---------------------------------------------------------
WORKDIR /app

# Install Python dependencies first (caching layer).
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and data.
COPY app/ ./app/
COPY data/ ./data/
COPY media/ ./media/

# Create a non-root user for runtime.
RUN useradd --create-home --shell /bin/bash appuser
RUN chown -R appuser:appuser /app
USER appuser

# -- runtime -------------------------------------------------------------
EXPOSE 8000

# Healthcheck uses a dedicated endpoint that doesn't require a matching
# verify token — avoids coupling the healthcheck to the user's .env value.
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

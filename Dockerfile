# syntax=docker/dockerfile:1
# CPU image by default. For CUDA:
#   docker build --build-arg EXTRAS=cuda -t whisper-hub:cuda .
FROM python:3.12-slim

ARG EXTRAS=""

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    WHUB_HOST=0.0.0.0 \
    WHUB_PORT=8765 \
    WHUB_DATA_DIR=/data

WORKDIR /app

COPY pyproject.toml README.md LICENSE ./
COPY whisper_hub ./whisper_hub

RUN if [ -n "$EXTRAS" ]; then \
        pip install --no-cache-dir ".[${EXTRAS}]"; \
    else \
        pip install --no-cache-dir .; \
    fi

# Run unprivileged; /data and the model cache belong to the app user.
RUN useradd --create-home --uid 1000 app \
    && mkdir -p /data /home/app/.cache/huggingface \
    && chown -R app:app /data /home/app/.cache \
    && chmod 700 /data
USER app
ENV HOME=/home/app
VOLUME ["/data"]

EXPOSE 8765

# start-period covers the first model download/load after setup.
HEALTHCHECK --interval=30s --timeout=5s --start-period=120s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:%s/healthz' % os.environ.get('WHUB_PORT', '8765'), timeout=4)" || exit 1

CMD ["whisper-hub"]

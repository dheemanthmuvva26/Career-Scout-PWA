FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

# fonts-liberation: resume.typ falls back to Liberation Serif.
# typst: baked in at build time so forge never downloads it at request time.
RUN apt-get update \
 && apt-get install -y --no-install-recommends curl xz-utils ca-certificates fonts-liberation \
 && curl -fsSL https://github.com/typst/typst/releases/download/v0.13.0/typst-x86_64-unknown-linux-musl.tar.xz \
    | tar -xJ -C /tmp \
 && mv /tmp/typst-x86_64-unknown-linux-musl/typst /usr/local/bin/typst \
 && rm -rf /tmp/typst-* \
 && apt-get purge -y curl xz-utils && apt-get autoremove -y \
 && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Cloud Run injects PORT (8080 by default).
CMD exec uvicorn api:app --host 0.0.0.0 --port ${PORT:-8080}

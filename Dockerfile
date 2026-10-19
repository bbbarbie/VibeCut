# VibeCut on a Linux host (Render). The Mac-only helpers (Vision faces and
# labels, voice, places, subtitles) don't build here and switch themselves
# off; everything else — the cut, music, captions, export — runs on ffmpeg.

FROM node:22-slim AS ui
WORKDIR /ui
COPY web/frontend/package.json web/frontend/package-lock.json ./
RUN npm ci
COPY web/frontend ./
RUN npm run build

FROM python:3.12-slim
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*
WORKDIR /app
COPY requirements.txt req-core.txt
COPY web/requirements.txt req-web.txt
RUN pip install --no-cache-dir -r req-core.txt -r req-web.txt
COPY . .
COPY --from=ui /ui/dist web/frontend/dist
# Projects, clip indexes, uploads and exports live on the mounted disk.
ENV VIBECUT_CACHE=/data/cache VIBECUT_EXPORTS=/data/exports PORT=8766
EXPOSE 8766
CMD ["sh", "-c", "uvicorn web.backend.app:app --host 0.0.0.0 --port ${PORT}"]

# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json ./
RUN npm install
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends util-linux \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir fastapi uvicorn pydantic

COPY backend/ /app/backend/
COPY --from=frontend-build /build/frontend/dist /app/frontend_dist
COPY overlay_lab/base /app/overlay_lab/base
COPY overlay_lab/sessions/.gitkeep /app/overlay_lab/sessions/.gitkeep

RUN mkdir -p /app/overlay_lab/nodes /app/overlay_lab/sessions

ENV OVERLAY_LAB_ROOT=/app/overlay_lab
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]

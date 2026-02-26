# syntax=docker/dockerfile:1.7

FROM node:20-alpine AS frontend-build
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

FROM python:3.11-slim AS runtime
WORKDIR /app

RUN pip install --no-cache-dir fastapi uvicorn pydantic

COPY backend/ /app/backend/
COPY --from=frontend-build /build/frontend/dist /app/frontend_dist

RUN mkdir -p /app/overlay_lab

ENV OVERLAY_LAB_ROOT=/app/overlay_lab
EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000"]

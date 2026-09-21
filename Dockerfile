# syntax=docker/dockerfile:1
#
# Niyam — single-container deploy.
# Stage 1 builds the React PWA into dist/. Stage 2 serves the API and the
# built app from one FastAPI/uvicorn process (same origin -> no CORS needed).

FROM node:20-alpine AS ui
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY index.html ./
COPY public ./public
COPY src ./src
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}
RUN npm run build

FROM python:3.12-slim AS api
WORKDIR /app
COPY backend/requirements.txt ./backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt
COPY backend ./backend
COPY --from=ui /app/dist ./dist
ENV PYTHONPATH=/app/backend
ENV ALLOWED_ORIGINS=""
EXPOSE 8000
# SQLite-backed prototype: keep worker count low to avoid write contention.
CMD ["uvicorn", "app:app", "--app-dir", "backend", "--host", "0.0.0.0", "--port", "8000", "--workers", "2", "--proxy-headers"]
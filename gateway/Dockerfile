# Stage 1 — Build frontend
FROM node:20-alpine AS frontend-build

WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
ARG VITE_DEMO_TOKEN
ARG VITE_API_BASE
RUN npm run build

# Stage 2 — Gateway
FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir -e .

COPY . .

COPY --from=frontend-build /app/dist /app/frontend/dist

EXPOSE 8000

CMD ["uvicorn", "gateway.main:app", "--host", "0.0.0.0", "--port", "8000"]

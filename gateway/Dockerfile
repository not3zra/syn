FROM node:20-alpine AS frontend-build
ARG VITE_DEMO_TOKEN
ENV VITE_DEMO_TOKEN=$VITE_DEMO_TOKEN
WORKDIR /build
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY pyproject.toml .
RUN pip install --no-cache-dir -e .
COPY gateway/ gateway/
COPY engine/ engine/
COPY --from=frontend-build /build/dist frontend/dist
EXPOSE 8000
CMD uvicorn gateway.main:app --host 0.0.0.0 --port ${PORT:-8000}

# Deployment Guide

1. Copy `.env.example` to `.env` and configure provider credentials.
2. Start the stack:

```bash
docker compose up --build
```

3. Open the services:

- FastAPI: `http://localhost:8000/docs`
- Streamlit: `http://localhost:8501`
- Prometheus: `http://localhost:9090`
- Grafana: `http://localhost:3000`
- Qdrant: `http://localhost:6333/dashboard`

For production, place the API behind an ingress or API gateway, enable `AUTH_ENABLED`, rotate `JWT_SECRET`, configure TLS, configure SQL Server read-only credentials, and send OTLP traces to your observability collector.


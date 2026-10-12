from pathlib import Path
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, StreamingResponse
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from slowapi import Limiter
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address
from starlette.requests import Request

from app.dependencies import get_orchestrator
from app_logging.structured import configure_logging, get_logger
from config.settings import get_settings
from models.schemas import ChatRequest, ChatResponse
from monitoring.observability import CHAT_LATENCY, configure_tracing
from tools.sql_tool import SqlServerTool
from rag.pipeline import RagPipeline
from services.chat_stream import chat_events

settings = get_settings()
configure_logging(settings.log_level)
configure_tracing()
logger = get_logger(__name__)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title=settings.app_name, version="0.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: Response("Rate limit exceeded", status_code=429))
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

UPLOAD_DIR = Path("sample_data/uploads")
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@app.get("/health")
async def health() -> dict[str, str]:
    return {"status": "ok", "environment": settings.app_env}


@app.get("/metrics")
async def metrics() -> Response:
    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/config/status")
async def config_status() -> dict[str, object]:
    return {
        "app_env": settings.app_env,
        "llm_provider": settings.llm_provider,
        "llm_model": settings.llm_model,
        "qdrant_enabled": settings.qdrant_enabled,
        "qdrant_url": settings.qdrant_url,
        "sqlserver_host": settings.sqlserver_host,
        "sqlserver_database": settings.sqlserver_database,
        "sqlserver_driver": settings.sqlserver_driver,
        "sqlserver_trusted_connection": settings.sqlserver_trusted_connection,
    }


@app.get("/sql/health")
async def sql_health() -> dict[str, object]:
    return SqlServerTool(settings).diagnostics()


@app.post("/chat", response_model=ChatResponse)
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def chat(request: Request, payload: ChatRequest, orchestrator=Depends(get_orchestrator)) -> ChatResponse:
    with CHAT_LATENCY.time():
        logger.info("chat_request", extra={"extra": {"session_id": payload.session_id, "query": payload.query}})
        return await orchestrator.chat(payload)


@app.post("/upload")
async def upload(files: list[UploadFile] = File(...)) -> dict[str, list[str]]:
    saved: list[str] = []
    for file in files:
        if not file.filename:
            raise HTTPException(status_code=400, detail="Uploaded file must have a filename")
        target = UPLOAD_DIR / f"{uuid4()}-{Path(file.filename).name}"
        target.write_bytes(await file.read())
        saved.append(str(target))
    return {"files": saved}


@app.post("/chat/stream")
@limiter.limit(f"{settings.rate_limit_per_minute}/minute")
async def chat_stream(request: Request, payload: ChatRequest, orchestrator=Depends(get_orchestrator)):
    async def measured_events():
        with CHAT_LATENCY.time():
            async for event in chat_events(orchestrator, payload):
                yield event
    return StreamingResponse(measured_events(), media_type="application/x-ndjson",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@app.post("/ingest")
async def ingest(paths: list[str], session_id: str | None = None, orchestrator=Depends(get_orchestrator)) -> dict[str, int]:
    total = 0
    pipeline = orchestrator.rag
    if session_id:
        if session_id not in orchestrator.session_rag:
            # Chat uploads stay local: never write them to the shared vector collection.
            local_settings = settings.model_copy(update={"qdrant_enabled": False})
            orchestrator.session_rag[session_id] = RagPipeline(local_settings)
        pipeline = orchestrator.session_rag[session_id]
    for raw_path in paths:
        path = Path(raw_path)
        if not path.exists():
            raise HTTPException(status_code=404, detail=f"File not found: {raw_path}")
        total += pipeline.ingest_path(path)
    return {"chunks": total}

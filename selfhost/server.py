"""Single-user self-hosted API and static React chat UI."""

import logging
import os
import secrets
import threading
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from fastapi.staticfiles import StaticFiles
from openai import OpenAIError

from agents.crypto_tools import analyze_crypto
from integrations.crypto_data import EXCHANGES, TIMEFRAMES, CryptoDataError, CryptoDataSource, CryptoQuery
from selfhost.agent import chat, llm_settings
from selfhost.models import AnalysisRequest, ChatRequest
from selfhost.store import ReportStore, access_token

logger = logging.getLogger(__name__)
bearer = HTTPBearer(auto_error=False)


@asynccontextmanager
async def lifespan(app: FastAPI):
    data_dir = Path(os.getenv("SELFHOST_DATA_DIR", ".wyckoff/selfhost"))
    data_dir.mkdir(parents=True, exist_ok=True)
    app.state.token = access_token(data_dir)
    app.state.store = ReportStore(data_dir / "reports.sqlite3")
    app.state.source = CryptoDataSource()
    app.state.slots = threading.BoundedSemaphore(2)
    yield


def authenticated(request: Request, credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)]):
    if credentials is None or not secrets.compare_digest(credentials.credentials, request.app.state.token):
        raise HTTPException(401, "访问口令无效，请重新登录")


def create_app() -> FastAPI:
    app = FastAPI(title="Wyckoff Crypto", lifespan=lifespan, docs_url=None, redoc_url=None, openapi_url=None)
    app.middleware("http")(request_boundary)
    app.get("/api/health")(health)
    guarded = [Depends(authenticated)]
    app.get("/api/config", dependencies=guarded)(config)
    app.get("/api/history", dependencies=guarded)(history)
    app.post("/api/analyze", dependencies=guarded)(analyze)
    app.post("/api/chat", dependencies=guarded)(conversation)
    dist = Path(os.getenv("SELFHOST_STATIC_DIR", "web/apps/web/dist-selfhost"))
    if (dist / "assets").is_dir():
        app.mount("/assets", StaticFiles(directory=dist / "assets"), name="assets")
    app.state.dist = dist
    app.get("/")(index)
    app.get("/chat")(index)
    return app


async def request_boundary(request: Request, call_next):
    if request.method == "POST":
        if request.headers.get("content-type", "").split(";")[0] != "application/json":
            return JSONResponse({"detail": "application/json required"}, status_code=415)
        body = bytearray()
        async for chunk in request.stream():
            body.extend(chunk)
            if len(body) > 65536:
                return JSONResponse({"detail": "请求超过 64 KiB"}, status_code=413)
        request._body = bytes(body)
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "no-referrer"
    response.headers["Content-Security-Policy"] = (
        "default-src 'self'; script-src 'self'; style-src 'self' 'unsafe-inline'; "
        "img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'; base-uri 'self'"
    )
    response.headers["Cache-Control"] = "no-store"
    return response


def health():
    return {"status": "ok", "service": "wyckoff-crypto"}


def config():
    return {"exchanges": EXCHANGES, "timeframes": list(TIMEFRAMES), "llm_enabled": bool(llm_settings()["model"])}


def history(request: Request):
    return request.app.state.store.list()


def _run(request: Request, operation):
    if not request.app.state.slots.acquire(blocking=False):
        raise HTTPException(429, "分析任务繁忙，请稍后重试")
    try:
        return operation()
    except CryptoDataError as exc:
        raise HTTPException(502, str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    except OpenAIError as exc:
        logger.warning("Model request failed: %s", type(exc).__name__)
        raise HTTPException(502, "模型连接失败，请检查服务器模型地址、名称和 Key，或稍后重试") from exc
    finally:
        request.app.state.slots.release()


def analyze(body: AnalysisRequest, request: Request):
    result = _run(request, lambda: analyze_crypto(request.app.state.source, CryptoQuery(**body.model_dump())))
    request.app.state.store.save(result)
    return result


def conversation(body: ChatRequest, request: Request):
    if body.messages[-1].role != "user":
        raise HTTPException(400, "最后一条消息必须来自用户")
    result = _run(request, lambda: chat(request.app.state.source, body))
    for report in result["reports"]:
        request.app.state.store.save(report)
    return result


def index(request: Request):
    path = request.app.state.dist / "index.html"
    if not path.exists():
        raise HTTPException(503, "Web UI 尚未构建，请使用 Docker Compose 启动")
    return FileResponse(path)


app = create_app()

"""
Voice Agent API (FastAPI)
=========================
    uvicorn app.main:app --reload --port 8000

Endpoints:
    GET  /api/health    -> checks the connection to the Sales MCP server (and through it, the DB)
    GET  /api/outlets   -> outlets for the dropdown
    POST /api/chat      -> question (text) -> answer + charts/tables
    POST /api/stt       -> audio (webm/wav) -> text  (Groq Whisper)
"""
from __future__ import annotations

import logging
import time
import uuid
from typing import Literal

from fastapi import FastAPI, File, HTTPException, Request, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from openai import AsyncOpenAI
from pydantic import BaseModel, Field

from .agent import SalesAgent
from .config import settings
from .logging_setup import setup_logging

setup_logging(settings.log_level, settings.log_format, settings.log_file)
log = logging.getLogger("api")

app = FastAPI(title="POS Voice Agent", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.cors_origins.split(",") if o.strip()],
    allow_methods=["*"],
    allow_headers=["*"],
)



@app.middleware("http")
async def access_log(request: Request, call_next):
    """One log line per HTTP request, with a request id that is also returned in the X-Request-ID header."""
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    request.state.rid = rid
    t0 = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        response.headers["X-Request-ID"] = rid
        return response
    finally:
        ms = int((time.perf_counter() - t0) * 1000)
        level = logging.ERROR if status >= 500 else logging.WARNING if (status >= 400 or ms > settings.slow_request_ms) else logging.INFO
        log.log(level, "%s %s -> %s in %s ms", request.method, request.url.path, status, ms,
                extra={"event": "http", "request_id": rid, "method": request.method, "path": request.url.path,
                       "status": status, "duration_ms": ms,
                       "client": request.client.host if request.client else None})


agent = SalesAgent()
stt_client = AsyncOpenAI(base_url=settings.llm_base_url, api_key=settings.llm_api_key or "missing-key")

STT_PROMPT = (
    "Restaurant POS sales question. "
    "Terms: sales, bills, Swiggy, Zomato, UPI, cash, card, dine-in, takeaway, "
    "top items, outlet, Koramangala, Bandra, Connaught Place."
)


def explain(exc: BaseException) -> str:
    """Readable message for errors coming from the MCP connection (unwraps task-group errors)."""
    while getattr(exc, "exceptions", None):
        exc = exc.exceptions[0]
    msg = str(exc) or type(exc).__name__
    if "error response" in msg or "401" in msg or "nauthorized" in msg:
        return (f"Sales MCP server at {settings.mcp_server_url} rejected the request. "
                "Check that MCP_AUTH_TOKEN in backend/.env matches mcp-server/.env.")
    if "connect" in msg.lower() or "ConnectError" in type(exc).__name__:
        return f"Cannot reach the Sales MCP server at {settings.mcp_server_url}. Is it running?"
    return msg


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(max_length=4000)


class Outlet(BaseModel):
    id: int
    name: str


class ChatRequest(BaseModel):
    messages: list[ChatMessage] = Field(min_length=1)
    outlet: Outlet | None = None


@app.get("/api/health")
async def health():
    out = {"api": "ok", "model": settings.llm_model, "llm_key_set": bool(settings.llm_api_key)}
    try:
        outlets = await agent.list_outlets()
        out["mcp"] = "ok"
        out["db"] = f"ok ({len(outlets)} outlets)"
    except Exception as exc:
        out["mcp"] = f"error: {explain(exc)}"
    return out


@app.get("/api/outlets")
async def outlets():
    try:
        rows = await agent.list_outlets()
    except Exception as exc:
        raise HTTPException(503, explain(exc)) from exc
    return [{"id": r["OutletId"], "name": r["OutletName"], "city": r.get("City")} for r in rows]


@app.post("/api/chat")
async def chat(req: ChatRequest, request: Request):
    if req.messages[-1].role != "user":
        raise HTTPException(400, "Last message must be from the user")
    if not settings.llm_api_key:
        raise HTTPException(500, "LLM_API_KEY is not set in backend/.env")
    # TODO (production): read the user's role/outlet from the JWT and set forced_outlet_id
    try:
        res = await agent.run(
            [m.model_dump() for m in req.messages],
            selected_outlet=req.outlet.model_dump() if req.outlet else None,
        )
        failed = [c["tool"] for c in res["tool_calls"] if not c["ok"]]
        log.log(logging.WARNING if failed else logging.INFO,
                "chat answered in %s ms, tools=%s, tokens=%s", res["elapsed_ms"],
                [c["tool"] for c in res["tool_calls"]], res["usage"]["total_tokens"],
                extra={"event": "chat", "request_id": request.state.rid,
                       "question": req.messages[-1].content[:300] if settings.log_questions else None,
                       "outlet": req.outlet.name if req.outlet else "All outlets",
                       "answer_chars": len(res["answer"]),
                       "tools": res["tool_calls"], "failed_tools": failed,
                       "llm_rounds": res["llm_rounds"], "model": res["model"],
                       "prompt_tokens": res["usage"]["prompt_tokens"],
                       "completion_tokens": res["usage"]["completion_tokens"],
                       "total_tokens": res["usage"]["total_tokens"],
                       "duration_ms": res["elapsed_ms"]})
        internal = {"tool", "report", "procedure"}
        return {
            "answer": res["answer"],
            "visuals": [{k: v for k, v in vis.items() if k not in internal} for vis in res["visuals"]],
        }
    except Exception as exc:
        log.exception("chat failed: %s", explain(exc),
                      extra={"event": "chat_error", "request_id": request.state.rid,
                             "question": req.messages[-1].content[:300] if settings.log_questions else None})
        raise HTTPException(502, f"Agent error: {explain(exc)}") from exc


@app.post("/api/stt")
async def stt(request: Request, audio: UploadFile = File(...)):
    data = await audio.read()
    t0 = time.perf_counter()
    if len(data) < 1000:
        raise HTTPException(400, "Recording too short")
    if len(data) > 20 * 1024 * 1024:
        raise HTTPException(413, "Recording too large")
    kwargs = {"model": settings.stt_model, "file": (audio.filename or "audio.webm", data), "prompt": STT_PROMPT}
    if settings.stt_language:
        kwargs["language"] = settings.stt_language
    try:
        tr = await stt_client.audio.transcriptions.create(**kwargs)
    except Exception as exc:
        log.exception("stt failed", extra={"event": "stt_error", "request_id": request.state.rid, "audio_bytes": len(data)})
        raise HTTPException(502, f"Speech-to-text error: {exc}") from exc
    text = (tr.text or "").strip()
    log.info("stt %s bytes -> %s chars", len(data), len(text),
             extra={"event": "stt", "request_id": request.state.rid, "audio_bytes": len(data), "model": settings.stt_model,
                    "text": text[:300] if settings.log_questions else None,
                    "duration_ms": int((time.perf_counter() - t0) * 1000)})
    return {"text": text}

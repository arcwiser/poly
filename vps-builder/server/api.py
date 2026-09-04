import os
import json
import time
import logging
import asyncio
from typing import Optional, List
from collections import defaultdict
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Depends, Header, Request
from fastapi.responses import Response, HTMLResponse
from pydantic import BaseModel, Field

from .build_manager import execute_build, VALID_PROJECTS, VALID_OPTIMIZATIONS
from .transformations import AVAILABLE_TRANSFORMATIONS
from .analyzer import compare_binaries
from .discord_logger import discord_log_server_start

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ── rate limiter ────────────────────────────────────────────

RATE_LIMIT = int(os.environ.get("POLYLAB_RATE_LIMIT", "30"))
RATE_WINDOW = 60  # seconds
MAX_CONCURRENT = int(os.environ.get("POLYLAB_MAX_CONCURRENT", "4"))

_rate_store: dict[str, list[float]] = defaultdict(list)
_build_semaphore = asyncio.Semaphore(MAX_CONCURRENT)


def _check_rate(ip: str):
    now = time.time()
    _rate_store[ip] = [t for t in _rate_store[ip] if now - t < RATE_WINDOW]
    if len(_rate_store[ip]) >= RATE_LIMIT:
        raise HTTPException(status_code=429, detail=f"Rate limit: {RATE_LIMIT} requests per {RATE_WINDOW}s")
    _rate_store[ip].append(now)


# ── app ─────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    token = os.environ.get("POLYLAB_API_TOKEN", "")
    host = os.environ.get("POLYLAB_HOST", "0.0.0.0")
    port = int(os.environ.get("POLYLAB_PORT", "8000"))
    discord_log_server_start(host, port, token)
    yield

app = FastAPI(
    title="LLVM Polymorphic Compilation Research Platform",
    description=(
        "Research API for studying compiler-generated binary diversity.\n\n"
        "Send a `POST /build` with a project name and seed to receive a "
        "Hello World executable compiled through a seed-deterministic LLVM "
        "transformation pipeline."
    ),
    version="0.2.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)


# ── auth ────────────────────────────────────────────────────

def get_api_token() -> str:
    token = os.environ.get("POLYLAB_API_TOKEN")
    if not token:
        raise HTTPException(status_code=500, detail="POLYLAB_API_TOKEN not set")
    return token


async def verify_token(
    request: Request,
    authorization: Optional[str] = Header(None),
    token: str = Depends(get_api_token),
):
    _check_rate(request.client.host if request.client else "unknown")

    if authorization is None:
        raise HTTPException(status_code=401, detail="Missing Authorization header. Use: Bearer <token>")
    parts = authorization.split()
    if len(parts) != 2 or parts[0] != "Bearer":
        raise HTTPException(status_code=401, detail="Invalid format. Use: Bearer <token>")
    if parts[1] != token:
        raise HTTPException(status_code=403, detail="Invalid API token")


# ── models ──────────────────────────────────────────────────

class BuildRequest(BaseModel):
    project: str = Field(..., description="Project name (only 'hello-world' supported)")
    seed: int = Field(..., ge=0, le=999_999_999, description="Deterministic build seed")
    optimization: str = Field(default="O2", description="Optimization level")
    transformations: Optional[List[str]] = Field(default=None, description="Specific transformations to apply (null = defaults)")

    class Config:
        json_schema_extra = {
            "example": {
                "project": "hello-world",
                "seed": 12345,
                "optimization": "O2",
                "transformations": None,
            }
        }


class CompareRequest(BaseModel):
    sha256_a: str = Field(..., description="SHA-256 of first build")
    sha256_b: str = Field(..., description="SHA-256 of second build")


# ── routes ──────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def root():
    return """<!DOCTYPE html>
<html><head><title>Polylab</title>
<style>
  body{font-family:system-ui;max-width:700px;margin:60px auto;padding:0 20px;color:#1a1a2e}
  h1{color:#5865F2} code{background:#f0f0f0;padding:2px 6px;border-radius:3px}
  a{color:#5865F2} .muted{color:#666}
</style></head>
<body>
<h1>LLVM Polymorphic Compilation Research Platform</h1>
<p>Research API for studying compiler-generated binary diversity.</p>
<ul>
  <li><a href="/docs">Swagger UI</a> — interactive API docs</li>
  <li><a href="/redoc">ReDoc</a> — reference docs</li>
  <li><code>GET /health</code> — health check</li>
  <li><code>GET /info</code> — server info &amp; toolchain</li>
  <li><code>POST /build</code> — compile a variant</li>
  <li><code>GET /transformations</code> — list available transformations</li>
</ul>
<p class="muted">github.com/arcwiser/poly</p>
</body></html>"""


@app.get("/health")
async def health():
    return {"status": "ok", "version": "0.2.0"}


@app.get("/info")
async def info():
    from .compiler import get_toolchain_info
    toolchain = get_toolchain_info()
    return {
        "server": "LLVM Polymorphic Compilation Research Platform",
        "version": "0.2.0",
        "toolchain": toolchain,
        "valid_projects": VALID_PROJECTS,
        "valid_optimizations": VALID_OPTIMIZATIONS,
        "available_transformations": list(AVAILABLE_TRANSFORMATIONS.keys()),
        "rate_limit": f"{RATE_LIMIT}/{RATE_WINDOW}s",
        "max_concurrent_builds": MAX_CONCURRENT,
    }


@app.get("/transformations")
async def list_transformations():
    transforms = {}
    for name, cls in AVAILABLE_TRANSFORMATIONS.items():
        instance = cls(seed=0)
        transforms[name] = {
            "name": instance.name,
            "version": instance.version,
            "description": cls.__doc__ or "IR transformation",
        }
    return {"transformations": transforms, "defaults": ["constant_expr", "block_reorder", "arithmetic_restructure"]}


@app.post("/build")
async def build(request: BuildRequest, _auth: str = Depends(verify_token)):
    if request.project not in VALID_PROJECTS:
        raise HTTPException(status_code=400, detail=f"Invalid project. Valid: {VALID_PROJECTS}")
    if request.optimization not in VALID_OPTIMIZATIONS:
        raise HTTPException(status_code=400, detail=f"Invalid optimization. Valid: {VALID_OPTIMIZATIONS}")
    if request.transformations:
        invalid = [t for t in request.transformations if t not in AVAILABLE_TRANSFORMATIONS]
        if invalid:
            raise HTTPException(status_code=400, detail=f"Invalid transformations: {invalid}. Available: {list(AVAILABLE_TRANSFORMATIONS.keys())}")

    async with _build_semaphore:
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: execute_build(
                project=request.project,
                seed=request.seed,
                optimization=request.optimization,
                transformations=request.transformations,
            ),
        )

    if not result["success"]:
        raise HTTPException(status_code=500, detail={"error": result.get("error"), "phase": result.get("phase")})

    return Response(
        content=result["artifact_bytes"],
        media_type="application/octet-stream",
        headers={
            "X-Build-ID": result["build_id"],
            "X-Build-Manifest": json.dumps(result["manifest"]),
            "X-Build-Seed": str(request.seed),
            "X-Build-Elapsed": str(result["elapsed_seconds"]),
            "Content-Disposition": f'attachment; filename="hello_seed_{request.seed}"',
        },
    )


@app.get("/build/{build_id}/manifest")
async def get_manifest(build_id: str, _auth: str = Depends(verify_token)):
    from pathlib import Path
    work_dir = os.environ.get("POLYLAB_WORK_DIR", "/tmp/polylab")
    manifest_path = Path(work_dir) / build_id / "manifest.json"
    if not manifest_path.exists():
        raise HTTPException(status_code=404, detail="Build not found or already cleaned up")
    return json.loads(manifest_path.read_text())


@app.post("/compare")
async def compare(request: CompareRequest, _auth: str = Depends(verify_token)):
    from pathlib import Path
    work_dir = os.environ.get("POLYLAB_WORK_DIR", "/tmp/polylab")

    found_a, found_b = None, None
    for d in Path(work_dir).iterdir():
        if not d.is_dir():
            continue
        manifest_path = d / "manifest.json"
        if manifest_path.exists():
            m = json.loads(manifest_path.read_text())
            if m.get("artifact_sha256") == request.sha256_a:
                found_a = m
            elif m.get("artifact_sha256") == request.sha256_b:
                found_b = m

    if not found_a or not found_b:
        raise HTTPException(status_code=404, detail="One or both builds not found (artifacts may have been cleaned up)")

    return {
        "build_a": {"build_id": found_a["build_id"], "seed": found_a["seed"], "sha256": found_a["artifact_sha256"]},
        "build_b": {"build_id": found_b["build_id"], "seed": found_b["seed"], "sha256": found_b["artifact_sha256"]},
        "sha_match": found_a["artifact_sha256"] == found_b["artifact_sha256"],
        "file_size_diff": abs(found_a.get("file_size", 0) - found_b.get("file_size", 0)),
        "text_size_diff": abs(found_a.get("text_size", 0) - found_b.get("text_size", 0)),
    }


# ── entry ───────────────────────────────────────────────────

def run_server(host: str = "0.0.0.0", port: int = 8000):
    import uvicorn
    uvicorn.run(app, host=host, port=port)

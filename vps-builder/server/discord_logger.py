import json
import os
import time
import urllib.request
import urllib.error
import threading
from datetime import datetime, timezone
from typing import Optional, Any

WEBHOOK_URL = os.environ.get("POLYLAB_DISCORD_WEBHOOK", "")
BUILD_STARTS: dict[str, float] = {}
_QUEUE_LOCK = threading.Lock()
ACTIVE_BUILDS = 0
QUEUED_BUILDS = 0

COLORS = {
    "info":    0x5865F2,
    "success": 0x57F287,
    "warning": 0xFEE75C,
    "error":   0xED4245,
    "purple":  0xEB459E,
}


def _post(payload: dict):
    if not WEBHOOK_URL:
        return

    def _do():
        try:
            data = json.dumps(payload).encode("utf-8")
            req = urllib.request.Request(
                WEBHOOK_URL,
                data=data,
                headers={"Content-Type": "application/json"},
                method="POST",
            )
            urllib.request.urlopen(req, timeout=10)
        except Exception:
            pass

    threading.Thread(target=_do, daemon=True).start()


def _embed(title: str, description: str, color: int, fields: Optional[dict] = None, footer: str = ""):
    embed: dict[str, Any] = {
        "title": title,
        "description": description[:4000],
        "color": color,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }
    if fields:
        embed["fields"] = [
            {"name": str(k)[:256], "value": str(v)[:1024], "inline": len(str(v)) < 60}
            for k, v in fields.items() if v is not None
        ]
    if footer:
        embed["footer"] = {"text": footer[:2048]}
    return embed


# ── server lifecycle ────────────────────────────────────────

def discord_log_server_start(host: str, port: int, token_hint: str):
    _post({"embeds": [_embed(
        "Server Started",
        "LLVM Polymorphic Compilation Research Platform is **online**",
        COLORS["success"],
        {
            "Host": f"`{host}`",
            "Port": f"`{port}`",
            "Token": f"`{token_hint[:8]}...`" if token_hint else "*none*",
            "Docs": f"`http://{host}:{port}/docs`",
        },
        footer="polylab v0.2.0",
    )]})


def discord_log_server_stop(reason: str = "shutdown"):
    _post({"embeds": [_embed(
        "Server Stopped",
        f"Reason: {reason}",
        COLORS["warning"],
    )]})


# ── build lifecycle ─────────────────────────────────────────

def discord_log_build_start(build_id: str, seed: int, optimization: str, project: str = "hello-world"):
    global ACTIVE_BUILDS, QUEUED_BUILDS
    with _QUEUE_LOCK:
        BUILD_STARTS[build_id] = time.time()
        ACTIVE_BUILDS += 1
        if QUEUED_BUILDS > 0:
            QUEUED_BUILDS -= 1

    _post({"embeds": [_embed(
        "Build Started",
        f"`{build_id[:8]}`",
        COLORS["warning"],
        {
            "Project": f"`{project}`",
            "Seed": f"`{seed}`",
            "Optimization": f"`{optimization}`",
            "Queue": f"{QUEUED_BUILDS} queued / {ACTIVE_BUILDS} active",
        },
    )]})


def discord_log_build_success(
    build_id: str,
    seed: int,
    sha256: str,
    file_size: int,
    text_size: int,
    elapsed: float,
    transformations: list,
):
    global ACTIVE_BUILDS
    with _QUEUE_LOCK:
        BUILD_STARTS.pop(build_id, None)
        ACTIVE_BUILDS = max(0, ACTIVE_BUILDS - 1)

    names = ", ".join(t.get("name", "?") for t in transformations) or "none"

    _post({"embeds": [_embed(
        "Build Completed",
        f"`{build_id[:8]}` — **success**",
        COLORS["success"],
        {
            "Seed": f"`{seed}`",
            "SHA-256": f"`{sha256[:32]}...`",
            "File Size": f"`{file_size:,}` bytes",
            ".text Size": f"`{text_size:,}` bytes",
            "Time": f"`{elapsed:.2f}s`",
            "Transformations": names,
            "Queue": f"{ACTIVE_BUILDS} active",
        },
    )]})


def discord_log_build_failure(build_id: str, seed: int, error: str, phase: str = "unknown"):
    global ACTIVE_BUILDS
    with _QUEUE_LOCK:
        BUILD_STARTS.pop(build_id, None)
        ACTIVE_BUILDS = max(0, ACTIVE_BUILDS - 1)

    _post({"embeds": [_embed(
        "Build Failed",
        f"`{build_id[:8]}` — **{phase}**",
        COLORS["error"],
        {
            "Seed": f"`{seed}`",
            "Phase": f"`{phase}`",
            "Error": error[:500],
            "Queue": f"{ACTIVE_BUILDS} active",
        },
    )]})


# ── experiment ──────────────────────────────────────────────

def discord_log_experiment(total: int, successful: int, unique: int, elapsed: float):
    _post({"embeds": [_embed(
        "Experiment Complete",
        f"Multi-seed experiment finished in `{elapsed:.1f}s`",
        COLORS["purple"],
        {
            "Total Builds": f"`{total}`",
            "Successful": f"`{successful}`",
            "Unique Hashes": f"`{unique}`",
            "Diversity": f"`{unique}/{total}` unique",
        },
        footer="polylab experiment",
    )]})


# ── queue status ────────────────────────────────────────────

def discord_log_queue_stats(active: int, queued: int):
    _post({"embeds": [_embed(
        "Queue Status",
        "Build queue status update",
        COLORS["info"],
        {
            "Active Builds": f"`{active}`",
            "Queued Builds": f"`{queued}`",
        },
    )]})

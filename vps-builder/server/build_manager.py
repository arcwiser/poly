import uuid
import logging
import time
from typing import Dict, Any, Optional

from .compiler import BuildWorkspace, get_toolchain_info, generate_ir, compile_from_ir, test_executable
from .transformations import TransformationEngine
from .analyzer import analyze_binary
from .manifest import create_manifest, save_manifest
from .cleanup import cleanup_workspace
from .discord_logger import (
    discord_log_build_start,
    discord_log_build_success,
    discord_log_build_failure,
)

logger = logging.getLogger(__name__)

VALID_PROJECTS = ["hello-world"]
VALID_OPTIMIZATIONS = ["O0", "O1", "O2", "O3"]
BUILD_PHASES = ["validation", "workspace", "toolchain", "ir_generation", "transformation", "compilation", "testing", "analysis", "manifest"]


def execute_build(
    project: str,
    seed: int,
    optimization: str = "O2",
    transformations: Optional[list] = None,
) -> Dict[str, Any]:
    # ── validation ──
    if project not in VALID_PROJECTS:
        return {"success": False, "error": f"Invalid project: {project}. Valid: {VALID_PROJECTS}", "phase": "validation"}
    if optimization not in VALID_OPTIMIZATIONS:
        return {"success": False, "error": f"Invalid optimization: {optimization}. Valid: {VALID_OPTIMIZATIONS}", "phase": "validation"}
    if not isinstance(seed, int) or seed < 0:
        return {"success": False, "error": "Seed must be a non-negative integer", "phase": "validation"}

    build_id = str(uuid.uuid4())
    workspace = BuildWorkspace(build_id)

    discord_log_build_start(build_id, seed, optimization, project)

    try:
        t0 = time.time()

        # ── workspace ──
        workspace.create()
        logger.info(f"[{build_id[:8]}] workspace created")

        # ── toolchain ──
        toolchain_info = get_toolchain_info()
        logger.info(f"[{build_id[:8]}] toolchain: {toolchain_info.get('compiler_version', '?')}")

        # ── IR generation ──
        ir_info = generate_ir(workspace, optimization)
        logger.info(f"[{build_id[:8]}] IR: {ir_info['ir_size']} bytes, {ir_info['ir_lines']} lines")

        # ── transformations ──
        original_ir = workspace.ir_path.read_text(encoding="utf-8")
        engine = TransformationEngine(seed=seed, enabled=transformations)
        transformed_ir = engine.apply(original_ir)
        workspace.transformed_ir_path.write_text(transformed_ir, encoding="utf-8")
        changed_count = sum(1 for t in engine.applied if t.get("changed"))
        logger.info(f"[{build_id[:8]}] {len(engine.applied)} transforms applied, {changed_count} changed IR")

        # ── compilation ──
        compile_from_ir(workspace, optimization)
        exe_size = workspace.executable_path.stat().st_size
        logger.info(f"[{build_id[:8]}] compiled: {exe_size:,} bytes")

        # ── testing ──
        test_result = test_executable(workspace)
        logger.info(f"[{build_id[:8]}] test: exit={test_result['exit_code']}, passed={test_result['passed']}")
        if not test_result["passed"]:
            err = f"exit={test_result['exit_code']}, stdout={test_result['stdout']!r}"
            discord_log_build_failure(build_id, seed, err, "testing")
            return {"success": False, "build_id": build_id, "error": err, "phase": "testing"}

        # ── analysis ──
        binary_metrics = analyze_binary(workspace.executable_path, ir_path=workspace.transformed_ir_path)
        logger.info(f"[{build_id[:8]}] sha256={binary_metrics['sha256'][:16]}...")

        # ── manifest ──
        pipeline_desc = engine.describe_pipeline()
        manifest = create_manifest(
            build_id=build_id,
            seed=seed,
            optimization=optimization,
            toolchain_info=toolchain_info,
            transformation_pipeline=pipeline_desc,
            binary_metrics=binary_metrics,
            test_result=test_result,
        )
        save_manifest(manifest, workspace.manifest_path)

        artifact_bytes = workspace.get_executable_bytes()
        elapsed = time.time() - t0

        discord_log_build_success(
            build_id=build_id,
            seed=seed,
            sha256=binary_metrics["sha256"],
            file_size=binary_metrics["file_size"],
            text_size=binary_metrics.get("text_size", 0),
            elapsed=elapsed,
            transformations=pipeline_desc.get("applied", []),
        )

        return {
            "success": True,
            "build_id": build_id,
            "manifest": manifest,
            "artifact_bytes": artifact_bytes,
            "elapsed_seconds": round(elapsed, 3),
        }

    except Exception as e:
        logger.error(f"[{build_id[:8]}] failed: {e}", exc_info=True)
        discord_log_build_failure(build_id, seed, str(e), "unknown")
        return {"success": False, "build_id": build_id, "error": str(e), "phase": "unknown"}
    finally:
        cleanup_workspace(build_id)
        logger.info(f"[{build_id[:8]}] workspace cleaned up")

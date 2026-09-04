import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, Optional


def create_manifest(
    build_id: str,
    seed: int,
    optimization: str,
    toolchain_info: Dict[str, Any],
    transformation_pipeline: Dict[str, Any],
    binary_metrics: Dict[str, Any],
    test_result: Dict[str, Any],
    source_revision: str = "local",
) -> Dict[str, Any]:
    manifest = {
        "build_id": build_id,
        "seed": seed,
        "source_revision": source_revision,
        "compiler": toolchain_info.get("compiler", "clang"),
        "compiler_version": toolchain_info.get(
            "compiler_version", "unknown"
        ),
        "llvm_version": toolchain_info.get("llvm_version", "unknown"),
        "target_triple": toolchain_info.get("target_triple", "unknown"),
        "optimization": optimization,
        "transformations": transformation_pipeline.get("applied", []),
        "transformation_config": {
            "enabled": transformation_pipeline.get(
                "enabled_transformations", []
            ),
            "total": transformation_pipeline.get(
                "total_transformations", 0
            ),
        },
        "artifact_sha256": binary_metrics.get("sha256", ""),
        "file_size": binary_metrics.get("file_size", 0),
        "text_size": binary_metrics.get("text_size", 0),
        "section_count": binary_metrics.get("section_count", 0),
        "sections": binary_metrics.get("sections", {}),
        "symbol_count": binary_metrics.get("symbol_count", 0),
        "ir_size": binary_metrics.get("ir_size", 0),
        "ir_lines": binary_metrics.get("ir_lines", 0),
        "function_count_ir": binary_metrics.get("function_count_ir", 0),
        "basic_block_count_ir": binary_metrics.get(
            "basic_block_count_ir", 0
        ),
        "test": {
            "exit_code": test_result.get("exit_code", -1),
            "stdout": test_result.get("stdout", ""),
            "passed": test_result.get("passed", False),
        },
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "reproducibility": {
            "source_revision": source_revision,
            "llvm_version": toolchain_info.get("llvm_version", ""),
            "compiler_version": toolchain_info.get(
                "compiler_version", ""
            ),
            "target_triple": toolchain_info.get("target_triple", ""),
            "optimization": optimization,
            "seed": seed,
            "transformation_versions": {
                t["name"]: t["version"]
                for t in transformation_pipeline.get("applied", [])
            },
        },
    }

    return manifest


def save_manifest(manifest: Dict[str, Any], path: Path):
    path.write_text(
        json.dumps(manifest, indent=2, ensure_ascii=False)
    )


def load_manifest(path: Path) -> Dict[str, Any]:
    return json.loads(path.read_text())

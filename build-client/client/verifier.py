import hashlib
from pathlib import Path
from typing import Dict, Any


def verify_artifact(
    artifact_bytes: bytes,
    manifest: Dict[str, Any],
) -> Dict[str, Any]:
    local_sha256 = hashlib.sha256(artifact_bytes).hexdigest()
    remote_sha256 = manifest.get("artifact_sha256", "")

    match = local_sha256 == remote_sha256

    local_size = len(artifact_bytes)
    remote_size = manifest.get("file_size", 0)
    size_match = local_size == remote_size

    return {
        "sha256_match": match,
        "local_sha256": local_sha256,
        "remote_sha256": remote_sha256,
        "size_match": size_match,
        "local_size": local_size,
        "remote_size": remote_size,
        "verified": match and size_match,
    }


def save_artifact(
    artifact_bytes: bytes,
    output_path: Path,
) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(artifact_bytes)

    if not (output_path).name.endswith(".exe"):
        try:
            import stat
            output_path.chmod(
                output_path.stat().st_mode
                | stat.S_IEXEC
                | stat.S_IXGRP
                | stat.S_IXOTH
            )
        except (OSError, AttributeError):
            pass

    return output_path


def execute_artifact(path: Path) -> Dict[str, Any]:
    import subprocess

    result = subprocess.run(
        [str(path)],
        capture_output=True,
        text=True,
        timeout=10,
    )

    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
    }

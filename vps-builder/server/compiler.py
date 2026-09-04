import os
import shutil
import hashlib
import subprocess
import logging
from pathlib import Path
from typing import Dict, Any, Optional

try:
    import resource
    _HAS_RESOURCE = True
except ImportError:
    _HAS_RESOURCE = False

logger = logging.getLogger(__name__)

HELLO_WORLD_SOURCE = """\
#include <iostream>

int main() {
    std::cout << "Hello, World!" << std::endl;
    return 0;
}
"""

BASE_TEMP_DIR = os.environ.get("POLYLAB_WORK_DIR", "/tmp/polylab")
BUILD_TIMEOUT = int(os.environ.get("POLYLAB_BUILD_TIMEOUT", "60"))


class BuildWorkspace:
    def __init__(self, build_id: str):
        self.build_id = build_id
        self.path = Path(BASE_TEMP_DIR) / build_id
        self.source_path = self.path / "main.cpp"
        self.ir_path = self.path / "input.ll"
        self.transformed_ir_path = self.path / "transformed.ll"
        self.executable_path = self.path / "hello"
        self.manifest_path = self.path / "manifest.json"

    def create(self) -> Path:
        self.path.mkdir(parents=True, exist_ok=True)
        self.source_path.write_text(HELLO_WORLD_SOURCE, encoding="utf-8")
        logger.info(f"Workspace created: {self.path}")
        return self.path

    def destroy(self):
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
            logger.info(f"Workspace destroyed: {self.path}")

    def get_executable_bytes(self) -> bytes:
        return self.executable_path.read_bytes()

    def disk_usage(self) -> int:
        total = 0
        if self.path.exists():
            for f in self.path.rglob("*"):
                if f.is_file():
                    total += f.stat().st_size
        return total


def _run(cmd: list[str], timeout: int = BUILD_TIMEOUT, **kwargs) -> subprocess.CompletedProcess:
    """Run a command with resource limits (Linux only)."""
    preexec = None
    if _HAS_RESOURCE and os.name != "nt":
        def _set_limits():
            resource.setrlimit(resource.RLIMIT_AS, (256 * 1024 * 1024, 256 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_CPU, (30, 30))
            resource.setrlimit(resource.RLIMIT_FSIZE, (50 * 1024 * 1024, 50 * 1024 * 1024))
            resource.setrlimit(resource.RLIMIT_NPROC, (64, 64))
        preexec = _set_limits

    merged = {
        "capture_output": True,
        "text": True,
        "timeout": timeout,
    }
    if preexec:
        merged["preexec_fn"] = preexec
    merged.update(kwargs)
    return subprocess.run(cmd, **merged)


def get_toolchain_info() -> Dict[str, Any]:
    info: Dict[str, Any] = {"compiler": "clang"}

    try:
        result = _run(["clang", "--version"], timeout=10)
        version_line = result.stdout.strip().split("\n")[0]
        info["compiler_version"] = version_line
        for p in version_line.split():
            if p[0].isdigit():
                info["clang_version"] = p
                info["llvm_version"] = p
                break
    except Exception as e:
        logger.error(f"clang version detection failed: {e}")
        info["compiler_version"] = info["clang_version"] = info["llvm_version"] = "unknown"

    try:
        result = _run(["clang", "-dumpmachine"], timeout=10)
        info["target_triple"] = result.stdout.strip()
    except Exception:
        info["target_triple"] = "unknown"

    return info


def generate_ir(workspace: BuildWorkspace, optimization: str = "O2") -> Dict[str, Any]:
    result = _run([
        "clang", f"-{optimization}", "-S", "-emit-llvm",
        "-o", str(workspace.ir_path),
        str(workspace.source_path),
    ])
    if result.returncode != 0:
        raise RuntimeError(f"IR generation failed (rc={result.returncode}): {result.stderr}")

    ir_content = workspace.ir_path.read_text(encoding="utf-8")
    return {
        "ir_size": len(ir_content.encode()),
        "ir_lines": len(ir_content.splitlines()),
    }


def compile_from_ir(workspace: BuildWorkspace, optimization: str = "O2") -> Dict[str, Any]:
    result = _run([
        "clang", f"-{optimization}",
        "-o", str(workspace.executable_path),
        str(workspace.transformed_ir_path),
    ])
    if result.returncode != 0:
        raise RuntimeError(f"Compilation failed (rc={result.returncode}): {result.stderr}")
    return {"compiled": True}


def test_executable(workspace: BuildWorkspace) -> Dict[str, Any]:
    try:
        test_preexec = None
        if _HAS_RESOURCE and os.name != "nt":
            def _test_limits():
                resource.setrlimit(resource.RLIMIT_CPU, (5, 5))
                resource.setrlimit(resource.RLIMIT_AS, (64 * 1024 * 1024, 64 * 1024 * 1024))
            test_preexec = _test_limits

        result = _run(
            [str(workspace.executable_path)],
            timeout=10,
            preexec_fn=test_preexec,
        )
    except subprocess.TimeoutExpired:
        return {"exit_code": -1, "stdout": "", "stderr": "timeout", "passed": False}

    return {
        "exit_code": result.returncode,
        "stdout": result.stdout,
        "stderr": result.stderr,
        "passed": result.returncode == 0 and result.stdout == "Hello, World!\n",
    }


def calculate_sha256(file_path: Path) -> str:
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()

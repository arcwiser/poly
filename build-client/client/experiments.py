import json
import time
import sys
from pathlib import Path
from typing import Dict, Any, Optional
from datetime import datetime, timezone

from .api import ClientAPI, APIError
from .verifier import verify_artifact, save_artifact


EXPERIMENTS_DIR = Path.home() / ".polylab" / "experiments"
ARTIFACTS_DIR = Path.home() / ".polylab" / "artifacts"

RED = "\033[0;31m" if sys.stdout.isatty() else ""
GREEN = "\033[0;32m" if sys.stdout.isatty() else ""
YELLOW = "\033[1;33m" if sys.stdout.isatty() else ""
CYAN = "\033[0;36m" if sys.stdout.isatty() else ""
BOLD = "\033[1m" if sys.stdout.isatty() else ""
DIM = "\033[2m" if sys.stdout.isatty() else ""
NC = "\033[0m" if sys.stdout.isatty() else ""


def run_experiment(
    api: ClientAPI,
    count: int,
    optimization: str = "O2",
    save_artifacts: bool = True,
) -> Dict[str, Any]:
    EXPERIMENTS_DIR.mkdir(parents=True, exist_ok=True)

    experiment_id = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
    results = []
    start_time = time.time()

    print(f"{BOLD}Running {count} builds with optimization {optimization}{NC}")
    print(f"{DIM}{'Seed':>6}  {'SHA-256 (first 16)':>18}  {'Size':>8}  {'.text':>8}  {'Sym':>5}  {'Time':>6}  Status{NC}")
    print(f"{DIM}{'─' * 75}{NC}")

    for seed in range(1, count + 1):
        t0 = time.time()

        try:
            build_result = api.request_build(seed=seed, optimization=optimization)
            elapsed = time.time() - t0

            verification = verify_artifact(
                build_result["artifact_bytes"],
                build_result["manifest"],
            )

            manifest = build_result["manifest"]

            if save_artifacts:
                d = ARTIFACTS_DIR / experiment_id
                d.mkdir(parents=True, exist_ok=True)
                save_artifact(build_result["artifact_bytes"], d / f"hello_seed_{seed}")

            result = {
                "seed": seed,
                "build_id": build_result["build_id"],
                "sha256": verification["local_sha256"],
                "verified": verification["verified"],
                "file_size": manifest.get("file_size", 0),
                "text_size": manifest.get("text_size", 0),
                "symbol_count": manifest.get("symbol_count", 0),
                "section_count": manifest.get("section_count", 0),
                "transformations": [t["name"] for t in manifest.get("transformations", [])],
                "test_passed": manifest.get("test", {}).get("passed", False),
                "elapsed_seconds": round(elapsed, 3),
            }
            results.append(result)

            sha_short = verification["local_sha256"][:16]
            sz = manifest.get("file_size", 0)
            tx = manifest.get("text_size", 0)
            sy = manifest.get("symbol_count", 0)
            status = f"{GREEN}OK{NC}" if verification["verified"] else f"{RED}HASH{NC}"
            print(f"{seed:>6}  {sha_short:>18}  {sz:>8,}  {tx:>8,}  {sy:>5}  {elapsed:>5.2f}s  {status}")

        except APIError as e:
            elapsed = time.time() - t0
            results.append({
                "seed": seed, "build_id": None, "sha256": None,
                "verified": False, "error": str(e),
                "file_size": 0, "text_size": 0, "test_passed": False,
                "elapsed_seconds": round(elapsed, 3),
            })
            print(f"{seed:>6}  {'─' * 18}  {'─' * 8}  {'─' * 8}  {'─' * 5}  {elapsed:>5.2f}s  {RED}FAIL: {e}{NC}")

    total_elapsed = time.time() - start_time

    unique = len(set(r["sha256"] for r in results if r.get("sha256")))
    ok = sum(1 for r in results if r.get("verified"))
    sizes = [r["file_size"] for r in results if r.get("file_size")]
    texts = [r["text_size"] for r in results if r.get("text_size")]

    print(f"{DIM}{'─' * 75}{NC}")
    print(f"{BOLD}Complete in {total_elapsed:.1f}s{NC} — {ok}/{count} OK, {unique} unique hashes")
    if sizes:
        print(f"  Size range: {min(sizes):,} – {max(sizes):,} bytes (spread: {max(sizes) - min(sizes):,})")
    if texts:
        print(f"  .text range: {min(texts):,} – {max(texts):,} bytes (spread: {max(texts) - min(texts):,})")

    experiment_data = {
        "experiment_id": experiment_id,
        "total_builds": count,
        "successful_builds": ok,
        "unique_hashes": unique,
        "optimization": optimization,
        "elapsed_seconds": round(total_elapsed, 3),
        "results": results,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    out_path = EXPERIMENTS_DIR / f"{experiment_id}.json"
    out_path.write_text(json.dumps(experiment_data, indent=2))
    print(f"  Results: {out_path}")

    return experiment_data

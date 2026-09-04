import os
import sys
import argparse
import json
import time
from pathlib import Path

from .api import ClientAPI, APIError
from .verifier import verify_artifact, save_artifact, execute_artifact
from .experiments import run_experiment, EXPERIMENTS_DIR
from .report import generate_report


class C:
    """ANSI colors - disabled on Windows cmd without ANSI support."""
    _enabled = sys.stdout.isatty() and os.name != "nt"
    R = "\033[0;31m" if _enabled else ""
    G = "\033[0;32m" if _enabled else ""
    Y = "\033[1;33m" if _enabled else ""
    B = "\033[1m" if _enabled else ""
    D = "\033[2m" if _enabled else ""
    C = "\033[0;36m" if _enabled else ""
    NC = "\033[0m" if _enabled else ""

    @staticmethod
    def ok(s): return f"{C.G}{s}{C.NC}"
    @staticmethod
    def warn(s): return f"{C.Y}{s}{C.NC}"
    @staticmethod
    def err(s): return f"{C.R}{s}{C.NC}"
    @staticmethod
    def bold(s): return f"{C.B}{s}{C.NC}"
    @staticmethod
    def dim(s): return f"{C.D}{s}{C.NC}"
    @staticmethod
    def cyan(s): return f"{C.C}{s}{C.NC}"


def _banner():
    print(f"""
{C.cyan(C.bold + '''  ┌──────────────────────────────────────────────────────┐
  │  LLVM Polymorphic Compilation Research Platform      │
  │  github.com/arcwiser/poly                            │
  └──────────────────────────────────────────────────────┘''')}{C.NC}
""")


def build_command(args, api: ClientAPI):
    print(f"Requesting LLVM build...")
    print(f"  Seed:        {C.bold(str(args.seed))}")
    print(f"  Optimization:{args.optimization}")
    print()

    retries = args.retries
    for attempt in range(1, retries + 1):
        try:
            t0 = time.time()
            result = api.request_build(
                seed=args.seed,
                optimization=args.optimization,
            )
            elapsed = time.time() - t0
            break
        except APIError as e:
            if attempt < retries:
                wait = 2 ** attempt
                print(f"  {C.warn(f'Attempt {attempt}/{retries} failed: {e}')} — retrying in {wait}s...")
                time.sleep(wait)
            else:
                print(f"  {C.err(f'Failed after {retries} attempts: {e}')}")
                sys.exit(1)

    manifest = result["manifest"]

    print(f"{C.ok('Build completed')} in {elapsed:.2f}s")
    pipeline = manifest.get("transformations", [])
    if pipeline:
        names = [t["name"] for t in pipeline]
        changed = sum(1 for t in pipeline if t.get("changed"))
        print(f"  Pipeline: {', '.join(names)} ({changed}/{len(pipeline)} modified IR)")
    else:
        print(f"  Pipeline: none")
    print()

    sha = manifest.get("artifact_sha256", "unknown")
    print(f"  SHA-256:    {C.dim(sha)}")
    print(f"  File size:  {manifest.get('file_size', 0):,} bytes")
    print(f"  .text size: {manifest.get('text_size', 0):,} bytes")
    print(f"  Symbols:    {manifest.get('symbol_count', 0)}")
    print()

    verification = verify_artifact(result["artifact_bytes"], manifest)
    if verification["verified"]:
        print(f"  {C.ok('SHA-256 verified locally.')}")
    else:
        print(f"  {C.err('SHA-256 MISMATCH!')}")
        print(f"    Local:  {verification['local_sha256']}")
        print(f"    Remote: {verification['remote_sha256']}")
        sys.exit(1)

    output_dir = Path(args.output) if args.output else Path(".")
    output_path = output_dir / f"hello_seed_{args.seed}"
    save_artifact(result["artifact_bytes"], output_path)
    print(f"  Saved:      {output_path}")
    print()

    print(f"  {C.bold('Running executable...')}")
    print(f"  {C.dim('─' * 40)}")
    exec_result = execute_artifact(output_path)
    if exec_result["stdout"]:
        print(f"  {exec_result['stdout'].rstrip()}")
    if exec_result["stderr"]:
        print(f"  {C.err(exec_result['stderr'].rstrip())}")
    print(f"  {C.dim('─' * 40)}")
    ec = exec_result["exit_code"]
    print(f"  Exit code:  {C.ok(str(ec)) if ec == 0 else C.err(str(ec))}")
    print()
    bid = result["build_id"]
    print(f"  {C.dim('Build ID: ' + bid)}")


def experiment_command(args, api: ClientAPI):
    data = run_experiment(
        api=api,
        count=args.count,
        optimization=args.optimization,
        save_artifacts=not args.no_save,
    )

    print()
    print(f"  {C.ok('Experiment complete.')}")
    print(f"  Total builds:   {data['total_builds']}")
    print(f"  Successful:     {C.ok(str(data['successful_builds']))}")
    print(f"  Unique hashes:  {C.bold(str(data['unique_hashes']))}")
    print(f"  Diversification:{data['unique_hashes']}/{data['total_builds']}")
    print(f"  Results saved:  {EXPERIMENTS_DIR / data['experiment_id']}.json")


def report_command(args):
    print(generate_report(args.experiment_id))


def info_command(args, api: ClientAPI):
    info = api.server_info()
    print(f"{C.bold('=== Server Info ===')}")
    print(f"  Server:  {info.get('server', '?')}")
    print(f"  Version: {info.get('version', '?')}")
    print()

    tc = info.get("toolchain", {})
    print(f"  {C.bold('LLVM Toolchain')}")
    print(f"    Compiler:  {tc.get('compiler_version', '?')}")
    print(f"    LLVM:      {tc.get('llvm_version', '?')}")
    print(f"    Target:    {tc.get('target_triple', '?')}")
    print()

    print(f"  {C.bold('Configuration')}")
    print(f"    Projects:       {info.get('valid_projects', [])}")
    print(f"    Optimizations:  {info.get('valid_optimizations', [])}")
    print(f"    Transforms:     {info.get('available_transformations', [])}")
    print(f"    Rate limit:     {info.get('rate_limit', '?')}")
    print(f"    Max concurrent: {info.get('max_concurrent_builds', '?')}")


def main():
    _banner()

    parser = argparse.ArgumentParser(
        prog="poly",
        description="LLVM Polymorphic Compilation Research Client",
    )
    parser.add_argument("--server", default=os.environ.get("POLYLAB_SERVER", "http://localhost:8000"),
                        help="VPS server URL")
    parser.add_argument("--token", default=os.environ.get("POLYLAB_API_TOKEN", ""),
                        help="API token")

    sub = parser.add_subparsers(dest="command")

    b = sub.add_parser("build", help="Request a single build")
    b.add_argument("--seed", type=int, default=42, help="Build seed (default: 42)")
    b.add_argument("--optimization", "-O", default="O2", choices=["O0", "O1", "O2", "O3"])
    b.add_argument("--output", "-o", default=None, help="Output directory")
    b.add_argument("--retries", type=int, default=3, help="Retry count")

    e = sub.add_parser("experiment", help="Run multi-seed experiment")
    e.add_argument("--count", type=int, default=20, help="Number of variants (default: 20)")
    e.add_argument("--optimization", "-O", default="O2", choices=["O0", "O1", "O2", "O3"])
    e.add_argument("--no-save", action="store_true", help="Don't save artifacts locally")

    r = sub.add_parser("report", help="Show experiment report")
    r.add_argument("--experiment-id", default=None)

    sub.add_parser("info", help="Show server info")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)
    if not args.token:
        print(f"{C.err('No API token. Set POLYLAB_API_TOKEN or use --token')}")
        sys.exit(1)

    api = ClientAPI(args.server, args.token)

    cmds = {
        "build": lambda: build_command(args, api),
        "experiment": lambda: experiment_command(args, api),
        "report": lambda: report_command(args),
        "info": lambda: info_command(args, api),
    }
    cmds[args.command]()


if __name__ == "__main__":
    main()

import json
import sys
from pathlib import Path
from typing import Optional

EXPERIMENTS_DIR = Path.home() / ".polylab" / "experiments"

RED = "\033[0;31m" if sys.stdout.isatty() else ""
GREEN = "\033[0;32m" if sys.stdout.isatty() else ""
YELLOW = "\033[1;33m" if sys.stdout.isatty() else ""
CYAN = "\033[0;36m" if sys.stdout.isatty() else ""
BOLD = "\033[1m" if sys.stdout.isatty() else ""
DIM = "\033[2m" if sys.stdout.isatty() else ""
NC = "\033[0m" if sys.stdout.isatty() else ""


def load_experiment(experiment_id: Optional[str] = None) -> Optional[dict]:
    if experiment_id:
        p = EXPERIMENTS_DIR / f"{experiment_id}.json"
        return json.loads(p.read_text()) if p.exists() else None
    files = sorted(EXPERIMENTS_DIR.glob("*.json"))
    return json.loads(files[-1].read_text()) if files else None


def generate_report(experiment_id: Optional[str] = None) -> str:
    data = load_experiment(experiment_id)
    if not data:
        return "No experiment data. Run: poly experiment --count 20"

    results = data["results"]
    ok = [r for r in results if r.get("verified")]
    hashes = [r["sha256"] for r in ok if r.get("sha256")]
    sizes = [r["file_size"] for r in ok if r.get("file_size")]
    texts = [r["text_size"] for r in ok if r.get("text_size")]
    syms = [r.get("symbol_count", 0) for r in ok if r.get("symbol_count")]

    lines = []
    w = 60

    lines.append(f"{BOLD}{'═' * w}{NC}")
    lines.append(f"{BOLD}  LLVM Polymorphic Compilation — Experiment Report{NC}")
    lines.append(f"{BOLD}{'═' * w}{NC}")
    lines.append("")
    lines.append(f"  {CYAN}Experiment ID:{NC}  {data.get('experiment_id', '?')}")
    lines.append(f"  {CYAN}Timestamp:{NC}     {data.get('timestamp', '?')}")
    lines.append(f"  {CYAN}Optimization:{NC}  {data.get('optimization', '?')}")
    lines.append(f"  {CYAN}Duration:{NC}      {data.get('elapsed_seconds', 0):.1f}s")
    lines.append("")

    # ── summary ──
    lines.append(f"{BOLD}  Summary{NC}")
    lines.append(f"  {'─' * (w - 4)}")
    unique = len(set(hashes))
    lines.append(f"  Total builds:        {data['total_builds']}")
    lines.append(f"  Successful:          {GREEN}{data['successful_builds']}{NC}")
    lines.append(f"  Unique SHA-256:      {BOLD}{unique}{NC}")
    if data["total_builds"] > 0:
        div_pct = unique / data["total_builds"] * 100
        lines.append(f"  Diversification:     {div_pct:.0f}%")
    lines.append("")

    # ── sizes ──
    if sizes:
        lines.append(f"{BOLD}  Executable Size{NC}")
        lines.append(f"  {'─' * (w - 4)}")
        avg = sum(sizes) / len(sizes)
        lines.append(f"  Min:    {min(sizes):>10,} bytes")
        lines.append(f"  Max:    {max(sizes):>10,} bytes")
        lines.append(f"  Avg:    {avg:>10,.0f} bytes")
        lines.append(f"  Spread: {max(sizes) - min(sizes):>10,} bytes")
        lines.append("")

    if texts:
        lines.append(f"{BOLD}  .text Section Size{NC}")
        lines.append(f"  {'─' * (w - 4)}")
        avg = sum(texts) / len(texts)
        lines.append(f"  Min:    {min(texts):>10,} bytes")
        lines.append(f"  Max:    {max(texts):>10,} bytes")
        lines.append(f"  Avg:    {avg:>10,.0f} bytes")
        lines.append(f"  Spread: {max(texts) - min(texts):>10,} bytes")
        lines.append("")

    # ── pairwise similarity ──
    if len(ok) >= 2:
        lines.append(f"{BOLD}  Pairwise Binary Similarity (by file size){NC}")
        lines.append(f"  {'─' * (w - 4)}")
        pairs = 0
        sim_sum = 0.0
        sim_min = 1.0
        sim_max = 0.0
        for i in range(len(ok)):
            for j in range(i + 1, len(ok)):
                a, b = ok[i], ok[j]
                if a["sha256"] == b["sha256"]:
                    sim = 1.0
                else:
                    diff = abs(a["file_size"] - b["file_size"])
                    mx = max(a["file_size"], b["file_size"])
                    sim = 1.0 - diff / mx if mx else 1.0
                pairs += 1
                sim_sum += sim
                sim_min = min(sim_min, sim)
                sim_max = max(sim_max, sim)
        avg = sim_sum / pairs
        lines.append(f"  Pairs compared:  {pairs}")
        lines.append(f"  Min similarity:  {sim_min:.4f}")
        lines.append(f"  Max similarity:  {sim_max:.4f}")
        lines.append(f"  Avg similarity:  {avg:.4f}")
        lines.append("")

    # ── per-build table ──
    lines.append(f"{BOLD}  Per-Build Results{NC}")
    lines.append(f"  {'─' * (w - 4)}")
    lines.append(f"  {'Seed':>6}  {'SHA-256':>18}  {'Size':>10}  {'.text':>10}  {'Sym':>5}  {'OK':>3}")
    lines.append(f"  {'─' * 62}")
    for r in results:
        seed = str(r.get("seed", "?"))
        sha = (r.get("sha256") or "N/A")[:16]
        sz = f"{r.get('file_size', 0):,}"
        tx = f"{r.get('text_size', 0):,}"
        sy = str(r.get("symbol_count", 0))
        ok_flag = f"{GREEN}Y{NC}" if r.get("verified") else f"{RED}N{NC}"
        lines.append(f"  {seed:>6}  {sha:>18}  {sz:>10}  {tx:>10}  {sy:>5}  {ok_flag:>3}")

    lines.append("")
    lines.append(f"{BOLD}{'═' * w}{NC}")

    return "\n".join(lines)

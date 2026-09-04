# LLVM Polymorphic Compilation Research Platform

Study how LLVM transformations produce different binary representations of the same C++ program while preserving behavior.

**github.com/arcwiser/poly**

## Quick Install (Ubuntu)

```bash
# One-liner remote install
curl -sSL https://raw.githubusercontent.com/arcwiser/poly/main/install.sh | sudo bash

# Or clone and run locally
git clone https://github.com/arcwiser/poly.git
cd poly/vps-builder
sudo bash setup.sh
```

## Quick Start — Client

```bash
cd build-client
export POLYLAB_SERVER="http://YOUR_VPS_IP:8000"
export POLYLAB_API_TOKEN="token-from-setup"

# Single build
python -m client build --seed 42

# Experiment with 20 variants
python -m client experiment --count 20

# View report
python -m client report
```

## Architecture

```
remote-polymorphic-lab/
├── install.sh                  One-liner remote installer
├── README.md
├── vps-builder/
│   ├── setup.sh               Ubuntu auto-installer (apt + systemd)
│   ├── main.py                Server entry point
│   ├── server/
│   │   ├── api.py             FastAPI + rate limiting + queue
│   │   ├── build_manager.py   Build orchestration
│   │   ├── compiler.py        Clang/LLVM with resource limits
│   │   ├── transformations/   Seed-deterministic IR transforms
│   │   ├── analyzer.py        Binary analysis & metrics
│   │   ├── manifest.py        Reproducibility manifests
│   │   ├── cleanup.py         Workspace destruction
│   │   └── discord_logger.py  Webhook notifications
│   └── requirements.txt
└── build-client/
    ├── client/
    │   ├── main.py            CLI (poly build/experiment/report/info)
    │   ├── api.py             VPS communication
    │   ├── verifier.py        SHA-256 verification
    │   ├── experiments.py     Multi-seed runner
    │   └── report.py          Experiment reports
    └── requirements.txt       (zero external deps)
```

## Features

- **5 IR transformations** — all deterministic, semantics-preserving
- **Seed system** — same seed = same result, always
- **Binary analysis** — SHA-256, sections, symbols, IR metrics
- **Rate limiting** — per-IP request throttling
- **Concurrency control** — max 4 simultaneous builds
- **Resource limits** — memory, CPU, disk per build
- **Discord notifications** — build start/success/failure/experiment
- **Interactive API docs** — Swagger UI at /docs
- **Auto-install** — one command to install on Ubuntu
- **systemd service** — auto-start, auto-restart, journal logs

## Transformations

| Name | Description |
|------|-------------|
| `constant_expr` | Parenthesized constant expressions |
| `block_reorder` | Deterministic basic block reordering |
| `arithmetic_restructure` | Equivalent arithmetic (add ↔ shl) |
| `function_reorder` | Function definition reordering |
| `ir_restructure` | Harmless IR attribute modifications |

## LLVM Toolchain

Pinned: **LLVM/Clang 14** (installed via apt by `setup.sh`)

## Reproducibility

Every build is reproducible from:
```
source + LLVM version + target + optimization + seed + transformation versions
```

## API

```
GET  /health          Health check
GET  /info            Server info + toolchain
POST /build           Compile a variant (auth required)
GET  /transformations List available transforms
POST /compare         Compare two builds (auth required)
GET  /docs            Swagger UI
GET  /redoc           ReDoc
```

## License

Research use only.

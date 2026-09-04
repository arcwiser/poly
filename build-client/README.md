# Build Client

Local client for the LLVM Polymorphic Compilation Research Platform.

## Requirements

- Python 3.10+
- No external dependencies (stdlib only)

## Setup

```bash
export POLYLAB_SERVER="http://YOUR_VPS_IP:8000"
export POLYLAB_API_TOKEN="your-token"
```

## Commands

### Single Build

```bash
python -m client build --seed 42
python -m client build --seed 42 -O O3
python -m client build --seed 42 -o ./artifacts
```

### Multi-Seed Experiment

```bash
python -m client experiment --count 20
python -m client experiment --count 50 -O O1 --no-save
```

### Report

```bash
python -m client report
python -m client report --experiment-id 20260904_120000
```

### Server Info

```bash
python -m client info
```

## Example Output

```
  ┌──────────────────────────────────────────────────────┐
  │  LLVM Polymorphic Compilation Research Platform      │
  │  github.com/arcwiser/poly                            │
  └──────────────────────────────────────────────────────┘

Requesting LLVM build...
  Seed:        42
  Optimization:O2

Build completed in 1.23s
  Pipeline: constant_expr, block_reorder, arithmetic_restructure (3/3 modified IR)

  SHA-256:    a1b2c3d4e5f6...
  File size:  16,384 bytes
  .text size: 5,120 bytes
  Symbols:    42

  SHA-256 verified locally.
  Saved:      ./hello_seed_42

  Running executable...
  ────────────────────────────────────────
  Hello, World!
  ────────────────────────────────────────
  Exit code:  0
```

## Experiment Output

```
Running 20 builds with optimization O2
  Seed  SHA-256 (first 16)       Size     .text    Sym   Time  Status
─────────────────────────────────────────────────────────────────────────────────────
     1  a1b2c3d4...             16,384    5,120    42  1.23s  OK
     2  e5f6a7b8...             16,416    5,152    42  1.19s  OK
     ...
Complete in 24.3s — 20/20 OK, 20 unique hashes
  Size range: 16,384 – 16,512 bytes (spread: 128)
  .text range: 5,120 – 5,248 bytes (spread: 128)
  Results: ~/.polylab/experiments/20260904_120000.json
```

## Artifact Storage

- Artifacts: `~/.polylab/artifacts/<experiment_id>/hello_seed_<N>`
- Experiments: `~/.polylab/experiments/<experiment_id>.json`

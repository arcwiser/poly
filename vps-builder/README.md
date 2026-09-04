# VPS Builder

Server-side compilation pipeline for the LLVM Polymorphic Compilation Research Platform.

## Install on Ubuntu

```bash
# Option 1: One-liner (from anywhere)
curl -sSL https://raw.githubusercontent.com/arcwiser/poly/main/install.sh | sudo bash

# Option 2: Clone and run
git clone https://github.com/arcwiser/poly.git
cd poly/vps-builder
sudo bash setup.sh

# Option 3: Custom config
sudo POLYLAB_API_TOKEN=mytoken POLYLAB_PORT=8080 bash setup.sh
```

## What the Installer Does

1. Installs Python 3, LLVM/Clang 14, binutils via apt
2. Adds LLVM apt repo if clang-14 isn't available
3. Creates a `polylab` non-root service user
4. Sets up a Python venv at `/opt/polylab/venv`
5. Installs pip dependencies
6. Creates build workspace at `/tmp/polylab`
7. Generates API token (or uses yours)
8. Installs systemd service with security hardening
9. Starts the service
10. Sends Discord notification
11. Prints connection info + token

## Management

```bash
systemctl status polylab
systemctl restart polylab
systemctl stop polylab
journalctl -u polylab -f
```

## Uninstall

```bash
sudo bash /opt/polylab/setup.sh --uninstall
```

## Environment Variables

| Variable | Default | Description |
|---|---|---|
| `POLYLAB_API_TOKEN` | auto-generated | API auth token |
| `POLYLAB_HOST` | `0.0.0.0` | Bind address |
| `POLYLAB_PORT` | `8000` | Server port |
| `POLYLAB_DISCORD_WEBHOOK` | set by installer | Discord webhook |
| `POLYLAB_LOG_FILE` | `/var/log/polylab.log` | Log file |
| `POLYLAB_WORK_DIR` | `/tmp/polylab` | Build workspace |
| `POLYLAB_MAX_CONCURRENT` | `4` | Max simultaneous builds |
| `POLYLAB_BUILD_TIMEOUT` | `60` | Per-build timeout (seconds) |
| `POLYLAB_RATE_LIMIT` | `30` | Requests per minute per IP |

## API

```
GET  /health              Health check
GET  /info                Server info + toolchain
POST /build               Compile a variant
GET  /transformations     List transforms
POST /compare             Compare builds
GET  /docs                Swagger UI
GET  /redoc               ReDoc
```

## Security

- Runs as `polylab` non-root user
- systemd: NoNewPrivileges, ProtectSystem=strict, ProtectHome=read-only
- Resource limits: 512MB memory, 80% CPU, 64 tasks
- Build sandbox: 256MB memory, 30s CPU, 50MB disk per compilation
- All artifacts deleted after transmission
- Rate limiting: 30 requests/minute/IP
- Only `hello-world` project accepted
- Arbitrary commands/flags rejected

## Discord Notifications

- Server start/stop
- Build started (seed, optimization, queue status)
- Build completed (SHA-256, size, time, transforms)
- Build failed (error, phase)
- Experiment complete (totals, unique hashes)

## Running Tests

```bash
cd /opt/polylab
POLYLAB_API_TOKEN=test venv/bin/python tests/test_pipeline.py
```

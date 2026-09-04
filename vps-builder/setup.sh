#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# LLVM Polymorphic Compilation Research Platform
# Complete Ubuntu auto-installer
#
# Copy this entire repo to your VPS, then run:
#   sudo bash setup.sh
#
# With custom options:
#   sudo POLYLAB_API_TOKEN=xxx POLYLAB_PORT=8080 bash setup.sh
#
# Uninstall:
#   sudo bash setup.sh --uninstall
# ─────────────────────────────────────────────────────────────
set -euo pipefail

# ── config ──────────────────────────────────────────────────

SERVICE_NAME="polylab"
SERVICE_USER="polylab"
INSTALL_DIR="/opt/polylab"
ENV_FILE="/etc/polylab.env"
LOG_FILE="/var/log/polylab.log"
WORK_DIR="/tmp/polylab"
MIN_PYTHON=3.10
REQUIRED_PKGS="python3 python3-pip python3-venv clang-14 llvm-14 lld-14 binutils curl jq"

# ── colors ──────────────────────────────────────────────────

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; DIM='\033[2m'; NC='\033[0m'

log()    { echo -e "${GREEN}[+]${NC} $*"; }
warn()   { echo -e "${YELLOW}[!]${NC} $*"; }
err()    { echo -e "${RED}[x]${NC} $*" >&2; }
die()    { err "$*"; exit 1; }
step()   { echo -e "\n${CYAN}${BOLD}── $* ──${NC}"; }
banner() {
    echo -e "${CYAN}${BOLD}"
    cat <<'BANNER'
  ┌──────────────────────────────────────────────────────┐
  │                                                      │
  │   LLVM Polymorphic Compilation Research Platform     │
  │   github.com/arcwiser/poly                           │
  │                                                      │
  └──────────────────────────────────────────────────────┘
BANNER
    echo -e "${NC}"
}

# ── uninstall ───────────────────────────────────────────────

if [[ "${1:-}" == "--uninstall" ]]; then
    warn "Uninstalling polylab..."
    systemctl stop "$SERVICE_NAME" 2>/dev/null || true
    systemctl disable "$SERVICE_NAME" 2>/dev/null || true
    rm -f "/etc/systemd/system/${SERVICE_NAME}.service"
    systemctl daemon-reload
    rm -rf "$INSTALL_DIR"
    rm -f "$ENV_FILE"
    rm -rf "$WORK_DIR"
    rm -f "$LOG_FILE"
    userdel "$SERVICE_USER" 2>/dev/null || true
    log "Uninstalled. Config in /etc/polylab.env preserved."
    exit 0
fi

# ── pre-flight ──────────────────────────────────────────────

banner

if [[ $EUID -ne 0 ]]; then
    die "Run as root: sudo bash setup.sh"
fi

# ── detect source dir ──────────────────────────────────────

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
if [[ ! -f "$SCRIPT_DIR/requirements.txt" ]] || [[ ! -d "$SCRIPT_DIR/server" ]]; then
    # Try parent dir (if run from vps-builder/)
    SCRIPT_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
fi
if [[ ! -f "$SCRIPT_DIR/server/__init__.py" ]]; then
    die "Cannot find polylab source. Run from repo root: sudo bash vps-builder/setup.sh"
fi
SRC_DIR="$SCRIPT_DIR/vps-builder"
[[ -d "$SRC_DIR" ]] || SRC_DIR="$SCRIPT_DIR"

log "Source directory: $SRC_DIR"

# ── system packages ─────────────────────────────────────────

step "Installing system packages"

apt-get update -qq

# add LLVM apt repo for guaranteed clang-14 availability
if ! apt-cache show clang-14 >/dev/null 2>&1; then
    log "Adding LLVM apt repository..."
    apt-get install -y -qq lsb-release wget software-properties-common gnupg
    wget -qO- https://apt.llvm.org/llvm-snapshot.gpg.key | tee /etc/apt/trusted.gpg.d/apt.llvm.org.asc >/dev/null
    CODENAME=$(lsb_release -cs)
    echo "deb http://apt.llvm.org/${CODENAME}/ llvm-toolchain-${CODENAME}-14 main" \
        > /etc/apt/sources.list.d/llvm-14.list
    apt-get update -qq
fi

DEBIAN_FRONTEND=noninteractive apt-get install -y -qq $REQUIRED_PKGS

# ── verify clang ────────────────────────────────────────────

step "Verifying toolchain"

if ! command -v clang-14 &>/dev/null; then
    die "clang-14 not found after install"
fi

update-alternatives --install /usr/bin/clang   clang   /usr/bin/clang-14   100
update-alternatives --install /usr/bin/clang++ clang++ /usr/bin/clang++-14 100
update-alternatives --install /usr/bin/llvm-as llvm-as /usr/bin/llvm-as-14 100
update-alternatives --install /usr/bin/opt     opt     /usr/bin/opt-14     100

CLANG_VER=$(clang --version | head -1)
log "  $CLANG_VER"

# ── python version check ───────────────────────────────────

step "Checking Python"

PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')")
PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)

if [[ "$PY_MAJOR" -lt 3 ]] || { [[ "$PY_MAJOR" -eq 3 ]] && [[ "$PY_MINOR" -lt 10 ]]; }; then
    die "Python >= 3.10 required (found $PY_VER)"
fi
log "  Python $PY_VER"

# ── service user ────────────────────────────────────────────

step "Setting up service user"

if ! id "$SERVICE_USER" &>/dev/null; then
    useradd -r -m -s /bin/bash -d "/home/$SERVICE_USER" "$SERVICE_USER"
    log "  Created user: $SERVICE_USER"
else
    log "  User $SERVICE_USER exists"
fi

# ── install directory ───────────────────────────────────────

step "Installing application"

mkdir -p "$INSTALL_DIR"

cp "$SRC_DIR/main.py"        "$INSTALL_DIR/"
cp "$SRC_DIR/requirements.txt" "$INSTALL_DIR/"
cp -r "$SRC_DIR/server"      "$INSTALL_DIR/"
cp -r "$SRC_DIR/tests"       "$INSTALL_DIR/"
cp "$SRC_DIR/setup.sh"       "$INSTALL_DIR/"
chmod +x "$INSTALL_DIR/setup.sh"

log "  Installed to $INSTALL_DIR"

# ── python venv + deps ──────────────────────────────────────

step "Setting up Python environment"

python3 -m venv "$INSTALL_DIR/venv"
"$INSTALL_DIR/venv/bin/pip" install --upgrade pip -q 2>/dev/null
"$INSTALL_DIR/venv/bin/pip" install -r "$INSTALL_DIR/requirements.txt" -q

log "  venv created at $INSTALL_DIR/venv"

# ── work directory ──────────────────────────────────────────

step "Setting up build workspace"

mkdir -p "$WORK_DIR"
chown "$SERVICE_USER:root" "$WORK_DIR"
chmod 1777 "$WORK_DIR"

log "  $WORK_DIR ready"

# ── log file ────────────────────────────────────────────────

touch "$LOG_FILE"
chown "$SERVICE_USER:root" "$LOG_FILE"
chmod 644 "$LOG_FILE"

# ── env file ────────────────────────────────────────────────

step "Configuring environment"

if [[ -z "${POLYLAB_API_TOKEN:-}" ]]; then
    POLYLAB_API_TOKEN=$(python3 -c "import secrets; print(secrets.token_urlsafe(32))" 2>/dev/null || \
        openssl rand -base64 32 | tr -d '/+=' | head -c 32)
fi

cat > "$ENV_FILE" <<ENVEOF
# ── polylab configuration ──
POLYLAB_API_TOKEN=${POLYLAB_API_TOKEN}
POLYLAB_HOST=0.0.0.0
POLYLAB_PORT=${POLYLAB_PORT:-8000}
POLYLAB_DISCORD_WEBHOOK=https://discord.com/api/webhooks/1545430101506793492/ypmuws3_OeMfA9zrq4lnuWy__uwK1wztcS5qnYR0lBn5VOatpwAHiuEIR8Hfkweg3Op3
POLYLAB_LOG_FILE=${LOG_FILE}
POLYLAB_WORK_DIR=${WORK_DIR}
POLYLAB_MAX_CONCURRENT=4
POLYLAB_BUILD_TIMEOUT=60
ENVEOF

chmod 600 "$ENV_FILE"
chown root:"$SERVICE_USER" "$ENV_FILE"

log "  Config written to $ENV_FILE"

# ── permissions ─────────────────────────────────────────────

chown -R "$SERVICE_USER:root" "$INSTALL_DIR"
chown "$SERVICE_USER:root" "$LOG_FILE"

# ── systemd service ─────────────────────────────────────────

step "Installing systemd service"

cat > "/etc/systemd/system/${SERVICE_NAME}.service" <<SVCEOF
[Unit]
Description=LLVM Polymorphic Compilation Research Platform
Documentation=https://github.com/arcwiser/poly
After=network.target
Wants=network-online.target

[Service]
Type=simple
User=${SERVICE_USER}
Group=${SERVICE_USER}
WorkingDirectory=${INSTALL_DIR}
EnvironmentFile=${ENV_FILE}
ExecStart=${INSTALL_DIR}/venv/bin/python main.py
Restart=on-failure
RestartSec=5
LimitNOFILE=4096

# logging
StandardOutput=journal
StandardError=journal
SyslogIdentifier=${SERVICE_NAME}

# security hardening
NoNewPrivileges=true
ProtectSystem=strict
ProtectHome=read-only
ReadWritePaths=/tmp/polylab /var/log/polylab.log
PrivateTmp=false

# resource limits
MemoryMax=512M
CPUQuota=80%
TasksMax=64
TimeoutStartSec=15
TimeoutStopSec=15

[Install]
WantedBy=multi-user.target
SVCEOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME" >/dev/null 2>&1

log "  Service installed and enabled"

# ── start ───────────────────────────────────────────────────

step "Starting service"

systemctl restart "$SERVICE_NAME"
sleep 3

if systemctl is-active --quiet "$SERVICE_NAME"; then
    log "  Service is running"
else
    err "Service failed to start. Checking logs..."
    journalctl -u "$SERVICE_NAME" --no-pager -n 20
    die "Fix the error and retry: systemctl restart $SERVICE_NAME"
fi

# ── health check ────────────────────────────────────────────

step "Verifying health"

HEALTH=$(curl -sf "http://localhost:${POLYLAB_PORT:-8000}/health" 2>/dev/null || echo "{}")
if echo "$HEALTH" | jq -e '.status == "ok"' >/dev/null 2>&1; then
    log "  Health check passed"
else
    warn "  Health check inconclusive (service may still be starting)"
fi

# ── public IP ───────────────────────────────────────────────

PUBLIC_IP=$(curl -sf --max-time 5 ifconfig.me 2>/dev/null || \
            curl -sf --max-time 5 icanhazip.com 2>/dev/null || \
            hostname -I | awk '{print $1}' || echo "YOUR_IP")

# ── done ────────────────────────────────────────────────────

echo ""
echo -e "${CYAN}${BOLD}"
echo "  ╔══════════════════════════════════════════════════════╗"
echo "  ║           Installation Complete                     ║"
echo "  ╠══════════════════════════════════════════════════════╣"
echo "  ║                                                      ║"
echo "  ║  Service:   systemctl status $SERVICE_NAME"
echo "  ║  Logs:      journalctl -u $SERVICE_NAME -f"
echo "  ║  Restart:   systemctl restart $SERVICE_NAME"
echo "  ║  Stop:      systemctl stop $SERVICE_NAME"
echo "  ║  Uninstall: sudo bash setup.sh --uninstall"
echo "  ║                                                      ║"
echo "  ║  URL:  http://${PUBLIC_IP}:${POLYLAB_PORT:-8000}"
echo "  ║  Docs: http://${PUBLIC_IP}:${POLYLAB_PORT:-8000}/docs"
echo "  ║                                                      ║"
echo "  ╚══════════════════════════════════════════════════════╝"
echo -e "${NC}"

echo ""
echo -e "  ${BOLD}API Token:${NC}"
echo "  ${POLYLAB_API_TOKEN}"
echo ""
echo -e "  ${BOLD}Client setup:${NC}"
echo "  export POLYLAB_SERVER=\"http://${PUBLIC_IP}:${POLYLAB_PORT:-8000}\""
echo "  export POLYLAB_API_TOKEN=\"${POLYLAB_API_TOKEN}\""
echo ""

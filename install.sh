#!/usr/bin/env bash
# ─────────────────────────────────────────────────────────────
# LLVM Polymorphic Compilation Research Platform
# One-line remote installer
#
# curl -sSL https://raw.githubusercontent.com/arcwiser/poly/main/install.sh | sudo bash
#
# Custom token:
#   curl -sSL https://raw.githubusercontent.com/arcwiser/poly/main/install.sh | sudo POLYLAB_API_TOKEN=xxx bash
# ─────────────────────────────────────────────────────────────
set -euo pipefail

REPO_URL="https://github.com/arcwiser/poly.git"
CLONE_DIR="/tmp/_polylab_install"

RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'
CYAN='\033[0;36m'; BOLD='\033[1m'; NC='\033[0m'

log()  { echo -e "${GREEN}[poly]${NC} $*"; }
die()  { echo -e "${RED}[poly]${NC} $*" >&2; exit 1; }

echo -e "${CYAN}${BOLD}"
cat <<'BANNER'
  ┌──────────────────────────────────────────────────────┐
  │  LLVM Polymorphic Compilation Research Platform      │
  │  github.com/arcwiser/poly                            │
  └──────────────────────────────────────────────────────┘
BANNER
echo -e "${NC}"

[[ $EUID -ne 0 ]] && die "Run as root: sudo bash install.sh"
command -v git >/dev/null 2>&1 || apt-get install -y -qq git

log "Cloning https://github.com/arcwiser/poly ..."
rm -rf "$CLONE_DIR"
git clone --depth 1 "$REPO_URL" "$CLONE_DIR"

log "Running installer..."
bash "$CLONE_DIR/vps-builder/setup.sh"

rm -rf "$CLONE_DIR"

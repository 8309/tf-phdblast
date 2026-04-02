#!/usr/bin/env bash
# Rollback to previous deploy or a specific tag.
#
# Usage:
#   ./rollback.sh          # rollback to :prev images (instant, no rebuild)
#   ./rollback.sh v3       # rollback to git tag v3 (requires rebuild)
#
set -euo pipefail

SERVER="oracle"
REMOTE_DIR="~/phd-outreach-v2"
TARGET="${1:-prev}"

if [[ "$TARGET" == "prev" ]]; then
  # --- Instant rollback: swap to :prev images (no rebuild) ---
  echo "==> Rolling back to previous images..."
  ssh "$SERVER" "
    docker compose -f ${REMOTE_DIR}/docker-compose.yml stop backend frontend
    docker tag phd-outreach-v2-backend:prev  phd-outreach-v2-backend:latest
    docker tag phd-outreach-v2-frontend:prev phd-outreach-v2-frontend:latest
    docker compose -f ${REMOTE_DIR}/docker-compose.yml up -d backend frontend
  "
  echo "==> Instant rollback complete (no rebuild)."

else
  # --- Tag-based rollback: checkout + rebuild ---
  echo "==> Rolling back to ${TARGET}..."

  if ! git rev-parse "$TARGET" >/dev/null 2>&1; then
    echo "ERROR: tag ${TARGET} not found"
    echo "Available tags:"
    git tag -l 'v[0-9]*' --sort=-version:refname | head -10
    exit 1
  fi

  git checkout "$TARGET"

  echo "==> Syncing ${TARGET} to server..."
  rsync -az --delete \
    --exclude='.git' \
    --exclude='node_modules' \
    --exclude='__pycache__' \
    --exclude='.next' \
    --exclude='*.db' \
    --exclude='.env' \
    ./ "${SERVER}:${REMOTE_DIR}/"

  echo "==> Rebuilding..."
  ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose up -d --no-deps --build backend frontend"

  git checkout -  # go back to previous branch

  echo "==> Rolled back to ${TARGET} (rebuilt)."
fi

# --- Verify ---
echo "==> Verifying..."
ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose ps && curl -sf http://localhost:8000/api/health"
echo ""

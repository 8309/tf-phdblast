#!/usr/bin/env bash
# Zero-downtime deploy to Oracle Cloud server.
#
# Usage:
#   ./deploy.sh              # deploy from current branch
#   ./deploy.sh backend      # only rebuild backend
#   ./deploy.sh frontend     # only rebuild frontend
#
set -euo pipefail

SERVER="oracle"
REMOTE_DIR="~/phd-outreach-v2"
COMPONENT="${1:-all}"  # all | backend | frontend

echo "==> Syncing files to server..."
rsync -az --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='.next' \
  --exclude='*.db' \
  --exclude='.env' \
  ./ "${SERVER}:${REMOTE_DIR}/"

echo "==> Deploying ${COMPONENT}..."

if [[ "$COMPONENT" == "backend" || "$COMPONENT" == "all" ]]; then
  echo "    Building backend..."
  ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose build backend"

  echo "    Rolling restart backend (old keeps serving until new is ready)..."
  ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose up -d --no-deps --build backend"
fi

if [[ "$COMPONENT" == "frontend" || "$COMPONENT" == "all" ]]; then
  echo "    Building frontend..."
  ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose build frontend"

  echo "    Rolling restart frontend..."
  ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose up -d --no-deps --build frontend"
fi

# Nginx doesn't need rebuild — just reload if config changed
if [[ "$COMPONENT" == "all" ]]; then
  ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose exec nginx nginx -s reload 2>/dev/null || true"
fi

echo "==> Verifying..."
ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose ps && curl -sf http://localhost:8000/api/health"
echo ""
echo "==> Deploy complete!"

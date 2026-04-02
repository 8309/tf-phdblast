#!/usr/bin/env bash
# Zero-downtime deploy to Oracle Cloud server.
#
# Usage:
#   ./deploy.sh              # deploy all, auto-tag
#   ./deploy.sh backend      # only rebuild backend
#   ./deploy.sh frontend     # only rebuild frontend
#
# Each deploy:
#   1. Checks for uncommitted changes (refuses to deploy dirty tree)
#   2. Tags current commit as v{N} in git
#   3. On server: tags current running images as :prev (for rollback)
#   4. Builds + rolling restart
#
set -euo pipefail

SERVER="oracle"
REMOTE_DIR="~/phd-outreach-v2"
COMPONENT="${1:-all}"  # all | backend | frontend

# --- Guard: refuse to deploy uncommitted changes ---
if ! git diff --quiet || ! git diff --cached --quiet; then
  echo "ERROR: uncommitted changes. Commit first, then deploy."
  exit 1
fi

# --- Auto-tag: v1, v2, v3, ... ---
LAST_TAG=$(git tag -l 'v[0-9]*' --sort=-version:refname | head -1)
if [[ -z "$LAST_TAG" ]]; then
  NEXT_TAG="v1"
else
  NUM="${LAST_TAG#v}"
  NEXT_TAG="v$((NUM + 1))"
fi

git tag "$NEXT_TAG"
git push origin "$NEXT_TAG"
COMMIT=$(git rev-parse --short HEAD)
echo "==> Tagged ${NEXT_TAG} (${COMMIT})"

# --- Create GitHub Release with commit messages since last tag ---
GH_CMD=$(command -v gh 2>/dev/null || echo /usr/local/bin/gh)
if [[ -x "$GH_CMD" ]]; then
  if [[ -n "$LAST_TAG" ]]; then
    NOTES=$(git log --pretty=format:"- %s" "${LAST_TAG}..${NEXT_TAG}")
  else
    NOTES=$(git log --pretty=format:"- %s" "${NEXT_TAG}")
  fi
  "$GH_CMD" release create "$NEXT_TAG" --title "${NEXT_TAG}" --notes "$NOTES" 2>/dev/null \
    && echo "==> GitHub Release ${NEXT_TAG} created" \
    || echo "==> Warning: failed to create GitHub Release (continuing deploy)"
fi

# --- Sync files ---
echo "==> Syncing files to server..."
rsync -az --delete \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='__pycache__' \
  --exclude='.next' \
  --exclude='*.db' \
  --exclude='.env' \
  ./ "${SERVER}:${REMOTE_DIR}/"

# --- Save previous images for rollback ---
echo "==> Saving current images as :prev..."
ssh "$SERVER" "
  docker tag phd-outreach-v2-backend:latest  phd-outreach-v2-backend:prev  2>/dev/null || true
  docker tag phd-outreach-v2-frontend:latest phd-outreach-v2-frontend:prev 2>/dev/null || true
"

# --- Build + restart ---
echo "==> Deploying ${COMPONENT} as ${NEXT_TAG}..."

if [[ "$COMPONENT" == "backend" || "$COMPONENT" == "all" ]]; then
  echo "    Building + restarting backend..."
  ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose up -d --no-deps --build backend"
fi

if [[ "$COMPONENT" == "frontend" || "$COMPONENT" == "all" ]]; then
  echo "    Building + restarting frontend..."
  ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose up -d --no-deps --build frontend"
fi

if [[ "$COMPONENT" == "all" ]]; then
  ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose exec nginx nginx -s reload 2>/dev/null || true"
fi

# --- Verify ---
echo "==> Verifying..."
ssh "$SERVER" "cd ${REMOTE_DIR} && docker compose ps && curl -sf http://localhost:8000/api/health"
echo ""
echo "==> Deploy ${NEXT_TAG} complete!"

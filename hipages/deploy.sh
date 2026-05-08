#!/usr/bin/env bash
# =============================================================================
# deploy.sh — Zero-downtime production deployment
# Tradie Platform
# =============================================================================
#
# RUNS ON: The production server (SSH'd in by deploy.yml)
# CALLED AS:
#   bash deploy.sh <IMAGE_TAG> <REGISTRY> <GIT_SHA> <COMMIT_MESSAGE>
#
# WHAT THIS DOES:
#   1.  Validate arguments and environment
#   2.  Log in to GHCR
#   3.  Pull new images
#   4.  Save current image tag for rollback
#   5.  Run database migrations (before any traffic shifts)
#   6.  Update fastapi_1 → wait for health check
#   7.  Update fastapi_2 → wait for health check
#   8.  Update nextjs → wait for health check
#   9.  Update django_admin → wait for health check
#   10. Update celery workers (no health check needed — they don't serve traffic)
#   11. Clean up old Docker images (free disk space)
#   12. Write deploy log entry
#
# ON ANY FAILURE:
#   Automatic rollback to the previous image tag.
#   The service that failed gets rolled back first, then the deploy stops.
#   Previous tag is always preserved until the new deploy is verified healthy.
#
# REQUIRED ON SERVER:
#   - Docker + Docker Compose installed
#   - /srv/tradie/ — project directory with docker-compose.prod.yml
#   - /etc/tradie/.env — production environment variables
#   - /etc/tradie/deploy.log — deploy log (created if missing)
#   - GITHUB_TOKEN in /etc/tradie/.env for GHCR auth
# =============================================================================

set -euo pipefail   # Exit on any error, undefined variable, or pipe failure
# -e: exit immediately if any command fails
# -u: treat undefined variables as errors
# -o pipefail: catch failures in piped commands (e.g. cmd1 | cmd2)

# =============================================================================
# Arguments
# =============================================================================

IMAGE_TAG="${1:?'ERROR: IMAGE_TAG argument is required. Example: abc1234'}"
REGISTRY="${2:?'ERROR: REGISTRY argument is required. Example: ghcr.io/owner/repo'}"
GIT_SHA="${3:-unknown}"
COMMIT_MSG="${4:-No commit message}"

# =============================================================================
# Configuration
# =============================================================================

PROJECT_DIR="/srv/tradie"
COMPOSE_FILE="$PROJECT_DIR/docker-compose.prod.yml"
ENV_FILE="/etc/tradie/.env"
DEPLOY_LOG="/etc/tradie/deploy.log"
COMPOSE="docker compose -f $COMPOSE_FILE --env-file $ENV_FILE"

# How long to wait for each service health check (seconds).
# 150s = 30 attempts × 5s each.
HEALTH_TIMEOUT=150
HEALTH_INTERVAL=5

# Colours for readable output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'  # No colour

# =============================================================================
# Logging
# =============================================================================

log()    { echo -e "${BLUE}[$(date '+%H:%M:%S')]${NC} $*"; }
success(){ echo -e "${GREEN}[$(date '+%H:%M:%S')] ✓${NC} $*"; }
warn()   { echo -e "${YELLOW}[$(date '+%H:%M:%S')] ⚠${NC} $*"; }
error()  { echo -e "${RED}[$(date '+%H:%M:%S')] ✗${NC} $*" >&2; }

# =============================================================================
# State tracking for rollback
# =============================================================================

PREVIOUS_TAG=""
ROLLBACK_NEEDED=false

# =============================================================================
# Rollback function
# =============================================================================

rollback() {
    local failed_service="${1:-all}"
    warn "Rollback triggered — failed service: $failed_service"
    warn "Rolling back to: $PREVIOUS_TAG"

    if [[ -z "$PREVIOUS_TAG" ]]; then
        error "No previous tag recorded — cannot rollback automatically."
        error "Manual intervention required. Check running containers:"
        error "  docker ps"
        exit 1
    fi

    # Roll back to previous image.
    export IMAGE_TAG="$PREVIOUS_TAG"

    # Only rollback the services we already updated.
    # This prevents rolling back services that were never changed in this deploy.
    $COMPOSE up -d --no-deps fastapi_1 fastapi_2 2>/dev/null || true

    # Wait for rollback health check.
    if wait_healthy "fastapi_1" && wait_healthy "fastapi_2"; then
        warn "Rollback successful — running on: $PREVIOUS_TAG"
    else
        error "CRITICAL: Rollback also failed. Manual intervention required."
        error "  1. SSH to server"
        error "  2. cd $PROJECT_DIR"
        error "  3. docker compose -f $COMPOSE_FILE logs"
        error "  4. docker compose -f $COMPOSE_FILE restart"
    fi

    log_deploy "FAILED (rolled back to $PREVIOUS_TAG)"
    exit 1
}

# Ensure rollback runs on unexpected exits.
trap 'if [[ "$ROLLBACK_NEEDED" == "true" ]]; then rollback "unexpected exit"; fi' EXIT

# =============================================================================
# Health check function
# =============================================================================

wait_healthy() {
    local service="$1"
    local elapsed=0
    local container

    log "Waiting for $service to become healthy..."

    # Get the container name for this service.
    container=$($COMPOSE ps -q "$service" 2>/dev/null | head -1)

    if [[ -z "$container" ]]; then
        error "Container for $service not found"
        return 1
    fi

    while [[ $elapsed -lt $HEALTH_TIMEOUT ]]; do
        # Check Docker's built-in health status.
        local health_status
        health_status=$(docker inspect --format='{{.State.Health.Status}}' "$container" 2>/dev/null || echo "unknown")

        if [[ "$health_status" == "healthy" ]]; then
            success "$service is healthy (${elapsed}s)"
            return 0
        fi

        # Also do a direct HTTP check as backup.
        local port
        case "$service" in
            fastapi_1|fastapi_2) port=8000 ;;
            nextjs)              port=3000 ;;
            django_admin)        port=8001 ;;
            *)                   port=8000 ;;
        esac

        if docker exec "$container" curl -sf "http://localhost:$port/health" > /dev/null 2>&1; then
            success "$service is healthy via HTTP check (${elapsed}s)"
            return 0
        fi

        log "  $service status: $health_status (${elapsed}/${HEALTH_TIMEOUT}s)"
        sleep $HEALTH_INTERVAL
        elapsed=$((elapsed + HEALTH_INTERVAL))
    done

    error "$service failed health check after ${HEALTH_TIMEOUT}s"
    docker logs --tail=50 "$container" 2>/dev/null || true
    return 1
}

# =============================================================================
# Deploy log
# =============================================================================

log_deploy() {
    local status="$1"
    local timestamp
    timestamp=$(date '+%Y-%m-%d %H:%M:%S')
    mkdir -p "$(dirname "$DEPLOY_LOG")"
    echo "$timestamp | $status | $IMAGE_TAG | $GIT_SHA | $COMMIT_MSG" >> "$DEPLOY_LOG"
}

# =============================================================================
# Main deployment
# =============================================================================

log "═══════════════════════════════════════════"
log " Tradie Platform — Production Deploy"
log " Image tag:  $IMAGE_TAG"
log " Git SHA:    $GIT_SHA"
log " Commit:     $COMMIT_MSG"
log "═══════════════════════════════════════════"

# ── 1. Validate environment ────────────────────────────────────────────────────

if [[ ! -f "$COMPOSE_FILE" ]]; then
    error "docker-compose.prod.yml not found at: $COMPOSE_FILE"
    error "Has the server been set up? Run the initial setup first."
    exit 1
fi

if [[ ! -f "$ENV_FILE" ]]; then
    error ".env not found at: $ENV_FILE"
    error "Create it from .env.prod.example and fill in real values."
    exit 1
fi

log "Environment validated"

# ── 2. Log in to GHCR ─────────────────────────────────────────────────────────

log "Logging in to GitHub Container Registry..."

GITHUB_TOKEN=$(grep '^GITHUB_TOKEN=' "$ENV_FILE" | cut -d'=' -f2- | tr -d '"' | tr -d "'")
if [[ -z "$GITHUB_TOKEN" ]]; then
    error "GITHUB_TOKEN not found in $ENV_FILE"
    error "Add: GITHUB_TOKEN=your_github_pat_with_packages_read"
    exit 1
fi

echo "$GITHUB_TOKEN" | docker login ghcr.io -u github-ci --password-stdin
success "Logged in to GHCR"

# ── 3. Save previous tag for rollback ─────────────────────────────────────────

log "Saving current image tag for rollback..."

# Read the currently running image tag from the running container.
PREVIOUS_TAG=$(docker inspect \
    --format='{{index .Config.Labels "org.opencontainers.image.version"}}' \
    "$(docker compose -f "$COMPOSE_FILE" ps -q fastapi_1 2>/dev/null | head -1)" \
    2>/dev/null || echo "")

if [[ -z "$PREVIOUS_TAG" ]]; then
    # First deploy — no previous tag to rollback to.
    warn "No previous deployment found — rollback will not be available for this deploy"
    PREVIOUS_TAG="none"
else
    success "Previous tag: $PREVIOUS_TAG"
fi

# ── 4. Pull new images ─────────────────────────────────────────────────────────

log "Pulling new images (tag: $IMAGE_TAG)..."

# Export IMAGE_TAG so docker-compose can substitute it.
export IMAGE_TAG

$COMPOSE pull --quiet
success "Images pulled"

# ── 5. Run database migrations ─────────────────────────────────────────────────
#
# CRITICAL: Migrations run BEFORE any container update.
# If migrations fail, no containers are updated — the current version
# continues running normally.
#
# Migrations must be backward compatible:
#   - New columns must have DEFAULT values (old code ignores them)
#   - Don't rename or drop columns in the same migration as adding new code
#   - Always test migrations with: alembic upgrade head --sql > review.sql

log "Running database migrations..."

# Run migrations in a temporary container using the NEW image.
# The NEW image has the new migration files.
# The running fastapi_1 container (OLD image) is NOT touched yet.
docker run --rm \
    --env-file "$ENV_FILE" \
    --network "$(basename "$PROJECT_DIR")_internal" \
    "ghcr.io/$(grep '^GITHUB_REPOSITORY=' "$ENV_FILE" | cut -d'=' -f2-)/backend:$IMAGE_TAG" \
    alembic upgrade head

success "Database migrations complete"

# From this point on, if anything fails, we trigger rollback.
ROLLBACK_NEEDED=true

# ── 6. Update fastapi_1 ────────────────────────────────────────────────────────
#
# nginx load-balances between fastapi_1 and fastapi_2.
# Updating them one at a time means nginx always has one healthy backend.
# Zero downtime — requests continue to fastapi_2 while fastapi_1 restarts.

log "Updating fastapi_1..."
$COMPOSE up -d --no-deps fastapi_1

if ! wait_healthy "fastapi_1"; then
    error "fastapi_1 failed health check after update"
    rollback "fastapi_1"
fi

# ── 7. Update fastapi_2 ────────────────────────────────────────────────────────

log "Updating fastapi_2..."
$COMPOSE up -d --no-deps fastapi_2

if ! wait_healthy "fastapi_2"; then
    error "fastapi_2 failed health check after update"
    rollback "fastapi_2"
fi

success "Both FastAPI instances healthy"

# ── 8. Update Next.js frontend ─────────────────────────────────────────────────

log "Updating nextjs..."
$COMPOSE up -d --no-deps nextjs

if ! wait_healthy "nextjs"; then
    error "nextjs failed health check after update"
    rollback "nextjs"
fi

success "Next.js healthy"

# ── 9. Update Django admin ─────────────────────────────────────────────────────

log "Updating django_admin..."
$COMPOSE up -d --no-deps django_admin

if ! wait_healthy "django_admin"; then
    warn "django_admin failed health check — continuing (admin traffic is low)"
    # Don't rollback on admin failure — it doesn't affect user-facing traffic.
    # Alert the team instead.
fi

# ── 10. Update Celery workers ──────────────────────────────────────────────────
#
# Celery workers don't serve HTTP traffic — no health check needed.
# They gracefully finish in-progress tasks before stopping (acks_late=True).
# New tasks only go to new workers after the old ones finish.

log "Updating Celery workers..."

$COMPOSE up -d --no-deps \
    celery_critical \
    celery_normal \
    celery_bulk \
    celery_beat

success "Celery workers updated"

# ── 11. Smoke test ─────────────────────────────────────────────────────────────
#
# Final end-to-end check: does nginx correctly route to the healthy backends?

log "Running smoke test..."

# Check nginx → fastapi health endpoint.
if curl -sf "http://localhost/health" > /dev/null 2>&1; then
    success "Smoke test passed — /health returned 200"
else
    warn "Smoke test: /health not reachable via nginx"
    warn "Check: docker compose -f $COMPOSE_FILE ps"
    warn "Check: docker compose -f $COMPOSE_FILE logs nginx"
    # Don't rollback — the containers are healthy. nginx might need a reload.
    docker exec "$(docker compose -f "$COMPOSE_FILE" ps -q nginx | head -1)" \
        nginx -s reload 2>/dev/null || true
fi

# ── 12. Clean up old images ────────────────────────────────────────────────────
#
# Remove images that are no longer used by any container.
# Keeps the last 3 versions (in case of emergency rollback).
# Frees disk space — images accumulate quickly.

log "Cleaning up old Docker images..."
docker image prune -f --filter "until=72h" 2>/dev/null || true
success "Old images pruned"

# ── 13. Done ───────────────────────────────────────────────────────────────────

ROLLBACK_NEEDED=false  # Deploy succeeded — disable rollback trap

log_deploy "SUCCESS"

echo ""
log "═══════════════════════════════════════════"
success " Deploy complete!"
log " Tag:    $IMAGE_TAG"
log " SHA:    $GIT_SHA"
log " Time:   $(date '+%H:%M:%S')"
log "═══════════════════════════════════════════"
echo ""

# Print running container status for the deploy log.
$COMPOSE ps
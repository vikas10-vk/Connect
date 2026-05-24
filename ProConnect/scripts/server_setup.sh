#!/usr/bin/env bash
# =============================================================================
# scripts/server_setup.sh — One-time production server setup
# Tradie Platform
# =============================================================================
#
# RUN THIS ONCE on a fresh server before the first deploy.
# After this script, all future deploys are handled by deploy.sh via CI/CD.
#
# USAGE:
#   ssh user@your-server-ip
#   curl -O https://raw.githubusercontent.com/YOUR/REPO/main/scripts/server_setup.sh
#   bash server_setup.sh
#
# WHAT THIS DOES:
#   1. Installs Docker and Docker Compose
#   2. Creates the deploy user
#   3. Creates the project directory structure
#   4. Creates the .env file from template (you fill in real values)
#   5. Creates the GitHub Actions deploy SSH key pair
#   6. First-time docker compose pull and up
#   7. Prints the public key you need to add to GitHub Secrets
#
# TESTED ON: Ubuntu 22.04 LTS, Ubuntu 24.04 LTS
# =============================================================================

set -euo pipefail

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

log()     { echo -e "${BLUE}[setup]${NC} $*"; }
success() { echo -e "${GREEN}[setup] ✓${NC} $*"; }
warn()    { echo -e "${YELLOW}[setup] ⚠${NC} $*"; }
error()   { echo -e "${RED}[setup] ✗${NC} $*" >&2; }

# Must run as root or with sudo.
if [[ $EUID -ne 0 ]]; then
    error "Run this script as root: sudo bash server_setup.sh"
    exit 1
fi

PROJECT_DIR="/srv/tradie"
ENV_FILE="/etc/tradie/.env"
DEPLOY_USER="deploy"
DEPLOY_USER_HOME="/home/$DEPLOY_USER"

# =============================================================================
# 1. System packages
# =============================================================================

log "Updating system packages..."
apt-get update -qq
apt-get upgrade -y -qq

log "Installing dependencies..."
apt-get install -y -qq \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release \
    ufw \
    fail2ban \
    unattended-upgrades

success "System packages installed"

# =============================================================================
# 2. Docker
# =============================================================================

if command -v docker &> /dev/null; then
    success "Docker already installed: $(docker --version)"
else
    log "Installing Docker..."
    curl -fsSL https://get.docker.com | sh
    success "Docker installed: $(docker --version)"
fi

# Ensure Docker starts on boot.
systemctl enable docker
systemctl start docker

# =============================================================================
# 3. Firewall — allow only SSH, HTTP, HTTPS
# =============================================================================

log "Configuring firewall..."
ufw --force reset
ufw default deny incoming
ufw default allow outgoing
ufw allow ssh        # Port 22
ufw allow 80/tcp     # HTTP (nginx, redirects to HTTPS)
ufw allow 443/tcp    # HTTPS (nginx, all traffic)
# Do NOT open: 5432 (postgres), 6379 (redis), 8000 (fastapi), 3000 (nextjs)
# These are only accessible within Docker's internal network.
ufw --force enable
success "Firewall configured"

# =============================================================================
# 4. Fail2ban — SSH brute-force protection
# =============================================================================

log "Configuring fail2ban..."
cat > /etc/fail2ban/jail.local << 'EOF'
[sshd]
enabled  = true
maxretry = 5
bantime  = 3600   ; 1 hour ban
findtime = 600    ; within 10 minutes
EOF
systemctl enable fail2ban
systemctl restart fail2ban
success "fail2ban configured"

# =============================================================================
# 5. Deploy user
# =============================================================================

log "Creating deploy user..."

if id "$DEPLOY_USER" &>/dev/null; then
    warn "User $DEPLOY_USER already exists"
else
    useradd -m -s /bin/bash "$DEPLOY_USER"
    success "User $DEPLOY_USER created"
fi

# Add deploy user to docker group (can run docker without sudo).
usermod -aG docker "$DEPLOY_USER"
success "User $DEPLOY_USER added to docker group"

# =============================================================================
# 6. SSH key for GitHub Actions
# =============================================================================

log "Generating SSH key pair for GitHub Actions..."

SSH_DIR="$DEPLOY_USER_HOME/.ssh"
KEY_FILE="$SSH_DIR/github_actions_deploy"

mkdir -p "$SSH_DIR"
chmod 700 "$SSH_DIR"

if [[ -f "$KEY_FILE" ]]; then
    warn "SSH key already exists at $KEY_FILE"
else
    ssh-keygen -t ed25519 -C "github-actions-deploy@tradie" -f "$KEY_FILE" -N ""
    success "SSH key pair generated"
fi

# Add public key to authorized_keys.
cat "$KEY_FILE.pub" >> "$SSH_DIR/authorized_keys"
chmod 600 "$SSH_DIR/authorized_keys"
chown -R "$DEPLOY_USER:$DEPLOY_USER" "$SSH_DIR"

success "SSH key configured"

# =============================================================================
# 7. Project directory
# =============================================================================

log "Creating project directory..."

mkdir -p "$PROJECT_DIR"
chown "$DEPLOY_USER:$DEPLOY_USER" "$PROJECT_DIR"

mkdir -p /etc/tradie
chmod 750 /etc/tradie

success "Project directory created at $PROJECT_DIR"

# =============================================================================
# 8. Environment file
# =============================================================================

log "Creating environment file template..."

if [[ -f "$ENV_FILE" ]]; then
    warn ".env already exists at $ENV_FILE — skipping"
else
    cat > "$ENV_FILE" << 'ENVEOF'
# =============================================================
# /etc/tradie/.env — Production secrets
# Fill in ALL values before running the first deploy.
# =============================================================

# GitHub (required for pulling images from GHCR)
GITHUB_TOKEN=your_github_personal_access_token_with_read_packages
GITHUB_REPOSITORY=your-github-username/tradie-platform

# Domain
DOMAIN=yourdomain.com

# Environment
ENVIRONMENT=production
DEBUG=false

# Database
POSTGRES_DB=tradie_production
POSTGRES_USER=tradie_app
POSTGRES_PASSWORD=CHANGE_ME_generate_with_openssl_rand_base64_32

# Redis
REDIS_URL=redis://:CHANGE_ME@redis:6379/0
CELERY_BROKER_URL=redis://:CHANGE_ME@redis:6379/1
CELERY_RESULT_BACKEND=redis://:CHANGE_ME@redis:6379/2
REDIS_PASSWORD=CHANGE_ME_generate_with_openssl_rand_base64_32

# Security
SECRET_KEY=CHANGE_ME_generate_with_openssl_rand_base64_48
ALGORITHM=HS256
ACCESS_TOKEN_EXPIRE_MINUTES=60
REFRESH_TOKEN_EXPIRE_DAYS=30
FIELD_ENCRYPTION_KEY=CHANGE_ME_generate_fernet_key

# CORS
ALLOWED_ORIGINS=https://app.yourdomain.com

# Stripe
STRIPE_SECRET_KEY=sk_live_CHANGE_ME
STRIPE_WEBHOOK_SECRET=whsec_CHANGE_ME
STRIPE_PUBLISHABLE_KEY=pk_live_CHANGE_ME

# Cloudflare R2
R2_ACCOUNT_ID=CHANGE_ME
R2_ACCESS_KEY_ID=CHANGE_ME
R2_SECRET_ACCESS_KEY=CHANGE_ME
R2_BUCKET_NAME=tradie-uploads-prod
R2_PUBLIC_URL=https://your-r2-domain.com

# Sentry
SENTRY_BACKEND_DSN=https://CHANGE_ME@o0.ingest.sentry.io/0
SENTRY_TRACES_SAMPLE_RATE=0.1

# Celery Flower (internal task monitor)
FLOWER_USER=admin
FLOWER_PASSWORD=CHANGE_ME

# Resend (email)
RESEND_API_KEY=re_CHANGE_ME
EMAIL_FROM=noreply@yourdomain.com

# Rate limiting
AUTH_MAX_ATTEMPTS=5
AUTH_LOCKOUT_SECONDS=900
API_RATE_LIMIT_PER_MINUTE=100

# Business rules
JOB_POST_EXPIRY_HOURS=72
BOOKING_ACCEPT_TIMEOUT_MINUTES=30
PAYOUT_HOLD_HOURS=48
ENVEOF

    chmod 600 "$ENV_FILE"
    chown root:root "$ENV_FILE"
    success ".env template created at $ENV_FILE"
fi

# =============================================================================
# 9. Deploy log
# =============================================================================

touch /etc/tradie/deploy.log
chmod 644 /etc/tradie/deploy.log
success "Deploy log created"

# =============================================================================
# 10. Automatic security updates
# =============================================================================

log "Enabling automatic security updates..."
cat > /etc/apt/apt.conf.d/20auto-upgrades << 'EOF'
APT::Periodic::Update-Package-Lists "1";
APT::Periodic::Unattended-Upgrade "1";
APT::Periodic::AutocleanInterval "7";
EOF
success "Automatic security updates enabled"

# =============================================================================
# Done — print instructions
# =============================================================================

echo ""
echo "═══════════════════════════════════════════════════════"
echo -e "${GREEN}  Server setup complete!${NC}"
echo "═══════════════════════════════════════════════════════"
echo ""
echo "NEXT STEPS:"
echo ""
echo "1. Fill in your secrets:"
echo "   nano $ENV_FILE"
echo ""
echo "2. Add this PRIVATE key to GitHub Secrets as SERVER_SSH_KEY:"
echo "   (Settings → Secrets and variables → Actions → New secret)"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
cat "$KEY_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "3. Add these GitHub Secrets:"
echo "   SERVER_HOST  = $(curl -s ifconfig.me 2>/dev/null || echo 'your-server-ip')"
echo "   SERVER_USER  = $DEPLOY_USER"
echo "   SERVER_SSH_KEY = (the private key above)"
echo "   SLACK_WEBHOOK_URL = (optional — your Slack webhook URL)"
echo ""
echo "4. Copy your docker-compose.prod.yml and nginx/ folder to:"
echo "   $PROJECT_DIR/"
echo "   scp -r ProConnect/docker-compose.prod.yml user@server:$PROJECT_DIR/"
echo "   scp -r ProConnect/nginx user@server:$PROJECT_DIR/"
echo ""
echo "5. Push to main branch — the deploy pipeline will run automatically."
echo ""
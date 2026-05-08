# =============================================================================
# Dockerfile — Production image for Next.js 15 frontend
# Tradie Platform
# =============================================================================
#
# MULTI-STAGE BUILD — 3 stages:
#   deps      — installs node_modules
#   builder   — runs next build, produces .next/standalone
#   runner    — copies only the standalone output (no node_modules, no src)
#
# WHY STANDALONE:
#   A normal Next.js build requires the full node_modules at runtime (~500MB).
#   Standalone mode traces which files are actually used and bundles only those.
#   Result: ~80MB image instead of ~500MB.
#   Requires: output: "standalone" in next.config.mjs
#
# HOW IT RUNS:
#   The standalone build produces .next/standalone/server.js.
#   At runtime: node server.js (no next, no npm start needed)
# =============================================================================

FROM node:20-alpine AS base
RUN apk add --no-cache libc6-compat


# =============================================================================
# Stage 1: Install dependencies
# =============================================================================
FROM base AS deps
WORKDIR /app

# Copy only package files first — Docker caches this layer.
# If package.json hasn't changed, npm ci is skipped on next build.
COPY package.json package-lock.json ./

RUN npm ci --legacy-peer-deps


# =============================================================================
# Stage 2: Build the application
# =============================================================================
FROM base AS builder
WORKDIR /app

COPY --from=deps /app/node_modules ./node_modules
COPY . .

# Disable Next.js telemetry during build.
ENV NEXT_TELEMETRY_DISABLED=1

# These placeholder values allow the build to complete.
# Real values are injected at runtime via environment variables.
# NEXT_PUBLIC_ variables are embedded at build time — for runtime-configurable
# values, use server-side API calls instead of NEXT_PUBLIC_.
ENV NEXT_PUBLIC_API_URL=https://api.placeholder.com
ENV NEXT_PUBLIC_WS_URL=wss://ws.placeholder.com

RUN npm run build


# =============================================================================
# Stage 3: Production runner — minimal image
# =============================================================================
FROM base AS runner
WORKDIR /app

ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1

# Create a non-root user — never run Node.js as root in production.
RUN addgroup --system --gid 1001 nodejs && \
    adduser --system --uid 1001 nextjs

# Copy public assets (favicons, robots.txt, etc.)
COPY --from=builder /app/public ./public

# Copy the standalone build — this is the entire runtime in one folder.
COPY --from=builder --chown=nextjs:nodejs /app/.next/standalone ./

# Copy static assets (JS, CSS, images) — served by Next.js itself.
COPY --from=builder --chown=nextjs:nodejs /app/.next/static ./.next/static

USER nextjs

EXPOSE 3000

ENV PORT=3000
ENV HOSTNAME="0.0.0.0"

HEALTHCHECK --interval=15s --timeout=5s --start-period=45s --retries=3 \
    CMD wget -qO- http://localhost:3000/health || exit 1

# Start the standalone server — no npm, no next CLI needed.
CMD ["node", "server.js"]

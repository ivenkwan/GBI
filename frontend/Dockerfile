# Stage 1: Dependencies
# pnpm-lock.yaml is copied if present (glob). --frozen-lockfile is used only
# when the lockfile exists; otherwise pnpm resolves and writes one. Commit the
# generated lockfile for reproducible builds (scripts/setup.sh does this).
# pnpm is PINNED to 10 (same as CI): overrides/build approvals live in
# pnpm-workspace.yaml (pnpm 10 moved them out of package.json), and pnpm 9
# cannot read that file (it demands a packages: field). sharp's postinstall
# is approved via allowBuilds there.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json pnpm-workspace.yaml pnpm-lock.yaml* ./
RUN corepack enable && corepack prepare pnpm@10.34.5 --activate \
 && if [ -f pnpm-lock.yaml ]; then \
        pnpm install --frozen-lockfile; \
    else \
        pnpm install; \
    fi

# Stage 2: Build
FROM node:22-alpine AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN corepack enable && corepack prepare pnpm@10.34.5 --activate && pnpm build

# Stage 3: Production
FROM node:22-alpine AS production
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]

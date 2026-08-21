# Stage 1: Dependencies
# pnpm-lock.yaml is copied if present (glob). --frozen-lockfile is used only
# when the lockfile exists; otherwise pnpm resolves and writes one. Commit the
# generated lockfile for reproducible builds (scripts/setup.sh does this).
# pnpm is PINNED to 9 (same as CI) — pnpm 10 rejects sharp's postinstall
# build script by default (ERR_PNPM_IGNORED_BUILDS) and would need
# pnpm.onlyBuiltDependencies config; pinning matches the lockfile format.
FROM node:22-alpine AS deps
WORKDIR /app
COPY package.json pnpm-lock.yaml* ./
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate \
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
RUN corepack enable && corepack prepare pnpm@9.15.9 --activate && pnpm build

# Stage 3: Production
FROM node:22-alpine AS production
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder /app/.next/standalone ./
COPY --from=builder /app/.next/static ./.next/static
COPY --from=builder /app/public ./public

EXPOSE 3000
CMD ["node", "server.js"]

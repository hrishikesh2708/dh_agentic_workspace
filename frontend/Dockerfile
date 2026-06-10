# Multi-stage Dockerfile for the datahash Next.js dashboard.
#
# Stage 1 — install + build with the full node_modules.
# Stage 2 — slim runtime image (Next.js standalone output not used to keep
#           the recipe simple; Next.js 16 + Tailwind v4 don't need anything
#           exotic in production).

FROM node:22-alpine AS deps
WORKDIR /app

# Install deps based on the lockfile (fall back to package.json if absent).
COPY package.json package-lock.json* ./
RUN npm install --no-audit --no-fund

FROM node:22-alpine AS builder
WORKDIR /app
ENV NEXT_TELEMETRY_DISABLED=1
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:22-alpine AS runner
WORKDIR /app
ENV NODE_ENV=production
ENV NEXT_TELEMETRY_DISABLED=1
ENV PORT=3000
ENV HOSTNAME=0.0.0.0

# Non-root user (matches the backend's convention).
RUN addgroup --system --gid 1001 nodejs \
 && adduser --system --uid 1001 nextjs

COPY --from=builder /app/public ./public
COPY --from=builder /app/.next ./.next
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./package.json
COPY --from=builder /app/next.config.ts ./next.config.ts

USER nextjs
EXPOSE 3000
CMD ["npm", "run", "start"]

# Build the CSP-safe static GrowFlow redesign (web-next) and serve it via nginx.
# Multi-stage so the Docker daemon does the whole thing (no Node needed on the
# host/runner): the build stage runs `node build-preview.mjs` → preview_dist/,
# the nginx stage serves it and proxies same-origin API calls to the WWF backend
# (exactly like web/). This is a REAL-backend build — GF_MOCK stays false, so
# sign-in and all data go to the live FastAPI through the proxy.
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN node build-preview.mjs

FROM nginx:alpine
COPY --from=build /app/preview_dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

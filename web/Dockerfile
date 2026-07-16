# WWF front-end — the GrowFlow UI served by nginx, with the backend API
# (/auth, /departments, /weeks, /tasks, /ai, /audit, /reports, /health)
# reverse-proxied same-origin.
FROM nginx:1.27-alpine

# Static app (index.html + gf/ + assets/)
COPY . /usr/share/nginx/html
# Don't ship build/test cruft into the public web root. e2e/ (specs, seed.js,
# record-*.cjs, playwright config) discloses API flows + selectors and must not
# be fetchable; also drop the Dockerfile/nginx.conf and loose docs. This runs
# regardless of build context (the deploy uses `git archive`, which ignores
# .dockerignore), so it is the effective guard.
RUN rm -f  /usr/share/nginx/html/Dockerfile /usr/share/nginx/html/nginx.conf \
 && rm -rf /usr/share/nginx/html/e2e \
 && find /usr/share/nginx/html -maxdepth 1 -name '*.md' -delete

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
# NOTE: intentionally no HEALTHCHECK — Traefik (host network mode here) won't
# route to a container marked "unhealthy", and busybox wget to "localhost" is
# unreliable in this image. nginx availability is observed via the route itself.

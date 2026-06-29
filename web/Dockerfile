# WWF front-end — static GrowFlow task-tracker served by nginx,
# with /ai, /agents and /health reverse-proxied to the gateway.
FROM nginx:1.27-alpine

# Static app (index.html + gf/ + assets/)
COPY . /usr/share/nginx/html
# Don't ship the Dockerfile / nginx.conf into the web root
RUN rm -f /usr/share/nginx/html/Dockerfile /usr/share/nginx/html/nginx.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
HEALTHCHECK --interval=30s --timeout=4s --retries=3 \
  CMD wget -qO- http://localhost/ >/dev/null 2>&1 || exit 1

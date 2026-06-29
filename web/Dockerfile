# WWF front-end — the GrowFlow UI served by nginx, with the backend API
# (/auth, /departments, /weeks, /tasks, /ai) reverse-proxied same-origin.
FROM nginx:1.27-alpine

# Static app (index.html + gf/ + assets/)
COPY . /usr/share/nginx/html
# Don't ship the Dockerfile / nginx.conf into the web root
RUN rm -f /usr/share/nginx/html/Dockerfile /usr/share/nginx/html/nginx.conf

COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
# NOTE: intentionally no HEALTHCHECK — Traefik (host network mode here) won't
# route to a container marked "unhealthy", and busybox wget to "localhost" is
# unreliable in this image. nginx availability is observed via the route itself.

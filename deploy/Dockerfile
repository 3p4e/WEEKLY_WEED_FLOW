# Front-end image: nginx serving the static GrowFlow shell.
# Build context expects the repo root (or a folder containing GrowFlow*.html,
# gf/, qc/, lab/, app/, scrap/).
FROM nginx:1.27-alpine

# Copy front-end assets
COPY GrowFlow*.html /usr/share/nginx/html/
COPY gf/  /usr/share/nginx/html/gf/
COPY qc/  /usr/share/nginx/html/qc/
COPY app/ /usr/share/nginx/html/app/
# Optional: lab canvas + ref images if present
COPY lab/ /usr/share/nginx/html/lab/

# nginx config
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
RUN rm -f /etc/nginx/conf.d/default.conf.dpkg-dist

# Healthcheck and run
EXPOSE 80
HEALTHCHECK --interval=30s --timeout=3s CMD wget -qO- http://localhost/healthz || exit 1
CMD ["nginx", "-g", "daemon off;"]

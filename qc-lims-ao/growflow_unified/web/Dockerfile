# web — build the Vite app, serve it with nginx (which also proxies the API, same-origin).
FROM node:22-slim AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci || npm install
COPY . .
# Empty base => the app uses relative URLs; nginx proxies /auth, /planner, etc. to the API.
ARG VITE_PLANNER_API=""
ENV VITE_PLANNER_API=$VITE_PLANNER_API
RUN npm run build

FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

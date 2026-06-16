# Multi-stage: build the Vite SPA, serve it with nginx.
# (Phase 1C swaps this for a Next.js service; the compose service name stays "web".)
FROM node:20-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci
COPY . .
# Optional: bake an absolute API base for split-host deploys. Leave empty to use
# same-origin "/api" (works behind the bundled nginx proxy).
ARG VITE_API_BASE_URL=""
ENV VITE_API_BASE_URL=$VITE_API_BASE_URL
RUN npm run build

FROM nginx:1.27-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80

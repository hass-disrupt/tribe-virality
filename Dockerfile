# Railway / container deployment: build the Vite SPA, serve it with nginx,
# and reverse-proxy /replicate-api/* to api.replicate.com (Replicate has no CORS).
FROM node:20-alpine AS build
WORKDIR /app
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npx vite build

FROM nginx:1.27-alpine
ENV PORT=8080
COPY deploy/nginx.conf.template /etc/nginx/templates/default.conf.template
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8080

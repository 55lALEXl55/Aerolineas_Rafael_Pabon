# ── Stage 1: Build React frontend ───────────────────────────────────────────
FROM node:22-alpine AS builder

WORKDIR /app

# Instalar dependencias primero (cache layer)
COPY package.json package-lock.json* ./
RUN npm ci 2>/dev/null || npm install

# Copiar fuentes y compilar
COPY . .
RUN npm run build

# ── Stage 2: Nginx para servir el build ──────────────────────────────────────
FROM nginx:alpine

# Copiar build
COPY --from=builder /app/dist /usr/share/nginx/html

# nginx.conf se monta via docker-compose (permite reconfigurar sin rebuild)
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]

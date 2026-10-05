# syntax=docker/dockerfile:1
# CampusMate Web（React + Vite）镜像
#
# 两阶段：Node 构建静态产物 -> Nginx 托管，并把 /api、/static 反代到后端。
# 这样交付给别人的是"生产构建 + 静态服务"，而不是 vite dev server。

# ---- Stage 1: 构建 ----
FROM node:22-slim AS build

# 可选：国内网络可通过 --build-arg NPM_REGISTRY=https://registry.npmmirror.com 加速。
ARG NPM_REGISTRY=""
# 可选：宿主机有代理时，用 --build-arg 传入，容器内经 host.docker.internal 访问。
ARG HTTP_PROXY=""
ARG HTTPS_PROXY=""
ARG NO_PROXY=""
ENV HTTP_PROXY=$HTTP_PROXY HTTPS_PROXY=$HTTPS_PROXY NO_PROXY=$NO_PROXY

WORKDIR /app

COPY package.json package-lock.json ./
RUN if [ -n "$NPM_REGISTRY" ]; then npm config set registry "$NPM_REGISTRY"; fi \
    && npm config set fetch-retries 5 \
    && npm config set fetch-retry-mintimeout 20000 \
    && npm config set fetch-retry-maxtimeout 120000 \
    && npm ci

COPY . .
RUN npm run build

# ---- Stage 2: 运行 ----
FROM nginx:1.27-alpine AS runtime

# 站点配置：监听 5174，SPA 回退 + 后端反代（含 SSE 关闭缓冲）。
COPY nginx.conf /etc/nginx/conf.d/default.conf

COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 5174

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=5 \
    CMD wget -q -O /dev/null http://127.0.0.1:5174/ || exit 1

CMD ["nginx", "-g", "daemon off;"]

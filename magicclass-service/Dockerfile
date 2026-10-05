# syntax=docker/dockerfile:1
# 受管 magic class 服务镜像
#
# 该服务**零第三方依赖**：只用 Node 内置模块 + 原生 TS 类型擦除
# （node --experimental-strip-types），因此镜像里没有 node_modules，
# 也不需要 npm/pnpm install。启动即可用。

FROM node:22-slim AS runtime

ENV NODE_ENV=production

WORKDIR /app

# 该服务只依赖 package.json 与 src/。
COPY package.json ./
COPY src ./src

# 服务自有 SQLite 数据库落在挂载卷里。
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 4010

# /internal/health/live 是唯一免鉴权的存活探针。
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=5 \
    CMD node -e "fetch('http://127.0.0.1:4010/internal/health/live').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"

CMD ["node", "--experimental-strip-types", "src/main.ts"]

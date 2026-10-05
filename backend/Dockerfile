# syntax=docker/dockerfile:1
# CampusMate FastAPI 后端镜像
#
# 基础镜像用 python:3.13-slim，与本地 .venv（CPython 3.13.14）保持一致。
# requirements.txt 里的 cryptography / bcrypt / uvloop 等都有 manylinux wheel，
# 一般无需在镜像里装编译工具链。

FROM python:3.13-slim AS runtime

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

WORKDIR /app

# 只装 curl，供 HEALTHCHECK 使用。
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

# 先装依赖，利用 Docker 层缓存：只改业务代码时不会重装依赖。
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# 再拷业务代码（.env / .venv / 本地 SQLite 由 .dockerignore 排除）。
COPY . .

# 发布资源保存在卷外；已存在的数据卷不会自动获得镜像中新加的文件。
# 仅移动 .dockerignore 明确放行的三类资源，绝不打包本地运行期数据。
RUN mkdir -p /opt/campusmate-release-data \
    && mv /app/data/universities.json /app/data/edu_system_candidates.json \
        /app/data/banner_images /opt/campusmate-release-data/

# 运行期数据（SQLite、上传、缓存、知识库）落在挂载卷里。
VOLUME ["/app/data"]

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=5 \
    CMD curl -fsS http://127.0.0.1:8000/api/v1/health || exit 1

ENTRYPOINT ["python", "/app/docker_entrypoint.py"]
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

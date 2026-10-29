# Digests fixados a partir dos manifests oficiais. Atualizar com scanning de imagem.
FROM node:24-bookworm-slim@sha256:c86ecead9e55a5210ac1727de38a4ca840bf03dcaf34dc9749addbf383b1920c AS frontend
WORKDIR /build/frontend
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci --ignore-scripts
COPY frontend/ ./
RUN npm run build

FROM python:3.12-slim-bookworm@sha256:e697c81897302a4c4333bade000d98038fbb21eb064f8ee1fd42d02ebcd9d337
ARG VCS_REF=unknown
LABEL org.opencontainers.image.title="OTM Guard" org.opencontainers.image.revision=$VCS_REF
ENV PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1 PIP_DISABLE_PIP_VERSION_CHECK=1 \
    OTM_BIND=0.0.0.0 PORT=8080 OTM_DATA_DIR=/data
WORKDIR /app
COPY requirements-api.lock ./
RUN pip install --no-cache-dir --require-hashes -r requirements-api.lock \
    && useradd --uid 10001 --create-home app \
    && mkdir /data && chown app:app /data
COPY app.py ./
COPY otm_guard/ ./otm_guard/
COPY platform_api/ ./platform_api/
COPY data/input/ ./data/input/
COPY --from=frontend /build/frontend/dist ./frontend/dist
USER 10001:10001
EXPOSE 8080
HEALTHCHECK --interval=30s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8080/readyz', timeout=3)"
CMD ["python", "-m", "platform_api.api"]

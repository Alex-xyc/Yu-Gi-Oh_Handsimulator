# The web app: builds the front end, then serves it and the API with uvicorn.
#   docker build -t ygo-calc .
#   docker run -p 8000:8000 -v ygo-cache:/cache ygo-calc

# Base images are pinned by digest, so every build uses exactly the images that were tested.
# To take in their security updates, look up the new digests and update both lines:
#   docker buildx imagetools inspect node:22-alpine   (and python:3.12-slim)
FROM node:22-alpine@sha256:0a7108bf6c7bf5de370ffb1a3ed6be93d405b43ff159f681a8d18c0e2bc2e402 AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim@sha256:a6e34c598f2467ed0e9a8d349809fcd8b5c603269512df273a0bb1784edc11b1
WORKDIR /app
COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt
COPY src/ ./src/
COPY --from=web /web/dist ./web/dist
# Runs as an unprivileged user that can only write to the cache. Card images and EDOPro
# databases are cached there (mount a volume to keep them). The fixed uid/gid 10001 lets a
# mounted folder be given to this user.
RUN groupadd --system --gid 10001 app \
    && useradd --system --uid 10001 --gid app --no-create-home --shell /usr/sbin/nologin app \
    && mkdir -p /cache && chown app:app /cache
USER app
ENV YGO_CACHE_DIR=/cache LOCALAPPDATA=/cache HOST=0.0.0.0 PORT=8000 PYTHONDONTWRITEBYTECODE=1
# Behind a hosting platform or reverse proxy, set YGO_PROXY_HOPS to the number of proxies (1
# behind Caddy, see deploy/compose.yaml) so the rate limits are per visitor: the app then takes the address
# the proxy appended to X-Forwarded-For. (Not uvicorn's FORWARDED_ALLOW_IPS=*: that takes the
# leftmost address, which the visitor sends themselves and can set to anything.) Unset, the
# connecting address is used, which is right when the container is reached directly.
EXPOSE 8000
# Healthy once the page is served (python, as the slim image has no curl); the Deploy workflow's
# `docker compose up --wait` waits for this, and rolls back if it never comes
HEALTHCHECK --interval=10s --timeout=5s --start-period=30s --retries=3 \
    CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:' + os.environ['PORT'] + '/', timeout=3)"
CMD ["python", "src/web.py"]

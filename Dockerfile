# The web app: builds the front end, then serves it and the API with uvicorn.
#   docker build -t ygo-calc .
#   docker run -p 8000:8000 -v ygo-cache:/cache ygo-calc

FROM node:22-alpine AS web
WORKDIR /web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
RUN npm run build

FROM python:3.12-slim
WORKDIR /app
COPY requirements-web.txt ./
RUN pip install --no-cache-dir -r requirements-web.txt
COPY src/ ./src/
COPY --from=web /web/dist ./web/dist
# Card images and EDOPro databases are cached here (mount a volume to keep them)
ENV YGO_CACHE_DIR=/cache LOCALAPPDATA=/cache HOST=0.0.0.0 PORT=8000
EXPOSE 8000
CMD ["python", "src/web.py"]

FROM node:22-bookworm-slim AS web-build
WORKDIR /build/web
COPY web/package.json web/package-lock.json ./
RUN npm ci
COPY web/ ./
# Vite staging build leaves VITE_API_BASE_URL unset: API calls use this origin.
RUN npm run build -- --mode staging

FROM node:22-bookworm-slim AS vectorizer-build
WORKDIR /build/vectorizer
COPY external/imagetosvg-mcp/package.json external/imagetosvg-mcp/package-lock.json ./
RUN npm ci
COPY external/imagetosvg-mcp/tsconfig.json ./
COPY external/imagetosvg-mcp/src/ ./src/
RUN npm run build && npm prune --omit=dev --ignore-scripts

FROM python:3.12-slim-bookworm
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    XIAOMANG_WEB_DIST=/app/web-dist \
    XIAOMANG_ENV=staging
WORKDIR /app
RUN apt-get update && apt-get install -y --no-install-recommends libstdc++6 \
    && rm -rf /var/lib/apt/lists/*
COPY xiaomang_pattern_lab/requirements.txt xiaomang_pattern_lab/requirements-web.txt /app/xiaomang_pattern_lab/
RUN pip install --no-cache-dir -r xiaomang_pattern_lab/requirements-web.txt
COPY ppg/ /app/ppg/
COPY xiaomang_pattern_lab/ /app/xiaomang_pattern_lab/
COPY external/imagetosvg_bridge.cjs /app/external/imagetosvg_bridge.cjs
COPY --from=vectorizer-build /build/vectorizer/package.json /app/external/imagetosvg-mcp/package.json
COPY --from=vectorizer-build /build/vectorizer/dist/ /app/external/imagetosvg-mcp/dist/
COPY --from=vectorizer-build /build/vectorizer/node_modules/ /app/external/imagetosvg-mcp/node_modules/
COPY --from=vectorizer-build /usr/local/bin/node /usr/local/bin/node
COPY --from=web-build /build/web/dist/ /app/web-dist/
EXPOSE 10000
CMD ["sh", "-c", "exec uvicorn xiaomang_pattern_lab.web.app:create_app --factory --host 0.0.0.0 --port \"${PORT:-10000}\""]

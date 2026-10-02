# ===== Frontend build =====
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps --no-audit --no-fund \
    && npm install --legacy-peer-deps --no-audit --no-fund --save-dev ajv@8.17.1 ajv-keywords@5.1.0
COPY frontend/ ./

# Render/CRA: build piu leggero e prevedibile.
# - niente sourcemap (riduce RAM durante webpack)
# - niente ESLint durante la build di produzione
# - CI=false evita che semplici warning vengano promossi a errori
ENV REACT_APP_BACKEND_URL="" \
    GENERATE_SOURCEMAP=false \
    DISABLE_ESLINT_PLUGIN=true \
    CI=false
RUN npm run build

# ===== Backend/runtime =====
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_BUILD_DIR=/app/frontend_build \
    UPLOAD_ROOT=/app/data/uploads/installazioni
WORKDIR /app

# Copiando subito il build frontend rendiamo questo stage dipendente dal frontend.
# In questo modo BuildKit non esegue npm build e pip install contemporaneamente.
COPY --from=frontend /app/frontend/build /app/frontend_build

COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/ /app/backend/
RUN mkdir -p /app/data/uploads/installazioni
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]

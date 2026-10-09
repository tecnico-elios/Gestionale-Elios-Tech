# ===== Frontend build =====
FROM node:20-alpine AS frontend
WORKDIR /app/frontend
COPY frontend/package*.json ./
RUN npm install --legacy-peer-deps --no-audit --no-fund \
    && npm install --legacy-peer-deps --no-audit --no-fund --save-dev ajv@8.17.1 ajv-keywords@5.1.0
COPY frontend/ ./
ENV REACT_APP_BACKEND_URL="" \
    GENERATE_SOURCEMAP=false \
    DISABLE_ESLINT_PLUGIN=true
RUN npm run build

# ===== Backend/runtime =====
FROM python:3.12-slim
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FRONTEND_BUILD_DIR=/app/frontend_build \
    UPLOAD_ROOT=/app/data/uploads/installazioni
WORKDIR /app
COPY backend/requirements.txt /app/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/backend/requirements.txt
COPY backend/ /app/backend/
RUN python /app/backend/scripts/apply_r56_backend.py
RUN python /app/backend/scripts/apply_r57_backend.py
RUN python /app/backend/scripts/apply_r58_calendar_roles.py
RUN python /app/backend/scripts/apply_r59_backend.py \
    && python /app/backend/scripts/audit_r59_flows.py
RUN python /app/backend/scripts/apply_r60_backend.py \
    && python /app/backend/scripts/audit_r60_flows.py
RUN python /app/backend/scripts/apply_r61_backend.py \
    && python /app/backend/scripts/audit_r61_flows.py
RUN python /app/backend/scripts/apply_r62_backend.py \
    && python /app/backend/scripts/audit_r62_flows.py \
    && python -m compileall -q /app/backend
COPY --from=frontend /app/frontend/build /app/frontend_build
RUN mkdir -p /app/data/uploads/installazioni
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]
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
RUN node scripts/apply-r54-copy.js \
    && node scripts/apply-r55-unified-header.js \
    && node scripts/apply-r56.js \
    && node scripts/apply-r58-calendar-roles-v2.js \
    && node scripts/apply-r59.js \
    && node scripts/audit-r59-flows.js \
    && node scripts/apply-r61-v2.js \
    && node scripts/audit-r61.js \
    && node scripts/apply-r62.js \
    && node scripts/audit-r62.js \
    && node scripts/apply-r63.js \
    && node scripts/audit-r63.js \
    && node scripts/prepare-r64.js \
    && node scripts/apply-r64.js \
    && node scripts/audit-r64.js \
    && node scripts/apply-r70-free-reports.js \
    && node scripts/audit-r70-free-reports.js \
    && node scripts/apply-r72-report-signatures-pages.js \
    && node scripts/audit-r72-report-signatures-pages.js \
    && node scripts/apply-r76-install-report-free-fields.js \
    && node scripts/audit-r76-install-report-free-fields.js \
    && node scripts/apply-r77-install-report-parity.js \
    && node scripts/audit-r77-install-report-parity.js \
    && npx craco build

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
    && python /app/backend/scripts/audit_r62_flows.py
RUN python /app/backend/scripts/apply_r63_backend.py \
    && python /app/backend/scripts/audit_r63_flows.py
RUN python /app/backend/scripts/prepare_r64_backend.py \
    && python /app/backend/scripts/apply_r64_backend.py \
    && python /app/backend/scripts/audit_r64_flows.py
RUN python /app/backend/scripts/apply_r65_backend.py \
    && python /app/backend/scripts/audit_r65_flows.py
RUN python /app/backend/scripts/apply_r66_backend.py \
    && python /app/backend/scripts/audit_r66_flows.py
RUN python /app/backend/scripts/apply_r67_backend.py \
    && python /app/backend/scripts/audit_r67_flows.py
RUN python /app/backend/scripts/apply_r68_backend.py \
    && python /app/backend/scripts/audit_r68_flows.py
RUN python /app/backend/scripts/apply_r69_backend.py \
    && python /app/backend/scripts/audit_r69_flows.py
RUN python /app/backend/scripts/apply_r70_backend.py \
    && python /app/backend/scripts/audit_r70_flows.py \
    && python -m compileall -q /app/backend
RUN python /app/backend/scripts/apply_r72_backend.py \
    && python /app/backend/scripts/audit_r72_flows.py \
    && python -m compileall -q /app/backend
RUN python /app/backend/scripts/apply_r73_pdf_layout.py \
    && python /app/backend/scripts/audit_r73_pdf_layout.py \
    && python -m compileall -q /app/backend
RUN python /app/backend/scripts/apply_r74_pdf_finish.py \
    && python /app/backend/scripts/audit_r74_pdf_finish.py \
    && python -m compileall -q /app/backend
RUN python /app/backend/scripts/apply_r75_signature_contrast.py \
    && python /app/backend/scripts/audit_r75_signature_contrast.py \
    && python -m compileall -q /app/backend
RUN python /app/backend/scripts/apply_r76_install_report_free_fields.py \
    && python /app/backend/scripts/audit_r76_install_report_free_fields.py \
    && python -m compileall -q /app/backend
RUN python /app/backend/scripts/apply_r77_install_report_parity.py \
    && python /app/backend/scripts/audit_r77_install_report_parity.py \
    && python -m compileall -q /app/backend
RUN python /app/backend/scripts/apply_r78_persistent_files.py \
    && python /app/backend/scripts/audit_r78_persistent_files.py \
    && python -m compileall -q /app/backend
RUN python /app/backend/scripts/apply_r79_remove_lead_api.py \
    && python /app/backend/scripts/audit_r79_remove_lead_api.py \
    && python -m compileall -q /app/backend
COPY --from=frontend /app/frontend/build /app/frontend_build
RUN mkdir -p /app/data/uploads/installazioni
WORKDIR /app/backend
CMD ["sh", "-c", "uvicorn server:app --host 0.0.0.0 --port ${PORT:-8000}"]

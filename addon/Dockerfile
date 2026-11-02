ARG BUILD_FROM

# --- Frontend build -------------------------------------------------------
FROM node:22-alpine AS frontend
WORKDIR /src
COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci
COPY frontend/ ./
RUN npm run build

# --- Add-on image ---------------------------------------------------------
FROM $BUILD_FROM
WORKDIR /app
COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt
COPY backend/autoledger /app/autoledger
COPY --from=frontend /src/dist /app/static
COPY run.sh /run.sh
RUN chmod a+x /run.sh

ENV AUTOLEDGER_DATA_DIR=/data \
    AUTOLEDGER_STATIC_DIR=/app/static \
    PYTHONPATH=/app

CMD [ "/run.sh" ]

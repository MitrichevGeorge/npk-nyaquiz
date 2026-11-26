FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends gcc libpq-dev && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /app/requirements.txt
RUN pip install --no-cache-dir -r /app/requirements.txt

COPY shared /app/shared
COPY backend /app/backend
COPY frontend/templates /app/frontend/templates
COPY alembic.ini /app/alembic.ini
COPY alembic /app/alembic

EXPOSE 8000

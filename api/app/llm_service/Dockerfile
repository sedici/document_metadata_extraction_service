FROM python:3.11-slim

WORKDIR /service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app/ ./app/

ENV SERVICE_PORT=9502
CMD uvicorn app.main:app --host 0.0.0.0 --port $SERVICE_PORT

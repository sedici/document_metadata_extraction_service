FROM python:3.11-slim

WORKDIR /service

COPY requirements.txt .
RUN pip install --no-cache-dir --timeout=120 --retries=5 \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu
RUN pip install --no-cache-dir --timeout=120 --retries=5 -r requirements.txt

COPY app/ ./app/

CMD uvicorn app.main:app --host 0.0.0.0 --port $SERVICE_PORT

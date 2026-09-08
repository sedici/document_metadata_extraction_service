FROM python:3.11-slim

WORKDIR /service

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Download NLTK data needed by pattern_extractors
RUN python -c "import nltk; nltk.download('stopwords', quiet=True); nltk.download('punkt', quiet=True); nltk.download('punkt_tab', quiet=True)"

COPY app/ ./app/

CMD uvicorn app.main:app --host 0.0.0.0 --port $SERVICE_PORT
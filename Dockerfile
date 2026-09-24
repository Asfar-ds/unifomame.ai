# Used by Hugging Face Spaces (and any other Docker host).
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend ./backend
COPY frontend ./frontend

# Hugging Face Spaces serves on 7860.
ENV PORT=7860
EXPOSE 7860

CMD uvicorn backend.main:app --host 0.0.0.0 --port $PORT

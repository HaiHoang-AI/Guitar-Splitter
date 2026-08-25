FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    GUITAR_SPLITTER_HOST=0.0.0.0 \
    GUITAR_SPLITTER_PORT=7860 \
    DEMUCS_DEVICE=cpu \
    TORCH_HOME=/app/model-cache

RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
RUN mkdir -p /app/data /app/model-cache

EXPOSE 7860
CMD ["python", "app.py"]

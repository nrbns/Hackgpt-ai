# SecuraIQ — local / on-prem security AI
FROM python:3.11-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app ./app
COPY static ./static
COPY data/knowledge ./data/knowledge
COPY run.py .

ENV HOST=0.0.0.0
ENV PORT=8080
ENV AUTH_ENABLED=true
ENV DATA_DIR=/data
ENV CHROMA_PERSIST_DIR=/data/chroma

VOLUME ["/data"]
EXPOSE 8080

CMD ["python", "run.py"]

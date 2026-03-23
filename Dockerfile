FROM python:3.11-slim

# System deps — slim image needs these for cryptography/motor
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libssl-dev libffi-dev && \
    rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python deps first (better layer caching)
COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

COPY . .

# Railway sets PORT env automatically
ENV PORT=8080
ENV PYTHONUNBUFFERED=1
ENV PYTHONDONTWRITEBYTECODE=1

CMD ["python", "-m", "FileStream"]

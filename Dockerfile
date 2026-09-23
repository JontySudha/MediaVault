FROM python:3.12-slim

WORKDIR /app

# System packages
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ffmpeg \
        git \
        ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Copy dependency file first for better Docker layer caching
COPY requirements.txt .

RUN pip install --no-cache-dir --upgrade pip \
    && pip install --no-cache-dir -r requirements.txt

# Copy application
COPY app ./app

# Create persistent directories
RUN mkdir -p database gallery

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
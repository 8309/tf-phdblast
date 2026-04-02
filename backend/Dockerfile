FROM python:3.11-slim

WORKDIR /app

# System deps for pymupdf
RUN apt-get update && apt-get install -y --no-install-recommends \
    libmupdf-dev && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy tinyfish SDK (not on PyPI)
COPY tinyfish_sdk/ /usr/local/lib/python3.11/site-packages/tinyfish/
RUN mkdir -p /usr/local/lib/python3.11/site-packages/tinyfish-0.2.4.dist-info && \
    echo "Metadata-Version: 2.1\nName: tinyfish\nVersion: 0.2.4" > \
    /usr/local/lib/python3.11/site-packages/tinyfish-0.2.4.dist-info/METADATA

COPY . .

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

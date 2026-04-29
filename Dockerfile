FROM python:3.11-slim

# System deps for OpenCV and DICOM processing
RUN apt-get update && apt-get install -y --no-install-recommends \
        libgl1 libglib2.0-0 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt ./
# CPU-only torch build to keep image small (~1.5 GB vs ~5 GB for CUDA)
# Override CUDA build by installing CPU wheels first
RUN pip install --no-cache-dir \
        torch==2.5.1+cpu torchvision==0.20.1+cpu \
        --index-url https://download.pytorch.org/whl/cpu \
    && pip install --no-cache-dir -r requirements.txt

COPY . .

# Non-root user
RUN useradd -m -u 1000 heartai && chown -R heartai:heartai /app
USER heartai

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

CMD ["uvicorn", "integration.api.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "1"]

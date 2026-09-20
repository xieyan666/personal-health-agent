# Reproducible FastAPI image for PDF parsing.  The OpenCV runtime libraries are
# required by RapidOCR; keeping them in the image avoids a scanned-PDF failure
# after a container is recreated.
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends libglib2.0-0 libgl1 libxcb1 libgomp1 \
    && rm -rf /var/lib/apt/lists/*

COPY backend/requirements.txt /tmp/requirements.txt
RUN python -m pip install --no-cache-dir --timeout 60 --retries 3 -r /tmp/requirements.txt

COPY backend /app/backend
ENV PYTHONPATH=/app

CMD ["python", "-m", "uvicorn", "backend.app.main:app", "--host", "0.0.0.0", "--port", "8000"]

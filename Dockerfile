FROM python:3.13-slim AS base

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install system deps (kept minimal). If building wheels fails for optional
# extras, consider adding build tools here: build-essential, rustc, cargo.
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential rustc cargo && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY src ./src
COPY main.py ./

ENV PYTHONPATH=/app/src \
    PORT=8000

EXPOSE 8000

CMD ["uvicorn", "gekko.app:app", "--host", "0.0.0.0", "--port", "8000"]


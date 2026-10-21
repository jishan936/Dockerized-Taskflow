# Small official Python image
FROM python:3.12-slim

# No .pyc files, and print logs immediately
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=run.py

WORKDIR /app

# Install dependencies first: Docker caches this layer until requirements.txt changes
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy only what the app needs (see .dockerignore: .env is never copied)
COPY config.py run.py ./
COPY app ./app

# Run as a normal user instead of root
RUN useradd --create-home --uid 1000 appuser
USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/health', timeout=3)" || exit 1

# 1) create tables once (waits/retries for the database), 2) start Gunicorn on 0.0.0.0:5000
CMD ["sh", "-c", "flask init-db && exec gunicorn --bind 0.0.0.0:5000 --workers 2 --access-logfile - run:app"]

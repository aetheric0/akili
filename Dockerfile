# Dockerfile - base image for Akili (FastAPI)
FROM python:3.11-slim

# Keep Python output unbuffered (helpful for logs)
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV POETRY_VIRTUALENVS_CREATE=false


WORKDIR /app

# Install small runtime tools used by healthchecks or libraries (curl)
RUN apt-get update \
	&& apt-get install -y --no-install-recommends curl \
	&& rm -rf /var/lib/apt/lists/*


RUN mkdir -p /tmp && chmod 777 /tmp


# Copy only requirements first to leverage Docker layer cache
COPY requirements.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . /app

# Create a non-root user for production safety
RUN groupadd --system app && useradd --system --gid app --create-home --home-dir /app app \
	&& chown -R app:app /app

# Expose default FastAPI port
EXPOSE 8000

# Run as non-root by default (dev docker-compose will override to root for mount convenience)
USER app

# Default command: production-ready (no --reload)
CMD ["gunicorn", "-k", "uvicorn.workers.UvicornWorker", "main:app", "--bind", "0.0.0.0:${PORT:-8000}", "--workers", "4"]

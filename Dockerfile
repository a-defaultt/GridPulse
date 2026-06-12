FROM python:3.12-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
ENV TZ=UTC

# Set work directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libxml2-dev \
    libxslt-dev \
    gnupg \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create data and logs directories
RUN mkdir -p data logs

# Ensure entrypoint script is executable
RUN chmod +x docker-entrypoint.sh

# Use a non-root user
RUN useradd -m gridpulse && chown -R gridpulse:gridpulse /app
USER gridpulse

# Run the application
ENTRYPOINT ["./docker-entrypoint.sh"]
CMD ["scheduler"]

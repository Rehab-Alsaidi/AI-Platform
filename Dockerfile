# Dockerfile for 51Talk AI Learning Platform (Railway/Production)
FROM python:3.11-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1

# Set work directory
WORKDIR /app

# Install system dependencies (if needed)
RUN apt-get update && apt-get install -y build-essential gcc && rm -rf /var/lib/apt/lists/*

# Copy requirements
COPY requirements.txt ./

# Install Python dependencies
RUN pip install --upgrade pip && pip install -r requirements.txt

# Copy application code
COPY . .

# Expose port (Railway uses $PORT, default 5000)
EXPOSE 5000

# Entrypoint
CMD ["python", "app.py"] 
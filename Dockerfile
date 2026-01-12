FROM python:3.11-slim

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    nodejs \
    npm \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Node dependencies and build CSS
COPY package.json tailwind.config.js ./
RUN npm install

COPY static/css/input.css ./static/css/
RUN npm run build:css

# Copy application code
COPY . .

# Create data directory
RUN mkdir -p /data/audio /data/sources

VOLUME /data
ENV PYTHONUNBUFFERED=1
ENV DATA_DIR=/data

EXPOSE 4040

CMD ["python", "run.py"]

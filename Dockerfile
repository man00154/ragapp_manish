FROM python:3.10-slim

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

# Install system dependencies & Ollama
RUN apt-get update && apt-get install -y \
    build-essential \
    curl \
    git \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama
RUN curl -fsSL https://ollama.com/install.sh | sh

# Set workdir
WORKDIR /app

# Copy requirements and install Python packages
COPY requirements.txt /app/
RUN pip install --no-cache-dir -r requirements.txt

# Copy app files
COPY . /app/

# Environment variables for Streamlit
ENV STREAMLIT_SERVER_HEADLESS=true
ENV STREAMLIT_SERVER_ENABLECORS=false
ENV STREAMLIT_SERVER_ADDRESS=0.0.0.0
ENV PORT=8501

# Expose ports
EXPOSE $PORT
EXPOSE 11434  # Ollama server port

# Pull models so they are ready at runtime
RUN ollama pull llama2 && ollama pull nomic-embed-text

# Start Ollama server in background, wait, then run Streamlit
CMD ollama serve & \
    sleep 5 && \
    streamlit run app.py --server.port=$PORT --server.address=0.0.0.0

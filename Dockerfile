# Use an official Python runtime as a parent image
FROM python:3.9-slim-buster

# Set the working directory in the container
WORKDIR /app

# Copy the current directory contents into the container at /app
COPY . /app

# Install any needed packages specified in requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port Streamlit runs on
EXPOSE 8501

# Command to run the Streamlit application
# The --server.port $PORT ensures Streamlit listens on the port provided by Render
# The --server.enableCORS false and --server.enableXsrfProtection false are often needed for deployment environments
CMD ["streamlit", "run", "app.py", "--server.port", "8501", "--server.address", "0.0.0.0", "--server.enableCORS", "false", "--server.enableXsrfProtection", "false"]
FROM python:3.11-slim

# Install build dependencies
RUN apt-get update && apt-get install -y build-essential libsqlite3-dev wget

# Upgrade SQLite
RUN wget https://www.sqlite.org/2024/sqlite-autoconf-3450000.tar.gz \
    && tar xvfz sqlite-autoconf-3450000.tar.gz \
    && cd sqlite-autoconf-3450000 \
    && ./configure --prefix=/usr/local \
    && make && make install

# Make Python use the new SQLite
RUN apt-get install -y python3-dev
RUN python3 -m pip install --upgrade pip

WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt

COPY . .
CMD ["streamlit", "run", "app.py", "--server.port=10000", "--server.address=0.0.0.0"]

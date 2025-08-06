# Use the official Ollama image
FROM ollama/ollama:latest

# Expose the default Ollama port
EXPOSE 11434

# Copy the models list
COPY models.txt /models.txt

# Run a script to pull the models on container startup
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# The entrypoint script will pull models and then start the server
ENTRYPOINT ["/entrypoint.sh"]

CMD ["ollama", "serve"]

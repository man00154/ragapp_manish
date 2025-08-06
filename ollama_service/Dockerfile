# Use the official Ollama image
FROM ollama/ollama:latest

# Expose the default Ollama port
EXPOSE 11434

# Command to run the Ollama server
# This will be overridden by Render's service command, but it's good practice
CMD ["ollama", "serve"]

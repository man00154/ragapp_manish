#!/bin/bash
set -e

# Read models from the models.txt file and pull them
if [ -f /models.txt ]; then
    echo "Pulling models from models.txt..."
    while read -r model; do
        if [ ! -z "$model" ]; then
            echo "Pulling model: $model"
            ollama pull "$model"
        fi
    done < /models.txt
    echo "Model pulling complete."
else
    echo "models.txt not found. Skipping model pre-loading."
fi

# Start the Ollama serve command
exec "$@"

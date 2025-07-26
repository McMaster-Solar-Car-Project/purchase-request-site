#!/bin/bash

# Quick script to run the Docker container with Supabase
# Usage: ./run-docker.sh

echo "🚀 Starting Purchase Request Site with Supabase..."

# Stop and remove existing container if it exists
if docker ps -a --format '{{.Names}}' | grep -q "^purchase-request-site$"; then
    echo "🛑 Stopping existing container..."
    docker stop purchase-request-site > /dev/null 2>&1
    docker rm purchase-request-site > /dev/null 2>&1
fi

# Run the container (DATABASE_URL is baked in from .env)
echo "🐳 Starting new container..."
docker run -d --name purchase-request-site --network host purchase-request-site

if [ $? -eq 0 ]; then
    echo "✅ Container started successfully!"
    echo ""
    echo "🌐 Your app is running at: http://localhost:80"
    echo "🔍 To view logs: docker logs -f purchase-request-site"
    echo "🛑 To stop: docker stop purchase-request-site"
    echo ""
    echo "⏳ Waiting for startup (checking logs in 3 seconds)..."
    sleep 3
    docker logs --tail=10 purchase-request-site
else
    echo "❌ Failed to start container!"
    exit 1
fi 
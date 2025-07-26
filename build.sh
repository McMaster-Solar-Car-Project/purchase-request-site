#!/bin/bash

# Build script that reads .env file and passes variables as build arguments
# Usage: ./build.sh

echo "🔨 Building Docker image with environment variables from .env file..."

# Check if .env file exists
if [ ! -f .env ]; then
    echo "❌ Error: .env file not found!"
    echo "Please create a .env file with your environment variables."
    exit 1
fi

# Read .env file and build --build-arg parameters
BUILD_ARGS=()
while IFS='=' read -r key value || [ -n "$key" ]; do
    # Skip empty lines and comments
    if [[ -z "$key" || "$key" =~ ^[[:space:]]*# ]]; then
        continue
    fi
    
    # Remove any leading/trailing whitespace
    key=$(echo "$key" | xargs)
    value=$(echo "$value" | xargs)
    
    # Remove quotes from value if present
    value="${value%\"}"
    value="${value#\"}"
    
    # Add to build arguments array
    BUILD_ARGS+=("--build-arg" "$key=$value")
done < .env

echo "🚀 Building optimized image with multi-stage build..."

# Build the Docker image
docker build "${BUILD_ARGS[@]}" -t purchase-request-site .

if [ $? -eq 0 ]; then
    echo "✅ Optimized Docker image built successfully!"
    
    # Show image size
    echo ""
    echo "📊 Image size:"
    docker images purchase-request-site --format "table {{.Repository}}\t{{.Tag}}\t{{.Size}}"
    
    echo ""
    echo "🏃 To run the container:"
    echo "   docker run -d --name purchase-request-site -p 8000:80 purchase-request-site"
else
    echo "❌ Docker build failed!"
    exit 1
fi 
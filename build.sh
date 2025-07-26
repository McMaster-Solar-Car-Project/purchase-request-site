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
    echo "🏃 To run the container with Supabase:"
    echo "   docker run -d --name purchase-request-site --network host purchase-request-site"
    echo ""
    echo "📝 Note: Using --network host to allow Supabase connection"
    echo "🌐 Access your app at: http://localhost:80"
    echo "💾 Database URL is baked into the container from .env file"
    echo ""
    echo "⚡ Quick start: ./run-docker.sh"
    echo ""
    echo "🔍 For code quality: ./format.sh"
    echo "🚀 CI/CD: GitHub Actions will run on push to main/master"
else
    echo "❌ Docker build failed!"
    exit 1
fi 
#!/bin/bash

# SMAP Speech-to-Text API - Build and Push Script
# Usage: ./build-speech-to-text.sh [build-push|login|help]

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

# Configuration
REGISTRY="${REGISTRY:-registry.tantai.dev}"
PROJECT="smap"
SERVICE="smap-speech-to-text"
DOCKERFILE="cmd/api/Dockerfile"
PLATFORM="linux/amd64"

# Helper functions
info() { echo -e "${BLUE}[INFO]${NC} $1"; }
success() { echo -e "${GREEN}[SUCCESS]${NC} $1"; }
warning() { echo -e "${YELLOW}[WARNING]${NC} $1"; }
error() { echo -e "${RED}[ERROR]${NC} $1"; }

# Generate image tag with timestamp
generate_tag() {
    date +"%y%m%d-%H%M%S"
}

# Get full image name
get_image_name() {
    local tag="${1:-$(generate_tag)}"
    echo "${REGISTRY}/${PROJECT}/${SERVICE}:${tag}"
}

# Login to registry
login() {
    info "Logging into registry: $REGISTRY"
    
    # Use env vars if available
    if [ -n "$HARBOR_USERNAME" ] && [ -n "$HARBOR_PASSWORD" ]; then
        echo "$HARBOR_PASSWORD" | docker login "$REGISTRY" -u "$HARBOR_USERNAME" --password-stdin
    else
        # Prompt for credentials
        read -p "Username: " username
        read -sp "Password: " password
        echo ""
        echo "$password" | docker login "$REGISTRY" -u "$username" --password-stdin
    fi
    
    if [ $? -eq 0 ]; then
        success "Logged in successfully"
    else
        error "Login failed"
        exit 1
    fi
}

# Check prerequisites
check_prerequisites() {
    # Check Docker
    if ! command -v docker &> /dev/null; then
        error "Docker is not installed"
        exit 1
    fi
    
    # Check buildx
    if ! docker buildx version &> /dev/null; then
        error "Docker buildx is not available"
        exit 1
    fi
    
    # Check Dockerfile
    if [ ! -f "$DOCKERFILE" ]; then
        error "Dockerfile not found: $DOCKERFILE"
        exit 1
    fi
}

# Build and push image
build_and_push() {
    check_prerequisites
    
    # Check if logged in
    if ! docker info 2>/dev/null | grep -q "Username:"; then
        warning "Not logged in, attempting to login..."
        login
    fi
    
    local tag=$(generate_tag)
    local image_name=$(get_image_name "$tag")
    
    info "Registry: $REGISTRY"
    info "Building image: $image_name"
    info "Platform: $PLATFORM"
    info "Dockerfile: $DOCKERFILE"
    
    # Build and push with attestation disabled for registry compatibility
    docker buildx build \
        --platform "$PLATFORM" \
        --provenance=false \
        --sbom=false \
        --tag "$image_name" \
        --tag "$(get_image_name latest)" \
        --file "$DOCKERFILE" \
        --push \
        .
    
    if [ $? -eq 0 ]; then
        success "Image built and pushed successfully!"
        info "Image: $image_name"
        info "Latest: $(get_image_name latest)"
    else
        error "Build and push failed"
        exit 1
    fi
}

# Show help
show_help() {
    cat << EOF
${GREEN}SMAP Speech-to-Text API - Build and Push Script${NC}

Usage: $0 [command]

Commands:
    build-push    Build and push Docker image (default)
    login         Login to registry
    help          Show this help

Examples:
    $0                    # Build and push
    $0 build-push         # Build and push
    $0 login              # Login to registry

Configuration:
    Registry:   $REGISTRY
    Project:    $PROJECT
    Service:    $SERVICE
    Platform:   $PLATFORM
    Dockerfile: $DOCKERFILE

Image Format:
    ${REGISTRY}/${PROJECT}/${SERVICE}:TIMESTAMP
    ${REGISTRY}/${PROJECT}/${SERVICE}:latest

Environment Variables:
    REGISTRY          Docker registry URL (default: registry.tantai.dev)
    HARBOR_USERNAME   Registry username (optional)
    HARBOR_PASSWORD   Registry password (optional)
    PLATFORM          Build platform (default: linux/amd64)

Note:
    This builds the Speech-to-Text API service.
    The server listens on port 8000 and provides transcription endpoints.

EOF
}

# Main
case "${1:-build-push}" in
    build-push)
        build_and_push
        ;;
    login)
        login
        ;;
    help|--help|-h)
        show_help
        ;;
    *)
        error "Unknown command: $1"
        echo ""
        show_help
        exit 1
        ;;
esac

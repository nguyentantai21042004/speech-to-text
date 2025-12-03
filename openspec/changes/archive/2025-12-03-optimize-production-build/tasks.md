# Implementation Tasks: Optimize Production Build

## Phase 1: Container Optimization

### 1.1 Optimize Build Context
- [x] Update `.dockerignore` to exclude `document/` directory and others
- [x] Update `.dockerignore` to exclude any other non-production files found
- [x] Verify build context size reduction

### 1.2 Optimize Dockerfile
- [x] Review `cmd/api/Dockerfile` for potential cleanups
- [x] Ensure `COPY`, `MOUNT` instructions are as specific as possible
- [x] Verify multi-stage build efficiency

## Phase 2: Deployment Optimization

### 2.1 Update Resource Limits
- [x] Update `k8s/deployment.yaml` CPU requests to `1000m`
- [x] Update `k8s/deployment.yaml` CPU limits to `2000m`
- [x] Update comments in `deployment.yaml` to explain the "1 core" strategy
- [x] Verify Memory settings align with recommendations (1Gi request, 2Gi limit)

### 2.2 Verify HPA Configuration
- [x] Confirm HPA target utilization (70%) is appropriate for the new limits
- [x] Ensure `minReplicas` and `maxReplicas` are set correctly

## Phase 3: Validation

### 3.1 Build Verification
- [x] Run `docker build -f cmd/api/Dockerfile -t stt-api:optimized .`
- [x] Verify image size and contents

### 3.2 Manifest Verification
- [x] Run `kubectl apply -f k8s/deployment.yaml --dry-run=client`
- [x] Review generated manifest for correctness

## Phase 4: Additional Optimizations

### 4.1 Docker Compose Alignment
- [x] Update `docker-compose.yml` resource limits to match K8s (1 core strategy)
- [x] Remove hardcoded credentials from `docker-compose.dev.yml`
- [x] Add production docker-compose with optimized settings

### 4.2 Security Hardening
- [x] Add non-root user to Dockerfile
- [x] Verify all sensitive values use environment variables

### 4.3 Push to Local Registry
- [x] Push optimized image to local registry
- [x] Verify image is accessible from k3s

## Phase 5: Code-Level Optimizations

### 5.1 Security Fixes
- [x] Remove hardcoded credentials from `core/config.py`
- [x] Remove hardcoded IPs/credentials from all files (scripts, docker-compose, README, .env.example)

### 5.2 Performance Optimizations
- [x] Add dedicated ThreadPoolExecutor for transcription tasks
- [x] Add connection pooling for HTTP audio downloader


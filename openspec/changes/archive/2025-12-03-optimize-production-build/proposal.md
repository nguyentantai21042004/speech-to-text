# Optimize Production Build and Deployment

## Why

Based on the performance analysis in `document/performance.md` and `document/scaling-guide.md`:

1.  **Resource Mismatch**: The current Kubernetes deployment requests **2.5 CPU cores** per pod, but the performance report indicates **poor multi-core scaling** and recommends **1-2 cores** for optimal efficiency. Using 2.5 cores wastes resources without significant performance gain.
2.  **Build Context Bloat**: The `.dockerignore` file excludes `docs/` but misses the `document/` directory, which contains large benchmark results and documentation not needed in the production image.
3.  **Production Readiness**: The user wants a stable, fast, and optimized build flow for production deployment.

## What Changes

### 1. Container Optimization
- **Update `.dockerignore`**: Explicitly exclude the `document/` directory to reduce build context size.
- **Review Dockerfile**: Ensure only necessary files are copied and layers are optimized.

### 2. Production Deployment Configuration
- **Optimize Resources**: Reduce CPU requests to **1 core (1000m)** and limits to **2 cores (2000m)** as per performance recommendations.
- **Update HPA**: Confirm HPA settings align with the new resource limits (target 70% utilization).
- **Documentation**: Update comments in manifests to reflect the new sizing rationale.

## User Review Required

> [!IMPORTANT]
> **CPU Request Reduction**: This change reduces CPU requests from 2.5 cores to 1 core per pod. This is based on the finding that the service does not scale well with more cores ("ít cores mạnh"). This will allow packing more pods per node and scaling horizontally, which is the recommended strategy.

## Proposed Changes

### Container Optimization

#### [MODIFY] [.dockerignore](file:///Users/tantai/Workspaces/tools/speech-to-text/.dockerignore)
- Add `document/` to exclusions.
- Verify other exclusions.

#### [MODIFY] [Dockerfile](file:///Users/tantai/Workspaces/tools/speech-to-text/cmd/api/Dockerfile)
- Review for any unnecessary copy operations (current state looks mostly good, but will double-check).

### Production Deployment

#### [MODIFY] [k8s/deployment.yaml](file:///Users/tantai/Workspaces/tools/speech-to-text/k8s/deployment.yaml)
- Update `resources.requests.cpu` to `1000m`.
- Update `resources.limits.cpu` to `2000m`.
- Update comments to reference `document/performance.md`.

## Verification Plan

### Automated Tests
- **Build Verification**: Run `docker build` to ensure the image builds successfully and is smaller/cleaner.
- **Manifest Validation**: Use `kubectl dry-run` or a linter to verify K8s manifests.

### Manual Verification
- **Context Check**: Verify `document/` is not present in the build context.
- **Resource Check**: Deploy to a test cluster (if available) and verify pods start with new limits.

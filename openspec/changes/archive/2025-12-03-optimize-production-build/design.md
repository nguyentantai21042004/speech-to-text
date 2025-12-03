# Design: Production Build and Deployment Optimization

## Overview

This change aligns the production build and deployment configuration with the performance insights gathered in `document/performance.md`. It focuses on efficiency, stability, and following the "horizontal scaling" strategy.

## Problem Statement

1.  **Inefficient Build Context**: The `document/` folder contains large files (benchmark results, images) that are not needed for the production build but are currently sent to the Docker daemon.
2.  **Over-provisioned CPU**: The current deployment requests 2.5 cores per pod. Research shows the service scales poorly beyond 2 cores. This wastes cluster resources and limits the number of pods that can be scheduled (horizontal scaling).

## Technical Approach

### 1. Container Optimization

**Strategy**: Exclude everything by default or explicitly exclude heavy directories.
**Action**: Add `document/` to `.dockerignore`.

### 2. Resource Sizing

**Insight**: "For single request speed: Use 1-2 cores per pod... For throughput: Scale horizontally".
**Decision**:
- **Request**: 1 Core (`1000m`). This guarantees dedicated capacity for the main thread.
- **Limit**: 2 Cores (`2000m`). This allows bursting for short periods or background tasks (like GC or download) without being throttled immediately.
- **Memory**: Keep at 1Gi/2Gi as this fits the Base/Small models well.

**Impact**:
- **Density**: We can fit 2.5x more pods on the same node compared to the 2.5 core request.
- **Throughput**: Since 2 pods with 1 core each > 1 pod with 2 cores (due to contention), overall system throughput increases.

## Trade-offs

| Decision | Trade-off | Rationale |
|----------|-----------|-----------|
| **Reduce CPU Request** | Single request *might* be slightly slower if node is busy | Horizontal scaling provides better total throughput and reliability. |
| **Strict .dockerignore** | Developers must remember to add new required folders | Prevents accidental inclusion of secrets or large files. |

## Success Criteria

1.  Docker build context does not include `document/`.
2.  K8s deployment requests 1 CPU core.
3.  K8s deployment limits 2 CPU cores.

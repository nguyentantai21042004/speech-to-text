# CPU Scaling Report

## System Information

| Property | Value |
|----------|-------|
| Timestamp | 2025-12-03T05:09:57.718869+00:00 |
| Architecture | x86_64 |
| CPU Model | VirtualApple @ 2.50GHz |
| Model Size | base |
| Audio Duration | 29.9s |

## Scaling Results

| Cores | Latency (ms) | RPS | Speedup | Efficiency |
|-------|--------------|-----|---------|------------|
| 1 | 10095.84 | 0.0991 | 1.00x | 100% |
| 2 | 10487.42 | 0.0954 | 0.96x | 48% |
| 4 | 11666.77 | 0.0857 | 0.87x | 22% |

## Analysis

- **Scaling Type**: poor
- **Optimal Cores**: 1
- **Diminishing Returns Point**: 2

## Recommendation

Service shows poor multi-core scaling. Recommendation: Use 'ít cores mạnh' - fewer but faster cores are more efficient.

## Answer: "Nhiều cores yếu hay ít cores mạnh?"

**Answer: Ít cores mạnh** - The service doesn't scale well with multiple cores.

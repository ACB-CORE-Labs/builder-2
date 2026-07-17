# Transition Runbook: vLLM Backend Promotion

## 1. Executive Summary
This runbook provides the framework for promoting the **vLLM Backend** serving infrastructure. This transition aims to replace our legacy LLM inference engine with vLLM to capitalize on PagedAttention, achieving higher throughput, lower time-to-first-token (TTFT), and better GPU memory utilization.

## 2. Readiness Records
### 2.1 Capability Gap Addressed
- Blocked capability: High-throughput vLLM backend integration.
- Status: **Pending Approval**
- Tracker Reference: `BUILDER-II-TRK-B2`

### 2.2 Validation Checklist
- [ ] **Model Compatibility**: Verified that all primary instruction-tuned models (e.g., Llama-3, Mistral) are successfully served by vLLM without degradation in response quality.
- [ ] **Throughput Benchmarks**: Confirmed a minimum of 2.5x increase in requests per second (RPS) compared to the legacy backend during peak load simulations.
- [ ] **Memory Profiling**: Verified PagedAttention memory allocation prevents out-of-memory (OOM) errors during maximum concurrent batch sizes.
- [ ] **Streaming Support**: Confirmed Server-Sent Events (SSE) streaming matches expected token emission rates.
- [ ] **Observability**: Metrics (KV cache usage, request queue length, GPU utilization) are successfully exporting to Prometheus.

## 3. Promotion Steps
1. **GPU Node Provisioning**: Scale up the production Kubernetes cluster with the required A100/H100 node pools.
2. **Model Weight Caching**: Pre-fetch and cache model weights onto the local NVMe storage of the GPU nodes to minimize cold start times.
3. **Deployment**: Deploy the vLLM Helm chart to the `production-inference` namespace.
4. **Traffic Shadowing**: Shadow 10% of production traffic to the new vLLM service and compare outputs and latencies offline.
5. **DNS/Ingress Cut-over**: Update the API gateway routing to point the `inference-svc` to the vLLM backend.

## 4. Rollback Story
If inference quality degrades, OOMs occur, or TTFT spikes above SLA:
1. **Immediate Traffic Reversal**: Revert the Ingress/Gateway routing rule to point back to the legacy inference service.
2. **Drain vLLM Nodes**: Cordon the vLLM Kubernetes deployments to prevent new requests, allowing in-flight requests to complete or time out.
3. **Log Collection**: Export GPU kernel logs, vLLM application logs, and Prometheus metrics for root cause analysis.
4. **Scale Down**: Scale the vLLM deployment to 0 to save GPU compute costs while the issue is investigated.

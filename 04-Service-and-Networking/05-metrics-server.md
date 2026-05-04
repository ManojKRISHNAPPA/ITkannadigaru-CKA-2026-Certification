# Kubernetes Metrics Server — Complete Guide

> Metrics Server is the pipeline that feeds real-time CPU and memory data to kubectl top, HPA, and VPA.

---

## Table of Contents

1. [What is Metrics Server?](#1-what-is-metrics-server)
2. [Why Metrics Server?](#2-why-metrics-server)
3. [Architecture — How it Works](#3-architecture--how-it-works)
4. [Installing Metrics Server](#4-installing-metrics-server)
   - [4.1 On Minikube](#41-on-minikube)
   - [4.2 On kubeadm / Bare Metal](#42-on-kubeadm--bare-metal)
   - [4.3 On Kind](#43-on-kind)
   - [4.4 On EKS (AWS)](#44-on-eks-aws)
5. [Verifying the Installation](#5-verifying-the-installation)
6. [Using Metrics — kubectl top](#6-using-metrics--kubectl-top)
7. [Metrics Server vs Full Monitoring](#7-metrics-server-vs-full-monitoring)
8. [Troubleshooting](#8-troubleshooting)
9. [Practical Demo](#9-practical-demo)
10. [Common Interview Questions](#10-common-interview-questions)
11. [Exam Practice Questions](#11-exam-practice-questions)

---

## 1. What is Metrics Server?

**Metrics Server** is a cluster-wide aggregator of **resource usage data** (CPU and memory). It:

- Collects metrics from each Node's **kubelet** (via the Summary API)
- Stores them **in memory** (not persisted to disk)
- Exposes them via the **Kubernetes Metrics API** (`metrics.k8s.io`)

```
  ┌──────────────────────────────────────────────────────────────┐
  │                     Kubernetes Cluster                       │
  │                                                              │
  │  ┌──────────────┐   ┌──────────────┐   ┌──────────────┐    │
  │  │    Node 1    │   │    Node 2    │   │    Node 3    │    │
  │  │  kubelet     │   │  kubelet     │   │  kubelet     │    │
  │  │  cAdvisor    │   │  cAdvisor    │   │  cAdvisor    │    │
  │  └──────┬───────┘   └──────┬───────┘   └──────┬───────┘    │
  │         │                  │                   │            │
  │         └──────────────────┼───────────────────┘            │
  │                            │ scrapes every 15s              │
  │                            ▼                               │
  │                  ┌─────────────────────┐                   │
  │                  │   Metrics Server    │                   │
  │                  │  (in-memory store)  │                   │
  │                  └─────────┬───────────┘                   │
  │                            │ exposes                       │
  │                            ▼                               │
  │                  metrics.k8s.io API                        │
  │                            │                               │
  │          ┌─────────────────┼─────────────────┐            │
  │          ▼                 ▼                 ▼            │
  │   kubectl top          HPA controller    VPA controller   │
  └──────────────────────────────────────────────────────────────┘
```

---

## 2. Why Metrics Server?

| Without Metrics Server | With Metrics Server |
|------------------------|---------------------|
| `kubectl top` → `error: Metrics API not available` | `kubectl top pods` shows CPU/memory live |
| HPA cannot scale (no metrics source) | HPA scales based on real CPU usage |
| VPA cannot right-size Pods | VPA recommends correct resource sizes |
| No visibility into per-Pod resource usage | Instant visibility per pod and node |

> **Important**: Metrics Server is NOT a full monitoring system. It keeps only the **latest** metrics (no history). For historical data, use **Prometheus + Grafana**.

---

## 3. Architecture — How it Works

```
  Collection Pipeline:

  Container (running)
       │
  cAdvisor (built into kubelet)
  - Measures CPU, memory, filesystem, network per container
       │
  kubelet Summary API
  - Aggregates per-pod stats
  - Endpoint: https://<node-ip>:10250/stats/summary
       │
  Metrics Server
  - Calls kubelet on every node every 15 seconds
  - Aggregates and stores latest snapshot in memory
       │
  Kubernetes Metrics API (metrics.k8s.io)
  - Registered as an API Extension (APIService object)
  - Consumers: kubectl, HPA, VPA
```

### API Paths

```bash
# Node metrics
GET /apis/metrics.k8s.io/v1beta1/nodes
GET /apis/metrics.k8s.io/v1beta1/nodes/<node-name>

# Pod metrics
GET /apis/metrics.k8s.io/v1beta1/namespaces/<ns>/pods
GET /apis/metrics.k8s.io/v1beta1/namespaces/<ns>/pods/<pod-name>
```

```bash
# You can call these directly
kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes | python3 -m json.tool
kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/default/pods | python3 -m json.tool
```

---

## 4. Installing Metrics Server

### 4.1 On Minikube

```bash
# Minikube has a built-in addon
minikube addons enable metrics-server

# Verify
minikube addons list | grep metrics-server
# metrics-server: enabled

# Wait for it to be ready
kubectl rollout status deployment metrics-server -n kube-system

# Test immediately
kubectl top nodes
kubectl top pods -A
```

---

### 4.2 On kubeadm / Bare Metal

The default manifest does not work on most kubeadm clusters because kubelet uses **self-signed TLS certificates** that Metrics Server rejects. You need to add `--kubelet-insecure-tls` flag.

```bash
# Step 1: Download the official manifest
wget https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml \
  -O metrics-server.yaml

# Step 2: Edit the Deployment to add --kubelet-insecure-tls flag
# Find the args section and add the flag:
```

```yaml
# Edit in metrics-server.yaml — find the Deployment and modify args:
spec:
  containers:
  - name: metrics-server
    image: registry.k8s.io/metrics-server/metrics-server:v0.7.2
    args:
    - --cert-dir=/tmp
    - --secure-port=10250
    - --kubelet-preferred-address-types=InternalIP,ExternalIP,Hostname
    - --kubelet-use-node-status-port
    - --metric-resolution=15s
    - --kubelet-insecure-tls          # ← ADD THIS LINE
```

```bash
# Or use sed to patch it in-place
sed -i '/--metric-resolution/a\        - --kubelet-insecure-tls' metrics-server.yaml

# Step 3: Apply
kubectl apply -f metrics-server.yaml

# Step 4: Watch it come up
kubectl rollout status deployment metrics-server -n kube-system

# Step 5: Verify
kubectl top nodes
```

**One-liner patch and apply:**

```bash
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Patch the deployment to add --kubelet-insecure-tls
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

---

### 4.3 On Kind

Kind also needs the `--kubelet-insecure-tls` flag:

```bash
# Apply with the patch
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# Wait for rollout
kubectl rollout status deployment/metrics-server -n kube-system --timeout=120s

kubectl top nodes
```

---

### 4.4 On EKS (AWS)

EKS has proper TLS configured, so the standard manifest works without `--kubelet-insecure-tls`.

```bash
# Method 1: kubectl apply (simplest)
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# Method 2: via Helm (more configurable)
helm repo add metrics-server https://kubernetes-sigs.github.io/metrics-server/
helm repo update

helm upgrade --install metrics-server metrics-server/metrics-server \
  --namespace kube-system \
  --set defaultArgs="{--cert-dir=/tmp,--kubelet-preferred-address-types=InternalIP,--kubelet-use-node-status-port,--metric-resolution=15s}"

# Wait for ready
kubectl rollout status deployment metrics-server -n kube-system

# Verify
kubectl top nodes
```

---

## 5. Verifying the Installation

```bash
# Check the pod is Running
kubectl get pods -n kube-system | grep metrics-server

# Check the APIService is registered and Available
kubectl get apiservice v1beta1.metrics.k8s.io

# Expected output:
# NAME                     SERVICE                      AVAILABLE   AGE
# v1beta1.metrics.k8s.io   kube-system/metrics-server   True        5m

# If AVAILABLE=False, check logs:
kubectl logs -n kube-system -l k8s-app=metrics-server

# Test the API directly
kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes

# Quick smoke test
kubectl top nodes
kubectl top pods -A
```

### Healthy Output

```
NAME          CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
master-node   152m         7%     1234Mi          32%
worker-1      89m          4%     876Mi           22%
worker-2      103m         5%     912Mi           23%
```

---

## 6. Using Metrics — kubectl top

```bash
# Node resource usage
kubectl top nodes

# Node usage sorted by CPU
kubectl top nodes --sort-by=cpu

# Node usage sorted by memory
kubectl top nodes --sort-by=memory

# Pod resource usage (default namespace)
kubectl top pods

# Pod usage in specific namespace
kubectl top pods -n kube-system

# Pod usage across ALL namespaces
kubectl top pods -A

# Pod usage sorted by CPU
kubectl top pods --sort-by=cpu

# Pod usage sorted by memory
kubectl top pods --sort-by=memory

# Show container-level metrics within pods
kubectl top pods --containers

# Specific pod
kubectl top pod nginx-pod
```

### Sample Output

```
# kubectl top pods -A --containers

NAMESPACE     POD                          NAME              CPU(cores)  MEMORY(bytes)
default       web-deploy-xxx               nginx             1m          3Mi
kube-system   coredns-xxx                  coredns           4m          17Mi
kube-system   metrics-server-xxx           metrics-server    6m          21Mi
```

---

## 7. Metrics Server vs Full Monitoring

| Feature | Metrics Server | Prometheus + Grafana |
|---------|---------------|----------------------|
| **Data retention** | Current values only (in-memory) | Days/weeks/months |
| **Historical queries** | ✗ No | ✓ Yes (PromQL) |
| **Custom metrics** | ✗ No | ✓ Yes |
| **Dashboards** | ✗ No | ✓ Yes (Grafana) |
| **Alerts** | ✗ No | ✓ Yes (Alertmanager) |
| **Required for HPA/VPA** | ✓ Yes | ✗ Not directly |
| **Resource footprint** | Tiny (~20Mi RAM) | Large (hundreds of MB) |
| **Use case** | Real-time scaling, kubectl top | Full observability platform |

> **Use both**: Metrics Server for HPA/VPA/kubectl top, Prometheus for dashboards and alerts.

---

## 8. Troubleshooting

### Problem: `kubectl top` returns `error: Metrics API not available`

```bash
# 1. Check if metrics-server pod exists
kubectl get pods -n kube-system | grep metrics-server

# 2. Check APIService
kubectl get apiservice v1beta1.metrics.k8s.io
# Look for: AVAILABLE = False

# 3. Check pod logs
kubectl logs -n kube-system deployment/metrics-server

# Common error: "x509: cannot validate certificate for <IP>"
# Fix: add --kubelet-insecure-tls to args
```

### Problem: Metrics Server pod CrashLoopBackOff

```bash
kubectl describe pod -n kube-system -l k8s-app=metrics-server

# Check events at the bottom of describe output
# Common causes:
# - OOMKilled: increase memory limits
# - Node affinity: ensure node is schedulable
# - Network: metrics-server can't reach kubelet on port 10250
```

### Problem: Nodes show metrics but Pods don't

```bash
# Metrics take ~60 seconds to propagate after pod startup
# Wait and retry

# Check if pod has been running long enough
kubectl get pods --sort-by=.status.startTime

# Verify kubelet port 10250 is reachable
kubectl get --raw /api/v1/nodes/<node-name>/proxy/stats/summary
```

---

## 9. Practical Demo

```bash
# === SETUP ===
# Enable metrics-server (minikube)
minikube addons enable metrics-server

# Or for kubeadm:
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# Wait for it
kubectl rollout status deployment/metrics-server -n kube-system

# === VERIFY ===
kubectl get apiservice v1beta1.metrics.k8s.io
kubectl top nodes

# === DEPLOY A WORKLOAD ===
kubectl create deployment stress-test --image=nginx --replicas=3
kubectl rollout status deployment/stress-test

# Wait 60 seconds for initial metrics
sleep 60

# Check pod metrics
kubectl top pods -l app=stress-test

# === GENERATE LOAD ===
kubectl run load-gen --image=busybox --rm -it --restart=Never \
  -- sh -c "while true; do wget -q -O- http://stress-test 2>/dev/null; done" &

# Watch metrics update every 15 seconds
watch kubectl top pods

# === CONTAINER LEVEL METRICS ===
kubectl top pods --containers

# === RAW API ===
kubectl get --raw /apis/metrics.k8s.io/v1beta1/namespaces/default/pods | \
  python3 -c "import sys,json; data=json.load(sys.stdin); [print(i['metadata']['name'], i['containers'][0]['usage']) for i in data['items']]"

# === CLEANUP ===
kubectl delete deployment stress-test
```

---

## 10. Common Interview Questions

**Q: What is Metrics Server and what does it provide?**
> Metrics Server is an in-cluster component that collects real-time CPU and memory metrics from each Node's kubelet/cAdvisor and exposes them via the `metrics.k8s.io` Kubernetes API. It enables `kubectl top` for humans and provides the data source for HPA and VPA to make scaling decisions.

---

**Q: Why does `kubectl top` fail on a fresh kubeadm cluster?**
> Metrics Server is not installed by default on kubeadm clusters. You need to deploy it manually. Additionally, on bare-metal/kubeadm clusters with self-signed kubelet certificates, you also need to add `--kubelet-insecure-tls` to the Metrics Server args, otherwise it cannot connect to kubelets.

---

**Q: Is Metrics Server a replacement for Prometheus?**
> No. Metrics Server stores only the current metrics snapshot (no history). It's lightweight and designed specifically for the HPA/VPA control loop and `kubectl top`. Prometheus is a full time-series database with alerting, dashboards, and long-term retention — use both together for complete observability.

---

**Q: How often does Metrics Server scrape metrics?**
> Every **15 seconds** by default (configurable via `--metric-resolution` flag). Data older than the latest scrape is not kept — it's pure current-state data.

---

**Q: What happens to HPA if Metrics Server goes down?**
> The HPA controller will log an error and use the **last known metrics**. It will not scale down to 0 or make drastic changes. After a configurable timeout period, it may stop scaling entirely until metrics are available again. This is a safety mechanism to avoid oscillation.

---

## 11. Exam Practice Questions

**1.** What command shows CPU and memory usage for all Pods in namespace `monitoring`?
```bash
kubectl top pods -n monitoring
```

**2.** Show per-container metrics for all pods across the cluster.
```bash
kubectl top pods -A --containers
```

**3.** On a kubeadm cluster, Metrics Server is installed but `kubectl top nodes` gives an error. What is the most likely fix?
```bash
# Add --kubelet-insecure-tls to metrics-server deployment args
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'
```

**4.** How do you verify the Metrics API is registered and available?
```bash
kubectl get apiservice v1beta1.metrics.k8s.io
# Check AVAILABLE column = True
```

**5.** Which component on each Node actually measures container CPU and memory?
> **cAdvisor**, which is built into the **kubelet**.

---

> **CKA Exam Tips**:
> - Metrics Server must be installed before HPA works — install it first in lab scenarios
> - On kubeadm exam environments: always add `--kubelet-insecure-tls`
> - `kubectl top` waits ~60s after pod creation for first metrics
> - `kubectl get apiservice v1beta1.metrics.k8s.io` is the fastest health check

---

*Notes by ITkannadigaru | CKA 2026 Certification*

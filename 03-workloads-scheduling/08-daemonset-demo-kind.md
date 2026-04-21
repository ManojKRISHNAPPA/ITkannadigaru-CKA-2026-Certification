# DaemonSet Demo — Prometheus + Grafana on kind Cluster

**Goal:** Prove the DaemonSet concept visually — deploy `node-exporter` as a DaemonSet so it runs on **every node** in a kind cluster, feed its metrics into Prometheus, and visualise per-node data in Grafana.

```
What you will see after this demo:
  node-exporter pod → on control-plane
  node-exporter pod → on worker-1
  node-exporter pod → on worker-2
  node-exporter pod → on worker-3
  
  Add a new node → DaemonSet auto-schedules a pod on it (no manual work)
  Remove a node  → Pod disappears automatically
```

---

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Prerequisites](#2-prerequisites)
3. [Step 1 — Create a Multi-Node kind Cluster](#3-step-1--create-a-multi-node-kind-cluster)
4. [Step 2 — Deploy Everything](#4-step-2--deploy-everything)
5. [Step 3 — Verify DaemonSet Behaviour](#5-step-3--verify-daemonset-behaviour)
6. [Step 4 — Open Prometheus UI](#6-step-4--open-prometheus-ui)
7. [Step 5 — Open Grafana UI](#7-step-5--open-grafana-ui)
8. [Step 6 — Prove DaemonSet Scales With Nodes](#8-step-6--prove-daemonset-scales-with-nodes)
9. [Step 7 — Explore node-exporter Metrics Directly](#9-step-7--explore-node-exporter-metrics-directly)
10. [Step 8 — Rolling Update Demo](#10-step-8--rolling-update-demo)
11. [Understanding the Architecture](#11-understanding-the-architecture)
12. [Troubleshooting](#12-troubleshooting)
13. [Cleanup](#13-cleanup)

---

## 1. Architecture Overview

```
┌──────────────────────────────────────────────────────────────────────┐
│                      kind Cluster (Docker)                           │
│                                                                      │
│  ┌─────────────────┐  ┌──────────────┐  ┌──────────────┐  ┌───────┐│
│  │ control-plane   │  │   worker-1   │  │   worker-2   │  │worker-3││
│  │                 │  │              │  │              │  │       ││
│  │[node-exporter]  │  │[node-exporter│  │[node-exporter│  │[node  ││
│  │ :9100           │  │  :9100]      │  │  :9100]      │  │exptr] ││
│  └─────────────────┘  └──────────────┘  └──────────────┘  └───────┘│
│           │                  │                 │               │     │
│           └──────────────────┼─────────────────┘───────────────     │
│                              │  scrapes all pods                     │
│                     ┌────────▼────────┐                             │
│                     │   Prometheus    │ (Deployment, 1 replica)     │
│                     │   :9090         │                             │
│                     └────────┬────────┘                             │
│                              │  datasource                          │
│                     ┌────────▼────────┐                             │
│                     │    Grafana      │ (Deployment, 1 replica)     │
│                     │   :3000         │                             │
│                     └─────────────────┘                             │
│                                                                      │
│  Your browser ─── kubectl port-forward ───► Grafana / Prometheus    │
└──────────────────────────────────────────────────────────────────────┘

DaemonSet (node-exporter):  1 pod per node  — scales automatically
Deployment  (prometheus):   1 pod total     — fixed replica
Deployment  (grafana):      1 pod total     — fixed replica
```

**Why node-exporter as DaemonSet?**
- It collects metrics from the **host node's OS** (CPU, memory, disk, network)
- It must run on **every node** to give complete cluster visibility
- If a new node joins, you need metrics from it **immediately** — DaemonSet handles this automatically

---

## 2. Prerequisites

```bash
# Check that kind is installed
kind version
# kind v0.27.0 go1.24.0 darwin/arm64

# Check kubectl
kubectl version --client
```

All YAML files for this demo are in:
```
03-workloads-scheduling/all-examples/daemonset-demo/
├── 01-kind-cluster.yaml              ← kind cluster definition
├── 02-namespace.yaml                 ← monitoring namespace
├── 03-node-exporter-daemonset.yaml   ← THE DAEMONSET (core demo)
├── 04-prometheus.yaml                ← Prometheus Deployment + config
├── 05-grafana.yaml                   ← Grafana Deployment + dashboards
└── 06-cleanup.sh                     ← tear down script
```

---

## 3. Step 1 — Create a Multi-Node kind Cluster

Navigate to the YAML files directory:

```bash
cd 03-workloads-scheduling/all-examples/daemonset-demo
```

Create the cluster (1 control-plane + 3 workers):

```bash
kind create cluster --name cka-demo --config 01-kind-cluster.yaml
```

Expected output:
```
Creating cluster "cka-demo" ...
 ✓ Ensuring node image (kindest/node:v1.32.0) 🖼
 ✓ Preparing nodes 📦 📦 📦 📦
 ✓ Writing configuration 📜
 ✓ Starting control-plane 🕹️
 ✓ Installing CNI 🔌
 ✓ Installing StorageClass 💾
 ✓ Joining worker nodes 🚜
Set kubectl context to "kind-cka-demo"
```

Verify 4 nodes are ready:

```bash
kubectl get nodes
# NAME                     STATUS   ROLES           AGE   VERSION
# cka-demo-control-plane   Ready    control-plane   1m    v1.32.0
# cka-demo-worker          Ready    <none>          1m    v1.32.0
# cka-demo-worker2         Ready    <none>          1m    v1.32.0
# cka-demo-worker3         Ready    <none>          1m    v1.32.0
```

> **CKA Key Point:** Notice 4 nodes — DaemonSet will create 4 pods automatically, 1 per node.

---

## 4. Step 2 — Deploy Everything

Apply all manifests in order:

```bash
# 1. Create the monitoring namespace
kubectl apply -f 02-namespace.yaml

# 2. Deploy node-exporter DaemonSet (MAIN DEMO OBJECT)
kubectl apply -f 03-node-exporter-daemonset.yaml

# 3. Deploy Prometheus
kubectl apply -f 04-prometheus.yaml

# 4. Deploy Grafana
kubectl apply -f 05-grafana.yaml
```

Or apply all at once:

```bash
kubectl apply -f 02-namespace.yaml \
              -f 03-node-exporter-daemonset.yaml \
              -f 04-prometheus.yaml \
              -f 05-grafana.yaml
```

Wait for all pods to be ready:

```bash
kubectl get pods -n monitoring -w

# Expected output (wait ~60s for all to reach Running):
# NAME                          READY   STATUS    NODE
# node-exporter-2k7bn           1/1     Running   cka-demo-control-plane
# node-exporter-4mxqp           1/1     Running   cka-demo-worker
# node-exporter-9zrwt           1/1     Running   cka-demo-worker2
# node-exporter-bvn8s           1/1     Running   cka-demo-worker3
# prometheus-7d6c4b5d9f-xk2mn   1/1     Running   cka-demo-worker
# grafana-5f6b7c8d9-zt4nw       1/1     Running   cka-demo-worker2
```

---

## 5. Step 3 — Verify DaemonSet Behaviour

### 5.1 Check DaemonSet status

```bash
kubectl get daemonset -n monitoring

# Output:
# NAME            DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR
# node-exporter   4         4         4       4            4           kubernetes.io/os=linux
#                 ^         ^         ^
#               4 nodes  4 pods   all ready
```

**Reading the columns:**
- `DESIRED` = number of nodes matching the DaemonSet's selector
- `CURRENT` = pods that have been created
- `READY` = pods that passed readiness check
- `UP-TO-DATE` = pods running the current spec
- `AVAILABLE` = pods available for service

### 5.2 Confirm 1 pod per node

```bash
kubectl get pods -n monitoring -o wide -l app=node-exporter

# NAME                READY   STATUS    NODE
# node-exporter-2k7bn 1/1     Running   cka-demo-control-plane   ← on control-plane!
# node-exporter-4mxqp 1/1     Running   cka-demo-worker
# node-exporter-9zrwt 1/1     Running   cka-demo-worker2
# node-exporter-bvn8s 1/1     Running   cka-demo-worker3
```

> **Key observation:** node-exporter runs on `cka-demo-control-plane` too!
> This is because we added a **toleration** for the control-plane taint.
> Without the toleration, DESIRED would be 3 (workers only).

### 5.3 Inspect the toleration that enables control-plane scheduling

```bash
kubectl get daemonset node-exporter -n monitoring -o yaml | grep -A 10 tolerations

# tolerations:
#   - effect: NoSchedule
#     key: node-role.kubernetes.io/control-plane
#     operator: Exists
#   - effect: NoSchedule
#     key: node-role.kubernetes.io/master
#     operator: Exists
```

### 5.4 Describe the DaemonSet

```bash
kubectl describe daemonset node-exporter -n monitoring

# Shows:
# Selector:   app=node-exporter
# Node-Selector: kubernetes.io/os=linux
# Tolerations: node-role.kubernetes.io/control-plane:NoSchedule op=Exists
#              node-role.kubernetes.io/master:NoSchedule op=Exists
# ...
# Events:
#   Normal  SuccessfulCreate  pod/node-exporter-2k7bn  (created for control-plane)
#   Normal  SuccessfulCreate  pod/node-exporter-4mxqp  (created for worker)
```

### 5.5 Verify node-exporter is exposing metrics

```bash
# Port-forward to one specific node-exporter pod
NODE_EXPORTER_POD=$(kubectl get pods -n monitoring -l app=node-exporter \
  -o jsonpath='{.items[0].metadata.name}')

kubectl port-forward -n monitoring pod/$NODE_EXPORTER_POD 9100:9100 &

# Test in another terminal
curl -s http://localhost:9100/metrics | head -20

# Expected: lines like:
# # HELP node_cpu_seconds_total Seconds the CPUs spent in each mode
# # TYPE node_cpu_seconds_total counter
# node_cpu_seconds_total{cpu="0",mode="idle"} 1234.56
# node_memory_MemTotal_bytes 8589934592
# node_filesystem_avail_bytes{...} 45678901234
```

```bash
# Stop the port-forward
kill %1
```

---

## 6. Step 4 — Open Prometheus UI

```bash
# Port-forward Prometheus to localhost:9090
kubectl port-forward -n monitoring svc/prometheus 9090:9090
```

Open your browser: **http://localhost:9090**

### What to check in Prometheus UI

**1. Verify all node-exporter targets are being scraped:**

Go to **Status → Targets** (`http://localhost:9090/targets`)

You should see **4 targets** (one per node), all showing `State: UP`:
```
node-exporter  http://192.168.x.x:9100/metrics  UP   (control-plane)
node-exporter  http://192.168.x.y:9100/metrics  UP   (worker-1)
node-exporter  http://192.168.x.z:9100/metrics  UP   (worker-2)
node-exporter  http://192.168.x.w:9100/metrics  UP   (worker-3)
```

> **This is the DaemonSet working:** 4 targets = 4 nodes = 4 node-exporter pods.

**2. Run test queries in the Graph tab:**

```promql
# CPU idle percentage per node
100 - (avg by (node) (rate(node_cpu_seconds_total{mode="idle"}[2m])) * 100)

# Memory available per node
node_memory_MemAvailable_bytes

# Count of node-exporter instances (should equal number of nodes)
count(up{job="node-exporter"})

# Load average per node
node_load1
```

---

## 7. Step 5 — Open Grafana UI

Stop the Prometheus port-forward first (`Ctrl+C`), then:

```bash
# Port-forward Grafana to localhost:3000
kubectl port-forward -n monitoring svc/grafana 3000:3000
```

Open your browser: **http://localhost:3000**

**Login credentials:**
```
Username: admin
Password: admin123
```

### Navigate to the pre-loaded dashboard

1. Click the **Dashboards** icon (grid icon in left sidebar)
2. Click **Browse**
3. Open folder **CKA Demo**
4. Click **Node Overview — DaemonSet Demo**

**What you will see:**
- **CPU Usage per Node (%)** — time-series, one line per node
- **Memory Usage per Node (%)** — time-series, one line per node
- **node-exporter Pods** — stat showing count = 4 (one per node)
- **Node Load Average** — per node
- **Filesystem Usage** — per node

> **Teaching moment:** The **"node-exporter Pods"** stat shows `4`.
> If the DaemonSet were a Deployment with `replicas: 4`, they might all
> land on 1 or 2 nodes — you'd get duplicate metrics from some nodes
> and no metrics from others. DaemonSet guarantees exactly 1 per node.

---

## 8. Step 6 — Prove DaemonSet Scales With Nodes

This is the most powerful part of the demo.

### 8.1 Check current state

```bash
kubectl get daemonset node-exporter -n monitoring
# DESIRED: 4

kubectl get pods -n monitoring -l app=node-exporter -o wide
# 4 pods on 4 nodes
```

### 8.2 Add a new worker node to the kind cluster

kind does NOT support adding nodes to an existing cluster. Instead, we demonstrate by **labeling a node to exclude it**, then re-including it:

```bash
# Option A: Simulate "node removed" by cordoning a node
kubectl cordon cka-demo-worker3

# Check DaemonSet — DESIRED drops (new pods won't schedule on cordoned node)
kubectl get daemonset node-exporter -n monitoring
# Note: existing pod on worker3 keeps running (cordon only affects NEW scheduling)

# Delete the pod on the cordoned node to simulate node removal
kubectl delete pod -n monitoring -l app=node-exporter \
  --field-selector spec.nodeName=cka-demo-worker3

# Check — DaemonSet will NOT reschedule it (node is cordoned)
kubectl get pods -n monitoring -l app=node-exporter -o wide
# worker3 has no node-exporter pod now

# Uncordon — DaemonSet immediately schedules a new pod
kubectl uncordon cka-demo-worker3

# Watch DaemonSet auto-create the pod
kubectl get pods -n monitoring -l app=node-exporter -o wide -w
# New pod appears on worker3 automatically — no manual action needed!
```

> **CKA Key Point:** `kubectl cordon <node>` adds taint
> `node.kubernetes.io/unschedulable:NoSchedule`. DaemonSet with a matching
> toleration would still schedule there, but without it — the pod won't
> reschedule on the cordoned node.

### 8.3 Alternative: Delete a node-exporter pod and watch it self-heal

```bash
# Delete one pod — DaemonSet controller immediately recreates it
kubectl delete pod -n monitoring \
  $(kubectl get pods -n monitoring -l app=node-exporter \
    -o jsonpath='{.items[0].metadata.name}')

# Watch it come back
kubectl get pods -n monitoring -l app=node-exporter -w
# The deleted pod is replaced within seconds
```

---

## 9. Step 7 — Explore node-exporter Metrics Directly

Each node-exporter pod exposes a `/metrics` endpoint. This shows what Prometheus scrapes from each node.

```bash
# Get all node-exporter pod names
kubectl get pods -n monitoring -l app=node-exporter \
  -o custom-columns="NAME:.metadata.name,NODE:.spec.nodeName"

# NAME                NODE
# node-exporter-2k7bn cka-demo-control-plane
# node-exporter-4mxqp cka-demo-worker
# node-exporter-9zrwt cka-demo-worker2
# node-exporter-bvn8s cka-demo-worker3
```

```bash
# Port-forward to the control-plane's node-exporter
kubectl port-forward -n monitoring \
  $(kubectl get pod -n monitoring -l app=node-exporter \
    --field-selector spec.nodeName=cka-demo-control-plane \
    -o jsonpath='{.items[0].metadata.name}') \
  9100:9100 &

# Explore metrics
curl -s http://localhost:9100/metrics | grep "^node_cpu"
curl -s http://localhost:9100/metrics | grep "^node_memory"
curl -s http://localhost:9100/metrics | grep "^node_load"

# Count metrics
curl -s http://localhost:9100/metrics | wc -l
# ~1000 metrics exposed per node

kill %1    # stop port-forward
```

```bash
# Now port-forward to worker-1 and compare
kubectl port-forward -n monitoring \
  $(kubectl get pod -n monitoring -l app=node-exporter \
    --field-selector spec.nodeName=cka-demo-worker \
    -o jsonpath='{.items[0].metadata.name}') \
  9101:9100 &

# These are DIFFERENT values — different node's hardware
curl -s http://localhost:9101/metrics | grep "^node_memory_MemTotal"

kill %1
```

---

## 10. Step 8 — Rolling Update Demo

Update the node-exporter image version and watch it roll out node by node:

```bash
# Current version
kubectl get daemonset node-exporter -n monitoring \
  -o jsonpath='{.spec.template.spec.containers[0].image}'
# prom/node-exporter:v1.7.0

# Trigger a rolling update by changing the image tag
kubectl set image daemonset/node-exporter \
  node-exporter=prom/node-exporter:v1.8.0 \
  -n monitoring

# Watch the rolling update — pods updated one node at a time
kubectl rollout status daemonset/node-exporter -n monitoring

# Waiting for daemon set "node-exporter" rollout to finish:
#   0 out of 4 new pods have been updated...
#   1 out of 4 new pods have been updated...
#   2 out of 4 new pods have been updated...
#   3 out of 4 new pods have been updated...
#   4 out of 4 new pods have been updated...
# daemon set "node-exporter" successfully rolled out

# Verify all pods now run v1.8.0
kubectl get pods -n monitoring -l app=node-exporter \
  -o custom-columns="NAME:.metadata.name,IMAGE:.spec.containers[0].image,NODE:.spec.nodeName"
```

### Roll back the update

```bash
kubectl rollout undo daemonset/node-exporter -n monitoring
kubectl rollout status daemonset/node-exporter -n monitoring

# All pods back to v1.7.0
```

---

## 11. Understanding the Architecture

### Why Deployment for Prometheus/Grafana, not DaemonSet?

```
node-exporter → DaemonSet
  WHY: Must collect metrics from EVERY node's host filesystem
       Running 4 copies in 4 locations is the correct design
       If a node joins → need metrics from it immediately

Prometheus → Deployment (1 replica)
  WHY: Single source of truth for all scraped data
       Has a persistent storage for time-series data
       Running multiple replicas needs HA setup (Thanos/Cortex)
       1 Prometheus scrapes all 4 node-exporters centrally

Grafana → Deployment (1 replica)
  WHY: UI layer, stateless, single instance is enough for demo
       Multiple replicas possible with shared storage
```

### How Prometheus discovers node-exporter pods

```yaml
# In prometheus.yml ConfigMap:
kubernetes_sd_configs:
  - role: pod              # Discover pods automatically via Kubernetes API
    namespaces:
      names: [monitoring]

relabel_configs:
  - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
    action: keep           # Only scrape pods with annotation: true
    regex: "true"
```

The DaemonSet pod template has:
```yaml
annotations:
  prometheus.io/scrape: "true"
  prometheus.io/port: "9100"
```

This is how Prometheus finds all 4 node-exporter pods without manual configuration — adding a node adds a pod, which Prometheus automatically discovers and starts scraping.

---

## 12. Troubleshooting

### Problem: DaemonSet shows DESIRED=3 instead of 4

```bash
# Control-plane node missing — check its taint
kubectl describe node cka-demo-control-plane | grep Taint
# Taints: node-role.kubernetes.io/control-plane:NoSchedule

# Check toleration in DaemonSet
kubectl get ds node-exporter -n monitoring -o yaml | grep -A 8 tolerations
# Should include the control-plane toleration

# If missing, patch it
kubectl patch daemonset node-exporter -n monitoring --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/tolerations/-",
  "value":{"key":"node-role.kubernetes.io/control-plane","operator":"Exists","effect":"NoSchedule"}}]'
```

### Problem: node-exporter pods in CrashLoopBackOff

```bash
# Check logs
kubectl logs -n monitoring \
  $(kubectl get pod -n monitoring -l app=node-exporter \
    -o jsonpath='{.items[0].metadata.name}')

# Common cause in kind: /proc or /sys mount issues
# Fix: verify hostPath volumes are correct in the YAML
kubectl describe pod -n monitoring \
  $(kubectl get pod -n monitoring -l app=node-exporter \
    -o jsonpath='{.items[0].metadata.name}') | grep -A 10 Volumes
```

### Problem: Prometheus shows 0 targets or all DOWN

```bash
# Check Prometheus logs
kubectl logs -n monitoring \
  $(kubectl get pod -n monitoring -l app=prometheus \
    -o jsonpath='{.items[0].metadata.name}')

# Check if Prometheus can reach node-exporter service
kubectl exec -n monitoring \
  $(kubectl get pod -n monitoring -l app=prometheus \
    -o jsonpath='{.items[0].metadata.name}') \
  -- wget -qO- http://node-exporter:9100/metrics | head -5

# Check RBAC — Prometheus needs permission to list pods
kubectl auth can-i list pods --as=system:serviceaccount:monitoring:prometheus -n monitoring
# Should return: yes
```

### Problem: Grafana shows "No data"

```bash
# Check if Grafana can reach Prometheus
kubectl exec -n monitoring \
  $(kubectl get pod -n monitoring -l app=grafana \
    -o jsonpath='{.items[0].metadata.name}') \
  -- wget -qO- http://prometheus:9090/api/v1/query?query=up | head

# Check datasource in Grafana UI
# → Configuration → Data sources → Prometheus → Test
```

### Problem: kubectl context not set to kind cluster

```bash
# List available contexts
kubectl config get-contexts

# Switch to the kind cluster
kubectl config use-context kind-cka-demo

# Verify
kubectl get nodes
```

---

## 13. Cleanup

When done with the demo:

```bash
# Option 1: Delete just the monitoring namespace (keeps cluster)
kubectl delete namespace monitoring

# Option 2: Delete the entire kind cluster (everything gone)
kind delete cluster --name cka-demo

# Or use the cleanup script
bash 06-cleanup.sh
```

---

## Quick Reference — All Commands in Order

```bash
# ── Setup ────────────────────────────────────────────────────
cd 03-workloads-scheduling/all-examples/daemonset-demo

kind create cluster --name cka-demo --config 01-kind-cluster.yaml

kubectl apply -f 02-namespace.yaml \
              -f 03-node-exporter-daemonset.yaml \
              -f 04-prometheus.yaml \
              -f 05-grafana.yaml

kubectl get pods -n monitoring -w

# ── Verify DaemonSet ─────────────────────────────────────────
kubectl get daemonset -n monitoring
kubectl get pods -n monitoring -l app=node-exporter -o wide
kubectl describe daemonset node-exporter -n monitoring

# ── Prometheus UI ────────────────────────────────────────────
kubectl port-forward -n monitoring svc/prometheus 9090:9090
# Open: http://localhost:9090  →  Status → Targets

# ── Grafana UI ───────────────────────────────────────────────
kubectl port-forward -n monitoring svc/grafana 3000:3000
# Open: http://localhost:3000  →  admin / admin123
# Dashboard: CKA Demo → Node Overview

# ── Self-healing demo ────────────────────────────────────────
kubectl delete pod -n monitoring \
  $(kubectl get pod -n monitoring -l app=node-exporter \
    -o jsonpath='{.items[0].metadata.name}')
kubectl get pods -n monitoring -l app=node-exporter -o wide -w

# ── Rolling update demo ──────────────────────────────────────
kubectl set image ds/node-exporter node-exporter=prom/node-exporter:v1.8.0 -n monitoring
kubectl rollout status ds/node-exporter -n monitoring
kubectl rollout undo ds/node-exporter -n monitoring

# ── Cleanup ──────────────────────────────────────────────────
kind delete cluster --name cka-demo
```

---

*Demo by ITkannadigaru | CKA 2026 Certification*

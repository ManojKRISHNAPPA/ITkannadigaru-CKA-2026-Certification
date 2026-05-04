# Kubernetes HPA — Horizontal Pod Autoscaler Complete Guide

> HPA watches your metrics and adds or removes Pod replicas automatically — so your app scales out under load and saves cost when idle.

---

## Table of Contents

1. [What is HPA?](#1-what-is-hpa)
2. [How HPA Works — The Control Loop](#2-how-hpa-works--the-control-loop)
3. [HPA Algorithm — Replica Calculation](#3-hpa-algorithm--replica-calculation)
4. [Prerequisites](#4-prerequisites)
5. [HPA v2 Spec — Full Reference](#5-hpa-v2-spec--full-reference)
6. [CPU-Based Autoscaling](#6-cpu-based-autoscaling)
7. [Memory-Based Autoscaling](#7-memory-based-autoscaling)
8. [Multiple Metrics](#8-multiple-metrics)
9. [Custom and External Metrics](#9-custom-and-external-metrics)
10. [Scaling Behavior — Speed Control](#10-scaling-behavior--speed-control)
11. [Full Demo — CPU-based HPA with Load Test](#11-full-demo--cpu-based-hpa-with-load-test)
12. [HPA with Deployments vs StatefulSets](#12-hpa-with-deployments-vs-statefulsets)
13. [Common Issues and Troubleshooting](#13-common-issues-and-troubleshooting)
14. [Common Interview Questions](#14-common-interview-questions)
15. [Exam Practice Questions](#15-exam-practice-questions)

---

## 1. What is HPA?

**Horizontal Pod Autoscaler (HPA)** automatically scales the **number of Pod replicas** in a Deployment, ReplicaSet, or StatefulSet based on observed metrics (CPU, memory, custom).

```
  Normal load:                  High load:                 Load drops:
  
  ┌──────────┐                 ┌──────────┐               ┌──────────┐
  │  HPA     │                 │  HPA     │               │  HPA     │
  │ min: 2   │                 │ detected │               │ detected │
  │ max: 10  │                 │ CPU 80%  │               │ CPU 20%  │
  └────┬─────┘                 └────┬─────┘               └────┬─────┘
       │                            │ scale out                │ scale in
       ▼                            ▼                          ▼
  [Pod][Pod]                [Pod][Pod][Pod][Pod]           [Pod][Pod]
```

**What HPA scales (horizontal):** adds/removes Pods  
**What HPA does NOT do:** change CPU/memory limits on existing Pods — that's VPA

---

## 2. How HPA Works — The Control Loop

```
  Every 15 seconds (default):

  ┌─────────────────────────────────────────────────────────┐
  │                  HPA Control Loop                        │
  │                                                          │
  │  1. Query Metrics API                                    │
  │     GET /apis/metrics.k8s.io/v1beta1/namespaces/...      │
  │                  │                                       │
  │  2. Calculate desired replicas                           │
  │     desiredReplicas = ceil(currentReplicas *              │
  │                       currentMetric / desiredMetric)      │
  │                  │                                       │
  │  3. Compare with current replica count                   │
  │                  │                                       │
  │  4. Update Deployment/ReplicaSet .spec.replicas          │
  │                  │                                       │
  │  5. Kubernetes scheduler creates/deletes Pods            │
  └─────────────────────────────────────────────────────────┘
```

**Key timing:**

| Action | Default Interval |
|--------|-----------------|
| HPA sync loop | 15 seconds |
| Scale-up cooldown | 0 seconds (scale up fast) |
| Scale-down stabilization | 300 seconds (5 min) |
| Metrics Server scrape | 15 seconds |

---

## 3. HPA Algorithm — Replica Calculation

```
desiredReplicas = ceil[ currentReplicas × (currentMetricValue / desiredMetricValue) ]
```

### Example Calculations

**Setup:** Deployment with 3 replicas, HPA target CPU = 50%

```
Scenario 1 — Scale Up:
  Current replicas:   3
  Current CPU avg:    90%
  Target CPU:         50%
  
  desiredReplicas = ceil(3 × 90/50) = ceil(5.4) = 6
  Result: Scale up to 6 replicas

Scenario 2 — Scale Down:
  Current replicas:   6
  Current CPU avg:    20%
  Target CPU:         50%
  
  desiredReplicas = ceil(6 × 20/50) = ceil(2.4) = 3
  Result: Scale down to 3 replicas (after stabilization window)

Scenario 3 — No Change:
  Current replicas:   4
  Current CPU avg:    50%
  Target CPU:         50%
  
  desiredReplicas = ceil(4 × 50/50) = ceil(4.0) = 4
  Result: No change
```

**Tolerances:**
- HPA ignores metric fluctuations within **±10%** of the target (avoids thrashing)
- If current metric is within 90%–110% of target, no scaling happens

---

## 4. Prerequisites

HPA requires:

```
1. Metrics Server installed and running
   kubectl get apiservice v1beta1.metrics.k8s.io  (AVAILABLE=True)

2. Pod must have resource requests defined
   resources:
     requests:
       cpu: 100m      ← HPA calculates % relative to this value
```

> **Critical**: If a Pod has no `resources.requests.cpu`, HPA cannot calculate CPU utilization percentage and will report `<unknown>`. Always set CPU requests on Pods that HPA manages.

---

## 5. HPA v2 Spec — Full Reference

```yaml
apiVersion: autoscaling/v2         # v2 supports multiple metrics
kind: HorizontalPodAutoscaler
metadata:
  name: my-hpa
  namespace: default
spec:
  # Target workload to scale
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment               # or StatefulSet, ReplicaSet
    name: my-deployment

  # Replica bounds
  minReplicas: 2                   # never scale below this
  maxReplicas: 10                  # never scale above this

  # Metrics to watch
  metrics:
  - type: Resource                 # CPU or Memory
    resource:
      name: cpu
      target:
        type: Utilization          # Utilization | AverageValue | Value
        averageUtilization: 50     # target 50% of requested CPU

  # Scaling speed control (optional)
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0
      policies:
      - type: Percent
        value: 100
        periodSeconds: 15
    scaleDown:
      stabilizationWindowSeconds: 300
      policies:
      - type: Pods
        value: 1
        periodSeconds: 60
```

### Metric Target Types

| type | Meaning | Unit |
|------|---------|------|
| `Utilization` | % of the Pod's resource request | 0–100 |
| `AverageValue` | Average raw metric value per Pod | e.g., `500m` CPU |
| `Value` | Total metric value across all Pods | e.g., `1000m` total |

---

## 6. CPU-Based Autoscaling

The most common HPA type — scale Pods when average CPU utilization crosses a threshold.

### Deployment with CPU request (required)

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: web-api
  template:
    metadata:
      labels:
        app: web-api
    spec:
      containers:
      - name: app
        image: nginx:1.21
        resources:
          requests:
            cpu: 100m           # ← HPA uses this as 100% baseline
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 256Mi
```

### HPA targeting 50% CPU

```yaml
# hpa-cpu.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-api-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web-api
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50   # scale when avg CPU > 50% of 100m = 50m
```

```bash
kubectl apply -f deployment.yaml
kubectl apply -f hpa-cpu.yaml

# Check HPA status
kubectl get hpa web-api-hpa

# Output:
# NAME          REFERENCE             TARGETS   MINPODS   MAXPODS   REPLICAS
# web-api-hpa   Deployment/web-api   22%/50%   2         10        2

# Detailed view
kubectl describe hpa web-api-hpa
```

### Imperative HPA creation

```bash
# Quick HPA with imperative command
kubectl autoscale deployment web-api --cpu-percent=50 --min=2 --max=10

# Same as applying the YAML above
```

---

## 7. Memory-Based Autoscaling

```yaml
# hpa-memory.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-api-mem-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web-api
  minReplicas: 2
  maxReplicas: 8
  metrics:
  - type: Resource
    resource:
      name: memory
      target:
        type: AverageValue
        averageValue: 200Mi    # scale when avg memory usage > 200Mi per pod
```

> **Note on Memory HPA**: Memory-based scaling is less reliable than CPU. Memory doesn't compress — Pods rarely release memory voluntarily. CPU drops naturally when load drops, memory might not. Consider VPA for memory right-sizing instead.

---

## 8. Multiple Metrics

HPA can watch multiple metrics simultaneously. It calculates the desired replica count for **each metric** and takes the **maximum** result.

```yaml
# hpa-multi.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-api-multi-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web-api
  minReplicas: 2
  maxReplicas: 20
  metrics:
  # Scale on CPU
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 60

  # AND scale on memory
  - type: Resource
    resource:
      name: memory
      target:
        type: AverageValue
        averageValue: 300Mi
```

**How HPA picks the replica count with multiple metrics:**
```
CPU metric says: scale to 4 replicas
Memory metric says: scale to 7 replicas
HPA chooses: 7 (always takes the MAX to ensure all metrics are satisfied)
```

---

## 9. Custom and External Metrics

For advanced use cases — scale on HTTP requests per second, queue length, etc.

**Requires:** custom metrics adapter (e.g., Prometheus Adapter, KEDA)

```yaml
# Scale on custom metric: http_requests_per_second
- type: Pods
  pods:
    metric:
      name: http_requests_per_second
    target:
      type: AverageValue
      averageValue: "1000"    # 1000 req/s per pod

# Scale on external metric: SQS queue depth
- type: External
  external:
    metric:
      name: sqs_messages_visible
      selector:
        matchLabels:
          queue: my-worker-queue
    target:
      type: AverageValue
      averageValue: "30"      # 30 messages per pod
```

---

## 10. Scaling Behavior — Speed Control

Control **how fast** HPA scales up or down to prevent flapping.

```yaml
spec:
  behavior:
    scaleUp:
      stabilizationWindowSeconds: 0    # scale up immediately
      policies:
      - type: Percent                  # scale up by max 100% per period
        value: 100
        periodSeconds: 15
      - type: Pods                     # OR scale up by max 4 pods per period
        value: 4
        periodSeconds: 60
      selectPolicy: Max                # use whichever policy allows MORE replicas

    scaleDown:
      stabilizationWindowSeconds: 300  # wait 5 min before scaling down
      policies:
      - type: Percent                  # scale down by max 10% per period
        value: 10
        periodSeconds: 60
      - type: Pods                     # OR scale down by max 2 pods per period
        value: 2
        periodSeconds: 60
      selectPolicy: Min                # use whichever policy allows FEWER scale-downs
```

### Stabilization Window Explained

```
  Without stabilization (bad):        With 5-min stabilization (good):
  
  t=0:  CPU 90% → 6 replicas          t=0:  CPU 90% → 6 replicas
  t=1m: CPU 40% → 2 replicas          t=1m: CPU 40% → "wants" 2 reps
  t=2m: CPU 80% → 5 replicas          t=2m: CPU 80% → "wants" 5 reps
  t=3m: CPU 30% → 2 replicas          t=3m: CPU 30% → "wants" 2 reps
  → Pods being killed and created      t=5m: 5-min window passes
    constantly (expensive + slow)      → Scales down to 2 replicas
                                       → Stable!
```

---

## 11. Full Demo — CPU-based HPA with Load Test

```bash
# === STEP 1: Install Metrics Server (if not done) ===
minikube addons enable metrics-server
# OR for kubeadm:
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
kubectl patch deployment metrics-server -n kube-system \
  --type='json' \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

kubectl rollout status deployment/metrics-server -n kube-system

# === STEP 2: Deploy a CPU-intensive app ===
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: php-apache
spec:
  replicas: 1
  selector:
    matchLabels:
      app: php-apache
  template:
    metadata:
      labels:
        app: php-apache
    spec:
      containers:
      - name: php-apache
        image: registry.k8s.io/hpa-example
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: 200m           # ← baseline for HPA %
          limits:
            cpu: 500m
---
apiVersion: v1
kind: Service
metadata:
  name: php-apache
spec:
  selector:
    app: php-apache
  ports:
  - port: 80
EOF

kubectl rollout status deployment/php-apache

# === STEP 3: Create HPA ===
kubectl autoscale deployment php-apache --cpu-percent=50 --min=1 --max=10

# OR with YAML:
cat <<EOF | kubectl apply -f -
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: php-apache
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: php-apache
  minReplicas: 1
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50
EOF

# Watch HPA status (open a new terminal for this)
kubectl get hpa php-apache -w

# === STEP 4: Generate Load ===
# In a SEPARATE terminal — run a load generator
kubectl run load-generator --image=busybox:1.28 --rm -it --restart=Never \
  -- /bin/sh -c "while sleep 0.01; do wget -q -O- http://php-apache; done"

# === STEP 5: Watch HPA Scale UP ===
# Back in original terminal:
watch -n5 kubectl get hpa php-apache

# After ~1-2 minutes you should see:
# NAME         REFERENCE               TARGETS    MINPODS   MAXPODS   REPLICAS
# php-apache   Deployment/php-apache   250%/50%   1         10        5

# Also watch pods:
kubectl get pods -l app=php-apache -w

# === STEP 6: Stop the Load ===
# Kill the load-generator pod (Ctrl+C in that terminal)

# === STEP 7: Watch HPA Scale DOWN ===
# Takes ~5 minutes (stabilization window)
watch -n15 kubectl get hpa php-apache

# After 5 minutes:
# NAME         REFERENCE               TARGETS   MINPODS   MAXPODS   REPLICAS
# php-apache   Deployment/php-apache   0%/50%    1         10        1

# === STEP 8: Inspect Events ===
kubectl describe hpa php-apache
# Look at "Events" section — shows each scale decision

# === CLEANUP ===
kubectl delete deployment php-apache
kubectl delete service php-apache
kubectl delete hpa php-apache
```

---

## 12. HPA with Deployments vs StatefulSets

```yaml
# HPA targeting a StatefulSet
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: StatefulSet    # ← works the same way
    name: my-statefulset
```

> **Caution with StatefulSets**: Scaling StatefulSets involves creating/deleting Pods with **stable identities and persistent storage**. Rapid autoscaling can cause storage provisioning delays or data issues. Use HPA carefully with stateful workloads — and always set conservative `scaleDown.stabilizationWindowSeconds`.

---

## 13. Common Issues and Troubleshooting

### Issue: HPA shows `<unknown>/50%` for targets

```bash
kubectl describe hpa my-hpa
# Event: "failed to get cpu utilization: unable to get metrics for resource cpu"

# Fix 1: Ensure Metrics Server is running
kubectl get pods -n kube-system | grep metrics-server

# Fix 2: Ensure pod has CPU requests defined
kubectl get deployment my-deploy -o yaml | grep -A5 resources
# Must have: requests.cpu value

# Fix 3: Wait — new pods take ~60s for initial metrics
```

### Issue: HPA not scaling up despite high CPU

```bash
# Check if maxReplicas is already reached
kubectl get hpa my-hpa

# Check if pod can't be scheduled (no node capacity)
kubectl get events --sort-by='.lastTimestamp' | grep FailedScheduling

# Check HPA conditions
kubectl describe hpa my-hpa | grep -A20 Conditions
```

### Issue: HPA scales down too aggressively

```yaml
# Add stabilization to prevent rapid scale-down
behavior:
  scaleDown:
    stabilizationWindowSeconds: 600   # wait 10 minutes before scaling down
```

---

## 14. Common Interview Questions

**Q: What is HPA and how does it work?**
> HPA (Horizontal Pod Autoscaler) automatically adjusts the number of Pod replicas in a Deployment or StatefulSet based on observed metrics. Every 15 seconds, the HPA controller queries the Metrics API, calculates the desired replica count using the formula `ceil(currentReplicas × currentMetric/targetMetric)`, and updates the workload's replica count. It respects `minReplicas` and `maxReplicas` bounds.

---

**Q: What are the prerequisites for HPA to work?**
> 1. **Metrics Server** must be installed (provides the CPU/memory data)
> 2. **Pods must have `resources.requests.cpu`** set — HPA calculates utilization as a percentage of the request value. Without requests, HPA reports `<unknown>`.

---

**Q: What is the difference between HPA and VPA?**
> **HPA** (Horizontal Pod Autoscaler) adds or removes Pod replicas. It scales OUT (more pods). **VPA** (Vertical Pod Autoscaler) adjusts CPU and memory requests/limits on existing Pods. It scales UP (bigger pods). HPA is better for stateless apps; VPA is better for stateful apps or when you want to right-size a single Pod.

---

**Q: How does HPA handle multiple metrics?**
> HPA calculates the desired replica count independently for each metric and takes the **maximum** result. This ensures all metrics are satisfied — if CPU says 4 replicas and memory says 7, HPA scales to 7.

---

**Q: What is the stabilization window and why is it important?**
> The stabilization window (default 300s for scale-down) prevents HPA from rapidly removing Pods when metrics temporarily drop. HPA looks back at the maximum desired replica count over the window and only scales down if the metric has consistently been below target. Without it, brief load drops cause pod deletions followed immediately by pod creations (thrashing).

---

## 15. Exam Practice Questions

**1.** Create an HPA for deployment `api-server` targeting 70% CPU, min 2, max 8 replicas.
```bash
kubectl autoscale deployment api-server --cpu-percent=70 --min=2 --max=8
```

**2.** Write a v2 HPA YAML for the same spec.
```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: api-server-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  minReplicas: 2
  maxReplicas: 8
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

**3.** HPA shows `<unknown>/50%`. What do you check?
> Check that Metrics Server is running (`kubectl get pods -n kube-system | grep metrics`), and that the target deployment's pods have `resources.requests.cpu` defined.

**4.** What command watches HPA status live?
```bash
kubectl get hpa -w
# or
watch kubectl get hpa
```

**5.** How do you see the scale events (when HPA scaled up/down and why)?
```bash
kubectl describe hpa <name>
# Look at the "Events" section
```

---

> **CKA Exam Tips**:
> - `kubectl autoscale deployment <name> --cpu-percent=50 --min=2 --max=10` is fastest
> - Always install Metrics Server before creating HPA in lab environments
> - HPA `TARGETS` column showing `<unknown>` = missing CPU requests on pods
> - `autoscaling/v2` supports multiple metrics; `autoscaling/v1` is CPU-only (legacy)
> - Scale-down default cooldown = 5 minutes — be patient in demos

---

*Notes by ITkannadigaru | CKA 2026 Certification*

# Resource Requests and Limits in Kubernetes — Complete Guide

## Table of Contents
1. [What are Requests and Limits?](#1-what-are-requests-and-limits)
2. [Why They Matter](#2-why-they-matter)
3. [CPU vs Memory — How They Behave Differently](#3-cpu-vs-memory--how-they-behave-differently)
4. [Units — How to Express CPU and Memory](#4-units--how-to-express-cpu-and-memory)
5. [Declarative Way — YAML Examples](#5-declarative-way--yaml-examples)
6. [Imperative Way — kubectl Commands](#6-imperative-way--kubectl-commands)
7. [LimitRange — Default Limits for a Namespace](#7-limitrange--default-limits-for-a-namespace)
8. [ResourceQuota — Namespace-Level Total Limits](#8-resourcequota--namespace-level-total-limits)
9. [Quality of Service (QoS) Classes](#9-quality-of-service-qos-classes)
10. [How the Scheduler Uses Requests](#10-how-the-scheduler-uses-requests)
11. [What Happens When Limits Are Exceeded](#11-what-happens-when-limits-are-exceeded)
12. [Real-World Use Cases and Patterns](#12-real-world-use-cases-and-patterns)
13. [Common Mistakes and Pitfalls](#13-common-mistakes-and-pitfalls)
14. [Interview Questions — Scenario Based](#14-interview-questions--scenario-based)

---

```
kubectl patch deployment metrics-server -n kube-system \
--type='json' \
-p='[
{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-preferred-address-types=InternalIP"},
{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}
]'

```

## 1. What are Requests and Limits?

**Requests** and **Limits** are the two resource knobs on every container in Kubernetes.

```
requests = "I need at LEAST this much to start and run"
            → Used by the SCHEDULER to find a node with enough free capacity

limits    = "I will NEVER use more than this"
            → Enforced at RUNTIME by the container runtime (cgroups)
```

```
┌───────────────────────────────────────────────────────────────┐
│                Container Resource Lifecycle                    │
│                                                               │
│  SCHEDULING TIME:                                             │
│  Scheduler finds a node where:                                │
│    node.allocatable.cpu    >= sum of all container requests   │
│    node.allocatable.memory >= sum of all container requests   │
│                                                               │
│  RUNTIME:                                                     │
│  CPU:    Container throttled if it tries to exceed limit      │
│  Memory: Container OOMKilled if it exceeds limit              │
└───────────────────────────────────────────────────────────────┘
```

### Where they live in a Pod spec

```yaml
spec:
  containers:
    - name: app
      image: nginx
      resources:
        requests:
          cpu: "250m"       # Scheduler: reserve 0.25 CPU core
          memory: "128Mi"   # Scheduler: reserve 128 MiB RAM
        limits:
          cpu: "500m"       # Runtime: throttle if > 0.5 CPU core
          memory: "256Mi"   # Runtime: OOMKill if > 256 MiB RAM
```

---

## 2. Why They Matter

### Without requests and limits

```
┌──────────────────────────────────────────────────────┐
│  Problem 1: Noisy Neighbour                          │
│  Pod A uses 90% CPU → Pod B starves → latency spike  │
│                                                      │
│  Problem 2: Node OOM                                 │
│  All pods grow → node runs out of memory             │
│  → node kills random processes → chaos               │
│                                                      │
│  Problem 3: Bad Scheduling                           │
│  Scheduler doesn't know how big a pod is             │
│  → over-packs nodes → all pods suffer                │
└──────────────────────────────────────────────────────┘
```

### With requests and limits

```
┌──────────────────────────────────────────────────────┐
│  Request: Scheduler picks the RIGHT node             │
│  Limit:   Misbehaving pod is contained               │
│  Result:  Predictable, fair resource sharing         │
└──────────────────────────────────────────────────────┘
```

---

## 3. CPU vs Memory — How They Behave Differently

This is one of the most important things to understand for CKA.

| Behaviour | CPU | Memory |
|-----------|-----|--------|
| Type | Compressible resource | Incompressible resource |
| Exceeds limit? | **Throttled** (slowed down) | **OOMKilled** (killed) |
| Can throttle? | Yes — CPU cycles withheld | No — can't take back memory |
| Pod evicted? | No | Yes (if over limit) |
| Exit code on breach | No exit | Exit code 137 (OOM) |

```
CPU is compressible:
  Pod uses too much CPU → kernel throttles it (fewer CPU slices)
  Pod is NOT killed — just slower

Memory is incompressible:
  Pod uses too much memory → OOM killer terminates the container
  Exit code 137 → container restarts (based on restartPolicy)
```

### The analogy

```
CPU   = Water tap    → you can restrict the flow rate without ending the session
Memory = Parking lot → once the lot is full, you have to tow a car to make space
```

---

## 4. Units — How to Express CPU and Memory

### CPU Units

```
1 CPU  = 1 vCPU = 1 core = 1000m (millicores)

Examples:
  cpu: "1"      = 1 full core
  cpu: "0.5"    = half a core       = cpu: "500m"
  cpu: "250m"   = quarter of a core
  cpu: "100m"   = 10% of a core
  cpu: "2000m"  = 2 full cores      = cpu: "2"

Smallest unit: 1m (1 millicore)
```

```
┌──────────────────────────────────────┐
│  1 CPU = 1000m                       │
│                                      │
│  ████████████████████████   1000m    │
│  ████████████             500m       │
│  ██████                   250m       │
│  ██                       100m       │
└──────────────────────────────────────┘
```

### Memory Units

```
SI (decimal):           Binary (IEC, recommended for K8s):
  K  = 1,000            Ki = 1,024
  M  = 1,000,000        Mi = 1,048,576
  G  = 1,000,000,000    Gi = 1,073,741,824

Examples:
  memory: "128Mi"   = 134,217,728 bytes   ← most common in K8s
  memory: "256Mi"
  memory: "512Mi"
  memory: "1Gi"     = 1,073,741,824 bytes
  memory: "2Gi"
  memory: "128M"    = 128,000,000 bytes   (slightly less than 128Mi)

Use Mi/Gi (binary) for K8s — more predictable with OS memory management.
```

---

## 5. Declarative Way — YAML Examples

### 5.1 Basic Pod with Requests and Limits

```yaml
# pod-resources.yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-app
spec:
  containers:
    - name: web
      image: nginx:1.25
      resources:
        requests:
          cpu: "100m"       # Reserve 0.1 CPU core
          memory: "128Mi"   # Reserve 128 MiB RAM
        limits:
          cpu: "500m"       # Cap at 0.5 CPU core
          memory: "256Mi"   # Kill if > 256 MiB RAM
```

### 5.2 Multi-Container Pod — Each Container Has Its Own Resources

```yaml
# multi-container-resources.yaml
apiVersion: v1
kind: Pod
metadata:
  name: frontend-backend
spec:
  containers:
    - name: frontend
      image: nginx:1.25
      resources:
        requests:
          cpu: "100m"
          memory: "64Mi"
        limits:
          cpu: "200m"
          memory: "128Mi"

    - name: backend
      image: myapp:1.0
      resources:
        requests:
          cpu: "500m"      # Backend needs more CPU
          memory: "256Mi"
        limits:
          cpu: "1000m"
          memory: "512Mi"

# Total Pod requests: cpu=600m, memory=320Mi
# Scheduler finds a node with 600m CPU and 320Mi RAM available
```

### 5.3 Deployment with Resources

```yaml
# deployment-resources.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-server
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-server
  template:
    metadata:
      labels:
        app: api-server
    spec:
      containers:
        - name: api
          image: myapi:2.0
          ports:
            - containerPort: 8080
          resources:
            requests:
              cpu: "250m"
              memory: "256Mi"
            limits:
              cpu: "1000m"      # Allow bursting to 1 full core
              memory: "512Mi"

# 3 replicas × 250m CPU request = 750m total CPU requested from cluster
# 3 replicas × 256Mi memory request = 768Mi total RAM requested
```

### 5.4 Resources Only (No limits — Burstable QoS)

```yaml
# Only requests defined — pod can burst above request up to node capacity
spec:
  containers:
    - name: batch-job
      image: worker:1.0
      resources:
        requests:
          cpu: "100m"
          memory: "128Mi"
        # No limits — Burstable QoS, evictable under memory pressure
```

### 5.5 Guaranteed QoS — Requests Equal Limits

```yaml
# requests == limits → Guaranteed QoS (highest priority, last to be evicted)
spec:
  containers:
    - name: database
      image: postgres:15
      resources:
        requests:
          cpu: "500m"
          memory: "1Gi"
        limits:
          cpu: "500m"       # Same as request
          memory: "1Gi"     # Same as request
```

---

## 6. Imperative Way — kubectl Commands

### 6.1 Set resources on a running Deployment

```bash
# Set both requests and limits on a deployment
kubectl set resources deployment/web \
  --requests=cpu=100m,memory=128Mi \
  --limits=cpu=500m,memory=256Mi

# Set only limits
kubectl set resources deployment/web --limits=cpu=500m,memory=256Mi

# Set only requests
kubectl set resources deployment/web --requests=cpu=100m,memory=128Mi
```

### 6.2 Generate Pod YAML with resources

```bash
# Generate a pod YAML and add resources manually
kubectl run web --image=nginx --dry-run=client -o yaml > pod.yaml
# Then edit pod.yaml to add resources block under containers
```

### 6.3 Check current resource usage (metrics)

```bash
# Requires metrics-server installed
kubectl top pods
kubectl top pods --all-namespaces
kubectl top pods -n production
kubectl top pod web-pod

# Node resource usage
kubectl top nodes

# Output:
# NAME        CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
# node01      250m         25%    512Mi           25%
```

### 6.4 Inspect resource requests/limits on running pods

```bash
# Check resources on a specific pod
kubectl describe pod web-pod | grep -A 10 "Limits\|Requests"

# Output:
#   Limits:
#     cpu:     500m
#     memory:  256Mi
#   Requests:
#     cpu:     100m
#     memory:  128Mi

# Get all pods with resource info in JSON
kubectl get pods -o json | jq '.items[].spec.containers[].resources'
```

### 6.5 Describe a node to see allocatable vs requested

```bash
kubectl describe node node01

# Shows:
# Allocatable:
#   cpu:     4
#   memory:  8Gi
#
# Allocated resources:
#   (Total limits may be over 100 percent, i.e., overcommitted.)
#   Resource  Requests   Limits
#   --------  --------   ------
#   cpu       1250m/4    2500m/4
#   memory    2Gi/8Gi    4Gi/8Gi
```

---

## 7. LimitRange — Default Limits for a Namespace

A **LimitRange** sets default requests and limits that are automatically applied to pods/containers in a namespace that don't specify their own.

### Why use LimitRange?

```
Without LimitRange:
  - A pod with no resources block → BestEffort QoS (evicted first)
  - A pod with no limits → can consume all node memory → starves others

With LimitRange:
  - Automatically injects sensible defaults for any pod lacking resource spec
  - Enforces min/max bounds so individual pods can't be too tiny or too large
```

### 7.1 LimitRange with defaults

```yaml
# limitrange-defaults.yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: development
spec:
  limits:
    - type: Container
      default:               # Applied as LIMIT if container sets none
        cpu: "500m"
        memory: "256Mi"
      defaultRequest:        # Applied as REQUEST if container sets none
        cpu: "100m"
        memory: "128Mi"
      max:                   # Container cannot set limit higher than this
        cpu: "2"
        memory: "2Gi"
      min:                   # Container cannot set request lower than this
        cpu: "50m"
        memory: "64Mi"
```

```bash
kubectl apply -f limitrange-defaults.yaml

# Verify
kubectl describe limitrange default-limits -n development
```

### 7.2 LimitRange for Pods (total)

```yaml
# limitrange-pod-total.yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: pod-total-limit
  namespace: development
spec:
  limits:
    - type: Pod
      max:
        cpu: "4"             # One Pod cannot exceed 4 CPU cores total
        memory: "4Gi"        # One Pod cannot exceed 4Gi RAM total
```

### How defaults are applied

```
Scenario:
  LimitRange sets default cpu limit = 500m, default cpu request = 100m

  Pod A (no resources block):
    → Gets: requests.cpu=100m, limits.cpu=500m  (injected by LimitRange)

  Pod B (only sets limit=250m, no request):
    → Gets: requests.cpu=250m  (request = limit when only limit is set)

  Pod C (sets both request=50m, limit=200m):
    → Uses its own values, LimitRange does not override
```

---

## 8. ResourceQuota — Namespace-Level Total Limits

A **ResourceQuota** caps the **total** resource consumption across all pods in a namespace.

```
LimitRange  = per-container / per-pod limits
ResourceQuota = total across the ENTIRE namespace
```

### 8.1 ResourceQuota for a team namespace

```yaml
# resourcequota-team.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
  namespace: team-alpha
spec:
  hard:
    # Total CPU and memory across all pods
    requests.cpu: "4"          # All pods combined cannot request > 4 CPU
    requests.memory: "8Gi"     # All pods combined cannot request > 8Gi RAM
    limits.cpu: "8"            # All pods combined cannot have > 8 CPU limits
    limits.memory: "16Gi"      # All pods combined cannot have > 16Gi limits

    # Object count limits
    pods: "20"                 # Max 20 pods in this namespace
    services: "10"
    persistentvolumeclaims: "5"
    secrets: "20"
    configmaps: "20"
```

```bash
kubectl apply -f resourcequota-team.yaml

# Check quota usage
kubectl describe resourcequota team-quota -n team-alpha
# Output:
#  Resource            Used    Hard
#  --------            ----    ----
#  limits.cpu          2500m   8
#  limits.memory       3Gi     16Gi
#  pods                5       20
#  requests.cpu        1250m   4
#  requests.memory     2Gi     8Gi
```

### 8.2 What happens when quota is exceeded

```bash
# Trying to create a pod that would breach the quota
kubectl run extra-pod --image=nginx -n team-alpha

# Error:
# Error from server (Forbidden): pods "extra-pod" is forbidden:
# exceeded quota: team-quota, requested: pods=1,
# used: pods=20, limited: pods=20
```

### LimitRange vs ResourceQuota — Side-by-Side

| Feature | LimitRange | ResourceQuota |
|---------|-----------|---------------|
| Scope | Per container / per pod | Entire namespace total |
| Sets defaults | Yes | No |
| Caps individual pod | Yes (min/max) | No |
| Caps namespace total | No | Yes |
| Typical use | Prevent oversized/undersized pods | Fair quota between teams |

---

## 9. Quality of Service (QoS) Classes

Kubernetes automatically assigns a **QoS class** to every Pod based on its resource configuration. This determines **eviction priority** when the node is under memory pressure.

### The 3 QoS Classes

```
┌──────────────────────────────────────────────────────────────┐
│               QoS Classes (eviction order)                   │
├──────────────────────────────────────────────────────────────┤
│  BestEffort   ← EVICTED FIRST (lowest priority)              │
│  No resources defined at all                                 │
├──────────────────────────────────────────────────────────────┤
│  Burstable    ← EVICTED SECOND                               │
│  Has requests but limits ≠ requests                          │
│  OR only some containers have limits                         │
├──────────────────────────────────────────────────────────────┤
│  Guaranteed   ← EVICTED LAST (highest priority)              │
│  requests == limits for ALL resources in ALL containers      │
└──────────────────────────────────────────────────────────────┘
```

### 9.1 BestEffort — No resources defined

```yaml
spec:
  containers:
    - name: app
      image: nginx
      # No resources block at all → BestEffort
```

```
BestEffort pods:
  - First to be evicted when node runs low on memory
  - Can use any available node resources (no reservation)
  - Use for: batch jobs, dev/test workloads where eviction is acceptable
```

### 9.2 Burstable — Has some resources defined

```yaml
spec:
  containers:
    - name: app
      image: nginx
      resources:
        requests:
          cpu: "100m"
          memory: "128Mi"
        limits:
          cpu: "500m"
          memory: "512Mi"
        # limits != requests → Burstable
```

```
Burstable pods:
  - Evicted after BestEffort, before Guaranteed
  - Can burst above request up to their limit
  - Use for: most production workloads
```

### 9.3 Guaranteed — Requests equal Limits

```yaml
spec:
  containers:
    - name: app
      image: nginx
      resources:
        requests:
          cpu: "500m"
          memory: "512Mi"
        limits:
          cpu: "500m"       # SAME as request
          memory: "512Mi"   # SAME as request
          # All containers, all resources must match → Guaranteed
```

```
Guaranteed pods:
  - Last to be evicted
  - Kubernetes won't over-commit their resources
  - Use for: databases, critical stateful services, payment systems
  - Trade-off: less flexible, may waste capacity if workload is light
```

### Check a pod's QoS class

```bash
kubectl describe pod web-pod | grep "QoS Class"
# QoS Class:  Guaranteed

kubectl get pod web-pod -o jsonpath='{.status.qosClass}'
# Guaranteed
```

### QoS Summary Table

| QoS Class | When Assigned | Eviction Priority |
|-----------|--------------|-------------------|
| Guaranteed | requests == limits for ALL containers, ALL resources | Last (safest) |
| Burstable | At least 1 container has requests or limits | Middle |
| BestEffort | No container has any requests or limits | First (most vulnerable) |

---

## 10. How the Scheduler Uses Requests

The scheduler uses **requests** (not limits) to decide where to place a Pod:

```
┌─────────────────────────────────────────────────────────────┐
│              Scheduler Node Selection                        │
│                                                              │
│  Pod requests: cpu=250m, memory=256Mi                        │
│                                                              │
│  Node A: allocatable=4CPU/8Gi, used=3750m CPU / 7.5Gi RAM   │
│          Free: 250m CPU / 0.5Gi RAM                          │
│          → CPU fits (250m ≤ 250m) but RAM doesn't (256Mi > 0.5Gi×0.9)  ✗ │
│                                                              │
│  Node B: allocatable=4CPU/8Gi, used=1CPU / 2Gi RAM          │
│          Free: 3CPU / 6Gi RAM → Pod fits ✓                   │
│                                                              │
│  Scheduler places Pod on Node B                              │
└─────────────────────────────────────────────────────────────┘
```

**Key point:** The scheduler doesn't know how much a pod will actually use. It only looks at **requests** as a promise of minimum need. This is why:
- Too-low requests → pod gets scheduled but may be evicted
- Too-high requests → pod can't schedule (Pending) even if nodes have capacity

---

## 11. What Happens When Limits Are Exceeded

### CPU Limit Exceeded

```
Pod tries to use more CPU than its limit:
  → Kernel throttles the container (CFS throttling)
  → Pod continues running but is SLOWER
  → No kill, no restart, no exit code
  → Visible in: kubectl top pods (high CPU) and CFS throttle metrics
```

### Memory Limit Exceeded

```
Pod tries to use more memory than its limit:
  → OOM Killer terminates the container
  → Exit code 137 (128 + SIGKILL)
  → Pod restarts (based on restartPolicy — default: Always)
  → kubectl describe pod shows: OOMKilled: true
  → Repeated OOMKills → CrashLoopBackOff
```

```bash
# Detect OOMKilled containers
kubectl describe pod web-pod
# Look for:
#   Last State: Terminated
#     Reason: OOMKilled
#     Exit Code: 137

# Or check with kubectl get
kubectl get pod web-pod -o jsonpath='{.status.containerStatuses[*].lastState.terminated.reason}'
# OOMKilled
```

---

## 12. Real-World Use Cases and Patterns

### Pattern 1 — Web API (Burstable — allow spikes)

```yaml
resources:
  requests:
    cpu: "100m"       # Reserve minimal baseline
    memory: "128Mi"
  limits:
    cpu: "1000m"      # Allow bursting during traffic spikes
    memory: "256Mi"
```

### Pattern 2 — Database (Guaranteed — predictable, no eviction)

```yaml
resources:
  requests:
    cpu: "2"
    memory: "4Gi"
  limits:
    cpu: "2"          # Same as request → Guaranteed QoS
    memory: "4Gi"
```

### Pattern 3 — Batch Job (BestEffort — use whatever is available)

```yaml
resources:
  requests:
    cpu: "500m"
    memory: "512Mi"
  # No limits — use as much as available when node is idle
  # Accept that it may be evicted if memory pressure rises
```

### Pattern 4 — Sidecar (small fixed allocation)

```yaml
# Main container
- name: app
  resources:
    requests:
      cpu: "500m"
      memory: "256Mi"
    limits:
      cpu: "1000m"
      memory: "512Mi"

# Sidecar (log shipper — should be minimal)
- name: log-agent
  resources:
    requests:
      cpu: "50m"
      memory: "64Mi"
    limits:
      cpu: "100m"
      memory: "128Mi"
```

---

## 13. Common Mistakes and Pitfalls

### Mistake 1 — No requests or limits at all

```yaml
# WRONG — BestEffort, evicted first, unpredictable scheduling
spec:
  containers:
    - name: app
      image: nginx
      # No resources block
```

```
Always define at least requests for production workloads.
```

### Mistake 2 — Setting limits lower than requests

```yaml
# WRONG — Pod will never schedule
resources:
  requests:
    memory: "512Mi"    # Requests 512Mi
  limits:
    memory: "256Mi"    # Limit is less than request → invalid
```

```
Limits must always be >= requests.
Kubernetes will reject this with a validation error.
```

### Mistake 3 — Setting memory limit too low for the workload

```yaml
# Pod starts fine but OOMKills under load
resources:
  limits:
    memory: "64Mi"    # Too small for a JVM or Node.js app

# Fix: profile your app with kubectl top pods first, then set limits
```

### Mistake 4 — Forgetting that requests affect scheduling

```yaml
# requests: cpu=4 but all nodes only have 2 CPUs allocatable
# → Pod stays Pending forever even though actual usage would be < 1 CPU
resources:
  requests:
    cpu: "4000m"      # Too high — won't schedule

# Fix: Set requests to what you need, not what you might spike to
```

### Mistake 5 — Using M instead of Mi for memory

```yaml
# Using SI units (M = megabytes, decimal)
memory: "128M"    # 128,000,000 bytes

# Using IEC units (Mi = mebibytes, binary) — standard for K8s
memory: "128Mi"   # 134,217,728 bytes

# Difference is small but can cause confusion.
# Convention: always use Mi and Gi in Kubernetes.
```

### Mistake 6 — CPU throttling with too-low CPU limits

```yaml
# If app is latency-sensitive, too-low CPU limit causes jitter
resources:
  limits:
    cpu: "100m"     # App regularly needs 300m → heavily throttled

# Fix: Either raise the limit or profile and optimize the app
```

---

## 14. Interview Questions — Scenario Based

---

### Q1 — CONCEPT: What is the difference between requests and limits?

> **"Explain the difference between resource requests and limits in Kubernetes."**

**Answer:**

- **Requests**: The minimum guaranteed resources. Used by the **scheduler** at placement time to find a node with enough free capacity. Does not cap usage — the container can use more than its request if the node has spare capacity.

- **Limits**: The maximum allowed resources. Enforced at **runtime** by cgroups. CPU is throttled if exceeded; memory triggers OOMKill if exceeded.

```
requests → scheduling decision
limits   → runtime enforcement
```

The most common pattern: set requests conservatively (typical steady-state usage) and set limits a bit higher (allow bursting).

---

### Q2 — SCENARIO: Pod stuck in Pending due to resources

> **"A pod is in Pending state. `kubectl describe pod` shows: `Insufficient cpu`. What do you do?"**

**Answer:**

```bash
# Step 1: Check what the pod requests
kubectl describe pod <pod-name> | grep -A 5 Requests

# Step 2: Check node capacity
kubectl top nodes
kubectl describe node node01 | grep -A 10 "Allocated resources"

# Common causes:
# 1. Pod request > any node's free capacity → scale the cluster or lower request
# 2. All nodes are at capacity → add nodes or reduce other pods' requests
# 3. Request was set too high by mistake → edit the deployment resource spec

# Fix if request was too high:
kubectl set resources deployment/web --requests=cpu=100m,memory=128Mi
```

---

### Q3 — CONCEPT: What is OOMKilled?

> **"A pod keeps restarting with OOMKilled. What does that mean and how do you fix it?"**

**Answer:**

OOMKilled means the container exceeded its **memory limit**. The Linux OOM killer terminated the process. Exit code is **137** (SIGKILL).

```bash
# Confirm OOMKill
kubectl describe pod <pod-name>
# Last State: Terminated
#   Reason: OOMKilled
#   Exit Code: 137

# Check how much memory it's actually using
kubectl top pod <pod-name>

# Fix: increase the memory limit (or find and fix the memory leak)
kubectl set resources deployment/web --limits=memory=512Mi
```

---

### Q4 — CONCEPT: What are the three QoS classes?

> **"What are the QoS classes in Kubernetes and which is evicted first?"**

**Answer:**

1. **BestEffort** — No requests or limits defined. Evicted **first** when node is under memory pressure.
2. **Burstable** — Has some requests or limits, but they're not equal. Evicted **second**.
3. **Guaranteed** — All containers have requests == limits for all resources. Evicted **last**.

```
Eviction order: BestEffort → Burstable → Guaranteed

Use Guaranteed for: databases, payment services, critical stateful apps
Use Burstable for: most stateless web services
Use BestEffort for: non-critical batch jobs, dev/test workloads
```

---

### Q5 — SCENARIO: What happens if CPU limit is exceeded?

> **"A container's CPU usage exceeds its CPU limit. What happens?"**

**Answer:**

The container is **CPU throttled** — the kernel reduces its share of CPU cycles. The container continues running but **slower**. It is NOT killed and does NOT restart.

This is different from memory: memory cannot be "taken back" from a running process, so exceeding a memory limit causes an OOMKill (container is terminated).

```
CPU exceeded → throttled (slow but alive)
Memory exceeded → OOMKilled (terminated + restarted)
```

---

### Q6 — CONCEPT: How does LimitRange differ from ResourceQuota?

> **"What is the difference between LimitRange and ResourceQuota?"**

**Answer:**

| | LimitRange | ResourceQuota |
|---|---|---|
| Scope | Per container / per pod | Total across entire namespace |
| Sets defaults | Yes — auto-injects defaults for pods with no resources | No |
| Caps | Min/max per individual pod | Total sum of all pods |
| Use case | Prevent individual pods from being too big or too small | Enforce fair resource sharing between teams/namespaces |

```
LimitRange: "No single pod can use more than 2 CPU"
ResourceQuota: "Team Alpha cannot use more than 10 CPU total"
```

---

### Q7 — EXAM TASK: Set resource requests and limits on a Deployment

> **"Update the deployment `frontend` to set cpu request=200m, memory request=256Mi, cpu limit=500m, memory limit=512Mi."**

**Answer (exam-ready):**

```bash
# Method 1: kubectl set resources (fastest)
kubectl set resources deployment/frontend \
  --requests=cpu=200m,memory=256Mi \
  --limits=cpu=500m,memory=512Mi

# Method 2: kubectl edit
kubectl edit deployment frontend
# Find containers[].resources block and edit directly

# Verify
kubectl describe deployment frontend | grep -A 10 "Limits\|Requests"

# Check pods got the update
kubectl rollout status deployment/frontend
kubectl describe pod $(kubectl get pods -l app=frontend -o name | head -1) | grep -A 10 Resources
```

---

### Q8 — SCENARIO: Node has capacity but pod is Pending

> **"A node has 4 CPU allocatable and only 1 CPU is used. But a pod requesting 500m CPU is Pending. Why?"**

**Answer:**

The scheduler checks **requests** across all pods. Even if actual usage is 1 CPU, the total **requests** summed across all pods might already be ≥ 4 CPU.

```bash
# Check
kubectl describe node node01 | grep -A 10 "Allocated resources"
# Might show: cpu Requests=3800m/4000m (95% of allocatable already reserved)

# Even though actual usage = 1 CPU, reserved requests = 3800m
# New pod needs 500m request → 3800m + 500m = 4300m > 4000m → can't schedule
```

This is called **resource over-commitment at request level**. The scheduler uses requests as the source of truth for available capacity.

---

## Quick Summary Cheat Sheet

```
┌──────────────────────────────────────────────────────────────────┐
│                Requests & Limits Cheat Sheet                     │
├──────────────────────────────────────────────────────────────────┤
│ requests = minimum reservation (scheduler uses this)             │
│ limits   = maximum cap (enforced at runtime by cgroups)          │
├──────────────────────────────────────────────────────────────────┤
│ CPU Exceeded  → THROTTLED (slow, not killed)                     │
│ RAM Exceeded  → OOMKILLED  (exit 137, pod restarts)              │
├──────────────────────────────────────────────────────────────────┤
│ UNITS                                                            │
│  CPU:    1 = 1000m  |  250m = 0.25 core                         │
│  Memory: use Mi/Gi  |  128Mi, 512Mi, 1Gi, 2Gi                   │
├──────────────────────────────────────────────────────────────────┤
│ QoS CLASSES (eviction order — first to last)                     │
│  BestEffort  → no resources defined at all                       │
│  Burstable   → has requests/limits but they differ               │
│  Guaranteed  → requests == limits (all containers, all resources)│
├──────────────────────────────────────────────────────────────────┤
│ LimitRange   → per-container / per-pod defaults + min/max        │
│ ResourceQuota → namespace total cap (teams/projects)             │
├──────────────────────────────────────────────────────────────────┤
│ KUBECTL COMMANDS                                                  │
│ kubectl set resources deploy/X --requests=cpu=100m,memory=128Mi  │
│ kubectl set resources deploy/X --limits=cpu=500m,memory=256Mi    │
│ kubectl top pods                (requires metrics-server)        │
│ kubectl top nodes                                                │
│ kubectl describe pod X | grep -A5 "Limits\|Requests"            │
│ kubectl describe node X | grep -A10 "Allocated"                 │
│ kubectl get pod X -o jsonpath='{.status.qosClass}'              │
└──────────────────────────────────────────────────────────────────┘
```

---

*Notes by ITkannadigaru | CKA 2026 Certification*

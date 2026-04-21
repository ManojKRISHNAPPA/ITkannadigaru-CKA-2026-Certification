# PriorityClass in Kubernetes — Complete Guide

## Table of Contents
1. [What is PriorityClass?](#1-what-is-priorityclass)
2. [Why PriorityClass Exists](#2-why-priorityclass-exists)
3. [How Priority Affects Scheduling and Preemption](#3-how-priority-affects-scheduling-and-preemption)
4. [Built-in System PriorityClasses](#4-built-in-system-priorityclasses)
5. [Declarative Way — YAML Examples](#5-declarative-way--yaml-examples)
6. [Imperative Way — kubectl Commands](#6-imperative-way--kubectl-commands)
7. [Preemption — How High-Priority Pods Evict Others](#7-preemption--how-high-priority-pods-evict-others)
8. [PreemptionPolicy — Control Preemption Behaviour](#8-preemptionpolicy--control-preemption-behaviour)
9. [PriorityClass with PodDisruptionBudget](#9-priorityclass-with-poddisruptionbudget)
10. [Real-World Use Cases](#10-real-world-use-cases)
11. [Common Mistakes and Pitfalls](#11-common-mistakes-and-pitfalls)
12. [Interview Questions — Scenario Based](#12-interview-questions--scenario-based)

---

## 1. What is PriorityClass?

A **PriorityClass** is a cluster-scoped resource that assigns a **numeric priority value** to pods. Higher-priority pods are:
1. **Scheduled first** when cluster capacity is limited
2. **Not preempted** (or last to be evicted) when nodes are under pressure
3. Able to **preempt** (evict) lower-priority pods to free up space

```
PriorityClass = a named, reusable priority level for pods
                higher value = more important = scheduled first + preempts lower
```

### Where it lives

```yaml
# PriorityClass (cluster-scoped resource — no namespace)
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high-priority
value: 1000000        # Higher = more important
globalDefault: false
description: "For critical production services"
---
# Pod uses it via priorityClassName
spec:
  priorityClassName: high-priority
```

---

## 2. Why PriorityClass Exists

### The Problem Without Priority

```
Cluster is full. 3 pending pods. Only 1 pod worth of capacity will free up soon.
Which pod should the scheduler prefer?

Without priority:
  → Scheduler has no way to decide → arbitrary or first-come-first-served
  → A dev/test pod might block a critical production pod for hours

With PriorityClass:
  → Critical production pod has higher priority
  → Scheduler and preemption engine favour it → it schedules first
  → Dev pod waits (or gets evicted to make room)
```

### Real scenarios

| Scenario | Without Priority | With Priority |
|----------|-----------------|---------------|
| Cluster full, new payment-service pod pending | Waits in queue | Preempts a dev pod to schedule immediately |
| Nodes under memory pressure, evictions needed | Random eviction | Low-priority batch pods evicted first |
| Multiple pods competing for a spare slot | Arbitrary | Critical pod wins |
| Control-plane components vs user workloads | Might compete | System uses `system-cluster-critical` to always win |

---

## 3. How Priority Affects Scheduling and Preemption

### Scheduling Phase

```
┌─────────────────────────────────────────────────────────────┐
│                 Scheduler Priority Queue                     │
│                                                             │
│  Pending pods sorted by priority (highest first):           │
│                                                             │
│  1. payment-service  (priority: 1000000) ← scheduled first  │
│  2. api-server       (priority: 500000)                     │
│  3. batch-worker     (priority: 1000)    ← scheduled last   │
│                                                             │
│  Higher priority pods jump the queue                        │
└─────────────────────────────────────────────────────────────┘
```

### Preemption Phase

```
Cluster is FULL. High-priority pod is pending:

Step 1: Scheduler finds no suitable node for high-priority pod
Step 2: Preemption kicks in — find a node where evicting low-priority
        pods would free enough resources
Step 3: Low-priority pods are TERMINATED (gracefully, then forcefully)
Step 4: High-priority pod is scheduled on the now-freed node
Step 5: Evicted pods re-enter the pending queue with their own priority
```

```
┌────────────────────────────────────────────────────────────────────┐
│  Before preemption                                                  │
│                                                                    │
│  Node A (full):                                                    │
│    [batch-job-1: priority=100][batch-job-2: priority=100]          │
│                                                                    │
│  Pending:                                                          │
│    [payment-service: priority=1000000] ← wants 1 pod worth of CPU │
│                                                                    │
│  After preemption                                                  │
│                                                                    │
│  Node A:                                                           │
│    [payment-service: priority=1000000]                             │
│    (batch-job-1 was evicted → re-enters pending queue)             │
└────────────────────────────────────────────────────────────────────┘
```

---

## 4. Built-in System PriorityClasses

Kubernetes ships with two pre-defined system PriorityClasses that you cannot delete:

```bash
kubectl get priorityclasses
# NAME                      VALUE        GLOBAL-DEFAULT   AGE
# system-cluster-critical   2000000000   false            365d
# system-node-critical      2000001000   false            365d
```

| Name | Value | Used by |
|------|-------|---------|
| `system-cluster-critical` | 2,000,000,000 | kube-dns, metrics-server, coredns |
| `system-node-critical` | 2,000,001,000 | kube-proxy, node-problem-detector |

```
system-node-critical > system-cluster-critical > any user-defined class

These ensure Kubernetes system components are NEVER preempted by user workloads.
Max user-defined priority value: 1,000,000,000 (one billion)
Values above this are reserved for system classes.
```

---

## 5. Declarative Way — YAML Examples

### 5.1 Define PriorityClasses for a team

```yaml
# priority-classes.yaml
---
# Critical production services
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: critical-production
value: 1000000
globalDefault: false
description: "Critical production workloads — will preempt lower priority pods"
preemptionPolicy: PreemptLowerPriority   # default

---
# Standard production services
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high
value: 100000
globalDefault: false
description: "Standard production workloads"

---
# Development and staging
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: low
value: 1000
globalDefault: false
description: "Development, staging, non-critical batch workloads"

---
# Default class if no priorityClassName is set
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: default
value: 0
globalDefault: true                  # Applied to pods with no priorityClassName
description: "Default priority for all workloads without a class"
```

```bash
kubectl apply -f priority-classes.yaml
kubectl get priorityclasses
```

### 5.2 Pod using a PriorityClass

```yaml
# critical-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: payment-service
spec:
  priorityClassName: critical-production    # Reference by name
  containers:
    - name: payment
      image: payment-service:2.0
      resources:
        requests:
          cpu: "500m"
          memory: "256Mi"
        limits:
          cpu: "1"
          memory: "512Mi"
```

### 5.3 Deployment using a PriorityClass

```yaml
# deployment-priority.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: api-gateway
spec:
  replicas: 3
  selector:
    matchLabels:
      app: api-gateway
  template:
    metadata:
      labels:
        app: api-gateway
    spec:
      priorityClassName: high           # All pods in this deployment get high priority
      containers:
        - name: gateway
          image: nginx:1.25
          resources:
            requests:
              cpu: "200m"
              memory: "128Mi"
```

### 5.4 Three-tier priority setup (full example)

```yaml
# tier-1-critical.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: payment-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: payment-api
  template:
    metadata:
      labels:
        app: payment-api
    spec:
      priorityClassName: critical-production   # value: 1000000
      containers:
        - name: payment
          image: payment:1.0
---
# tier-2-standard.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-frontend
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      priorityClassName: high                  # value: 100000
      containers:
        - name: web
          image: nginx:1.25
---
# tier-3-batch.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: report-generator
spec:
  replicas: 5
  selector:
    matchLabels:
      app: reports
  template:
    metadata:
      labels:
        app: reports
    spec:
      priorityClassName: low                   # value: 1000
      containers:
        - name: report
          image: report-gen:1.0
```

```
Preemption order if cluster runs out of space:
  1. report-generator pods evicted first (lowest priority: 1000)
  2. web-frontend pods evicted next (priority: 100000)
  3. payment-api pods evicted last (highest user priority: 1000000)
```

---

## 6. Imperative Way — kubectl Commands

PriorityClass objects are **not creatable imperatively** (`kubectl create priorityclass` does not exist). You must use YAML. However, you can inspect and manage them:

### 6.1 List PriorityClasses

```bash
kubectl get priorityclasses
kubectl get pc                        # short name

# Detailed view
kubectl describe priorityclass critical-production
kubectl describe pc critical-production
```

### 6.2 Check which pods are using which PriorityClass

```bash
# Get priority info for all pods
kubectl get pods -o custom-columns=\
"NAME:.metadata.name,\
PRIORITY:.spec.priority,\
PC:.spec.priorityClassName" \
--all-namespaces

# Check a specific pod's priority
kubectl get pod payment-service -o jsonpath='{.spec.priority}'
kubectl get pod payment-service -o jsonpath='{.spec.priorityClassName}'
```

### 6.3 Set priorityClassName on an existing Deployment

```bash
# Patch a deployment to add priorityClassName
kubectl patch deployment web-frontend \
  -p '{"spec":{"template":{"spec":{"priorityClassName":"high"}}}}'

# Verify
kubectl rollout status deployment/web-frontend
kubectl get pods -l app=web -o jsonpath='{.items[*].spec.priorityClassName}'
```

### 6.4 Delete a PriorityClass

```bash
# Note: cannot delete system-cluster-critical or system-node-critical
kubectl delete priorityclass low
kubectl delete pc low
```

### 6.5 Watch preemption events

```bash
# Watch events across the cluster for preemption
kubectl get events --all-namespaces --watch | grep -i preempt

# Check events on a specific pod (shows if it was preempted)
kubectl describe pod <pod-name> | grep -A 10 Events

# Look for:
# Preempted: by kube-system/critical-pod on node node01
```

---

## 7. Preemption — How High-Priority Pods Evict Others

### Preemption Step-by-Step

```
1. High-priority pod P is created but no node has enough free capacity
2. Scheduler tries to find a "preemption victim" node:
   - Can evicting lower-priority pods on node N free enough resources?
   - Lower-priority = pod.spec.priority < P.spec.priority
3. Scheduler selects the node and victim pods (minimizes disruption)
4. Victims are gracefully terminated (terminationGracePeriodSeconds)
5. P is bound to the node
6. Evicted pods re-enter pending queue and may schedule elsewhere
```

### Preemption Diagram

```
┌────────────────────────────────────────────────────────────────────┐
│                                                                    │
│  Pending: [payment-svc priority=1000000]                          │
│                                                                    │
│  Node 1:                     Node 2:                              │
│  ┌──────────────────────┐    ┌──────────────────────┐             │
│  │ web-app    p=100000  │    │ report-gen  p=1000   │◄── victim   │
│  │ batch-job  p=1000    │◄── │ batch-gen   p=1000   │    node     │
│  └──────────────────────┘    └──────────────────────┘             │
│                                                                    │
│  Scheduler picks Node 2: evict report-gen + batch-gen             │
│  → payment-svc scheduled on Node 2                                │
│  → report-gen + batch-gen re-enter pending queue                  │
│                                                                    │
└────────────────────────────────────────────────────────────────────┘
```

### Rules the preemption engine follows

```
1. Only evict pods with LOWER priority than the incoming pod
2. Choose the node that requires evicting the fewest / lowest-priority pods
3. Respect PodDisruptionBudgets (PDB) — won't evict if PDB says minimum count is met
4. Give evicted pods terminationGracePeriodSeconds to shut down cleanly
5. Pending pod gets a "nominated node" annotation while waiting for evictions
```

---

## 8. PreemptionPolicy — Control Preemption Behaviour

The `preemptionPolicy` field on a PriorityClass controls whether a pod with that priority is allowed to **preempt** lower-priority pods:

| Value | Behaviour |
|-------|-----------|
| `PreemptLowerPriority` (default) | Pod can evict lower-priority pods to free space |
| `Never` | Pod gets high priority in queue but **will NOT evict** lower-priority pods |

```yaml
# High priority but won't kick out anyone
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high-no-preempt
value: 500000
preemptionPolicy: Never        # Will wait in queue, never trigger eviction
globalDefault: false
description: "High scheduling priority but non-preemptive — waits its turn"
```

### When to use `Never`

```
Use PreemptLowerPriority (default) for:
  - True critical services (payment, auth, core APIs) that must run NOW
  - Workloads where a few seconds of scheduling delay = revenue loss

Use Never for:
  - Important but not urgent — prefer sooner but can wait
  - Avoid cascading evictions in batch pipelines
  - Workloads where you want the priority queue benefit but not the disruption
```

---

## 9. PriorityClass with PodDisruptionBudget

PriorityClass works alongside **PodDisruptionBudget (PDB)** — PDBs protect pods from eviction even during preemption:

```yaml
# PDB protects the web-frontend from being fully evicted
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: web-frontend-pdb
spec:
  minAvailable: 2              # At least 2 pods must remain available
  selector:
    matchLabels:
      app: web-frontend
```

```
Preemption scenario:
  web-frontend has 3 pods and PDB minAvailable=2
  A critical pod needs space → preemption engine wants to evict web-frontend pods

  Can evict: at most 1 (3 - 2 = 1)
  If 1 evicted pod is not enough space → preemption engine looks elsewhere
```

```
PDB + PriorityClass = balanced protection
  PriorityClass: "This pod is critical and should preempt lower pods"
  PDB: "But you can only evict down to N replicas of this lower-priority deployment"
```

---

## 10. Real-World Use Cases

### Use Case 1 — Multi-tenant cluster with SLA tiers

```
Tier 1 (Gold):    payment, auth, order-service    → priority: 1000000
Tier 2 (Silver):  frontend, notification, search  → priority: 100000
Tier 3 (Bronze):  reporting, analytics, batch     → priority: 10000
Dev/Test:         all development workloads        → priority: 100
```

```yaml
# When cluster fills up → Bronze pods evicted first
# → Gold tier always has capacity reserved via preemption
```

### Use Case 2 — Cluster Autoscaler alignment

PriorityClass integrates with **Cluster Autoscaler**: low-priority pods are safe to evict during scale-down, allowing the autoscaler to shrink the cluster without disrupting critical services.

```yaml
# Label batch pods for CA to evict freely
priorityClassName: low   # CA knows these are safe to evict
```

### Use Case 3 — Critical DaemonSet (must run on every node)

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: network-agent
spec:
  template:
    spec:
      priorityClassName: system-node-critical  # Never preempted
      tolerations:
        - operator: Exists
      containers:
        - name: network-agent
          image: calico/node:v3.27.0
```

### Use Case 4 — GPU workloads (priority within a scarce resource pool)

```yaml
# GPU nodes are scarce — ensure production ML inference beats research/dev
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: gpu-production
value: 900000
description: "Production ML inference — preempts GPU dev jobs"
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: gpu-research
value: 10000
description: "Research training jobs — can be preempted"
```

---

## 11. Common Mistakes and Pitfalls

### Mistake 1 — Only one PriorityClass set to globalDefault

```yaml
# WRONG — two PriorityClasses both marked globalDefault: true
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high
value: 1000000
globalDefault: true    # Can only have ONE globalDefault across the cluster
---
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: medium
value: 500000
globalDefault: true    # Kubernetes will reject this — only 1 allowed
```

```
Fix: Set globalDefault: true on exactly one PriorityClass (or none).
```

### Mistake 2 — Using system-reserved priority values

```yaml
# WRONG — value above 1 billion is reserved for system classes
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: super-critical
value: 2000000001     # Above system-cluster-critical (2000000000)
```

```
Fix: User-defined priorities must be <= 1,000,000,000.
Values above this are reserved for system-cluster-critical and system-node-critical.
```

### Mistake 3 — Forgetting that preemption causes cascading disruption

```
Creating a critical-priority Deployment that requests large resources
→ Triggers mass eviction of lower-priority pods on a full cluster
→ Those pods re-enter pending → may trigger more preemptions elsewhere

Fix: Use preemptionPolicy: Never for "high priority but can wait" workloads.
     Use PreemptLowerPriority only for truly critical, time-sensitive pods.
```

### Mistake 4 — Not pairing PriorityClass with resource requests

```yaml
# WRONG — high priority pod with no resource requests
spec:
  priorityClassName: critical-production
  containers:
    - name: app
      image: myapp
      # No resources block → BestEffort QoS despite high priority

# PriorityClass = scheduling order preference
# QoS Class = eviction resistance under memory pressure
# They are independent! A high-priority BestEffort pod is still evicted
# first under memory pressure (QoS wins for eviction, priority wins for preemption).
```

```
Best practice: Always define requests/limits alongside priorityClassName.
```

### Mistake 5 — PriorityClass name typo causes pod to fail

```yaml
spec:
  priorityClassName: critcal-production   # typo: "critcal" not "critical"
```

```bash
# Pod fails to create:
# Error: no PriorityClass with name "critcal-production" was found

# Always verify
kubectl get priorityclass
```

---

## 12. Interview Questions — Scenario Based

---

### Q1 — CONCEPT: What is PriorityClass and why use it?

> **"What is a PriorityClass in Kubernetes and when would you use it?"**

**Answer:**

A PriorityClass is a **cluster-scoped object** that assigns a **numeric priority value** to pods. Pods with higher priority:
1. Are scheduled **first** when multiple pods are pending for limited capacity
2. Can **preempt** (evict) lower-priority pods to free up resources for themselves

Use PriorityClass when:
- Running a multi-tenant cluster where different teams/services have different SLA requirements
- Critical production services (payment, auth) must always have capacity — even at the expense of batch/dev workloads
- You want to protect system components from being starved by user workloads

---

### Q2 — SCENARIO: Critical pod is pending, cluster is full

> **"Your `payment-service` pod is stuck in Pending state. The cluster is full of batch-job pods. How would you use PriorityClass to fix this?"**

**Answer:**

```bash
# Step 1: Create a high-priority PriorityClass for payment-service
cat <<EOF | kubectl apply -f -
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: critical
value: 1000000
globalDefault: false
description: "Critical production services"
EOF

# Step 2: Create a low-priority class for batch jobs
cat <<EOF | kubectl apply -f -
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: batch
value: 100
globalDefault: false
EOF

# Step 3: Add priorityClassName to payment-service Deployment
kubectl patch deployment payment-service \
  -p '{"spec":{"template":{"spec":{"priorityClassName":"critical"}}}}'

# Step 4: Add low priority to batch-job Deployment
kubectl patch deployment batch-worker \
  -p '{"spec":{"template":{"spec":{"priorityClassName":"batch"}}}}'

# Result: Kubernetes preempts batch pods → payment-service schedules
kubectl get events | grep -i preempt
```

---

### Q3 — CONCEPT: What are the built-in system PriorityClasses?

> **"Name the two built-in PriorityClasses that Kubernetes creates automatically and explain their purpose."**

**Answer:**

1. **`system-cluster-critical`** (value: 2,000,000,000)
   - Used by: CoreDNS, metrics-server, cluster-level add-ons
   - Purpose: Ensures cluster-level system pods are never preempted by user workloads

2. **`system-node-critical`** (value: 2,000,001,000)
   - Used by: kube-proxy, node-level agents
   - Purpose: Highest built-in priority — ensures node-critical pods run always

```
system-node-critical (2,000,001,000)  ← highest
system-cluster-critical (2,000,000,000)
user-defined maximum: 1,000,000,000
```

User-defined priorities must be ≤ 1,000,000,000 — cannot override system classes.

---

### Q4 — CONCEPT: How does PriorityClass affect eviction order vs scheduling?

> **"Does PriorityClass affect which pods are evicted first under memory pressure?"**

**Answer:**

**Partially yes, but QoS class is the primary eviction driver.**

```
Eviction under memory pressure:
  Primary key:   QoS Class   (BestEffort → Burstable → Guaranteed)
  Secondary key: Priority     (within the same QoS class, lower priority evicted first)
  Tertiary key:  Memory usage vs request ratio
```

So:
- A **BestEffort pod with priority=1000000** is still evicted before a **Guaranteed pod with priority=0**
- Within the same QoS class, priority breaks the tie — lower priority evicted first

**Preemption** (triggered by a pending pod needing space) is **directly driven by priority**: the preemption engine only evicts pods with strictly lower priority than the incoming pod.

```
Memory eviction: QoS class first, then priority
Preemption:      Priority is the primary (only) driver
```

---

### Q5 — CONCEPT: PreemptionPolicy — what does Never mean?

> **"What is the difference between `preemptionPolicy: PreemptLowerPriority` and `preemptionPolicy: Never`?"**

**Answer:**

Both give the pod higher scheduling queue priority. The difference is **what happens when there's no free capacity**:

- `PreemptLowerPriority` (default): Pod will **evict** lower-priority pods to free up space. Aggressive but ensures the pod runs ASAP.
- `Never`: Pod gets queue priority but will **wait** in Pending if no free capacity exists. It will NOT trigger evictions.

```
Use case for Never:
  "I want this pod to schedule sooner than default pods when capacity is available,
   but I don't want it to disrupt running lower-priority workloads."

Example: Important analytics job — should schedule before dev pods,
         but should NOT evict production batch pipelines.
```

---

### Q6 — EXAM TASK: Create a PriorityClass and use it in a Pod

> **"Create a PriorityClass named `high-priority` with value `900000`. Create a pod named `web` using image `nginx` that uses this PriorityClass."**

**Answer (exam-ready):**

```bash
# Step 1: Create PriorityClass YAML
cat <<EOF > priority.yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: high-priority
value: 900000
globalDefault: false
description: "High priority for important workloads"
EOF

kubectl apply -f priority.yaml

# Step 2: Verify it was created
kubectl get priorityclass high-priority

# Step 3: Create a Pod using it
cat <<EOF > web-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: web
spec:
  priorityClassName: high-priority
  containers:
    - name: web
      image: nginx
EOF

kubectl apply -f web-pod.yaml

# Step 4: Verify pod has the priority set
kubectl get pod web -o jsonpath='{.spec.priority}'
# 900000

kubectl get pod web -o jsonpath='{.spec.priorityClassName}'
# high-priority
```

---

### Q7 — SCENARIO: Prevent critical pods from being preempted by other critical pods

> **"You have two 'critical' services. You want both to have high scheduling priority but neither should preempt the other. How?"**

**Answer:**

Use **the same PriorityClass** for both — preemption only occurs when the incoming pod has **strictly higher** priority than the victim. Equal-priority pods do NOT preempt each other.

```yaml
# Both services use the same PriorityClass
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: production-critical
value: 1000000
preemptionPolicy: PreemptLowerPriority
```

```yaml
# service A
spec:
  priorityClassName: production-critical

# service B
spec:
  priorityClassName: production-critical
# Neither can preempt the other (same priority value)
# Both can preempt lower-priority pods
```

---

### Q8 — CONCEPT: globalDefault — what does it do?

> **"What does `globalDefault: true` mean on a PriorityClass?"**

**Answer:**

When `globalDefault: true` is set, that PriorityClass is **automatically applied to all pods that do not explicitly set a `priorityClassName`**.

```
Without globalDefault: pods with no priorityClassName get priority = 0
With globalDefault:    pods with no priorityClassName get the globalDefault's value
```

Only **one** PriorityClass can have `globalDefault: true` in a cluster.

```yaml
apiVersion: scheduling.k8s.io/v1
kind: PriorityClass
metadata:
  name: standard
value: 50000
globalDefault: true          # All pods without priorityClassName get value=50000
description: "Default priority for all workloads"
```

**Use case**: Raise the baseline priority for all user workloads above 0 (the system default), so they all beat any pods that might be created without a class.

---

## Quick Summary Cheat Sheet

```
┌──────────────────────────────────────────────────────────────────┐
│                  PriorityClass Cheat Sheet                       │
├──────────────────────────────────────────────────────────────────┤
│ WHAT:   Cluster-scoped object that gives pods a priority value   │
│ WHY:    Higher priority → scheduled first + can preempt others   │
│ SCOPE:  Cluster-scoped (no namespace)                            │
├──────────────────────────────────────────────────────────────────┤
│ KEY FIELDS                                                        │
│  value              → integer priority (higher = more important)│
│  globalDefault      → auto-apply to pods with no priorityClassName│
│  preemptionPolicy   → PreemptLowerPriority (default) or Never    │
│  description        → human-readable label                      │
├──────────────────────────────────────────────────────────────────┤
│ BUILT-IN SYSTEM CLASSES                                          │
│  system-node-critical     = 2,000,001,000 (highest)             │
│  system-cluster-critical  = 2,000,000,000                       │
│  Max user-defined value   = 1,000,000,000                        │
├──────────────────────────────────────────────────────────────────┤
│ PREEMPTION                                                       │
│  PreemptLowerPriority → evicts pods with lower priority value   │
│  Never               → waits in queue, no eviction triggered    │
│  Equal priority pods → do NOT preempt each other                │
├──────────────────────────────────────────────────────────────────┤
│ PRIORITY vs QoS (eviction under memory pressure)                │
│  Memory eviction: QoS class wins (BestEffort first)             │
│  Scheduling preemption: Priority wins (lower priority evicted)  │
├──────────────────────────────────────────────────────────────────┤
│ KUBECTL COMMANDS                                                  │
│  kubectl get priorityclass            → list all                 │
│  kubectl get pc                       → short alias              │
│  kubectl describe pc <name>           → details                  │
│  kubectl delete pc <name>             → delete (not system ones) │
│  kubectl get pod X -o jsonpath='{.spec.priority}'               │
│  kubectl get pod X -o jsonpath='{.spec.priorityClassName}'      │
│  kubectl patch deploy X -p '{"spec":{"template":{"spec":{        │
│    "priorityClassName":"high-priority"}}}}'                      │
│  kubectl get events | grep -i preempt → watch preemptions       │
├──────────────────────────────────────────────────────────────────┤
│ COMMON PATTERN (3-tier production cluster)                       │
│  critical   = 1000000  → payment, auth, order-service           │
│  high       = 100000   → frontend, API, notification            │
│  low        = 1000     → batch jobs, analytics, dev/test        │
└──────────────────────────────────────────────────────────────────┘
```

---

*Notes by ITkannadigaru | CKA 2026 Certification*

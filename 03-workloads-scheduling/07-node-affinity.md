# Node Affinity in Kubernetes — Complete Guide

## Table of Contents
1. [What is Node Affinity?](#1-what-is-node-affinity)
2. [Why Node Affinity over NodeSelector?](#2-why-node-affinity-over-nodeselector)
3. [The Two Types of Node Affinity](#3-the-two-types-of-node-affinity)
4. [Operators — The Power of Node Affinity](#4-operators--the-power-of-node-affinity)
5. [Declarative Way — YAML Examples](#5-declarative-way--yaml-examples)
6. [Imperative Way — kubectl Commands](#6-imperative-way--kubectl-commands)
7. [Combining Required + Preferred](#7-combining-required--preferred)
8. [nodeSelectorTerms — OR Between Blocks](#8-nodeselectorterms--or-between-blocks)
9. [Node Affinity vs NodeSelector — Side by Side](#9-node-affinity-vs-nodeselector--side-by-side)
10. [Real-World Use Cases](#10-real-world-use-cases)
11. [Common Mistakes and Pitfalls](#11-common-mistakes-and-pitfalls)
12. [Interview Questions — Scenario Based](#12-interview-questions--scenario-based)

---

## 1. What is Node Affinity?

**Node Affinity** is a set of rules that tells the Kubernetes scheduler **which nodes a Pod prefers or requires** to be scheduled on — based on node labels.

It is the **evolved, more powerful version of `nodeSelector`**.

```
nodeSelector  =  Basic scheduling by label (exact match, AND only)
Node Affinity =  Advanced scheduling with OR logic, soft preference,
                  and rich operators (In, NotIn, Exists, Gt, Lt...)
```

### Where it lives in a Pod spec

```yaml
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:   # HARD rule
        ...
      preferredDuringSchedulingIgnoredDuringExecution:  # SOFT rule
        ...
```

---

## 2. Why Node Affinity over NodeSelector?

### NodeSelector Limitations (the problems Node Affinity solves)

```
Problem 1:  nodeSelector only supports AND logic
            disk=ssd AND gpu=true  ✓
            disk=ssd OR disk=nvme  ✗  (impossible with nodeSelector)

Problem 2:  nodeSelector has no soft preference
            "Prefer GPU nodes, but schedule anywhere if none exist" ✗

Problem 3:  nodeSelector only supports exact equality
            "Schedule on nodes with more than 4 CPUs" ✗
            "Schedule only if key 'gpu' exists (any value)" ✗
            "Do NOT schedule on nodes labeled env=dev" ✗
```

### Node Affinity solves all of these

```
OR logic          →  operator: In   with multiple values
Soft preference   →  preferredDuringSchedulingIgnoredDuringExecution
Exists check      →  operator: Exists
Not equal         →  operator: NotIn / DoesNotExist
Greater than      →  operator: Gt / Lt
```

---

## 3. The Two Types of Node Affinity

This is the most important thing to understand and memorize for CKA.

### Type 1: `requiredDuringSchedulingIgnoredDuringExecution`

```
required  = HARD constraint — MUST match
Ignored   = Once running, node label changes are IGNORED (pod keeps running)
```

```
┌──────────────────────────────────────────────────────┐
│  requiredDuringSchedulingIgnoredDuringExecution       │
│                                                       │
│  Scheduling time:  Node MUST match the rule          │
│  If no match:      Pod stays PENDING                 │
│  After scheduled:  Label changes ignored             │
│                    Pod keeps running even if node     │
│                    label is removed                   │
└──────────────────────────────────────────────────────┘
```

**Analogy:** "I will ONLY fly business class. If no business class seat, I won't board."

### Type 2: `preferredDuringSchedulingIgnoredDuringExecution`

```
preferred = SOFT constraint — schedule here IF possible
Ignored   = Once running, node label changes are IGNORED
```

```
┌──────────────────────────────────────────────────────┐
│  preferredDuringSchedulingIgnoredDuringExecution      │
│                                                       │
│  Scheduling time:  Scheduler tries to match rule     │
│  If no match:      Pod schedules ANYWHERE            │
│                    (does NOT go Pending)              │
│  weight:           1–100, higher = stronger prefer   │
│  After scheduled:  Label changes ignored             │
└──────────────────────────────────────────────────────┘
```

**Analogy:** "I prefer a window seat. If none is available, I'll take any seat."

### Side-by-Side Comparison

```
┌────────────────────┬──────────────────┬──────────────────────┐
│                    │    required...   │    preferred...       │
├────────────────────┼──────────────────┼──────────────────────┤
│ Rule type          │   HARD           │   SOFT               │
│ No match behavior  │   Pod PENDING    │   Schedule anywhere  │
│ Has weight         │   No             │   Yes (1–100)        │
│ Use when           │ Must be on node  │ Prefer node, not    │
│                    │ type X           │ mandatory            │
└────────────────────┴──────────────────┴──────────────────────┘
```

---

## 4. Operators — The Power of Node Affinity

Operators go inside `matchExpressions`. They define HOW to compare the node label value.

| Operator        | Meaning                                      | Example                          |
|-----------------|----------------------------------------------|----------------------------------|
| `In`            | Label value is in the given list             | `disk In [ssd, nvme]`            |
| `NotIn`         | Label value is NOT in the given list         | `env NotIn [dev, staging]`       |
| `Exists`        | Label key exists (any value)                 | `gpu Exists`                     |
| `DoesNotExist`  | Label key does NOT exist on the node         | `spot DoesNotExist`              |
| `Gt`            | Label value (numeric) is greater than        | `cpu-count Gt 4`                 |
| `Lt`            | Label value (numeric) is less than           | `memory-gb Lt 32`                |

### In vs Exists vs NotIn — When to Use Which

```
Use In          →  when you know the exact allowed values
                   e.g., disk In [ssd, nvme]  (accept either)

Use Exists      →  when any value is fine, just need key to be present
                   e.g., gpu: Exists  (any gpu type is ok)

Use NotIn       →  exclude specific nodes
                   e.g., env NotIn [dev, test]  (prod + staging ok)

Use DoesNotExist→  node must NOT have this label at all
                   e.g., spot DoesNotExist  (no spot/preemptible nodes)

Use Gt / Lt     →  for numeric comparisons
                   e.g., storage-gb Gt 100  (nodes with >100 GB storage)
```

---

## 5. Declarative Way — YAML Examples

### 5.1 Required — Hard Constraint (OR logic with In)

Schedule Pod only on nodes where `disk` is `ssd` OR `nvme`:

```yaml
# node-affinity-required.yaml
apiVersion: v1
kind: Pod
metadata:
  name: fast-storage-pod
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: disk
                operator: In
                values:
                  - ssd
                  - nvme          # OR between values in the same list
  containers:
    - name: app
      image: nginx:1.25
```

### 5.2 Preferred — Soft Preference with Weight

Prefer GPU nodes (weight 80), prefer SSD nodes (weight 40). If neither — schedule anywhere:

```yaml
# node-affinity-preferred.yaml
apiVersion: v1
kind: Pod
metadata:
  name: ml-workload
spec:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 80                  # Strong preference
          preference:
            matchExpressions:
              - key: gpu
                operator: In
                values:
                  - "true"
        - weight: 40                  # Weaker preference
          preference:
            matchExpressions:
              - key: disk
                operator: In
                values:
                  - ssd
  containers:
    - name: trainer
      image: tensorflow/tensorflow:2.13.0-gpu
```

```
Scheduler scoring:
  Node A (gpu=true, disk=ssd)   → score 80 + 40 = 120  ← wins
  Node B (gpu=true, disk=hdd)   → score 80
  Node C (disk=ssd)             → score 40
  Node D (no matching labels)   → score 0   ← last resort
```

### 5.3 Exists Operator — Node Must Have the Key

Any node that has a `gpu` label (regardless of value):

```yaml
# node-affinity-exists.yaml
apiVersion: v1
kind: Pod
metadata:
  name: any-gpu-pod
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: gpu
                operator: Exists    # gpu=anything is fine, just must have the key
  containers:
    - name: gpu-app
      image: nvidia/cuda:12.0-base
```

### 5.4 NotIn Operator — Avoid Specific Nodes

Do NOT schedule on dev or staging nodes:

```yaml
# node-affinity-notin.yaml
apiVersion: v1
kind: Pod
metadata:
  name: production-pod
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: env
                operator: NotIn
                values:
                  - dev
                  - staging       # Avoid dev AND staging (schedule on anything else)
  containers:
    - name: app
      image: myapp:prod
```

### 5.5 DoesNotExist — Avoid Spot/Preemptible Nodes

Ensure Pod never lands on spot instances (nodes that lack a `spot` label):

```yaml
# node-affinity-doesnotexist.yaml
apiVersion: v1
kind: Pod
metadata:
  name: critical-service
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: spot
                operator: DoesNotExist    # Only on nodes WITHOUT a 'spot' label
  containers:
    - name: critical-app
      image: myapp:latest
```

### 5.6 Deployment with Node Affinity

Node Affinity in a Deployment applies to **all Pods** managed by it:

```yaml
# deployment-with-affinity.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-app
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
      affinity:
        nodeAffinity:
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: env
                    operator: In
                    values:
                      - production
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 70
              preference:
                matchExpressions:
                  - key: disk
                    operator: In
                    values:
                      - ssd
      containers:
        - name: web
          image: nginx:1.25
```

```
This Deployment:
  MUST schedule on env=production nodes  (hard rule)
  PREFERS ssd nodes within production    (soft preference, weight 70)
```

### 5.7 Gt / Lt Operators — Numeric Comparisons

Schedule only on nodes with more than 4 CPU cores (custom label):

```yaml
# node-affinity-gt.yaml
apiVersion: v1
kind: Pod
metadata:
  name: cpu-hungry-pod
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: cpu-cores
                operator: Gt
                values:
                  - "4"           # Node label cpu-cores must be > 4
  containers:
    - name: compute-app
      image: myapp:latest
```

> **Note:** `Gt` and `Lt` compare string values lexicographically as integers. The node must have the label with a numeric string value e.g. `kubectl label node node01 cpu-cores=8`

---

## 6. Imperative Way — kubectl Commands

Node Affinity itself is defined only in YAML (no direct kubectl flag for it). The imperative part is **labeling nodes** and **generating/patching YAML**.

### 6.1 Label Nodes (required before affinity works)

```bash
# Add labels to nodes for affinity rules
kubectl label node node01 disk=ssd
kubectl label node node02 disk=nvme
kubectl label node node03 gpu=true
kubectl label node node04 env=production

# Label multiple nodes
kubectl label node node01 node02 disk=ssd

# Numeric label for Gt/Lt
kubectl label node node01 cpu-cores=8
kubectl label node node02 cpu-cores=2
```

### 6.2 Verify Node Labels

```bash
# Show all labels on all nodes
kubectl get nodes --show-labels

# Filter nodes matching a label
kubectl get nodes -l disk=ssd
kubectl get nodes -l env=production,disk=ssd

# Detailed view of one node's labels
kubectl describe node node01 | grep -A 10 Labels
```

### 6.3 Generate Pod YAML and Add Affinity

```bash
# Step 1: Generate base YAML
kubectl run myapp --image=nginx --dry-run=client -o yaml > pod.yaml

# Step 2: Open and manually add spec.affinity block
# (see YAML examples in section 5)

# Step 3: Apply
kubectl apply -f pod.yaml
```

### 6.4 Debug a Pending Pod

```bash
# Check events — most common cause of Pending is affinity mismatch
kubectl describe pod <pod-name>

# Look for:
# Warning  FailedScheduling  0/3 nodes are available:
#   3 node(s) didn't match Pod's node affinity/selector.

# Check if nodes have the required labels
kubectl get nodes --show-labels | grep <key>

# Check the pod's affinity rules
kubectl get pod <pod-name> -o yaml | grep -A 20 affinity
```

### 6.5 Remove a Node Label

```bash
# Remove a label (trailing dash removes the key)
kubectl label node node01 disk-

# Overwrite
kubectl label node node01 disk=nvme --overwrite
```

---

## 7. Combining Required + Preferred

You can use **both** types together in the same Pod spec. This is very common in production:

```yaml
# combined-affinity.yaml
apiVersion: v1
kind: Pod
metadata:
  name: smart-scheduled-pod
spec:
  affinity:
    nodeAffinity:

      # HARD RULE: Must be on production nodes
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: env
                operator: In
                values:
                  - production

      # SOFT RULE: Within production, prefer SSD nodes
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 90
          preference:
            matchExpressions:
              - key: disk
                operator: In
                values:
                  - ssd

  containers:
    - name: app
      image: myapp:latest
```

```
Flow:
  1. Filter all nodes → keep only env=production  (hard rule)
  2. Among those, score higher for disk=ssd        (soft rule)
  3. Schedule on highest-scored production node
```

---

## 8. nodeSelectorTerms — OR Between Blocks

`nodeSelectorTerms` is a **list**. Multiple items in this list are OR'd together.
`matchExpressions` within a single term are AND'd.

```yaml
nodeSelectorTerms:
  - matchExpressions:          # Term 1
      - key: disk
        operator: In
        values: [ssd]
      - key: env               # AND
        operator: In
        values: [production]

  - matchExpressions:          # Term 2 (OR with Term 1)
      - key: gpu
        operator: Exists
```

```
Logic:
  (disk=ssd AND env=production)  OR  (gpu exists)

Schedule the pod if:
  → Node has disk=ssd AND env=production
  OR
  → Node has any gpu label
```

### AND vs OR — Summary Table

```
Within one matchExpressions list  →  AND   (all must match)
Between nodeSelectorTerms items   →  OR    (any term can match)
Within one values list (In/NotIn) →  OR    (any value can match)
```

---

## 9. Node Affinity vs NodeSelector — Side by Side

| Feature                          | nodeSelector | Node Affinity        |
|----------------------------------|:------------:|:--------------------:|
| Hard requirement                 | Yes          | Yes (required...)    |
| Soft preference                  | No           | Yes (preferred...)   |
| OR logic between values          | No           | Yes (In operator)    |
| OR logic between rule blocks     | No           | Yes (nodeSelectorTerms) |
| NotIn / Exclude nodes            | No           | Yes                  |
| Exists / DoesNotExist            | No           | Yes                  |
| Numeric comparison (Gt, Lt)      | No           | Yes                  |
| Weight / scoring                 | No           | Yes                  |
| YAML verbosity                   | Low          | High                 |
| Ease of learning                 | Easy         | Medium               |

---

## 10. Real-World Use Cases

### Use Case 1 — ML Training (Prefer GPU, Fall Back to CPU)

```yaml
spec:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          preference:
            matchExpressions:
              - key: accelerator
                operator: In
                values: [nvidia-v100, nvidia-a100]
```
Pod runs on GPU nodes when available, CPU nodes otherwise — no Pending.

### Use Case 2 — High Availability Across Zones

```yaml
# Prefer zone-a, but fall back to zone-b or zone-c
spec:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 70
          preference:
            matchExpressions:
              - key: topology.kubernetes.io/zone
                operator: In
                values: [us-east-1a]
```

### Use Case 3 — Dedicated Nodes for Critical Workloads (Not Spot)

```yaml
# Production database must never land on spot/preemptible
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: node-lifecycle
                operator: DoesNotExist    # No spot label = on-demand only
```

### Use Case 4 — Multi-arch Cluster (amd64 + arm64)

```yaml
# App supports only amd64 — must not land on ARM nodes
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: kubernetes.io/arch
                operator: In
                values: [amd64]
```

### Use Case 5 — Dev/Staging Pods Avoid Production Nodes

```yaml
# Dev pods must NOT go on prod nodes
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: env
                operator: NotIn
                values: [production]
```

---

## 11. Common Mistakes and Pitfalls

### Mistake 1 — Mixing up required vs preferred

```yaml
# Wrong intent: "I want soft preference but I used required"
requiredDuringSchedulingIgnoredDuringExecution:
  ...

# If no matching node → Pod goes PENDING (not what you wanted)
# Fix: use preferredDuringSchedulingIgnoredDuringExecution
```

### Mistake 2 — Forgetting that preferred needs a weight field

```yaml
# WRONG — missing weight
preferredDuringSchedulingIgnoredDuringExecution:
  - preference:
      matchExpressions: ...

# CORRECT
preferredDuringSchedulingIgnoredDuringExecution:
  - weight: 80        # Required field, range 1–100
    preference:
      matchExpressions: ...
```

### Mistake 3 — OR vs AND confusion in nodeSelectorTerms

```yaml
# This is OR between the two terms (NOT AND)
nodeSelectorTerms:
  - matchExpressions:
      - key: disk
        operator: In
        values: [ssd]       # Term 1
  - matchExpressions:
      - key: gpu
        operator: Exists    # Term 2 — OR with Term 1

# Pods will schedule on nodes matching EITHER term
# If you want AND, put both in the SAME matchExpressions list
nodeSelectorTerms:
  - matchExpressions:
      - key: disk
        operator: In
        values: [ssd]
      - key: gpu            # AND — both must match
        operator: Exists
```

### Mistake 4 — Gt/Lt values must be numeric strings

```yaml
# WRONG
- key: cpu-cores
  operator: Gt
  values:
    - four        # String "four" is invalid

# CORRECT
- key: cpu-cores
  operator: Gt
  values:
    - "4"         # Must be a numeric string
```

### Mistake 5 — Node label not matching exactly

```bash
# Node labeled:
kubectl label node node01 Environment=Production   # capital E and P

# YAML has:
operator: In
values:
  - production    # lowercase — will NOT match

# Labels are case-sensitive!
```

---

## 12. Interview Questions — Scenario Based

---

### Q1 — CONCEPT: required vs preferred

> **"Explain the difference between `requiredDuringScheduling` and `preferredDuringScheduling` in Node Affinity."**

**Answer:**

- `requiredDuringSchedulingIgnoredDuringExecution` — **hard rule**. The Pod **must** schedule on a matching node. If no node matches, the Pod stays in `Pending` state. Think of it like a hard filter.

- `preferredDuringSchedulingIgnoredDuringExecution` — **soft rule**. The scheduler tries its best to place the Pod on a matching node, but if no match exists, the Pod schedules anywhere. Uses a `weight` (1–100) to score nodes.

Both types use `IgnoredDuringExecution` meaning: if a node's label changes after the Pod is running, the Pod is **not evicted**.

---

### Q2 — SCENARIO: Pod should prefer GPU nodes, but not block

> **"You want ML training Pods to run on GPU nodes when available, but they should still schedule even if no GPU nodes are free. How do you configure this?"**

**Answer:**

Use `preferredDuringSchedulingIgnoredDuringExecution` — this creates a soft preference:

```yaml
spec:
  affinity:
    nodeAffinity:
      preferredDuringSchedulingIgnoredDuringExecution:
        - weight: 100
          preference:
            matchExpressions:
              - key: gpu
                operator: In
                values:
                  - "true"
```

```bash
# Label the GPU nodes
kubectl label node gpu-node-1 gpu=true
kubectl label node gpu-node-2 gpu=true
```

The Pod will go to GPU nodes when available. When all GPU nodes are full or absent, it schedules on regular nodes — no Pending.

---

### Q3 — CONCEPT: How is Node Affinity different from nodeSelector?

> **"What can Node Affinity do that nodeSelector cannot?"**

**Answer (4 key points):**

1. **OR logic** — `In` operator with multiple values: `disk In [ssd, nvme]`
2. **Soft preference** — `preferredDuring...` with `weight` — won't cause Pending
3. **Negative matching** — `NotIn`, `DoesNotExist` to avoid specific nodes
4. **Existence check** — `Exists` operator, just check if key is present regardless of value
5. **Numeric comparison** — `Gt`, `Lt` operators for numeric label values

---

### Q4 — SCENARIO: Critical service must avoid spot nodes

> **"Your critical payment service must never run on spot/preemptible nodes (which are labeled `node-lifecycle=spot`). How do you enforce this?"**

**Answer:**

```yaml
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: node-lifecycle
                operator: NotIn
                values:
                  - spot
```

Or alternatively use `DoesNotExist` if spot nodes have no `node-lifecycle` label:

```yaml
              - key: node-lifecycle
                operator: DoesNotExist
```

**Key insight:** Use `NotIn` when you know the label exists but want to exclude specific values. Use `DoesNotExist` when the label key should be completely absent.

---

### Q5 — SCENARIO: Pod going Pending with Node Affinity set

> **"A Pod with `requiredDuringSchedulingIgnoredDuringExecution` is stuck in `Pending`. How do you debug it?"**

**Answer (step-by-step):**

```bash
# Step 1: Check events on the pod
kubectl describe pod <pod-name>
# Look for: "0/3 nodes are available: 3 node(s) didn't match..."

# Step 2: Find what affinity the pod needs
kubectl get pod <pod-name> -o yaml | grep -A 30 affinity

# Step 3: Check which nodes match
# e.g., if affinity needs  disk=ssd
kubectl get nodes -l disk=ssd

# If no output → no node has that label

# Step 4: Fix by labeling a node
kubectl label node <node-name> disk=ssd

# Step 5: Watch pod schedule
kubectl get pod <pod-name> -w
```

**Common causes:**
- Node label is missing → add it
- Label is misspelled (case-sensitive) → fix the typo
- All matching nodes are at full capacity → add nodes or reduce resource requests

---

### Q6 — CONCEPT: OR logic in Node Affinity

> **"How do you express OR logic in Node Affinity? Give an example."**

**Answer:**

Two ways to get OR logic:

**OR between values (same key):**
```yaml
matchExpressions:
  - key: disk
    operator: In
    values:
      - ssd
      - nvme    # disk=ssd OR disk=nvme
```

**OR between different conditions (nodeSelectorTerms):**
```yaml
nodeSelectorTerms:
  - matchExpressions:                    # Condition A
      - key: disk
        operator: In
        values: [ssd]
  - matchExpressions:                    # OR Condition B
      - key: gpu
        operator: Exists
# Schedules on node matching A OR B
```

---

### Q7 — SCENARIO: Deployment must run on production SSD nodes, prefer zone-a

> **"Design Node Affinity for a Deployment that: (1) MUST run on env=production nodes, (2) PREFERS disk=ssd, (3) PREFERS topology zone us-east-1a."**

**Answer:**

```yaml
spec:
  template:
    spec:
      affinity:
        nodeAffinity:

          # Hard rule — must be production
          requiredDuringSchedulingIgnoredDuringExecution:
            nodeSelectorTerms:
              - matchExpressions:
                  - key: env
                    operator: In
                    values:
                      - production

          # Soft rules — preferences within production nodes
          preferredDuringSchedulingIgnoredDuringExecution:
            - weight: 80
              preference:
                matchExpressions:
                  - key: disk
                    operator: In
                    values:
                      - ssd
            - weight: 50
              preference:
                matchExpressions:
                  - key: topology.kubernetes.io/zone
                    operator: In
                    values:
                      - us-east-1a
```

```
Scheduler scoring on production nodes:
  prod + ssd + zone-a  → 80 + 50 = 130  ← best
  prod + ssd + zone-b  → 80
  prod + hdd + zone-a  → 50
  prod + hdd + zone-b  → 0   ← least preferred, still valid
```

---

### Q8 — EXAM TASK: Node Affinity with required rule

> **"Create a Pod named `app` using image `nginx`. It must only schedule on nodes that have the label `tier=backend`. Use Node Affinity (not nodeSelector)."**

**Answer (exam-ready):**

```bash
# Step 1: Label the node
kubectl label node worker-1 tier=backend

# Step 2: Create YAML
cat <<EOF > app-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app
spec:
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
          - matchExpressions:
              - key: tier
                operator: In
                values:
                  - backend
  containers:
    - name: app
      image: nginx
EOF

# Step 3: Apply
kubectl apply -f app-pod.yaml

# Step 4: Verify
kubectl get pod app -o wide
# Should show NODE = worker-1
```

---

## Quick Summary Cheat Sheet

```
┌──────────────────────────────────────────────────────────────────┐
│                   Node Affinity Cheat Sheet                      │
├──────────────────────────────────────────────────────────────────┤
│ TWO TYPES                                                        │
│  required...  = HARD — pod PENDING if no match                  │
│  preferred... = SOFT — schedules anywhere if no match            │
│                uses weight (1–100)                               │
├──────────────────────────────────────────────────────────────────┤
│ OPERATORS                                                        │
│  In            → value in list      (OR between values)         │
│  NotIn         → value not in list  (exclusion)                 │
│  Exists        → key present        (any value ok)              │
│  DoesNotExist  → key absent         (must not have label)       │
│  Gt / Lt       → numeric compare    (needs numeric string val)  │
├──────────────────────────────────────────────────────────────────┤
│ LOGIC RULES                                                      │
│  matchExpressions items    → AND (all must match)               │
│  nodeSelectorTerms items   → OR  (any can match)                │
│  values in In/NotIn list   → OR  (any value matches)            │
├──────────────────────────────────────────────────────────────────┤
│ COMMON PATTERN                                                   │
│  required  = filter to the right node type                      │
│  preferred = tune placement within that filtered set            │
├──────────────────────────────────────────────────────────────────┤
│ DEBUG PENDING POD                                                │
│  kubectl describe pod <name>   → check Events section           │
│  kubectl get nodes --show-labels → find nodes with label        │
│  kubectl label node <node> key=value → fix missing label        │
└──────────────────────────────────────────────────────────────────┘
```

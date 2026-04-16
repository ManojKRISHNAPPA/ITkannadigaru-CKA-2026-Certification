# NodeSelector in Kubernetes — Complete Guide

## Table of Contents
1. [What is NodeSelector?](#1-what-is-nodeselector)
2. [Why NodeSelector is Important](#2-why-nodeselector-is-important)
3. [How Kubernetes Scheduling Works](#3-how-kubernetes-scheduling-works)
4. [Node Labels — The Foundation](#4-node-labels--the-foundation)
5. [Declarative Way — YAML Manifests](#5-declarative-way--yaml-manifests)
6. [Imperative Way — kubectl Commands](#6-imperative-way--kubectl-commands)
7. [NodeSelector vs Other Scheduling Methods](#7-nodeselector-vs-other-scheduling-methods)
8. [Limitations of NodeSelector](#8-limitations-of-nodeselector)
9. [Real-World Use Cases](#9-real-world-use-cases)
10. [Common Mistakes and Pitfalls](#10-common-mistakes-and-pitfalls)
11. [Interview Questions — Scenario Based](#11-interview-questions--scenario-based)

---

## 1. What is NodeSelector?

`nodeSelector` is the **simplest form of node scheduling constraint** in Kubernetes. It tells the scheduler to place a Pod **only on nodes that have matching labels**.

```
nodeSelector = "Schedule this Pod ONLY on nodes that have these labels"
```

### Simple Mental Model

```
┌────────────────────────────────────────────────────────────────┐
│                      Kubernetes Cluster                        │
│                                                                │
│  ┌────────────────┐    ┌────────────────┐   ┌──────────────┐  │
│  │   Node A       │    │   Node B       │   │   Node C     │  │
│  │ label:         │    │ label:         │   │ label:       │  │
│  │  disk=ssd      │    │  disk=hdd      │   │  disk=ssd    │  │
│  │  gpu=true      │    │  env=staging   │   │  env=prod    │  │
│  └───────┬────────┘    └────────────────┘   └──────┬───────┘  │
│          │                                          │          │
│   Pod with nodeSelector:                           │          │
│   disk: ssd            ──── Scheduled Here ────────┘          │
│   (matches Node A OR Node C — scheduler picks one)            │
└────────────────────────────────────────────────────────────────┘
```

---

## 2. Why NodeSelector is Important

### The Core Problem NodeSelector Solves

In a real cluster, nodes are **not identical**. You may have:

| Node Type         | Hardware/Purpose                        |
|-------------------|-----------------------------------------|
| GPU nodes         | NVIDIA/AMD GPUs for ML training         |
| SSD nodes         | Fast NVMe disks for databases           |
| High-memory nodes | 512 GB RAM for in-memory caches         |
| Spot/preemptible  | Cheap nodes for batch workloads         |
| Arm nodes         | Energy-efficient for specific binaries  |
| Zone-specific     | Nodes in us-east-1a for data locality   |

**Without NodeSelector**, the Kubernetes scheduler places Pods on any available node. This can lead to:

- A database Pod landing on a slow HDD node instead of the SSD node
- An ML training job running without GPU access
- A compliance-sensitive workload running on a node in the wrong region
- Uneven resource utilization — noisy neighbor problems

**With NodeSelector**, you guarantee Pods land on the right nodes.

### Why It Matters for CKA Exam

- NodeSelector is a **core scheduling concept** tested in CKA
- It is the **prerequisite** to understanding Node Affinity, Taints, and Tolerations
- Questions often test "why is my Pod in Pending state?" — a common answer is a bad or missing nodeSelector

---

## 3. How Kubernetes Scheduling Works

Understanding the scheduler flow makes NodeSelector click:

```
┌─────────────────────────────────────────────────────────────┐
│                   Kubernetes Scheduler Flow                  │
│                                                              │
│  New Pod Created                                             │
│       │                                                      │
│       ▼                                                      │
│  [Filtering Phase]  ← nodeSelector applied HERE             │
│   Remove all nodes that DON'T match the Pod's constraints    │
│       │                                                      │
│       ▼                                                      │
│  [Scoring Phase]                                             │
│   Rank remaining nodes by resource availability, affinity   │
│       │                                                      │
│       ▼                                                      │
│  [Binding Phase]                                             │
│   Assign Pod to the highest-scored node                      │
│       │                                                      │
│       ▼                                                      │
│  Pod scheduled → Kubelet on that node starts the container   │
└─────────────────────────────────────────────────────────────┘
```

If **no node matches** the nodeSelector, the Pod stays in `Pending` state forever (until a matching node appears or the selector is fixed).

---

## 4. Node Labels — The Foundation

NodeSelector works by **matching labels on nodes**. Before using nodeSelector, you must label your nodes.

### Built-in / Well-Known Node Labels (Auto-applied by Kubernetes)

These labels are automatically added when a node joins the cluster:

```
kubernetes.io/hostname          = node01
kubernetes.io/os               = linux
kubernetes.io/arch             = amd64
node.kubernetes.io/instance-type = m5.xlarge    (cloud providers)
topology.kubernetes.io/region  = us-east-1       (cloud providers)
topology.kubernetes.io/zone    = us-east-1a      (cloud providers)
```

### Custom Node Labels (You add these)

These must be added manually:

```
disk=ssd
gpu=true
env=production
team=data-engineering
workload-type=batch
```

---

## 5. Declarative Way — YAML Manifests

The declarative approach defines the desired state in a YAML file and applies it with `kubectl apply`.

### 5.1 Basic NodeSelector Example

```yaml
# pod-with-nodeselector.yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx-on-ssd
  labels:
    app: nginx
spec:
  nodeSelector:
    disk: ssd          # Pod will ONLY schedule on nodes labeled disk=ssd
  containers:
    - name: nginx
      image: nginx:1.25
      ports:
        - containerPort: 80
```

Apply it:
```bash
kubectl apply -f pod-with-nodeselector.yaml
```

### 5.2 Multiple Labels in NodeSelector (AND logic)

When you specify **multiple key-value pairs**, ALL labels must match (logical AND):

```yaml
# ml-training-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: ml-training
  labels:
    app: model-training
    team: data-science
spec:
  nodeSelector:
    gpu: "true"            # Node must have GPU
    disk: ssd              # AND must have SSD storage
    env: production        # AND must be a production node
  containers:
    - name: trainer
      image: tensorflow/tensorflow:2.13.0-gpu
      resources:
        limits:
          nvidia.com/gpu: "1"
```

```
nodeSelector with multiple labels:
  gpu: "true"    ─┐
  disk: ssd      ─┼─ ALL must match (AND condition)
  env: production─┘
```

### 5.3 NodeSelector in a Deployment

NodeSelector in a Deployment applies to **all Pods** managed by that Deployment:

```yaml
# database-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: postgres-db
  labels:
    app: postgres
spec:
  replicas: 3
  selector:
    matchLabels:
      app: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      nodeSelector:
        disk: ssd            # All 3 replicas go to SSD nodes only
        env: production
      containers:
        - name: postgres
          image: postgres:15
          env:
            - name: POSTGRES_DB
              value: myapp
          volumeMounts:
            - name: pgdata
              mountPath: /var/lib/postgresql/data
      volumes:
        - name: pgdata
          emptyDir: {}
```

### 5.4 NodeSelector Using Built-in Node Labels

Use pre-existing Kubernetes node labels — no manual labeling required:

```yaml
# linux-only-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: linux-app
spec:
  nodeSelector:
    kubernetes.io/os: linux           # Only Linux nodes
  containers:
    - name: app
      image: myapp:latest
```

```yaml
# zone-specific-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: zone-locked-app
spec:
  nodeSelector:
    topology.kubernetes.io/zone: us-east-1a    # Only in this AZ
  containers:
    - name: app
      image: myapp:latest
```

### 5.5 NodeSelector in a DaemonSet

DaemonSet + nodeSelector: run a Pod on **specific nodes only**, not all nodes:

```yaml
# log-collector-daemonset.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: log-collector
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: log-collector
  template:
    metadata:
      labels:
        app: log-collector
    spec:
      nodeSelector:
        workload-type: production    # Only on production nodes
      containers:
        - name: fluentd
          image: fluentd:v1.16
          volumeMounts:
            - name: varlog
              mountPath: /var/log
      volumes:
        - name: varlog
          hostPath:
            path: /var/log
```

### 5.6 NodeSelector in a StatefulSet

StatefulSets (databases, message queues) that need local SSD storage:

```yaml
# kafka-statefulset.yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: kafka
spec:
  serviceName: kafka
  replicas: 3
  selector:
    matchLabels:
      app: kafka
  template:
    metadata:
      labels:
        app: kafka
    spec:
      nodeSelector:
        disk: ssd
        kafka-node: "true"     # Dedicated Kafka nodes
      containers:
        - name: kafka
          image: confluentinc/cp-kafka:7.5.0
```

---

## 6. Imperative Way — kubectl Commands

The imperative approach uses `kubectl` commands directly — faster for quick operations and exam scenarios.

### 6.1 Label a Node (Required Before NodeSelector Works)

```bash
# Syntax
kubectl label node <node-name> <key>=<value>

# Examples
kubectl label node node01 disk=ssd
kubectl label node node02 gpu=true
kubectl label node node03 env=production
kubectl label node node-worker-1 workload-type=batch

# Label multiple nodes at once
kubectl label node node01 node02 disk=ssd
```

### 6.2 Verify Node Labels

```bash
# Show all labels on all nodes
kubectl get nodes --show-labels

# Show labels in wide format
kubectl get nodes -o wide --show-labels

# Filter nodes by a specific label
kubectl get nodes -l disk=ssd

# Filter nodes by multiple labels
kubectl get nodes -l disk=ssd,env=production

# Describe a specific node to see all details
kubectl describe node node01

# Output node labels as JSON (useful for scripting)
kubectl get node node01 -o json | jq '.metadata.labels'
```

### 6.3 Run a Pod with NodeSelector Imperatively

```bash
# kubectl run does NOT natively support --node-selector flag (as of k8s 1.29)
# The workaround: generate YAML, edit, then apply

# Step 1: Generate YAML without applying
kubectl run nginx --image=nginx --dry-run=client -o yaml > pod.yaml

# Step 2: Edit and add nodeSelector (under spec:)
# spec:
#   nodeSelector:
#     disk: ssd

# Step 3: Apply
kubectl apply -f pod.yaml
```

Or do it in one command with a patch (exam trick):

```bash
# Generate YAML, add nodeSelector inline with sed, then apply
kubectl run ssd-pod --image=nginx --dry-run=client -o yaml | \
  kubectl patch --local -f - \
  -p '{"spec":{"nodeSelector":{"disk":"ssd"}}}' \
  --dry-run=client -o yaml | kubectl apply -f -
```

### 6.4 Remove / Update a Node Label

```bash
# Remove a label from a node (note the trailing dash -)
kubectl label node node01 disk-

# Update / overwrite an existing label
kubectl label node node01 disk=nvme --overwrite
```

### 6.5 Check Why a Pod is Pending (Debugging NodeSelector)

```bash
# Check Pod status and events
kubectl describe pod <pod-name>

# Look for events like:
# Warning  FailedScheduling  0/3 nodes are available:
#          3 node(s) didn't match Pod's node affinity/selector.

# Check which nodes have the required label
kubectl get nodes -l disk=ssd

# Check the Pod's nodeSelector
kubectl get pod <pod-name> -o jsonpath='{.spec.nodeSelector}'
```

### 6.6 Quick Reference — Imperative Commands Summary

```bash
# Label node
kubectl label node <node> key=value

# Remove label from node
kubectl label node <node> key-

# Overwrite label
kubectl label node <node> key=newvalue --overwrite

# Get nodes by label
kubectl get nodes -l key=value

# Show all node labels
kubectl get nodes --show-labels

# Describe node (see all labels)
kubectl describe node <node-name>

# Check pod scheduling events
kubectl describe pod <pod-name> | grep -A 5 Events

# Get nodeSelector of a running pod
kubectl get pod <pod-name> -o jsonpath='{.spec.nodeSelector}'
```

---

## 7. NodeSelector vs Other Scheduling Methods

Understanding where NodeSelector fits in the broader picture:

```
┌──────────────────────────────────────────────────────────────────┐
│              Kubernetes Node Scheduling Mechanisms               │
│                                                                  │
│  Simple ──────────────────────────────────────── Complex        │
│                                                                  │
│  nodeSelector → Node Affinity → Taints/Tolerations → TopologySpreadConstraints │
│                                                                  │
│  nodeSelector:      "Must go to nodes with label X=Y"            │
│  Node Affinity:     "Prefer nodes with X=Y, but allow Y=Z too"  │
│  Taints/Tolerations:"Nodes REPEL pods unless pod can tolerate"   │
│  TopologySpread:    "Spread pods evenly across zones/nodes"      │
└──────────────────────────────────────────────────────────────────┘
```

| Feature                   | nodeSelector | Node Affinity | Taints/Tolerations |
|---------------------------|:------------:|:-------------:|:------------------:|
| Hard requirement          | Yes          | Yes           | Yes (NoSchedule)   |
| Soft preference           | No           | Yes           | No                 |
| Operator support (In, NotIn, Exists) | No | Yes        | No                 |
| Anti-affinity (avoid nodes)| No          | Yes           | Yes                |
| Complexity                | Low          | Medium        | High               |
| CKA exam relevance        | High         | High          | High               |

---

## 8. Limitations of NodeSelector

### 8.1 Only AND Logic — No OR

```yaml
nodeSelector:
  disk: ssd    # AND
  gpu: "true"  # AND
# You CANNOT do: disk=ssd OR disk=nvme
# For OR logic, use Node Affinity with `In` operator
```

### 8.2 No Soft/Preference Scheduling

NodeSelector is **binary** — either the Pod schedules or it stays Pending. There is no "prefer these nodes but allow others." For that, use Node Affinity's `preferredDuringSchedulingIgnoredDuringExecution`.

### 8.3 No "Not Equal" or "Does Not Have" Logic

```yaml
# You CANNOT express: "Do NOT schedule on nodes with disk=hdd"
# For that, use Node Affinity with NotIn operator or Taints
```

### 8.4 Does Not React After Scheduling

If a node label is **removed after** a Pod is already running on it, the Pod **continues running** on that node. NodeSelector only applies at **scheduling time**.

```
nodeSelector = checked at scheduling, ignored afterwards
```

---

## 9. Real-World Use Cases

### Use Case 1 — GPU Workloads (ML/AI)

```yaml
# ML training must land on GPU nodes only
spec:
  nodeSelector:
    gpu: "true"
    accelerator: nvidia-tesla-v100
```

```bash
kubectl label node gpu-node-1 gpu=true accelerator=nvidia-tesla-v100
```

### Use Case 2 — Database on SSD

```yaml
# Postgres performance requires SSD
spec:
  nodeSelector:
    disk: ssd
    iops-class: high
```

### Use Case 3 — Compliance / Data Residency

```yaml
# EU data must stay in EU region nodes
spec:
  nodeSelector:
    topology.kubernetes.io/region: eu-west-1
    data-classification: gdpr-compliant
```

### Use Case 4 — Multi-Tenant Cluster (Team Isolation)

```yaml
# Data engineering team pods go to their dedicated nodes
spec:
  nodeSelector:
    team: data-engineering
```

```bash
kubectl label node node-de-1 node-de-2 team=data-engineering
```

### Use Case 5 — Windows Workloads

```yaml
# Windows containers must run on Windows nodes
spec:
  nodeSelector:
    kubernetes.io/os: windows
```

### Use Case 6 — Cost Optimization (Spot vs On-Demand)

```yaml
# Batch jobs go to cheap spot instances
spec:
  nodeSelector:
    node-lifecycle: spot
    workload-type: batch
```

---

## 10. Common Mistakes and Pitfalls

### Mistake 1 — Labeling with wrong key-value (case-sensitive!)

```bash
# Wrong
kubectl label node node01 Disk=SSD    # capital D and S

# YAML has
nodeSelector:
  disk: ssd    # lowercase — will NEVER match!
```

Labels are **case-sensitive**. `disk=ssd` ≠ `Disk=SSD`.

### Mistake 2 — Forgetting to label nodes before deploying pods

```bash
# Applied pod.yaml first, then forgot to label the node
# Pod stays Pending until you label the node
kubectl label node node01 disk=ssd   # pod will then schedule
```

### Mistake 3 — Label typo causes Pending Pod

```bash
# Node labeled:
kubectl label node node01 evironment=prod    # typo: evironment

# Pod expects:
nodeSelector:
  environment: prod                           # correct spelling
# Pod stays Pending — labels don't match
```

**Debug habit:**
```bash
kubectl describe pod <pod-name>  # Always check Events section
```

### Mistake 4 — Removing node label while pods depend on it

```bash
kubectl label node node01 disk-   # removes disk label
# Existing pods keep running, but NEW pods with disk=ssd won't schedule
# Creates confusion — check labels before removing
```

### Mistake 5 — Confusing nodeSelector with nodeName

```yaml
# nodeName: HARDCODES to a specific node by name (bypasses scheduler entirely)
spec:
  nodeName: node01    # Only this exact node — very rigid

# nodeSelector: matches by LABEL — flexible, multiple nodes can qualify
spec:
  nodeSelector:
    disk: ssd         # Any node with this label
```

---

## 11. Interview Questions — Scenario Based

---

### Q1 — SCENARIO: Pod stuck in Pending

> **"You deploy a Pod. It stays in `Pending` state. `kubectl describe pod` shows: `0/3 nodes are available: 3 node(s) didn't match Pod's node affinity/selector.` What do you do?"**

**Answer (structured):**

1. Check the Pod's nodeSelector:
   ```bash
   kubectl get pod <pod-name> -o jsonpath='{.spec.nodeSelector}'
   ```

2. Check which nodes have the required label:
   ```bash
   kubectl get nodes -l <key>=<value>
   ```

3. If no nodes have the label, either:
   - Add the label to an appropriate node:
     ```bash
     kubectl label node <node-name> <key>=<value>
     ```
   - Or fix the nodeSelector in the YAML if it was a typo

4. Verify the Pod schedules:
   ```bash
   kubectl get pod <pod-name> -w
   ```

---

### Q2 — CONCEPT: nodeSelector vs nodeName

> **"What is the difference between `nodeSelector` and `nodeName` in a Pod spec?"**

**Answer:**

| Feature      | `nodeName`                          | `nodeSelector`                          |
|--------------|-------------------------------------|-----------------------------------------|
| Mechanism    | Hardcodes exact node name           | Matches by label key-value              |
| Scheduler    | Bypasses scheduler entirely         | Goes through the scheduler              |
| Flexibility  | Rigid — one specific node           | Flexible — any node with matching label |
| Use case     | Debugging, very specific pinning    | Production workload placement           |
| Failure mode | Pod fails if node is down/removed   | Pod reschedules to another matching node|

**Key insight:** `nodeName` bypasses the Kubernetes scheduler. `nodeSelector` works with it.

---

### Q3 — SCENARIO: New GPU nodes added, old jobs not using them

> **"Your team added 5 new GPU nodes to the cluster. Existing ML training Pods are not using these nodes. What is likely the issue and how do you fix it?"**

**Answer:**

The new GPU nodes likely don't have the required labels that the ML Pod's `nodeSelector` is matching.

Steps:
```bash
# 1. Check what labels the ML pod expects
kubectl describe pod <ml-pod> | grep -A 5 "Node-Selectors"

# 2. Check the new GPU nodes' current labels
kubectl get nodes --show-labels | grep gpu-node

# 3. Add the required labels to the new GPU nodes
kubectl label node gpu-node-1 gpu=true accelerator=nvidia-tesla-v100
kubectl label node gpu-node-2 gpu=true accelerator=nvidia-tesla-v100

# 4. Verify new pods schedule on GPU nodes
kubectl get pods -o wide
```

---

### Q4 — CONCEPT: When would you use Node Affinity over nodeSelector?

> **"When would you choose Node Affinity over nodeSelector?"**

**Answer:**

Use **Node Affinity** when you need:

1. **OR logic** — "disk=ssd OR disk=nvme"
   ```yaml
   affinity:
     nodeAffinity:
       requiredDuringSchedulingIgnoredDuringExecution:
         nodeSelectorTerms:
           - matchExpressions:
               - key: disk
                 operator: In
                 values: [ssd, nvme]    # OR between values
   ```

2. **Soft preference** — "prefer GPU nodes, but schedule anywhere if none available"
   ```yaml
   preferredDuringSchedulingIgnoredDuringExecution:
     - weight: 100
       preference:
         matchExpressions:
           - key: gpu
             operator: In
             values: ["true"]
   ```

3. **Anti-affinity** — "do NOT schedule on nodes with label X"
   ```yaml
   operator: NotIn
   ```

4. **Exists check** — "schedule on any node that has key `gpu` (regardless of value)"
   ```yaml
   operator: Exists
   ```

Use **nodeSelector** for simple, single-label hard requirements — it is simpler and easier to read.

---

### Q5 — SCENARIO: Compliance requirement for data residency

> **"Your company has a compliance requirement: EU customer data must only be processed on nodes in the `eu-west-1` region. How do you enforce this with Kubernetes?"**

**Answer:**

```bash
# Step 1: Label EU region nodes (cloud provider may auto-apply topology labels)
kubectl label node eu-node-1 eu-node-2 topology.kubernetes.io/region=eu-west-1
kubectl label node eu-node-1 eu-node-2 data-classification=gdpr

# Step 2: Use nodeSelector in all EU data Pods/Deployments
```

```yaml
spec:
  nodeSelector:
    topology.kubernetes.io/region: eu-west-1
    data-classification: gdpr
```

**Deeper answer:** For stronger enforcement, combine nodeSelector with **Taints and Tolerations** — taint the EU nodes so **only** GDPR-compliant pods can schedule on them, preventing non-GDPR pods from accidentally landing there.

---

### Q6 — SCENARIO: DaemonSet on only some nodes

> **"You want to run a log collector DaemonSet but only on nodes labeled `env=production`. How?"**

**Answer:**

A regular DaemonSet runs on ALL nodes. To restrict it, add a `nodeSelector`:

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: log-collector
spec:
  selector:
    matchLabels:
      app: log-collector
  template:
    metadata:
      labels:
        app: log-collector
    spec:
      nodeSelector:
        env: production     # Only production nodes
      containers:
        - name: fluentd
          image: fluentd:v1.16
```

```bash
# Verify it only runs on production nodes
kubectl get pods -l app=log-collector -o wide
```

---

### Q7 — CONCEPT: What happens if you remove a node label after pods are running?

> **"A Pod is running on node01 which has label `disk=ssd`. You remove that label. What happens to the running Pod?"**

**Answer:**

**Nothing immediately** — the running Pod **continues to run** on node01.

`nodeSelector` is only evaluated at **scheduling time**, not continuously. The Pod will not be evicted or restarted when the label is removed.

**However:**
- If the Pod crashes and needs to restart, it will reschedule — and now node01 doesn't have `disk=ssd`, so it might schedule elsewhere
- New Pods with that nodeSelector will not schedule on node01

This is the key difference from Node Affinity's `requiredDuringSchedulingRequiredDuringExecution` (which would evict the Pod if the node no longer matches — though this feature is still in beta in many clusters).

---

### Q8 — EXAM TASK: Label node and deploy pod

> **"Label node `worker-1` with `tier=frontend`. Deploy a Pod named `web` using image `nginx` that only runs on this node. Verify placement."**

**Answer (exam-ready commands):**

```bash
# Step 1: Label the node
kubectl label node worker-1 tier=frontend

# Step 2: Verify label
kubectl get node worker-1 --show-labels | grep tier

# Step 3: Create Pod YAML
cat <<EOF > web-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: web
spec:
  nodeSelector:
    tier: frontend
  containers:
    - name: web
      image: nginx
EOF

# Step 4: Apply
kubectl apply -f web-pod.yaml

# Step 5: Verify Pod is on worker-1
kubectl get pod web -o wide
# Should show NODE = worker-1
```

---

### Q9 — CONCEPT: nodeSelector AND logic — multiple labels

> **"Can nodeSelector match a node that has EITHER of two labels? Like disk=ssd OR disk=nvme?"**

**Answer:**

**No.** `nodeSelector` only supports **AND** logic. All key-value pairs in a `nodeSelector` block must match simultaneously on the same node.

To achieve OR logic, you must use **Node Affinity** with the `In` operator:

```yaml
affinity:
  nodeAffinity:
    requiredDuringSchedulingIgnoredDuringExecution:
      nodeSelectorTerms:
        - matchExpressions:
            - key: disk
              operator: In
              values:
                - ssd
                - nvme    # OR between values in the same list
```

---

### Q10 — DEEP DIVE: nodeSelector in multi-tenant cluster

> **"You manage a shared cluster for 3 teams: frontend, backend, and data-science. Each team has dedicated nodes. How do you use nodeSelector to ensure team isolation?"**

**Answer:**

```bash
# Step 1: Label nodes per team
kubectl label node node-fe-1 node-fe-2 team=frontend
kubectl label node node-be-1 node-be-2 team=backend
kubectl label node node-ds-1 node-ds-2 team=data-science
```

```yaml
# Frontend team deployment
spec:
  nodeSelector:
    team: frontend

# Backend team deployment
spec:
  nodeSelector:
    team: backend

# Data science team deployment
spec:
  nodeSelector:
    team: data-science
```

**Limitation of this approach:** nodeSelector alone is a SOFT isolation — it only prevents pods from going to the wrong nodes by default. If a pod has no nodeSelector, it can still land on any team's nodes.

**Stronger isolation:** Combine with **Taints and Tolerations**:
```bash
# Taint team nodes so only that team's pods can run there
kubectl taint node node-fe-1 node-fe-2 team=frontend:NoSchedule
```
Team pods add a toleration — all other pods are repelled.

---

## Quick Summary Cheat Sheet

```
┌─────────────────────────────────────────────────────────────────┐
│                   nodeSelector Cheat Sheet                      │
├─────────────────────────────────────────────────────────────────┤
│ WHAT:   Key-value pairs in spec.nodeSelector                    │
│ WHEN:   Applied at Pod scheduling time only                     │
│ LOGIC:  AND — all labels must match on a single node            │
│ FAIL:   Pod stays Pending if no matching node exists            │
├─────────────────────────────────────────────────────────────────┤
│ IMPERATIVE COMMANDS                                             │
│ Label node:    kubectl label node <node> key=value              │
│ Remove label:  kubectl label node <node> key-                   │
│ Find nodes:    kubectl get nodes -l key=value                   │
│ Debug pod:     kubectl describe pod <name> | grep -A5 Events    │
├─────────────────────────────────────────────────────────────────┤
│ DECLARATIVE (in spec:)                                          │
│   nodeSelector:                                                 │
│     disk: ssd                                                   │
│     env: production                                             │
├─────────────────────────────────────────────────────────────────┤
│ LIMITATIONS                                                     │
│ - No OR logic (use Node Affinity)                               │
│ - No soft preference (use preferredDuringScheduling)            │
│ - No anti-affinity (use NotIn operator / Taints)                │
│ - Not enforced post-scheduling (pod keeps running if label gone)│
└─────────────────────────────────────────────────────────────────┘
```

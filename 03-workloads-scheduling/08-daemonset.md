# DaemonSet in Kubernetes — Complete Guide

## Table of Contents
1. [What is a DaemonSet?](#1-what-is-a-daemonset)
2. [Why DaemonSets Exist](#2-why-daemonsets-exist)
3. [DaemonSet vs Deployment vs ReplicaSet](#3-daemonset-vs-deployment-vs-replicaset)
4. [How DaemonSet Scheduling Works](#4-how-daemonset-scheduling-works)
5. [Declarative Way — YAML Examples](#5-declarative-way--yaml-examples)
6. [Imperative Way — kubectl Commands](#6-imperative-way--kubectl-commands)
7. [DaemonSet with NodeSelector and Node Affinity](#7-daemonset-with-nodeselector-and-node-affinity)
8. [DaemonSet with Tolerations (Run on Master/Control-plane)](#8-daemonset-with-tolerations-run-on-mastercontrol-plane)
9. [Update Strategies](#9-update-strategies)
10. [DaemonSet vs Static Pods](#10-daemonset-vs-static-pods)
11. [Real-World Use Cases](#11-real-world-use-cases)
12. [Common Mistakes and Pitfalls](#12-common-mistakes-and-pitfalls)
13. [Interview Questions — Scenario Based](#13-interview-questions--scenario-based)

---

## 1. What is a DaemonSet?

A **DaemonSet** ensures that **exactly one copy of a Pod runs on every node** (or a subset of nodes) in a cluster. When new nodes are added, the DaemonSet automatically schedules a Pod on them. When nodes are removed, Pods are garbage-collected.

```
DaemonSet = "Run this Pod on EVERY node (or specific nodes)"
```

### Simple Mental Model

```
┌──────────────────────────────────────────────────────────┐
│                    Kubernetes Cluster                     │
│                                                           │
│  ┌──────────┐    ┌──────────┐    ┌──────────┐            │
│  │  Node 1  │    │  Node 2  │    │  Node 3  │            │
│  │          │    │          │    │          │            │
│  │ [Pod DS] │    │ [Pod DS] │    │ [Pod DS] │ ← 1 pod    │
│  │          │    │          │    │          │   per node │
│  └──────────┘    └──────────┘    └──────────┘            │
│                                                           │
│  New node added? → DaemonSet auto-schedules a Pod on it  │
│  Node removed?   → Pod is garbage collected              │
└──────────────────────────────────────────────────────────┘
```

---

## 2. Why DaemonSets Exist

### The Problem DaemonSets Solve

Some workloads must run on **every single node** in the cluster because they deal with **node-level concerns**:

| Need | Example |
|------|---------|
| Log collection from each node | Fluentd, Filebeat, Promtail |
| Node metrics collection | node-exporter (Prometheus) |
| Network plugin (CNI) | Calico, Flannel, Cilium |
| Storage daemon | Ceph OSD, GlusterFS |
| Security agent | Falco, Sysdig, CrowdStrike |
| DNS on each node | CoreDNS (sometimes) |
| GPU device plugin | NVIDIA device plugin |

**Without DaemonSets**, you'd have to manually create a Pod on every node and watch for new nodes — error-prone and operationally expensive.

**With DaemonSets**, the controller handles it automatically — even as the cluster scales up or down.

---

## 3. DaemonSet vs Deployment vs ReplicaSet

| Feature | DaemonSet | Deployment | ReplicaSet |
|---------|-----------|-----------|------------|
| Pod count | 1 per node (automatic) | Fixed replica count | Fixed replica count |
| Scaling | Scales with cluster nodes | Manual / HPA | Manual / HPA |
| Pod placement | Every node (or subset) | Any available node | Any available node |
| Rolling updates | Yes (RollingUpdate / OnDelete) | Yes | No |
| Rollback | Yes | Yes | No |
| Use case | Node-level agents | Stateless apps | Rarely used directly |
| Can run on control-plane? | Yes (with tolerations) | No (by default) | No (by default) |

```
┌─────────────────────────────────────────────────────┐
│  3 nodes, 3 replicas                                 │
│                                                      │
│  Deployment:                                         │
│  [Pod1][Pod2][Pod3] might all land on Node1          │
│  (scheduler decides placement)                       │
│                                                      │
│  DaemonSet:                                          │
│  Node1:[Pod]   Node2:[Pod]   Node3:[Pod]             │
│  Exactly 1 per node — guaranteed                     │
└─────────────────────────────────────────────────────┘
```

---

## 4. How DaemonSet Scheduling Works

### Default behavior (no nodeSelector)

When you create a DaemonSet with no scheduling constraints:
- Kubernetes schedules **1 Pod on every node** including new nodes added later
- This includes **worker nodes** and by default **skips control-plane nodes** (they have taints)

### Scheduling mechanism

```
DaemonSet controller loop:
  1. List all nodes in the cluster
  2. For each node:
     - Is there already a DaemonSet pod on this node? → skip
     - Does node match nodeSelector/affinity? → if no, skip
     - Does node have taints? → if pod has no tolerations, skip
     - Otherwise → create a Pod on that node
  3. If a node is removed → Pod is garbage collected
  4. If a new node is added → Pod is scheduled on it automatically
```

### How DaemonSet Pods bypass the scheduler

DaemonSet Pods are scheduled differently:
- Pre-Kubernetes 1.12: DaemonSet controller bypassed the kube-scheduler entirely
- Post-Kubernetes 1.12+: DaemonSet uses the default scheduler with a `nodeName` field pre-filled — gives full scheduler features (affinity, taints, resources) while still guaranteeing 1 per node

---

## 5. Declarative Way — YAML Examples

### 5.1 Minimal DaemonSet

```yaml
# daemonset-minimal.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: log-collector
  namespace: default
  labels:
    app: log-collector
spec:
  selector:
    matchLabels:
      app: log-collector          # Must match template labels
  template:
    metadata:
      labels:
        app: log-collector
    spec:
      containers:
        - name: fluentd
          image: fluentd:v1.16
```

```bash
kubectl apply -f daemonset-minimal.yaml
```

### 5.2 Full DaemonSet YAML Reference

```yaml
# daemonset-full.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: node-exporter
  namespace: monitoring
  labels:
    app: node-exporter
    component: metrics
  annotations:
    description: "Prometheus node-level metrics agent"

spec:
  selector:
    matchLabels:
      app: node-exporter

  # ── Update Strategy ─────────────────────────────────────
  updateStrategy:
    type: RollingUpdate           # RollingUpdate (default) | OnDelete
    rollingUpdate:
      maxUnavailable: 1           # Max nodes updating simultaneously

  # ── Pod Template ─────────────────────────────────────────
  template:
    metadata:
      labels:
        app: node-exporter
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "9100"

    spec:
      # ── Tolerations (to run on control-plane nodes too) ──
      tolerations:
        - key: node-role.kubernetes.io/control-plane
          operator: Exists
          effect: NoSchedule

      # ── Host Network (access node's network namespace) ───
      hostNetwork: true
      hostPID: true                # Access host's PID namespace

      containers:
        - name: node-exporter
          image: prom/node-exporter:v1.7.0
          ports:
            - containerPort: 9100
              hostPort: 9100       # Bind to node's port directly

          # ── Resource Requests and Limits ─────────────────
          resources:
            requests:
              cpu: "100m"
              memory: "64Mi"
            limits:
              cpu: "250m"
              memory: "128Mi"

          # ── Security Context ─────────────────────────────
          securityContext:
            privileged: false
            readOnlyRootFilesystem: true

          # ── Volume Mounts ─────────────────────────────────
          volumeMounts:
            - name: proc
              mountPath: /host/proc
              readOnly: true
            - name: sys
              mountPath: /host/sys
              readOnly: true

      volumes:
        - name: proc
          hostPath:
            path: /proc           # Mount host's /proc for node metrics
        - name: sys
          hostPath:
            path: /sys

      # ── Service Account ───────────────────────────────────
      serviceAccountName: node-exporter
      terminationGracePeriodSeconds: 30
```

### 5.3 Log Collector DaemonSet (Fluentd)

```yaml
# fluentd-daemonset.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: fluentd
  namespace: kube-system
  labels:
    app: fluentd
    k8s-app: fluentd-logging
spec:
  selector:
    matchLabels:
      app: fluentd
  template:
    metadata:
      labels:
        app: fluentd
    spec:
      tolerations:
        - key: node-role.kubernetes.io/control-plane
          operator: Exists
          effect: NoSchedule
      containers:
        - name: fluentd
          image: fluent/fluentd-kubernetes-daemonset:v1.16-debian-elasticsearch8-1
          env:
            - name: FLUENT_ELASTICSEARCH_HOST
              value: "elasticsearch-service"
            - name: FLUENT_ELASTICSEARCH_PORT
              value: "9200"
          resources:
            requests:
              cpu: "100m"
              memory: "200Mi"
            limits:
              cpu: "500m"
              memory: "500Mi"
          volumeMounts:
            - name: varlog
              mountPath: /var/log            # Container logs
            - name: varlibdockercontainers
              mountPath: /var/lib/docker/containers
              readOnly: true
      terminationGracePeriodSeconds: 30
      volumes:
        - name: varlog
          hostPath:
            path: /var/log
        - name: varlibdockercontainers
          hostPath:
            path: /var/lib/docker/containers
```

### 5.4 Network Plugin DaemonSet (Calico style)

```yaml
# calico-node-daemonset.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: calico-node
  namespace: kube-system
spec:
  selector:
    matchLabels:
      k8s-app: calico-node
  template:
    metadata:
      labels:
        k8s-app: calico-node
    spec:
      # Network plugins must run on EVERY node including control-plane
      tolerations:
        - effect: NoSchedule
          operator: Exists
        - effect: NoExecute
          operator: Exists
      hostNetwork: true            # Must use host's network namespace
      priorityClassName: system-node-critical  # Highest priority
      containers:
        - name: calico-node
          image: calico/node:v3.27.0
          env:
            - name: DATASTORE_TYPE
              value: "kubernetes"
          securityContext:
            privileged: true       # CNI needs privileged access
          volumeMounts:
            - mountPath: /lib/modules
              name: lib-modules
              readOnly: true
            - mountPath: /run/xtables.lock
              name: xtables-lock
      volumes:
        - name: lib-modules
          hostPath:
            path: /lib/modules
        - name: xtables-lock
          hostPath:
            path: /run/xtables.lock
            type: FileOrCreate
```

---

## 6. Imperative Way — kubectl Commands

There is **no direct `kubectl create daemonset` command** (unlike Deployments). The common patterns are:

### 6.1 Generate DaemonSet YAML from a Deployment (fastest method)

```bash
# Step 1: Generate a Deployment YAML as a template
kubectl create deployment log-agent --image=fluentd:v1.16 \
  --dry-run=client -o yaml > daemonset.yaml

# Step 2: Edit daemonset.yaml:
#   - Change kind: Deployment → kind: DaemonSet
#   - Remove: spec.replicas
#   - Remove: spec.strategy  (DaemonSet uses updateStrategy)
#   - Keep: spec.selector and spec.template

# Step 3: Apply
kubectl apply -f daemonset.yaml
```

### 6.2 View DaemonSets

```bash
# List DaemonSets in current namespace
kubectl get daemonset
kubectl get ds                     # short name

# List across all namespaces
kubectl get ds --all-namespaces
kubectl get ds -A

# Wide output (shows images, selector)
kubectl get ds -o wide

# Detailed info
kubectl describe ds <name>
kubectl describe ds log-collector
```

### 6.3 Check which nodes have DaemonSet pods

```bash
# List pods with node placement info
kubectl get pods -l app=log-collector -o wide

# Output:
# NAME                READY   STATUS    NODE
# log-collector-abc   1/1     Running   node01
# log-collector-def   1/1     Running   node02
# log-collector-ghi   1/1     Running   node03
```

### 6.4 Verify DaemonSet Pod count

```bash
kubectl get ds
# Output:
# NAME            DESIRED   CURRENT   READY   UP-TO-DATE   AVAILABLE   NODE SELECTOR
# log-collector   3         3         3       3            3           <none>
#                 ^         ^         ^       ^            ^
#               nodes   scheduled   ready  updated     available
```

### 6.5 Update DaemonSet image (triggers rolling update)

```bash
kubectl set image daemonset/log-collector fluentd=fluentd:v1.17
kubectl rollout status daemonset/log-collector
```

### 6.6 Roll back a DaemonSet

```bash
kubectl rollout undo daemonset/log-collector
kubectl rollout history daemonset/log-collector
kubectl rollout undo daemonset/log-collector --to-revision=2
```

### 6.7 Delete a DaemonSet

```bash
# Delete DaemonSet and its Pods
kubectl delete daemonset log-collector

# Delete DaemonSet but keep Pods running (orphan them)
kubectl delete daemonset log-collector --cascade=orphan
```

---

## 7. DaemonSet with NodeSelector and Node Affinity

By default, a DaemonSet runs on ALL nodes. Use `nodeSelector` or `nodeAffinity` to restrict it to a subset.

### 7.1 NodeSelector — Run only on production nodes

```yaml
# daemonset-nodeselector.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: security-agent
spec:
  selector:
    matchLabels:
      app: security-agent
  template:
    metadata:
      labels:
        app: security-agent
    spec:
      nodeSelector:
        env: production          # Only production nodes
      containers:
        - name: agent
          image: security-agent:1.0
```

```bash
# Label production nodes first
kubectl label node node01 node02 env=production

# DaemonSet Pod runs only on node01 and node02
kubectl get pods -l app=security-agent -o wide
```

### 7.2 Node Affinity — Run on SSD or NVMe nodes

```yaml
spec:
  template:
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
                      - nvme      # OR logic — run on ssd OR nvme nodes
```

---

## 8. DaemonSet with Tolerations (Run on Master/Control-plane)

By default, control-plane nodes have a **taint** that prevents regular pods from scheduling on them:

```
node-role.kubernetes.io/control-plane:NoSchedule
```

To run a DaemonSet Pod on **every node including control-plane**, add a toleration:

### 8.1 Tolerate control-plane taint

```yaml
# daemonset-all-nodes.yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: monitoring-agent
spec:
  selector:
    matchLabels:
      app: monitoring-agent
  template:
    metadata:
      labels:
        app: monitoring-agent
    spec:
      tolerations:
        # Tolerate control-plane taint (K8s 1.24+)
        - key: node-role.kubernetes.io/control-plane
          operator: Exists
          effect: NoSchedule
        # Also tolerate master taint (older clusters)
        - key: node-role.kubernetes.io/master
          operator: Exists
          effect: NoSchedule
      containers:
        - name: agent
          image: monitoring-agent:1.0
```

```
With no tolerations:  Pods run on worker nodes only
With tolerations:     Pods run on ALL nodes (workers + control-plane)
```

### 8.2 Tolerate ALL taints (run anywhere)

Network plugins and critical agents often need to tolerate everything:

```yaml
tolerations:
  - operator: Exists    # Tolerate ANY taint with ANY key and ANY effect
```

```
Warning: This is very permissive.
Use for: CNI plugins, critical monitoring agents that MUST run everywhere.
```

---

## 9. Update Strategies

DaemonSets support two update strategies:

### 9.1 RollingUpdate (default)

Updates Pods on nodes one at a time (or in small batches).

```yaml
spec:
  updateStrategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1       # Max nodes whose pods are being updated at once
                              # Can be absolute (1) or percent (10%)
```

```
Before: Node1:[v1]  Node2:[v1]  Node3:[v1]
Step 1: Node1:[v2]  Node2:[v1]  Node3:[v1]  ← Node1 updating
Step 2: Node1:[v2]  Node2:[v2]  Node3:[v1]  ← Node2 updating
Step 3: Node1:[v2]  Node2:[v2]  Node3:[v2]  ← Done
```

### 9.2 OnDelete

Pods are only updated when you **manually delete** the old Pod. The controller then creates a new Pod with the new spec.

```yaml
spec:
  updateStrategy:
    type: OnDelete            # No automatic rollout — manual control
```

```bash
# Trigger update on a specific node manually
kubectl delete pod <daemonset-pod-name-on-node>
# DaemonSet controller creates a new pod with new spec on that node
```

```
Use OnDelete when:
- You need manual, controlled rollout node by node
- The update requires draining nodes first
- Critical system agents where auto-updates are risky
```

### Side-by-Side

| Strategy | Update Trigger | Control | Disruption |
|----------|---------------|---------|------------|
| `RollingUpdate` | Automatic on spec change | `maxUnavailable` | Minimal |
| `OnDelete` | Manual (delete pod) | Fully manual | User-controlled |

---

## 10. DaemonSet vs Static Pods

Both run on every node. Key differences:

| Feature | DaemonSet | Static Pod |
|---------|-----------|------------|
| Managed by | DaemonSet controller (API server) | kubelet directly (reads from `/etc/kubernetes/manifests/`) |
| Visible via kubectl? | Yes — `kubectl get pods` shows them | Yes — but read-only (can't delete via kubectl) |
| Namespace | Any | Usually `kube-system` |
| Updates | Rolling update via controller | Edit the file in `/etc/kubernetes/manifests/` |
| Used for | Application-level node agents | Kubernetes control-plane components (etcd, kube-apiserver) |
| Depends on API server? | Yes | No — works even if API server is down |

```
kube-apiserver, etcd, kube-controller-manager, kube-scheduler
  → all Static Pods (managed by kubelet, not DaemonSet)

Fluentd, node-exporter, calico-node
  → DaemonSets (managed by API server, visible in kubectl)
```

---

## 11. Real-World Use Cases

### Use Case 1 — Prometheus Node Exporter (Metrics)

```yaml
# Collects OS-level metrics from every node
spec:
  template:
    spec:
      tolerations:
        - operator: Exists
      hostNetwork: true
      hostPID: true
      containers:
        - name: node-exporter
          image: prom/node-exporter:v1.7.0
          ports:
            - containerPort: 9100
              hostPort: 9100
```

### Use Case 2 — Log Shipper (Logging)

```yaml
# Ships container logs from /var/log on every node to Elasticsearch/Loki
spec:
  template:
    spec:
      volumes:
        - name: varlog
          hostPath:
            path: /var/log
      containers:
        - name: logshipper
          image: promtail:2.9.0
          volumeMounts:
            - name: varlog
              mountPath: /var/log
```

### Use Case 3 — CNI Plugin (Networking)

```yaml
# Must run on ALL nodes including control-plane to set up networking
spec:
  template:
    spec:
      tolerations:
        - operator: Exists    # Tolerate all taints
      hostNetwork: true
      containers:
        - name: calico-node
          image: calico/node:v3.27.0
          securityContext:
            privileged: true
```

### Use Case 4 — GPU Device Plugin (Specialized Hardware)

```yaml
# Exposes GPU resources to pods — only needed on GPU nodes
spec:
  template:
    spec:
      nodeSelector:
        accelerator: gpu    # Only on GPU-equipped nodes
      containers:
        - name: nvidia-device-plugin
          image: nvcr.io/nvidia/k8s-device-plugin:v0.14.5
          securityContext:
            privileged: true
```

---

## 12. Common Mistakes and Pitfalls

### Mistake 1 — Forgetting `spec.selector` must match template labels

```yaml
# WRONG — selector doesn't match template labels
spec:
  selector:
    matchLabels:
      app: agent           # ← this key
  template:
    metadata:
      labels:
        name: agent        # ← different key — validation error!
```

```yaml
# CORRECT
spec:
  selector:
    matchLabels:
      app: agent
  template:
    metadata:
      labels:
        app: agent         # Must match selector exactly
```

### Mistake 2 — Using `spec.replicas` in a DaemonSet

```yaml
# WRONG — DaemonSet does not have replicas field
spec:
  replicas: 3            # ← not valid for DaemonSet
  selector: ...
```

```
DaemonSet replica count = number of matching nodes
You cannot set replicas manually — it's node-driven.
```

### Mistake 3 — DaemonSet not running on control-plane

```bash
# Symptom: DaemonSet shows 2/3 nodes covered
kubectl get ds node-exporter
# DESIRED=2 but cluster has 3 nodes (1 control-plane)

# Fix: add toleration for control-plane
tolerations:
  - key: node-role.kubernetes.io/control-plane
    operator: Exists
    effect: NoSchedule
```

### Mistake 4 — Not using `hostPath` when node-level data is needed

```yaml
# WRONG — Container cannot see node's /var/log
containers:
  - name: log-agent
    image: fluentd:v1.16
    # No volumeMount — container sees its own filesystem, not the node's

# CORRECT
containers:
  - name: log-agent
    image: fluentd:v1.16
    volumeMounts:
      - name: varlog
        mountPath: /var/log
volumes:
  - name: varlog
    hostPath:
      path: /var/log      # Mount node's actual /var/log
```

### Mistake 5 — Forgetting to set `updateStrategy`

```
Default updateStrategy for DaemonSet is RollingUpdate.
If you need manual control (e.g., for CNI updates), explicitly set OnDelete.
```

---

## 13. Interview Questions — Scenario Based

---

### Q1 — CONCEPT: What is a DaemonSet and when would you use it?

> **"What is a DaemonSet and when would you use it instead of a Deployment?"**

**Answer:**

A DaemonSet ensures **exactly one Pod runs on every node** (or a selected subset). Unlike a Deployment where you specify a replica count and the scheduler spreads them arbitrarily, a DaemonSet guarantees **per-node placement**.

Use a DaemonSet when the workload is **node-level** — it needs to run on every node to collect data, configure the node, or provide networking. Examples:
- Log collectors (Fluentd, Promtail) — collect logs from every node's `/var/log`
- Metrics agents (node-exporter) — gather node OS/hardware metrics
- CNI plugins (Calico, Flannel) — configure networking on every node
- Security agents (Falco) — scan every node for threats
- Storage daemons (Ceph OSD) — need to run on every storage node

---

### Q2 — SCENARIO: DaemonSet showing fewer pods than nodes

> **"You create a DaemonSet but `kubectl get ds` shows DESIRED=2 while your cluster has 3 nodes. What is likely wrong?"**

**Answer:**

The third node is likely the control-plane node, which has a `NoSchedule` taint:

```bash
# Check node taints
kubectl describe node <control-plane-node> | grep Taint
# Taint: node-role.kubernetes.io/control-plane:NoSchedule

# Fix: Add toleration to the DaemonSet spec
tolerations:
  - key: node-role.kubernetes.io/control-plane
    operator: Exists
    effect: NoSchedule
```

Other causes:
- A `nodeSelector` is restricting the DaemonSet to labeled nodes only
- A node is cordoned: `kubectl cordon <node>` adds `node.kubernetes.io/unschedulable:NoSchedule` taint

---

### Q3 — CONCEPT: DaemonSet vs Deployment for 3-replica cluster

> **"If I create a Deployment with replicas=3 and a DaemonSet in a 3-node cluster, what is the difference in Pod placement?"**

**Answer:**

```
Deployment (replicas=3):
  All 3 pods could land on the same node, or be spread — scheduler decides.
  If a node is added → no new pod (still only 3 total).
  If a node is removed → pods reschedule elsewhere.

DaemonSet:
  Exactly 1 pod per node → 3 pods total on 3 nodes.
  If node 4 is added → DaemonSet auto-schedules a 4th pod on it.
  If a node is removed → that pod is deleted, now 2 pods total.
```

The fundamental difference: **Deployment** manages a fixed count; **DaemonSet** manages a count tied to the cluster's node count.

---

### Q4 — SCENARIO: Running log collector only on production nodes

> **"You want a Fluentd DaemonSet to run only on nodes labeled `env=production`, not staging or dev nodes. How?"**

**Answer:**

Add `nodeSelector` to the DaemonSet's pod template:

```yaml
spec:
  template:
    spec:
      nodeSelector:
        env: production    # Only run on production nodes
      containers:
        - name: fluentd
          image: fluentd:v1.16
```

```bash
# Label the production nodes
kubectl label node node01 node02 env=production

# Verify DaemonSet only runs there
kubectl get pods -l app=fluentd -o wide
```

---

### Q5 — CONCEPT: DaemonSet update strategies

> **"What are the two DaemonSet update strategies and when would you use each?"**

**Answer:**

**RollingUpdate** (default):
- Updates Pods automatically, one node at a time
- `maxUnavailable` controls how many nodes update simultaneously
- Good for: non-critical agents, log shippers, metrics collectors

**OnDelete**:
- Pods are only replaced when manually deleted
- Full control over which nodes update and when
- Good for: CNI plugins, critical security agents where uncontrolled restarts are risky

```yaml
# Rolling (automatic):
updateStrategy:
  type: RollingUpdate
  rollingUpdate:
    maxUnavailable: 1

# Manual (delete to trigger update):
updateStrategy:
  type: OnDelete
```

---

### Q6 — EXAM TASK: Create a DaemonSet

> **"Create a DaemonSet named `monitor` in the `monitoring` namespace using the image `nginx`. It should run on all nodes including control-plane."**

**Answer (exam-ready):**

```bash
# Step 1: Generate Deployment YAML as a base
kubectl create deployment monitor --image=nginx \
  --dry-run=client -o yaml > monitor-ds.yaml
```

Edit `monitor-ds.yaml`:
- Change `kind: Deployment` → `kind: DaemonSet`
- Change `namespace: default` → `namespace: monitoring`
- Remove the `replicas:` line
- Remove the `strategy:` block
- Add toleration for control-plane

```yaml
apiVersion: apps/v1
kind: DaemonSet
metadata:
  name: monitor
  namespace: monitoring
spec:
  selector:
    matchLabels:
      app: monitor
  template:
    metadata:
      labels:
        app: monitor
    spec:
      tolerations:
        - key: node-role.kubernetes.io/control-plane
          operator: Exists
          effect: NoSchedule
      containers:
        - name: monitor
          image: nginx
```

```bash
# Create namespace if needed
kubectl create namespace monitoring

# Apply
kubectl apply -f monitor-ds.yaml

# Verify — DESIRED should equal total nodes
kubectl get ds monitor -n monitoring
kubectl get pods -n monitoring -o wide
```

---

### Q7 — SCENARIO: DaemonSet vs Static Pod — which is kube-apiserver?

> **"Is kube-apiserver managed by a DaemonSet or a Static Pod? How can you tell?"**

**Answer:**

**Static Pod** — managed by kubelet directly, not the DaemonSet controller.

```bash
# Check on the control-plane node
ls /etc/kubernetes/manifests/
# kube-apiserver.yaml  kube-controller-manager.yaml
# kube-scheduler.yaml  etcd.yaml
# → All are Static Pods

# Static Pods appear in kubectl but can't be deleted:
kubectl get pod kube-apiserver-controlplane -n kube-system
# You cannot kubectl delete them — kubelet recreates them immediately
```

Key differences:
- Static Pods live in `/etc/kubernetes/manifests/` on the node
- DaemonSet Pods are managed by the API server (need API server running)
- Static Pods work even if the control-plane is down — that's why control-plane components use them

---

## Quick Summary Cheat Sheet

```
┌──────────────────────────────────────────────────────────────────┐
│                    DaemonSet Cheat Sheet                         │
├──────────────────────────────────────────────────────────────────┤
│ WHAT:   1 Pod per node (or subset of nodes)                      │
│ WHY:    Node-level workloads: logs, metrics, networking, security│
│ HOW:    Controller watches nodes, auto-schedules / removes pods  │
├──────────────────────────────────────────────────────────────────┤
│ KEY FIELDS                                                        │
│  spec.selector         → must match template labels              │
│  spec.updateStrategy   → RollingUpdate (default) or OnDelete     │
│  spec.template         → Pod spec (same as Deployment)           │
│  NO replicas field     → count = number of matching nodes        │
├──────────────────────────────────────────────────────────────────┤
│ RESTRICT TO SUBSET OF NODES                                      │
│  nodeSelector           → simple label match (AND only)         │
│  spec.affinity          → complex matching (OR, Gt, NotIn...)    │
├──────────────────────────────────────────────────────────────────┤
│ RUN ON CONTROL-PLANE (add toleration)                            │
│  - key: node-role.kubernetes.io/control-plane                    │
│    operator: Exists                                              │
│    effect: NoSchedule                                            │
├──────────────────────────────────────────────────────────────────┤
│ KUBECTL COMMANDS                                                  │
│  kubectl get ds                    → list DaemonSets             │
│  kubectl get ds -o wide            → with images                 │
│  kubectl describe ds <name>        → details + events            │
│  kubectl get pods -l app=X -o wide → check which nodes          │
│  kubectl rollout status ds/<name>  → update progress            │
│  kubectl rollout undo ds/<name>    → rollback                    │
│  kubectl set image ds/<name> c=img → trigger rolling update      │
│  kubectl delete ds <name>          → delete (and all pods)       │
├──────────────────────────────────────────────────────────────────┤
│ VS DEPLOYMENT                                                     │
│  Deployment = fixed replica count, scheduler picks nodes         │
│  DaemonSet  = 1 per node, scales with cluster                    │
├──────────────────────────────────────────────────────────────────┤
│ VS STATIC POD                                                     │
│  DaemonSet  = managed by API server (kubectl visible + editable) │
│  Static Pod = managed by kubelet (/etc/kubernetes/manifests/)    │
│               used for kube-apiserver, etcd, etc.               │
└──────────────────────────────────────────────────────────────────┘
```

---

*Notes by ITkannadigaru | CKA 2026 Certification*

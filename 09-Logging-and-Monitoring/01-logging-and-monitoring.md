# Logging & Monitoring in Kubernetes — Complete Guide

> Domain: Logging and Monitoring  
> CKA 2026 Course — [YouTube Playlist](https://www.youtube.com/playlist?list=PLaZfMOMvbDOZas6hEZ4_G-JH8FhpzmYQA)

---

## Video-Document Mapper

| Sr No | Topic |
|-------|-------|
| 1 | [Kubernetes Events](#1-kubernetes-events) |
| 2 | [Field Selectors](#2-field-selectors) |
| 3 | [Deploying Metrics Server](#3-deploying-metrics-server) |
| 4 | [Pod Lifecycle Phases](#4-pod-lifecycle-phases) |
| 5 | [Container Restart Policy](#5-container-restart-policy) |

---

## Table of Contents

1. [Kubernetes Events](#1-kubernetes-events)
2. [Field Selectors](#2-field-selectors)
3. [Deploying Metrics Server](#3-deploying-metrics-server)
4. [Pod Lifecycle Phases](#4-pod-lifecycle-phases)
5. [Container Restart Policy](#5-container-restart-policy)
6. [kubectl logs — Deep Dive](#6-kubectl-logs--deep-dive)
7. [Node-Level Logging](#7-node-level-logging)
8. [Monitoring with kubectl top](#8-monitoring-with-kubectl-top)
9. [Common Interview Questions](#9-common-interview-questions)
10. [Exam Practice Questions](#10-exam-practice-questions)

---

## 1. Kubernetes Events

Events are records of what happened to Kubernetes objects — Pod scheduled, image pulled, container started, errors, warnings.

### Viewing Events

```bash
# List all events in current namespace
kubectl get events

# List events sorted by time (most recent last)
kubectl get events --sort-by='.lastTimestamp'

# Events in all namespaces
kubectl get events -A

# Events for a specific object
kubectl describe pod my-pod        # events shown at the bottom
kubectl describe node node1        # node events

# Watch events live
kubectl get events -w

# Filter by type (Normal or Warning)
kubectl get events --field-selector type=Warning
kubectl get events --field-selector type=Normal
```

### Event Fields

```bash
# Events with useful columns
kubectl get events -o custom-columns=\
  'LAST-SEEN:.lastTimestamp,TYPE:.type,REASON:.reason,OBJECT:.involvedObject.name,MESSAGE:.message'
```

```
  KEY EVENT REASONS (common ones to know for CKA):

  Scheduled         → Pod successfully assigned to a node
  Pulling           → Image is being pulled
  Pulled            → Image pulled successfully
  Created           → Container created
  Started           → Container started
  Killing           → Container is being killed
  BackOff           → Container is in CrashLoopBackOff
  FailedScheduling  → Pod cannot be scheduled (insufficient resources, taint, etc.)
  OOMKilling        → Container killed due to out-of-memory
  Evicted           → Pod evicted (low disk/memory on node)
  NodeNotReady      → Node went NotReady
```

### Events in YAML

```bash
# Get event details as YAML
kubectl get event <event-name> -o yaml

# Sample event structure:
# apiVersion: v1
# kind: Event
# involvedObject:
#   kind: Pod
#   name: my-pod
#   namespace: default
# message: "Back-off restarting failed container"
# reason: BackOff
# type: Warning
# count: 42
# firstTimestamp: "2026-05-01T10:00:00Z"
# lastTimestamp: "2026-05-01T11:30:00Z"
```

---

## 2. Field Selectors

Field selectors filter Kubernetes resources by field values — more specific than label selectors.

### Basic Syntax

```bash
kubectl get <resource> --field-selector <field>=<value>
```

### Pod Field Selectors

```bash
# Get pods running on a specific node
kubectl get pods --field-selector spec.nodeName=node1

# Get pods in Running phase
kubectl get pods --field-selector status.phase=Running

# Get pods NOT in Running phase
kubectl get pods --field-selector status.phase!=Running

# Get pods with a specific IP
kubectl get pods --field-selector status.podIP=192.168.1.100

# Combine multiple field selectors (AND logic)
kubectl get pods \
  --field-selector status.phase=Running,spec.nodeName=node1
```

### Event Field Selectors

```bash
# Get only Warning events
kubectl get events --field-selector type=Warning

# Get events for a specific pod
kubectl get events \
  --field-selector involvedObject.name=my-pod,involvedObject.kind=Pod

# Get events from a specific reason
kubectl get events --field-selector reason=BackOff

# All events in all namespaces for a node
kubectl get events -A \
  --field-selector involvedObject.kind=Node,involvedObject.name=node1
```

### Node Field Selectors

```bash
# Nodes with a specific hostname
kubectl get nodes --field-selector metadata.name=node1

# All nodes except one
kubectl get nodes --field-selector metadata.name!=control-plane
```

---

## 3. Deploying Metrics Server

Metrics Server collects CPU and memory metrics from kubelets — required for `kubectl top` and HPA.

### Install Metrics Server

```bash
# Install from official manifests
kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml

# For kubeadm clusters (often needs --kubelet-insecure-tls)
kubectl patch deployment metrics-server \
  -n kube-system \
  --type=json \
  -p='[{"op":"add","path":"/spec/template/spec/containers/0/args/-","value":"--kubelet-insecure-tls"}]'

# Verify it's running
kubectl get pods -n kube-system | grep metrics-server
kubectl top nodes      # wait ~1 minute after install
kubectl top pods
```

### Metrics Server Architecture

```
  Each kubelet exposes metrics at: https://<node-ip>:10250/stats/summary
            │
            │ Metrics Server scrapes every 60 seconds
            ▼
  Metrics Server (pod in kube-system)
            │
            │ stores in-memory (no persistence!)
            │
  kubectl top / HPA → query Metrics Server via Metrics API
```

> **Important**: Metrics Server stores data in-memory only — no historical data. For historical metrics and dashboards, use Prometheus + Grafana.

### Verify Metrics API

```bash
# Check if metrics API is available
kubectl get apiservice v1beta1.metrics.k8s.io

# Query metrics API directly
kubectl get --raw /apis/metrics.k8s.io/v1beta1/nodes
kubectl get --raw /apis/metrics.k8s.io/v1beta1/pods
```

---

## 4. Pod Lifecycle Phases

Understanding Pod phases is critical for debugging and monitoring.

### Pod Phase Values

```
  Pending   → Pod accepted but containers not yet running
              Possible reasons:
              - Waiting for scheduling (insufficient resources)
              - Waiting for image pull
              - Init containers still running

  Running   → At least one container is running, starting, or restarting

  Succeeded → All containers exited with code 0 (for Jobs/CronJobs)

  Failed    → All containers have exited, at least one with non-zero code

  Unknown   → State cannot be determined (usually: node unreachable)
```

### Container States Within a Pod

```bash
kubectl describe pod my-pod

# Container States:
# Waiting:
#   Reason: ContainerCreating / PodInitializing / CrashLoopBackOff
# Running:
#   Started At: 2026-05-01T10:00:00Z
# Terminated:
#   Reason: Error / OOMKilled / Completed
#   Exit Code: 1
#   Started At / Finished At
```

```
  Container State → Waiting Reasons:
  
  ContainerCreating    → pulling image, setting up volumes
  PodInitializing      → init containers running
  CrashLoopBackOff     → container keeps crashing, k8s backing off restarts
  ImagePullBackOff     → can't pull the image (wrong name, no credentials)
  ErrImagePull         → first image pull failure (before backoff)
  CreateContainerError → failed to create container (bad volume, etc.)
  RunContainerError    → container exits immediately after start
```

### Debugging by Phase

```bash
# Pod stuck in Pending?
kubectl describe pod my-pod | grep -A10 "Events:"
# Look for: FailedScheduling, Insufficient cpu/memory, Taints

# Pod stuck in ContainerCreating?
kubectl describe pod my-pod | grep -A5 "Warning"
# Look for: FailedMount (bad PVC), image pull errors

# Pod in CrashLoopBackOff?
kubectl logs my-pod --previous        # ← logs from the PREVIOUS crash
kubectl describe pod my-pod           # ← check exit code

# Pod OOMKilled?
kubectl describe pod my-pod | grep -i "oom\|memory"
# Exit Code: 137 = OOMKilled
```

---

## 5. Container Restart Policy

Defines when a container should be restarted after it exits.

### Restart Policy Options

| Policy | Behavior |
|--------|----------|
| `Always` | Always restart (default for Deployments) |
| `OnFailure` | Restart only if container exits with non-zero code |
| `Never` | Never restart |

```yaml
apiVersion: v1
kind: Pod
spec:
  restartPolicy: OnFailure          # ← Pod-level setting (not container-level)
  containers:
  - name: app
    image: my-app
```

### When to Use Each Policy

```
  Always (default for most workloads):
  → Web servers, APIs, long-running services
  → Deployments, DaemonSets, StatefulSets always use "Always"

  OnFailure:
  → Jobs that should retry on failure
  → Batch processing that's idempotent
  → CronJobs

  Never:
  → Jobs that should run once only
  → Debug containers
  → One-time migration scripts
```

### Restart Backoff

Kubernetes uses exponential backoff to avoid restarting a crashing container too frequently:

```
  Restart 1: immediate
  Restart 2: 10 seconds
  Restart 3: 20 seconds
  Restart 4: 40 seconds
  Restart 5: 80 seconds
  Restart 6+: 5 minutes (max)

  If container runs for >10 minutes without crashing → backoff resets
```

```bash
# See restart count and status
kubectl get pod my-pod
# NAME       READY   STATUS             RESTARTS   AGE
# my-pod     0/1     CrashLoopBackOff   5          10m

# Get detailed restart info
kubectl describe pod my-pod | grep "Restart Count"
```

---

## 6. kubectl logs — Deep Dive

```bash
# Get logs from a pod (single container)
kubectl logs my-pod

# Logs from a specific container (multi-container pod)
kubectl logs my-pod -c container-name

# Follow logs live (-f flag)
kubectl logs my-pod -f
kubectl logs my-pod -f -c app-container

# Last N lines
kubectl logs my-pod --tail=100

# Logs since a time
kubectl logs my-pod --since=1h
kubectl logs my-pod --since=30m
kubectl logs my-pod --since-time="2026-05-01T10:00:00Z"

# Logs from a PREVIOUS container crash (CrashLoopBackOff)
kubectl logs my-pod --previous
kubectl logs my-pod -p                 # ← short form

# Logs from all pods of a deployment
kubectl logs deployment/my-deployment
kubectl logs deployment/my-deployment -f   # follow

# Logs from all pods with a label
kubectl logs -l app=nginx
kubectl logs -l app=nginx --all-containers

# Add timestamps
kubectl logs my-pod --timestamps
```

---

## 7. Node-Level Logging

Logs stored on the node itself (outside Kubernetes):

```bash
# System logs
journalctl -u kubelet                 # kubelet logs
journalctl -u containerd             # containerd logs
journalctl -u kube-apiserver         # API server (if not a static pod)

# Container logs on disk
ls /var/log/containers/               # symlinks to pod log files
ls /var/log/pods/                     # actual pod log directories

# Follow kubelet logs live
journalctl -u kubelet -f

# Kubelet logs with filtering
journalctl -u kubelet --since "1 hour ago" | grep -i error
```

---

## 8. Monitoring with kubectl top

```bash
# Node resource usage
kubectl top nodes
# NAME     CPU(cores)   CPU%   MEMORY(bytes)   MEMORY%
# node1    250m         13%    1200Mi          15%
# node2    1200m        62%    4500Mi          57%

# Pod resource usage in current namespace
kubectl top pods

# Pod usage in all namespaces
kubectl top pods -A

# Pod usage in specific namespace
kubectl top pods -n kube-system

# Sort by CPU or memory
kubectl top pods --sort-by=cpu
kubectl top pods --sort-by=memory

# Show containers within pods
kubectl top pods --containers
```

---

## 9. Common Interview Questions

**Q: How do you check why a Pod is failing?**
> 1. `kubectl get pods` — check Status and Restarts  
> 2. `kubectl describe pod <name>` — read Events section  
> 3. `kubectl logs <pod> --previous` — read crash logs  
> 4. `kubectl logs <pod> -c <container>` — for multi-container pods

**Q: What is the difference between Pod phase "Running" and "Succeeded"?**
> Running means at least one container is actively running. Succeeded means all containers exited with code 0 — typically for Jobs.

**Q: What is CrashLoopBackOff?**
> A Pod status where a container keeps crashing and Kubernetes is applying exponential backoff before restarting it again. Check logs with `kubectl logs <pod> --previous`.

**Q: What does Metrics Server provide?**
> Real-time CPU and memory metrics for nodes and pods via the Kubernetes Metrics API. Required for `kubectl top` and HPA. Does not store historical data.

**Q: How do you get events for a specific Pod?**
> `kubectl describe pod <name>` shows events at the bottom. Or `kubectl get events --field-selector involvedObject.name=<pod-name>`.

**Q: What does exit code 137 mean?**
> The container was killed by SIGKILL (signal 9). This is typically OOMKilled — the container exceeded its memory limit.

---

## 10. Exam Practice Questions

```
1. Get all events of type Warning in the current namespace.
   Answer: kubectl get events --field-selector type=Warning

2. Get logs from a CrashLoopBackOff pod (previous crash).
   Answer: kubectl logs <pod-name> --previous

3. Show CPU and memory usage for all nodes.
   Answer: kubectl top nodes

4. Get pods running on node "node2".
   Answer: kubectl get pods --field-selector spec.nodeName=node2

5. Watch events live as they occur.
   Answer: kubectl get events -w

6. Get last 50 lines of logs from container "app" in pod "my-pod".
   Answer: kubectl logs my-pod -c app --tail=50

7. Show logs from the last 30 minutes with timestamps.
   Answer: kubectl logs my-pod --since=30m --timestamps

8. Install metrics-server and verify it works.
   Answer:
   kubectl apply -f https://github.com/kubernetes-sigs/metrics-server/releases/latest/download/components.yaml
   kubectl top nodes

9. Get all events related to pod "crashed-pod".
   Answer: kubectl get events --field-selector involvedObject.name=crashed-pod

10. Get pods sorted by the number of restarts (most restarts first).
    Answer: kubectl get pods --sort-by='.status.containerStatuses[0].restartCount'
```

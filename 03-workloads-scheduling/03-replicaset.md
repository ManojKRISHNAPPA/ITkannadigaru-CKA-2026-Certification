# Complete Guide to Kubernetes ReplicaSets

## Table of Contents
1. [What is a ReplicaSet?](#1-what-is-a-replicaset)
2. [ReplicaSet vs ReplicationController](#2-replicaset-vs-replicationcontroller)
3. [ReplicaSet vs Deployment](#3-replicaset-vs-deployment)
4. [Imperative Way — Creating ReplicaSets](#4-imperative-way--creating-replicasets)
5. [Declarative Way — Creating ReplicaSets](#5-declarative-way--creating-replicasets)
6. [Full ReplicaSet YAML Reference](#6-full-replicaset-yaml-reference)
7. [How ReplicaSet Selectors Work](#7-how-replicaset-selectors-work)
8. [Scaling a ReplicaSet](#8-scaling-a-replicaset)
9. [ReplicaSet and Pod Adoption](#9-replicaset-and-pod-adoption)
10. [ReplicaSet Self-Healing Demo](#10-replicaset-self-healing-demo)
11. [ReplicaSet with Different Pod Templates](#11-replicaset-with-different-pod-templates)
12. [Useful kubectl Commands](#12-useful-kubectl-commands)
13. [Common Interview Questions](#13-common-interview-questions)

---

## 1. What is a ReplicaSet?

A **ReplicaSet** ensures that a **specified number of identical Pod replicas** are running at any given time.

```
ReplicaSet = "I want EXACTLY N copies of this Pod running. Always."
```

**What it does:**
- If a Pod crashes → ReplicaSet creates a replacement
- If there are too many Pods → ReplicaSet deletes extras
- It continuously watches the cluster state and reconciles toward the desired state

```
Desired State: replicas: 3
                    │
        ┌───────────┼───────────┐
        ▼           ▼           ▼
    ┌───────┐   ┌───────┐   ┌───────┐
    │ Pod 1 │   │ Pod 2 │   │ Pod 3 │
    │(nginx)│   │(nginx)│   │(nginx)│
    └───────┘   └───────┘   └───────┘

Pod 2 crashes →  ReplicaSet detects only 2 running →  Creates Pod 4
```

**Key characteristics:**
- Maintains desired replica count at all times
- Uses **label selectors** to identify which Pods it manages
- Replaces failed Pods automatically (self-healing)
- Supports **horizontal scaling** (up and down)
- Does NOT support rolling updates (use Deployment for that)

---

## 2. ReplicaSet vs ReplicationController

| Feature | ReplicationController (RC) | ReplicaSet (RS) |
|---------|---------------------------|-----------------|
| API version | `v1` | `apps/v1` |
| Selector type | Equality-based only | Equality + Set-based |
| Current status | Legacy (older) | Current standard |
| Use in production | Not recommended | Preferred (via Deployment) |
| Rolling update | Manual | Via Deployment |

> **ReplicationController** is the older version. **ReplicaSet** replaced it with richer selector support. You should always use ReplicaSet (or better, Deployment) in practice.

```yaml
# Old way — ReplicationController
apiVersion: v1
kind: ReplicationController
metadata:
  name: old-rc
spec:
  replicas: 3
  selector:
    app: web            # Only equality-based selector supported
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: nginx
        image: nginx
```

---

## 3. ReplicaSet vs Deployment

| Feature | ReplicaSet | Deployment |
|---------|-----------|------------|
| Pod management | ✓ Yes | ✓ Yes (via ReplicaSet) |
| Self-healing | ✓ Yes | ✓ Yes |
| Scaling | ✓ Yes | ✓ Yes |
| Rolling updates | ✗ No | ✓ Yes |
| Rollback | ✗ No | ✓ Yes |
| Update history | ✗ No | ✓ Yes |
| Pause/Resume updates | ✗ No | ✓ Yes |
| Recommended for production | Indirectly (via Deployment) | ✓ Yes |

```
Deployment
    └── manages → ReplicaSet (new)
    └── keeps   → ReplicaSet (old, for rollback)
                    └── manages → Pods
```

> **In practice**: You almost never create a ReplicaSet directly. You create a **Deployment**, which creates a ReplicaSet for you. However, understanding ReplicaSets is essential for the CKA exam.

---

## 4. Imperative Way — Creating ReplicaSets

> **Note**: There is no direct `kubectl create replicaset` command like there is for Deployments. The primary imperative method is to generate YAML using `--dry-run` and then apply it, OR use a Deployment imperatively and inspect the resulting ReplicaSet.

### 4.1 Generate ReplicaSet YAML using dry-run (most common exam approach)

```bash
# Generate a Deployment YAML and convert it to a ReplicaSet
kubectl create deployment web --image=nginx --replicas=3 --dry-run=client -o yaml
```

### 4.2 Create from generated/edited YAML

```bash
# Step 1: Generate base
kubectl create deployment web --image=nginx --replicas=3 --dry-run=client -o yaml > rs.yaml

# Step 2: Edit the file — change 'kind: Deployment' to 'kind: ReplicaSet'
#         and remove the 'strategy' section (not valid in RS)

# Step 3: Apply
kubectl apply -f rs.yaml
```

### 4.3 Imperative ReplicaSet operations (on existing RS)

```bash
# Scale replicas up
kubectl scale replicaset web-rs --replicas=5

# Scale replicas down
kubectl scale replicaset web-rs --replicas=2

# Scale to 0 (effectively stops all pods but keeps the RS)
kubectl scale replicaset web-rs --replicas=0

# Delete a ReplicaSet (and all its pods)
kubectl delete replicaset web-rs

# Delete ReplicaSet but keep pods (orphan them)
kubectl delete replicaset web-rs --cascade=orphan
```

---

## 5. Declarative Way — Creating ReplicaSets

### 5.1 Minimal ReplicaSet

```yaml
# rs-minimal.yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: web-rs
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web        # MUST match selector
    spec:
      containers:
      - name: nginx
        image: nginx:1.25
```

```bash
kubectl apply -f rs-minimal.yaml
```

### 5.2 Apply, Verify, Delete

```bash
# Create
kubectl apply -f rs-minimal.yaml

# Verify
kubectl get replicaset
kubectl get pods

# Scale by editing the file and reapplying
# Change replicas: 3 to replicas: 5 in rs-minimal.yaml
kubectl apply -f rs-minimal.yaml

# Delete RS and all its pods
kubectl delete -f rs-minimal.yaml
```

### 5.3 Edit inline (declarative update)

```bash
# Open RS in editor, change replicas value, save
kubectl edit replicaset web-rs
```

---

## 6. Full ReplicaSet YAML Reference

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: frontend-rs                  # ReplicaSet name
  namespace: default
  labels:                            # Labels ON the ReplicaSet itself
    app: guestbook
    tier: frontend
  annotations:
    description: "Frontend web server ReplicaSet"

spec:
  replicas: 3                        # Desired number of Pod replicas

  # ── Selector: which Pods this RS manages ─────────────────
  selector:
    matchLabels:                     # Equality-based
      app: web
      tier: frontend
    matchExpressions:                # Set-based (optional)
    - key: env
      operator: In
      values:
      - production
      - staging
    - key: deprecated
      operator: DoesNotExist

  # ── Pod Template: blueprint for creating new Pods ─────────
  template:
    metadata:
      labels:                        # MUST include all labels in selector
        app: web
        tier: frontend
        env: production              # Needed for matchExpressions
      annotations:
        prometheus.io/scrape: "true"
    spec:
      containers:
      - name: web-container
        image: nginx:1.25
        ports:
        - containerPort: 80
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "250m"
            memory: "256Mi"
        readinessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 10
        livenessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 10
          periodSeconds: 30

      restartPolicy: Always          # Must be Always for ReplicaSet
```

> **Critical rule**: The Pod template labels MUST satisfy the ReplicaSet's selector. If they don't match, Kubernetes will reject the ReplicaSet with a validation error.

---

## 7. How ReplicaSet Selectors Work

### The Selector-Template Relationship

```
ReplicaSet Selector: app=web
                │
                │  "Find or create Pods matching this selector"
                ▼
Pod Template Labels: app=web   ← MUST be a superset of selector
```

### What happens at each step

```
Step 1: RS created with selector {app: web} and replicas: 3
Step 2: RS queries: "How many Pods with label app=web exist?"
Step 3: Answer is 0, desired is 3 → Create 3 new Pods
Step 4: New Pods get labels from template: {app: web}
Step 5: Pods match the selector → RS counts them
Step 6: Desired = 3, Actual = 3 → No action needed
```

### Pod acquisition

```
Existing Pod (app=web)  ←── RS adopts this pod!
                              Counts toward replica count

Existing Pod (app=api)  ←── RS ignores this pod (doesn't match selector)
```

### Selector Immutability

> **Important**: The `.spec.selector` field is **immutable** after creation. You cannot change it. If you need a different selector, delete and recreate the ReplicaSet.

---

## 8. Scaling a ReplicaSet

### Method 1: Imperative scale command

```bash
kubectl scale replicaset web-rs --replicas=5
```

### Method 2: Edit the YAML and re-apply

```bash
# Edit rs.yaml: change replicas: 3 to replicas: 5
kubectl apply -f rs.yaml
```

### Method 3: kubectl edit

```bash
kubectl edit replicaset web-rs
# Change replicas field in the editor, save
```

### Method 4: kubectl patch

```bash
kubectl patch replicaset web-rs -p '{"spec":{"replicas":5}}'
```

### Method 5: Horizontal Pod Autoscaler (HPA)

```bash
# Automatically scale based on CPU usage
kubectl autoscale replicaset web-rs --min=2 --max=10 --cpu-percent=70

# View HPA
kubectl get hpa
```

```yaml
# hpa-for-rs.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-rs-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: ReplicaSet
    name: web-rs
  minReplicas: 2
  maxReplicas: 10
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

---

## 9. ReplicaSet and Pod Adoption

### Scenario: Orphaned Pod gets adopted

```bash
# Create a standalone pod with matching labels
kubectl run orphan-pod --image=nginx --labels="app=web"

# Now create a ReplicaSet with selector app=web, replicas=3
kubectl apply -f rs.yaml

# The RS will ADOPT the orphan-pod (counts as 1 of 3)
# RS will only create 2 new Pods (not 3), because orphan-pod already counts
```

### Scenario: Relabeling a Pod removes it from RS

```bash
# RS is managing 3 pods with app=web
# Relabel one pod to remove it from RS control
kubectl label pod web-rs-abc12 app=orphan --overwrite

# RS detects only 2 matching pods, creates a new one to reach replicas=3
# The relabeled pod still runs but is now unmanaged
```

### Scenario: Deleting RS without deleting Pods (orphaning)

```bash
kubectl delete replicaset web-rs --cascade=orphan
# Pods continue running, but RS is gone
# Pods are now unmanaged (orphans)

# Verify: Pods still running, RS gone
kubectl get pods
kubectl get replicaset
```

---

## 10. ReplicaSet Self-Healing Demo

```bash
# Step 1: Create a ReplicaSet with 3 replicas
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: demo-rs
spec:
  replicas: 3
  selector:
    matchLabels:
      app: demo
  template:
    metadata:
      labels:
        app: demo
    spec:
      containers:
      - name: nginx
        image: nginx:1.25
EOF

# Step 2: Verify 3 Pods running
kubectl get pods -l app=demo

# Step 3: Delete one Pod to simulate failure
kubectl delete pod <pod-name>

# Step 4: Immediately watch — RS creates a replacement
kubectl get pods -l app=demo -w

# RS automatically creates a new Pod within seconds!
```

---

## 11. ReplicaSet with Different Pod Templates

### Example 1: Python Flask app RS

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: flask-rs
  labels:
    app: flask-api
spec:
  replicas: 2
  selector:
    matchLabels:
      app: flask-api
  template:
    metadata:
      labels:
        app: flask-api
        tier: backend
    spec:
      containers:
      - name: flask-app
        image: python:3.11-slim
        command: ["python", "-m", "flask", "run", "--host=0.0.0.0"]
        env:
        - name: FLASK_APP
          value: app.py
        ports:
        - containerPort: 5000
        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "300m"
            memory: "256Mi"
```

### Example 2: Multi-environment RS

```yaml
# production-rs.yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: web-prod-rs
spec:
  replicas: 5              # More replicas for production
  selector:
    matchLabels:
      app: web
      env: production
  template:
    metadata:
      labels:
        app: web
        env: production
    spec:
      containers:
      - name: nginx
        image: nginx:1.25  # Pinned stable version
        resources:
          requests:
            cpu: "200m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
---
# development-rs.yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: web-dev-rs
spec:
  replicas: 1              # Only 1 replica for development
  selector:
    matchLabels:
      app: web
      env: development
  template:
    metadata:
      labels:
        app: web
        env: development
    spec:
      containers:
      - name: nginx
        image: nginx:latest  # Latest for dev
        resources:
          requests:
            cpu: "50m"
            memory: "64Mi"
```

### Example 3: RS with Init Container

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: app-rs
spec:
  replicas: 3
  selector:
    matchLabels:
      app: myapp
  template:
    metadata:
      labels:
        app: myapp
    spec:
      initContainers:
      - name: wait-for-db
        image: busybox
        command: ['sh', '-c', 'until nc -z db-service 5432; do sleep 2; done']
      containers:
      - name: app
        image: myapp:1.0
        ports:
        - containerPort: 8080
```

### Example 4: RS with Set-Based Selector

```yaml
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: multi-env-rs
spec:
  replicas: 4
  selector:
    matchLabels:
      app: web
    matchExpressions:
    - key: env
      operator: In
      values:
      - production
      - staging
    - key: version
      operator: Exists
  template:
    metadata:
      labels:
        app: web
        env: production    # Satisfies 'In [production, staging]'
        version: "2.0"     # Satisfies 'Exists'
    spec:
      containers:
      - name: nginx
        image: nginx:1.25
```

---

## 12. Useful kubectl Commands

```bash
# ── Create & Apply ────────────────────────────────────────
kubectl apply -f replicaset.yaml
kubectl delete -f replicaset.yaml

# ── Get ReplicaSets ───────────────────────────────────────
kubectl get replicaset                        # or rs (short name)
kubectl get rs
kubectl get rs -o wide                        # Shows selector info
kubectl get rs -o yaml                        # Full YAML
kubectl get rs -n kube-system                 # In specific namespace
kubectl get rs --all-namespaces

# ── Describe ─────────────────────────────────────────────
kubectl describe rs web-rs                    # Detailed info + events
# Shows: Replicas, Selector, Pod Template, Events

# ── Scale ────────────────────────────────────────────────
kubectl scale rs web-rs --replicas=5
kubectl scale rs web-rs --replicas=0          # Stop all pods
kubectl patch rs web-rs -p '{"spec":{"replicas":3}}'

# ── Edit ─────────────────────────────────────────────────
kubectl edit rs web-rs                        # Opens in $EDITOR

# ── Delete ───────────────────────────────────────────────
kubectl delete rs web-rs                      # Deletes RS + all pods
kubectl delete rs web-rs --cascade=orphan     # Deletes RS, keeps pods

# ── Watch Pods ───────────────────────────────────────────
kubectl get pods -l app=web -w               # Watch pods managed by RS

# ── Events ───────────────────────────────────────────────
kubectl describe rs web-rs | grep -A 10 Events

# ── Check which RS owns a Pod ────────────────────────────
kubectl get pod web-rs-abc12 -o yaml | grep ownerReferences -A 5

# ── Get Pods managed by a specific RS ────────────────────
kubectl get pods -l app=web --show-labels

# ── Check RS selector ────────────────────────────────────
kubectl get rs web-rs -o jsonpath='{.spec.selector}'
```

---

## 13. Common Interview Questions

**Q: What is the difference between a ReplicaSet and a ReplicationController?**
> Both ensure a desired number of Pod replicas. ReplicaSet is the newer version and supports set-based selectors (In, NotIn, Exists). ReplicationController only supports equality-based selectors. ReplicaSet is the current standard.

**Q: Why do we use Deployments instead of ReplicaSets directly?**
> Deployments add rolling update, rollback, and update history on top of ReplicaSets. In production, you always use Deployments, which internally manage ReplicaSets for you.

**Q: What happens when you delete a ReplicaSet?**
> By default (`--cascade=background`), deleting a ReplicaSet also deletes all Pods it owns. With `--cascade=orphan`, the RS is deleted but Pods continue running as orphans.

**Q: What happens if you manually create a Pod with labels matching a ReplicaSet's selector?**
> The ReplicaSet adopts that Pod. It counts toward the desired replica count, and the RS will create fewer new Pods. If the count exceeds desired replicas, the RS may delete the excess (including your manually created Pod).

**Q: Can you change a ReplicaSet's selector after creation?**
> No. The `.spec.selector` is **immutable**. You must delete and recreate the ReplicaSet to change its selector.

**Q: What is the difference between `replicas: 0` and deleting a ReplicaSet?**
> `replicas: 0` scales down all Pods but keeps the ReplicaSet definition alive. You can scale back up anytime. Deleting the RS removes the RS object entirely (and typically the Pods too).

**Q: What is the ownerReference in a Pod created by a ReplicaSet?**
> Kubernetes sets a `.metadata.ownerReferences` field on each Pod pointing to its ReplicaSet. This is how the RS knows which Pods it owns. The garbage collector uses this to delete Pods when the RS is deleted.

```bash
# Check ownerReference on a Pod
kubectl get pod <pod-name> -o yaml | grep -A 6 ownerReferences
```

**Q: How does a ReplicaSet know how many Pods to create?**
> It queries the API server for Pods matching its `.spec.selector`, counts them, compares to `.spec.replicas`, and creates or deletes Pods to match the desired count. This reconciliation loop runs continuously via the controller manager.

**Q: What is the restartPolicy allowed in a ReplicaSet?**
> Only `Always`. ReplicaSets are designed for long-running services. For batch jobs use `Job` (OnFailure or Never).

---

*Notes by ITkannadigaru | CKA 2026 Certification*

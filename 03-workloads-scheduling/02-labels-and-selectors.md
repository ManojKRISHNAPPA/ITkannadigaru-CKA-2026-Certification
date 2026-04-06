# Complete Guide to Kubernetes Labels and Selectors

## Table of Contents
1. [What are Labels?](#1-what-are-labels)
2. [What are Selectors?](#2-what-are-selectors)
3. [Labels — Imperative Way](#3-labels--imperative-way)
4. [Labels — Declarative Way](#4-labels--declarative-way)
5. [Label Naming Rules and Conventions](#5-label-naming-rules-and-conventions)
6. [Selector Types](#6-selector-types)
7. [Equality-Based Selectors](#7-equality-based-selectors)
8. [Set-Based Selectors](#8-set-based-selectors)
9. [Labels on Different Resources](#9-labels-on-different-resources)
10. [Annotations vs Labels](#10-annotations-vs-labels)
11. [Real-World Labeling Strategy](#11-real-world-labeling-strategy)
12. [Useful kubectl Commands](#12-useful-kubectl-commands)
13. [Common Interview Questions](#13-common-interview-questions)

---

## 1. What are Labels?

**Labels** are **key-value pairs** attached to Kubernetes objects (Pods, Nodes, Services, etc.) that are used to **identify and organize** resources.

```
Labels = Tags on your Kubernetes objects
```

- Labels are **non-unique** — many objects can have the same label
- Labels are used to **select** and **group** objects
- You can add, modify, or remove labels at any time
- Labels have **no semantic meaning** to Kubernetes itself — you define their meaning

```
┌─────────────────────────────────────┐
│   Pod: nginx-pod                    │
│   Labels:                           │
│     app: web          ← key: value  │
│     env: production   ← key: value  │
│     tier: frontend    ← key: value  │
│     version: "1.0"    ← key: value  │
└─────────────────────────────────────┘
```

### Why Labels Matter in Kubernetes

| Use Case | Description |
|----------|-------------|
| **Services** | Use selectors to route traffic to matching Pods |
| **ReplicaSets/Deployments** | Use selectors to manage matching Pods |
| **Network Policies** | Apply rules to Pods matching labels |
| **kubectl filtering** | `kubectl get pods -l env=prod` |
| **Monitoring** | Group metrics by label (e.g., by env, app) |
| **Canary Deployments** | Route a % of traffic to pods with `version: canary` |

---

## 2. What are Selectors?

A **Selector** is a query that filters Kubernetes objects based on their labels.

```
Selectors = "Give me all objects where label X = Y"
```

```
Service (selector: app=web)
        │
        ├── Pod (app=web, env=prod)   ✓ MATCHED
        ├── Pod (app=web, env=dev)    ✓ MATCHED
        └── Pod (app=api, env=prod)   ✗ NOT MATCHED
```

---

## 3. Labels — Imperative Way

### 3.1 Add a label when creating a Pod

```bash
kubectl run nginx-pod --image=nginx --labels="app=web,env=prod,tier=frontend"
```

### 3.2 Add a label to an existing Pod

```bash
# Add single label
kubectl label pod nginx-pod version=1.0

# Add multiple labels
kubectl label pod nginx-pod team=alpha project=ecommerce
```

### 3.3 Update (overwrite) an existing label

```bash
# --overwrite is required when changing an existing label value
kubectl label pod nginx-pod env=staging --overwrite
```

### 3.4 Remove a label (use key-)

```bash
# The minus sign (-) after the key removes the label
kubectl label pod nginx-pod version-

# Remove multiple labels
kubectl label pod nginx-pod version- team-
```

### 3.5 Label a Node

```bash
kubectl label node worker-1 disktype=ssd
kubectl label node worker-1 region=us-east-1
kubectl label node worker-1 gpu=true

# Overwrite
kubectl label node worker-1 disktype=nvme --overwrite

# Remove
kubectl label node worker-1 gpu-
```

### 3.6 Label multiple objects at once

```bash
# Label all pods in a namespace
kubectl label pods --all env=test

# Label pods matching a selector
kubectl label pods -l app=web version=2.0
```

### 3.7 Show labels

```bash
kubectl get pods --show-labels

kubectl get nodes --show-labels

# Show a specific label as a column
kubectl get pods -L app,env
# Output shows app and env as separate columns
```

---

## 4. Labels — Declarative Way

### 4.1 Pod with labels

```yaml
# pod-with-labels.yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-pod
  labels:
    app: web
    env: production
    tier: frontend
    version: "2.1"
    team: "platform"
spec:
  containers:
  - name: nginx
    image: nginx:1.25
    ports:
    - containerPort: 80
```

```bash
kubectl apply -f pod-with-labels.yaml
```

### 4.2 Multiple Pods with consistent labels

```yaml
# pod-prod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-prod-1
  labels:
    app: web
    env: production
spec:
  containers:
  - name: nginx
    image: nginx:1.25
---
apiVersion: v1
kind: Pod
metadata:
  name: web-prod-2
  labels:
    app: web
    env: production
spec:
  containers:
  - name: nginx
    image: nginx:1.25
---
apiVersion: v1
kind: Pod
metadata:
  name: web-dev-1
  labels:
    app: web
    env: development
spec:
  containers:
  - name: nginx
    image: nginx:latest
```

```bash
kubectl apply -f pod-prod.yaml

# Query only production pods
kubectl get pods -l env=production
# Returns: web-prod-1, web-prod-2

# Query only dev pods
kubectl get pods -l env=development
# Returns: web-dev-1
```

### 4.3 Service using label selector (declarative)

```yaml
# service-with-selector.yaml
apiVersion: v1
kind: Service
metadata:
  name: web-service
spec:
  selector:
    app: web           # Routes traffic to ALL pods with app=web
    env: production    # AND env=production
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
```

---

## 5. Label Naming Rules and Conventions

### Key Format
```
[optional-prefix/]name

Examples:
  app                          ← simple key (no prefix)
  app.kubernetes.io/name       ← with prefix
  mycompany.com/tier           ← custom prefix
```

### Rules
- Key name: max **63 characters**, alphanumeric, `-`, `_`, `.`
- Key prefix: must be a valid DNS subdomain, max **253 characters**
- Value: max **63 characters**, alphanumeric, `-`, `_`, `.`, or empty string
- Must start and end with alphanumeric character

### Recommended Label Keys (Kubernetes Well-Known Labels)

```yaml
labels:
  app.kubernetes.io/name: "myapp"           # App name
  app.kubernetes.io/instance: "myapp-prod"  # Unique instance
  app.kubernetes.io/version: "1.0.0"        # App version
  app.kubernetes.io/component: "database"   # Component type
  app.kubernetes.io/part-of: "ecommerce"    # Larger system name
  app.kubernetes.io/managed-by: "helm"      # Tool managing this
```

### Common Custom Labels (Team conventions)

```yaml
labels:
  app: myapp
  env: production          # production | staging | development | testing
  tier: frontend           # frontend | backend | database | cache
  team: platform           # owning team
  version: "1.2.3"
  release: stable          # stable | canary | beta
```

---

## 6. Selector Types

Kubernetes has two types of label selectors:

| Type | Supported By | Syntax |
|------|-------------|--------|
| **Equality-based** | ReplicationController, Service | `=`, `==`, `!=` |
| **Set-based** | ReplicaSet, Deployment, Job, DaemonSet | `in`, `notin`, `exists` |

> **Note**: ReplicaSets, Deployments use `matchLabels` and `matchExpressions` (both types). Services use only `selector` (equality-based).

---

## 7. Equality-Based Selectors

Filter based on exact key=value match.

### In kubectl

```bash
# Equal (=  or  ==)
kubectl get pods -l app=web
kubectl get pods -l app==web        # same as above

# Not equal (!=)
kubectl get pods -l env!=production

# Multiple conditions (AND logic — comma-separated)
kubectl get pods -l app=web,env=production

# Combination
kubectl get pods -l app=web,env!=development
```

### In YAML (Services use equality-based selectors)

```yaml
# Service — equality selector
apiVersion: v1
kind: Service
metadata:
  name: frontend-service
spec:
  selector:
    app: web          # app == web
    tier: frontend    # AND tier == frontend
  ports:
  - port: 80
    targetPort: 80
```

### In ReplicaSet (matchLabels = equality-based)

```yaml
spec:
  selector:
    matchLabels:
      app: web          # Equality: app == web
      env: production   # AND env == production
  template:
    metadata:
      labels:
        app: web          # Must match selector
        env: production
```

---

## 8. Set-Based Selectors

More expressive than equality-based. Supported by ReplicaSet, Deployment, Job.

### Operators

| Operator | Meaning | Example |
|----------|---------|---------|
| `In` | Value is in a set | `env in (prod, staging)` |
| `NotIn` | Value is not in a set | `env notin (dev, test)` |
| `Exists` | Key exists (any value) | `tier` |
| `DoesNotExist` | Key does not exist | `!tier` |

### In kubectl

```bash
# In operator
kubectl get pods -l 'env in (production, staging)'

# NotIn operator
kubectl get pods -l 'env notin (development, testing)'

# Exists (key exists, any value)
kubectl get pods -l 'tier'

# DoesNotExist (key absent)
kubectl get pods -l '!tier'

# Combine set-based and equality-based
kubectl get pods -l 'app=web,env in (production, staging)'
```

### In YAML (matchExpressions)

```yaml
# ReplicaSet with set-based selector
apiVersion: apps/v1
kind: ReplicaSet
metadata:
  name: web-rs
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web              # Equality-based
    matchExpressions:
    - key: env
      operator: In          # Set-based: env must be in this list
      values:
      - production
      - staging
    - key: tier
      operator: NotIn       # tier must NOT be in this list
      values:
      - backend
    - key: version          # version key must exist
      operator: Exists
  template:
    metadata:
      labels:
        app: web
        env: production
        tier: frontend
        version: "1.0"
    spec:
      containers:
      - name: nginx
        image: nginx:1.25
```

### Full matchExpressions Example

```yaml
selector:
  matchLabels:
    app: myapp
  matchExpressions:
  - key: env
    operator: In
    values: [production, staging]
  - key: tier
    operator: NotIn
    values: [test]
  - key: release
    operator: Exists
  - key: deprecated
    operator: DoesNotExist
```

> **All conditions are ANDed together** — the Pod must satisfy ALL rules to be selected.

---

## 9. Labels on Different Resources

### Node Labels

```yaml
# Label a node declaratively via Node manifest is unusual;
# commonly done imperatively:
kubectl label node worker-1 disktype=ssd region=ap-south-1 gpu=false

# Use in Pod via nodeSelector
spec:
  nodeSelector:
    disktype: ssd
    region: ap-south-1
```

### Namespace Labels

```bash
kubectl label namespace dev team=alpha
kubectl label namespace prod team=beta env=production
```

```yaml
# In NetworkPolicy — select namespaces by label
spec:
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          team: alpha
```

### Service Labels (different from selector)

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-service
  labels:              # Labels ON the service itself
    app: web
    env: production
spec:
  selector:            # Labels of Pods to target
    app: web
  ports:
  - port: 80
```

### ConfigMap / Secret Labels

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  labels:
    app: web
    env: production
data:
  db_host: "localhost"
```

---

## 10. Annotations vs Labels

| Feature | Labels | Annotations |
|---------|--------|-------------|
| Purpose | Identify, select, group | Store metadata/non-identifying info |
| Used in selectors | ✓ Yes | ✗ No |
| Value restrictions | Max 63 chars, alphanumeric | Any string, any length |
| Used by Kubernetes | Yes (routing, scheduling) | Rarely (some controllers read annotations) |
| Examples | `app=web`, `env=prod` | `description`, `git-commit`, `build-date` |

```yaml
metadata:
  name: my-pod
  labels:
    app: web              # Used by Services, ReplicaSets for selection
    env: production
  annotations:
    description: "Main web server"
    owner: "team-platform"
    git-commit: "abc123def456"
    build-date: "2026-01-15"
    prometheus.io/scrape: "true"     # Prometheus reads this annotation
    prometheus.io/port: "8080"
    kubectl.kubernetes.io/last-applied-configuration: |
      {...json...}
```

### Add annotation imperatively

```bash
kubectl annotate pod my-pod description="My web server"
kubectl annotate pod my-pod owner="team-alpha" build-date="2026-01-15"

# Overwrite
kubectl annotate pod my-pod description="Updated description" --overwrite

# Remove
kubectl annotate pod my-pod description-
```

---

## 11. Real-World Labeling Strategy

### Example: E-commerce Application

```yaml
# Frontend Pod
labels:
  app.kubernetes.io/name: ecommerce
  app.kubernetes.io/component: frontend
  app.kubernetes.io/version: "3.2.1"
  env: production
  team: frontend-squad

# Backend API Pod
labels:
  app.kubernetes.io/name: ecommerce
  app.kubernetes.io/component: api
  app.kubernetes.io/version: "2.0.5"
  env: production
  team: backend-squad

# Database Pod
labels:
  app.kubernetes.io/name: ecommerce
  app.kubernetes.io/component: database
  env: production
  tier: data
```

```bash
# Get all production resources
kubectl get pods -l env=production

# Get all ecommerce app pods
kubectl get pods -l 'app.kubernetes.io/name=ecommerce'

# Get only frontend pods
kubectl get pods -l 'app.kubernetes.io/component=frontend'

# Get non-database pods
kubectl get pods -l 'app.kubernetes.io/component notin (database)'
```

### Canary Deployment Pattern

```yaml
# Stable version - 9 replicas
labels:
  app: web
  track: stable

# Canary version - 1 replica
labels:
  app: web
  track: canary
```

```yaml
# Service routes to ALL (both stable and canary)
spec:
  selector:
    app: web     # Selects stable + canary (both have app=web)
```

```bash
# Monitor canary
kubectl get pods -l 'app=web,track=canary'

# Get stable only
kubectl get pods -l 'app=web,track=stable'
```

---

## 12. Useful kubectl Commands

```bash
# ── Viewing Labels ────────────────────────────────────────
kubectl get pods --show-labels
kubectl get pods -L app,env,tier          # Show these labels as columns
kubectl get nodes --show-labels
kubectl get all --show-labels

# ── Filtering with Selectors ─────────────────────────────
kubectl get pods -l app=web
kubectl get pods -l app=web,env=production
kubectl get pods -l 'env in (production, staging)'
kubectl get pods -l 'env notin (development)'
kubectl get pods -l '!version'                    # Pods WITHOUT version label
kubectl get pods -l 'app=web,env in (prod,staging),!deprecated'

# ── Adding Labels ─────────────────────────────────────────
kubectl label pod my-pod app=web
kubectl label pod my-pod app=web env=prod tier=frontend
kubectl label pods --all env=test                 # All pods
kubectl run nginx --image=nginx --labels="app=web,env=prod"

# ── Updating Labels ───────────────────────────────────────
kubectl label pod my-pod env=staging --overwrite

# ── Removing Labels ───────────────────────────────────────
kubectl label pod my-pod env-          # Remove 'env' label

# ── Deleting by Selector ─────────────────────────────────
kubectl delete pods -l env=test
kubectl delete pods -l 'env in (test, development)'

# ── Labels on Other Resources ────────────────────────────
kubectl label node worker-1 disktype=ssd
kubectl label namespace dev team=alpha
kubectl label service my-svc version=2

# ── Annotations ──────────────────────────────────────────
kubectl annotate pod my-pod description="Web server" owner="team-a"
kubectl annotate pod my-pod description="Updated" --overwrite
kubectl annotate pod my-pod description-          # Remove annotation
```

---

## 13. Common Interview Questions

**Q: What is the difference between labels and annotations?**
> Labels are key-value pairs used to **identify and select** objects (used in selectors). Annotations store **arbitrary non-identifying metadata** (descriptions, build info, tool configs) and cannot be used in selectors.

**Q: What is the difference between equality-based and set-based selectors?**
> Equality-based: `key=value` or `key!=value`. Simple exact match.
> Set-based: `key in (val1,val2)`, `key notin (val1)`, `Exists`, `DoesNotExist`. More expressive, allows multiple values.

**Q: Can a Service use set-based selectors?**
> No. Services only support equality-based selectors (`key: value`). Set-based selectors (matchExpressions) are only supported by ReplicaSet, Deployment, Job, DaemonSet.

**Q: What happens if a Pod is created manually with labels that match a ReplicaSet's selector?**
> The ReplicaSet will **adopt** that Pod and count it toward its desired replica count. If you already have 3 replicas, the ReplicaSet may terminate the manually created Pod or reduce new creations.

**Q: How do you select pods that DON'T have a specific label?**
> `kubectl get pods -l '!version'` — this returns pods where the key `version` does not exist.

**Q: What happens if a Pod's labels are changed to no longer match its controller's selector?**
> The controller (ReplicaSet/Deployment) abandons that Pod and creates a new one to maintain the desired count. The relabeled Pod becomes an orphan.

---

*Notes by ITkannadigaru | CKA 2026 Certification*

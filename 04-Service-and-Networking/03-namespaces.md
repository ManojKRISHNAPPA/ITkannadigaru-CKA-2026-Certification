# Kubernetes Namespaces — Complete Guide

> Namespaces are virtual clusters inside a physical cluster — walls that separate teams, projects, and environments without needing separate hardware.

---

## Table of Contents

1. [What is a Namespace?](#1-what-is-a-namespace)
2. [Why Namespaces?](#2-why-namespaces)
3. [Default Namespaces](#3-default-namespaces)
4. [Namespace-Scoped vs Cluster-Scoped Resources](#4-namespace-scoped-vs-cluster-scoped-resources)
5. [Creating and Managing Namespaces](#5-creating-and-managing-namespaces)
6. [Working in a Namespace — kubectl Context](#6-working-in-a-namespace--kubectl-context)
7. [Resource Quotas — Limiting Namespace Resources](#7-resource-quotas--limiting-namespace-resources)
8. [LimitRange — Default Limits per Container](#8-limitrange--default-limits-per-container)
9. [Cross-Namespace Communication](#9-cross-namespace-communication)
10. [Namespace Patterns in Production](#10-namespace-patterns-in-production)
11. [Practical Demo](#11-practical-demo)
12. [Common Interview Questions](#12-common-interview-questions)
13. [Exam Practice Questions](#13-exam-practice-questions)

---

## 1. What is a Namespace?

A **Namespace** is a mechanism to partition a single Kubernetes cluster into multiple **virtual clusters**. Resources inside one namespace are isolated from resources in another.

```
  Physical Cluster
  ┌─────────────────────────────────────────────────────────────────┐
  │                                                                 │
  │  ┌──────────────────┐  ┌──────────────────┐  ┌─────────────┐  │
  │  │  Namespace: dev  │  │ Namespace: prod   │  │  Namespace  │  │
  │  │                  │  │                   │  │  staging    │  │
  │  │  web-pod         │  │  web-pod          │  │  web-pod    │  │
  │  │  db-service      │  │  db-service       │  │  db-service │  │
  │  │  api-deploy      │  │  api-deploy       │  │  api-deploy │  │
  │  └──────────────────┘  └──────────────────┘  └─────────────┘  │
  │                                                                 │
  │  Same names, different namespaces — no collision!               │
  └─────────────────────────────────────────────────────────────────┘
```

**Key properties:**
- Resources with the same name can exist in different namespaces
- Network policies can isolate namespaces from each other
- RBAC can be scoped to a namespace (users only see/touch their namespace)
- Resource Quotas limit CPU/memory per namespace
- DNS names include the namespace: `svc.namespace.svc.cluster.local`

---

## 2. Why Namespaces?

| Problem | Namespace Solution |
|---------|-------------------|
| Dev and prod resources collide | Separate `dev` and `prod` namespaces |
| Team A can accidentally delete Team B's resources | RBAC scoped per namespace |
| One team uses too much cluster CPU | ResourceQuota per namespace |
| Hard to audit what belongs to which project | Label + namespace filtering |
| Cluster sprawl (too many small clusters) | Multiple namespaces on one cluster |

> **When NOT to use namespaces**: For small teams (< 10 people) or single-project clusters, the overhead isn't worth it. Use namespaces when you have multiple teams, environments, or projects sharing one cluster.

---

## 3. Default Namespaces

Kubernetes creates four namespaces on cluster creation:

```bash
kubectl get namespaces
```

```
NAME              STATUS   AGE
default           Active   10d
kube-node-lease   Active   10d
kube-public       Active   10d
kube-system       Active   10d
```

| Namespace | Purpose | Should you touch it? |
|-----------|---------|---------------------|
| **default** | Where resources go when no namespace is specified | Yes — for dev/learning |
| **kube-system** | Core Kubernetes components (API server, scheduler, CoreDNS, kube-proxy) | Read-only in prod |
| **kube-public** | Publicly readable by all users (cluster info, bootstrap tokens) | Rarely |
| **kube-node-lease** | Node heartbeat Lease objects (improves node failure detection) | Never |

```bash
# See what runs in kube-system
kubectl get pods -n kube-system

# Output includes:
# coredns-xxx             ← DNS
# etcd-master             ← key-value store
# kube-apiserver-master   ← API server
# kube-scheduler-master   ← scheduler
# kube-proxy-xxx          ← networking (DaemonSet)
```

---

## 4. Namespace-Scoped vs Cluster-Scoped Resources

Not every Kubernetes resource belongs to a namespace. Some are **cluster-wide**.

```
  Namespace-Scoped:                  Cluster-Scoped:
  (live inside a namespace)          (exist at cluster level, no namespace)

  Pods                               Nodes
  Services                           PersistentVolumes
  Deployments                        StorageClasses
  ReplicaSets                        ClusterRoles
  ConfigMaps                         ClusterRoleBindings
  Secrets                            Namespaces (itself!)
  ServiceAccounts                    IngressClasses
  PersistentVolumeClaims             CustomResourceDefinitions (CRDs)
  Ingress                            PriorityClasses
  ResourceQuota
  LimitRange
```

```bash
# Check which resources are namespace-scoped
kubectl api-resources --namespaced=true

# Check cluster-scoped resources
kubectl api-resources --namespaced=false
```

---

## 5. Creating and Managing Namespaces

### Create a Namespace

```bash
# Imperative (quick)
kubectl create namespace dev
kubectl create namespace prod
kubectl create namespace staging

# Declarative (YAML)
```

```yaml
# namespace.yaml
apiVersion: v1
kind: Namespace
metadata:
  name: dev
  labels:
    environment: development
    team: backend
```

```bash
kubectl apply -f namespace.yaml
```

### Common Namespace Operations

```bash
# List all namespaces
kubectl get ns

# Describe a namespace (shows quotas, limits)
kubectl describe ns dev

# Delete a namespace (DELETES EVERYTHING inside it!)
kubectl delete ns dev

# Create resource in a specific namespace
kubectl run nginx --image=nginx -n dev

# Get pods in a specific namespace
kubectl get pods -n dev

# Get pods across ALL namespaces
kubectl get pods -A
kubectl get pods --all-namespaces

# Get all resources in a namespace
kubectl get all -n dev
```

### Setting a Default Namespace for kubectl

```bash
# Set default namespace for current context (avoids -n flag every time)
kubectl config set-context --current --namespace=dev

# Verify
kubectl config view --minify | grep namespace

# Switch back to default
kubectl config set-context --current --namespace=default
```

---

## 6. Working in a Namespace — kubectl Context

```bash
# See your current context and namespace
kubectl config current-context
kubectl config view --minify

# Create a context for a specific namespace
kubectl config set-context dev-context \
  --cluster=my-cluster \
  --user=admin \
  --namespace=dev

# Switch to that context
kubectl config use-context dev-context

# Install kubens for easy namespace switching (optional tool)
# brew install kubectx
kubens dev       # switch to dev namespace
kubens -         # switch back to previous
kubens           # list all namespaces
```

---

## 7. Resource Quotas — Limiting Namespace Resources

A **ResourceQuota** sets hard limits on total resource consumption within a namespace. Once the quota is reached, new Pods are rejected.

```
  Namespace: dev
  ┌─────────────────────────────────────────────────┐
  │  ResourceQuota: dev-quota                       │
  │                                                 │
  │  CPU limit:      10 cores total                 │
  │  Memory limit:   20Gi total                     │
  │  Pods:           50 max                         │
  │  Services:       10 max                         │
  │                                                 │
  │  Current usage:                                 │
  │  CPU:    6/10    ████████░░                     │
  │  Memory: 12/20   ████████░░░░                   │
  │  Pods:   24/50   ████████░░░░░░░░░░             │
  └─────────────────────────────────────────────────┘
```

### ResourceQuota YAML

```yaml
# resource-quota.yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: dev-quota
  namespace: dev
spec:
  hard:
    # Compute resources
    requests.cpu: "4"           # total CPU requests across all pods
    requests.memory: 8Gi        # total memory requests
    limits.cpu: "8"             # total CPU limits
    limits.memory: 16Gi         # total memory limits

    # Object counts
    pods: "20"                  # max number of pods
    services: "10"
    secrets: "20"
    configmaps: "20"
    persistentvolumeclaims: "10"

    # Service type limits
    services.nodeports: "0"     # block NodePort services in this namespace
    services.loadbalancers: "2"
```

```bash
kubectl apply -f resource-quota.yaml

# Check quota usage
kubectl describe quota dev-quota -n dev

# Output:
# Name:            dev-quota
# Resource         Used  Hard
# --------         ----  ----
# limits.cpu       500m  8
# limits.memory    1Gi   16Gi
# pods             3     20
```

> **Key rule**: Once a ResourceQuota is set for CPU/memory, ALL Pods in that namespace MUST specify `resources.requests` and `resources.limits`. Pods without them will be REJECTED.

---

## 8. LimitRange — Default Limits per Container

A **LimitRange** sets default resource requests/limits for containers that don't specify them, and enforces min/max boundaries.

```yaml
# limitrange.yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: dev-limits
  namespace: dev
spec:
  limits:
  - type: Container
    default:              # applied if container doesn't specify limits
      cpu: 500m
      memory: 256Mi
    defaultRequest:       # applied if container doesn't specify requests
      cpu: 100m
      memory: 128Mi
    max:                  # container cannot exceed these
      cpu: "2"
      memory: 2Gi
    min:                  # container must request at least these
      cpu: 50m
      memory: 64Mi

  - type: Pod             # limits across all containers in a pod
    max:
      cpu: "4"
      memory: 4Gi

  - type: PersistentVolumeClaim
    max:
      storage: 10Gi
    min:
      storage: 1Gi
```

```bash
kubectl apply -f limitrange.yaml

# Check limitrange
kubectl describe limitrange dev-limits -n dev
```

### ResourceQuota vs LimitRange

| Feature | ResourceQuota | LimitRange |
|---------|--------------|------------|
| **Scope** | Total across all pods in namespace | Per individual container/pod |
| **Purpose** | Cap total resource consumption | Set defaults + enforce per-object limits |
| **Rejects pod if** | Namespace total would be exceeded | Container exceeds max or is below min |
| **Sets defaults** | No | Yes (`default`, `defaultRequest`) |

---

## 9. Cross-Namespace Communication

Services in different namespaces CAN communicate using the **full DNS name**.

```
  Namespace: frontend                Namespace: backend
  ┌─────────────────┐               ┌─────────────────────┐
  │  frontend-pod   │               │  api-service        │
  │                 │──────────────►│  ClusterIP          │
  │  calls:         │               │  10.96.50.10        │
  │  api-service.   │               └─────────────────────┘
  │  backend.svc.   │
  │  cluster.local  │
  └─────────────────┘

  Short name works within same namespace: api-service
  Full name needed across namespaces: api-service.backend.svc.cluster.local
```

### DNS Format for Cross-Namespace

```
<service-name>.<namespace>.svc.cluster.local

Examples:
  api-service.backend.svc.cluster.local
  db-service.database.svc.cluster.local
  redis.cache.svc.cluster.local
```

```bash
# Test cross-namespace DNS from a pod
kubectl run test --image=busybox --rm -it -n frontend \
  -- wget -qO- http://api-service.backend.svc.cluster.local
```

### Network Policies for Namespace Isolation

By default all namespaces can talk to each other. Use NetworkPolicy to block cross-namespace traffic:

```yaml
# deny-all-ingress.yaml — block all incoming traffic to namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all-ingress
  namespace: prod
spec:
  podSelector: {}          # applies to all pods in namespace
  policyTypes:
  - Ingress                # block all ingress
```

```yaml
# allow-from-namespace.yaml — only allow traffic from 'frontend' namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-frontend
  namespace: backend
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  ingress:
  - from:
    - namespaceSelector:
        matchLabels:
          name: frontend   # namespace must have this label
```

```bash
# Label a namespace for NetworkPolicy matching
kubectl label namespace frontend name=frontend
```

---

## 10. Namespace Patterns in Production

### Pattern 1: Environment-Based

```
namespaces: dev, staging, prod
Each environment has its own set of all microservices
```

### Pattern 2: Team-Based

```
namespaces: team-payments, team-auth, team-catalog
Each team owns their namespace, manages their own RBAC
```

### Pattern 3: Component-Based

```
namespaces: frontend, backend, database, monitoring, logging
Each layer of the stack in its own namespace
```

### Pattern 4: Combination (Most Common in Enterprise)

```
prod-payments, prod-auth, prod-catalog
staging-payments, staging-auth
dev (shared for all dev work)
monitoring (cluster-wide observability)
```

---

## 11. Practical Demo

```bash
# === SETUP ===
# Create two namespaces
kubectl create ns team-a
kubectl create ns team-b

# === ISOLATION ===
# Deploy same app name in both namespaces
kubectl create deployment web --image=nginx -n team-a
kubectl create deployment web --image=nginx -n team-b

# Both exist without collision
kubectl get deploy -n team-a
kubectl get deploy -n team-b

# === QUOTAS ===
# Apply quota to team-a
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-a-quota
  namespace: team-a
spec:
  hard:
    pods: "5"
    requests.cpu: "2"
    requests.memory: 4Gi
    limits.cpu: "4"
    limits.memory: 8Gi
EOF

# Try to create pod without resource limits — will fail now
kubectl run test --image=nginx -n team-a
# Error: pod minimum cpu/memory not specified

# Create pod WITH limits — succeeds
kubectl run test --image=nginx -n team-a \
  --requests='cpu=100m,memory=128Mi' \
  --limits='cpu=200m,memory=256Mi'

kubectl describe quota team-a-quota -n team-a

# === CROSS-NAMESPACE COMMUNICATION ===
kubectl expose deployment web --port=80 -n team-b --name=web-svc

kubectl run curl-test --image=curlimages/curl --rm -it -n team-a \
  -- curl http://web-svc.team-b.svc.cluster.local

# === CLEANUP ===
kubectl delete ns team-a team-b
```

---

## 12. Common Interview Questions

**Q: What is a Kubernetes Namespace and when would you use one?**
> A Namespace is a virtual partition within a Kubernetes cluster that provides resource isolation, separate RBAC boundaries, and independent resource quotas. Use them when you need to share a cluster across multiple teams, environments (dev/staging/prod), or projects, while preventing resource conflicts and controlling access.

---

**Q: Can two Pods in different namespaces have the same name?**
> Yes. Names must be unique within a namespace, but the same name can exist in multiple namespaces. This is why namespaces enable environment separation — a `web` deployment can exist in both `dev` and `prod` without conflict.

---

**Q: Are all Kubernetes resources namespace-scoped?**
> No. Resources like Nodes, PersistentVolumes, StorageClasses, ClusterRoles, and Namespaces themselves are cluster-scoped. Use `kubectl api-resources --namespaced=false` to see all cluster-scoped resources.

---

**Q: What happens when you delete a namespace?**
> Deleting a namespace is **destructive** — it deletes ALL resources inside it (Pods, Services, Deployments, Secrets, ConfigMaps, etc.) immediately and permanently. There is no confirmation prompt. Always double-check before running `kubectl delete ns`.

---

**Q: What is the difference between ResourceQuota and LimitRange?**
> **ResourceQuota** caps the total resource consumption across all objects in a namespace. **LimitRange** sets default requests/limits for individual containers and enforces per-container min/max boundaries. They work together: LimitRange ensures containers have limits, ResourceQuota ensures the total doesn't exceed the namespace cap.

---

**Q: How do services in different namespaces communicate?**
> Using the full DNS name: `<service>.<namespace>.svc.cluster.local`. Short names like `my-service` only resolve within the same namespace. DNS search suffixes handle the short form.

---

## 13. Exam Practice Questions

**1.** Create a namespace named `project-x` with label `team=devops`.
```bash
kubectl create namespace project-x
kubectl label namespace project-x team=devops
```

**2.** Get all pods across every namespace.
```bash
kubectl get pods -A
# or
kubectl get pods --all-namespaces
```

**3.** Set your current context to always use namespace `dev` by default.
```bash
kubectl config set-context --current --namespace=dev
```

**4.** Create a ResourceQuota in namespace `dev` limiting pods to 10 and CPU requests to 2 cores.
```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: dev-quota
  namespace: dev
spec:
  hard:
    pods: "10"
    requests.cpu: "2"
```

**5.** How do you check the resource quota usage in namespace `dev`?
```bash
kubectl describe quota -n dev
# or
kubectl get resourcequota -n dev
```

**6.** What command lists all namespace-scoped API resources?
```bash
kubectl api-resources --namespaced=true
```

---

> **CKA Exam Tips**:
> - `-n <namespace>` flag works on almost every kubectl command
> - `kubectl get all -n <ns>` gives a quick overview of everything in a namespace
> - ResourceQuota + LimitRange = complete namespace resource control
> - Deleting a namespace deletes everything in it — no undo

---

*Notes by ITkannadigaru | CKA 2026 Certification*

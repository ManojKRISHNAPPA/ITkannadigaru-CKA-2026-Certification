# Kubernetes Services & Networking — Complete Guide

> A Service is the gateway to your Pods. Without it, Pods are invisible islands.

---

## Table of Contents

### Services & Networking
1. [What is a Kubernetes Service?](#1-what-is-a-kubernetes-service)
2. [Why Do We Need Services?](#2-why-do-we-need-services)
3. [How Services Distribute Load](#3-how-services-distribute-load)
4. [Services and Labels — The Relationship](#4-services-and-labels--the-relationship)
5. [How Endpoints Work](#5-how-endpoints-work)
6. [Service Types](#6-service-types)
   - [6.1 ClusterIP (Default)](#61-clusterip-default)
   - [6.2 NodePort](#62-nodeport)
   - [6.3 LoadBalancer](#63-loadbalancer)
   - [6.4 ExternalName](#64-externalname)
7. [Headless Services](#7-headless-services)
8. [Service Discovery — DNS in Kubernetes](#8-service-discovery--dns-in-kubernetes)
9. [Full Demo — Deploy App with Service](#9-full-demo--deploy-app-with-service)
10. [Service Comparison Table](#10-service-comparison-table)
11. [Common Interview Questions](#11-common-interview-questions)
12. [Exam Practice Questions](#12-exam-practice-questions)

---

## 1. What is a Kubernetes Service?

A **Service** is a Kubernetes object that provides a **stable network endpoint** to access a group of Pods.

Pods are **ephemeral** — they get created and destroyed constantly. Every time a Pod restarts, it gets a **new IP address**. This makes it impossible for other applications to reliably talk to Pods using their IP directly.

A Service solves this by acting as a **permanent, stable address** in front of Pods.

```
Without Service:                 With Service:
                                 
 Pod A  → IP: 10.0.0.1           ┌─────────────┐
 Pod B  → IP: 10.0.0.2     →     │   Service   │  ← Stable IP: 10.96.50.10
 Pod C  → IP: 10.0.0.3           └──────┬──────┘
                                        │ routes to
                                 Pod A / Pod B / Pod C
```

**Key properties of a Service:**
- Has a **stable ClusterIP** that never changes
- Has a **DNS name** (e.g., `my-service.default.svc.cluster.local`)
- Automatically discovers Pods using **label selectors**
- Performs **load balancing** across healthy Pods
- Works even when Pods are scaled up or down

---

## 2. Why Do We Need Services?

### The Core Problem

```
                  [ Client App ]
                        |
                        | which IP do I call?
                        ↓
  ┌──────────┬──────────┬──────────┐
  │  Pod A   │  Pod B   │  Pod C   │
  │ (dies)   │ (new)    │ (scaled) │
  │10.0.0.1  │10.0.0.9  │10.0.0.15 │
  └──────────┴──────────┴──────────┘
  
  IPs change on every restart — direct Pod access is unreliable!
```

### The Service Solution

```
                  [ Client App ]
                        |
                        | calls stable address
                        ↓
               ┌────────────────┐
               │    Service     │  ← IP: 10.96.50.10 (never changes)
               │  my-app-svc    │  ← DNS: my-app-svc.default.svc.cluster.local
               └───────┬────────┘
                       │ kube-proxy routes traffic
              ┌────────┼────────┐
              ↓        ↓        ↓
           Pod A     Pod B    Pod C
```

**Without Services you cannot:**
- Scale Pods reliably (no consistent address)
- Do rolling updates (IPs change during update)
- Expose apps outside the cluster
- Enable internal microservice communication

---

## 3. How Services Distribute Load

A Service uses **kube-proxy** (running on every Node) and **iptables/IPVS rules** to distribute incoming traffic across all healthy Pod endpoints.

### Load Balancing Flow

```
                     ┌──────────────────────────────┐
  Incoming Request   │         kube-proxy           │
  ─────────────────► │  (watches Service + Endpoints)│
                     └──────────────┬───────────────┘
                                    │
                         iptables / IPVS rules
                                    │
                    ┌───────────────┼───────────────┐
                    │               │               │
                    ▼               ▼               ▼
               ┌─────────┐   ┌─────────┐   ┌─────────┐
               │  Pod A  │   │  Pod B  │   │  Pod C  │
               │ (1/3)   │   │ (1/3)   │   │ (1/3)   │
               └─────────┘   └─────────┘   └─────────┘
                        Round-Robin by default
```

### How kube-proxy works

| Component | Role |
|-----------|------|
| **kube-proxy** | DaemonSet on every Node; programs network rules |
| **iptables mode** | Default; rewrites packet destination using NAT rules |
| **IPVS mode** | High-performance; better for large clusters (1000+ services) |
| **Endpoints object** | Tracks the IPs of all matching Pods |

### Load Balancing Algorithm

By default, Kubernetes uses **random/round-robin** load balancing. Traffic is distributed roughly equally across all healthy endpoints.

```
Request 1 → Pod A
Request 2 → Pod B
Request 3 → Pod C
Request 4 → Pod A   ← cycles back
```

> **Key rule**: Services do NOT guarantee session affinity by default. Each request may land on a different Pod.

**To enable session affinity** (sticky sessions):
```yaml
spec:
  sessionAffinity: ClientIP        # same client always hits same Pod
  sessionAffinityConfig:
    clientIP:
      timeoutSeconds: 10800        # 3 hour timeout
```

---

## 4. Services and Labels — The Relationship

This is the **most critical concept** for understanding Services. A Service does NOT directly reference Pods by name or IP. Instead it uses **label selectors** to dynamically find and track matching Pods.

### How Label Selectors Work

```
  Pod Definition:                Service Definition:
  ────────────────               ──────────────────
  metadata:                      spec:
    labels:                        selector:
      app: my-app         ←────────  app: my-app
      tier: frontend      ←────────  tier: frontend
      version: v2
```

If a Pod has labels that **match all** the selector key-value pairs, the Service automatically includes that Pod as a backend.

### Visual: Labels Glue Services to Pods

```
  ┌────────────────────────────────────────────────────────┐
  │                    Kubernetes Cluster                  │
  │                                                        │
  │   ┌──────────────────────────────────────────────┐    │
  │   │              Service: web-svc                │    │
  │   │        selector: { app: web }                │    │
  │   └───────────────────┬──────────────────────────┘    │
  │                        │ matches label app=web          │
  │         ┌──────────────┼──────────────┐               │
  │         ▼              ▼              ▼               │
  │   ┌──────────┐  ┌──────────┐  ┌──────────┐           │
  │   │  Pod A   │  │  Pod B   │  │  Pod C   │           │
  │   │app: web  │  │app: web  │  │app: db   │           │
  │   │tier: fe  │  │tier: fe  │  │tier: db  │           │
  │   └──────────┘  └──────────┘  └──────────┘           │
  │   ✓ SELECTED    ✓ SELECTED    ✗ NOT SELECTED          │
  │                                                        │
  └────────────────────────────────────────────────────────┘
```

### Dynamic Membership — Pods Join and Leave Automatically

```
Scale from 2 → 4 replicas:

Before:                    After kubectl scale:
Service selector           Service selector
app=web                    app=web
  │                          │
  ├── Pod A (app=web) ✓       ├── Pod A (app=web) ✓
  └── Pod B (app=web) ✓       ├── Pod B (app=web) ✓
                              ├── Pod C (app=web) ✓  ← NEW
                              └── Pod D (app=web) ✓  ← NEW

Service automatically picks up new Pods — no config change needed!
```

### Practical Example

```yaml
# Pod with labels
apiVersion: v1
kind: Pod
metadata:
  name: web-pod-1
  labels:
    app: web          # ← label key=value
    tier: frontend
    version: v2
spec:
  containers:
  - name: nginx
    image: nginx:1.21
    ports:
    - containerPort: 80
```

```yaml
# Service selecting those Pods
apiVersion: v1
kind: Service
metadata:
  name: web-service
spec:
  selector:
    app: web          # ← must match Pod label
    tier: frontend    # ← ALL selectors must match (AND logic)
  ports:
  - protocol: TCP
    port: 80          # Service port (what clients call)
    targetPort: 80    # Container port (what Pod listens on)
```

> **CKA Tip**: The `selector` in a Service uses AND logic — a Pod must match ALL listed labels to be included. If you need OR logic, create multiple Services.

---

## 5. How Endpoints Work

An **Endpoints** object (or **EndpointSlice** in modern Kubernetes) is an automatically managed object that stores the actual **IP addresses and ports** of Pods matching a Service's selector.

### The Endpoints Object

```
  Service: web-service           Endpoints: web-service (auto-created)
  ─────────────────────          ──────────────────────────────────────
  selector:                      subsets:
    app: web              ──►      - addresses:
                                     - ip: 10.244.1.5    ← Pod A IP
                                     - ip: 10.244.2.3    ← Pod B IP
                                     - ip: 10.244.3.7    ← Pod C IP
                                   ports:
                                     - port: 80
```

### Lifecycle of Endpoints

```
  1. Service created with selector: app=web
          │
          ▼
  2. Endpoints Controller (part of controller-manager) watches for Pods
          │
          ▼
  3. Pods matching app=web are discovered
          │
          ▼
  4. Their IPs added to Endpoints object
          │
          ▼
  5. kube-proxy reads Endpoints and programs iptables rules
          │
          ▼
  6. Traffic now routes to Pod IPs

  When a Pod dies → its IP removed from Endpoints → traffic stops going there
  When a Pod starts → its IP added to Endpoints → traffic starts flowing
```

### Inspecting Endpoints

```bash
# View endpoints for a service
kubectl get endpoints web-service

# Detailed view
kubectl describe endpoints web-service

# Watch endpoints change in real time
kubectl get endpoints web-service -w
```

Example output:
```
NAME          ENDPOINTS                                 AGE
web-service   10.244.1.5:80,10.244.2.3:80,10.244.3.7:80   5m
```

### EndpointSlices (Modern Kubernetes ≥ 1.21)

In large clusters, a single Endpoints object becomes a bottleneck. **EndpointSlices** split endpoints into smaller chunks (max 100 per slice by default).

```bash
# View endpoint slices
kubectl get endpointslices

# Filter by service
kubectl get endpointslices -l kubernetes.io/service-name=web-service
```

### Manual Endpoints (Services without Selectors)

You can create a Service **without a selector** and manually define Endpoints. Useful for pointing to external databases or legacy systems.

```yaml
# Service without selector
apiVersion: v1
kind: Service
metadata:
  name: external-db
spec:
  ports:
  - port: 5432
    targetPort: 5432
  # No selector!
---
# Manually created Endpoints
apiVersion: v1
kind: Endpoints
metadata:
  name: external-db    # Must match Service name exactly
subsets:
- addresses:
  - ip: 192.168.1.100  # External DB server IP
  ports:
  - port: 5432
```

---

## 6. Service Types

Kubernetes provides **four Service types**, each exposing workloads differently depending on who needs access.

```
  Access Scope:
  
  ┌──────────────────────────────────────────────────────────────┐
  │  ClusterIP  →  Only inside the cluster                       │
  ├──────────────────────────────────────────────────────────────┤
  │  NodePort   →  Inside cluster + via Node's external IP       │
  ├──────────────────────────────────────────────────────────────┤
  │  LoadBalancer → Inside cluster + external cloud LB           │
  ├──────────────────────────────────────────────────────────────┤
  │  ExternalName → Maps to an external DNS name                 │
  └──────────────────────────────────────────────────────────────┘
```

---

### 6.1 ClusterIP (Default)

**ClusterIP** creates a virtual IP address **only accessible within the cluster**. This is the default type when no `type` is specified.

**Use when:** Microservices that only need to talk to each other internally.

```
  External World    │     Kubernetes Cluster
  ──────────────────│─────────────────────────────────
  ✗ No access       │   App Pod ──► ClusterIP ──► DB Pod
                    │                10.96.50.10
                    │
                    │   ClusterIP = internal-only VIP
```

**YAML Example:**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: backend-service
  namespace: default
spec:
  type: ClusterIP      # default; can omit this line
  selector:
    app: backend
  ports:
  - protocol: TCP
    port: 80           # Port exposed by the Service
    targetPort: 8080   # Port the container listens on
```

**Commands:**

```bash
# Create service imperatively
kubectl expose deployment backend --port=80 --target-port=8080 --type=ClusterIP

# Get the ClusterIP
kubectl get svc backend-service

# Test from inside the cluster
kubectl run test-pod --image=busybox --rm -it -- wget -qO- http://backend-service
```

---

### 6.2 NodePort

**NodePort** exposes the Service on a **static port on every Node's IP**. A ClusterIP is also created automatically. External clients can reach the Service at `<NodeIP>:<NodePort>`.

**Port range:** 30000–32767 (default)

```
  External World         Kubernetes Nodes           Pods
  ──────────────         ────────────────           ────
  
  Browser/Client         Node 1: 192.168.1.10
       │                 ┌──────────────────┐      ┌─────────┐
       │ :30080          │  NodePort: 30080 │─────►│  Pod A  │
       └────────────────►│  ClusterIP:80    │      │  :8080  │
                         └──────────────────┘      └─────────┘
                         
                         Node 2: 192.168.1.11       ┌─────────┐
                         ┌──────────────────┐  ────►│  Pod B  │
                         │  NodePort: 30080 │       │  :8080  │
                         └──────────────────┘       └─────────┘
                         
  ANY node's IP + NodePort works — even if Pod isn't on that node!
```

**YAML Example:**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-nodeport
spec:
  type: NodePort
  selector:
    app: web
  ports:
  - protocol: TCP
    port: 80           # ClusterIP port (internal)
    targetPort: 8080   # Container port
    nodePort: 30080    # External port on Node (30000-32767)
                       # omit to auto-assign
```

**Commands:**

```bash
# Create NodePort service
kubectl expose deployment web --port=80 --target-port=8080 --type=NodePort

# Check assigned NodePort
kubectl get svc web-nodeport

# Access from outside (replace with actual node IP)
curl http://<NODE-IP>:30080

# Get node IP
kubectl get nodes -o wide
```

> **CKA Tip**: If `nodePort` is omitted, Kubernetes auto-assigns a port in the 30000–32767 range. You can specify it explicitly only if the port is free.

**When to use NodePort:**
- Dev/test environments
- On-premise clusters without cloud load balancers
- When you need simple external access without a cloud provider

---

### 6.3 LoadBalancer

**LoadBalancer** provisions an **external cloud load balancer** (AWS ELB, GCP Load Balancer, Azure LB) automatically. It builds on top of NodePort and ClusterIP.

**Use when:** Running on a cloud provider and need production-grade external access.

```
  Internet           Cloud LB            Kubernetes Nodes           Pods
  ────────           ────────            ────────────────           ────
  
  Users              AWS/GCP/Azure       Node 1                  ┌─────────┐
    │                   ELB              ┌───────────────┐   ───►│  Pod A  │
    │ HTTPS:443         │ :80            │ NodePort:31000│       └─────────┘
    └──────────────────►│────────────────►               │       
                        │                └───────────────┘       ┌─────────┐
                                         Node 2              ───►│  Pod B  │
                                         ┌───────────────┐       └─────────┘
                                         │ NodePort:31000│
                                         └───────────────┘
                                         
  External IP automatically provisioned by cloud provider
```

**YAML Example:**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: web-lb
  annotations:
    # AWS-specific annotation to create internal LB
    service.beta.kubernetes.io/aws-load-balancer-internal: "true"
spec:
  type: LoadBalancer
  selector:
    app: web
  ports:
  - protocol: TCP
    port: 80           # External LB port
    targetPort: 8080   # Container port
```

**Commands:**

```bash
# Create LoadBalancer service
kubectl expose deployment web --port=80 --target-port=8080 --type=LoadBalancer

# Watch for external IP to be assigned (takes 1-3 mins on cloud)
kubectl get svc web-lb -w

# Output after provisioning:
# NAME     TYPE           CLUSTER-IP    EXTERNAL-IP      PORT(S)        AGE
# web-lb   LoadBalancer   10.96.50.10   34.120.55.201    80:31000/TCP   2m
```

> **Note**: On local clusters (minikube, kind), LoadBalancer stays in `<pending>` state. Use `minikube tunnel` to simulate it.

```bash
# For minikube
minikube tunnel

# For kind, use MetalLB or port-forward instead
kubectl port-forward svc/web-lb 8080:80
```

---

### 6.4 ExternalName

**ExternalName** maps a Service name to an **external DNS name**. No proxying, no IPs — just a CNAME DNS record.

**Use when:** You want Pods to access an external service (like an RDS database) using a Kubernetes-style service name.

```
  Pod inside cluster             External World
  ──────────────────             ──────────────
  
  connects to:                   
  db-service.default.svc.cluster.local
           │
           │ CNAME DNS lookup
           ▼
  mydb.example.rds.amazonaws.com  ← actual external hostname
           │
           ▼
  192.168.100.50  (resolved by external DNS)
```

**YAML Example:**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: external-db
  namespace: default
spec:
  type: ExternalName
  externalName: mydb.us-east-1.rds.amazonaws.com  # External DNS name
  # No selector needed — no Pods involved
```

**How Pods use it:**

```bash
# Pod can now connect using the service name instead of the external URL
# Instead of: mydb.us-east-1.rds.amazonaws.com:5432
# Use:        external-db.default.svc.cluster.local:5432

# This makes it easy to swap out the external DB without changing app code
```

> **Key rule**: ExternalName works at the DNS level (CNAME). It does NOT proxy traffic. The Pod directly connects to the resolved external address.

---

## 7. Headless Services

A **Headless Service** is a ClusterIP service with `clusterIP: None`. Instead of returning a single virtual IP, DNS returns the **individual IPs of all matching Pods**.

**Use when:** StatefulSets (databases like Cassandra, Kafka) where each Pod needs its own stable identity.

```
  Normal ClusterIP Service:        Headless Service:
  ─────────────────────────        ────────────────
  
  DNS query: my-svc               DNS query: my-svc
  Returns: 10.96.50.10 (VIP)      Returns:
                                   10.244.1.5  (Pod 0)
                                   10.244.2.3  (Pod 1)
                                   10.244.3.7  (Pod 2)
                                  
  Load balanced — client           Client picks specific Pod
  doesn't know Pod IPs             (e.g., for leader election)
```

**YAML Example:**

```yaml
apiVersion: v1
kind: Service
metadata:
  name: cassandra-headless
spec:
  clusterIP: None     # ← This makes it headless
  selector:
    app: cassandra
  ports:
  - port: 9042
    targetPort: 9042
```

**Per-Pod DNS with StatefulSets:**

```
StatefulSet: cassandra (3 replicas) + Headless Service: cassandra-headless

Each Pod gets its own DNS:
  cassandra-0.cassandra-headless.default.svc.cluster.local → 10.244.1.5
  cassandra-1.cassandra-headless.default.svc.cluster.local → 10.244.2.3
  cassandra-2.cassandra-headless.default.svc.cluster.local → 10.244.3.7
```

---

## 8. Service Discovery — DNS in Kubernetes

Kubernetes runs **CoreDNS** (as a Deployment in `kube-system`) which assigns every Service a DNS name automatically.

### DNS Naming Format

```
<service-name>.<namespace>.svc.<cluster-domain>

Examples:
  web-service.default.svc.cluster.local     ← full form
  web-service.default                        ← short form (from same cluster)
  web-service                                ← shortest (from same namespace)
```

### How Pods Resolve Service Names

```
  Pod in 'default' namespace wants to reach 'web-service':
  
  Step 1: Pod DNS config (/etc/resolv.conf):
          search default.svc.cluster.local svc.cluster.local cluster.local
          nameserver 10.96.0.10   ← CoreDNS ClusterIP
          
  Step 2: Pod calls: web-service
  
  Step 3: CoreDNS expands to: web-service.default.svc.cluster.local
  
  Step 4: CoreDNS returns: 10.96.50.10  (Service ClusterIP)
  
  Step 5: kube-proxy routes to a Pod
```

```bash
# Check CoreDNS pods
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Test DNS resolution from inside a pod
kubectl run dns-test --image=busybox --rm -it -- nslookup web-service

# Full DNS name lookup
kubectl run dns-test --image=busybox --rm -it -- nslookup web-service.default.svc.cluster.local
```

---

## 9. Full Demo — Deploy App with Service

This demo deploys a 3-replica Nginx app and exposes it via different Service types.

### Step 1: Create a Deployment

```bash
kubectl create deployment web-demo --image=nginx:1.21 --replicas=3
```

Or with YAML:

```yaml
# deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-demo
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-demo
  template:
    metadata:
      labels:
        app: web-demo      # ← these labels are used by Service selector
        tier: frontend
    spec:
      containers:
      - name: nginx
        image: nginx:1.21
        ports:
        - containerPort: 80
```

```bash
kubectl apply -f deployment.yaml
kubectl get pods -l app=web-demo
```

### Step 2: Create a ClusterIP Service

```yaml
# clusterip-service.yaml
apiVersion: v1
kind: Service
metadata:
  name: web-demo-clusterip
spec:
  type: ClusterIP
  selector:
    app: web-demo          # ← matches Pod labels
  ports:
  - port: 80
    targetPort: 80
```

```bash
kubectl apply -f clusterip-service.yaml

# Verify service and endpoints
kubectl get svc web-demo-clusterip
kubectl get endpoints web-demo-clusterip

# Test from inside cluster
kubectl run curl-test --image=curlimages/curl --rm -it -- curl http://web-demo-clusterip
```

### Step 3: Verify Load Balancing

```bash
# Run 6 requests and see which Pod responds
for i in $(seq 1 6); do
  kubectl run test-$i --image=curlimages/curl --rm -it --restart=Never \
    -- curl -s http://web-demo-clusterip/hostname 2>/dev/null
done

# Watch endpoints in real time
kubectl get endpoints web-demo-clusterip -w
```

### Step 4: Scale and Watch Endpoints Update

```bash
# Scale up
kubectl scale deployment web-demo --replicas=5

# Watch endpoints automatically update
kubectl get endpoints web-demo-clusterip

# Scale down
kubectl scale deployment web-demo --replicas=2

# Endpoints shrink automatically
kubectl get endpoints web-demo-clusterip
```

### Step 5: Create a NodePort Service

```bash
kubectl expose deployment web-demo --name=web-demo-nodeport \
  --type=NodePort --port=80 --target-port=80

# Get the NodePort
kubectl get svc web-demo-nodeport

# Access via NodePort (get node IP first)
kubectl get nodes -o wide

curl http://<NODE-IP>:<NODE-PORT>
```

### Step 6: Inspect the Full Picture

```bash
# See all services
kubectl get svc

# Describe a service (shows selector, endpoints, events)
kubectl describe svc web-demo-clusterip

# See endpoints
kubectl get ep

# See labels on pods
kubectl get pods --show-labels

# Delete pods and watch endpoints update
kubectl delete pod <pod-name>
kubectl get endpoints web-demo-clusterip -w
```

### Step 7: Cleanup

```bash
kubectl delete deployment web-demo
kubectl delete svc web-demo-clusterip web-demo-nodeport
```

---

## 10. Service Comparison Table

| Feature | ClusterIP | NodePort | LoadBalancer | ExternalName |
|---------|-----------|----------|--------------|--------------|
| **Accessible from** | Inside cluster only | Inside + Node IP | Inside + External LB | DNS CNAME redirect |
| **External IP** | ✗ No | Via Node IP + port | ✓ Cloud LB IP | ✗ No (DNS only) |
| **Port range** | Any | 30000–32767 | Any | N/A |
| **Use case** | Internal microservices | Dev/test, on-prem | Production on cloud | External DNS alias |
| **Needs cloud provider** | ✗ No | ✗ No | ✓ Yes | ✗ No |
| **Load balancing** | ✓ Yes | ✓ Yes | ✓ Yes (L4) | ✗ No |
| **Default type** | ✓ Yes | ✗ No | ✗ No | ✗ No |
| **Builds on top of** | — | ClusterIP | NodePort + ClusterIP | — |

### When to Use What

| Scenario | Recommended Type |
|----------|-----------------|
| Database Pod accessed only by backend | **ClusterIP** |
| Dev environment, expose app for testing | **NodePort** |
| Production web app on AWS/GCP/Azure | **LoadBalancer** |
| Connect Pods to external RDS/Mongo | **ExternalName** |
| StatefulSet (Kafka, Cassandra) | **Headless (ClusterIP: None)** |

---

## 11. Common Interview Questions

**Q: What is a Kubernetes Service and why is it needed?**
> A Service is a stable network abstraction over a set of Pods. Pods are ephemeral and their IPs change on every restart. A Service provides a permanent ClusterIP and DNS name so other components can reliably reach the Pods regardless of their IP changes.

---

**Q: How does a Service know which Pods to route traffic to?**
> A Service uses a **label selector** in its `spec.selector` field. Any Pod that has labels matching ALL the key-value pairs in the selector is automatically added to the Service's backend. This is tracked via the **Endpoints** object, which is updated by the Endpoints Controller whenever matching Pods start, stop, or change health state.

---

**Q: What is the difference between `port`, `targetPort`, and `nodePort`?**
> - **`port`**: The port on which the Service is exposed (what clients call)
> - **`targetPort`**: The port on the container/Pod the traffic is forwarded to
> - **`nodePort`**: (NodePort type only) The port opened on every Node's IP for external access (30000–32767)

---

**Q: What is an Endpoints object?**
> An **Endpoints** object is automatically created and managed by Kubernetes whenever a Service with a selector exists. It holds the IP addresses and ports of all healthy Pods currently matching the Service's selector. kube-proxy reads this object to program iptables/IPVS rules for traffic routing.

---

**Q: What is the difference between ClusterIP and NodePort?**
> **ClusterIP** is only accessible within the cluster via a virtual IP. **NodePort** extends ClusterIP by additionally opening a static port on every cluster Node's external IP, allowing access from outside the cluster. Every NodePort service also gets a ClusterIP.

---

**Q: What happens if you define a Service with no selector?**
> A Service without a selector will not automatically create an Endpoints object. You must manually create an Endpoints object with the same name as the Service, listing the IP:port pairs you want traffic to route to. This is useful for pointing to external services or databases outside the cluster.

---

**Q: What is a Headless Service?**
> A Headless Service has `clusterIP: None`. Instead of returning a single virtual IP, DNS returns the individual Pod IPs directly. This is used with StatefulSets where each Pod needs a stable, unique identity (e.g., Cassandra, Kafka, Zookeeper).

---

**Q: How does kube-proxy do load balancing?**
> kube-proxy runs on every Node as a DaemonSet. It watches the API server for Service and Endpoints changes and programs **iptables** (default) or **IPVS** rules to implement virtual IP routing and load balancing. In iptables mode, it uses DNAT rules to rewrite the destination IP to a randomly selected Pod IP.

---

**Q: What is the default load balancing algorithm for Kubernetes Services?**
> By default, Kubernetes uses **random/round-robin** selection among healthy endpoints. Session affinity is not enabled by default. You can enable `sessionAffinity: ClientIP` to make the same client always route to the same Pod.

---

**Q: Can a Service route to Pods in multiple namespaces?**
> No. A Service's selector only matches Pods in the **same namespace** as the Service. To route to Pods in another namespace, you would need to use ExternalName or create separate Services in each namespace.

---

**Q: What is the difference between a Service and an Ingress?**
> A **Service** operates at Layer 4 (TCP/UDP) and provides basic load balancing between Pods. An **Ingress** operates at Layer 7 (HTTP/HTTPS) and provides host-based/path-based routing, SSL termination, and name-based virtual hosting — it routes to backend Services. Ingress requires an Ingress Controller (nginx, traefik, etc.) to function.

---

## 12. Exam Practice Questions

### Section A: Concept Questions

**1.** What is the default Service type when you run `kubectl expose deployment my-app --port=80`?
> **ClusterIP** — it's the default when no `--type` is specified.

---

**2.** You have a Pod with labels `app=frontend, version=v1, env=prod`. Which of the following Services would select this Pod?
```
   Service A selector: { app: frontend }
   Service B selector: { app: frontend, env: dev }
   Service C selector: { app: frontend, env: prod }
   Service D selector: { version: v1, env: prod }
```
> **Service A, C, and D** would select the Pod. Service B would NOT because `env=dev` doesn't match `env=prod`. A Pod must match ALL selector labels.

---

**3.** A Service has three healthy Pod endpoints. You send 9 requests to the Service. Approximately how many requests does each Pod receive?
> **3 requests each** — round-robin distributes traffic roughly equally across all endpoints.

---

**4.** What command shows you the Pod IPs behind a Service?
> `kubectl get endpoints <service-name>` or `kubectl describe endpoints <service-name>`

---

**5.** What port range is valid for NodePort services?
> **30000–32767** (default range, configurable via kube-apiserver flag `--service-node-port-range`)

---

### Section B: YAML Writing Tasks

**Task 1:** Write a ClusterIP Service named `db-service` that routes to Pods with label `app=mysql` on port 3306.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: db-service
spec:
  type: ClusterIP
  selector:
    app: mysql
  ports:
  - port: 3306
    targetPort: 3306
```

---

**Task 2:** Write a NodePort Service named `frontend-svc` exposing a Deployment with `app=frontend` on NodePort 32000, container port 8080.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: frontend-svc
spec:
  type: NodePort
  selector:
    app: frontend
  ports:
  - port: 80
    targetPort: 8080
    nodePort: 32000
```

---

**Task 3:** Create a Service without a selector that points to external IP `10.0.0.100` on port 5432.

```yaml
apiVersion: v1
kind: Service
metadata:
  name: external-pg
spec:
  ports:
  - port: 5432
    targetPort: 5432
---
apiVersion: v1
kind: Endpoints
metadata:
  name: external-pg
subsets:
- addresses:
  - ip: 10.0.0.100
  ports:
  - port: 5432
```

---

### Section C: Troubleshooting Scenarios

**Scenario 1:** A Service exists but gets no traffic. `kubectl get endpoints my-svc` shows `<none>`. What is wrong?
> The Service **selector does not match any Pod labels**. Either the Pods don't exist, the labels are misspelled, or the namespace is wrong. Fix: run `kubectl get pods --show-labels` and compare against the Service selector with `kubectl describe svc my-svc`.

---

**Scenario 2:** You created a NodePort service but cannot access `<NodeIP>:30080` from outside. What do you check?
> 1. **Firewall/Security Group** — ensure the NodePort is open in cloud security groups
> 2. **Node is reachable** — ping the Node IP
> 3. **Service endpoints** — `kubectl get endpoints` should show Pod IPs
> 4. **Pod is running** — `kubectl get pods` shows Running status
> 5. **Correct node IP** — use `kubectl get nodes -o wide` for the external IP

---

**Scenario 3:** You have `sessionAffinity: None` but need the same user to always hit the same Pod. What do you change?
> Set `sessionAffinity: ClientIP` in the Service spec. This makes kube-proxy route all traffic from the same source IP to the same backend Pod for the duration of the `timeoutSeconds` window.

---

### Section D: Quick-Fire Commands

```bash
# Create a ClusterIP service for deployment 'api' on port 8080
kubectl expose deployment api --port=8080 --target-port=8080

# Create NodePort service, auto-assign port
kubectl expose deployment web --port=80 --type=NodePort

# Get all services with their types
kubectl get svc -o wide

# Get endpoints for a service
kubectl get ep web-service

# Describe service (shows selector, routing, events)
kubectl describe svc web-service

# Check if DNS resolves from inside cluster
kubectl run nslookup-test --image=busybox --rm -it -- nslookup web-service

# Port-forward to test locally without NodePort
kubectl port-forward svc/web-service 8080:80

# Delete a service
kubectl delete svc web-service

# Generate service YAML without applying (dry-run)
kubectl expose deployment web --port=80 --type=NodePort --dry-run=client -o yaml
```

---

> **CKA Exam Tips Summary**:
> - Use `--dry-run=client -o yaml` to generate Service YAML quickly in the exam
> - `kubectl expose` is faster than writing YAML for simple services
> - Always check `kubectl get endpoints` when a service isn't routing
> - Remember: selector in Service must match labels on Pod spec's `metadata.labels`, not `spec.selector` of a Deployment
> - NodePort range: **30000–32767** — memorize this

---

*Notes by ITkannadigaru | CKA 2026 Certification*

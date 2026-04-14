# Complete Guide to Multi-Container Pods in Kubernetes

## Table of Contents
1. [What is a Multi-Container Pod?](#1-what-is-a-multi-container-pod)
2. [Why Multi-Container Pods?](#2-why-multi-container-pods)
3. [Multi-Container Design Patterns](#3-multi-container-design-patterns)
4. [Shared Resources Between Containers](#4-shared-resources-between-containers)
5. [Imperative Way — Creating Multi-Container Pods](#5-imperative-way--creating-multi-container-pods)
6. [Declarative Way — Manifest Files](#6-declarative-way--manifest-files)
7. [Sidecar Pattern — Deep Dive](#7-sidecar-pattern--deep-dive)
8. [Ambassador Pattern — Deep Dive](#8-ambassador-pattern--deep-dive)
9. [Adapter Pattern — Deep Dive](#9-adapter-pattern--deep-dive)
10. [Init Containers vs Sidecar Containers](#10-init-containers-vs-sidecar-containers)
11. [Real-World Use Cases](#11-real-world-use-cases)
12. [Inter-Container Communication](#12-inter-container-communication)
13. [Advantages and Disadvantages](#13-advantages-and-disadvantages)
14. [Useful kubectl Commands](#14-useful-kubectl-commands)
15. [Common Interview Questions](#15-common-interview-questions)

---

## 1. What is a Multi-Container Pod?

A **Multi-Container Pod** is a Kubernetes Pod that runs **more than one container** simultaneously — all within the same Pod boundary.

These containers are **tightly coupled** and:
- Share the **same network namespace** (same IP, same localhost)
- Share **storage volumes** (emptyDir, PVC)
- Start and stop **together** (same Pod lifecycle)
- Are scheduled on the **same node**

```
┌──────────────────────────────────────────────────────────┐
│                        POD                               │
│   ┌─────────────────┐     ┌─────────────────────────┐   │
│   │  Main Container │     │    Sidecar Container    │   │
│   │  (app/nginx)    │◄───►│  (log-shipper/proxy)   │   │
│   └─────────────────┘     └─────────────────────────┘   │
│                                                          │
│   Shared: Network (localhost) + Volumes                  │
│   Pod IP: 10.244.1.10                                    │
└──────────────────────────────────────────────────────────┘
```

> **Core Rule**: Containers in the same Pod are NOT separate microservices. They are **helper processes** that support one primary application.

---

## 2. Why Multi-Container Pods?

### The Problem Without Multi-Container Pods
- Your app container handles logging, proxying, syncing — bloated image
- Hard to update each concern independently
- Violates Single Responsibility Principle at the container level

### The Solution
Split responsibilities across containers **within the same Pod**, so they:
- Can be **independently updated** (update log shipper without touching app)
- Use **different images** (nginx + fluentd)
- Stay **tightly coupled** at runtime (share network/storage)

### When to Use Multi-Container Pods vs Separate Pods

| Scenario | Use |
|----------|-----|
| Containers must share a localhost network | Multi-Container Pod |
| Containers must share a volume directly | Multi-Container Pod |
| Containers scale independently | Separate Pods |
| Containers are different microservices | Separate Pods |
| A helper process is tightly bound to the app | Multi-Container Pod |

> **Key Rule**: If two processes need to share a file or communicate via localhost, they belong in the same Pod. If they scale or deploy independently, use separate Pods.

---

## 3. Multi-Container Design Patterns

Kubernetes recognizes three classic patterns:

```
┌──────────────────────────────────────────────────────────────────┐
│   SIDECAR              AMBASSADOR           ADAPTER              │
│                                                                  │
│  ┌────────┐            ┌────────┐           ┌────────┐          │
│  │  App   │────logs──► │  App   │           │  App   │          │
│  └────────┘            └────────┘           └────────┘          │
│  ┌────────┐            ┌────────┐           ┌────────┐          │
│  │ Sidecar│ (enhances) │ Proxy  │(redirects)│Adapter │(formats) │
│  └────────┘            └────────┘           └────────┘          │
│                            │                    │               │
│                         External             Monitoring         │
│                         Service              System             │
└──────────────────────────────────────────────────────────────────┘
```

| Pattern | Role | Example |
|---------|------|---------|
| **Sidecar** | Enhances or extends the main container | Log shipper, config sync, certificate refresher |
| **Ambassador** | Proxy that handles network communication on behalf of main container | Envoy, Nginx reverse proxy, DB connection proxy |
| **Adapter** | Transforms main container output to a format others expect | Prometheus exporter, log formatter |

---

## 4. Shared Resources Between Containers

### 4.1 Shared Network

All containers in a Pod share the **same network namespace**:

```
Container A (port 8080)
Container B (port 9090)
       │
       └── Both reachable at: Pod IP  (e.g. 10.244.1.10)
           Container A reaches B via:  localhost:9090
           Container B reaches A via:  localhost:8080
```

**Implication**: Two containers in the same Pod **cannot use the same port**.

### 4.2 Shared Storage (Volumes)

Use `emptyDir` to share files between containers:

```
┌──────────────────────────────────────────┐
│                  POD                     │
│                                          │
│  ┌──────────┐    ┌──────────────────┐   │
│  │   App    │    │  Log Sidecar     │   │
│  │          │    │                  │   │
│  │ writes   │    │ reads            │   │
│  │ /var/log │    │ /logs            │   │
│  └────┬─────┘    └────────┬─────────┘   │
│       │                   │             │
│       └──────┬────────────┘             │
│              │                          │
│       ┌──────▼──────┐                   │
│       │  emptyDir   │  (shared volume)  │
│       └─────────────┘                   │
└──────────────────────────────────────────┘
```

---

## 5. Imperative Way — Creating Multi-Container Pods

> **Note**: `kubectl run` only creates single-container Pods directly. For multi-container Pods imperatively, the best practice is to **generate a YAML** and patch it.

### 5.1 Generate base YAML and add second container

```bash
# Step 1: Generate base YAML for main container
kubectl run multi-pod --image=nginx --dry-run=client -o yaml > multi-pod.yaml
```

Then manually edit `multi-pod.yaml` to add a second container under `spec.containers`.

### 5.2 Apply and verify

```bash
kubectl apply -f multi-pod.yaml

# Check all containers are running
kubectl get pod multi-pod

# Describe pod to see all containers
kubectl describe pod multi-pod

# Get container statuses
kubectl get pod multi-pod -o jsonpath='{.status.containerStatuses[*].name}'
```

### 5.3 Exec into a specific container

```bash
# Default: enters first container
kubectl exec -it multi-pod -- bash

# Specify container by name with -c flag
kubectl exec -it multi-pod -c log-sidecar -- sh
```

### 5.4 Get logs from specific container

```bash
# Logs from main container
kubectl logs multi-pod -c app

# Logs from sidecar
kubectl logs multi-pod -c log-sidecar

# Follow logs from sidecar
kubectl logs -f multi-pod -c log-sidecar
```

### 5.5 Delete

```bash
kubectl delete pod multi-pod

# Force delete
kubectl delete pod multi-pod --grace-period=0 --force
```

---

## 6. Declarative Way — Manifest Files

### 6.1 Minimal Multi-Container Pod

```yaml
# multi-pod-minimal.yaml
apiVersion: v1
kind: Pod
metadata:
  name: multi-pod-minimal
spec:
  containers:
  - name: app
    image: nginx:1.25
    ports:
    - containerPort: 80

  - name: sidecar
    image: busybox
    command: ['sh', '-c', 'while true; do echo "sidecar running"; sleep 10; done']
```

```bash
kubectl apply -f multi-pod-minimal.yaml
kubectl get pod multi-pod-minimal
# READY column shows: 2/2  (both containers running)
```

### 6.2 Multi-Container Pod with Shared Volume (Log Shipping)

```yaml
# multi-pod-shared-volume.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-log-sidecar
  labels:
    app: web
    tier: frontend
spec:
  containers:
  # ── Main Application Container ─────────────────────────
  - name: app
    image: nginx:1.25
    ports:
    - containerPort: 80
    volumeMounts:
    - name: shared-logs
      mountPath: /var/log/nginx   # App writes logs here

  # ── Sidecar: Log Shipper ────────────────────────────────
  - name: log-sidecar
    image: busybox
    command: ['sh', '-c', 'tail -F /logs/access.log']
    volumeMounts:
    - name: shared-logs
      mountPath: /logs            # Sidecar reads from same directory

  # ── Shared Volume ───────────────────────────────────────
  volumes:
  - name: shared-logs
    emptyDir: {}                  # Lives as long as the Pod
```

### 6.3 Multi-Container Pod with localhost Communication

```yaml
# multi-pod-localhost.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-redis-sidecar
spec:
  containers:
  # ── Main App ────────────────────────────────────────────
  - name: app
    image: myapp:1.0
    ports:
    - containerPort: 8080
    env:
    - name: REDIS_HOST
      value: "localhost"          # Talks to redis via localhost
    - name: REDIS_PORT
      value: "6379"

  # ── Redis Sidecar ───────────────────────────────────────
  - name: redis-sidecar
    image: redis:7-alpine
    ports:
    - containerPort: 6379         # Only one container can use port 6379
    resources:
      requests:
        cpu: "50m"
        memory: "64Mi"
      limits:
        cpu: "100m"
        memory: "128Mi"
```

### 6.4 Multi-Container Pod with Init + Sidecar

```yaml
# multi-pod-full.yaml
apiVersion: v1
kind: Pod
metadata:
  name: full-multi-container-pod
  labels:
    app: myapp
    version: "1.0"
spec:
  # ── Init Containers (run BEFORE main containers) ─────────
  initContainers:
  - name: wait-for-database
    image: busybox:1.36
    command: ['sh', '-c',
      'until nc -z postgres-service 5432; do echo waiting for postgres; sleep 2; done']

  - name: run-migrations
    image: myapp:1.0
    command: ['python', 'manage.py', 'migrate']
    env:
    - name: DB_HOST
      value: postgres-service

  # ── Main Containers (run AFTER all init containers) ──────
  containers:
  # Primary App
  - name: app
    image: myapp:1.0
    ports:
    - containerPort: 8000
    env:
    - name: DB_HOST
      value: postgres-service
    - name: CACHE_HOST
      value: localhost             # Redis sidecar
    resources:
      requests:
        cpu: "200m"
        memory: "256Mi"
      limits:
        cpu: "500m"
        memory: "512Mi"
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8000
      initialDelaySeconds: 30
      periodSeconds: 10
    readinessProbe:
      httpGet:
        path: /ready
        port: 8000
      initialDelaySeconds: 10
      periodSeconds: 5
    volumeMounts:
    - name: app-logs
      mountPath: /app/logs

  # Redis Cache Sidecar
  - name: redis
    image: redis:7-alpine
    ports:
    - containerPort: 6379
    resources:
      requests:
        cpu: "50m"
        memory: "64Mi"
      limits:
        cpu: "100m"
        memory: "128Mi"

  # Log Shipper Sidecar
  - name: log-shipper
    image: fluent/fluent-bit:2.1
    volumeMounts:
    - name: app-logs
      mountPath: /logs
    - name: fluent-config
      mountPath: /fluent-bit/etc

  volumes:
  - name: app-logs
    emptyDir: {}
  - name: fluent-config
    configMap:
      name: fluent-bit-config

  restartPolicy: Always
```

---

## 7. Sidecar Pattern — Deep Dive

The **Sidecar** runs alongside the main container and **enhances its functionality** without the main container knowing.

```
┌────────────────────────────────┐
│             POD                │
│  ┌──────────┐  ┌────────────┐ │
│  │   Main   │  │  Sidecar   │ │
│  │  (nginx) │  │(log-shipper│ │
│  │          │  │ /fluentd)  │ │
│  └────┬─────┘  └──────┬─────┘ │
│       │               │       │
│  ┌────▼───────────────▼─────┐ │
│  │       emptyDir volume    │ │
│  └──────────────────────────┘ │
└────────────────────────────────┘
```

### Real Use Cases for Sidecar
- **Log shipping**: App writes logs → Sidecar ships to Elasticsearch/S3
- **Config sync**: Sidecar pulls config from Git/Vault → writes to shared volume
- **TLS certificate rotation**: Sidecar refreshes certs without restarting app
- **Metrics collection**: Prometheus exporter sidecar alongside app

### Sidecar: Log Aggregation with Fluentd

```yaml
# sidecar-log-aggregation.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-fluentd-sidecar
spec:
  containers:
  - name: app
    image: nginx:1.25
    ports:
    - containerPort: 80
    volumeMounts:
    - name: logs
      mountPath: /var/log/nginx

  - name: fluentd
    image: fluent/fluentd:v1.16
    env:
    - name: FLUENTD_ARGS
      value: --no-supervisor -q
    volumeMounts:
    - name: logs
      mountPath: /var/log/nginx     # Same path as app
      readOnly: true                # Sidecar only reads

  volumes:
  - name: logs
    emptyDir: {}
```

### Sidecar: Git Sync (Config Refresh)

```yaml
# sidecar-git-sync.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-git-sync
spec:
  containers:
  - name: app
    image: myapp:1.0
    volumeMounts:
    - name: config-dir
      mountPath: /app/config       # App reads config from here

  - name: git-sync
    image: registry.k8s.io/git-sync/git-sync:v4.1.0
    env:
    - name: GITSYNC_REPO
      value: "https://github.com/myorg/app-config.git"
    - name: GITSYNC_BRANCH
      value: "main"
    - name: GITSYNC_PERIOD
      value: "30s"                  # Sync every 30 seconds
    - name: GITSYNC_ROOT
      value: /git
    volumeMounts:
    - name: config-dir
      mountPath: /git               # Git sync writes here

  volumes:
  - name: config-dir
    emptyDir: {}
```

---

## 8. Ambassador Pattern — Deep Dive

The **Ambassador** acts as a **proxy** that handles all outbound connections on behalf of the main container. The main container always connects to `localhost`, and the ambassador routes traffic to the right external destination.

```
┌──────────────────────────────────────────┐
│                   POD                    │
│                                          │
│  ┌──────────┐     ┌───────────────────┐ │
│  │   App    │────►│    Ambassador     │ │
│  │          │     │    (Envoy/Nginx)  │ │
│  │ connects │     │                  │ │
│  │  to      │     │  Routes to:      │ │
│  │ localhost│     │  - prod DB       │ │
│  │  :5432   │     │  - test DB       │ │
│  └──────────┘     │  - staging DB    │ │
│                   └────────┬──────────┘ │
└────────────────────────────┼────────────┘
                             │
                         External DBs / Services
```

### Ambassador: Database Proxy

```yaml
# ambassador-db-proxy.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-db-ambassador
spec:
  containers:
  - name: app
    image: myapp:1.0
    env:
    - name: DB_HOST
      value: "localhost"         # Always connect to localhost
    - name: DB_PORT
      value: "5432"

  - name: db-ambassador
    image: haproxy:2.8
    ports:
    - containerPort: 5432
    volumeMounts:
    - name: haproxy-config
      mountPath: /usr/local/etc/haproxy

  volumes:
  - name: haproxy-config
    configMap:
      name: haproxy-config       # HAProxy routes localhost:5432 → real DB
```

### Ambassador: Envoy Proxy (Service Mesh sidecar)

```yaml
# ambassador-envoy.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-envoy
  annotations:
    sidecar.istio.io/inject: "true"   # Istio auto-injects Envoy
spec:
  containers:
  - name: app
    image: myapp:1.0
    ports:
    - containerPort: 8080

  # Envoy is injected automatically by Istio, but can be manual:
  - name: envoy
    image: envoyproxy/envoy:v1.28
    ports:
    - containerPort: 9901       # Admin port
    - containerPort: 10000      # Proxy port
    volumeMounts:
    - name: envoy-config
      mountPath: /etc/envoy

  volumes:
  - name: envoy-config
    configMap:
      name: envoy-config
```

---

## 9. Adapter Pattern — Deep Dive

The **Adapter** transforms the output of the main container into a format expected by an external system — without changing the main container.

```
┌─────────────────────────────────────────────────┐
│                     POD                         │
│                                                 │
│  ┌──────────────┐     ┌───────────────────────┐│
│  │  App (legacy)│────►│       Adapter         ││
│  │              │     │                       ││
│  │ Outputs logs │     │  Converts:            ││
│  │ in custom    │     │  custom → Prometheus  ││
│  │ format       │     │  format               ││
│  └──────────────┘     └───────────┬───────────┘│
└───────────────────────────────────┼────────────┘
                                    │
                             Prometheus / Grafana
```

### Adapter: Prometheus Metrics Exporter

```yaml
# adapter-prometheus-exporter.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-metrics-adapter
  labels:
    app: legacy-app
spec:
  containers:
  - name: legacy-app
    image: legacy-app:1.0
    ports:
    - containerPort: 8080
    # App exposes metrics in a non-Prometheus format at /metrics-custom

  - name: prometheus-adapter
    image: nginx/nginx-prometheus-exporter:0.11
    ports:
    - containerPort: 9113           # Prometheus scrapes this port
    env:
    - name: SCRAPE_URI
      value: "http://localhost:8080/metrics-custom"
    # Adapter converts custom format → Prometheus format
```

### Adapter: Log Format Normalization

```yaml
# adapter-log-normalizer.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-log-adapter
spec:
  containers:
  - name: app
    image: old-java-app:1.0
    volumeMounts:
    - name: logs
      mountPath: /app/logs         # Writes in Apache Combined format

  - name: log-adapter
    image: fluent/fluent-bit:2.1
    command: ['fluent-bit', '-c', '/etc/fluent-bit/fluent-bit.conf']
    volumeMounts:
    - name: logs
      mountPath: /logs
      readOnly: true
    - name: fb-config
      mountPath: /etc/fluent-bit   # Config converts Apache → JSON

  volumes:
  - name: logs
    emptyDir: {}
  - name: fb-config
    configMap:
      name: fluent-bit-config
```

---

## 10. Init Containers vs Sidecar Containers

This is a very common CKA and interview topic:

| Feature | Init Container | Sidecar Container |
|---------|---------------|-------------------|
| **When it runs** | Before main containers start | Alongside main containers |
| **Lifecycle** | Runs to **completion** then stops | Runs for the **entire Pod lifetime** |
| **Must succeed?** | Yes — if it fails, Pod restarts | No — main container can run independently |
| **Run order** | Sequential (one by one) | Parallel (all start together) |
| **Use case** | Setup tasks, preconditions | Ongoing helpers (logging, proxying) |
| **Access to volumes** | Yes (prepare data) | Yes (share data at runtime) |

```
Timeline:
──────────────────────────────────────────────────────────►
[  Init1  ] [  Init2  ] |──── App Container (running) ────|
                         |──── Sidecar (running)      ────|
```

### Init Container Example (sequential setup)

```yaml
# init-then-sidecar.yaml
apiVersion: v1
kind: Pod
metadata:
  name: init-then-sidecar
spec:
  initContainers:
  - name: init-fetch-config
    image: busybox
    command: ['sh', '-c', 'wget -O /config/app.conf http://config-server/app.conf']
    volumeMounts:
    - name: config-vol
      mountPath: /config

  containers:
  - name: app
    image: myapp:1.0
    volumeMounts:
    - name: config-vol
      mountPath: /app/config      # Config already there when app starts

  - name: config-refresher         # Sidecar keeps config up-to-date
    image: busybox
    command: ['sh', '-c',
      'while true; do wget -O /config/app.conf http://config-server/app.conf; sleep 60; done']
    volumeMounts:
    - name: config-vol
      mountPath: /config

  volumes:
  - name: config-vol
    emptyDir: {}
```

---

## 11. Real-World Use Cases

### Use Case 1: Istio Service Mesh (Envoy Sidecar)
Every Pod in an Istio mesh gets an **Envoy proxy** injected as a sidecar. This gives:
- Automatic mTLS between services
- Traffic management (retries, circuit breaking)
- Observability (metrics, tracing)

```
Pod A                          Pod B
┌──────────────────┐          ┌──────────────────┐
│ App │ Envoy      │──mTLS───►│ Envoy │ App      │
└──────────────────┘          └──────────────────┘
```

### Use Case 2: Log Aggregation (EFK Stack)
```
App → writes logs → emptyDir → Fluentd/Fluent-bit sidecar → Elasticsearch
```

### Use Case 3: Vault Agent Injector (Secret Management)
HashiCorp Vault injects a sidecar that:
- Authenticates to Vault
- Writes secrets to a shared volume
- Refreshes secrets before expiry

```yaml
# vault-agent-sidecar (auto-injected by Vault)
annotations:
  vault.hashicorp.com/agent-inject: "true"
  vault.hashicorp.com/role: "myapp"
  vault.hashicorp.com/agent-inject-secret-db-creds: "secret/myapp/db"
```

### Use Case 4: Nginx + Content Sync
```
git-sync sidecar ──► emptyDir ──► Nginx serves static content
(pulls from GitHub)              (reads from emptyDir)
```

```yaml
# nginx-git-content.yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx-git-content
spec:
  containers:
  - name: nginx
    image: nginx:1.25
    ports:
    - containerPort: 80
    volumeMounts:
    - name: www
      mountPath: /usr/share/nginx/html  # Serves content from here

  - name: git-sync
    image: registry.k8s.io/git-sync/git-sync:v4.1.0
    env:
    - name: GITSYNC_REPO
      value: "https://github.com/myorg/website.git"
    - name: GITSYNC_BRANCH
      value: "main"
    - name: GITSYNC_ROOT
      value: /www
    - name: GITSYNC_PERIOD
      value: "60s"
    volumeMounts:
    - name: www
      mountPath: /www                   # Syncs content here

  volumes:
  - name: www
    emptyDir: {}
```

### Use Case 5: Application + Metrics Exporter (Prometheus)

```yaml
# app-with-exporter.yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-metrics
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "9113"
spec:
  containers:
  - name: app
    image: myapp:1.0
    ports:
    - containerPort: 8080

  - name: metrics-exporter
    image: prom/statsd-exporter:v0.24
    ports:
    - containerPort: 9113     # Prometheus scrapes this
    - containerPort: 9125     # App pushes metrics here
    args:
    - "--statsd.listen-udp=:9125"
    - "--web.listen-address=:9113"
```

---

## 12. Inter-Container Communication

### Via localhost (Network)

```yaml
# Containers share the Pod's network namespace
# Container A talks to Container B via localhost + B's port

containers:
- name: frontend
  image: nginx
  # Can reach backend via: localhost:8000

- name: backend
  image: myapp
  ports:
  - containerPort: 8000
```

```bash
# Test from inside frontend container:
kubectl exec -it multi-pod -c frontend -- curl localhost:8000/api
```

### Via Shared Volume (Filesystem)

```yaml
containers:
- name: writer
  image: busybox
  command: ['sh', '-c', 'while true; do date >> /shared/data.txt; sleep 1; done']
  volumeMounts:
  - name: shared
    mountPath: /shared

- name: reader
  image: busybox
  command: ['sh', '-c', 'tail -f /shared/data.txt']
  volumeMounts:
  - name: shared
    mountPath: /shared         # Same volume, same directory

volumes:
- name: shared
  emptyDir: {}
```

### Via Unix Socket (IPC)

```yaml
# Containers share IPC namespace via:
# spec.hostIPC: true  (for node-level IPC sharing)
# or via shared volume for socket files

containers:
- name: app
  image: myapp
  volumeMounts:
  - name: socket-dir
    mountPath: /var/run/app    # App creates /var/run/app/app.sock

- name: agent
  image: myagent
  volumeMounts:
  - name: socket-dir
    mountPath: /var/run/app    # Agent reads /var/run/app/app.sock

volumes:
- name: socket-dir
  emptyDir: {}
```

---

## 13. Advantages and Disadvantages

### Advantages

| Advantage | Details |
|-----------|---------|
| **Tight coupling when needed** | Processes that must share data/network co-exist naturally |
| **Independent image updates** | Update sidecar (fluentd version) without rebuilding main app |
| **Separation of concerns** | Main app handles business logic; sidecar handles infra concerns |
| **Reusability** | Same sidecar image used across many different app Pods |
| **Shared localhost** | No service discovery overhead — direct localhost:port communication |
| **Shared volume** | Zero-copy file sharing between containers |
| **Single scheduling unit** | Guaranteed to be on the same node — low-latency communication |

### Disadvantages / When to Avoid

| Disadvantage | Details |
|--------------|---------|
| **Coupled scaling** | All containers in the Pod scale together — can't scale sidecar independently |
| **Shared fate** | If Pod crashes, all containers restart |
| **Resource overhead** | Each sidecar consumes CPU/memory from the same node |
| **Port conflicts** | Containers share network — can't reuse the same port |
| **Complexity** | Debugging multi-container Pods is harder than single-container |
| **Not for microservices** | Don't use it to co-locate separate microservices — use Services instead |

---

## 14. Useful kubectl Commands

```bash
# ── Create ─────────────────────────────────────────────────
kubectl apply -f multi-pod.yaml

# ── Get Status ─────────────────────────────────────────────
kubectl get pod multi-pod
# READY: 2/2 means both containers are running

kubectl get pod multi-pod -o wide
kubectl get pod multi-pod -o yaml

# ── See all containers in a pod ────────────────────────────
kubectl get pod multi-pod -o jsonpath='{.spec.containers[*].name}'

# Describe shows all containers separately
kubectl describe pod multi-pod

# ── Logs ───────────────────────────────────────────────────
kubectl logs multi-pod                         # First container (default)
kubectl logs multi-pod -c app                  # Specific container
kubectl logs multi-pod -c log-sidecar          # Sidecar logs
kubectl logs -f multi-pod -c log-sidecar       # Follow sidecar logs
kubectl logs multi-pod --all-containers=true   # All containers at once
kubectl logs multi-pod --previous -c app       # Previous crashed container

# ── Exec ───────────────────────────────────────────────────
kubectl exec -it multi-pod -- bash                 # First container
kubectl exec -it multi-pod -c sidecar -- sh        # Specific container
kubectl exec multi-pod -c app -- env               # Non-interactive command

# ── Test inter-container communication ─────────────────────
kubectl exec -it multi-pod -c sidecar -- wget -qO- localhost:80

# ── Check container statuses ───────────────────────────────
kubectl get pod multi-pod -o jsonpath='{range .status.containerStatuses[*]}{.name}: {.state}{"\n"}{end}'

# ── Events ─────────────────────────────────────────────────
kubectl get events --field-selector involvedObject.name=multi-pod

# ── Delete ─────────────────────────────────────────────────
kubectl delete pod multi-pod
kubectl delete -f multi-pod.yaml
```

---

## 15. Common Interview Questions

---

**Q: What is a multi-container Pod in Kubernetes?**
> A Pod that runs more than one container simultaneously. All containers share the same network namespace (IP, localhost), storage volumes, and lifecycle. Used when processes are tightly coupled and need to communicate via localhost or share files directly.

---

**Q: What are the three design patterns for multi-container Pods?**
> 1. **Sidecar** — enhances the main container (e.g., log shipper, config sync)
> 2. **Ambassador** — proxies outbound traffic for the main container (e.g., Envoy, HAProxy)
> 3. **Adapter** — transforms main container's output to a standard format (e.g., Prometheus exporter)

---

**Q: How do containers within the same Pod communicate?**
> Via `localhost` — they share the same network namespace. Container A can reach Container B at `localhost:<port>`. They also communicate through **shared volumes** (one writes, another reads).

---

**Q: What is the difference between an init container and a sidecar container?**
> - **Init container**: Runs before main containers start, must complete successfully, then stops. Used for setup tasks.
> - **Sidecar container**: Runs alongside main containers for the entire Pod lifetime. Used for ongoing support tasks like logging or proxying.

---

**Q: Can two containers in the same Pod use the same port?**
> No. They share the same network namespace, so port conflicts apply just as they would on a single host. Each container must use a unique port.

---

**Q: When would you NOT use a multi-container Pod?**
> - When containers need to scale independently
> - When containers are separate microservices
> - When containers don't need to share localhost or volumes
> In those cases, use separate Pods connected by Kubernetes Services.

---

**Q: How does Istio use multi-container Pods?**
> Istio automatically injects an **Envoy proxy sidecar** into every Pod. This sidecar handles all incoming/outgoing traffic — enabling mTLS, load balancing, retries, and observability — without changing the application container.

---

**Q: What volume type is commonly used to share data between containers in a Pod?**
> `emptyDir` — created when the Pod starts, deleted when the Pod ends. Perfect for temporary shared storage between containers in the same Pod.

---

**Q: What does `READY: 2/2` mean in kubectl get pods output?**
> Both containers in the Pod are in the **Ready** state. `2/2` = 2 containers ready out of 2 total. `1/2` would mean only one container is ready (e.g., sidecar hasn't started yet).

---

**Q: Can containers in the same Pod have different restart policies?**
> No. The `restartPolicy` is set at the **Pod level** and applies to all containers in that Pod. You cannot set different restart policies per container.

---

**Q: In the CKA exam, how do you quickly create a multi-container Pod?**
> 1. Generate base YAML: `kubectl run my-pod --image=nginx --dry-run=client -o yaml > pod.yaml`
> 2. Edit the YAML to add the second container under `spec.containers`
> 3. Apply: `kubectl apply -f pod.yaml`
>
> The `-c` flag is critical for targeting specific containers: `kubectl logs`, `kubectl exec -c <container-name>`

---

*Notes by ITkannadigaru | CKA 2026 Certification*

# Complete Guide to Kubernetes Pods

## Table of Contents
1. [What is a Pod?](#1-what-is-a-pod)
2. [Pod vs Container](#2-pod-vs-container)
3. [Imperative Way — Creating Pods](#3-imperative-way--creating-pods)
4. [Declarative Way — Creating Pods](#4-declarative-way--creating-pods)
5. [Full Pod YAML Reference](#5-full-pod-yaml-reference)
6. [Pod Lifecycle](#6-pod-lifecycle)
7. [Pod Phases](#7-pod-phases)
8. [Container States](#8-container-states)
9. [Restart Policies](#9-restart-policies)
10. [Init Containers](#10-init-containers)
11. [Multi-Container Pods (Sidecar Pattern)](#11-multi-container-pods-sidecar-pattern)
12. [Resource Requests and Limits](#12-resource-requests-and-limits)
13. [Probes — Liveness, Readiness, Startup](#13-probes--liveness-readiness-startup)
14. [Environment Variables](#14-environment-variables)
15. [Volumes in Pods](#15-volumes-in-pods)
16. [Node Scheduling — nodeSelector & nodeName](#16-node-scheduling--nodeselector--nodename)
17. [Security Context](#17-security-context)
18. [Pod with ConfigMap and Secret](#18-pod-with-configmap-and-secret)
19. [Static Pods](#19-static-pods)
20. [Useful kubectl Commands for Pods](#20-useful-kubectl-commands-for-pods)
21. [Common Interview Questions](#21-common-interview-questions)

---

## 1. What is a Pod?

A **Pod** is the **smallest and most basic deployable unit** in Kubernetes.

- A Pod wraps **one or more containers** that share:
  - The **same network namespace** (same IP address, same ports)
  - The **same storage volumes**
  - The **same lifecycle** (started and stopped together)

- Every Pod gets a **unique IP address** inside the cluster.
- Containers inside a Pod talk to each other via `localhost`.

```
┌─────────────────────────────────┐
│              POD                │
│   ┌───────────┐ ┌───────────┐  │
│   │ Container │ │ Container │  │
│   │   (app)   │ │ (sidecar) │  │
│   └───────────┘ └───────────┘  │
│         Shared Network & Storage│
│         IP: 10.244.0.5          │
└─────────────────────────────────┘
```

> **Key rule**: One Pod = One application instance. For scaling, you run multiple Pods (not multiple containers in one Pod).

---

## 2. Pod vs Container

| Feature | Container | Pod |
|---------|-----------|-----|
| Unit | Docker/OCI container | Kubernetes abstraction |
| Network | Own namespace | Shared namespace within Pod |
| Scheduling | Not scheduled directly | Scheduled on a Node |
| IP Address | Container-level | Pod-level (shared by all containers) |
| Lifecycle | Managed by container runtime | Managed by Kubernetes |

---

## 3. Imperative Way — Creating Pods

Imperative = **run commands directly** without writing YAML files.
Good for: quick testing, learning, debugging.

### 3.1 Run a basic Pod

```bash
kubectl run my-pod --image=nginx
```

### 3.2 Run a Pod and expose a port

```bash
kubectl run my-pod --image=nginx --port=80
```

### 3.3 Run a Pod with environment variables

```bash
kubectl run my-pod --image=nginx --env="ENV=production" --env="APP=myapp"
```

### 3.4 Run a Pod with resource limits

```bash
kubectl run my-pod --image=nginx --requests='cpu=100m,memory=128Mi' --limits='cpu=500m,memory=256Mi'
```

### 3.5 Run a Pod with labels

```bash
kubectl run my-pod --image=nginx --labels="app=web,env=prod"
```

### 3.6 Run a Pod in a specific namespace

```bash
kubectl run my-pod --image=nginx --namespace=dev
```

### 3.7 Generate YAML without creating (dry-run)

```bash
# Output YAML to terminal
kubectl run my-pod --image=nginx --dry-run=client -o yaml

# Save YAML to a file
kubectl run my-pod --image=nginx --dry-run=client -o yaml > pod.yaml
```

> **Tip for CKA exam**: Use `--dry-run=client -o yaml` to quickly generate base YAML and then edit it. This saves a lot of time.

### 3.8 Run a Pod interactively (bash shell)

```bash
# Run and get an interactive terminal
kubectl run -it --rm debug-pod --image=busybox -- sh

# After shell exits, Pod is automatically deleted (--rm flag)
```

### 3.9 Override command

```bash
kubectl run my-pod --image=busybox -- sleep 3600
```

### 3.10 Delete a Pod imperatively

```bash
kubectl delete pod my-pod

# Delete immediately (force)
kubectl delete pod my-pod --grace-period=0 --force
```

---

## 4. Declarative Way — Creating Pods

Declarative = **write a YAML file** and apply it with kubectl.
Good for: production, version control, repeatability.

### 4.1 Minimal Pod

```yaml
# pod-minimal.yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx-pod
spec:
  containers:
  - name: nginx
    image: nginx:1.25
```

```bash
kubectl apply -f pod-minimal.yaml
```

### 4.2 Pod with labels and annotations

```yaml
# pod-with-labels.yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-pod
  namespace: default
  labels:
    app: web
    env: production
    tier: frontend
    version: "1.0"
  annotations:
    description: "Main web server pod"
    owner: "team-alpha"
    git-commit: "abc123"
spec:
  containers:
  - name: nginx
    image: nginx:1.25
    ports:
    - containerPort: 80
```

### 4.3 Apply, Update, Delete

```bash
# Create or update
kubectl apply -f pod.yaml

# Delete using the same file
kubectl delete -f pod.yaml

# Replace (destructive - deletes and recreates)
kubectl replace -f pod.yaml

# Replace forcefully
kubectl replace --force -f pod.yaml
```

---

## 5. Full Pod YAML Reference

Below is a comprehensive Pod YAML showing all major fields:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: full-example-pod           # Name of the Pod
  namespace: default               # Namespace (default if not specified)
  labels:                          # Key-value pairs for selection/filtering
    app: myapp
    env: production
    tier: frontend
  annotations:                     # Non-identifying metadata (not used for selection)
    description: "Full example pod"
    owner: "devops-team"

spec:
  # ── Scheduling ──────────────────────────────────────────
  nodeName: node01                 # Assign directly to a specific node (bypasses scheduler)
  nodeSelector:                    # Schedule on nodes with these labels
    disktype: ssd
    region: us-east

  # ── Init Containers (run before main containers) ─────────
  initContainers:
  - name: init-db
    image: busybox
    command: ['sh', '-c', 'until nslookup mydb; do echo waiting; sleep 2; done']

  # ── Main Containers ──────────────────────────────────────
  containers:
  - name: app-container            # Container name (unique within the Pod)
    image: nginx:1.25              # Image with tag (always pin the tag!)
    imagePullPolicy: Always        # Always | Never | IfNotPresent

    # Ports
    ports:
    - name: http
      containerPort: 80            # Port the container listens on
      protocol: TCP

    # Command and Args (override Docker CMD/ENTRYPOINT)
    command: ["/bin/sh"]           # Overrides ENTRYPOINT
    args: ["-c", "nginx -g 'daemon off;'"]  # Overrides CMD

    # Environment Variables
    env:
    - name: APP_ENV
      value: "production"
    - name: DB_HOST
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: db_host
    - name: DB_PASSWORD
      valueFrom:
        secretKeyRef:
          name: app-secret
          key: password

    # Resource Requests and Limits
    resources:
      requests:                    # Minimum guaranteed resources
        cpu: "100m"                # 100 millicores = 0.1 CPU
        memory: "128Mi"
      limits:                      # Maximum allowed resources
        cpu: "500m"
        memory: "256Mi"

    # Volume Mounts
    volumeMounts:
    - name: config-volume
      mountPath: /etc/config
      readOnly: true
    - name: data-volume
      mountPath: /var/data

    # Liveness Probe — restart if unhealthy
    livenessProbe:
      httpGet:
        path: /healthz
        port: 80
      initialDelaySeconds: 10      # Wait before first probe
      periodSeconds: 10            # How often to probe
      timeoutSeconds: 5            # Probe timeout
      failureThreshold: 3          # Failures before restart

    # Readiness Probe — remove from Service if not ready
    readinessProbe:
      httpGet:
        path: /ready
        port: 80
      initialDelaySeconds: 5
      periodSeconds: 5

    # Startup Probe — for slow-starting apps
    startupProbe:
      httpGet:
        path: /started
        port: 80
      failureThreshold: 30
      periodSeconds: 10

    # Security Context (container-level)
    securityContext:
      runAsUser: 1000              # Run as user ID 1000
      runAsNonRoot: true           # Enforce non-root
      allowPrivilegeEscalation: false
      readOnlyRootFilesystem: true

  # ── Sidecar Container ────────────────────────────────────
  - name: log-sidecar
    image: busybox
    command: ['sh', '-c', 'tail -f /var/log/app.log']
    volumeMounts:
    - name: log-volume
      mountPath: /var/log

  # ── Volumes ──────────────────────────────────────────────
  volumes:
  - name: config-volume
    configMap:
      name: app-config
  - name: data-volume
    emptyDir: {}                   # Temporary storage, deleted with Pod
  - name: log-volume
    hostPath:
      path: /var/log/myapp
      type: DirectoryOrCreate

  # ── Pod-level Security Context ───────────────────────────
  securityContext:
    runAsUser: 1000
    runAsGroup: 3000
    fsGroup: 2000                  # Group for volume ownership

  # ── Restart Policy ───────────────────────────────────────
  restartPolicy: Always            # Always | OnFailure | Never

  # ── DNS Config ───────────────────────────────────────────
  dnsPolicy: ClusterFirst          # ClusterFirst | Default | None | ClusterFirstWithHostNet

  # ── Service Account ──────────────────────────────────────
  serviceAccountName: default

  # ── Image Pull Secrets (for private registries) ──────────
  imagePullSecrets:
  - name: registry-secret

  # ── Tolerations (allow Pod on tainted nodes) ─────────────
  tolerations:
  - key: "dedicated"
    operator: "Equal"
    value: "gpu"
    effect: "NoSchedule"

  # ── Affinity ─────────────────────────────────────────────
  affinity:
    nodeAffinity:
      requiredDuringSchedulingIgnoredDuringExecution:
        nodeSelectorTerms:
        - matchExpressions:
          - key: kubernetes.io/os
            operator: In
            values:
            - linux
```

---

## 6. Pod Lifecycle

Understanding how Kubernetes handles a Pod from creation to termination:

```
kubectl apply -f pod.yaml
        │
        ▼
┌─────────────────┐
│   API Server    │ ← Validates & stores in etcd
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    Scheduler    │ ← Finds best Node for the Pod
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│    kubelet      │ ← On the chosen Node, pulls image & starts containers
└────────┬────────┘
         │
         ▼
┌─────────────────┐
│ Container       │
│ Runtime         │ ← (containerd/CRI-O) actually runs the container
└────────┬────────┘
         │
         ▼
    Pod Running
         │
         ▼ (kubectl delete or failure)
┌─────────────────┐
│  Terminating    │ ← SIGTERM sent, grace period (default 30s)
└────────┬────────┘
         │
         ▼
    Pod Deleted
```

### Lifecycle Events in Detail

| Stage | Description |
|-------|-------------|
| **Pending** | Pod accepted by API server, but containers not started yet (may be scheduling or pulling image) |
| **Running** | At least one container is running |
| **Succeeded** | All containers exited with code 0 (success) |
| **Failed** | At least one container exited with non-zero code |
| **Unknown** | Pod state cannot be determined (node communication issue) |

### Termination Flow (Graceful Shutdown)

```
kubectl delete pod my-pod
        │
        ▼
1. Pod set to "Terminating" state
2. Removed from Service Endpoints (no more traffic)
3. preStop hook runs (if defined)
4. SIGTERM sent to container process
5. Grace period starts (default: 30 seconds)
6. If container still running after grace period → SIGKILL
7. Pod removed from etcd
```

**Custom grace period:**
```bash
kubectl delete pod my-pod --grace-period=60    # 60 second grace period
kubectl delete pod my-pod --grace-period=0 --force  # Immediate force delete
```

---

## 7. Pod Phases

```bash
# Check current phase
kubectl get pod my-pod -o jsonpath='{.status.phase}'
```

| Phase | Meaning |
|-------|---------|
| `Pending` | Waiting to be scheduled or image being pulled |
| `Running` | Bound to a node, all containers created, at least one running |
| `Succeeded` | All containers terminated with exit code 0, won't restart |
| `Failed` | All containers terminated, at least one failed (exit code != 0) |
| `Unknown` | Cannot determine state (usually node issue) |

---

## 8. Container States

Each container inside a Pod has its own state:

```bash
kubectl describe pod my-pod | grep -A 5 "State:"
```

| State | Description |
|-------|-------------|
| `Waiting` | Not running yet — pulling image or waiting for dependency |
| `Running` | Executing, with `startedAt` timestamp |
| `Terminated` | Completed or crashed — shows `exitCode`, `reason`, `startedAt`, `finishedAt` |

**Common reasons for `Waiting` state:**
- `ContainerCreating` — image pull in progress
- `ImagePullBackOff` — image pull failed (wrong image name/tag or auth issue)
- `CrashLoopBackOff` — container keeps crashing and restarting
- `ErrImagePull` — cannot reach registry

---

## 9. Restart Policies

Defined at the Pod level and applies to all containers:

```yaml
spec:
  restartPolicy: Always   # Default
```

| Policy | Behavior | Use Case |
|--------|----------|----------|
| `Always` | Restart container whenever it exits (success or failure) | Long-running apps (web servers, APIs) |
| `OnFailure` | Restart only if exit code is non-zero | Batch jobs, scripts |
| `Never` | Never restart, regardless of exit code | One-time tasks, CI pipeline steps |

```bash
# Check restart count
kubectl get pod my-pod
# RESTARTS column shows how many times containers have restarted
```

---

## 10. Init Containers

Init containers **run and complete before** the main containers start.

**Key characteristics:**
- Run sequentially (one after another)
- All init containers must succeed before main containers start
- If an init container fails, the Pod restarts (based on restartPolicy)
- They can have different images from main containers

### Use Cases
- Wait for a database to be ready
- Pre-populate a volume with data
- Run migrations
- Download configuration files

### Example: Wait for a service before starting app

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-init
spec:
  initContainers:
  - name: wait-for-db
    image: busybox:1.36
    command: ['sh', '-c',
      'until nc -z mydb-service 5432; do echo "waiting for db..."; sleep 2; done; echo "DB is up!"']

  - name: run-migrations
    image: myapp:latest
    command: ['python', 'manage.py', 'migrate']
    env:
    - name: DB_HOST
      value: mydb-service

  containers:
  - name: app
    image: myapp:latest
    ports:
    - containerPort: 8000
```

**Check init container status:**
```bash
kubectl describe pod app-with-init
# Look for "Init Containers:" section

kubectl get pod app-with-init
# Shows: Init:0/2 (waiting), Init:1/2 (first done), PodInitializing, Running
```

---

## 11. Multi-Container Pods (Sidecar Pattern)

Multiple containers in one Pod **share network and volumes**.

### Common Patterns

| Pattern | Description | Example |
|---------|-------------|---------|
| **Sidecar** | Enhances main container | Log shipper, sync agent |
| **Ambassador** | Proxy for main container | Envoy proxy |
| **Adapter** | Transform output of main container | Log formatter |

### Example: App + Log Sidecar

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-with-sidecar
spec:
  containers:
  # Main application container
  - name: app
    image: nginx:1.25
    volumeMounts:
    - name: shared-logs
      mountPath: /var/log/nginx

  # Sidecar: ships logs to external system
  - name: log-shipper
    image: busybox
    command: ['sh', '-c', 'tail -F /logs/access.log']
    volumeMounts:
    - name: shared-logs
      mountPath: /logs

  volumes:
  - name: shared-logs
    emptyDir: {}
```

### Inter-Container Communication

```yaml
# Containers in same Pod talk via localhost
- name: app
  image: myapp
  env:
  - name: CACHE_HOST
    value: "localhost"  # sidecar redis running in same Pod

- name: redis-sidecar
  image: redis:7
  ports:
  - containerPort: 6379
```

---

## 12. Resource Requests and Limits

| Field | Meaning |
|-------|---------|
| `requests.cpu` | Minimum CPU guaranteed. Used for scheduling. |
| `requests.memory` | Minimum memory guaranteed. Used for scheduling. |
| `limits.cpu` | Maximum CPU. Container is throttled if it exceeds this. |
| `limits.memory` | Maximum memory. Container is OOMKilled if it exceeds this. |

### CPU Units
- `1` = 1 full CPU core
- `500m` = 500 millicores = 0.5 CPU
- `100m` = 0.1 CPU

### Memory Units
- `128Mi` = 128 mebibytes
- `1Gi` = 1 gibibyte
- `512M` = 512 megabytes

```yaml
resources:
  requests:
    cpu: "100m"
    memory: "128Mi"
  limits:
    cpu: "500m"
    memory: "256Mi"
```

```bash
# Check resource usage
kubectl top pod my-pod
kubectl top pod my-pod --containers
```

### QoS Classes (determined by requests/limits)

| Class | Condition | Eviction Priority |
|-------|-----------|-------------------|
| `Guaranteed` | requests == limits for all containers | Last evicted |
| `Burstable` | requests < limits, or only requests set | Middle |
| `BestEffort` | No requests or limits set | First evicted |

```bash
kubectl describe pod my-pod | grep "QoS Class"
```

---

## 13. Probes — Liveness, Readiness, Startup

### Liveness Probe
- **Purpose**: Detect if container is alive. If it fails → container is **restarted**.
- Use when: app can get into a deadlock state (not crashed but not working)

### Readiness Probe
- **Purpose**: Detect if container is ready to accept traffic. If it fails → Pod is **removed from Service endpoints** (no traffic sent).
- Use when: app needs time to warm up (load cache, connect to DB)

### Startup Probe
- **Purpose**: For slow-starting containers. Disables liveness/readiness probes until startup completes.
- Use when: app has a long initialization time

### Probe Types

**HTTP GET** (most common):
```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
    httpHeaders:
    - name: Custom-Header
      value: Awesome
  initialDelaySeconds: 10
  periodSeconds: 10
  timeoutSeconds: 5
  successThreshold: 1
  failureThreshold: 3
```

**TCP Socket**:
```yaml
readinessProbe:
  tcpSocket:
    port: 3306
  initialDelaySeconds: 5
  periodSeconds: 10
```

**Exec Command**:
```yaml
livenessProbe:
  exec:
    command:
    - cat
    - /tmp/healthy
  initialDelaySeconds: 5
  periodSeconds: 5
```

### Probe Parameters Explained

| Parameter | Default | Description |
|-----------|---------|-------------|
| `initialDelaySeconds` | 0 | Seconds to wait after container starts before probing |
| `periodSeconds` | 10 | How often (seconds) to perform the probe |
| `timeoutSeconds` | 1 | Seconds after which probe times out |
| `successThreshold` | 1 | Min consecutive successes to be considered healthy |
| `failureThreshold` | 3 | Min consecutive failures before taking action |

---

## 14. Environment Variables

### Inline Value
```yaml
env:
- name: APP_ENV
  value: "production"
- name: LOG_LEVEL
  value: "debug"
```

### From ConfigMap
```yaml
env:
- name: DB_HOST
  valueFrom:
    configMapKeyRef:
      name: app-config    # ConfigMap name
      key: database_host  # Key in ConfigMap

# Load ALL keys from ConfigMap
envFrom:
- configMapRef:
    name: app-config
```

### From Secret
```yaml
env:
- name: DB_PASSWORD
  valueFrom:
    secretKeyRef:
      name: app-secret    # Secret name
      key: password       # Key in Secret

# Load ALL keys from Secret
envFrom:
- secretRef:
    name: app-secret
```

### From Pod/Node metadata (Downward API)
```yaml
env:
- name: POD_NAME
  valueFrom:
    fieldRef:
      fieldPath: metadata.name
- name: POD_NAMESPACE
  valueFrom:
    fieldRef:
      fieldPath: metadata.namespace
- name: NODE_NAME
  valueFrom:
    fieldRef:
      fieldPath: spec.nodeName
- name: POD_IP
  valueFrom:
    fieldRef:
      fieldPath: status.podIP
```

---

## 15. Volumes in Pods

### emptyDir — Temporary shared storage
```yaml
volumes:
- name: cache-volume
  emptyDir: {}

# With size limit
- name: cache-volume
  emptyDir:
    sizeLimit: 500Mi
```

### hostPath — Mount from Node filesystem
```yaml
volumes:
- name: host-logs
  hostPath:
    path: /var/log
    type: Directory    # Directory | DirectoryOrCreate | File | FileOrCreate
```

### configMap — Mount ConfigMap as files
```yaml
volumes:
- name: config
  configMap:
    name: app-config
    items:
    - key: app.properties
      path: app.properties
```

### secret — Mount Secret as files
```yaml
volumes:
- name: tls-certs
  secret:
    secretName: tls-secret
    defaultMode: 0400  # File permissions
```

### PersistentVolumeClaim
```yaml
volumes:
- name: persistent-storage
  persistentVolumeClaim:
    claimName: my-pvc
```

---

## 16. Node Scheduling — nodeSelector & nodeName

### nodeName — Direct assignment (bypasses scheduler)
```yaml
spec:
  nodeName: worker-node-1
```

### nodeSelector — Label-based selection
```yaml
spec:
  nodeSelector:
    disktype: ssd
    region: us-east-1
```

```bash
# Add label to a node
kubectl label node worker-1 disktype=ssd

# Verify
kubectl get nodes --show-labels
```

---

## 17. Security Context

### Pod-level
```yaml
spec:
  securityContext:
    runAsUser: 1000       # UID to run all containers
    runAsGroup: 3000      # GID to run all containers
    fsGroup: 2000         # GID for volumes (all files owned by this group)
    runAsNonRoot: true    # Fail if image runs as root
```

### Container-level (overrides Pod-level)
```yaml
containers:
- name: app
  securityContext:
    runAsUser: 1000
    allowPrivilegeEscalation: false
    readOnlyRootFilesystem: true  # Container cannot write to root FS
    capabilities:
      add: ["NET_ADMIN"]
      drop: ["ALL"]
```

---

## 18. Pod with ConfigMap and Secret

### Create ConfigMap imperatively
```bash
kubectl create configmap app-config \
  --from-literal=db_host=localhost \
  --from-literal=db_port=5432

# From file
kubectl create configmap app-config --from-file=config.properties
```

### Create Secret imperatively
```bash
kubectl create secret generic app-secret \
  --from-literal=password=mysecretpassword \
  --from-literal=api_key=myapikey
```

### Use in Pod
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: config-pod
spec:
  containers:
  - name: app
    image: nginx
    envFrom:
    - configMapRef:
        name: app-config
    - secretRef:
        name: app-secret
    volumeMounts:
    - name: config-files
      mountPath: /etc/app/config
  volumes:
  - name: config-files
    configMap:
      name: app-config
```

---

## 19. Static Pods

Static Pods are managed **directly by kubelet** on a specific node, **not by the API server**.

- Definition files placed in: `/etc/kubernetes/manifests/`
- kubelet watches this directory and creates/deletes Pods accordingly
- Control plane components (kube-apiserver, etcd, scheduler, controller-manager) run as static Pods
- Mirror Pod is created in the API server (read-only, cannot be deleted via kubectl)

```bash
# View static pod manifests
ls /etc/kubernetes/manifests/

# To create a static pod
cp my-pod.yaml /etc/kubernetes/manifests/

# kubelet will start it automatically
```

---

## 20. Useful kubectl Commands for Pods

```bash
# ── Create & Run ──────────────────────────────────────────
kubectl run my-pod --image=nginx
kubectl run my-pod --image=nginx --dry-run=client -o yaml > pod.yaml
kubectl apply -f pod.yaml

# ── Get Info ─────────────────────────────────────────────
kubectl get pods
kubectl get pods -o wide                      # Shows Node IP, Node Name
kubectl get pods -o yaml                      # Full YAML output
kubectl get pods -o json                      # Full JSON output
kubectl get pods --all-namespaces             # All namespaces
kubectl get pods -n kube-system               # Specific namespace
kubectl get pods --show-labels                # Show labels column
kubectl get pods -l app=web                   # Filter by label
kubectl get pods --field-selector status.phase=Running

# ── Describe ─────────────────────────────────────────────
kubectl describe pod my-pod                   # Detailed info + events

# ── Logs ─────────────────────────────────────────────────
kubectl logs my-pod                           # Current logs
kubectl logs my-pod -f                        # Follow (stream) logs
kubectl logs my-pod --previous                # Logs from crashed container
kubectl logs my-pod -c sidecar                # Specific container logs
kubectl logs my-pod --tail=50                 # Last 50 lines
kubectl logs my-pod --since=1h                # Logs from last 1 hour

# ── Exec ─────────────────────────────────────────────────
kubectl exec my-pod -- ls /                   # Run a command
kubectl exec -it my-pod -- bash               # Interactive shell
kubectl exec -it my-pod -c sidecar -- sh      # Shell in specific container

# ── Copy Files ───────────────────────────────────────────
kubectl cp my-pod:/var/log/app.log ./app.log  # From pod to local
kubectl cp ./config.yaml my-pod:/etc/config   # From local to pod

# ── Port Forward ─────────────────────────────────────────
kubectl port-forward pod/my-pod 8080:80       # local 8080 → pod 80

# ── Edit ─────────────────────────────────────────────────
kubectl edit pod my-pod                       # Open in editor (limited fields)

# ── Delete ───────────────────────────────────────────────
kubectl delete pod my-pod
kubectl delete pod my-pod --grace-period=0 --force
kubectl delete -f pod.yaml

# ── Watch ────────────────────────────────────────────────
kubectl get pods -w                           # Watch for changes
kubectl get pod my-pod -w

# ── Events ───────────────────────────────────────────────
kubectl get events --sort-by=.metadata.creationTimestamp
kubectl get events -n default --field-selector involvedObject.name=my-pod
```

---

## 21. Common Interview Questions

**Q: What is the difference between a Pod and a Container?**
> A Container is a runtime unit (Docker image running as a process). A Pod is a Kubernetes abstraction that wraps one or more containers, giving them a shared IP, hostname, and storage.

**Q: Can you have multiple containers in a Pod? Why would you?**
> Yes. Use it for tightly-coupled processes that must share data or network (e.g., app + log sidecar, app + proxy).

**Q: What happens when a Pod is deleted?**
> Kubernetes sends SIGTERM to the container, waits for the grace period (default 30s), then sends SIGKILL if still running. The Pod is removed from Service endpoints before SIGTERM.

**Q: What is CrashLoopBackOff?**
> The container keeps crashing on startup and Kubernetes keeps restarting it with exponential backoff (10s, 20s, 40s... up to 5 min).

**Q: What is the difference between Liveness and Readiness probes?**
> Liveness: "Is this container alive?" → fails → container **restarts**.
> Readiness: "Is this container ready for traffic?" → fails → Pod removed from **Service endpoints** (not restarted).

**Q: What is a static Pod?**
> A Pod managed directly by kubelet from a manifest file on disk (`/etc/kubernetes/manifests/`). Not through the API server. Used for control plane components.

**Q: What is init container?**
> A special container that runs and must complete successfully before main app containers start. Used for setup tasks like waiting for services, running migrations.

**Q: What is imagePullPolicy: Always vs IfNotPresent?**
> `Always`: Always pull from registry (even if cached). Good for `latest` tag.
> `IfNotPresent`: Use local cache if available. Good for pinned versions.
> `Never`: Never pull, must exist locally.

---

*Notes by ITkannadigaru | CKA 2026 Certification*

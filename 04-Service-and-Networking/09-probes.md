# Kubernetes Probes — Complete Guide

> Probes are Kubernetes health checks that tell the kubelet whether your container is alive, ready to serve traffic, or still starting up.

---

## Table of Contents

1. [What are Probes?](#1-what-are-probes)
2. [Why Probes Matter](#2-why-probes-matter)
3. [Three Types of Probes](#3-three-types-of-probes)
4. [Four Probe Mechanisms](#4-four-probe-mechanisms)
   - [4.1 HTTP GET](#41-http-get)
   - [4.2 TCP Socket](#42-tcp-socket)
   - [4.3 Exec (Command)](#43-exec-command)
   - [4.4 gRPC](#44-grpc)
5. [Probe Configuration Parameters](#5-probe-configuration-parameters)
6. [Liveness Probe — Deep Dive](#6-liveness-probe--deep-dive)
7. [Readiness Probe — Deep Dive](#7-readiness-probe--deep-dive)
8. [Startup Probe — Deep Dive](#8-startup-probe--deep-dive)
9. [How the Three Probes Work Together](#9-how-the-three-probes-work-together)
10. [Probe Combinations — Best Practices](#10-probe-combinations--best-practices)
11. [Practical Demo](#11-practical-demo)
12. [Probe Failure Behaviour and Debugging](#12-probe-failure-behaviour-and-debugging)
13. [Common Interview Questions](#13-common-interview-questions)
14. [Exam Practice Questions](#14-exam-practice-questions)

---

## 1. What are Probes?

A **probe** is a periodic diagnostic check that the **kubelet** runs on a container to determine its health. Based on probe results, Kubernetes decides whether to restart the container, send it traffic, or wait for it to finish starting up.

```
  kubelet (on each Node)
  ┌───────────────────────────────────────────────────────┐
  │                                                       │
  │  Every N seconds, kubelet probes each container:     │
  │                                                       │
  │  → Is it still alive?         Liveness Probe         │
  │  → Is it ready for traffic?   Readiness Probe        │
  │  → Has it finished starting?  Startup Probe          │
  │                                                       │
  │  Result: Success / Failure / Unknown                  │
  └───────────────────────────────────────────────────────┘
```

**Probe results:**

| Result | Meaning |
|--------|---------|
| **Success** | Container passed the health check |
| **Failure** | Container failed the health check |
| **Unknown** | Probe could not be executed (treated as no action) |

---

## 2. Why Probes Matter

### Without Probes

```
  Scenario 1: App crashes but process stays alive
  ────────────────────────────────────────────────
  Container PID 1 running    ← kubelet thinks it's healthy (process is up)
  App is deadlocked inside   ← but requests hang forever
  No liveness probe          → Kubernetes never restarts it
  Users: 504 Gateway Timeout forever

  Scenario 2: App deployed but not ready yet
  ──────────────────────────────────────────
  Container just started     ← kubelet marks it Running immediately
  App loading DB connections ← not ready to serve yet
  No readiness probe         → Service sends traffic immediately
  Users: connection refused or 500 errors during startup

  Scenario 3: Slow-starting legacy app
  ─────────────────────────────────────
  App takes 90 seconds to start
  Liveness probe set to 10s
  After 10s: liveness fails  → Kubernetes kills and restarts
  After 10s: fails again     → restart loop — app never starts!
```

### With Probes

```
  Scenario 1 fixed: Liveness probe detects deadlock → container restarted
  Scenario 2 fixed: Readiness probe gates traffic → users only reach ready pods
  Scenario 3 fixed: Startup probe gives 90s grace → liveness only starts after
```

---

## 3. Three Types of Probes

```
  Container Lifecycle with Probes:

  t=0s   Container starts
         │
         ├─── Startup Probe begins (if configured)
         │    → Checks if app has finished initialising
         │    → Liveness and Readiness are PAUSED until Startup succeeds
         │
  t=Xs   Startup Probe succeeds (or not configured)
         │
         ├─── Liveness Probe begins  ──► Fail → RESTART container
         │
         └─── Readiness Probe begins ──► Fail → REMOVE from Service endpoints
                                         Pass → ADD to Service endpoints
```

| Probe | Question it answers | On failure |
|-------|--------------------|-----------| 
| **Liveness** | "Is this container alive and functional?" | Restart the container |
| **Readiness** | "Is this container ready to accept traffic?" | Remove from Service endpoints (no traffic sent) |
| **Startup** | "Has this container finished its initial startup?" | Kill and restart (treated like liveness failure) |

---

## 4. Four Probe Mechanisms

Every probe type (liveness, readiness, startup) can use one of these four mechanisms:

---

### 4.1 HTTP GET

kubelet sends an **HTTP GET** request to the container. Any response code **≥ 200 and < 400** = Success. Anything else = Failure.

```yaml
livenessProbe:
  httpGet:
    path: /healthz          # endpoint to call
    port: 8080              # container port (not service port)
    scheme: HTTP            # HTTP (default) or HTTPS
    httpHeaders:            # optional custom headers
    - name: Custom-Header
      value: health-check
```

```
  kubelet  ──── GET /healthz HTTP/1.1 ────►  Container :8080
           ◄── 200 OK ────────────────────
           → Success

  kubelet  ──── GET /healthz HTTP/1.1 ────►  Container :8080
           ◄── 500 Internal Server Error ──
           → Failure (restart / remove from endpoints)

  kubelet  ──── GET /healthz HTTP/1.1 ────►  Container :8080
           ← (no response, timeout)
           → Failure
```

**Best for:** HTTP/HTTPS web apps and APIs. Most common probe mechanism.

---

### 4.2 TCP Socket

kubelet tries to **open a TCP connection** to the specified port. If the connection succeeds = Success. If refused or times out = Failure.

```yaml
livenessProbe:
  tcpSocket:
    port: 3306              # container port to probe
```

```
  kubelet  ──── TCP SYN ────►  Container :3306
           ◄── SYN-ACK ──────
           → Success (TCP handshake completed)

  kubelet  ──── TCP SYN ────►  Container :3306
           ◄── RST / timeout ─
           → Failure
```

**Best for:** Apps that don't have an HTTP health endpoint — databases (MySQL :3306), Redis (:6379), message brokers (:5672).

---

### 4.3 Exec (Command)

kubelet **executes a command inside the container**. Exit code **0** = Success. Any non-zero exit code = Failure.

```yaml
livenessProbe:
  exec:
    command:
    - cat
    - /tmp/healthy          # file exists → exit 0 → Success
                            # file missing → exit 1 → Failure
```

```
  kubelet  ──── exec: cat /tmp/healthy ────►  Container
           ◄── exit code 0 ─────────────────
           → Success

  kubelet  ──── exec: cat /tmp/healthy ────►  Container
           ◄── exit code 1 (no such file) ──
           → Failure
```

**Real-world examples:**

```yaml
# Check if MySQL is accepting connections
exec:
  command:
  - sh
  - -c
  - "mysqladmin ping -h localhost -u root -p$MYSQL_ROOT_PASSWORD"

# Check if Redis is responding
exec:
  command:
  - redis-cli
  - ping
  # exits 0 if Redis replies PONG

# Check if a config file was loaded
exec:
  command:
  - test
  - -f
  - /etc/app/config.yaml
```

**Best for:** Databases, custom checks, any app without HTTP.

---

### 4.4 gRPC

kubelet calls a **gRPC health check** (using the standard gRPC health checking protocol). Status `SERVING` = Success.

```yaml
livenessProbe:
  grpc:
    port: 50051             # gRPC port
    service: ""             # optional: specific gRPC service name (empty = overall health)
```

> **Note**: Your app must implement the [gRPC Health Checking Protocol](https://github.com/grpc/grpc/blob/master/doc/health-checking.md). Available from Kubernetes v1.24+.

**Best for:** gRPC microservices.

---

## 5. Probe Configuration Parameters

Every probe (regardless of mechanism) shares the same set of timing and threshold parameters:

```yaml
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080

  # Timing parameters
  initialDelaySeconds: 15   # Wait this long after container starts before first probe
  periodSeconds: 10         # How often to run the probe (default: 10)
  timeoutSeconds: 5         # Probe times out after this (default: 1)

  # Threshold parameters
  successThreshold: 1       # Consecutive successes needed to be considered healthy
                            # (must be 1 for liveness and startup probes)
  failureThreshold: 3       # Consecutive failures before action is taken (default: 3)
```

### Visual: Parameter Timeline

```
  Container starts
  │
  │◄── initialDelaySeconds (15s) ──►│
  │                                  │
  │                                  probe 1 ──► result
  │                                  │◄── periodSeconds (10s) ──►│
  │                                  │                            probe 2 ──► result
  │                                  │                            │
  │                               (each probe has timeoutSeconds to complete)
  │
  After failureThreshold (3) consecutive failures → action taken
```

### Parameter Reference

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `initialDelaySeconds` | 0 | Seconds to wait after container starts before first probe |
| `periodSeconds` | 10 | How often to run the probe (seconds) |
| `timeoutSeconds` | 1 | Seconds after which probe times out |
| `successThreshold` | 1 | Consecutive successes to declare healthy |
| `failureThreshold` | 3 | Consecutive failures before taking action |

> **Key rule**: `timeoutSeconds` must be less than `periodSeconds`. If a probe takes longer than `timeoutSeconds` to respond, it counts as a **failure**.

### Calculating Worst-Case Time to Action

```
  Time before liveness restarts container =
  initialDelaySeconds + (periodSeconds × failureThreshold)

  Example: initialDelay=10, period=5, failureThreshold=3
  = 10 + (5 × 3) = 25 seconds from container start to restart
```

---

## 6. Liveness Probe — Deep Dive

**Purpose:** Detect containers that are running but broken — deadlocked, out of memory, corrupted state. kubelet **restarts** the container on failure.

```
  Liveness Probe behaviour:

  Probe PASSES  ────────────────────────────────► Container keeps running
  
  Probe FAILS (1st) ──► failure count: 1/3 (no action yet)
  Probe FAILS (2nd) ──► failure count: 2/3 (no action yet)
  Probe FAILS (3rd) ──► failure count: 3/3 ──► CONTAINER RESTARTED
                                                (restartPolicy applies)
  
  After restart, count resets to 0
```

### HTTP Liveness Example

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-app
spec:
  containers:
  - name: app
    image: myapp:1.0
    ports:
    - containerPort: 8080
    livenessProbe:
      httpGet:
        path: /healthz        # your app must implement this endpoint
        port: 8080
      initialDelaySeconds: 10 # give app 10s to start before first check
      periodSeconds: 10       # check every 10 seconds
      timeoutSeconds: 5       # fail if no response in 5s
      failureThreshold: 3     # restart after 3 consecutive failures
```

### What a Good `/healthz` Endpoint Should Check

```python
# Example: Python Flask health endpoint
@app.route('/healthz')
def healthz():
    # Check critical dependencies
    try:
        db.ping()              # database reachable?
        cache.ping()           # cache reachable?
        return {"status": "ok"}, 200
    except Exception as e:
        return {"status": "error", "reason": str(e)}, 500
```

> **Warning**: Do NOT check external dependencies in the liveness probe. If your database goes down, killing and restarting your app won't fix it — it will cause a restart loop. Use readiness for that instead.

### Exec Liveness Example

```yaml
livenessProbe:
  exec:
    command:
    - sh
    - -c
    - "redis-cli ping | grep -q PONG"
  initialDelaySeconds: 5
  periodSeconds: 10
  failureThreshold: 3
```

### TCP Liveness Example

```yaml
livenessProbe:
  tcpSocket:
    port: 3306
  initialDelaySeconds: 15
  periodSeconds: 20
  failureThreshold: 3
```

---

## 7. Readiness Probe — Deep Dive

**Purpose:** Signal when a container is ready to accept traffic. kubelet **removes the Pod from Service endpoints** on failure and **adds it back** on success.

```
  Readiness Probe behaviour:

  Pod starts
  │
  Readiness FAILS ──► Pod NOT in Service endpoints ──► No traffic sent
  │
  (app loads config, warms up cache, connects to DB...)
  │
  Readiness PASSES ──► Pod ADDED to Service endpoints ──► Traffic flows
  │
  (during rolling update, app is overloaded...)
  │
  Readiness FAILS ──► Pod REMOVED from endpoints ──► Traffic diverted to healthy pods
  │                    (Pod is NOT restarted — just sidelined)
  │
  Readiness PASSES ──► Pod ADDED back to endpoints
```

### Key Difference from Liveness

```
  Liveness failure  → RESTART the container (kill + recreate)
  Readiness failure → REMOVE from endpoints (container keeps running, just no traffic)
```

### HTTP Readiness Example

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: api-server
spec:
  containers:
  - name: api
    image: myapi:2.0
    ports:
    - containerPort: 8080
    readinessProbe:
      httpGet:
        path: /ready          # separate endpoint from /healthz
        port: 8080
      initialDelaySeconds: 5
      periodSeconds: 5
      successThreshold: 1
      failureThreshold: 3
```

### What `/ready` Should Check (vs `/healthz`)

```
  /healthz (liveness) — is the PROCESS okay?
  ├── Is the app event loop running?
  ├── Is memory usage sane?
  └── Is the app not deadlocked?

  /ready (readiness) — can it SERVE REQUESTS?
  ├── Is the database connection pool established?
  ├── Is the cache warmed up?
  ├── Are config files loaded?
  └── Are dependent services reachable?
```

### Readiness with Database Dependency

```yaml
readinessProbe:
  exec:
    command:
    - sh
    - -c
    - |
      # Check DB connection
      pg_isready -h $DB_HOST -p 5432 -U $DB_USER
  initialDelaySeconds: 5
  periodSeconds: 10
  failureThreshold: 6    # 6 × 10s = 60s of failures before considered not ready
```

### Rolling Update Behaviour with Readiness Probe

```
  Deployment rolling update (maxSurge=1, maxUnavailable=0):

  Old Pod (v1):  Running  ──► Ready ──► in endpoints
  New Pod (v2):  Starting ──► Readiness probe running...
                          ──► Readiness PASSES ──► added to endpoints
                          ──► Old Pod (v1) terminated

  If new pod's readiness FAILS:
  ──► Old pod stays running (not terminated)
  ──► Rollout pauses
  ──► No downtime because traffic still goes to old pod
```

---

## 8. Startup Probe — Deep Dive

**Purpose:** Handle **slow-starting containers** that need more time to initialise than liveness allows. Liveness and readiness probes are **suspended** until the startup probe succeeds.

```
  Without Startup Probe (problem):

  App needs 120s to start
  Liveness initialDelay=10s, period=10s, failureThreshold=3
  
  t=10s  first liveness check → app not ready → FAIL 1/3
  t=20s  second check → FAIL 2/3
  t=30s  third check → FAIL 3/3 → CONTAINER RESTARTED
  t=40s  cycle repeats → app NEVER starts → CrashLoopBackOff

  With Startup Probe (fixed):

  Startup probe: period=10s, failureThreshold=15 → allows 150s grace
  
  t=0    container starts
  t=10s  startup probe check → FAIL (still loading)
  t=20s  startup probe check → FAIL (still loading)
  ...
  t=120s startup probe check → SUCCESS!
         ↓
         Startup probe deactivated
         Liveness + Readiness probes NOW begin
```

### Startup Probe Example for Slow App

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: legacy-app
spec:
  containers:
  - name: legacy
    image: slow-legacy-app:3.0
    ports:
    - containerPort: 8080
    startupProbe:
      httpGet:
        path: /healthz
        port: 8080
      failureThreshold: 30    # 30 failures allowed
      periodSeconds: 10       # checked every 10s
      # max startup time = failureThreshold × periodSeconds = 300s (5 min)
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
      periodSeconds: 10
      failureThreshold: 3
    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      periodSeconds: 5
```

### Calculating Maximum Startup Time

```
  maxStartupTime = failureThreshold × periodSeconds

  Examples:
  failureThreshold=30, periodSeconds=10  → 300 seconds (5 min)
  failureThreshold=60, periodSeconds=5   → 300 seconds (5 min)
  failureThreshold=12, periodSeconds=15  → 180 seconds (3 min)
```

> **Best practice**: Set `failureThreshold × periodSeconds` to the maximum realistic startup time plus a safety margin (e.g., 150% of P99 startup time).

---

## 9. How the Three Probes Work Together

### Complete Timeline

```
  Container starts
  │
  ├── startupProbe begins (period=10s, failureThreshold=30)
  │   liveness and readiness are PAUSED
  │
  │   t=10s:  startup FAIL (1/30) ── still loading...
  │   t=20s:  startup FAIL (2/30) ── DB connecting...
  │   t=30s:  startup FAIL (3/30) ── cache warming...
  │   t=45s:  startup SUCCESS ──────── app is initialised!
  │
  │   startupProbe deactivated
  │
  ├── livenessProbe begins (period=10s, failureThreshold=3)
  │   t=55s:  liveness SUCCESS ── app healthy
  │   t=65s:  liveness SUCCESS ── app healthy
  │   ...
  │   (later: deadlock detected)
  │   t=125s: liveness FAIL (1/3)
  │   t=135s: liveness FAIL (2/3)
  │   t=145s: liveness FAIL (3/3) → RESTART CONTAINER
  │
  └── readinessProbe begins (period=5s, failureThreshold=3)
      t=50s:  readiness FAIL ── not in endpoints yet
      t=55s:  readiness FAIL ── warming up
      t=60s:  readiness SUCCESS ── ADDED TO SERVICE ENDPOINTS → traffic flows
      ...
      (during rolling update)
      t=120s: readiness FAIL ── high load
      t=125s: readiness FAIL ── still overloaded
      t=130s: readiness FAIL (3/3) → REMOVED FROM ENDPOINTS
      t=145s: readiness SUCCESS → RE-ADDED TO ENDPOINTS
```

---

## 10. Probe Combinations — Best Practices

### Full Production Template

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: production-api
spec:
  replicas: 3
  selector:
    matchLabels:
      app: production-api
  template:
    metadata:
      labels:
        app: production-api
    spec:
      containers:
      - name: api
        image: myapi:3.0
        ports:
        - containerPort: 8080
        resources:
          requests:
            cpu: 100m
            memory: 128Mi
          limits:
            cpu: 500m
            memory: 512Mi

        # Startup probe — handle slow initialisation
        startupProbe:
          httpGet:
            path: /healthz
            port: 8080
          failureThreshold: 30   # allow up to 300s startup
          periodSeconds: 10
          timeoutSeconds: 5

        # Liveness probe — detect and recover from broken state
        livenessProbe:
          httpGet:
            path: /healthz
            port: 8080
          periodSeconds: 10
          timeoutSeconds: 5
          failureThreshold: 3
          # No initialDelaySeconds needed — startupProbe handles it

        # Readiness probe — gate traffic until truly ready
        readinessProbe:
          httpGet:
            path: /ready         # deeper check than /healthz
            port: 8080
          periodSeconds: 5
          timeoutSeconds: 3
          successThreshold: 1
          failureThreshold: 3
```

### Common Patterns by App Type

**Pattern 1: Stateless HTTP API**

```yaml
startupProbe:
  httpGet: { path: /healthz, port: 8080 }
  failureThreshold: 12
  periodSeconds: 5           # 60s startup grace

livenessProbe:
  httpGet: { path: /healthz, port: 8080 }
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet: { path: /ready, port: 8080 }
  periodSeconds: 5
  failureThreshold: 3
```

**Pattern 2: Database (MySQL/PostgreSQL)**

```yaml
livenessProbe:
  exec:
    command: ["sh", "-c", "mysqladmin ping -h localhost --silent"]
  initialDelaySeconds: 30
  periodSeconds: 10
  failureThreshold: 5

readinessProbe:
  exec:
    command: ["sh", "-c", "mysql -h localhost -u$MYSQL_USER -p$MYSQL_PASSWORD -e 'SELECT 1'"]
  initialDelaySeconds: 5
  periodSeconds: 5
  failureThreshold: 3
```

**Pattern 3: Redis**

```yaml
livenessProbe:
  exec:
    command: ["redis-cli", "ping"]
  initialDelaySeconds: 15
  periodSeconds: 5

readinessProbe:
  exec:
    command: ["redis-cli", "ping"]
  initialDelaySeconds: 5
  periodSeconds: 3
```

**Pattern 4: Nginx/Static Server**

```yaml
livenessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 5
  periodSeconds: 10

readinessProbe:
  httpGet:
    path: /
    port: 80
  initialDelaySeconds: 3
  periodSeconds: 5
```

**Pattern 5: Java / JVM app (slow startup)**

```yaml
startupProbe:
  httpGet: { path: /actuator/health, port: 8080 }
  failureThreshold: 60       # allow up to 10 minutes for JVM warmup
  periodSeconds: 10

livenessProbe:
  httpGet: { path: /actuator/health/liveness, port: 8080 }
  periodSeconds: 10
  failureThreshold: 3

readinessProbe:
  httpGet: { path: /actuator/health/readiness, port: 8080 }
  periodSeconds: 5
  failureThreshold: 3
```

### What NOT to Do

```yaml
# BAD: No initialDelaySeconds without startupProbe on slow app
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  periodSeconds: 5
  failureThreshold: 3
# If app takes 30s to start, this kills it at 15s → CrashLoopBackOff

# BAD: Liveness checking external dependencies
livenessProbe:
  httpGet:
    path: /healthz   # endpoint checks DB, redis, external APIs
    port: 8080
# If DB goes down: all pods restart infinitely — makes incident worse

# BAD: timeoutSeconds > periodSeconds
livenessProbe:
  httpGet:
    path: /healthz
    port: 8080
  periodSeconds: 5
  timeoutSeconds: 10   # timeout longer than period — probes pile up

# BAD: Very short initialDelaySeconds without startupProbe
livenessProbe:
  initialDelaySeconds: 2
  periodSeconds: 3
  failureThreshold: 2
# 2 + (3×2) = 8 seconds — barely any grace for any real app
```

---

## 11. Practical Demo

```bash
# === DEMO 1: Liveness Probe — Self-healing Pod ===

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: liveness-demo
spec:
  containers:
  - name: app
    image: busybox
    args:
    - /bin/sh
    - -c
    - |
      touch /tmp/healthy          # create healthy file
      sleep 30                    # stay healthy for 30 seconds
      rm -f /tmp/healthy          # simulate failure after 30s
      sleep 600                   # keep process alive (but probe will fail)
    livenessProbe:
      exec:
        command:
        - cat
        - /tmp/healthy
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 3
EOF

# Watch the pod — after ~45 seconds it will restart
kubectl get pod liveness-demo -w

# Watch restart count increase
kubectl describe pod liveness-demo | grep -E "Restart|Last State|Events" -A5

# See the restart event
kubectl describe pod liveness-demo | tail -20


# === DEMO 2: Readiness Probe — Traffic Gating ===

cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: readiness-demo
spec:
  replicas: 3
  selector:
    matchLabels:
      app: readiness-demo
  template:
    metadata:
      labels:
        app: readiness-demo
    spec:
      containers:
      - name: nginx
        image: nginx:1.21
        ports:
        - containerPort: 80
        readinessProbe:
          httpGet:
            path: /ready.html       # file we'll create manually
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
          failureThreshold: 3
---
apiVersion: v1
kind: Service
metadata:
  name: readiness-demo-svc
spec:
  selector:
    app: readiness-demo
  ports:
  - port: 80
EOF

kubectl rollout status deployment/readiness-demo

# Check endpoints — pods are NOT ready (no /ready.html)
kubectl get endpoints readiness-demo-svc
# ENDPOINTS: <none>

# Check pod status
kubectl get pods -l app=readiness-demo
# READY column shows 0/1

# Create the ready file in one pod
POD=$(kubectl get pods -l app=readiness-demo -o name | head -1)
kubectl exec $POD -- sh -c "echo 'ok' > /usr/share/nginx/html/ready.html"

# Watch the endpoints update
kubectl get endpoints readiness-demo-svc -w
# Pod added to endpoints after readiness probe passes

# Create ready file in all pods
for pod in $(kubectl get pods -l app=readiness-demo -o name); do
  kubectl exec $pod -- sh -c "echo 'ok' > /usr/share/nginx/html/ready.html"
done

kubectl get pods -l app=readiness-demo
# READY column shows 1/1 for all

# Remove the file from one pod — watch it leave endpoints
POD=$(kubectl get pods -l app=readiness-demo -o name | head -1)
kubectl exec $POD -- rm /usr/share/nginx/html/ready.html

kubectl get endpoints readiness-demo-svc
# That pod's IP removed from endpoints

kubectl get pods -l app=readiness-demo
# That pod shows 0/1 (not ready) but NOT restarted


# === DEMO 3: Startup Probe — Slow App ===

cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: startup-demo
spec:
  containers:
  - name: slow-app
    image: busybox
    args:
    - /bin/sh
    - -c
    - |
      echo "Simulating slow startup..."
      sleep 40                    # takes 40 seconds to "initialise"
      touch /tmp/started
      echo "App started!"
      sleep 600
    startupProbe:
      exec:
        command:
        - test
        - -f
        - /tmp/started
      failureThreshold: 12        # 12 × 5s = 60s grace period
      periodSeconds: 5
    livenessProbe:
      exec:
        command:
        - test
        - -f
        - /tmp/started
      periodSeconds: 10
      failureThreshold: 3
EOF

# Watch — pod stays in Running without restarting despite taking 40s
kubectl get pod startup-demo -w

# After 40+ seconds, startupProbe passes, then liveness takes over
kubectl describe pod startup-demo | grep -A5 "Startup\|Liveness"


# === CLEANUP ===
kubectl delete pod liveness-demo startup-demo
kubectl delete deployment readiness-demo
kubectl delete svc readiness-demo-svc
```

---

## 12. Probe Failure Behaviour and Debugging

### Debugging Failed Probes

```bash
# Check restart count and last restart reason
kubectl get pod <pod-name>
# Look at RESTARTS column

# Full probe details and recent events
kubectl describe pod <pod-name>

# Look for events like:
# Liveness probe failed: HTTP probe failed with statuscode: 500
# Readiness probe failed: dial tcp: connection refused
# Startup probe failed: exec command failed

# Check container logs around the time of restart
kubectl logs <pod-name> --previous   # logs from previous (crashed) container
kubectl logs <pod-name>              # current container logs

# Check probe configuration
kubectl get pod <pod-name> -o yaml | grep -A20 "livenessProbe\|readinessProbe\|startupProbe"
```

### Reading `kubectl describe` Probe Events

```
  Events:
  Type     Reason     Age              Message
  ----     ------     ----             -------
  Warning  Unhealthy  2m               Liveness probe failed: Get "http://10.244.1.5:8080/healthz": dial tcp 10.244.1.5:8080: connect: connection refused
  Warning  Unhealthy  90s (×3 over 2m) Readiness probe failed: HTTP probe failed with statuscode: 503
  Normal   Killing    88s              Container app failed liveness probe, will be restarted
  Normal   Pulled     85s              Container image "myapp:1.0" already present on machine
  Normal   Started    85s              Started container app
```

### Common Probe Failure Reasons

| Error Message | Root Cause | Fix |
|--------------|-----------|-----|
| `connection refused` | App not listening on that port, or port number wrong | Check containerPort matches probe port |
| `HTTP probe failed with statuscode: 404` | Health endpoint path is wrong | Fix `path` in httpGet |
| `HTTP probe failed with statuscode: 500` | App is broken / returning error | Fix the app or the /healthz endpoint |
| `dial tcp: i/o timeout` | `timeoutSeconds` too short or app too slow | Increase `timeoutSeconds` |
| `exec: no such file or directory` | Binary not in container | Use full path, check image |
| Pod in `CrashLoopBackOff` | Liveness killing before app starts | Add `startupProbe` or increase `initialDelaySeconds` |
| Pod stuck in `0/1 Ready` forever | Readiness probe path wrong or app never passes check | Check endpoint exists, fix path |

---

## 13. Common Interview Questions

**Q: What are the three types of Kubernetes probes?**
> **Liveness** probe checks if a container is still alive and functioning — failure causes the container to be restarted. **Readiness** probe checks if a container is ready to accept traffic — failure removes it from the Service's endpoints without restarting it. **Startup** probe handles slow-starting containers by blocking liveness and readiness checks until it succeeds.

---

**Q: What is the difference between a liveness and a readiness probe?**
> **Liveness** detects a broken container and fixes it by restarting. **Readiness** detects a container that's temporarily not ready (loading, overloaded, dependencies unavailable) and temporarily removes it from traffic routing — it does NOT restart the container. A container can be alive but not ready.

---

**Q: Why would a Pod be in CrashLoopBackOff because of a probe?**
> Usually because a **liveness probe is configured without a startup probe or sufficient `initialDelaySeconds`** for a slow-starting application. The liveness probe fires before the app finishes initialising, marks it as failed, restarts it, and the cycle repeats indefinitely. Fix: add a `startupProbe` with `failureThreshold × periodSeconds` ≥ max startup time.

---

**Q: What is a startup probe and when should you use it?**
> A startup probe is used for containers that take a long time to initialise (JVM apps, apps loading large datasets, legacy apps). While the startup probe is active, liveness and readiness probes are paused. This prevents liveness from killing the container before it finishes starting. Use it whenever the startup time is longer than `initialDelaySeconds + (failureThreshold × periodSeconds)` of your liveness probe.

---

**Q: What are the four probe mechanisms?**
> **HTTP GET** — kubelet calls an HTTP endpoint; 2xx/3xx = success. **TCP Socket** — kubelet opens a TCP connection; connected = success. **Exec** — kubelet runs a command inside the container; exit code 0 = success. **gRPC** — kubelet uses gRPC health protocol (Kubernetes ≥ 1.24).

---

**Q: Can a Pod be Running but not Ready? What does that mean?**
> Yes. `Running` means the container process is alive. `Ready` (in the `READY` column) means all readiness probes are passing. A Pod can be `Running` with `0/1 Ready` when its readiness probe is failing — it's alive but excluded from Service endpoints. This is normal during startup, rolling updates, or temporary overload.

---

**Q: What happens to traffic when a readiness probe fails during a rolling update?**
> The new Pod is excluded from the Service endpoints and the old Pod is NOT terminated. The rollout pauses. Traffic continues to flow to the old (healthy) Pods. This prevents downtime — Kubernetes waits for the new Pod to become ready before terminating the old one. This is why readiness probes are critical for zero-downtime rolling updates.

---

**Q: Should a liveness probe check external dependencies like a database?**
> No. If the database goes down, all Pods would fail their liveness check and restart in a loop — which doesn't fix the database and makes the outage worse. Liveness should only check the health of the process itself (memory, deadlocks, internal state). Use the readiness probe for dependency checks — a failed readiness removes the Pod from traffic without restarting it.

---

## 14. Exam Practice Questions

### Section A: Concept Questions

**1.** A Pod shows `READY 0/1` but `STATUS Running`. What is the likely cause?
> The **readiness probe is failing**. The container is alive (Running) but not accepting traffic. Check `kubectl describe pod` Events for readiness probe failure details.

---

**2.** Your app takes 90 seconds to start. Liveness is configured with `initialDelaySeconds: 10, periodSeconds: 10, failureThreshold: 3`. What happens?
> The pod will enter **CrashLoopBackOff**. Liveness starts at t=10s. By t=40s (10 + 3×10), three failures have occurred and the container is restarted — before the app finishes starting. Fix: add `startupProbe` with `failureThreshold: 15, periodSeconds: 10` (150s grace).

---

**3.** What is the maximum time a startup probe with `failureThreshold: 20` and `periodSeconds: 10` gives a container?
> **200 seconds** (20 × 10). After 200 seconds of consecutive failures, the container is killed like a liveness failure.

---

**4.** During a rolling update, the new Pod's readiness probe keeps failing. What happens to the old Pod?
> The old Pod is **NOT terminated**. The rollout pauses and waits. Traffic continues to flow only to the old Pod. The update will not proceed until the new Pod passes its readiness probe (or times out with `progressDeadlineSeconds`).

---

### Section B: YAML Writing Tasks

**Task 1:** Write a Pod with an HTTP liveness probe on `/healthz:8080` that starts checking after 15 seconds, probes every 10 seconds, times out in 3 seconds, and restarts after 3 failures.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-with-liveness
spec:
  containers:
  - name: app
    image: nginx
    ports:
    - containerPort: 8080
    livenessProbe:
      httpGet:
        path: /healthz
        port: 8080
      initialDelaySeconds: 15
      periodSeconds: 10
      timeoutSeconds: 3
      failureThreshold: 3
```

---

**Task 2:** Add a readiness probe to the above Pod using `/ready:8080` that checks every 5 seconds.

```yaml
    readinessProbe:
      httpGet:
        path: /ready
        port: 8080
      periodSeconds: 5
      failureThreshold: 3
```

---

**Task 3:** Add a startup probe that allows up to 2 minutes for the app to start.

```yaml
    startupProbe:
      httpGet:
        path: /healthz
        port: 8080
      failureThreshold: 12    # 12 × 10s = 120s
      periodSeconds: 10
```

---

**Task 4:** Write a TCP socket liveness probe for a MySQL Pod on port 3306.

```yaml
    livenessProbe:
      tcpSocket:
        port: 3306
      initialDelaySeconds: 30
      periodSeconds: 10
      failureThreshold: 3
```

---

**Task 5:** Write an exec liveness probe that checks the file `/tmp/healthy` exists.

```yaml
    livenessProbe:
      exec:
        command:
        - cat
        - /tmp/healthy
      initialDelaySeconds: 5
      periodSeconds: 5
      failureThreshold: 3
```

---

### Section C: Debugging Scenario

**Scenario:** A Deployment of 3 Pods was just rolled out. Two pods show `1/1 Running` but one shows `0/1 Running`. Logs show no errors. What do you investigate?

```bash
# Step 1: Find the not-ready pod
kubectl get pods -l app=my-app

# Step 2: Describe the not-ready pod
kubectl describe pod <not-ready-pod>
# Look at:
# - Conditions section (Ready = False)
# - Events section (readiness probe failures)

# Step 3: Check what readiness probe is configured
kubectl get pod <not-ready-pod> -o yaml | grep -A15 readinessProbe

# Step 4: Manually test the readiness endpoint
kubectl exec <not-ready-pod> -- wget -qO- http://localhost:8080/ready
# If 404: path is wrong
# If 500: app is returning an error
# If connection refused: wrong port

# Step 5: Check endpoints — confirm this pod is excluded
kubectl get endpoints my-service
```

---

### Section D: Quick-Fire Commands

```bash
# Check probe config on a running pod
kubectl get pod <name> -o yaml | grep -A20 "Probe:"

# Watch pod readiness change
kubectl get pod <name> -w

# Check events for probe failures
kubectl describe pod <name> | grep -A30 Events

# Check logs from previous (restarted) container
kubectl logs <pod> --previous

# Check restart count
kubectl get pod <name>

# Force a liveness failure test (exec probe)
kubectl exec <pod> -- rm /tmp/healthy

# Check endpoint membership
kubectl get endpoints <service-name>
```

---

> **CKA Exam Tips**:
> - Know the three probe types by heart: Liveness (restart), Readiness (remove from endpoints), Startup (protect slow start)
> - `CrashLoopBackOff` with probes → almost always liveness killing before app is ready → add startupProbe
> - `0/1 Ready` not `Running` → readiness probe failing (not liveness)
> - `kubectl describe pod` Events section is the fastest way to see probe failures
> - Liveness should NOT check external services — that's readiness's job
> - `successThreshold` must be 1 for liveness and startup probes (spec requirement)

---

*Notes by ITkannadigaru | CKA 2026 Certification*

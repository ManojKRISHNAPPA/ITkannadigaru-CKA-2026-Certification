# Complete Guide to Kubernetes Deployments

## Table of Contents
1. [What is a Deployment?](#1-what-is-a-deployment)
2. [Deployment vs ReplicaSet vs Pod](#2-deployment-vs-replicaset-vs-pod)
3. [Imperative Way — Creating Deployments](#3-imperative-way--creating-deployments)
4. [Declarative Way — Creating Deployments](#4-declarative-way--creating-deployments)
5. [Full Deployment YAML Reference](#5-full-deployment-yaml-reference)
6. [Update Strategies](#6-update-strategies)
7. [Rolling Update Strategy (Deep Dive)](#7-rolling-update-strategy-deep-dive)
8. [Recreate Strategy](#8-recreate-strategy)
9. [Blue-Green Deployment](#9-blue-green-deployment)
10. [Canary Deployment](#10-canary-deployment)
11. [Updating a Deployment](#11-updating-a-deployment)
12. [Rollback a Deployment](#12-rollback-a-deployment)
13. [Pausing and Resuming Deployments](#13-pausing-and-resuming-deployments)
14. [Scaling a Deployment](#14-scaling-a-deployment)
15. [Deployment with ConfigMap and Secret](#15-deployment-with-configmap-and-secret)
16. [Deployment Status and Conditions](#16-deployment-status-and-conditions)
17. [Useful kubectl Commands](#17-useful-kubectl-commands)
18. [Common Interview Questions](#18-common-interview-questions)

---

## 1. What is a Deployment?

A **Deployment** is a higher-level Kubernetes object that manages **ReplicaSets** and provides **declarative updates** to Pods.

```
Deployment = ReplicaSet + Rolling Updates + Rollback History
```

**What it gives you:**
- Desired number of Pod replicas running (via ReplicaSet)
- Self-healing (replace failed Pods)
- **Rolling updates** — update Pods gradually with zero downtime
- **Rollback** — revert to a previous version instantly
- **Pause/Resume** — make multiple changes before applying them

```
┌─────────────────────────────────────────────┐
│                 Deployment                  │
│  (manages update strategy + history)        │
└───────────────┬─────────────────────────────┘
                │ creates & manages
        ┌───────┴────────┐
        ▼                ▼
┌──────────────┐  ┌──────────────┐
│ ReplicaSet   │  │ ReplicaSet   │
│  (v2, new)   │  │  (v1, old)   │  ← kept for rollback
└──────┬───────┘  └──────────────┘
       │ manages
  ┌────┼────┐
  ▼    ▼    ▼
Pod1 Pod2 Pod3
(v2) (v2) (v2)
```

---

## 2. Deployment vs ReplicaSet vs Pod

| Feature | Pod | ReplicaSet | Deployment |
|---------|-----|-----------|------------|
| Single unit | ✓ | ✗ | ✗ |
| Replica management | ✗ | ✓ | ✓ |
| Self-healing | ✗ | ✓ | ✓ |
| Rolling updates | ✗ | ✗ | ✓ |
| Rollback | ✗ | ✗ | ✓ |
| Update history | ✗ | ✗ | ✓ |
| Pause/Resume | ✗ | ✗ | ✓ |
| Recommended for | Dev/test | Rarely directly | Production |

---

## 3. Imperative Way — Creating Deployments

### 3.1 Create a basic Deployment

```bash
kubectl create deployment web --image=nginx
```

### 3.2 Create with specific replicas

```bash
kubectl create deployment web --image=nginx --replicas=3
```

### 3.3 Create with specific port

```bash
kubectl create deployment web --image=nginx --replicas=3 --port=80
```

### 3.4 Generate YAML without creating (dry-run) — most useful for CKA

```bash
# Print to terminal
kubectl create deployment web --image=nginx --replicas=3 --dry-run=client -o yaml

# Save to file
kubectl create deployment web --image=nginx --replicas=3 --dry-run=client -o yaml > deployment.yaml
```

### 3.5 Create in a specific namespace

```bash
kubectl create deployment web --image=nginx --replicas=3 -n production
```

### 3.6 Scale an existing Deployment

```bash
kubectl scale deployment web --replicas=5
```

### 3.7 Update the image (triggers rolling update)

```bash
kubectl set image deployment/web nginx=nginx:1.25
#                              ^         ^     ^
#                    deploy name  container  new image
```

### 3.8 Check rollout status

```bash
kubectl rollout status deployment/web
```

### 3.9 Rollback

```bash
kubectl rollout undo deployment/web
```

### 3.10 Delete a Deployment

```bash
kubectl delete deployment web
```

---

## 4. Declarative Way — Creating Deployments

### 4.1 Minimal Deployment

```yaml
# deployment-minimal.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: nginx
        image: nginx:1.25
```

```bash
kubectl apply -f deployment-minimal.yaml
```

### 4.2 Apply, Update, Delete

```bash
# Create or update
kubectl apply -f deployment.yaml

# Track the rollout
kubectl rollout status deployment/web

# Delete
kubectl delete -f deployment.yaml
```

---

## 5. Full Deployment YAML Reference

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-deployment
  namespace: default
  labels:                              # Labels ON the Deployment object
    app: web
    env: production
    version: "2.0"
  annotations:
    deployment.kubernetes.io/revision: "1"
    description: "Production web server deployment"

spec:
  replicas: 3                          # Desired number of Pod replicas

  # ── Selector ──────────────────────────────────────────────
  selector:
    matchLabels:
      app: web                         # Must match template labels
    matchExpressions:                  # Optional: set-based
    - key: env
      operator: In
      values: [production, staging]

  # ── Update Strategy ───────────────────────────────────────
  strategy:
    type: RollingUpdate                # RollingUpdate | Recreate
    rollingUpdate:
      maxSurge: 1                      # Max pods ABOVE desired during update
      maxUnavailable: 0                # Max pods BELOW desired during update

  # ── Revision History ──────────────────────────────────────
  revisionHistoryLimit: 10             # Number of old ReplicaSets to keep (default: 10)

  # ── Min Ready Seconds ─────────────────────────────────────
  minReadySeconds: 5                   # Pod must be ready for N seconds before considered available

  # ── Progress Deadline ─────────────────────────────────────
  progressDeadlineSeconds: 600         # Seconds before deployment is considered failed (default: 600)

  # ── Pod Template ──────────────────────────────────────────
  template:
    metadata:
      labels:
        app: web                       # Must match selector
        env: production
        version: "2.0"
      annotations:
        prometheus.io/scrape: "true"
        prometheus.io/port: "8080"

    spec:
      containers:
      - name: web
        image: nginx:1.25              # Always pin image tag!
        imagePullPolicy: IfNotPresent

        ports:
        - name: http
          containerPort: 80

        resources:
          requests:
            cpu: "100m"
            memory: "128Mi"
          limits:
            cpu: "500m"
            memory: "256Mi"

        env:
        - name: APP_ENV
          value: "production"

        readinessProbe:                # IMPORTANT for rolling updates
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
          failureThreshold: 3

        livenessProbe:
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 15
          periodSeconds: 20

      restartPolicy: Always            # Must be Always for Deployments
      terminationGracePeriodSeconds: 30
```

---

## 6. Update Strategies

Kubernetes Deployments support two built-in strategies, plus two common patterns implemented manually:

| Strategy | Built-in | Downtime | Use Case |
|----------|----------|----------|----------|
| **RollingUpdate** | ✓ Yes | Zero downtime | Default, most common |
| **Recreate** | ✓ Yes | Has downtime | Stateful apps, DB schema changes |
| **Blue-Green** | ✗ Manual pattern | Zero downtime | Instant full switchover |
| **Canary** | ✗ Manual pattern | Zero downtime | Gradual traffic shift, risk reduction |

---

## 7. Rolling Update Strategy (Deep Dive)

### How it works

Rolling update replaces Pods **gradually** — a few at a time — so the app stays available throughout the update.

```
Before update:   [v1] [v1] [v1] [v1] [v1]   (5 replicas, all v1)

Step 1 (surge):  [v1] [v1] [v1] [v1] [v1] [v2]   (add 1 new)
Step 2 (remove): [v1] [v1] [v1] [v1] [v2]         (remove 1 old)
Step 3 (surge):  [v1] [v1] [v1] [v1] [v2] [v2]   (add 1 new)
Step 4 (remove): [v1] [v1] [v1] [v2] [v2]         (remove 1 old)
...continues...
After update:    [v2] [v2] [v2] [v2] [v2]   (5 replicas, all v2)
```

### Key Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `maxSurge` | 25% | Max number of Pods ABOVE desired count during update. Can be integer or % |
| `maxUnavailable` | 25% | Max number of Pods BELOW desired count during update. Can be integer or % |

### maxSurge and maxUnavailable explained

```
replicas: 4
maxSurge: 1        → at most 5 pods exist at any time (4+1)
maxUnavailable: 1  → at least 3 pods available at all times (4-1)
```

### Strategy Variants

#### Zero Downtime (safest, slower)
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 1
    maxUnavailable: 0     # Never go below desired count
```
```
replicas=4, maxSurge=1, maxUnavailable=0
→ always at least 4 pods available
→ max 5 pods total during update
→ update happens 1 pod at a time
```

#### Fast Update (risky, quicker)
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 0
    maxUnavailable: 1     # Allow 1 pod to be unavailable
```
```
replicas=4, maxSurge=0, maxUnavailable=1
→ at least 3 pods available during update
→ max 4 pods total (no extra capacity needed)
→ good when cluster resources are tight
```

#### Percentage-based
```yaml
strategy:
  type: RollingUpdate
  rollingUpdate:
    maxSurge: 25%         # 25% of replicas
    maxUnavailable: 25%   # Default values
```

### Full Rolling Update Deployment Example

```yaml
# deployment-rolling.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-rolling
  labels:
    app: web
spec:
  replicas: 4
  selector:
    matchLabels:
      app: web
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0
  minReadySeconds: 10          # Pod must be stable for 10s before proceeding
  progressDeadlineSeconds: 300 # Fail if update takes more than 5 mins
  template:
    metadata:
      labels:
        app: web
    spec:
      containers:
      - name: nginx
        image: nginx:1.24     # Start with 1.24
        ports:
        - containerPort: 80
        readinessProbe:       # REQUIRED: RS uses this to judge Pod readiness
          httpGet:
            path: /
            port: 80
          initialDelaySeconds: 5
          periodSeconds: 5
```

### Perform a rolling update

```bash
# Apply initial deployment
kubectl apply -f deployment-rolling.yaml

# Watch Pods
kubectl get pods -w

# Trigger rolling update by changing the image
kubectl set image deployment/web-rolling nginx=nginx:1.25

# Watch rollout in real-time
kubectl rollout status deployment/web-rolling

# Output:
# Waiting for deployment "web-rolling" rollout to finish: 1 out of 4 new replicas have been updated...
# Waiting for deployment "web-rolling" rollout to finish: 2 out of 4 new replicas have been updated...
# Waiting for deployment "web-rolling" rollout to finish: 3 out of 4 new replicas have been updated...
# Waiting for deployment "web-rolling" rollout to finish: 4 out of 4 new replicas have been updated...
# deployment "web-rolling" successfully rolled out
```

### Why readinessProbe matters for rolling updates

```
Without readinessProbe:
→ Kubernetes marks new Pod as ready as soon as container starts
→ Old Pod removed immediately
→ New Pod might not be serving traffic yet → brief errors

With readinessProbe:
→ Kubernetes waits for probe to pass before marking Pod ready
→ Old Pod removed only AFTER new Pod is confirmed ready
→ True zero-downtime update
```

---

## 8. Recreate Strategy

### How it works

Recreate **terminates ALL existing Pods** first, then creates new ones.

```
Before:  [v1] [v1] [v1]

Step 1:  [ ]  [ ]  [ ]   ← ALL old pods deleted (DOWNTIME here)

Step 2:  [v2] [v2] [v2]  ← All new pods created
```

### When to use Recreate
- Stateful apps that cannot run two versions simultaneously
- Database schema changes that are not backward-compatible
- Apps that hold exclusive locks on resources
- Development environments where downtime is acceptable
- When you need a clean state before the new version starts

### Recreate Deployment YAML

```yaml
# deployment-recreate.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-recreate
  labels:
    app: web-recreate
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-recreate
  strategy:
    type: Recreate            # No rollingUpdate block needed
  template:
    metadata:
      labels:
        app: web-recreate
    spec:
      containers:
      - name: nginx
        image: nginx:1.24
        ports:
        - containerPort: 80
```

```bash
# Apply
kubectl apply -f deployment-recreate.yaml

# Trigger update
kubectl set image deployment/web-recreate nginx=nginx:1.25

# Watch: ALL old pods terminate, then all new pods start
kubectl get pods -w
```

### Recreate vs RollingUpdate

| Aspect | Recreate | RollingUpdate |
|--------|----------|---------------|
| Downtime | Yes (gap between old and new) | No |
| Speed | Fast (all at once) | Slower (gradual) |
| Resource usage | Lower (no surge) | Higher during update |
| Two versions co-existing | Never | Yes (briefly) |
| Risk | All-or-nothing | Partial rollout possible |

---

## 9. Blue-Green Deployment

### Concept

Maintain **two identical environments** (Blue = current, Green = new). Switch traffic instantly by changing the Service selector.

```
          ┌──────────┐
Users ──→ │ Service  │
          └────┬─────┘
               │ selector: version=blue
               ▼
     ┌─────────────────────┐
     │  Blue Deployment    │  ← LIVE (version 1.0)
     │  [v1] [v1] [v1]     │
     └─────────────────────┘

     ┌─────────────────────┐
     │  Green Deployment   │  ← STANDBY (version 2.0, ready to go)
     │  [v2] [v2] [v2]     │
     └─────────────────────┘
```

**Switch traffic**: Change Service selector from `version=blue` to `version=green` → instant switchover.

### Step-by-Step Blue-Green Example

**Step 1: Deploy Blue (current live version)**

```yaml
# blue-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-blue
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
      version: blue
  template:
    metadata:
      labels:
        app: web
        version: blue
    spec:
      containers:
      - name: nginx
        image: nginx:1.24
        ports:
        - containerPort: 80
```

**Step 2: Create Service pointing to Blue**

```yaml
# service-blue-green.yaml
apiVersion: v1
kind: Service
metadata:
  name: web-service
spec:
  selector:
    app: web
    version: blue        # Points to blue currently
  ports:
  - port: 80
    targetPort: 80
  type: ClusterIP
```

**Step 3: Deploy Green (new version) — no traffic yet**

```yaml
# green-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-green
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
      version: green
  template:
    metadata:
      labels:
        app: web
        version: green
    spec:
      containers:
      - name: nginx
        image: nginx:1.25    # New version
        ports:
        - containerPort: 80
```

**Step 4: Test Green (optional — before switching)**

```bash
kubectl apply -f green-deployment.yaml

# Test green directly (before switching)
kubectl port-forward deployment/web-green 8080:80
curl http://localhost:8080
```

**Step 5: Switch traffic to Green (the cutover)**

```bash
# Imperative switch
kubectl patch service web-service -p '{"spec":{"selector":{"app":"web","version":"green"}}}'

# OR edit the service file and re-apply
# Change:  version: blue  →  version: green
kubectl apply -f service-blue-green.yaml
```

**Step 6: Verify, then clean up Blue**

```bash
# Verify green is serving traffic
kubectl describe service web-service

# After confirming success, delete blue
kubectl delete deployment web-blue

# If rollback needed: patch service back to blue
kubectl patch service web-service -p '{"spec":{"selector":{"app":"web","version":"blue"}}}'
```

### Blue-Green Advantages & Disadvantages

| Advantage | Disadvantage |
|-----------|-------------|
| Instant rollback (just change selector) | Requires 2x resources during switchover |
| Both environments available simultaneously | State/data migration must be handled separately |
| Easy to test new version before going live | More complex to manage |
| Zero downtime | Database compatibility issues between versions |

---

## 10. Canary Deployment

### Concept

Route a **small percentage of traffic** to the new version. Gradually increase traffic to new version as confidence grows.

```
          ┌──────────┐
Users ──→ │ Service  │  selector: app=web (matches BOTH)
          └────┬─────┘
               │
       ┌───────┴───────┐
       ▼               ▼
  [v1][v1][v1][v1]    [v2]
   Stable (4 pods)   Canary (1 pod)
     80% traffic       20% traffic
```

Traffic is distributed proportionally by pod count (Service load balances across all matching pods).

### Step-by-Step Canary Example

**Step 1: Stable Deployment (4 replicas = 80% traffic)**

```yaml
# stable-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-stable
spec:
  replicas: 4
  selector:
    matchLabels:
      app: web
      track: stable
  template:
    metadata:
      labels:
        app: web
        track: stable
    spec:
      containers:
      - name: nginx
        image: nginx:1.24
        ports:
        - containerPort: 80
```

**Step 2: Service selects ALL pods with app=web (stable + canary)**

```yaml
# service-canary.yaml
apiVersion: v1
kind: Service
metadata:
  name: web-service
spec:
  selector:
    app: web            # Matches BOTH stable and canary pods
  ports:
  - port: 80
    targetPort: 80
```

**Step 3: Canary Deployment (1 replica = ~20% traffic)**

```yaml
# canary-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-canary
spec:
  replicas: 1           # 1 out of 5 total = 20%
  selector:
    matchLabels:
      app: web
      track: canary
  template:
    metadata:
      labels:
        app: web
        track: canary
    spec:
      containers:
      - name: nginx
        image: nginx:1.25   # New version
        ports:
        - containerPort: 80
```

**Step 4: Monitor the canary**

```bash
kubectl apply -f canary-deployment.yaml

# Monitor canary pods
kubectl get pods -l track=canary

# Check error rates, latency, etc.
# kubectl logs, metrics, monitoring dashboards
```

**Step 5a: Promote canary (if successful)**

```bash
# Scale up canary
kubectl scale deployment web-canary --replicas=4

# Scale down stable
kubectl scale deployment web-stable --replicas=0

# OR: Update stable deployment image and delete canary
kubectl set image deployment/web-stable nginx=nginx:1.25
kubectl delete deployment web-canary
```

**Step 5b: Rollback canary (if issues found)**

```bash
# Simply delete the canary — stable keeps serving
kubectl delete deployment web-canary
# 100% traffic returns to stable
```

### Canary Traffic Percentages by Replica Count

| Stable Replicas | Canary Replicas | Canary Traffic % |
|----------------|-----------------|-----------------|
| 9 | 1 | ~10% |
| 4 | 1 | ~20% |
| 3 | 1 | ~25% |
| 1 | 1 | ~50% |
| 0 | 4 | 100% (fully promoted) |

### Canary Advantages & Disadvantages

| Advantage | Disadvantage |
|-----------|-------------|
| Low risk — only small % of users affected | Both versions running simultaneously |
| Real production testing | Data/state compatibility needed |
| Easy rollback (delete canary) | Traffic split is coarse (pod count based) |
| Gradual rollout | Precise % control needs Ingress/service mesh |

---

## 11. Updating a Deployment

### Method 1: kubectl set image (imperative — fastest for CKA)

```bash
kubectl set image deployment/web nginx=nginx:1.25
#                          ^     ^        ^
#                deploy-name  container  new-image

# Verify
kubectl rollout status deployment/web
```

### Method 2: kubectl edit

```bash
kubectl edit deployment web
# Change image field in editor, save → triggers rollout
```

### Method 3: Edit YAML and apply (declarative)

```bash
# Edit deployment.yaml: change image: nginx:1.24 → nginx:1.25
kubectl apply -f deployment.yaml
```

### Method 4: kubectl patch

```bash
kubectl patch deployment web -p '{"spec":{"template":{"spec":{"containers":[{"name":"nginx","image":"nginx:1.25"}]}}}}'
```

### Updating other fields

```bash
# Update environment variable
kubectl set env deployment/web APP_ENV=staging

# Update resource limits
kubectl set resources deployment/web --limits=cpu=500m,memory=512Mi

# Update replicas
kubectl scale deployment web --replicas=5

# Add a label to pod template (triggers rollout)
kubectl patch deployment web -p '{"spec":{"template":{"metadata":{"labels":{"version":"2.0"}}}}}'
```

### Annotate updates for rollout history

```bash
# --record is deprecated but annotation is useful for tracking
kubectl set image deployment/web nginx=nginx:1.25 --record

# Better approach — add annotation manually
kubectl annotate deployment web kubernetes.io/change-cause="Update nginx to 1.25 for security patch"
```

---

## 12. Rollback a Deployment

### View rollout history

```bash
kubectl rollout history deployment/web

# Output:
# REVISION  CHANGE-CAUSE
# 1         kubectl create deployment web --image=nginx:1.24
# 2         Update nginx to 1.25
# 3         Update nginx to 1.26

# View details of a specific revision
kubectl rollout history deployment/web --revision=2
```

### Rollback to previous version

```bash
# Undo last rollout (go back one revision)
kubectl rollout undo deployment/web

# Verify rollback
kubectl rollout status deployment/web
kubectl get deployment web -o wide   # shows current image
```

### Rollback to a specific revision

```bash
kubectl rollout undo deployment/web --to-revision=1
```

### How rollback works internally

```
Before rollback:
  RS v3 (current) → 3 pods
  RS v2 (old)     → 0 pods
  RS v1 (oldest)  → 0 pods

After undo:
  RS v2 (now current) → 3 pods (scaled up)
  RS v3 (old)         → 0 pods (scaled down)
  RS v1 (oldest)      → 0 pods
```

```bash
# See the ReplicaSets created by deployment
kubectl get replicasets -l app=web
kubectl get rs
```

### Controlling history limit

```yaml
spec:
  revisionHistoryLimit: 5    # Keep last 5 ReplicaSets (default: 10)
                             # Set to 0 to disable rollback (saves resources)
```

---

## 13. Pausing and Resuming Deployments

Useful when you want to make **multiple changes** before triggering a rollout.

```bash
# Pause the deployment
kubectl rollout pause deployment/web

# Make changes — these won't trigger a rollout
kubectl set image deployment/web nginx=nginx:1.25
kubectl set resources deployment/web --limits=cpu=500m,memory=512Mi
kubectl set env deployment/web LOG_LEVEL=debug

# Resume — NOW the rollout happens with ALL changes at once
kubectl rollout resume deployment/web

# Watch the single combined rollout
kubectl rollout status deployment/web
```

---

## 14. Scaling a Deployment

### Imperative scaling

```bash
kubectl scale deployment web --replicas=10

# Scale to 0 (stop all pods, keep deployment)
kubectl scale deployment web --replicas=0
```

### Declarative scaling

```bash
# Edit deployment.yaml: change replicas: 3 → replicas: 10
kubectl apply -f deployment.yaml
```

### Horizontal Pod Autoscaler (HPA)

```bash
# Create HPA imperatively
kubectl autoscale deployment web --min=2 --max=20 --cpu-percent=50

# View HPA
kubectl get hpa
```

```yaml
# hpa.yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: web-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: web
  minReplicas: 2
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 50
  - type: Resource
    resource:
      name: memory
      target:
        type: AverageValue
        averageValue: 200Mi
```

---

## 15. Deployment with ConfigMap and Secret

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: web-config
data:
  APP_ENV: "production"
  LOG_LEVEL: "info"
  DB_HOST: "postgres-service"
---
# secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: web-secret
type: Opaque
data:
  DB_PASSWORD: cGFzc3dvcmQxMjM=    # base64 encoded: password123
  API_KEY: bXlhcGlrZXk=            # base64 encoded: myapikey
---
# deployment-with-config.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-configured
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web-configured
  template:
    metadata:
      labels:
        app: web-configured
    spec:
      containers:
      - name: app
        image: nginx:1.25
        envFrom:
        - configMapRef:
            name: web-config     # Load ALL configmap keys as env vars
        - secretRef:
            name: web-secret     # Load ALL secret keys as env vars
        volumeMounts:
        - name: config-vol
          mountPath: /etc/app
      volumes:
      - name: config-vol
        configMap:
          name: web-config
```

---

## 16. Deployment Status and Conditions

### Check Deployment status

```bash
kubectl get deployment web

# Output:
# NAME   READY   UP-TO-DATE   AVAILABLE   AGE
# web    3/3     3            3           10m
#        ^       ^            ^
#    ready/desired  updated   available
```

### Deployment Conditions

```bash
kubectl describe deployment web | grep -A 20 Conditions

# Conditions:
#   Type             Status  Reason
#   ----             ------  ------
#   Progressing      True    NewReplicaSetAvailable
#   Available        True    MinimumReplicasAvailable
```

| Condition | Meaning |
|-----------|---------|
| `Progressing=True` | Rollout in progress OR completed successfully |
| `Progressing=False` | Rollout failed (exceeded progressDeadlineSeconds) |
| `Available=True` | Minimum available replicas are running |
| `Available=False` | Fewer than minAvailable replicas ready |

### Deployment Status Fields

```bash
kubectl get deployment web -o jsonpath='{.status}'

# Key fields:
# .status.replicas            - total pods
# .status.readyReplicas       - ready pods
# .status.updatedReplicas     - pods with latest template
# .status.availableReplicas   - pods meeting minReadySeconds
# .status.observedGeneration  - last processed spec change
```

---

## 17. Useful kubectl Commands

```bash
# ── Create ────────────────────────────────────────────────
kubectl create deployment web --image=nginx --replicas=3
kubectl create deployment web --image=nginx --replicas=3 --dry-run=client -o yaml > dep.yaml
kubectl apply -f deployment.yaml

# ── Get Info ─────────────────────────────────────────────
kubectl get deployments
kubectl get deploy                                   # short name
kubectl get deploy -o wide                           # shows image, selector
kubectl get deploy -o yaml                           # full yaml
kubectl get deploy web -o jsonpath='{.spec.template.spec.containers[0].image}'
kubectl get deploy --all-namespaces
kubectl get deploy -n production

# ── Describe ─────────────────────────────────────────────
kubectl describe deployment web
# Shows: replicas, strategy, pod template, conditions, events

# ── Scale ────────────────────────────────────────────────
kubectl scale deployment web --replicas=5
kubectl scale deployment web --replicas=0              # stop all pods
kubectl autoscale deployment web --min=2 --max=10 --cpu-percent=70

# ── Update Image ─────────────────────────────────────────
kubectl set image deployment/web nginx=nginx:1.25
kubectl set image deployment/web nginx=nginx:1.25 --record   # (deprecated but useful)

# ── Update Env / Resources ───────────────────────────────
kubectl set env deployment/web DB_HOST=new-db-host
kubectl set resources deployment/web --limits=cpu=500m,memory=256Mi

# ── Rollout ──────────────────────────────────────────────
kubectl rollout status deployment/web                  # watch rollout
kubectl rollout history deployment/web                 # view revisions
kubectl rollout history deployment/web --revision=2    # view specific revision
kubectl rollout undo deployment/web                    # rollback one step
kubectl rollout undo deployment/web --to-revision=1    # rollback to revision 1
kubectl rollout pause deployment/web                   # pause updates
kubectl rollout resume deployment/web                  # resume updates
kubectl rollout restart deployment/web                 # restart all pods (rolling)

# ── Edit ─────────────────────────────────────────────────
kubectl edit deployment web

# ── Delete ───────────────────────────────────────────────
kubectl delete deployment web
kubectl delete -f deployment.yaml

# ── Watch Pods ───────────────────────────────────────────
kubectl get pods -l app=web -w
kubectl get replicasets -l app=web                    # see RS history

# ── Check Owning ReplicaSet ──────────────────────────────
kubectl get rs
kubectl describe rs <rs-name>

# ── Annotate for change history ──────────────────────────
kubectl annotate deployment web kubernetes.io/change-cause="Upgraded nginx to 1.25"
```

---

## 18. Common Interview Questions

**Q: What is the difference between a Deployment and a ReplicaSet?**
> A ReplicaSet only ensures a desired number of Pod replicas are running. A Deployment adds rolling updates, rollback capability, and revision history on top of a ReplicaSet. In production, you always use Deployments — they manage ReplicaSets internally.

**Q: What are the two built-in deployment strategies?**
> `RollingUpdate` (default): Replaces Pods gradually, zero downtime.
> `Recreate`: Terminates all old Pods before creating new ones, causes downtime.

**Q: What are maxSurge and maxUnavailable?**
> `maxSurge`: How many extra Pods above the desired count can exist during a rolling update.
> `maxUnavailable`: How many Pods below the desired count are acceptable during a rolling update.
> Both can be absolute numbers or percentages.

**Q: How does Kubernetes achieve zero-downtime rolling updates?**
> By using `readinessProbe` — Kubernetes only removes an old Pod after the new Pod passes its readiness check. Combined with `maxUnavailable: 0`, this ensures traffic is never routed to an unhealthy Pod.

**Q: How do you roll back a Deployment?**
> `kubectl rollout undo deployment/web` — reverts to the previous ReplicaSet.
> `kubectl rollout undo deployment/web --to-revision=2` — reverts to a specific revision.

**Q: What is the difference between Blue-Green and Canary deployments?**
> Blue-Green: Two full environments, instant 100% traffic switch via Service selector change.
> Canary: Both versions get real traffic simultaneously (small % to new version), traffic split proportional to replica count. Gradual promotion.

**Q: How many ReplicaSets does a Deployment keep?**
> Controlled by `revisionHistoryLimit` (default: 10). Old ReplicaSets are kept with 0 replicas for rollback. Reduce this to save resources if rollback history is not needed.

**Q: How do you trigger a new rollout without changing the image?**
> `kubectl rollout restart deployment/web` — replaces all Pods with the same spec. Useful to pick up changes in ConfigMaps/Secrets mounted as environment variables, or to force a restart.

**Q: What happens if a rolling update gets stuck?**
> After `progressDeadlineSeconds` (default: 600s), the Deployment is marked as failed with condition `Progressing=False`. You must diagnose the issue (bad image, failed probes) and fix or rollback.

**Q: Can you pause a Deployment rollout mid-way?**
> Yes — `kubectl rollout pause deployment/web`. The partial rollout stops (some pods may already be updated). Resume with `kubectl rollout resume deployment/web`.

---

*Notes by ITkannadigaru | CKA 2026 Certification*

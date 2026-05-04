# Kubernetes VPA — Vertical Pod Autoscaler Complete Guide

> VPA watches how much CPU and memory your containers actually use and adjusts their requests and limits to fit — so you stop over-provisioning and stop running out of resources.

---

## Table of Contents

1. [What is VPA?](#1-what-is-vpa)
2. [HPA vs VPA — When to Use Which](#2-hpa-vs-vpa--when-to-use-which)
3. [VPA Architecture](#3-vpa-architecture)
4. [VPA Modes](#4-vpa-modes)
5. [Installing VPA](#5-installing-vpa)
6. [VPA Spec — Full Reference](#6-vpa-spec--full-reference)
7. [VPA in Off Mode — Recommendations Only](#7-vpa-in-off-mode--recommendations-only)
8. [VPA in Auto Mode — Automatic Resizing](#8-vpa-in-auto-mode--automatic-resizing)
9. [VPA with Container-Level Policies](#9-vpa-with-container-level-policies)
10. [VPA + HPA — Can They Coexist?](#10-vpa--hpa--can-they-coexist)
11. [Practical Demo](#11-practical-demo)
12. [Limitations of VPA](#12-limitations-of-vpa)
13. [Common Interview Questions](#13-common-interview-questions)
14. [Exam Practice Questions](#14-exam-practice-questions)

---

## 1. What is VPA?

**VPA (Vertical Pod Autoscaler)** automatically adjusts the **CPU and memory requests and limits** of containers in Pods based on their actual resource usage history.

```
  Without VPA (manual, often wrong):       With VPA (auto-tuned):

  Developer guesses:                        VPA observes over time:
  requests.cpu: 500m                        requests.cpu: 120m  ← actual usage
  requests.memory: 512Mi       →            requests.memory: 180Mi ← actual usage
  limits.cpu: 1000m                         limits.cpu: 300m
  limits.memory: 1Gi                        limits.memory: 400Mi

  Result: 4x wasted resources               Result: efficient bin-packing
```

**What VPA adjusts:**
- `resources.requests.cpu`
- `resources.requests.memory`
- `resources.limits.cpu`
- `resources.limits.memory`

**What VPA does NOT do:**
- Change the number of replicas (that's HPA)
- Store metrics long-term (uses its own history mechanism)

---

## 2. HPA vs VPA — When to Use Which

```
  Stateless apps (web servers, APIs):       Stateful apps (databases, ML jobs):
  ─────────────────────────────────         ──────────────────────────────────

  Traffic spikes → add more pods            Single large workload → needs more RAM
  
  Use: HPA                                  Use: VPA
  Scale: out (more replicas)                Scale: up (bigger pod)
```

| Dimension | HPA | VPA |
|-----------|-----|-----|
| **What it changes** | Number of replicas | CPU/memory per container |
| **Scale direction** | Horizontal (out/in) | Vertical (up/down) |
| **Best for** | Stateless, traffic-driven workloads | Stateful, single-instance workloads |
| **Pod restart required** | No (new pods added) | Yes (pod must restart to apply new limits) |
| **Works with** | CPU %, memory, custom metrics | Observed usage history |
| **Requires Metrics Server** | Yes | Yes (+ VPA's own metrics store) |

---

## 3. VPA Architecture

VPA consists of three components, each running as a separate Deployment:

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                        VPA Components                            │
  │                                                                  │
  │  ┌───────────────────────┐                                       │
  │  │  VPA Recommender      │  ← watches Pod metrics, calculates    │
  │  │  (reads metrics)      │    optimal CPU/memory recommendations │
  │  └───────────┬───────────┘                                       │
  │              │ writes recommendations to VPA object              │
  │              ▼                                                   │
  │  ┌───────────────────────┐                                       │
  │  │  VPA object           │  ← stores: lowerBound, upperBound,   │
  │  │  (CR with status)     │    target, uncappedTarget             │
  │  └───────────┬───────────┘                                       │
  │              │                                                   │
  │    ┌─────────┴──────────┐                                       │
  │    ▼                    ▼                                       │
  │  ┌──────────────┐  ┌──────────────────────┐                     │
  │  │ VPA Updater  │  │ VPA Admission Plugin  │                    │
  │  │ (evicts pods │  │ (mutates pod spec at  │                    │
  │  │  to resize)  │  │  creation time)       │                    │
  │  └──────────────┘  └──────────────────────┘                     │
  └──────────────────────────────────────────────────────────────────┘
```

| Component | Role |
|-----------|------|
| **Recommender** | Reads metrics history, computes recommended requests/limits |
| **Updater** | Evicts pods that are using non-recommended resources (triggers restart) |
| **Admission Controller** | Patches new/restarted pods with the recommended values at creation |

---

## 4. VPA Modes

VPA supports four operating modes:

| Mode | What it does | Pod restart? |
|------|-------------|-------------|
| **Off** | Computes recommendations, does NOT apply them | No |
| **Initial** | Applies recommendations ONLY when Pod is first created (not after) | No (only on new pods) |
| **Auto** | Applies recommendations, evicts pods to resize (like Recreate) | Yes |
| **Recreate** | Same as Auto but only uses Recreate update strategy | Yes |

```
  Off mode:      VPA thinks → writes recommendations → you read and decide
  Initial mode:  VPA thinks → applies on pod creation → never touches again
  Auto mode:     VPA thinks → applies now → evicts+recreates pod to resize
```

> **Start with `Off` mode** to see what VPA recommends before letting it auto-resize. Validate the recommendations, then switch to `Initial` or `Auto`.

---

## 5. Installing VPA

VPA is not built into Kubernetes — it's an add-on from the `kubernetes/autoscaler` repo.

### Step 1: Clone the repository

```bash
git clone https://github.com/kubernetes/autoscaler.git
cd autoscaler/vertical-pod-autoscaler
```

### Step 2: Install VPA components

```bash
# Install CRDs and all VPA components
./hack/vpa-up.sh

# This installs:
# - VPA CRDs (VerticalPodAutoscaler, VerticalPodAutoscalerCheckpoint)
# - vpa-recommender Deployment
# - vpa-updater Deployment
# - vpa-admission-controller Deployment + WebhookConfiguration
```

### Step 3: Verify installation

```bash
# Check all VPA pods are running
kubectl get pods -n kube-system | grep vpa

# Expected:
# vpa-admission-controller-xxx   1/1   Running
# vpa-recommender-xxx            1/1   Running
# vpa-updater-xxx                1/1   Running

# Check VPA CRDs
kubectl get crd | grep verticalpodautoscaler
# verticalpodautoscalercheckpoints.autoscaling.k8s.io
# verticalpodautoscalers.autoscaling.k8s.io
```

### Alternative: Helm installation

```bash
helm repo add fairwinds-stable https://charts.fairwinds.com/stable
helm repo update

helm install vpa fairwinds-stable/vpa \
  --namespace kube-system \
  --set recommender.enabled=true \
  --set updater.enabled=true \
  --set admissionController.enabled=true
```

### On Minikube

```bash
minikube addons enable vpa
kubectl get pods -n kube-system | grep vpa
```

---

## 6. VPA Spec — Full Reference

```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: my-app-vpa
  namespace: default
spec:
  # Target workload
  targetRef:
    apiVersion: apps/v1
    kind: Deployment         # or StatefulSet, DaemonSet, ReplicaSet
    name: my-app

  # Update policy
  updatePolicy:
    updateMode: "Auto"       # Off | Initial | Auto | Recreate

  # Per-container resource policies (optional)
  resourcePolicy:
    containerPolicies:
    - containerName: "*"     # applies to all containers
      minAllowed:
        cpu: 50m             # VPA will never recommend below this
        memory: 64Mi
      maxAllowed:
        cpu: "2"             # VPA will never recommend above this
        memory: 2Gi
      controlledResources:
      - cpu
      - memory
      controlledValues: RequestsAndLimits   # or RequestsOnly
```

### VPA Status — Reading Recommendations

```bash
kubectl describe vpa my-app-vpa
```

```yaml
status:
  recommendation:
    containerRecommendations:
    - containerName: my-app
      lowerBound:             # safe minimum (will definitely help)
        cpu: 25m
        memory: 128Mi
      target:                 # recommended value (what VPA will apply)
        cpu: 100m
        memory: 256Mi
      upperBound:             # upper safe bound (going higher is wasteful)
        cpu: 500m
        memory: 1Gi
      uncappedTarget:         # what VPA would recommend without min/max caps
        cpu: 85m
        memory: 230Mi
```

---

## 7. VPA in Off Mode — Recommendations Only

Use `Off` mode to get recommendations without any automatic changes. Perfect for right-sizing before committing.

```yaml
# vpa-off.yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: hamster-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: hamster
  updatePolicy:
    updateMode: "Off"         # ← only recommends, never applies
```

```bash
kubectl apply -f vpa-off.yaml

# Check recommendations (may take a few minutes for initial data)
kubectl describe vpa hamster-vpa

# Or get just the recommendation in JSON
kubectl get vpa hamster-vpa -o json | \
  python3 -c "import sys,json; d=json.load(sys.stdin); \
  [print(c['containerName'], c['target']) for c in d['status']['recommendation']['containerRecommendations']]"
```

---

## 8. VPA in Auto Mode — Automatic Resizing

```yaml
# vpa-auto.yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: hamster-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: hamster
  updatePolicy:
    updateMode: "Auto"         # ← recommends AND evicts pods to apply
  resourcePolicy:
    containerPolicies:
    - containerName: hamster
      minAllowed:
        cpu: 50m
        memory: 50Mi
      maxAllowed:
        cpu: "1"
        memory: 500Mi
```

**What happens in Auto mode:**
1. VPA Recommender watches Pod CPU/memory usage for a warm-up period (~several minutes to hours)
2. It writes recommendations to the VPA object's `.status`
3. VPA Updater checks if running Pods are "out of bounds" (using significantly different resources than recommended)
4. If out of bounds, Updater **evicts** (deletes) the Pod
5. VPA Admission Controller **intercepts** the new Pod creation and **patches** the resource requests/limits before the Pod starts

> **Warning**: VPA Auto mode restarts Pods. Do not use it for Pods where restarts are disruptive (single-replica databases, batch jobs mid-run).

---

## 9. VPA with Container-Level Policies

Fine-tune which containers VPA manages and what boundaries it uses.

```yaml
resourcePolicy:
  containerPolicies:
  # Main app container — let VPA tune it
  - containerName: app
    mode: Auto
    minAllowed:
      cpu: 100m
      memory: 256Mi
    maxAllowed:
      cpu: "4"
      memory: 4Gi
    controlledResources: ["cpu", "memory"]
    controlledValues: RequestsAndLimits   # adjust both requests and limits

  # Sidecar — recommendations only, don't auto-apply
  - containerName: istio-proxy
    mode: "Off"
    controlledValues: RequestsOnly         # only adjust requests, not limits
```

### controlledValues Options

| Value | Effect |
|-------|--------|
| `RequestsAndLimits` | Adjust both requests and limits (keeps ratio) |
| `RequestsOnly` | Adjust only requests; limits remain unchanged |

---

## 10. VPA + HPA — Can They Coexist?

Using both VPA and HPA on the same workload for the **same metric** causes conflicts:

```
  ✗ CONFLICT:
  VPA Auto + HPA CPU — both fighting over CPU, unstable behavior

  ✓ ALLOWED:
  VPA Auto + HPA custom metrics (e.g., requests-per-second)
  VPA Auto + HPA memory (if VPA is set to controlledResources: [cpu] only)
  VPA Off  + HPA any metric (VPA only gives advice, HPA actually scales)
```

**Safe combination:**

```yaml
# VPA: only tune memory, leave CPU to HPA
resourcePolicy:
  containerPolicies:
  - containerName: app
    controlledResources: ["memory"]   # VPA only adjusts memory

# HPA: scales replicas based on CPU
metrics:
- type: Resource
  resource:
    name: cpu
    target:
      type: Utilization
      averageUtilization: 60
```

---

## 11. Practical Demo

```bash
# === STEP 1: Install VPA (minikube) ===
minikube addons enable vpa
kubectl get pods -n kube-system | grep vpa

# === STEP 2: Deploy the hamster example ===
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: hamster
spec:
  replicas: 2
  selector:
    matchLabels:
      app: hamster
  template:
    metadata:
      labels:
        app: hamster
    spec:
      containers:
      - name: hamster
        image: registry.k8s.io/ubuntu-slim:0.1
        resources:
          requests:
            cpu: 100m          # intentionally low — VPA will suggest higher
            memory: 50Mi
        command:
        - /bin/sh
        - -c
        - "while true; do timeout 0.5s yes > /dev/null; sleep 0.5s; done"
EOF

kubectl rollout status deployment/hamster

# === STEP 3: Create VPA in Off mode first (observe only) ===
cat <<EOF | kubectl apply -f -
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: hamster-vpa
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: hamster
  updatePolicy:
    updateMode: "Off"
  resourcePolicy:
    containerPolicies:
    - containerName: hamster
      minAllowed:
        cpu: 50m
        memory: 50Mi
      maxAllowed:
        cpu: "1"
        memory: 512Mi
EOF

# === STEP 4: Wait for recommendations (3-5 minutes) ===
kubectl describe vpa hamster-vpa

# Look for:
# status:
#   recommendation:
#     containerRecommendations:
#     - containerName: hamster
#       target:
#         cpu: "587m"   ← VPA suggests much more than our 100m
#         memory: "..."

# === STEP 5: Switch to Auto mode ===
kubectl patch vpa hamster-vpa \
  --type='json' \
  -p='[{"op":"replace","path":"/spec/updatePolicy/updateMode","value":"Auto"}]'

# === STEP 6: Watch pods get evicted and recreated with new resources ===
kubectl get pods -l app=hamster -w
# You will see pods Terminating then new ones Starting

# === STEP 7: Check new pod has updated resources ===
kubectl get pod -l app=hamster -o yaml | grep -A8 resources

# Resources should now match VPA target recommendation

# === STEP 8: Compare before/after ===
# Before: requests.cpu: 100m  (what we set)
# After:  requests.cpu: ~587m (what VPA set based on actual usage)

# === CLEANUP ===
kubectl delete deployment hamster
kubectl delete vpa hamster-vpa
```

---

## 12. Limitations of VPA

| Limitation | Detail |
|-----------|--------|
| **Pod restart required** | VPA cannot resize a running container — it evicts and recreates the Pod |
| **Not for single replicas** | Evicting the only replica causes downtime |
| **HPA conflict** | Cannot use both on same metric for same workload |
| **Cold start** | VPA needs historical data (~few minutes to hours) before making recommendations |
| **Not in Kubernetes core** | Must be installed separately; not available on all managed k8s flavors |
| **Memory scaling is imprecise** | Apps don't always release memory — recommendations can be off |
| **Admission webhook dependency** | Auto/Initial mode requires the admission webhook to be running and reachable |

---

## 13. Common Interview Questions

**Q: What is VPA and what problem does it solve?**
> VPA (Vertical Pod Autoscaler) automatically adjusts the CPU and memory requests/limits on containers based on their observed usage history. It solves the problem of over-provisioning (wasted resources when requests are set too high) and under-provisioning (OOMKill or CPU throttling when requests are too low). It right-sizes containers without manual intervention.

---

**Q: What are the four VPA modes?**
> **Off**: Only generates recommendations, applies nothing. **Initial**: Applies recommendations only when a Pod is first created, never updates existing Pods. **Auto**: Applies recommendations and evicts Pods to resize them (most aggressive). **Recreate**: Same as Auto but only works with Recreate update strategy Deployments.

---

**Q: Can VPA and HPA be used together?**
> Only if they target **different metrics**. Using VPA Auto and HPA both on CPU causes conflicts. A safe pattern is: VPA controlling memory (set `controlledResources: ["memory"]`), HPA controlling replica count based on CPU utilization.

---

**Q: Why does VPA need to restart Pods?**
> Container resource requests and limits cannot be changed on a running container — it's a Linux kernel-level constraint. VPA must evict (delete) the Pod and let the Admission Controller inject the new resource values when the Pod is recreated by the ReplicaSet/Deployment controller.

---

**Q: What is the VPA Recommender?**
> The VPA Recommender is a component that continuously monitors Pod resource usage via the Metrics API, builds a histogram of usage patterns, and calculates the optimal resource requests/limits. It writes these recommendations to the VPA object's `.status.recommendation` field.

---

## 14. Exam Practice Questions

**1.** Create a VPA in `Off` mode for Deployment `api-server` in namespace `prod`.
```yaml
apiVersion: autoscaling.k8s.io/v1
kind: VerticalPodAutoscaler
metadata:
  name: api-server-vpa
  namespace: prod
spec:
  targetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: api-server
  updatePolicy:
    updateMode: "Off"
```

**2.** How do you read VPA recommendations?
```bash
kubectl describe vpa api-server-vpa -n prod
# Look at status.recommendation.containerRecommendations[].target
```

**3.** What VPA mode applies recommendations only to newly created Pods (not existing ones)?
> **`Initial`** mode.

**4.** Name the three VPA components and their roles.
> **Recommender** — reads metrics, calculates recommendations. **Updater** — evicts pods whose resources are out of bounds. **Admission Controller** — patches pod spec with new resource values at creation time.

**5.** You have a Deployment with 1 replica. What is the risk of using VPA in Auto mode?
> VPA Auto will evict (delete) the only Pod to resize it, causing **downtime** until the new Pod starts. Always ensure `minReplicas ≥ 2` (via Deployment or HPA) before enabling VPA Auto mode.

---

> **CKA Exam Tips**:
> - VPA is less commonly tested than HPA but know: Off → Initial → Auto progression
> - VPA requires pod restart to apply changes — always mention this in answers
> - `kubectl describe vpa <name>` shows recommendations in `.status`
> - VPA and HPA on same CPU metric = conflict — never do this

---

*Notes by ITkannadigaru | CKA 2026 Certification*

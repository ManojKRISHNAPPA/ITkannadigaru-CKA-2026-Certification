# Kubernetes Gateway API — Complete Guide

> Gateway API is the next-generation replacement for Ingress — expressive, extensible, role-oriented routing for HTTP, TCP, gRPC, and beyond.

---

## Table of Contents

1. [What is Gateway API?](#1-what-is-gateway-api)
2. [Gateway API vs Ingress — Why the Upgrade?](#2-gateway-api-vs-ingress--why-the-upgrade)
3. [Core Concepts and Resources](#3-core-concepts-and-resources)
   - [3.1 GatewayClass](#31-gatewayclass)
   - [3.2 Gateway](#32-gateway)
   - [3.3 HTTPRoute](#33-httproute)
   - [3.4 TCPRoute / TLSRoute / GRPCRoute](#34-tcproute--tlsroute--grpcroute)
4. [Role-Oriented Design](#4-role-oriented-design)
5. [Installing Gateway API CRDs](#5-installing-gateway-api-crds)
6. [Install a Gateway Controller](#6-install-a-gateway-controller)
   - [6.1 NGINX Gateway Fabric](#61-nginx-gateway-fabric)
   - [6.2 Envoy Gateway](#62-envoy-gateway)
   - [6.3 Istio as Gateway Controller](#63-istio-as-gateway-controller)
7. [HTTPRoute Rules — Deep Dive](#7-httproute-rules--deep-dive)
   - [7.1 Host-Based Routing](#71-host-based-routing)
   - [7.2 Path-Based Routing](#72-path-based-routing)
   - [7.3 Header-Based Routing](#73-header-based-routing)
   - [7.4 Traffic Splitting (Canary)](#74-traffic-splitting-canary)
8. [TLS Configuration](#8-tls-configuration)
9. [Cross-Namespace Routing](#9-cross-namespace-routing)
10. [Simple End-to-End Demo](#10-simple-end-to-end-demo)
11. [Traffic Splitting Demo — Canary Release](#11-traffic-splitting-demo--canary-release)
12. [Gateway API vs Ingress — Full Comparison](#12-gateway-api-vs-ingress--full-comparison)
13. [Common Interview Questions](#13-common-interview-questions)
14. [Exam Practice Questions](#14-exam-practice-questions)

---

## 1. What is Gateway API?

**Gateway API** is a collection of Kubernetes CRDs (Custom Resource Definitions) that provide a richer, more expressive, and more extensible way to manage traffic routing into and within a Kubernetes cluster.

It is the official **successor to the Ingress API**, maintained by the Kubernetes SIG-Network group and released as GA (v1.0) in October 2023.

```
  Evolution of Kubernetes Traffic APIs:
  
  v1.0  (2014)  ──────► Services (NodePort, LoadBalancer)
  v1.0  (2019)  ──────► Ingress  (HTTP/HTTPS L7 routing)
  GA    (2023)  ──────► Gateway API (multi-protocol, role-oriented, extensible)
```

**Key properties:**
- **Role-oriented**: Different personas (infrastructure admin, cluster operator, app developer) manage different objects
- **Expressive**: Header matching, traffic weighting, request mirroring, URL rewriting — all native
- **Extensible**: Custom filter support per controller
- **Multi-protocol**: HTTP, HTTPS, TCP, TLS, gRPC, UDP
- **Cross-namespace**: Routes in one namespace can bind to Gateways in another

---

## 2. Gateway API vs Ingress — Why the Upgrade?

### Problems with Ingress

```
  Ingress problems:
  
  1. Limited expressiveness:
     No native header matching, traffic splitting, or request mirroring
     → Workaround: annotations (nginx.ingress.kubernetes.io/canary-weight: "20")
     → Annotations are non-portable — different for every controller!

  2. Single resource does too much:
     One Ingress mixes infrastructure config (class, TLS) with app routing rules
     → Can't separate concerns across teams

  3. Protocol locked:
     Only HTTP and HTTPS — no TCP, gRPC, UDP routing in spec

  4. Poor cross-namespace support:
     Each namespace needs its own Ingress — no shared gateway
```

### How Gateway API Solves This

```
  Gateway API solution:

  1. Expressive by default:
     header matching, path rewrites, traffic splitting — all in spec, no annotations needed

  2. Role separation:
     Infra admin → GatewayClass  (which controller)
     Cluster ops → Gateway       (entry point, TLS, listeners)
     App devs    → HTTPRoute     (path/host rules, backends)

  3. Multi-protocol:
     HTTPRoute, TCPRoute, TLSRoute, GRPCRoute, UDPRoute

  4. Cross-namespace routing with ReferenceGrant
```

---

## 3. Core Concepts and Resources

### The Three-Layer Model

```
  ┌───────────────────────────────────────────────────────────────┐
  │ Layer 1: Infrastructure                                        │
  │                                                               │
  │  ┌──────────────────────────────────────────────────────┐    │
  │  │  GatewayClass                                         │    │
  │  │  "Which controller handles Gateways of this class?"  │    │
  │  │  Managed by: Infrastructure Provider / Cluster Admin │    │
  │  └──────────────────────────────────────────────────────┘    │
  └───────────────────────────────────────────────────────────────┘
                          │
  ┌───────────────────────▼───────────────────────────────────────┐
  │ Layer 2: Platform                                             │
  │                                                               │
  │  ┌──────────────────────────────────────────────────────┐    │
  │  │  Gateway                                              │    │
  │  │  "Entry point: what ports, protocols, and TLS certs" │    │
  │  │  Managed by: Cluster Operator                        │    │
  │  └──────────────────────────────────────────────────────┘    │
  └───────────────────────────────────────────────────────────────┘
                          │
  ┌───────────────────────▼───────────────────────────────────────┐
  │ Layer 3: Application                                          │
  │                                                               │
  │  ┌──────────────────────────────────────────────────────┐    │
  │  │  HTTPRoute / TCPRoute / GRPCRoute                     │    │
  │  │  "How traffic is routed to backend services"         │    │
  │  │  Managed by: Application Developer                   │    │
  │  └──────────────────────────────────────────────────────┘    │
  └───────────────────────────────────────────────────────────────┘
```

---

### 3.1 GatewayClass

A **GatewayClass** is a cluster-scoped resource that defines which controller implements Gateways of this class. Similar to `IngressClass`.

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: GatewayClass
metadata:
  name: nginx
spec:
  controllerName: gateway.nginx.org/nginx-gateway-controller
  description: "Nginx Gateway Fabric controller"
```

```bash
# List available gateway classes (installed by controllers)
kubectl get gatewayclass
```

---

### 3.2 Gateway

A **Gateway** is a namespace-scoped resource that defines a load balancer entry point: which ports to listen on, which protocols, and TLS configuration.

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: prod-gateway
  namespace: gateway-infra     # often a dedicated infra namespace
spec:
  gatewayClassName: nginx      # references the GatewayClass

  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces:
        from: All              # allow routes from any namespace

  - name: https
    protocol: HTTPS
    port: 443
    tls:
      mode: Terminate
      certificateRefs:
      - name: prod-tls-secret
        namespace: gateway-infra
    allowedRoutes:
      namespaces:
        from: Selector
        selector:
          matchLabels:
            gateway-access: "true"
```

```bash
# Check gateway status (shows EXTERNAL-IP and ready conditions)
kubectl get gateway -n gateway-infra

# NAME            CLASS   ADDRESS         PROGRAMMED   AGE
# prod-gateway    nginx   34.120.55.201   True         5m
```

---

### 3.3 HTTPRoute

An **HTTPRoute** defines how HTTP/HTTPS traffic is routed from a Gateway to backend Services.

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: web-route
  namespace: default
spec:
  parentRefs:
  - name: prod-gateway           # which Gateway to attach to
    namespace: gateway-infra
    sectionName: http            # which listener on the Gateway

  hostnames:
  - "example.com"                # optional host filter

  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /api
    backendRefs:
    - name: api-service
      port: 8080
      weight: 100

  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: frontend-service
      port: 80
```

---

### 3.4 TCPRoute / TLSRoute / GRPCRoute

```yaml
# TCPRoute — for raw TCP workloads (databases, custom protocols)
apiVersion: gateway.networking.k8s.io/v1alpha2
kind: TCPRoute
metadata:
  name: db-route
spec:
  parentRefs:
  - name: tcp-gateway
    sectionName: db-listener
  rules:
  - backendRefs:
    - name: postgres-service
      port: 5432

# GRPCRoute — for gRPC services (GA in Gateway API v1.1)
apiVersion: gateway.networking.k8s.io/v1
kind: GRPCRoute
metadata:
  name: grpc-route
spec:
  parentRefs:
  - name: prod-gateway
    sectionName: https
  hostnames:
  - "grpc.example.com"
  rules:
  - matches:
    - method:
        service: com.example.UserService
        method: GetUser
    backendRefs:
    - name: user-grpc-service
      port: 50051
```

---

## 4. Role-Oriented Design

Gateway API was explicitly designed around **three personas**:

```
  Infrastructure Provider       Cluster Operator         Application Developer
  ─────────────────────────     ─────────────────         ───────────────────────
  Manages: GatewayClass         Manages: Gateway          Manages: HTTPRoute
                                                           TCPRoute, GRPCRoute

  "I operate the             "I configure entry        "I control how my app's
  underlying LB/proxy        points, ports, TLS,       traffic is routed"
  infrastructure"            and namespace access"

  Example: cloud provider    Example: platform team    Example: dev team
  or nginx operator          or SRE team

  Scope: Cluster             Scope: Namespace          Scope: Namespace
         (GatewayClass is           (Gateway)                  (Routes)
          cluster-scoped)
```

This separation means app developers **only touch Routes** — they cannot accidentally misconfigure the Gateway's TLS or change which ports are exposed.

---

## 5. Installing Gateway API CRDs

The Gateway API CRDs must be installed before any controller. There are two channels:

| Channel | Stability | Includes |
|---------|-----------|---------|
| **Standard** | GA (stable) | GatewayClass, Gateway, HTTPRoute, GRPCRoute, ReferenceGrant |
| **Experimental** | Alpha/Beta | TCPRoute, TLSRoute, UDPRoute, BackendTLSPolicy, etc. |

```bash
# Install Standard channel (recommended for production)
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.1/standard-install.yaml

# Install Experimental channel (for TCPRoute, UDPRoute, etc.)
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.1/experimental-install.yaml

# Verify CRDs are installed
kubectl get crd | grep gateway.networking.k8s.io

# Expected:
# gatewayclasses.gateway.networking.k8s.io
# gateways.gateway.networking.k8s.io
# httproutes.gateway.networking.k8s.io
# grpcroutes.gateway.networking.k8s.io
# referencegrants.gateway.networking.k8s.io
```

---

## 6. Install a Gateway Controller

CRDs alone do nothing — you need a controller that implements the Gateway API.

### 6.1 NGINX Gateway Fabric

The official NGINX implementation of Gateway API.

```bash
# Step 1: Install the NGINX Gateway Fabric CRDs (in addition to Gateway API CRDs)
kubectl apply -f https://raw.githubusercontent.com/nginx/nginx-gateway-fabric/v1.4.0/deploy/crds.yaml

# Step 2: Install NGINX Gateway Fabric
kubectl apply -f https://raw.githubusercontent.com/nginx/nginx-gateway-fabric/v1.4.0/deploy/default/deploy.yaml

# Step 3: Verify
kubectl get pods -n nginx-gateway
# nginx-gateway-xxx   2/2   Running

# Check GatewayClass was created
kubectl get gatewayclass
# NAME    CONTROLLER                                   ACCEPTED   AGE
# nginx   gateway.nginx.org/nginx-gateway-controller   True       1m

# Get the Gateway's external IP (may take a minute)
kubectl get svc -n nginx-gateway
```

---

### 6.2 Envoy Gateway

Envoy Gateway is a Kubernetes-native implementation backed by Envoy Proxy.

```bash
# Install Envoy Gateway
helm install eg oci://docker.io/envoyproxy/gateway-helm \
  --version v1.2.0 \
  -n envoy-gateway-system \
  --create-namespace

# Wait for it to be ready
kubectl rollout status deployment/envoy-gateway -n envoy-gateway-system --timeout=120s

# Verify GatewayClass
kubectl get gatewayclass
# NAME      CONTROLLER                        ACCEPTED
# eg        gateway.envoyproxy.io/gatewayclass   True

# Create a Gateway
cat <<EOF | kubectl apply -f -
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: eg
  namespace: default
spec:
  gatewayClassName: eg
  listeners:
  - name: http
    protocol: HTTP
    port: 80
EOF

kubectl get gateway eg
```

---

### 6.3 Istio as Gateway Controller

If you have Istio installed, it supports Gateway API natively.

```bash
# Install Istio (minimal profile)
istioctl install --set profile=minimal -y

# Istio automatically registers its GatewayClass
kubectl get gatewayclass
# istio   istio.io/gateway-controller   True

# Create a Gateway using Istio
cat <<EOF | kubectl apply -f -
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: my-gateway
  namespace: default
  annotations:
    networking.istio.io/service-type: ClusterIP
spec:
  gatewayClassName: istio
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces:
        from: All
EOF
```

---

## 7. HTTPRoute Rules — Deep Dive

### 7.1 Host-Based Routing

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: multi-host-route
spec:
  parentRefs:
  - name: prod-gateway
    namespace: infra

  rules:
  - matches:
    - headers:
      - name: ":authority"
    # Use hostnames field at spec level for host matching:
  hostnames:
  - "api.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: api-service
      port: 8080
```

Or with separate HTTPRoute objects per host (cleaner for team separation):

```yaml
# HTTPRoute for api.example.com
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: api-route
  namespace: api-team
spec:
  parentRefs:
  - name: prod-gateway
    namespace: infra
  hostnames:
  - "api.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: api-svc
      port: 8080
---
# HTTPRoute for web.example.com (different namespace!)
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: web-route
  namespace: web-team
spec:
  parentRefs:
  - name: prod-gateway
    namespace: infra
  hostnames:
  - "web.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: web-svc
      port: 80
```

---

### 7.2 Path-Based Routing

```yaml
spec:
  rules:
  # Exact path
  - matches:
    - path:
        type: Exact
        value: /healthz
    backendRefs:
    - name: health-svc
      port: 8080

  # Prefix path (most common)
  - matches:
    - path:
        type: PathPrefix
        value: /api/v2
    backendRefs:
    - name: api-v2-svc
      port: 8080

  # Regex path (experimental / controller-specific)
  - matches:
    - path:
        type: RegularExpression
        value: /user/[0-9]+/profile
    backendRefs:
    - name: user-svc
      port: 9090
```

---

### 7.3 Header-Based Routing

Native in Gateway API — no annotations needed.

```yaml
spec:
  rules:
  # Route beta users to new version
  - matches:
    - headers:
      - name: X-Beta-User
        value: "true"
    backendRefs:
    - name: api-v2-svc
      port: 8080

  # Route mobile users
  - matches:
    - headers:
      - name: User-Agent
        type: RegularExpression
        value: ".*(iPhone|Android).*"
    backendRefs:
    - name: mobile-api-svc
      port: 8080

  # Default route
  - backendRefs:
    - name: api-svc
      port: 8080
```

---

### 7.4 Traffic Splitting (Canary)

Split traffic by weight between two backends — no annotations, purely in spec.

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: canary-route
spec:
  parentRefs:
  - name: prod-gateway
  hostnames:
  - "app.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: app-stable        # current production version
      port: 80
      weight: 90              # 90% of traffic
    - name: app-canary        # new version under test
      port: 80
      weight: 10              # 10% of traffic
```

---

## 8. TLS Configuration

### Terminate TLS at Gateway

```yaml
# Step 1: Create TLS secret
kubectl create secret tls example-tls \
  --cert=tls.crt \
  --key=tls.key \
  -n gateway-infra

# Step 2: Gateway with TLS termination
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: secure-gateway
  namespace: gateway-infra
spec:
  gatewayClassName: nginx
  listeners:
  - name: https
    protocol: HTTPS
    port: 443
    tls:
      mode: Terminate          # decrypt here, send plain HTTP to backends
      certificateRefs:
      - kind: Secret
        name: example-tls
        namespace: gateway-infra
    allowedRoutes:
      namespaces:
        from: All

  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces:
        from: All
```

### HTTPRoute for HTTPS listener

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: secure-route
spec:
  parentRefs:
  - name: secure-gateway
    namespace: gateway-infra
    sectionName: https         # bind to the HTTPS listener
  hostnames:
  - "secure.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: web-service
      port: 80
```

### HTTP → HTTPS Redirect

```yaml
# Attach to HTTP listener and redirect to HTTPS
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: http-redirect
spec:
  parentRefs:
  - name: secure-gateway
    sectionName: http          # bind to HTTP listener
  rules:
  - filters:
    - type: RequestRedirect
      requestRedirect:
        scheme: https
        statusCode: 301        # permanent redirect
```

---

## 9. Cross-Namespace Routing

App teams can route from their namespace to a shared Gateway in another namespace, but this requires a **ReferenceGrant**.

```
  gateway-infra namespace     │    app-team namespace
  ────────────────────────    │    ──────────────────
  Gateway: prod-gateway       │    HTTPRoute: app-route
                              │    parentRef → prod-gateway (in gateway-infra)
  ReferenceGrant: allow       │
  → allows app-team to        │
    reference prod-gateway    │
```

```yaml
# ReferenceGrant in the Gateway's namespace (gateway-infra)
apiVersion: gateway.networking.k8s.io/v1beta1
kind: ReferenceGrant
metadata:
  name: allow-app-team
  namespace: gateway-infra     # must be in the Gateway's namespace
spec:
  from:
  - group: gateway.networking.k8s.io
    kind: HTTPRoute
    namespace: app-team         # allow routes from this namespace
  to:
  - group: gateway.networking.k8s.io
    kind: Gateway
    name: prod-gateway          # to reference this specific Gateway
```

```yaml
# HTTPRoute in app-team namespace referencing gateway in gateway-infra
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: app-route
  namespace: app-team
spec:
  parentRefs:
  - name: prod-gateway
    namespace: gateway-infra   # cross-namespace reference (allowed by ReferenceGrant)
  hostnames:
  - "app.example.com"
  rules:
  - backendRefs:
    - name: app-svc
      port: 80
```

---

## 10. Simple End-to-End Demo

This demo uses **Envoy Gateway** on a local cluster.

```bash
# === STEP 1: Install CRDs and Envoy Gateway ===
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.1/standard-install.yaml

helm install eg oci://docker.io/envoyproxy/gateway-helm \
  --version v1.2.0 \
  -n envoy-gateway-system \
  --create-namespace

kubectl rollout status deployment/envoy-gateway -n envoy-gateway-system

# === STEP 2: Create Gateway ===
cat <<EOF | kubectl apply -f -
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: demo-gateway
  namespace: default
spec:
  gatewayClassName: eg
  listeners:
  - name: http
    protocol: HTTP
    port: 80
    allowedRoutes:
      namespaces:
        from: All
EOF

kubectl get gateway demo-gateway -w
# Wait for PROGRAMMED=True and ADDRESS to populate

# === STEP 3: Deploy sample apps ===
kubectl create deployment app-v1 --image=hashicorp/http-echo -- /http-echo -text="App Version 1"
kubectl create deployment app-v2 --image=hashicorp/http-echo -- /http-echo -text="App Version 2"
kubectl expose deployment app-v1 --port=5678 --name=app-v1-svc
kubectl expose deployment app-v2 --port=5678 --name=app-v2-svc

# === STEP 4: Create HTTPRoute ===
cat <<EOF | kubectl apply -f -
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: demo-route
  namespace: default
spec:
  parentRefs:
  - name: demo-gateway
    namespace: default
  hostnames:
  - "demo.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /v1
    backendRefs:
    - name: app-v1-svc
      port: 5678

  - matches:
    - path:
        type: PathPrefix
        value: /v2
    backendRefs:
    - name: app-v2-svc
      port: 5678

  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: app-v1-svc
      port: 5678
      weight: 80
    - name: app-v2-svc
      port: 5678
      weight: 20
EOF

# === STEP 5: Get Gateway address ===
GW_IP=$(kubectl get gateway demo-gateway -o jsonpath='{.status.addresses[0].value}')
echo "Gateway IP: $GW_IP"

# === STEP 6: Test routing ===
# Path routing
curl -H "Host: demo.example.com" http://$GW_IP/v1
# App Version 1

curl -H "Host: demo.example.com" http://$GW_IP/v2
# App Version 2

# Traffic split (run multiple times to see distribution)
for i in $(seq 1 10); do
  curl -s -H "Host: demo.example.com" http://$GW_IP/
done
# ~8 responses "App Version 1", ~2 responses "App Version 2"

# === STEP 7: Inspect route status ===
kubectl describe httproute demo-route
# Look at status.parents for acceptance condition

# === CLEANUP ===
kubectl delete httproute demo-route
kubectl delete gateway demo-gateway
kubectl delete deployment app-v1 app-v2
kubectl delete svc app-v1-svc app-v2-svc
```

---

## 11. Traffic Splitting Demo — Canary Release

```bash
# === Deploy stable v1 ===
cat <<EOF | kubectl apply -f -
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-stable
spec:
  replicas: 3
  selector:
    matchLabels:
      app: web
      version: stable
  template:
    metadata:
      labels:
        app: web
        version: stable
    spec:
      containers:
      - name: web
        image: nginx:1.21
        ports:
        - containerPort: 80
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: web-canary
spec:
  replicas: 1
  selector:
    matchLabels:
      app: web
      version: canary
  template:
    metadata:
      labels:
        app: web
        version: canary
    spec:
      containers:
      - name: web
        image: nginx:1.25       # new version
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: web-stable-svc
spec:
  selector:
    app: web
    version: stable
  ports:
  - port: 80
---
apiVersion: v1
kind: Service
metadata:
  name: web-canary-svc
spec:
  selector:
    app: web
    version: canary
  ports:
  - port: 80
EOF

# === Start with 95/5 split ===
cat <<EOF | kubectl apply -f -
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: canary-route
spec:
  parentRefs:
  - name: demo-gateway
  hostnames:
  - "app.example.com"
  rules:
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: web-stable-svc
      port: 80
      weight: 95
    - name: web-canary-svc
      port: 80
      weight: 5
EOF

# === Gradually increase canary to 50% ===
kubectl patch httproute canary-route \
  --type='json' \
  -p='[
    {"op":"replace","path":"/spec/rules/0/backendRefs/0/weight","value":50},
    {"op":"replace","path":"/spec/rules/0/backendRefs/1/weight","value":50}
  ]'

# === Full rollout: 100% to canary ===
kubectl patch httproute canary-route \
  --type='json' \
  -p='[
    {"op":"replace","path":"/spec/rules/0/backendRefs/0/weight","value":0},
    {"op":"replace","path":"/spec/rules/0/backendRefs/1/weight","value":100}
  ]'
```

---

## 12. Gateway API vs Ingress — Full Comparison

| Feature | Ingress | Gateway API |
|---------|---------|-------------|
| **Status** | Frozen (no new features) | Active development (GA v1.0+) |
| **Protocols** | HTTP, HTTPS only | HTTP, HTTPS, TCP, TLS, gRPC, UDP |
| **Traffic splitting** | Annotation (controller-specific) | Native in spec (`weight` field) |
| **Header matching** | Annotation (controller-specific) | Native in spec |
| **URL rewrite** | Annotation | Native filter |
| **Cross-namespace** | Not supported | Supported via ReferenceGrant |
| **Role separation** | Single object | GatewayClass / Gateway / Route |
| **Extensibility** | Annotations only | Custom filters + policies |
| **Portability** | Low (annotations differ per controller) | High (standard spec) |
| **Maturity** | Stable, widely supported | GA since Oct 2023 |

---

## 13. Common Interview Questions

**Q: What is Gateway API and how does it differ from Ingress?**
> Gateway API is the next-generation Kubernetes traffic management API, designed as a more expressive, extensible, and role-oriented replacement for Ingress. Unlike Ingress, Gateway API natively supports traffic splitting, header-based routing, cross-namespace routing, and multiple protocols (TCP, gRPC). It separates concerns across three resource types: GatewayClass (infra), Gateway (platform), and HTTPRoute (application).

---

**Q: What are GatewayClass, Gateway, and HTTPRoute?**
> **GatewayClass** is a cluster-scoped resource that identifies which controller implements Gateways of that class (similar to IngressClass). **Gateway** defines the actual entry point — ports, protocols, and TLS configuration. **HTTPRoute** defines how HTTP traffic matching certain host names or paths is routed to backend Services. Together they form a layered, role-oriented traffic management system.

---

**Q: What is a ReferenceGrant?**
> A **ReferenceGrant** is a Gateway API resource that allows objects in one namespace to reference objects in another. For example, an HTTPRoute in the `app` namespace can reference a Gateway in the `infra` namespace only if a ReferenceGrant exists in the `infra` namespace explicitly permitting this. It prevents unauthorized cross-namespace references.

---

**Q: Can Gateway API do traffic splitting natively?**
> Yes. HTTPRoute `backendRefs` supports a `weight` field. Traffic is distributed proportionally to weights — for example, `weight: 90` to stable and `weight: 10` to canary routes 10% of traffic to the new version. This is a first-class feature, unlike Ingress where you need controller-specific annotations.

---

**Q: Is Gateway API backwards compatible with Ingress?**
> Not directly — they are separate APIs with different resource types. However, most Gateway API controllers also support Ingress for backward compatibility. You can run both on the same cluster during migration. There is also a tool (`ingress2gateway`) to help convert Ingress resources to HTTPRoutes.

---

**Q: What is the difference between `mode: Terminate` and `mode: Passthrough` in Gateway TLS config?**
> **Terminate** means the Gateway decrypts TLS and sends plain HTTP to backends. **Passthrough** means the Gateway forwards the TLS connection unchanged to the backend, which handles TLS termination itself. Passthrough is used for end-to-end encryption where the backend needs to see the raw TLS.

---

## 14. Exam Practice Questions

**1.** What command installs the Gateway API standard CRDs?
```bash
kubectl apply -f https://github.com/kubernetes-sigs/gateway-api/releases/download/v1.2.1/standard-install.yaml
```

**2.** Write an HTTPRoute named `shop-route` that routes `shop.example.com/checkout` (Exact) to `checkout-svc:8080` and everything else to `frontend-svc:80`.
```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: shop-route
spec:
  parentRefs:
  - name: my-gateway
  hostnames:
  - "shop.example.com"
  rules:
  - matches:
    - path:
        type: Exact
        value: /checkout
    backendRefs:
    - name: checkout-svc
      port: 8080
  - matches:
    - path:
        type: PathPrefix
        value: /
    backendRefs:
    - name: frontend-svc
      port: 80
```

**3.** Write a traffic split sending 80% to `v1-svc` and 20% to `v2-svc`.
```yaml
rules:
- matches:
  - path:
      type: PathPrefix
      value: /
  backendRefs:
  - name: v1-svc
    port: 80
    weight: 80
  - name: v2-svc
    port: 80
    weight: 20
```

**4.** What resource must exist to allow an HTTPRoute in namespace `team-a` to reference a Gateway in namespace `infra`?
> A **ReferenceGrant** in the `infra` namespace that permits `HTTPRoute` resources from namespace `team-a` to reference the Gateway.

**5.** Name two advantages of Gateway API over Ingress.
> (1) Native traffic splitting via `weight` field — no annotations needed. (2) Role-oriented design with separate GatewayClass/Gateway/HTTPRoute resources allowing different teams to manage different layers. Other valid answers: multi-protocol support, cross-namespace routing, header-based routing in spec.

---

> **CKA Exam Tips**:
> - Gateway API CRDs must be installed separately before any controller
> - Three key resources in order: GatewayClass → Gateway → HTTPRoute
> - `parentRefs` in HTTPRoute links it to a Gateway (not selector — explicit reference)
> - `weight` in backendRefs enables traffic splitting natively
> - ReferenceGrant = the security mechanism for cross-namespace references
> - Check Gateway status: `kubectl get gateway` — look for PROGRAMMED=True

---

*Notes by ITkannadigaru | CKA 2026 Certification*

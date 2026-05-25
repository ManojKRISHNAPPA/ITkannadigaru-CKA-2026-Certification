# Kubernetes ConfigMap & Secrets — Complete Guide

> ConfigMaps store non-sensitive configuration. Secrets store sensitive data. Together, they let you externalise all config from your container image — the Kubernetes way to implement 12-factor app principles.

---

## Table of Contents

1. [The Problem They Solve](#1-the-problem-they-solve)
2. [ConfigMap — What It Is](#2-configmap--what-it-is)
3. [Creating ConfigMaps](#3-creating-configmaps)
   - [3.1 Imperative (CLI)](#31-imperative-cli)
   - [3.2 Declarative (YAML)](#32-declarative-yaml)
4. [Injecting ConfigMap into Pods](#4-injecting-configmap-into-pods)
   - [4.1 As Environment Variables (envFrom)](#41-as-environment-variables-envfrom)
   - [4.2 As Single Env Var (valueFrom)](#42-as-single-env-var-valuefrom)
   - [4.3 As Volume (Config Files)](#43-as-volume-config-files)
5. [Secrets — What They Are](#5-secrets--what-they-are)
6. [Secret Types](#6-secret-types)
7. [Creating Secrets](#7-creating-secrets)
   - [7.1 Imperative (CLI)](#71-imperative-cli)
   - [7.2 Declarative (YAML)](#72-declarative-yaml)
8. [Injecting Secrets into Pods](#8-injecting-secrets-into-pods)
   - [8.1 As Environment Variables](#81-as-environment-variables)
   - [8.2 As Volume (Files)](#82-as-volume-files)
9. [ConfigMap vs Secret — When to Use What](#9-configmap-vs-secret--when-to-use-what)
10. [Production Demo — E-Commerce Microservice](#10-production-demo--e-commerce-microservice)
    - [10.1 The Production Scenario](#101-the-production-scenario)
    - [10.2 Endpoints & Dummy Credentials](#102-endpoints--dummy-credentials)
    - [10.3 ConfigMap — App Config](#103-configmap--app-config)
    - [10.4 Secret — Sensitive Credentials](#104-secret--sensitive-credentials)
    - [10.5 Pod — Inject Both CM and Secret](#105-pod--inject-both-cm-and-secret)
    - [10.6 Deployment — Full Production Setup](#106-deployment--full-production-setup)
    - [10.7 Verify Inside the Pod](#107-verify-inside-the-pod)
11. [ConfigMap as Mounted Config File](#11-configmap-as-mounted-config-file)
12. [Updating ConfigMaps and Secrets](#12-updating-configmaps-and-secrets)
13. [Security Best Practices for Secrets](#13-security-best-practices-for-secrets)
14. [Common Interview Questions](#14-common-interview-questions)
15. [Exam Practice Questions](#15-exam-practice-questions)

---

## 1. The Problem They Solve

### Without ConfigMap / Secret (the bad way)

```
  Dockerfile:
  ENV DB_HOST=prod-db.internal
  ENV DB_PASSWORD=SuperSecret123

  Problem 1: Same image can't work in dev, staging, and prod
  Problem 2: Secrets baked into image → leaked in Docker Hub, logs, git history
  Problem 3: Changing a config requires rebuilding and redeploying the entire image
```

### With ConfigMap + Secret (the Kubernetes way)

```
  Image: generic (no env-specific values baked in)
     │
     ├─── ConfigMap ────────────────────► Pod as ENV / File
     │    (non-sensitive: host, port,
     │     URLs, feature flags)
     │
     └─── Secret ──────────────────────► Pod as ENV / File
          (sensitive: passwords, tokens,
           keys, certs, DB strings)

  Result:
  ✓ Same image runs in dev / staging / prod — different CM/Secrets per env
  ✓ Secrets never in Dockerfile or Git
  ✓ Change config without rebuilding image
  ✓ RBAC controls who can read Secrets
```

---

## 2. ConfigMap — What It Is

A **ConfigMap** is a Kubernetes object that stores **non-sensitive** key-value pairs (or entire config files). Think of it as a dictionary your Pod can read at runtime.

```
  ConfigMap: app-config
  ┌─────────────────────────────────────────┐
  │  APP_ENV         = production           │
  │  DB_HOST         = postgres.internal    │
  │  DB_PORT         = 5432                 │
  │  REDIS_HOST      = redis.internal       │
  │  API_BASE_URL    = https://api.internal │
  │  LOG_LEVEL       = INFO                 │
  │  MAX_CONNECTIONS = 100                  │
  └─────────────────────────────────────────┘

  Pods can read this as:
  ├── Environment variables  (export DB_HOST=postgres.internal)
  └── Mounted files          (/etc/config/app.properties)
```

**Key limits:**
- Max size: **1 MiB** per ConfigMap
- ConfigMaps are **namespace-scoped** — a Pod can only use ConfigMaps in the same namespace
- Values are stored as **plaintext** — never put secrets here

---

## 3. Creating ConfigMaps

### 3.1 Imperative (CLI)

```bash
# From literal key=value pairs
kubectl create configmap app-config \
  --from-literal=APP_ENV=production \
  --from-literal=DB_HOST=postgres.internal.svc.cluster.local \
  --from-literal=DB_PORT=5432 \
  --from-literal=REDIS_HOST=redis.internal.svc.cluster.local \
  --from-literal=LOG_LEVEL=INFO

# From a file (key = filename, value = file content)
kubectl create configmap nginx-config --from-file=nginx.conf

# From a file with a custom key name
kubectl create configmap app-props --from-file=application.properties=./config/app.properties

# From an entire directory (each file becomes a key)
kubectl create configmap all-configs --from-file=./configs/

# Inspect the created ConfigMap
kubectl get configmap app-config -o yaml
kubectl describe configmap app-config
```

### 3.2 Declarative (YAML)

```yaml
# configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: production
data:
  # Single-line values
  APP_ENV: "production"
  DB_HOST: "postgres.internal.svc.cluster.local"
  DB_PORT: "5432"
  DB_NAME: "ecomm_production"
  REDIS_HOST: "redis.internal.svc.cluster.local"
  REDIS_PORT: "6379"
  LOG_LEVEL: "INFO"
  MAX_CONNECTIONS: "100"
  CACHE_TTL_SECONDS: "3600"
  FEATURE_FLAG_NEW_CHECKOUT: "true"

  # Multi-line value (a config file stored as a CM key)
  app.properties: |
    server.port=8080
    spring.datasource.url=jdbc:postgresql://postgres.internal:5432/ecomm
    spring.redis.host=redis.internal
    spring.redis.port=6379
    logging.level.root=INFO
```

```bash
kubectl apply -f configmap.yaml

# Quick check
kubectl get cm app-config
kubectl get cm app-config -o jsonpath='{.data.DB_HOST}'
```

---

## 4. Injecting ConfigMap into Pods

### 4.1 As Environment Variables (envFrom)

Injects **all keys** from the ConfigMap as environment variables in one shot.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-pod
spec:
  containers:
  - name: app
    image: my-ecomm-app:1.0
    envFrom:
    - configMapRef:
        name: app-config     # ← inject ALL keys from this CM as env vars
```

```bash
# Inside the pod, every key is now an env var:
kubectl exec app-pod -- env | grep -E "DB_HOST|DB_PORT|APP_ENV|LOG_LEVEL"
# DB_HOST=postgres.internal.svc.cluster.local
# DB_PORT=5432
# APP_ENV=production
# LOG_LEVEL=INFO
```

### 4.2 As Single Env Var (valueFrom)

Inject **specific keys** with the ability to rename them.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-pod
spec:
  containers:
  - name: app
    image: my-ecomm-app:1.0
    env:
    - name: DATABASE_HOST          # name in the Pod (can differ from CM key)
      valueFrom:
        configMapKeyRef:
          name: app-config         # which ConfigMap
          key: DB_HOST             # which key inside that CM

    - name: DATABASE_PORT
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: DB_PORT

    - name: ENVIRONMENT
      valueFrom:
        configMapKeyRef:
          name: app-config
          key: APP_ENV
```

### 4.3 As Volume (Config Files)

Mount ConfigMap as files inside the container. Each key becomes a file.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-pod
spec:
  volumes:
  - name: config-volume
    configMap:
      name: app-config              # CM to mount
      items:                        # optional: pick specific keys
      - key: app.properties
        path: application.properties  # file name in the container

  containers:
  - name: app
    image: my-ecomm-app:1.0
    volumeMounts:
    - name: config-volume
      mountPath: /etc/app/config    # directory in the container
      readOnly: true
```

```bash
# Inside the pod:
kubectl exec app-pod -- ls /etc/app/config/
# application.properties

kubectl exec app-pod -- cat /etc/app/config/application.properties
# server.port=8080
# spring.datasource.url=jdbc:postgresql://postgres.internal:5432/ecomm
# ...
```

---

## 5. Secrets — What They Are

A **Secret** is a Kubernetes object for **sensitive** data — passwords, tokens, TLS certificates, database connection strings, API keys.

```
  ConfigMap (plaintext):                Secret (base64-encoded):
  ┌────────────────────┐               ┌───────────────────────────────────┐
  │ DB_HOST: postgres  │               │ DB_PASSWORD: UzNjdXIzUEBzc3cwcmQh│
  │ DB_PORT: 5432      │               │ JWT_SECRET:  and0LXN1cGVyLXNlY3Jl│
  │ LOG_LEVEL: INFO    │               │ STRIPE_KEY:  c2tfbGl2ZV9lY29tbQ==  │
  └────────────────────┘               └───────────────────────────────────┘
  Stored as plaintext in etcd          Base64 encoded in etcd
  (not encrypted by default)           (use etcd encryption at rest for real security)
```

> **Important:** Base64 is NOT encryption — it is encoding. Anyone with access to the Secret object can decode it. Real security comes from:
> - **RBAC** restricting who can `get` Secrets
> - **etcd encryption at rest** (EncryptionConfiguration)
> - **External secret managers** (Vault, AWS Secrets Manager, GCP Secret Manager)

---

## 6. Secret Types

| Type | `type` field | Use Case |
|------|-------------|---------|
| **Generic** (default) | `Opaque` | Arbitrary key-value pairs (passwords, tokens) |
| **TLS** | `kubernetes.io/tls` | TLS certificates and keys for Ingress |
| **Docker Registry** | `kubernetes.io/dockerconfigjson` | Pull images from private registry |
| **Basic Auth** | `kubernetes.io/basic-auth` | Username + password |
| **SSH Auth** | `kubernetes.io/ssh-auth` | SSH private key |
| **Service Account Token** | `kubernetes.io/service-account-token` | SA tokens (pre-1.24) |

```bash
# Check types of existing secrets
kubectl get secrets -A
kubectl get secret <name> -o yaml | grep type
```

---

## 7. Creating Secrets

### 7.1 Imperative (CLI)

```bash
# Generic secret from literal values
kubectl create secret generic db-credentials \
  --from-literal=DB_PASSWORD='S3cur3P@ssw0rd!2026' \
  --from-literal=DB_CONNECTION_STRING='postgresql://ecomm_user:S3cur3P@ssw0rd!2026@postgres.internal.svc.cluster.local:5432/ecomm_production'

# Generic secret from a file (e.g., a private key)
kubectl create secret generic ssh-key \
  --from-file=id_rsa=~/.ssh/id_rsa

# TLS secret (for Ingress)
kubectl create secret tls my-tls-secret \
  --cert=tls.crt \
  --key=tls.key

# Docker registry secret (to pull from private registry)
kubectl create secret docker-registry registry-creds \
  --docker-server=myregistry.example.com \
  --docker-username=myuser \
  --docker-password=mypassword

# Inspect
kubectl get secret db-credentials -o yaml
# Values are base64-encoded — not human-readable
```

### 7.2 Declarative (YAML)

> **Important:** In YAML Secrets, values under `data:` must be **base64-encoded**. Use `stringData:` to write plaintext and let Kubernetes encode it.

```bash
# Encode a value manually
echo -n 'S3cur3P@ssw0rd!2026' | base64
# UzNjdXIzUEBzc3cwcmQhMjAyNg==

# Decode to verify
echo 'UzNjdXIzUEBzc3cwcmQhMjAyNg==' | base64 -d
# S3cur3P@ssw0rd!2026
```

```yaml
# secret-data.yaml (using base64 under data:)
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: production
type: Opaque
data:
  DB_PASSWORD: UzNjdXIzUEBzc3cwcmQhMjAyNg==         # base64 of: S3cur3P@ssw0rd!2026
  REDIS_PASSWORD: UjNkIXNQQHNzIzIwMjY=              # base64 of: R3d!sP@ss#2026
  JWT_SECRET: and0LXN1cGVyLXNlY3JldC1rZXktZWNvbW0tMjAyNg==  # base64 of: jwt-super-secret-key-ecomm-2026
```

```yaml
# secret-stringdata.yaml (easier — Kubernetes encodes for you)
apiVersion: v1
kind: Secret
metadata:
  name: db-credentials
  namespace: production
type: Opaque
stringData:
  DB_PASSWORD: "S3cur3P@ssw0rd!2026"
  DB_CONNECTION_STRING: "postgresql://ecomm_user:S3cur3P@ssw0rd!2026@postgres.internal.svc.cluster.local:5432/ecomm_production"
  REDIS_PASSWORD: "R3d!sP@ss#2026"
  JWT_SECRET: "jwt-super-secret-key-ecomm-2026"
  STRIPE_API_KEY: "sk_live_ecomm_stripe_key_2026"
```

```bash
kubectl apply -f secret-stringdata.yaml

# Get the secret
kubectl get secret db-credentials -o yaml

# Decode a specific key
kubectl get secret db-credentials \
  -o jsonpath='{.data.DB_PASSWORD}' | base64 -d
```

---

## 8. Injecting Secrets into Pods

Injection syntax is **identical** to ConfigMaps — just replace `configMapRef`/`configMapKeyRef` with `secretRef`/`secretKeyRef`.

### 8.1 As Environment Variables

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-pod
spec:
  containers:
  - name: app
    image: my-ecomm-app:1.0
    # Inject ALL keys from the Secret as env vars
    envFrom:
    - secretRef:
        name: db-credentials

    # OR inject specific keys with custom names
    env:
    - name: DATABASE_PASSWORD
      valueFrom:
        secretKeyRef:
          name: db-credentials
          key: DB_PASSWORD

    - name: PAYMENT_API_KEY
      valueFrom:
        secretKeyRef:
          name: db-credentials
          key: STRIPE_API_KEY
          optional: false          # Pod will fail to start if this key is missing
```

### 8.2 As Volume (Files)

Kubernetes decodes base64 automatically — files contain the original plaintext values.

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-pod
spec:
  volumes:
  - name: secret-volume
    secret:
      secretName: db-credentials
      defaultMode: 0400            # read-only for owner (secure file permission)

  containers:
  - name: app
    image: my-ecomm-app:1.0
    volumeMounts:
    - name: secret-volume
      mountPath: /etc/secrets
      readOnly: true
```

```bash
# Inside the pod — files are auto-created, values are decoded:
kubectl exec app-pod -- ls /etc/secrets
# DB_PASSWORD
# DB_CONNECTION_STRING
# JWT_SECRET

kubectl exec app-pod -- cat /etc/secrets/DB_PASSWORD
# S3cur3P@ssw0rd!2026    ← decoded automatically
```

> **Volume mount vs Env var for secrets:**
> - **Volume mount** is more secure — env vars can be leaked in logs, crash dumps, child processes
> - Mounted secret files are **updated automatically** when the Secret changes (env vars are NOT)
> - Prefer volume mounts for TLS certs and sensitive files; env vars are acceptable for short-lived credentials

---

## 9. ConfigMap vs Secret — When to Use What

```
  Ask: "Would I be embarrassed if this value was logged or visible in git?"

  YES → Use Secret        NO → Use ConfigMap
```

| Configuration Item | Use |
|-------------------|-----|
| Database hostname / port | ConfigMap |
| Database password | **Secret** |
| Database connection string (contains password) | **Secret** |
| Redis hostname | ConfigMap |
| Redis password | **Secret** |
| API endpoint URLs | ConfigMap |
| API keys / tokens | **Secret** |
| JWT signing secret | **Secret** |
| Feature flags | ConfigMap |
| Log level | ConfigMap |
| TLS certificates | **Secret** (type: tls) |
| Private registry credentials | **Secret** (type: dockerconfigjson) |
| Nginx config file | ConfigMap |
| Environment name (dev/prod) | ConfigMap |

```
  Visual:

  ConfigMap                              Secret
  ────────────────────────────           ──────────────────────────────
  APP_ENV=production                     DB_PASSWORD=S3cur3P@ssw0rd!
  DB_HOST=postgres.internal              REDIS_PASSWORD=R3d!sP@ss
  DB_PORT=5432                           JWT_SECRET=jwt-super-secret
  DB_NAME=ecomm_production               STRIPE_KEY=sk_live_xxxxx
  REDIS_HOST=redis.internal              TLS_CERT=-----BEGIN CERT-----
  API_BASE_URL=https://api.internal      TLS_KEY=-----BEGIN RSA KEY---
  LOG_LEVEL=INFO
  MAX_CONNECTIONS=100
  FEATURE_FLAG_CHECKOUT=true
```

---

## 10. Production Demo — E-Commerce Microservice

### 10.1 The Production Scenario

```
  Production environment: e-commerce platform
  Service: order-service (Node.js / Python app)
  Namespace: ecomm-prod

  Architecture:
  ┌────────────────────────────────────────────────────────────────┐
  │                       ecomm-prod namespace                     │
  │                                                                │
  │   order-service Pod                                            │
  │   ┌────────────────────────────────────────────────────┐      │
  │   │  Container: order-service                          │      │
  │   │                                                    │      │
  │   │  ENV from ConfigMap (app-config):                  │      │
  │   │  ├── DB_HOST, DB_PORT, DB_NAME                     │      │
  │   │  ├── REDIS_HOST, REDIS_PORT                        │      │
  │   │  ├── API_BASE_URL, AUTH_SERVICE_URL                │      │
  │   │  └── LOG_LEVEL, MAX_CONNECTIONS                    │      │
  │   │                                                    │      │
  │   │  ENV from Secret (app-secrets):                    │      │
  │   │  ├── DB_PASSWORD                                   │      │
  │   │  ├── DB_CONNECTION_STRING                          │      │
  │   │  ├── REDIS_PASSWORD                                │      │
  │   │  ├── JWT_SECRET                                    │      │
  │   │  └── STRIPE_API_KEY                               │      │
  │   └────────────────────────────────────────────────────┘      │
  │                                                                │
  │   Connects to:                                                 │
  │   postgres.ecomm-prod.svc.cluster.local:5432                   │
  │   redis.ecomm-prod.svc.cluster.local:6379                      │
  └────────────────────────────────────────────────────────────────┘
```

### 10.2 Endpoints & Dummy Credentials

```
  ─────────────────────────────────────────────────────────
  NON-SENSITIVE CONFIG  (goes in ConfigMap)
  ─────────────────────────────────────────────────────────
  DB_HOST            = postgres.ecomm-prod.svc.cluster.local
  DB_PORT            = 5432
  DB_NAME            = ecomm_production
  REDIS_HOST         = redis.ecomm-prod.svc.cluster.local
  REDIS_PORT         = 6379
  API_BASE_URL       = https://api.ecomm.internal/v2
  AUTH_SERVICE_URL   = https://auth.ecomm.internal/v1
  PAYMENT_GW_URL     = https://payments.ecomm.internal/v3
  INVENTORY_SVC_URL  = https://inventory.ecomm.internal/v1
  NOTIFICATION_URL   = https://notify.ecomm.internal/v1
  APP_ENV            = production
  LOG_LEVEL          = INFO
  MAX_DB_CONNECTIONS = 20
  CACHE_TTL_SECONDS  = 3600
  REQUEST_TIMEOUT_MS = 5000
  FEATURE_NEW_CART   = true

  ─────────────────────────────────────────────────────────
  SENSITIVE DATA  (goes in Secret)
  ─────────────────────────────────────────────────────────
  DB_USER              = ecomm_user
  DB_PASSWORD          = S3cur3P@ssw0rd!2026
  DB_CONNECTION_STRING = postgresql://ecomm_user:S3cur3P@ssw0rd!2026@postgres.ecomm-prod.svc.cluster.local:5432/ecomm_production
  REDIS_PASSWORD       = R3d!sP@ss#2026
  JWT_SECRET           = jwt-super-secret-key-ecomm-2026
  STRIPE_API_KEY       = sk_live_ecomm_stripe_key_2026xxxxxxxxxxx
  SENDGRID_API_KEY     = SG.ecomm_sendgrid_key_prod_2026
  INTERNAL_API_TOKEN   = Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9
  ─────────────────────────────────────────────────────────
```

### 10.3 ConfigMap — App Config

```yaml
# app-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config
  namespace: ecomm-prod
  labels:
    app: order-service
    env: production
data:
  # Database (non-sensitive parts)
  DB_HOST: "postgres.ecomm-prod.svc.cluster.local"
  DB_PORT: "5432"
  DB_NAME: "ecomm_production"

  # Redis Cache
  REDIS_HOST: "redis.ecomm-prod.svc.cluster.local"
  REDIS_PORT: "6379"

  # Internal Service Endpoints
  API_BASE_URL: "https://api.ecomm.internal/v2"
  AUTH_SERVICE_URL: "https://auth.ecomm.internal/v1"
  PAYMENT_GW_URL: "https://payments.ecomm.internal/v3"
  INVENTORY_SVC_URL: "https://inventory.ecomm.internal/v1"
  NOTIFICATION_URL: "https://notify.ecomm.internal/v1"

  # App Behaviour
  APP_ENV: "production"
  LOG_LEVEL: "INFO"
  MAX_DB_CONNECTIONS: "20"
  CACHE_TTL_SECONDS: "3600"
  REQUEST_TIMEOUT_MS: "5000"
  FEATURE_NEW_CART: "true"
```

```bash
kubectl apply -f app-configmap.yaml
kubectl get cm app-config -n ecomm-prod
kubectl describe cm app-config -n ecomm-prod
```

### 10.4 Secret — Sensitive Credentials

```yaml
# app-secret.yaml
apiVersion: v1
kind: Secret
metadata:
  name: app-secrets
  namespace: ecomm-prod
  labels:
    app: order-service
    env: production
type: Opaque
stringData:
  DB_USER: "ecomm_user"
  DB_PASSWORD: "S3cur3P@ssw0rd!2026"
  DB_CONNECTION_STRING: "postgresql://ecomm_user:S3cur3P@ssw0rd!2026@postgres.ecomm-prod.svc.cluster.local:5432/ecomm_production"
  REDIS_PASSWORD: "R3d!sP@ss#2026"
  JWT_SECRET: "jwt-super-secret-key-ecomm-2026"
  STRIPE_API_KEY: "sk_live_ecomm_stripe_key_2026xxxxxxxxxxx"
  SENDGRID_API_KEY: "SG.ecomm_sendgrid_key_prod_2026"
  INTERNAL_API_TOKEN: "Bearer eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9"
```

```bash
kubectl apply -f app-secret.yaml
kubectl get secret app-secrets -n ecomm-prod
# NAME          TYPE     DATA   AGE
# app-secrets   Opaque   8      5s

# Peek at a decoded value
kubectl get secret app-secrets -n ecomm-prod \
  -o jsonpath='{.data.DB_PASSWORD}' | base64 -d
# S3cur3P@ssw0rd!2026
```

### 10.5 Pod — Inject Both CM and Secret

```yaml
# order-service-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: order-service
  namespace: ecomm-prod
  labels:
    app: order-service
spec:
  containers:
  - name: order-service
    image: my-ecomm/order-service:2.1.0
    ports:
    - containerPort: 8080

    # ── Step 1: Inject ALL ConfigMap keys as env vars ──
    envFrom:
    - configMapRef:
        name: app-config

    # ── Step 2: Inject ALL Secret keys as env vars ──
    envFrom:
    - secretRef:
        name: app-secrets

    # ── Step 3: Override or add specific env vars ──
    env:
    - name: PORT
      value: "8080"
    # Explicitly set DB_CONNECTION_STRING from Secret (named differently)
    - name: DATABASE_URL
      valueFrom:
        secretKeyRef:
          name: app-secrets
          key: DB_CONNECTION_STRING

    resources:
      requests:
        cpu: 100m
        memory: 128Mi
      limits:
        cpu: 500m
        memory: 512Mi
```

> **Note:** When using multiple `envFrom` blocks, define them as a list under the same `envFrom:` key.

```yaml
# Correct way to inject both CM and Secret together:
envFrom:
- configMapRef:
    name: app-config
- secretRef:
    name: app-secrets
```

### 10.6 Deployment — Full Production Setup

```yaml
# order-service-deployment.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
  namespace: ecomm-prod
  labels:
    app: order-service
    version: "2.1.0"
spec:
  replicas: 3
  selector:
    matchLabels:
      app: order-service
  template:
    metadata:
      labels:
        app: order-service
        version: "2.1.0"
    spec:
      containers:
      - name: order-service
        image: my-ecomm/order-service:2.1.0
        ports:
        - containerPort: 8080

        # ── Inject ConfigMap (non-sensitive config) ──
        # ── Inject Secret (sensitive credentials) ──
        envFrom:
        - configMapRef:
            name: app-config       # DB_HOST, REDIS_HOST, API URLs, LOG_LEVEL...
        - secretRef:
            name: app-secrets      # DB_PASSWORD, JWT_SECRET, STRIPE_KEY...

        # ── Also mount TLS cert as a volume ──
        volumeMounts:
        - name: tls-certs
          mountPath: /etc/tls
          readOnly: true

        # ── Readiness check ──
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
          initialDelaySeconds: 10
          periodSeconds: 5

        # ── Liveness check ──
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 30
          periodSeconds: 10

        resources:
          requests:
            cpu: 200m
            memory: 256Mi
          limits:
            cpu: 1000m
            memory: 512Mi

      volumes:
      - name: tls-certs
        secret:
          secretName: app-tls-cert   # TLS secret (kubectl create secret tls ...)
          defaultMode: 0400          # owner read-only

---
apiVersion: v1
kind: Service
metadata:
  name: order-service
  namespace: ecomm-prod
spec:
  selector:
    app: order-service
  ports:
  - port: 80
    targetPort: 8080
  type: ClusterIP
```

```bash
# Deploy everything in order
kubectl apply -f app-configmap.yaml
kubectl apply -f app-secret.yaml
kubectl apply -f order-service-deployment.yaml

# Verify
kubectl get all -n ecomm-prod
kubectl rollout status deployment/order-service -n ecomm-prod
```

### 10.7 Verify Inside the Pod

```bash
# Pick one running pod
POD=$(kubectl get pods -n ecomm-prod -l app=order-service -o name | head -1)

# Confirm ConfigMap env vars are injected
kubectl exec $POD -n ecomm-prod -- env | grep -E "DB_HOST|REDIS_HOST|API_BASE_URL|LOG_LEVEL"
# DB_HOST=postgres.ecomm-prod.svc.cluster.local
# REDIS_HOST=redis.ecomm-prod.svc.cluster.local
# API_BASE_URL=https://api.ecomm.internal/v2
# LOG_LEVEL=INFO

# Confirm Secret env vars are injected (decoded automatically)
kubectl exec $POD -n ecomm-prod -- env | grep -E "DB_PASSWORD|JWT_SECRET|STRIPE"
# DB_PASSWORD=S3cur3P@ssw0rd!2026
# JWT_SECRET=jwt-super-secret-key-ecomm-2026
# STRIPE_API_KEY=sk_live_ecomm_stripe_key_2026xxxxxxxxxxx

# Confirm DB_CONNECTION_STRING
kubectl exec $POD -n ecomm-prod -- env | grep DATABASE_URL
# DATABASE_URL=postgresql://ecomm_user:S3cur3P@ssw0rd!2026@postgres.ecomm-prod.svc.cluster.local:5432/ecomm_production
```

```
  What just happened in production:

  ┌─────────────────────────────────────────────────────────┐
  │  ConfigMap (app-config)          Secret (app-secrets)   │
  │  ┌──────────────────────┐        ┌───────────────────┐  │
  │  │ DB_HOST              │        │ DB_PASSWORD ●●●●● │  │
  │  │ DB_PORT              │        │ DB_CONN_STR ●●●●● │  │
  │  │ REDIS_HOST           │        │ JWT_SECRET  ●●●●● │  │
  │  │ API_BASE_URL         │        │ STRIPE_KEY  ●●●●● │  │
  │  │ LOG_LEVEL            │        └─────────┬─────────┘  │
  │  └─────────┬────────────┘                  │            │
  │            │                               │            │
  │            └──────────────┬────────────────┘            │
  │                           ▼                             │
  │              order-service Pod (3 replicas)             │
  │              All env vars injected at startup           │
  │              App reads: os.environ['DB_HOST']           │
  │                          os.environ['DB_PASSWORD']      │
  │                          os.environ['JWT_SECRET']       │
  └─────────────────────────────────────────────────────────┘
```

---

## 11. ConfigMap as Mounted Config File

Real apps (Nginx, Prometheus, Spring Boot) need full config files, not just env vars. Mount the CM as a file.

```yaml
# nginx-configmap.yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: nginx-config
  namespace: ecomm-prod
data:
  nginx.conf: |
    server {
        listen 80;
        server_name api.ecomm.internal;

        location /health {
            return 200 'ok';
            add_header Content-Type text/plain;
        }

        location / {
            proxy_pass http://order-service.ecomm-prod.svc.cluster.local:80;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
        }
    }
```

```yaml
# nginx-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx-proxy
  namespace: ecomm-prod
spec:
  volumes:
  - name: nginx-config-vol
    configMap:
      name: nginx-config

  containers:
  - name: nginx
    image: nginx:1.25
    volumeMounts:
    - name: nginx-config-vol
      mountPath: /etc/nginx/conf.d   # nginx reads *.conf files from this dir
      readOnly: true
```

```bash
# Verify file is mounted
kubectl exec nginx-proxy -n ecomm-prod -- cat /etc/nginx/conf.d/nginx.conf
```

---

## 12. Updating ConfigMaps and Secrets

```bash
# Edit ConfigMap directly
kubectl edit configmap app-config -n ecomm-prod

# Patch a single key
kubectl patch configmap app-config -n ecomm-prod \
  --type merge -p '{"data":{"LOG_LEVEL":"DEBUG"}}'

# Apply updated YAML
kubectl apply -f app-configmap.yaml

# Update a Secret (patch)
kubectl patch secret app-secrets -n ecomm-prod \
  --type merge -p '{"stringData":{"DB_PASSWORD":"NewP@ss2026!"}}'
```

### What happens after update?

```
  Update method      │ Env vars updated?  │ Volume files updated?
  ───────────────────┼────────────────────┼─────────────────────
  envFrom/env        │ NO                 │ N/A
  (env vars)         │ Pod restart needed │
  ───────────────────┼────────────────────┼─────────────────────
  volumeMount        │ N/A                │ YES (automatically)
  (files)            │                   │ within ~1-2 minutes
```

```bash
# To propagate env var changes:
kubectl rollout restart deployment/order-service -n ecomm-prod
```

---

## 13. Security Best Practices for Secrets

```
  DO                                  DON'T
  ─────────────────────────────────   ───────────────────────────────────
  ✓ Use RBAC to restrict Secret get  ✗ kubectl get secret -o yaml in logs
  ✓ Enable etcd encryption at rest   ✗ Store secrets in ConfigMaps
  ✓ Use external secret managers     ✗ Commit Secrets YAML to git
    (Vault, AWS SM, GCP SM)          ✗ Print env vars in app logs
  ✓ Rotate secrets regularly         ✗ Use default namespace for prod
  ✓ Mount as volume, not env var     ✗ Give all pods access to all secrets
  ✓ Set defaultMode: 0400 on files   ✗ Use long-lived tokens when short ones work
  ✓ Separate secrets per service
  ✓ Use namespaces to isolate envs
```

```bash
# Restrict who can read a Secret (example RBAC)
kubectl create role secret-reader \
  --verb=get,list \
  --resource=secrets \
  --resource-name=app-secrets \
  -n ecomm-prod

kubectl create rolebinding order-service-secrets \
  --role=secret-reader \
  --serviceaccount=ecomm-prod:order-service-sa \
  -n ecomm-prod
```

---

## 14. Common Interview Questions

**Q: What is the difference between a ConfigMap and a Secret?**
> A ConfigMap stores non-sensitive configuration data as plaintext key-value pairs. A Secret stores sensitive data (passwords, tokens, certificates) as base64-encoded values with tighter access control via RBAC. Both can be injected into Pods as environment variables or mounted as files. The critical difference is semantics, access control, and the encryption boundary — Secrets can be encrypted at rest in etcd using EncryptionConfiguration; ConfigMaps cannot.

---

**Q: Is base64 in Secrets secure?**
> No. Base64 is encoding, not encryption — anyone with `kubectl get secret` access can decode it instantly with `base64 -d`. Real security comes from: (1) RBAC restricting who can read the Secret object, (2) enabling etcd encryption at rest, (3) using external secret managers like HashiCorp Vault or AWS Secrets Manager that never store plaintext in etcd.

---

**Q: How do you inject environment variables from a ConfigMap into a Pod?**
> Two ways: (1) `envFrom: configMapRef: name: my-cm` — injects all keys at once; (2) `env: valueFrom: configMapKeyRef: name: my-cm, key: MY_KEY` — injects a specific key, optionally renamed. Volume mounting is a third option that makes each key a file inside the container.

---

**Q: What happens to a Pod's env vars when you update a ConfigMap?**
> Environment variables injected via `envFrom` or `env` are NOT updated automatically when the ConfigMap changes — they are set at Pod startup and fixed for the Pod's lifetime. You must restart the Pod (e.g., `kubectl rollout restart deployment`) to pick up changes. However, ConfigMap data mounted as a **volume** IS updated automatically (within ~1-2 minutes via kubelet sync), without a Pod restart.

---

**Q: Where is ConfigMap/Secret data stored?**
> Both are stored in **etcd**, the Kubernetes backing store. ConfigMaps are stored as plaintext. Secrets are stored as base64 by default, but can be encrypted using EncryptionConfiguration with providers like AES-CBC, AES-GCM, or KMS.

---

**Q: Can a ConfigMap be used across namespaces?**
> No. ConfigMaps and Secrets are namespace-scoped. A Pod in `namespace-A` cannot reference a ConfigMap in `namespace-B`. You must duplicate the ConfigMap in each namespace, or use a tool like Reflector, External Secrets Operator, or Vault to sync across namespaces.

---

**Q: What is the `stringData` field in a Secret YAML?**
> `stringData` is a write-only field that accepts plaintext values — Kubernetes automatically encodes them to base64 before storing in etcd. It is the developer-friendly alternative to manually encoding values under `data:`. When you `kubectl get secret -o yaml`, you see the base64 values under `data:`, not `stringData:`.

---

## 15. Exam Practice Questions

**1.** Create a ConfigMap named `web-config` in namespace `prod` with:
- `APP_PORT=3000`
- `CACHE_ENABLED=true`
- `LOG_LEVEL=WARN`

```bash
kubectl create configmap web-config -n prod \
  --from-literal=APP_PORT=3000 \
  --from-literal=CACHE_ENABLED=true \
  --from-literal=LOG_LEVEL=WARN
```

---

**2.** Create a Secret named `web-secrets` in namespace `prod` with `DB_PASS=MySecretPass`:

```bash
kubectl create secret generic web-secrets -n prod \
  --from-literal=DB_PASS=MySecretPass
```

---

**3.** Write a Pod spec that injects `web-config` ConfigMap AND `web-secrets` Secret as environment variables:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: web-pod
  namespace: prod
spec:
  containers:
  - name: web
    image: nginx
    envFrom:
    - configMapRef:
        name: web-config
    - secretRef:
        name: web-secrets
```

---

**4.** Read only `LOG_LEVEL` from `web-config` and expose it as `LOG` in the container:

```yaml
env:
- name: LOG
  valueFrom:
    configMapKeyRef:
      name: web-config
      key: LOG_LEVEL
```

---

**5.** Mount the Secret `web-secrets` at `/run/secrets` in a Pod:

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: secret-mount-pod
  namespace: prod
spec:
  volumes:
  - name: sec-vol
    secret:
      secretName: web-secrets
      defaultMode: 0400
  containers:
  - name: app
    image: busybox
    command: ["sleep", "3600"]
    volumeMounts:
    - name: sec-vol
      mountPath: /run/secrets
      readOnly: true
```

---

**6.** Decode the `DB_PASS` from secret `web-secrets`:

```bash
kubectl get secret web-secrets -n prod \
  -o jsonpath='{.data.DB_PASS}' | base64 -d
```

---

**7.** Update `LOG_LEVEL` in `web-config` to `DEBUG` without editing the YAML file:

```bash
kubectl patch configmap web-config -n prod \
  --type merge -p '{"data":{"LOG_LEVEL":"DEBUG"}}'
```

---

**8.** After updating the ConfigMap, what must you do for a Deployment to pick up the change?

```bash
kubectl rollout restart deployment/<name> -n prod
# Env vars do NOT hot-reload — a pod restart is required
```

---

> **CKA Exam Tips:**
> - `--from-literal` for quick CM/Secret creation; `--from-file` for file-based config
> - `envFrom` = inject ALL keys; `valueFrom` = inject specific key
> - `configMapRef` / `secretRef` in `envFrom`; `configMapKeyRef` / `secretKeyRef` in `valueFrom`
> - `stringData:` in Secret YAML = plaintext (Kubernetes encodes it); `data:` = must be base64 already
> - Secrets mounted as volumes are **automatically refreshed**; env vars need Pod restart
> - ConfigMaps and Secrets are **namespace-scoped** — always specify `-n <namespace>`
> - Always use `base64 -d` (not `--decode`) on macOS and Linux for decoding

---

*Notes by ITkannadigaru | CKA 2026 Certification*

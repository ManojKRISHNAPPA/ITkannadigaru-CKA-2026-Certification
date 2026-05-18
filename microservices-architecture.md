# Microservices Architecture Design — From Internet to Service

> **Interview Answer: 10+ Years DevOps Experience**
> 
> *"Walk me through how you'd design the architecture for 5 microservices accessible from the internet."*

---

## Table of Contents

1. [High-Level Traffic Flow](#1-high-level-traffic-flow)
2. [DNS Layer](#2-dns-layer)
3. [CDN Layer](#3-cdn-layer)
4. [WAF — Web Application Firewall](#4-waf--web-application-firewall)
5. [Load Balancer (L7)](#5-load-balancer-l7)
6. [API Gateway](#6-api-gateway--the-critical-layer)
7. [Service Mesh](#7-service-mesh-east-west-traffic)
8. [The 5 Microservices — Internal Design](#8-the-5-microservices--internal-design-principles)
9. [Kubernetes Deployment](#9-kubernetes-deployment)
10. [Observability Stack](#10-observability-stack)
11. [Security Hardening](#11-security-hardening)
12. [CI/CD Pipeline](#12-cicd-pipeline-per-service)
13. [Disaster Recovery & HA](#13-disaster-recovery--high-availability)
14. [Key Talking Points](#14-key-talking-points-that-impress-interviewers)

---

## 1. High-Level Traffic Flow

```
Internet
   │
   ▼
[DNS — Route53 / Cloudflare]
   │
   ▼
[CDN — CloudFront / Fastly]         ← Static assets, DDoS protection, edge caching
   │
   ▼
[WAF — Web Application Firewall]    ← OWASP rules, rate limiting, IP blocking
   │
   ▼
[Load Balancer — Layer 7 ALB / Nginx / Traefik]
   │
   ▼
[API Gateway — Kong / AWS API GW / Apigee]   ← Auth, rate limit, routing
   │
   ├─────────────────────────────────────────────────────────┐
   ▼                                                         ▼
[Service Mesh — Istio / Linkerd]             [Internal Load Balancer]
   │                                                         │
   ├──► Service A — User Service                ├──► Service D — Payment Service
   ├──► Service B — Product Service             └──► Service E — Notification Service
   └──► Service C — Order Service
```

---

## 2. DNS Layer

| Component | Options | Notes |
|-----------|---------|-------|
| DNS Provider | Route53, Cloudflare DNS | Health checks built-in |
| Routing Policy | GeoDNS, Latency-based | Route users to nearest region |
| TTL | 60 seconds | Low TTL for fast failover |
| Failover | Active-Passive or Active-Active | Depends on RTO requirement |

**Key Design Decisions:**
- Use **GeoDNS** to route users to nearest region — reduces latency globally
- Set **low TTL (60s)** for production records to enable fast failover
- Enable **health checks** on DNS level — DNS stops resolving to unhealthy endpoints
- Use **latency-based routing** if running multi-region deployments

---

## 3. CDN Layer

```
User Request
    │
    ▼
[CDN Edge Node — nearest to user]
    │
    ├── Cache HIT  → Return cached response (no origin hit)
    │
    └── Cache MISS → Forward to Origin Shield
                          │
                          └── Forward to Load Balancer (origin)
```

**Tools:** CloudFront, Fastly, Akamai, Cloudflare

**What CDN handles:**
- Serve static assets (JS, CSS, images) from edge — reduces origin load by ~70%
- **TLS termination at edge** — offloads compute from your origin servers
- **DDoS protection** at edge level before traffic hits your infra
- **Origin Shield** — extra caching layer, reduces origin requests further
- Geo-blocking — restrict access by country if needed

**Cache-Control Strategy:**

```
Static Assets (JS/CSS/Images):  Cache-Control: public, max-age=31536000, immutable
API Responses (dynamic):        Cache-Control: no-store
Shared pages:                   Cache-Control: public, s-maxage=60, stale-while-revalidate=300
```

---

## 4. WAF — Web Application Firewall

**Tools:** AWS WAF, Cloudflare WAF, ModSecurity, Imperva

### Rule Categories

| Rule Type | What It Blocks |
|-----------|---------------|
| OWASP Top 10 | SQLi, XSS, path traversal, SSRF |
| Rate Limiting | Brute force, credential stuffing |
| Geo Blocking | Restrict by country/region |
| Bot Protection | Scrapers, bad bots, automated attacks |
| IP Reputation | Known malicious IPs, Tor exit nodes |
| Custom Rules | Business-specific block/allow logic |

**Key Practices:**
- Start WAF rules in **Count mode**, analyze logs, then switch to **Block mode**
- Set rate limits **per IP per endpoint** — not global rate limits
- Different rule sensitivity per service — Payment Service stricter than Product Service
- Integrate WAF logs with your **SIEM** for threat intelligence

---

## 5. Load Balancer (L7)

**Tools:** AWS ALB, GCP Global Load Balancer, Nginx, HAProxy, Traefik

```
Incoming Request: POST /api/orders/checkout
        │
        ▼
[ALB — Layer 7 Load Balancer]
        │
        ├── Path: /api/users/*     → User Service target group
        ├── Path: /api/products/*  → Product Service target group
        ├── Path: /api/orders/*    → Order Service target group
        ├── Path: /api/payments/*  → Payment Service target group
        └── Path: /api/notify/*    → Notification Service target group
```

**Responsibilities:**
- **Path-based routing** — route by URL path to correct service
- **Host-based routing** — route by domain/subdomain
- **SSL/TLS termination** — decrypt here, optionally re-encrypt to backend
- **Health checks** — remove unhealthy instances from rotation automatically
- **Connection draining** — graceful shutdown, no dropped requests during deploys
- **Sticky sessions** — if service requires session affinity (avoid if possible)

---

## 6. API Gateway — The Critical Layer

> **"I never expose a microservice directly to the internet. The API Gateway is the single entry point for all external traffic."**

**Tools:** Kong, AWS API Gateway, Apigee, Traefik, Tyk

```
Client Request
      │
      ▼
[API Gateway]
      │
      ├── 1. Authentication    → Validate JWT / OAuth2 / API Key
      ├── 2. Authorization     → Check scopes, roles, permissions
      ├── 3. Rate Limiting     → Per-client, per-endpoint quotas
      ├── 4. Request Transform → Inject headers, transform payload
      ├── 5. Routing           → Forward to correct microservice
      ├── 6. Response Transform→ Normalize responses, filter fields
      ├── 7. Logging           → Centralized access logs
      └── 8. Circuit Breaking  → Fail fast, prevent cascade failures
```

### Authentication Flow

```
Client ──► API Gateway ──► Auth Service (validate token)
                │
                ├── Token VALID   → Inject user-id header → Forward to service
                └── Token INVALID → 401 Unauthorized (never reaches service)
```

### Rate Limiting Strategy

| Tier | Limit | Window |
|------|-------|--------|
| Free users | 100 requests | per minute |
| Pro users | 1,000 requests | per minute |
| Internal services | 10,000 requests | per minute |
| Per endpoint (e.g., /login) | 10 requests | per minute per IP |

### Circuit Breaker Pattern

```
Normal State (CLOSED)
    │── Requests pass through normally
    │── Count failures
    │
    ▼ (failure threshold exceeded)

Open State (OPEN)
    │── All requests fail fast (no forwarding)
    │── Return cached response or error
    │── Wait for reset timeout
    │
    ▼ (after timeout)

Half-Open State
    │── Allow limited requests through
    │── If success → back to CLOSED
    └── If failure → back to OPEN
```

---

## 7. Service Mesh (East-West Traffic)

Once traffic is inside the cluster, service-to-service communication needs governance.

**Tools:** Istio, Linkerd, Consul Connect, AWS App Mesh

```
Service A ──────────────────────► Service B
  │                                   │
[Envoy Sidecar]                 [Envoy Sidecar]
  │                                   │
  └── mTLS encrypted tunnel ──────────┘
```

### What Service Mesh Provides

| Feature | Benefit |
|---------|---------|
| mTLS between all services | Zero-trust — no plaintext internal traffic |
| Retries with backoff | Handle transient failures automatically |
| Timeouts per route | Prevent slow services from blocking callers |
| Circuit breaking | Stop cascading failures |
| Traffic splitting | Canary deployments — 90% v1 / 10% v2 |
| Distributed tracing | Auto-inject trace headers via sidecar |
| Observability | Metrics per service-to-service call |

### Traffic Splitting (Canary Deployment)

```yaml
# Istio VirtualService example
apiVersion: networking.istio.io/v1alpha3
kind: VirtualService
metadata:
  name: order-service
spec:
  http:
  - route:
    - destination:
        host: order-service
        subset: v1
      weight: 90
    - destination:
        host: order-service
        subset: v2
      weight: 10
```

---

## 8. The 5 Microservices — Internal Design Principles

### Service Breakdown

| Service | Responsibility | DB | Sync/Async |
|---------|---------------|-----|------------|
| User Service | Auth, profiles, sessions | PostgreSQL | Sync (gRPC) |
| Product Service | Catalog, inventory, search | MongoDB | Sync (REST) |
| Order Service | Order lifecycle, cart | PostgreSQL | Both |
| Payment Service | Transactions, billing | PostgreSQL | Sync (gRPC) |
| Notification Service | Email, SMS, push | Redis + DynamoDB | Async (Kafka) |

### Core Design Rules

```
Each Microservice:
├── Owns its own database         ← No shared DB — avoids tight coupling
├── Has its own CI/CD pipeline    ← Deploy independently
├── Scales independently          ← HPA based on its own metrics
├── Has its own SLO/SLA           ← Different reliability targets
├── Fails independently           ← One service down != all down
└── Has its own config/secrets    ← No shared config files
```

### Communication Patterns

```
SYNCHRONOUS (real-time requirement):
User Service ──gRPC──► Auth check
Order Service ──gRPC──► Payment Service (charge card now)

ASYNCHRONOUS (decouple, tolerate failure):
Order Service ──Kafka event──► Notification Service (send confirmation email)
Product Service ──Kafka event──► Order Service (inventory update)

Benefits of async:
├── Notification Service can be down — orders still process
├── Natural buffer for traffic spikes
├── Retry failed events via dead letter queue
└── Event sourcing / audit log for free
```

### Event-Driven Flow Example

```
1. User places order
       │
       ▼
2. Order Service saves order (DB) → publishes "order.created" event to Kafka
       │
       ├──► Payment Service consumes event → processes payment
       │           │
       │           └── publishes "payment.success" or "payment.failed"
       │
       └──► Notification Service consumes "order.created" → sends email
```

---

## 9. Kubernetes Deployment

### Per-Service Kubernetes Resources

```yaml
# Deployment — Rolling update strategy
apiVersion: apps/v1
kind: Deployment
metadata:
  name: order-service
spec:
  replicas: 3
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxSurge: 1
      maxUnavailable: 0        # Zero downtime deployments
  template:
    spec:
      containers:
      - name: order-service
        image: order-service:v1.2.3
        resources:
          requests:
            cpu: "250m"
            memory: "256Mi"
          limits:
            cpu: "500m"
            memory: "512Mi"
        livenessProbe:
          httpGet:
            path: /health/live
            port: 8080
          initialDelaySeconds: 10
        readinessProbe:
          httpGet:
            path: /health/ready
            port: 8080
```

```yaml
# HPA — Horizontal Pod Autoscaler
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: order-service-hpa
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: order-service
  minReplicas: 3
  maxReplicas: 20
  metrics:
  - type: Resource
    resource:
      name: cpu
      target:
        type: Utilization
        averageUtilization: 70
```

```yaml
# PodDisruptionBudget — Maintain availability during node drain
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata:
  name: order-service-pdb
spec:
  minAvailable: 2
  selector:
    matchLabels:
      app: order-service
```

```yaml
# Network Policy — Whitelist only allowed traffic
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: order-service-netpol
spec:
  podSelector:
    matchLabels:
      app: order-service
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: api-gateway       # Only API gateway can reach order service
  - from:
    - podSelector:
        matchLabels:
          app: payment-service   # Payment service can call back
```

### Multi-Namespace Strategy

```
Namespaces:
├── production      → Live traffic
├── staging         → Pre-prod validation
├── development     → Dev testing
├── monitoring      → Prometheus, Grafana, Jaeger
├── ingress         → Ingress controllers
└── service-mesh    → Istio control plane
```

---

## 10. Observability Stack

> **"Observability is not an afterthought — metrics, logs, and traces are day-1 requirements."**

### The Three Pillars

```
                    OBSERVABILITY
                         │
          ┌──────────────┼──────────────┐
          ▼              ▼              ▼
       METRICS          LOGS          TRACES
          │              │              │
    Prometheus       ELK / Loki      Jaeger /
    + Grafana        + Grafana        Zipkin
          │              │              │
    "Is it slow?"   "What failed?"  "Where is it slow?"
```

### Metrics (Prometheus + Grafana)

```
Per Service — Track these metrics (RED Method):
├── Rate        → Requests per second
├── Errors      → Error rate (4xx, 5xx)
└── Duration    → P50, P95, P99 latency

Infrastructure Metrics:
├── CPU, Memory, Disk per pod/node
├── Network I/O
├── DB connection pool usage
└── Kafka consumer lag
```

### Logging Strategy

```json
// Structured JSON logs — every service
{
  "timestamp": "2026-05-18T10:30:00Z",
  "level": "ERROR",
  "service": "order-service",
  "trace_id": "abc-123-xyz",
  "span_id": "def-456",
  "user_id": "usr_789",
  "message": "Payment processing failed",
  "error_code": "PAYMENT_TIMEOUT",
  "duration_ms": 5002
}
```

**Log Levels by Environment:**

| Environment | Log Level |
|-------------|-----------|
| Production | WARN + ERROR only |
| Staging | INFO + above |
| Development | DEBUG + above |

### Distributed Tracing

```
User Request → API Gateway → Order Service → Payment Service
     │               │              │               │
  trace_id        span_id        span_id         span_id
  abc-123          001            002             003

Timeline:
|──────────────── 450ms total ───────────────────|
     |── API GW: 10ms ──|
                         |── Order Svc: 50ms ──|
                                                 |── Payment: 390ms ──|
                                                       ↑
                                               BOTTLENECK IDENTIFIED
```

### Alerting Rules

| Alert | Threshold | Severity |
|-------|-----------|----------|
| Error rate | > 1% for 5 min | Critical |
| P99 latency | > 2s for 5 min | Warning |
| Pod restarts | > 3 in 10 min | Warning |
| Kafka consumer lag | > 10,000 messages | Critical |
| CPU usage | > 85% for 10 min | Warning |
| DB connections | > 90% pool used | Critical |

---

## 11. Security Hardening

### Defense in Depth

```
Layer 1 — Network
├── VPC with private subnets (services not publicly routable)
├── Security Groups — whitelist only required ports
├── NACLs — subnet-level firewall
└── VPC Flow Logs — network traffic visibility

Layer 2 — Application Entry
├── WAF — block malicious requests
├── API Gateway — authentication before any service is reached
└── TLS everywhere — no HTTP in prod

Layer 3 — Service-to-Service
├── mTLS via service mesh — mutual authentication
├── Network Policies — whitelist allowed service connections
└── Zero-trust — no implicit trust between services

Layer 4 — Container / Pod
├── Non-root user in all containers
├── Read-only root filesystem
├── No privileged containers
├── Seccomp + AppArmor profiles
└── Image signing (Cosign) — only verified images run

Layer 5 — Secrets Management
├── HashiCorp Vault / AWS Secrets Manager
├── No secrets in environment variables or config maps
├── Secret rotation automated
└── Audit log on every secret access
```

### Secret Management Flow

```
Service Startup
      │
      ▼
[Vault Agent Sidecar]
      │
      ├── Authenticate with Vault (via K8s ServiceAccount)
      ├── Fetch secrets for this service only
      ├── Inject as in-memory files (not env vars)
      └── Auto-rotate before expiry (no restart needed)
```

### RBAC — Least Privilege

```yaml
# Each service gets its own ServiceAccount
apiVersion: v1
kind: ServiceAccount
metadata:
  name: order-service-sa
  namespace: production
---
# IAM Role for order-service — only what it needs
# Can read from order-db S3 backups
# Can publish to order-events Kafka topic
# Cannot access payment-db or user-db
```

---

## 12. CI/CD Pipeline Per Service

> **"GitOps for deployments — the Git repo is the source of truth, not kubectl commands."**

### Pipeline Stages

```
Developer pushes code
         │
         ▼
[GitHub / GitLab]
         │
         ▼
[CI — GitHub Actions / Jenkins / GitLab CI]
         │
         ├── 1. Lint + Unit Tests           (fail fast)
         ├── 2. Integration Tests           (real DB, not mocks)
         ├── 3. SAST Scan (Semgrep/Sonar)   (security static analysis)
         ├── 4. Dependency Audit            (CVE check — Snyk/OWASP)
         ├── 5. Docker Build
         ├── 6. Container Scan (Trivy)      (CVE scan on image)
         ├── 7. Push to ECR/Artifact Reg    (tagged with git SHA)
         └── 8. Update GitOps Repo          (bump image tag in Helm values)
                          │
                          ▼
              [ArgoCD watches GitOps repo]
                          │
                          ├── Dev     → Auto-sync + deploy
                          ├── Staging → Auto-sync + smoke tests
                          └── Prod    → Manual approval gate
                                            │
                                            ▼
                                  [Canary Deployment]
                                  10% traffic → new version
                                  Monitor SLOs for 10 min
                                  Promote or auto-rollback
```

### Deployment Strategy Per Environment

| Environment | Strategy | Approval | Rollback |
|-------------|----------|----------|----------|
| Development | Recreate | Auto | Manual |
| Staging | Rolling Update | Auto | Auto |
| Production | Canary → Rolling | Manual gate | Auto (SLO breach) |

### Rollback Trigger

```
Production Canary Running
        │
        ├── P99 latency > threshold  ──► Auto-rollback
        ├── Error rate > 1%          ──► Auto-rollback
        ├── Pod crash loops          ──► Auto-rollback
        └── All metrics healthy      ──► Promote to 100%
```

---

## 13. Disaster Recovery & High Availability

### Availability Design

```
Single AZ — AVOID in production
Multi-AZ  — Minimum for production (99.95% SLA)
Multi-Region — For critical services (99.99%+ SLA)

Per Service HA Setup:
├── Min 3 replicas (survive 1 pod failure + 1 node drain)
├── Spread across 3 availability zones (PodAntiAffinity)
├── HPA ready to scale on traffic spikes
└── PDB ensures min replicas during node maintenance
```

### Database HA

```
PostgreSQL:
├── Primary + 2 Read Replicas (Multi-AZ)
├── Automated backups (point-in-time recovery)
├── Failover < 30 seconds (RDS Multi-AZ or Patroni)
└── Connection pooling via PgBouncer

Kafka:
├── 3 brokers minimum (replication factor 3)
├── Min ISR (in-sync replicas) = 2
├── Cross-AZ broker placement
└── Consumer group rebalancing on failure
```

### RTO / RPO Targets

| Service | RTO | RPO | Strategy |
|---------|-----|-----|----------|
| Payment Service | < 1 min | 0 (no data loss) | Active-Active multi-region |
| Order Service | < 5 min | < 1 min | Multi-AZ, async replication |
| User Service | < 5 min | < 1 min | Multi-AZ |
| Product Service | < 15 min | < 5 min | Single region, Multi-AZ |
| Notification Service | < 30 min | < 10 min | Best effort |

### Chaos Engineering

```
Practice failure before it happens in prod:
├── Chaos Monkey — randomly kill pods
├── Litmus Chaos — network partition, CPU stress, I/O throttle
├── Game Days — scheduled failure injection exercises
└── Runbooks — documented recovery steps per failure scenario
```

---

## 14. Key Talking Points That Impress Interviewers

> These statements signal senior-level thinking. Use them naturally in your answer.

---

**On API Gateway:**
> *"I never expose a microservice directly to the internet. The API Gateway is the single entry point — authentication, authorization, and rate limiting happen there before any service is touched."*

---

**On Databases:**
> *"Each service owns its own database. No shared schemas. If Service A goes down, Service B's DB is unaffected. We use the Saga pattern for distributed transactions instead of shared DBs."*

---

**On Internal Security:**
> *"East-west traffic uses mTLS via the service mesh. Zero-trust by default — a compromised service can't freely talk to other services. Network policies whitelist exactly what each service is allowed to call."*

---

**On Failure Design:**
> *"I design for failure. Circuit breakers prevent cascade failures. Kafka decouples async workflows so a slow consumer doesn't block producers. Dead letter queues catch failures for replay."*

---

**On Observability:**
> *"Observability is a day-1 requirement, not an afterthought. Before a service ships to prod, it must emit metrics, structured logs with trace IDs, and distributed traces. We define SLOs and burn rate alerts before launch."*

---

**On Deployments:**
> *"GitOps — the Git repository is the source of truth. No one kubectl-applies to prod. ArgoCD watches the repo and syncs. Every production deployment goes through a canary with automated SLO-based promotion or rollback."*

---

**On Scaling:**
> *"Each service scales independently based on its own metrics. The Notification Service might scale on Kafka consumer lag while the Order Service scales on CPU. One HPA config doesn't fit all."*

---

## Summary Architecture Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                           INTERNET                              │
└─────────────────────────────┬───────────────────────────────────┘
                              │
                    ┌─────────▼─────────┐
                    │   DNS (Route53)    │  GeoDNS, health checks
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │       CDN          │  Edge cache, TLS termination
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │       WAF          │  OWASP rules, rate limiting
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │  Load Balancer L7  │  Path routing, health checks
                    └─────────┬─────────┘
                              │
                    ┌─────────▼─────────┐
                    │   API Gateway      │  Auth, rate limit, routing
                    └────────┬──────────┘
                             │
              ┌──────────────┼──────────────┐
              │         Service Mesh (mTLS)  │
              │                             │
   ┌──────────▼──────┐           ┌──────────▼──────┐
   │  User Service   │           │ Payment Service  │
   │  (PostgreSQL)   │           │  (PostgreSQL)    │
   └─────────────────┘           └─────────────────┘
   ┌─────────────────┐           ┌─────────────────┐
   │ Product Service │           │Notification Svc  │
   │   (MongoDB)     │           │ (Kafka consumer) │
   └─────────────────┘           └─────────────────┘
   ┌─────────────────┐
   │  Order Service  │──────────────► [Kafka] ──► Notification
   │  (PostgreSQL)   │
   └─────────────────┘

              │                    │                   │
   ┌──────────▼────────────────────▼───────────────────▼──────────┐
   │               OBSERVABILITY PLANE                             │
   │  Prometheus + Grafana │ ELK/Loki │ Jaeger │ PagerDuty        │
   └───────────────────────────────────────────────────────────────┘
```

---

*Document covers: DNS → CDN → WAF → Load Balancer → API Gateway → Service Mesh → Microservices → Kubernetes → Observability → Security → CI/CD → Disaster Recovery*

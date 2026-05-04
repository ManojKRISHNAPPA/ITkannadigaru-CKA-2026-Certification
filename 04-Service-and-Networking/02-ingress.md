# Kubernetes Ingress — Complete Guide with Practical Setup

> Ingress is the smart traffic cop at the edge of your cluster — routing HTTP/HTTPS by host and path so you don't need a cloud LoadBalancer per service.

---

## Table of Contents

### Ingress & Controllers
1. [What is Ingress?](#1-what-is-ingress)
2. [Why Ingress? — The Problem it Solves](#2-why-ingress--the-problem-it-solves)
3. [Ingress Architecture — Resource vs Controller](#3-ingress-architecture--resource-vs-controller)
4. [Install NGINX Ingress Controller](#4-install-nginx-ingress-controller)
   - [4.1 On Minikube](#41-on-minikube)
   - [4.2 On kubeadm / Bare Metal](#42-on-kubeadm--bare-metal)
   - [4.3 On Kind (local)](#43-on-kind-local)
5. [Install AWS ALB Ingress Controller (AWS LB Controller)](#5-install-aws-alb-ingress-controller-aws-lb-controller)
   - [5.1 Prerequisites](#51-prerequisites)
   - [5.2 Create IAM Policy](#52-create-iam-policy)
   - [5.3 Create IAM Role & Service Account (IRSA)](#53-create-iam-role--service-account-irsa)
   - [5.4 Install via Helm](#54-install-via-helm)
   - [5.5 Verify Installation](#55-verify-installation)
6. [Ingress Rules — Deep Dive](#6-ingress-rules--deep-dive)
   - [6.1 Host-Based Routing](#61-host-based-routing)
   - [6.2 Path-Based Routing](#62-path-based-routing)
   - [6.3 Combined Host + Path Routing](#63-combined-host--path-routing)
   - [6.4 Default Backend](#64-default-backend)
   - [6.5 TLS / HTTPS](#65-tls--https)
7. [Ingress Annotations](#7-ingress-annotations)
8. [Simple End-to-End Demo](#8-simple-end-to-end-demo)
9. [AWS ALB Ingress Demo](#9-aws-alb-ingress-demo)
10. [Ingress vs Service Comparison](#10-ingress-vs-service-comparison)
11. [Common Interview Questions](#11-common-interview-questions)
12. [Exam Practice Questions](#12-exam-practice-questions)

---

## 1. What is Ingress?

**Ingress** is a Kubernetes API object that manages **external HTTP and HTTPS access** to services inside a cluster. It provides:

- **Layer 7** (HTTP/HTTPS) routing — unlike Services which are Layer 4 (TCP/UDP)
- **Host-based** routing — `api.example.com` → API service, `web.example.com` → Web service
- **Path-based** routing — `/api` → API service, `/static` → CDN service
- **TLS termination** — handle SSL certificates in one place
- **Single entry point** — one IP/LoadBalancer for many services

```
  Before Ingress (1 LB per service = expensive):        With Ingress (1 LB for all):

  api.example.com  → LB1 → api-service                 ┌──────────────────────────┐
  web.example.com  → LB2 → web-service     →            │     Ingress Controller   │
  app.example.com  → LB3 → app-service                  │  1 LoadBalancer IP        │
                                                         └────────────┬─────────────┘
  Cost: 3 cloud LBs $$$$                                             │
                                                        ┌────────────┴───────────────┐
                                                        │ Routing Rules (Ingress obj)│
                                                        │ api.example.com → api-svc  │
                                                        │ web.example.com → web-svc  │
                                                        │ /app            → app-svc  │
                                                        └────────────────────────────┘
                                                        Cost: 1 cloud LB $
```

> **Key rule**: Ingress itself is just a **configuration object** (a set of rules). It does nothing without an **Ingress Controller** running in the cluster to actually process those rules.

---

## 2. Why Ingress? — The Problem it Solves

### Without Ingress

```
  User Traffic:
  
  curl api.myapp.com     → needs LoadBalancer ($$$) → api-service → api Pods
  curl web.myapp.com     → needs LoadBalancer ($$$) → web-service → web Pods
  curl admin.myapp.com   → needs LoadBalancer ($$$) → admin-service → admin Pods

  Problems:
  ✗ 3 external IPs to manage
  ✗ 3 cloud load balancer costs
  ✗ No URL path routing
  ✗ TLS certificate managed separately in each service
  ✗ No centralized access control or rate limiting
```

### With Ingress

```
  User Traffic:
  
  curl api.myapp.com       ─┐
  curl web.myapp.com       ─┤─→  Single IP  →  Ingress Controller  →  routes by rules
  curl admin.myapp.com     ─┘         │
  curl myapp.com/api       ─┘         │
                                      │
                           ┌──────────┴──────────────────────────┐
                           │         Routing Decision             │
                           │  host=api.myapp.com   → api-svc     │
                           │  host=web.myapp.com   → web-svc     │
                           │  path=/api            → api-svc     │
                           │  default              → 404-page    │
                           └─────────────────────────────────────┘

  Benefits:
  ✓ 1 external IP / 1 cloud LB
  ✓ Centralized TLS termination
  ✓ Host and path based routing
  ✓ Annotations for rate limiting, auth, redirects
```

---

## 3. Ingress Architecture — Resource vs Controller

Understanding the two-part architecture is critical:

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                      Kubernetes Cluster                          │
  │                                                                  │
  │   ┌───────────────────┐          ┌──────────────────────────┐   │
  │   │  Ingress Resource │          │   Ingress Controller     │   │
  │   │  (YAML config)    │◄─reads───│   (nginx/traefik/alb)    │   │
  │   │                   │          │   Runs as Pod(s)          │   │
  │   │  Rules:           │          │                          │   │
  │   │  host → service   │          │   Watches API server     │   │
  │   │  path → service   │          │   Configures itself      │   │
  │   └───────────────────┘          │   Handles real traffic   │   │
  │                                  └──────────┬───────────────┘   │
  │                                             │                   │
  │                                  ┌──────────┴───────────────┐   │
  │                                  │   LoadBalancer Service   │   │
  │                                  │   (exposes controller)   │   │
  │                                  └──────────────────────────┘   │
  └──────────────────────────────────────────────────────────────────┘
                                             │
                                    External IP / DNS
                                             │
                                        User Traffic
```

| Component | What it is | Who manages it |
|-----------|-----------|----------------|
| **Ingress Resource** | YAML object with routing rules | You (the developer/admin) |
| **Ingress Controller** | Pod(s) that read rules and route traffic | Cluster admin installs it |
| **IngressClass** | Tells which controller handles which Ingress | Cluster admin configures it |

### Popular Ingress Controllers

| Controller | Best For |
|------------|----------|
| **nginx** | Most common, on-prem and cloud |
| **AWS ALB** | Native AWS, uses Application Load Balancer |
| **GCE** | Google Cloud, uses GCP HTTP LB |
| **Traefik** | Cloud-native, auto-discovers services |
| **HAProxy** | High performance, enterprise |
| **Istio** | Service mesh, advanced traffic management |

---

## 4. Install NGINX Ingress Controller

### 4.1 On Minikube

Minikube has a built-in nginx ingress addon — the easiest way to get started.

```bash
# Step 1: Enable the ingress addon
minikube addons enable ingress

# Step 2: Verify the controller pod is running (namespace: ingress-nginx)
kubectl get pods -n ingress-nginx

# Expected output:
# NAME                                        READY   STATUS    RESTARTS
# ingress-nginx-controller-7c6974c4d8-xxxxx   1/1     Running   0

# Step 3: Verify IngressClass was created
kubectl get ingressclass

# Expected output:
# NAME    CONTROLLER             PARAMETERS   AGE
# nginx   k8s.io/ingress-nginx   <none>       2m

# Step 4: Get the minikube IP (use this as your "external" IP)
minikube ip
# Output: 192.168.49.2
```

---

### 4.2 On kubeadm / Bare Metal

Use the official manifests from the nginx ingress project.

```bash
# Step 1: Apply the official nginx ingress manifest
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.1/deploy/static/provider/baremetal/deploy.yaml

# Step 2: Watch controller pod come up
kubectl get pods -n ingress-nginx -w

# Step 3: Confirm all resources created
kubectl get all -n ingress-nginx

# Expected resources:
# pod/ingress-nginx-controller-xxx   Running
# service/ingress-nginx-controller   NodePort  (port 80:3xxxx/TCP, 443:3xxxx/TCP)
# deployment.apps/ingress-nginx-controller
```

**On bare metal, the controller is exposed via NodePort** (no cloud LB available):

```bash
# Get the NodePorts for HTTP and HTTPS
kubectl get svc -n ingress-nginx

# NAME                                 TYPE       CLUSTER-IP    PORT(S)
# ingress-nginx-controller             NodePort   10.96.x.x     80:30080/TCP,443:30443/TCP

# Access via: http://<NODE-IP>:30080
```

**Optional: Use MetalLB for a real LoadBalancer IP on bare metal**

```bash
# Install MetalLB
kubectl apply -f https://raw.githubusercontent.com/metallb/metallb/v0.14.5/config/manifests/metallb-native.yaml

# Configure an IP pool (edit the range to match your network)
cat <<EOF | kubectl apply -f -
apiVersion: metallb.io/v1beta1
kind: IPAddressPool
metadata:
  name: default-pool
  namespace: metallb-system
spec:
  addresses:
  - 192.168.1.200-192.168.1.250   # adjust to your LAN range
---
apiVersion: metallb.io/v1beta1
kind: L2Advertisement
metadata:
  name: default
  namespace: metallb-system
EOF

# Now nginx ingress service will get a real EXTERNAL-IP from the pool
kubectl get svc -n ingress-nginx
```

---

### 4.3 On Kind (local)

Kind requires extra port mapping at cluster creation time.

```bash
# Step 1: Create kind cluster with port mapping
cat <<EOF > kind-config.yaml
kind: Cluster
apiVersion: kind.x-k8s.io/v1alpha4
nodes:
- role: control-plane
  kubeadmConfigPatches:
  - |
    kind: InitConfiguration
    nodeRegistration:
      kubeletExtraArgs:
        node-labels: "ingress-ready=true"
  extraPortMappings:
  - containerPort: 80
    hostPort: 80           # localhost:80 maps to cluster port 80
    protocol: TCP
  - containerPort: 443
    hostPort: 443
    protocol: TCP
EOF

kind create cluster --config kind-config.yaml

# Step 2: Install nginx ingress for Kind
kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.10.1/deploy/static/provider/kind/deploy.yaml

# Step 3: Wait for it to be ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=90s

# Step 4: Ingress is now accessible at localhost:80
curl http://localhost/
```

---

## 5. Install AWS ALB Ingress Controller (AWS LB Controller)

The **AWS Load Balancer Controller** creates an **Application Load Balancer (ALB)** per Ingress resource on EKS. This is the production-grade setup for AWS.

```
  Internet
     │
     ▼
  ┌────────────────────────┐
  │   AWS ALB              │  ← provisioned automatically per Ingress
  │   (Application LB)     │
  └──────────┬─────────────┘
             │ Target Groups (Pod IPs directly — no NodePort!)
    ┌────────┴────────┐
    ▼                 ▼
  Pod A             Pod B
```

### 5.1 Prerequisites

```bash
# You need:
# 1. EKS cluster running (eksctl or terraform)
# 2. eksctl installed
# 3. AWS CLI configured
# 4. Helm 3 installed
# 5. kubectl connected to EKS cluster

# Verify cluster connection
kubectl get nodes

# Check your cluster name and region
aws eks list-clusters
export CLUSTER_NAME=my-eks-cluster
export AWS_REGION=us-east-1
export AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Cluster: $CLUSTER_NAME"
echo "Region:  $AWS_REGION"
echo "Account: $AWS_ACCOUNT_ID"
```

### 5.2 Create IAM Policy

The controller needs IAM permissions to create/manage ALBs on your behalf.

```bash
# Step 1: Download the official IAM policy JSON
curl -O https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.7.2/docs/install/iam_policy.json

# Step 2: Create the IAM policy in your AWS account
aws iam create-policy \
  --policy-name AWSLoadBalancerControllerIAMPolicy \
  --policy-document file://iam_policy.json

# Save the policy ARN from output — you'll need it next
# Example: arn:aws:iam::123456789012:policy/AWSLoadBalancerControllerIAMPolicy
export POLICY_ARN="arn:aws:iam::${AWS_ACCOUNT_ID}:policy/AWSLoadBalancerControllerIAMPolicy"
```

### 5.3 Create IAM Role & Service Account (IRSA)

IRSA (IAM Roles for Service Accounts) lets the controller Pod assume an IAM role without storing credentials.

```bash
# Step 1: Ensure OIDC provider is associated with your cluster
eksctl utils associate-iam-oidc-provider \
  --region $AWS_REGION \
  --cluster $CLUSTER_NAME \
  --approve

# Step 2: Create IAM service account (creates IAM role + k8s ServiceAccount)
eksctl create iamserviceaccount \
  --cluster=$CLUSTER_NAME \
  --namespace=kube-system \
  --name=aws-load-balancer-controller \
  --role-name AmazonEKSLoadBalancerControllerRole \
  --attach-policy-arn=$POLICY_ARN \
  --approve \
  --region=$AWS_REGION

# Step 3: Verify the service account was created
kubectl get serviceaccount aws-load-balancer-controller -n kube-system

# Verify the IAM annotation is set
kubectl describe sa aws-load-balancer-controller -n kube-system | grep Annotations
# Should show: eks.amazonaws.com/role-arn: arn:aws:iam::...
```

### 5.4 Install via Helm

```bash
# Step 1: Add the EKS Helm chart repository
helm repo add eks https://aws.github.io/eks-charts
helm repo update

# Step 2: Get your VPC ID (needed for controller configuration)
export VPC_ID=$(aws eks describe-cluster \
  --name $CLUSTER_NAME \
  --query "cluster.resourcesVpcConfig.vpcId" \
  --output text)
echo "VPC ID: $VPC_ID"

# Step 3: Install the controller
helm install aws-load-balancer-controller eks/aws-load-balancer-controller \
  -n kube-system \
  --set clusterName=$CLUSTER_NAME \
  --set serviceAccount.create=false \
  --set serviceAccount.name=aws-load-balancer-controller \
  --set region=$AWS_REGION \
  --set vpcId=$VPC_ID \
  --set image.repository=602401143452.dkr.ecr.$AWS_REGION.amazonaws.com/amazon/aws-load-balancer-controller

# Note: The image repository account ID (602401143452) is AWS-managed and is the same across regions
# For regions outside us-*/eu-*/ap-*, verify the correct account at AWS docs
```

### 5.5 Verify Installation

```bash
# Step 1: Check controller pods are running
kubectl get deployment -n kube-system aws-load-balancer-controller

# Expected:
# NAME                           READY   UP-TO-DATE   AVAILABLE
# aws-load-balancer-controller   2/2     2            2

# Step 2: Check controller logs (should show no errors)
kubectl logs -n kube-system \
  -l app.kubernetes.io/name=aws-load-balancer-controller \
  --tail=20

# Step 3: Verify IngressClass was created
kubectl get ingressclass

# Expected:
# NAME   CONTROLLER                        PARAMETERS   AGE
# alb    ingress.k8s.aws/alb               IngressClassParams.elbv2.k8s.aws/default   2m

# Step 4: Verify CRDs were installed
kubectl get crd | grep elbv2
# targetgroupbindings.elbv2.k8s.aws
# ingressclassparams.elbv2.k8s.aws
```

> **CKA Tip**: The AWS LB Controller requires subnet tags for ALB provisioning to work. Public subnets need `kubernetes.io/role/elb=1` and private subnets need `kubernetes.io/role/internal-elb=1`.

```bash
# Tag public subnets (replace with your subnet IDs)
aws ec2 create-tags \
  --resources subnet-xxxxxxxx subnet-yyyyyyyy \
  --tags Key=kubernetes.io/role/elb,Value=1

# Tag private subnets
aws ec2 create-tags \
  --resources subnet-aaaaaaaaa subnet-bbbbbbbbb \
  --tags Key=kubernetes.io/role/internal-elb,Value=1
```

---

## 6. Ingress Rules — Deep Dive

### Anatomy of an Ingress Resource

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
  namespace: default
  annotations:                          # controller-specific config
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx               # which controller handles this
  defaultBackend:                       # catch-all if no rules match
    service:
      name: fallback-service
      port:
        number: 80
  tls:                                  # TLS config (optional)
  - hosts:
    - example.com
    secretName: example-tls
  rules:                                # routing rules
  - host: example.com                   # hostname match
    http:
      paths:
      - path: /api                      # path match
        pathType: Prefix                # Prefix | Exact | ImplementationSpecific
        backend:
          service:
            name: api-service
            port:
              number: 8080
```

### Path Types

| pathType | Behaviour | Example path `/api` matches |
|----------|-----------|------------------------------|
| **Prefix** | Matches path prefix, after stripping trailing `/` | `/api`, `/api/v1`, `/api/v2/users` |
| **Exact** | Matches exact path only | `/api` only — `/api/v1` does NOT match |
| **ImplementationSpecific** | Controller decides (nginx uses regex) | Depends on controller |

---

### 6.1 Host-Based Routing

Different domains go to different services — like virtual hosting.

```
  api.example.com   ──►  api-service   (port 8080)
  web.example.com   ──►  web-service   (port 80)
  admin.example.com ──►  admin-service (port 9090)
```

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: host-based-ingress
spec:
  ingressClassName: nginx
  rules:
  - host: api.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: api-service
            port:
              number: 8080

  - host: web.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80

  - host: admin.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: admin-service
            port:
              number: 9090
```

---

### 6.2 Path-Based Routing

Single domain, different paths go to different services.

```
  example.com/         ──►  frontend-service
  example.com/api      ──►  api-service
  example.com/static   ──►  cdn-service
```

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: path-based-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /$2   # strips the path prefix
spec:
  ingressClassName: nginx
  rules:
  - host: example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-service
            port:
              number: 80

      - path: /api(/|$)(.*)
        pathType: ImplementationSpecific
        backend:
          service:
            name: api-service
            port:
              number: 8080

      - path: /static
        pathType: Prefix
        backend:
          service:
            name: cdn-service
            port:
              number: 80
```

---

### 6.3 Combined Host + Path Routing

The most common production pattern — multiple hosts each with multiple paths.

```
  app.example.com/        ──►  frontend-svc
  app.example.com/api     ──►  backend-svc
  app.example.com/health  ──►  health-svc (Exact match)

  admin.example.com/      ──►  admin-svc
  admin.example.com/logs  ──►  logging-svc
```

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: combined-ingress
spec:
  ingressClassName: nginx
  rules:
  - host: app.example.com
    http:
      paths:
      - path: /health
        pathType: Exact               # exact match wins over Prefix
        backend:
          service:
            name: health-svc
            port:
              number: 8080

      - path: /api
        pathType: Prefix
        backend:
          service:
            name: backend-svc
            port:
              number: 8080

      - path: /
        pathType: Prefix             # catch-all for this host
        backend:
          service:
            name: frontend-svc
            port:
              number: 80

  - host: admin.example.com
    http:
      paths:
      - path: /logs
        pathType: Prefix
        backend:
          service:
            name: logging-svc
            port:
              number: 9200

      - path: /
        pathType: Prefix
        backend:
          service:
            name: admin-svc
            port:
              number: 80
```

> **Routing priority**: More specific rules (Exact) are matched before less specific ones (Prefix). Longer Prefix paths match before shorter ones.

---

### 6.4 Default Backend

The **default backend** receives all traffic that matches no rule. It's your 404 handler.

```
  Traffic to unknown host or path  ──►  default-backend (shows error page)
```

```yaml
# Option 1: defaultBackend field in Ingress
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
spec:
  ingressClassName: nginx
  defaultBackend:
    service:
      name: custom-404-service
      port:
        number: 80
  rules:
  - host: example.com
    ...
```

```yaml
# Option 2: Set cluster-wide default backend when installing nginx
# (via Helm values)
controller:
  defaultBackend:
    enabled: true
    image:
      repository: registry.k8s.io/defaultbackend-amd64
      tag: "1.5"
```

---

### 6.5 TLS / HTTPS

Ingress can terminate TLS (SSL) and serve traffic over HTTPS.

```
  Browser ──HTTPS──► Ingress Controller (decrypts TLS) ──HTTP──► Service ──► Pods
                           │
                    reads TLS cert from
                    Kubernetes Secret
```

**Step 1: Create a TLS Secret**

```bash
# Generate a self-signed cert (for testing)
openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
  -keyout tls.key \
  -out tls.crt \
  -subj "/CN=example.com/O=example"

# Create the Kubernetes Secret
kubectl create secret tls example-tls \
  --key tls.key \
  --cert tls.crt

# Verify
kubectl get secret example-tls
```

**Step 2: Reference the Secret in Ingress**

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: tls-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"   # force HTTPS redirect
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - example.com                # must match the cert CN
    secretName: example-tls      # Secret with tls.crt and tls.key
  rules:
  - host: example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
```

**Production TLS with cert-manager (auto-renewing certs):**

```bash
# Install cert-manager
kubectl apply -f https://github.com/cert-manager/cert-manager/releases/latest/download/cert-manager.yaml

# Create a ClusterIssuer for Let's Encrypt
cat <<EOF | kubectl apply -f -
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: letsencrypt-prod
spec:
  acme:
    server: https://acme-v02.api.letsencrypt.org/directory
    email: admin@example.com
    privateKeySecretRef:
      name: letsencrypt-prod
    solvers:
    - http01:
        ingress:
          class: nginx
EOF
```

```yaml
# Ingress with auto-TLS via cert-manager annotation
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: auto-tls-ingress
  annotations:
    cert-manager.io/cluster-issuer: letsencrypt-prod   # auto-provision cert
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - example.com
    secretName: example-com-tls   # cert-manager will create this secret
  rules:
  - host: example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: web-service
            port:
              number: 80
```

---

## 7. Ingress Annotations

Annotations customize controller behaviour without changing the spec. Each controller has its own annotation prefix.

### NGINX Annotations

```yaml
metadata:
  annotations:
    # Rewrite target path
    nginx.ingress.kubernetes.io/rewrite-target: /

    # Force HTTPS redirect
    nginx.ingress.kubernetes.io/ssl-redirect: "true"

    # Rate limiting — 10 requests/second per IP
    nginx.ingress.kubernetes.io/limit-rps: "10"

    # Enable CORS
    nginx.ingress.kubernetes.io/enable-cors: "true"

    # Custom connection timeout
    nginx.ingress.kubernetes.io/proxy-connect-timeout: "30"
    nginx.ingress.kubernetes.io/proxy-read-timeout: "60"

    # Max request body size (default 1m)
    nginx.ingress.kubernetes.io/proxy-body-size: "50m"

    # Sticky sessions
    nginx.ingress.kubernetes.io/affinity: "cookie"
    nginx.ingress.kubernetes.io/session-cookie-name: "INGRESSCOOKIE"
```

### AWS ALB Annotations

```yaml
metadata:
  annotations:
    # Required: mark this ingress for ALB controller
    kubernetes.io/ingress.class: alb

    # Internet-facing or internal ALB
    alb.ingress.kubernetes.io/scheme: internet-facing

    # Target type: ip (pod direct) or instance (nodeport)
    alb.ingress.kubernetes.io/target-type: ip

    # Subnets for ALB (optional, auto-discovered if tagged)
    alb.ingress.kubernetes.io/subnets: subnet-xxx,subnet-yyy

    # SSL certificate from ACM
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:123456789012:certificate/xxx

    # HTTP → HTTPS redirect
    alb.ingress.kubernetes.io/ssl-redirect: "443"

    # Health check settings
    alb.ingress.kubernetes.io/healthcheck-path: /health
    alb.ingress.kubernetes.io/healthcheck-interval-seconds: "30"
```

---

## 8. Simple End-to-End Demo

This demo runs entirely on **Minikube** and shows host-based + path-based routing.

### What we're building

```
  http://hello.local/      ──►  hello-app (shows "Hello from v1")
  http://hello.local/v2    ──►  hello-app-v2 (shows "Hello from v2")
  http://world.local/      ──►  world-app (shows "World App")
```

### Step 1: Start Minikube and Enable Ingress

```bash
minikube start
minikube addons enable ingress

# Wait for nginx controller to be ready
kubectl wait --namespace ingress-nginx \
  --for=condition=ready pod \
  --selector=app.kubernetes.io/component=controller \
  --timeout=120s

kubectl get pods -n ingress-nginx
```

### Step 2: Deploy Three Applications

```bash
# App 1: hello v1
kubectl create deployment hello-v1 --image=hashicorp/http-echo -- /http-echo -text="Hello from v1"
kubectl expose deployment hello-v1 --port=5678 --name=hello-v1-svc

# App 2: hello v2
kubectl create deployment hello-v2 --image=hashicorp/http-echo -- /http-echo -text="Hello from v2"
kubectl expose deployment hello-v2 --port=5678 --name=hello-v2-svc

# App 3: world app
kubectl create deployment world-app --image=hashicorp/http-echo -- /http-echo -text="World App Here"
kubectl expose deployment world-app --port=5678 --name=world-app-svc

# Verify all are running
kubectl get pods
kubectl get svc
```

### Step 3: Create the Ingress Resource

```yaml
# ingress-demo.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: demo-ingress
  annotations:
    nginx.ingress.kubernetes.io/rewrite-target: /
spec:
  ingressClassName: nginx
  rules:

  # Rule 1: host=hello.local, path=/ → hello-v1
  - host: hello.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: hello-v1-svc
            port:
              number: 5678

      # path=/v2 → hello-v2
      - path: /v2
        pathType: Prefix
        backend:
          service:
            name: hello-v2-svc
            port:
              number: 5678

  # Rule 2: host=world.local, path=/ → world-app
  - host: world.local
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: world-app-svc
            port:
              number: 5678
```

```bash
kubectl apply -f ingress-demo.yaml

# Check ingress status
kubectl get ingress

# Expected (ADDRESS takes ~30 sec to show):
# NAME           CLASS   HOSTS                         ADDRESS        PORTS   AGE
# demo-ingress   nginx   hello.local,world.local       192.168.49.2   80      1m
```

### Step 4: Configure Local DNS (hosts file)

```bash
# Get minikube IP
MINIKUBE_IP=$(minikube ip)
echo "Minikube IP: $MINIKUBE_IP"

# Add to /etc/hosts (requires sudo)
echo "$MINIKUBE_IP hello.local" | sudo tee -a /etc/hosts
echo "$MINIKUBE_IP world.local" | sudo tee -a /etc/hosts

# Verify
cat /etc/hosts | grep local
```

### Step 5: Test the Routing

```bash
# Test hello.local → hello v1
curl http://hello.local
# Output: Hello from v1

# Test hello.local/v2 → hello v2
curl http://hello.local/v2
# Output: Hello from v2

# Test world.local → world app
curl http://world.local
# Output: World App Here

# Test unknown host → 404
curl http://unknown.local
# Output: 404 page not found
```

### Step 6: Inspect and Debug

```bash
# Describe ingress (shows rules, backend service health)
kubectl describe ingress demo-ingress

# Check nginx controller logs
kubectl logs -n ingress-nginx \
  -l app.kubernetes.io/component=controller \
  --tail=20

# Check ingress events
kubectl get events --field-selector involvedObject.name=demo-ingress

# Get ingress in YAML form
kubectl get ingress demo-ingress -o yaml
```

### Step 7: Cleanup

```bash
kubectl delete ingress demo-ingress
kubectl delete deployment hello-v1 hello-v2 world-app
kubectl delete svc hello-v1-svc hello-v2-svc world-app-svc

# Remove /etc/hosts entries
sudo sed -i '' '/hello.local/d' /etc/hosts
sudo sed -i '' '/world.local/d' /etc/hosts
```

---

## 9. AWS ALB Ingress Demo

This demo runs on **EKS** and creates an internet-facing ALB.

### Step 1: Deploy a Sample App

```yaml
# alb-demo-app.yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: game-2048
  namespace: default
spec:
  replicas: 2
  selector:
    matchLabels:
      app: game-2048
  template:
    metadata:
      labels:
        app: game-2048
    spec:
      containers:
      - name: game-2048
        image: public.ecr.aws/l6m2t8p7/docker-2048:latest
        ports:
        - containerPort: 80
---
apiVersion: v1
kind: Service
metadata:
  name: game-2048-svc
  namespace: default
spec:
  type: ClusterIP
  selector:
    app: game-2048
  ports:
  - port: 80
    targetPort: 80
```

```bash
kubectl apply -f alb-demo-app.yaml
kubectl get pods -l app=game-2048
kubectl get svc game-2048-svc
```

### Step 2: Create ALB Ingress

```yaml
# alb-ingress.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: game-2048-ingress
  namespace: default
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing      # public ALB
    alb.ingress.kubernetes.io/target-type: ip              # route directly to Pod IPs
    alb.ingress.kubernetes.io/healthcheck-path: /          # health check endpoint
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}]'
spec:
  rules:
  - http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: game-2048-svc
            port:
              number: 80
```

```bash
kubectl apply -f alb-ingress.yaml

# Watch for ALB to provision (takes 2-3 minutes)
kubectl get ingress game-2048-ingress -w

# Expected after provisioning:
# NAME                CLASS   HOSTS   ADDRESS                                            PORTS
# game-2048-ingress   alb     *       k8s-default-game2048-xxxxxxxx.us-east-1.elb.amazonaws.com   80

# Access the app
ALB_URL=$(kubectl get ingress game-2048-ingress -o jsonpath='{.status.loadBalancer.ingress[0].hostname}')
echo "App URL: http://$ALB_URL"
curl http://$ALB_URL
```

### Step 3: Verify in AWS Console

```bash
# Check ALB was created in AWS
aws elbv2 describe-load-balancers \
  --query "LoadBalancers[?contains(LoadBalancerName, 'k8s')].{Name:LoadBalancerName,DNS:DNSName,State:State.Code}" \
  --output table

# Check target group health
aws elbv2 describe-target-health \
  --target-group-arn $(aws elbv2 describe-target-groups \
    --query "TargetGroups[?contains(TargetGroupName, 'k8s')].TargetGroupArn" \
    --output text) \
  --query "TargetHealthDescriptions[*].{IP:Target.Id,Port:Target.Port,Health:TargetHealth.State}"
```

### Step 4: Add HTTPS with ACM Certificate

```yaml
# alb-ingress-tls.yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: game-2048-ingress
  namespace: default
  annotations:
    kubernetes.io/ingress.class: alb
    alb.ingress.kubernetes.io/scheme: internet-facing
    alb.ingress.kubernetes.io/target-type: ip
    alb.ingress.kubernetes.io/listen-ports: '[{"HTTP": 80}, {"HTTPS": 443}]'
    alb.ingress.kubernetes.io/ssl-redirect: "443"          # force HTTPS
    alb.ingress.kubernetes.io/certificate-arn: arn:aws:acm:us-east-1:123456789012:certificate/xxxxxxxx
spec:
  rules:
  - host: game.example.com                                  # your domain
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: game-2048-svc
            port:
              number: 80
```

```bash
kubectl apply -f alb-ingress-tls.yaml

# After applying, create a CNAME/A record in Route53 or your DNS
# pointing game.example.com → the ALB DNS name
```

### Step 5: Cleanup

```bash
# Delete ingress first (triggers ALB deletion in AWS)
kubectl delete ingress game-2048-ingress

# Verify ALB is deleted (takes ~1 min)
aws elbv2 describe-load-balancers \
  --query "LoadBalancers[?contains(LoadBalancerName, 'k8s')]"

# Then delete app
kubectl delete -f alb-demo-app.yaml
```

---

## 10. Ingress vs Service Comparison

| Feature | Service (NodePort/LB) | Ingress |
|---------|----------------------|---------|
| **Layer** | L4 (TCP/UDP) | L7 (HTTP/HTTPS) |
| **Routing** | By IP + port only | By host + path |
| **TLS termination** | ✗ No (on LB type only) | ✓ Yes |
| **One IP for many apps** | ✗ No (1 LB per service) | ✓ Yes |
| **Path-based routing** | ✗ No | ✓ Yes |
| **Redirects** | ✗ No | ✓ Yes (annotations) |
| **Rate limiting** | ✗ No | ✓ Yes (annotations) |
| **Requires controller** | ✗ No | ✓ Yes |
| **Works without HTTP** | ✓ Yes (any TCP) | ✗ No (HTTP/HTTPS only) |

### Traffic Flow Comparison

```
  Service LoadBalancer:
  User → Cloud LB → NodePort → ClusterIP → Pod

  Ingress:
  User → Cloud LB → Ingress Controller Pod → ClusterIP Service → Pod
  (controller makes routing decision based on Host/Path headers)
```

---

## 11. Common Interview Questions

**Q: What is the difference between a Service and an Ingress?**
> A **Service** operates at Layer 4 (TCP/UDP) and provides a stable endpoint to reach Pods — it has no concept of HTTP hosts or paths. An **Ingress** operates at Layer 7 (HTTP/HTTPS) and routes traffic based on hostname and URL path. Ingress routes to backend Services, not directly to Pods. You need both: Ingress sits in front of Services.

---

**Q: What is an Ingress Controller and why is it needed?**
> An **Ingress Controller** is a Pod (usually running nginx, traefik, or a cloud LB like ALB) that watches for Ingress resource changes and actually implements the routing rules. The Ingress resource itself is just a config object — it does nothing without a controller watching it. You must install a controller separately (it's not built into Kubernetes core).

---

**Q: What is IngressClass and why was it introduced?**
> **IngressClass** specifies which Ingress Controller should handle an Ingress resource (via `spec.ingressClassName`). It was introduced in Kubernetes 1.18 to cleanly replace the older `kubernetes.io/ingress.class` annotation and support multiple controllers in the same cluster. For example, you might have both an nginx controller and an ALB controller and assign different Ingresses to each.

---

**Q: Can you have multiple Ingress Controllers in one cluster?**
> Yes. You install multiple controllers (e.g., nginx for internal traffic, ALB for external traffic) and use **IngressClass** to direct each Ingress resource to the right controller. Each controller watches only the Ingress resources that reference its IngressClass.

---

**Q: What happens if an Ingress rule has no matching host and no defaultBackend?**
> The Ingress Controller returns the controller's own default 404/503 response. It's best practice to always define a `defaultBackend` to serve a custom error page.

---

**Q: How does path-based routing work in nginx Ingress?**
> The nginx controller translates Ingress rules into nginx `location` blocks. When a request arrives, nginx checks the `Host` header to select the right server block, then matches the URL path using the rules in order of specificity (Exact before Prefix, longer Prefix before shorter). It then proxies the request to the backend Service's ClusterIP.

---

**Q: What is the difference between `pathType: Prefix` and `pathType: Exact`?**
> **Exact** matches only the exact URL path — `/api` matches `/api` but not `/api/v1`. **Prefix** matches the path and anything below it — `/api` matches `/api`, `/api/v1`, `/api/users/123`. When both Exact and Prefix rules could match a request, Exact takes priority.

---

**Q: What are Ingress annotations?**
> Annotations are key-value metadata on the Ingress object that pass controller-specific configuration — things that go beyond what the standard Ingress spec supports, like rate limiting, CORS headers, SSL redirects, proxy timeouts, and sticky sessions. Each controller has its own annotation prefix (e.g., `nginx.ingress.kubernetes.io/` for nginx, `alb.ingress.kubernetes.io/` for AWS ALB).

---

**Q: How does TLS termination work in Ingress?**
> The Ingress Controller reads the TLS Secret referenced in `spec.tls[].secretName` (which contains `tls.crt` and `tls.key`). It presents the certificate to clients, decrypts the HTTPS traffic, and forwards plain HTTP to the backend Service. This means Pods only ever handle plain HTTP internally.

---

**Q: What is the difference between the AWS ALB Controller and nginx Ingress?**
> **nginx Ingress** runs a Pod inside the cluster that proxies traffic — all traffic goes through the nginx Pod. **AWS ALB Controller** provisions a native AWS Application Load Balancer outside the cluster and configures it to route traffic directly to Pod IPs (with `target-type: ip`) or Node ports. ALB is better integrated with AWS features (WAF, ACM, Shield, CloudWatch) but only works on AWS.

---

## 12. Exam Practice Questions

### Section A: Concept Questions

**1.** You create an Ingress resource but traffic is not routing. The `kubectl get ingress` shows no ADDRESS. What is the most likely cause?
> **No Ingress Controller is installed** in the cluster. An Ingress resource without a controller is just configuration — nothing reads or implements it. Install a controller (nginx, traefik, etc.).

---

**2.** What is the valid `pathType` to match `/app` and also `/app/dashboard` but NOT `/application`?
> **`Prefix`** with path `/app/`. Using just `/app` with Prefix would also match `/application` in some controllers. Use `/app/` to anchor to the path segment boundary.

---

**3.** You have two Ingress resources both with `ingressClassName: nginx`. Can they conflict?
> Yes, if they define rules for the **same host and overlapping paths**. The nginx controller merges all Ingress resources into a single nginx config and may produce unexpected routing. Use different namespaces or non-overlapping paths to avoid conflicts.

---

**4.** What Kubernetes resource stores the TLS certificate used by Ingress?
> A **Secret** of type `kubernetes.io/tls` containing `tls.crt` (certificate) and `tls.key` (private key). Created with `kubectl create secret tls <name> --cert=tls.crt --key=tls.key`.

---

**5.** On a bare metal cluster, after installing nginx Ingress, the Service type is `NodePort`. How do external users access the Ingress?
> Via `http://<any-node-IP>:<nodePort>`. The nginx controller's Service exposes port 80 on a NodePort (e.g., 30080). Users must know a Node's external IP and the NodePort. For a proper external IP, add **MetalLB** to give the Service a real LoadBalancer IP.

---

### Section B: YAML Writing Tasks

**Task 1:** Write an Ingress named `shop-ingress` with nginx class that routes:
- `shop.example.com/` → `frontend-svc:80`
- `shop.example.com/api` → `api-svc:8080`

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: shop-ingress
spec:
  ingressClassName: nginx
  rules:
  - host: shop.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-svc
            port:
              number: 8080
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-svc
            port:
              number: 80
```

---

**Task 2:** Add TLS to the above Ingress using a secret named `shop-tls`.

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: shop-ingress
  annotations:
    nginx.ingress.kubernetes.io/ssl-redirect: "true"
spec:
  ingressClassName: nginx
  tls:
  - hosts:
    - shop.example.com
    secretName: shop-tls
  rules:
  - host: shop.example.com
    http:
      paths:
      - path: /api
        pathType: Prefix
        backend:
          service:
            name: api-svc
            port:
              number: 8080
      - path: /
        pathType: Prefix
        backend:
          service:
            name: frontend-svc
            port:
              number: 80
```

---

**Task 3:** Create a TLS secret from certificate files `app.crt` and `app.key`.

```bash
kubectl create secret tls shop-tls \
  --cert=app.crt \
  --key=app.key
```

---

### Section C: Troubleshooting Scenarios

**Scenario 1:** `curl http://api.example.com` returns a 404 from nginx, not your app. What do you check?
> 1. `kubectl describe ingress` — verify host and path rules are correct
> 2. `kubectl get svc api-service` — confirm Service name and port match Ingress backend
> 3. `kubectl get endpoints api-service` — ensure Service has healthy Pod endpoints
> 4. Check `Host` header: nginx matches the exact string, including case and trailing dots
> 5. Check pathType — `Exact` vs `Prefix` may be the mismatch

---

**Scenario 2:** On EKS, your ALB Ingress stays in `<pending>` ADDRESS state after 5 minutes. What do you check?
> 1. `kubectl describe ingress` — look at Events section for error messages
> 2. ALB controller logs: `kubectl logs -n kube-system -l app.kubernetes.io/name=aws-load-balancer-controller`
> 3. IAM permissions — is the controller's ServiceAccount annotated with the correct IAM role ARN?
> 4. Subnet tags — public subnets need `kubernetes.io/role/elb=1`
> 5. Security groups — does the ALB security group allow inbound 80/443?

---

### Section D: Quick-Fire Commands

```bash
# List all ingress resources
kubectl get ingress -A

# Describe ingress (shows rules, backend health, events)
kubectl describe ingress <name>

# Get ingress with backend addresses
kubectl get ingress -o wide

# Check nginx ingress controller logs
kubectl logs -n ingress-nginx -l app.kubernetes.io/component=controller --tail=30

# Create TLS secret
kubectl create secret tls my-tls --cert=tls.crt --key=tls.key

# Generate Ingress YAML without applying
kubectl create ingress demo --rule="example.com/=svc:80" --dry-run=client -o yaml

# Port-forward ingress controller for local testing
kubectl port-forward -n ingress-nginx svc/ingress-nginx-controller 8080:80

# Test via curl with Host header (without DNS)
curl -H "Host: example.com" http://localhost:8080/

# Delete ingress
kubectl delete ingress my-ingress
```

---

> **CKA Exam Tips Summary**:
> - `kubectl create ingress` with `--rule` flag generates YAML fast — practice it
> - Ingress without a controller = nothing works — always install a controller first
> - Check `kubectl describe ingress` events when routing fails
> - `spec.ingressClassName` (v1.18+) replaces the old annotation — use the spec field
> - TLS Secret must be in the **same namespace** as the Ingress
> - Remember: Ingress routes to **Services**, not Pods directly
> - On minikube: `minikube addons enable ingress` is all you need for the exam lab

---

*Notes by ITkannadigaru | CKA 2026 Certification*

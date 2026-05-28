# TLS & SSL Management in Kubernetes — Complete Guide

> TLS is the backbone of Kubernetes security. Every component in the cluster talks to every other component over encrypted, certificate-verified connections.

---

## Table of Contents

1. [What is TLS/SSL?](#1-what-is-tlsssl)
2. [How TLS Handshake Works](#2-how-tls-handshake-works)
3. [Why Kubernetes Uses TLS Everywhere](#3-why-kubernetes-uses-tls-everywhere)
4. [Kubernetes PKI — The Certificate Authority](#4-kubernetes-pki--the-certificate-authority)
5. [Certificate Components in a Cluster](#5-certificate-components-in-a-cluster)
6. [How Each Component Uses TLS](#6-how-each-component-uses-tls)
7. [Certificate File Locations (kubeadm)](#7-certificate-file-locations-kubeadm)
8. [Generating and Inspecting Certificates](#8-generating-and-inspecting-certificates)
9. [TLS in Pods — Secrets for TLS](#9-tls-in-pods--secrets-for-tls)
10. [Certificate Signing Requests (CSR) API](#10-certificate-signing-requests-csr-api)
11. [Certificate Rotation](#11-certificate-rotation)
12. [Common Interview Questions](#12-common-interview-questions)
13. [Exam Practice Questions](#13-exam-practice-questions)

---

## 1. What is TLS/SSL?

**SSL (Secure Sockets Layer)** is the old protocol — deprecated and insecure.  
**TLS (Transport Layer Security)** is its modern replacement. We still say "SSL" casually but always use TLS.

TLS provides three guarantees:

```
  ┌─────────────────────────────────────────────────────────────┐
  │                     TLS Guarantees                          │
  ├─────────────────┬───────────────────────────────────────────┤
  │  Encryption     │  Data in transit is unreadable to others  │
  │  Authentication │  You're talking to who you think you are  │
  │  Integrity      │  Data was not tampered with in transit    │
  └─────────────────┴───────────────────────────────────────────┘
```

### Key Terminology

| Term | Meaning |
|------|---------|
| **Certificate (cert)** | A public key + identity info, signed by a CA |
| **Private Key** | Secret key, never shared, used to prove identity |
| **CA (Certificate Authority)** | Trusted entity that signs and validates certs |
| **CSR (Certificate Signing Request)** | Request to a CA to issue a cert |
| **PKI (Public Key Infrastructure)** | The full system of certs, keys, and CAs |
| **x509** | Standard format for certificates |
| **PEM** | Text encoding for certs (base64, starts with `-----BEGIN`) |

---

## 2. How TLS Handshake Works

Before any encrypted data is sent, both parties run a **TLS handshake** to agree on encryption keys.

```
  Client (kubectl)                      Server (API Server)
       │                                       │
       │──── 1. ClientHello ──────────────────>│
       │     (TLS version, cipher suites)      │
       │                                       │
       │<─── 2. ServerHello ──────────────────│
       │     (chosen cipher, server cert)      │
       │                                       │
       │     3. Client validates server cert   │
       │        against its trusted CA         │
       │                                       │
       │──── 4. ClientKeyExchange ────────────>│
       │     (encrypted pre-master secret)     │
       │                                       │
       │     5. Both derive session keys       │
       │        (symmetric encryption begins)  │
       │                                       │
       │<═══ 6. Encrypted communication ══════>│
```

### Mutual TLS (mTLS)

Standard TLS only verifies the **server** identity. Kubernetes components use **mutual TLS (mTLS)** where **both sides** present certificates.

```
  kubectl                              API Server
     │                                     │
     │──── presents client cert ──────────>│  "Who are you?"
     │<─── presents server cert ──────────│  "Who are you?"
     │                                     │
     │     Both validate each other        │
     │     against the cluster CA          │
     │                                     │
     │<═══════ Encrypted + Authenticated ══>│
```

> This is how Kubernetes components authenticate each other — not passwords, but certificates.

---

## 3. Why Kubernetes Uses TLS Everywhere

Without TLS, any process on the network could:
- Read secrets being transmitted
- Impersonate the API server and inject malicious responses
- Intercept kubeconfig credentials

```
  WITHOUT TLS (dangerous):
  
  etcd ←─── plaintext ───→ API Server ←─── plaintext ───→ kubectl
  
  Anyone who can sniff network traffic sees everything.


  WITH TLS (Kubernetes default):
  
  etcd ←═══ encrypted + verified ═══→ API Server ←═══ encrypted + verified ═══→ kubectl
  
  Even on a compromised network, data is safe.
```

---

## 4. Kubernetes PKI — The Certificate Authority

Kubernetes creates its own **internal CA** during cluster setup (usually by kubeadm). This CA is the **root of trust** for the entire cluster.

```
                  ┌─────────────────────────────────┐
                  │      Kubernetes CA               │
                  │  /etc/kubernetes/pki/ca.crt      │
                  │  /etc/kubernetes/pki/ca.key      │
                  └──────────────┬──────────────────┘
                                 │ signs
              ┌──────────────────┼──────────────────┐
              ↓                  ↓                   ↓
     API Server cert       etcd cert          kubelet cert
     (apiserver.crt)      (etcd/ca.crt)    (client cert)
```

### Two CAs in a Cluster

kubeadm actually creates **two separate CAs**:

| CA | Path | Purpose |
|----|------|---------|
| **Kubernetes CA** | `/etc/kubernetes/pki/ca.crt` | Signs API server, controller-manager, scheduler, kubelet |
| **etcd CA** | `/etc/kubernetes/pki/etcd/ca.crt` | Signs only etcd-related certs |

This separation ensures that a compromised etcd cert cannot be used against the API server.

---

## 5. Certificate Components in a Cluster

```
  SERVERS (present certs to prove their identity):
  ┌──────────────────────────────────────────────────────────────┐
  │  Component            Server Cert           Server Key       │
  ├──────────────────────────────────────────────────────────────┤
  │  kube-apiserver       apiserver.crt         apiserver.key    │
  │  etcd                 etcd/server.crt       etcd/server.key  │
  │  kubelet              kubelet.crt           kubelet.key      │
  └──────────────────────────────────────────────────────────────┘

  CLIENTS (present certs to prove who they are to the API server):
  ┌──────────────────────────────────────────────────────────────┐
  │  Component            Client Cert           Purpose          │
  ├──────────────────────────────────────────────────────────────┤
  │  kubectl (admin)      admin.crt             Human admin      │
  │  kube-scheduler       scheduler.crt         Scheduler auth   │
  │  controller-manager   controller-manager.crt CM auth         │
  │  kubelet (each node)  kubelet-client.crt    Node auth        │
  │  API server → etcd    apiserver-etcd-client.crt API→etcd     │
  │  API server → kubelet apiserver-kubelet-client.crt API→node  │
  └──────────────────────────────────────────────────────────────┘
```

---

## 6. How Each Component Uses TLS

### API Server

The API server is the most complex — it acts as both a **server** and a **client**.

```
  As a server (receives connections from):
  ├── kubectl          → validates with apiserver.crt
  ├── kubelet          → validates with apiserver.crt
  └── kube-proxy       → validates with apiserver.crt

  As a client (initiates connections to):
  ├── etcd             → uses apiserver-etcd-client.crt
  └── kubelet          → uses apiserver-kubelet-client.crt
```

API Server flags that control TLS:
```bash
kube-apiserver \
  --tls-cert-file=/etc/kubernetes/pki/apiserver.crt \
  --tls-private-key-file=/etc/kubernetes/pki/apiserver.key \
  --client-ca-file=/etc/kubernetes/pki/ca.crt \
  --etcd-cafile=/etc/kubernetes/pki/etcd/ca.crt \
  --etcd-certfile=/etc/kubernetes/pki/apiserver-etcd-client.crt \
  --etcd-keyfile=/etc/kubernetes/pki/apiserver-etcd-client.key \
  --kubelet-client-certificate=/etc/kubernetes/pki/apiserver-kubelet-client.crt \
  --kubelet-client-key=/etc/kubernetes/pki/apiserver-kubelet-client.key
```

### etcd

```bash
etcd \
  --cert-file=/etc/kubernetes/pki/etcd/server.crt \
  --key-file=/etc/kubernetes/pki/etcd/server.key \
  --trusted-ca-file=/etc/kubernetes/pki/etcd/ca.crt \
  --peer-cert-file=/etc/kubernetes/pki/etcd/peer.crt \
  --peer-key-file=/etc/kubernetes/pki/etcd/peer.key \
  --peer-trusted-ca-file=/etc/kubernetes/pki/etcd/ca.crt
```

> `peer-*` certs are used for etcd-to-etcd communication in HA clusters.

### kubelet

Each node's kubelet serves an HTTPS API (port 10250) that the API server calls to:
- Get logs
- Run `exec`
- Get metrics

```bash
kubelet \
  --tls-cert-file=/var/lib/kubelet/pki/kubelet.crt \
  --tls-private-key-file=/var/lib/kubelet/pki/kubelet.key \
  --client-ca-file=/etc/kubernetes/pki/ca.crt
```

---

## 7. Certificate File Locations (kubeadm)

```
/etc/kubernetes/pki/
├── ca.crt                          ← Cluster CA cert (public)
├── ca.key                          ← Cluster CA key (KEEP SECRET)
├── apiserver.crt                   ← API server TLS cert
├── apiserver.key                   ← API server TLS key
├── apiserver-etcd-client.crt       ← API server → etcd client cert
├── apiserver-etcd-client.key
├── apiserver-kubelet-client.crt    ← API server → kubelet client cert
├── apiserver-kubelet-client.key
├── front-proxy-ca.crt              ← Front proxy CA
├── front-proxy-ca.key
├── front-proxy-client.crt          ← Front proxy client cert
├── front-proxy-client.key
├── sa.pub                          ← Service account public key
├── sa.key                          ← Service account private key
└── etcd/
    ├── ca.crt                      ← etcd CA cert
    ├── ca.key                      ← etcd CA key
    ├── server.crt                  ← etcd server cert
    ├── server.key
    ├── peer.crt                    ← etcd peer cert (HA clusters)
    ├── peer.key
    ├── healthcheck-client.crt      ← liveness probe client
    └── healthcheck-client.key
```

---

## 8. Generating and Inspecting Certificates

### Inspect a Certificate

```bash
# View certificate details (expiry, subject, SANs)
openssl x509 -in /etc/kubernetes/pki/apiserver.crt -text -noout

# Key fields to check:
# Subject: CN = kube-apiserver
# Not After: (expiry date)
# X509v3 Subject Alternative Name: DNS:kubernetes, DNS:kubernetes.default, IP:10.96.0.1
```

### Check Certificate Expiry

```bash
# Check all kubeadm certs at once
kubeadm certs check-expiration

# Output example:
# CERTIFICATE                EXPIRES                  RESIDUAL TIME
# admin.conf                 May 01, 2026 10:00 UTC   364d
# apiserver                  May 01, 2026 10:00 UTC   364d
# apiserver-etcd-client      May 01, 2026 10:00 UTC   364d
```

### Manually Create a Certificate (for a new user)

```bash
# Step 1: Generate private key
openssl genrsa -out john.key 2048

# Step 2: Create CSR (Certificate Signing Request)
openssl req -new -key john.key -subj "/CN=john/O=dev-team" -out john.csr

# Step 3: Sign with cluster CA
openssl x509 -req \
  -in john.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial \
  -out john.crt \
  -days 365

# Result: john.crt (certificate) + john.key (private key)
# Use these in kubeconfig to authenticate as "john"
```

### Renew All Certificates

```bash
# Renew all kubeadm-managed certs (extend by 1 year)
kubeadm certs renew all

# Renew specific cert
kubeadm certs renew apiserver
```

> After renewing certs, restart the control plane components:
> ```bash
> # On control plane node
> crictl pods | grep kube-apiserver   # find pod id
> crictl stopp <pod-id>               # stop it (kubelet will recreate)
> ```

---

## 9. TLS in Pods — Secrets for TLS

When your application inside a Pod needs TLS (e.g., an nginx HTTPS server), store the cert and key in a **TLS Secret**.

### Create a TLS Secret

```bash
# From existing cert files
kubectl create secret tls my-tls-secret \
  --cert=tls.crt \
  --key=tls.key

# The secret stores:
# tls.crt → the certificate
# tls.key → the private key
```

### Use TLS Secret in a Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: nginx-tls
spec:
  containers:
  - name: nginx
    image: nginx
    ports:
    - containerPort: 443
    volumeMounts:
    - name: tls-certs
      mountPath: /etc/nginx/ssl
      readOnly: true
  volumes:
  - name: tls-certs
    secret:
      secretName: my-tls-secret
```

```yaml
# nginx.conf snippet
server {
    listen 443 ssl;
    ssl_certificate     /etc/nginx/ssl/tls.crt;
    ssl_certificate_key /etc/nginx/ssl/tls.key;
}
```

### TLS in Ingress

```yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: my-ingress
spec:
  tls:
  - hosts:
    - myapp.example.com
    secretName: my-tls-secret     # ← TLS Secret reference
  rules:
  - host: myapp.example.com
    http:
      paths:
      - path: /
        pathType: Prefix
        backend:
          service:
            name: my-service
            port:
              number: 80
```

---

## 10. Certificate Signing Requests (CSR) API

Instead of manually running `openssl x509 -req ...`, Kubernetes has a built-in **CSR API** for signing certificates.

### Workflow

```
  Developer/Admin                Kubernetes CA
       │                               │
       │─── Create CSR object ────────>│
       │    (contains base64 CSR)      │
       │                               │
       │                     Admin approves CSR
       │                               │
       │<── Certificate issued ────────│
```

### Step 1: Generate Key and CSR

```bash
openssl genrsa -out jane.key 2048
openssl req -new -key jane.key -subj "/CN=jane/O=developers" -out jane.csr
```

### Step 2: Create CSR Kubernetes Object

```yaml
apiVersion: certificates.k8s.io/v1
kind: CertificateSigningRequest
metadata:
  name: jane-csr
spec:
  request: $(cat jane.csr | base64 | tr -d '\n')
  signerName: kubernetes.io/kube-apiserver-client
  expirationSeconds: 86400   # 1 day
  usages:
  - client auth
```

```bash
kubectl apply -f jane-csr.yaml
```

### Step 3: Approve the CSR

```bash
# View pending CSRs
kubectl get csr

# NAME       AGE   SIGNERNAME                            REQUESTOR   CONDITION
# jane-csr   10s   kubernetes.io/kube-apiserver-client   admin       Pending

# Approve
kubectl certificate approve jane-csr

# Or deny
kubectl certificate deny jane-csr
```

### Step 4: Retrieve the Certificate

```bash
kubectl get csr jane-csr -o jsonpath='{.status.certificate}' | base64 -d > jane.crt
```

> Now use `jane.crt` + `jane.key` in a kubeconfig file for Jane to authenticate.

---

## 11. Certificate Rotation

### Automatic Rotation (kubelet)

Kubelets can be configured to **automatically rotate** their client certificates before expiry:

```bash
# kubelet config
rotateCertificates: true
```

### Manual Rotation with kubeadm

```bash
# Renew all certs (run on control plane node)
kubeadm certs renew all

# Check new expiry
kubeadm certs check-expiration

# Restart control plane static pods to pick up new certs
mv /etc/kubernetes/manifests/kube-apiserver.yaml /tmp/
mv /tmp/kube-apiserver.yaml /etc/kubernetes/manifests/
# (or just reboot the control plane node)
```

### Important Rotation Facts

```
  Before rotation:
  cert expires in 30 days → applications still work

  After rotation without restart:
  new cert is on disk but old cert is still in memory → no effect yet

  After restart:
  new cert is loaded → rotation complete
```

---

## 12. Common Interview Questions

**Q: What is the difference between a server certificate and a client certificate?**
> A server cert proves the server's identity to the client. A client cert proves the client's identity to the server. Kubernetes uses both — this is called mutual TLS (mTLS).

**Q: Where does the kube-apiserver store its TLS certificates?**
> `/etc/kubernetes/pki/apiserver.crt` (cert) and `/etc/kubernetes/pki/apiserver.key` (key).

**Q: What is the Kubernetes CA and why is it important?**
> The CA (Certificate Authority) is the root of trust for the cluster. All component certificates are signed by it. Located at `/etc/kubernetes/pki/ca.crt`. If the CA key is compromised, the entire cluster's security is broken.

**Q: How do you check when cluster certificates expire?**
> `kubeadm certs check-expiration` — shows all cert expiry dates and residual time.

**Q: Why does Kubernetes use a separate CA for etcd?**
> Defense in depth — if an etcd cert is compromised, it can't be used to authenticate against the API server since they have different CAs.

**Q: What happens if the API server's cert expires?**
> `kubectl` commands fail with TLS handshake errors. You must renew the cert (`kubeadm certs renew apiserver`) and restart the API server.

---

## 13. Exam Practice Questions

```
1. View the expiry date of the API server certificate.
   Answer: openssl x509 -in /etc/kubernetes/pki/apiserver.crt -text -noout | grep "Not After"

2. Create a TLS secret called "web-tls" using tls.crt and tls.key files.
   Answer: kubectl create secret tls web-tls --cert=tls.crt --key=tls.key

3. Approve a pending CSR named "dev-user".
   Answer: kubectl certificate approve dev-user

4. Renew all cluster certificates.
   Answer: kubeadm certs renew all

5. What CN (Common Name) does the kube-scheduler use for its client certificate?
   Answer: system:kube-scheduler

6. List all pending certificate signing requests.
   Answer: kubectl get csr

7. Retrieve the signed certificate from CSR "new-user" and save to new-user.crt.
   Answer: kubectl get csr new-user -o jsonpath='{.status.certificate}' | base64 -d > new-user.crt
```

---

*Next: [02-authentication-and-authorization.md](./02-authentication-and-authorization.md) — How Kubernetes decides who you are and what you can do*

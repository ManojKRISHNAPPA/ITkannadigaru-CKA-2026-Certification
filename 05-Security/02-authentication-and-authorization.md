# Authentication & Authorization in Kubernetes — Complete Guide

> Authentication answers "WHO are you?" — Authorization answers "WHAT can you do?"  
> Kubernetes handles both as separate, pluggable layers.

---

## Table of Contents

1. [The Request Lifecycle](#1-the-request-lifecycle)
2. [Authentication — Who Are You?](#2-authentication--who-are-you)
   - [2.1 X.509 Client Certificates](#21-x509-client-certificates)
   - [2.2 Static Token File](#22-static-token-file)
   - [2.3 Bootstrap Tokens](#23-bootstrap-tokens)
   - [2.4 Service Account Tokens](#24-service-account-tokens)
   - [2.5 OpenID Connect (OIDC)](#25-openid-connect-oidc)
   - [2.6 Webhook Token Authentication](#26-webhook-token-authentication)
   - [2.7 Anonymous Requests](#27-anonymous-requests)
3. [User Identities in Kubernetes](#3-user-identities-in-kubernetes)
4. [Authorization — What Can You Do?](#4-authorization--what-can-you-do)
   - [4.1 RBAC (Role-Based Access Control)](#41-rbac-role-based-access-control)
   - [4.2 ABAC (Attribute-Based Access Control)](#42-abac-attribute-based-access-control)
   - [4.3 Node Authorization](#43-node-authorization)
   - [4.4 Webhook Authorization](#44-webhook-authorization)
5. [Admission Controllers](#5-admission-controllers)
6. [API Server Security Flags](#6-api-server-security-flags)
7. [Checking Your Permissions](#7-checking-your-permissions)
8. [Common Interview Questions](#8-common-interview-questions)
9. [Exam Practice Questions](#9-exam-practice-questions)

---

## 1. The Request Lifecycle

Every request to the Kubernetes API server goes through three sequential gates:

```
  kubectl apply -f pod.yaml
          │
          ▼
  ┌───────────────────────────────────────────────────────────────┐
  │                    kube-apiserver                             │
  │                                                               │
  │  ┌─────────────────┐                                          │
  │  │ 1. AUTHN        │  Who are you?                            │
  │  │  (Authentication)│  Validates identity via cert/token      │
  │  └────────┬────────┘                                          │
  │           │ identity confirmed (username, groups)             │
  │  ┌────────▼────────┐                                          │
  │  │ 2. AUTHZ        │  What are you allowed to do?             │
  │  │  (Authorization) │  Checks RBAC / ABAC / Webhook           │
  │  └────────┬────────┘                                          │
  │           │ action permitted                                  │
  │  ┌────────▼────────┐                                          │
  │  │ 3. ADMISSION    │  Should this specific request be allowed?│
  │  │  Controllers    │  Validates + mutates (e.g., quotas,      │
  │  │                 │  security policies, defaults)            │
  │  └────────┬────────┘                                          │
  │           │ request passes all gates                          │
  └───────────┼───────────────────────────────────────────────────┘
              │
              ▼
          etcd (state stored)
```

> A request is **rejected at the first failed gate** — if authentication fails, authorization is never checked.

---

## 2. Authentication — Who Are You?

Kubernetes does **not** have a built-in user database. Users are validated externally through pluggable authenticator modules. Multiple authenticators can be enabled simultaneously — the first one to successfully identify the requester wins.

```
  Request arrives at API server
          │
          ▼
  ┌──────────────────┐
  │ Try authenticator│──► X.509 Cert?      ──► Authenticated ✓
  │ chain in order   │──► Bearer Token?    ──► Check token source
  │                  │──► OIDC Token?      ──► Check OIDC provider
  │                  │──► Webhook?         ──► Ask external system
  └──────────────────┘
          │ (all failed)
          ▼
     Anonymous (if enabled) or 401 Unauthorized
```

---

### 2.1 X.509 Client Certificates

The most common method for **human admins** and **cluster components**.

**How it works:**
1. Client presents a TLS client certificate
2. API server verifies the cert was signed by the cluster CA (`--client-ca-file`)
3. The cert's `CN` (Common Name) becomes the **username**
4. The cert's `O` (Organization) fields become **groups**

```
  Certificate Subject: /CN=john/O=developers/O=devops-team
                               │              │        │
                        username: "john"  group: "developers"  group: "devops-team"
```

**Create a user with client cert:**
```bash
# Generate key + CSR
openssl genrsa -out john.key 2048
openssl req -new -key john.key -subj "/CN=john/O=developers" -out john.csr

# Sign with cluster CA
openssl x509 -req \
  -in john.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial -out john.crt -days 365

# Add to kubeconfig
kubectl config set-credentials john \
  --client-certificate=john.crt \
  --client-key=john.key
```

> **Limitation**: There is no way to "revoke" a certificate before it expires. If a user's cert is compromised, you must rotate the entire cluster CA.

---

### 2.2 Static Token File

A CSV file passed to the API server at startup. Simple but inflexible — requires API server restart to change.

```
# /etc/kubernetes/tokens.csv format:
token,username,uid,group1[,group2,...]

example:
abc123secrettoken,jane,u-0002,developers
xyz789admintoken,admin,u-0001,system:masters
```

```bash
# API server flag
kube-apiserver --token-auth-file=/etc/kubernetes/tokens.csv
```

```bash
# Use token in kubectl
kubectl get pods --token=abc123secrettoken

# Or in kubeconfig:
users:
- name: jane
  user:
    token: abc123secrettoken
```

> **Avoid in production** — tokens are stored in plaintext, never expire, and require restart to revoke.

---

### 2.3 Bootstrap Tokens

Special short-lived tokens used during cluster bootstrapping (when kubelets join the cluster). Format: `[a-z0-9]{6}.[a-z0-9]{16}`

```bash
# Create a bootstrap token
kubeadm token create

# Output: dvc47v.zz4p3g4f3gkx09gw

# List active tokens
kubeadm token list

# Use it to join a node
kubeadm join <api-server>:6443 \
  --token dvc47v.zz4p3g4f3gkx09gw \
  --discovery-token-ca-cert-hash sha256:<hash>
```

Bootstrap tokens are stored as Secrets in the `kube-system` namespace and automatically deleted when expired.

---

### 2.4 Service Account Tokens

Automatically created for Pods. A JWT token is mounted into Pods and used to authenticate against the API server.

```
  Pod starts
     │
     ▼
  kubelet mounts ServiceAccount token into Pod at:
  /var/run/secrets/kubernetes.io/serviceaccount/token

  Pod makes API request with this token in:
  Authorization: Bearer <token>

  API server validates JWT signature using sa.pub key
  → identifies: serviceaccount name + namespace
```

```bash
# Read the token from inside a Pod
cat /var/run/secrets/kubernetes.io/serviceaccount/token

# Use it to call the API from inside a Pod
TOKEN=$(cat /var/run/secrets/kubernetes.io/serviceaccount/token)
curl -H "Authorization: Bearer $TOKEN" \
     --cacert /var/run/secrets/kubernetes.io/serviceaccount/ca.crt \
     https://kubernetes.default.svc/api/v1/namespaces/default/pods
```

> Modern Kubernetes (v1.21+) uses **bound service account tokens** — shorter-lived, audience-restricted JWTs.

---

### 2.5 OpenID Connect (OIDC)

Integrate Kubernetes with external identity providers: **Google**, **Azure AD**, **Okta**, **Dex**, **Keycloak**.

```
  User → logs into OIDC Provider (e.g., Google)
              │
              │ gets id_token (JWT)
              │
  User → sends id_token to kubectl
              │
  kubectl → sends id_token to API server in Authorization header
              │
  API server → validates token with OIDC provider's public key
              │
        extracts username and groups from JWT claims
```

**API server flags:**
```bash
kube-apiserver \
  --oidc-issuer-url=https://accounts.google.com \
  --oidc-client-id=kubernetes \
  --oidc-username-claim=email \
  --oidc-groups-claim=groups
```

**kubeconfig with OIDC:**
```yaml
users:
- name: user@example.com
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: kubectl
      args:
      - oidc-login
      - get-token
      - --oidc-issuer-url=https://accounts.google.com
      - --oidc-client-id=kubernetes
```

---

### 2.6 Webhook Token Authentication

Outsource authentication to an **external service**. The API server sends a `TokenReview` request to your webhook; the webhook replies with the identity.

```
  kubectl (with token)
          │
          ▼
  API Server → POST TokenReview to your webhook
                    │
                    ▼
              Your Auth Service
              (checks LDAP, DB, etc.)
                    │
                    ▼
         Returns: authenticated=true, username="alice", groups=["devs"]
                    │
                    ▼
  API Server accepts the identity
```

```bash
# API server flag
kube-apiserver --authentication-token-webhook-config-file=/etc/kubernetes/webhook-authn.yaml
```

---

### 2.7 Anonymous Requests

Requests that fail all authenticators can optionally be treated as anonymous (`system:anonymous` user, `system:unauthenticated` group).

```bash
# Enable anonymous auth (default: true)
kube-apiserver --anonymous-auth=true

# Disable for stricter security
kube-apiserver --anonymous-auth=false
```

> Anonymous auth is required for kubelet and liveness probe healthchecks. Disabling it can break cluster functionality.

---

## 3. User Identities in Kubernetes

After authentication, every request has an **identity** consisting of:

| Field | Description | Example |
|-------|-------------|---------|
| **Username** | String identifier | `john`, `system:kube-scheduler` |
| **UID** | Unique identifier | `uid:abc123` |
| **Groups** | Set of group names | `["developers", "system:masters"]` |
| **Extra** | Additional attributes | key-value pairs for webhooks |

### Special System Users and Groups

```
  system:masters        → members get cluster-admin rights (bound to cluster-admin ClusterRole)
  system:authenticated  → all authenticated users belong to this group
  system:unauthenticated → unauthenticated (anonymous) requests

  system:kube-scheduler    → scheduler's identity
  system:kube-controller-manager → controller manager's identity
  system:nodes             → group for all kubelets (node bootstrapping)
  system:node:<nodeName>   → specific kubelet identity
```

> **Critical**: Any user in the `system:masters` group has **unrestricted cluster-admin access** — RBAC cannot deny them.

---

## 4. Authorization — What Can You Do?

After authentication, Kubernetes checks if the authenticated identity is **permitted** to perform the requested action.

```
  Authenticated identity: username=john, groups=[developers]
  Requested action:       GET pods in namespace=production
          │
          ▼
  ┌─────────────────────────────────────────────────────┐
  │              Authorization Modules                   │
  │                                                     │
  │  1. RBAC    → check Role/ClusterRole bindings       │
  │  2. Node    → check if kubelet, grant node access   │
  │  3. ABAC    → check attribute policy file           │
  │  4. Webhook → ask external service                  │
  │                                                     │
  │  First module to ALLOW → request proceeds           │
  │  All modules DENY      → 403 Forbidden              │
  └─────────────────────────────────────────────────────┘
```

### Authorization Mode Configuration

```bash
kube-apiserver \
  --authorization-mode=Node,RBAC,Webhook
  # Order matters: Node first for kubelet efficiency
```

Common combinations:
- `--authorization-mode=Node,RBAC` — standard production setup
- `--authorization-mode=AlwaysAllow` — insecure, for testing only
- `--authorization-mode=AlwaysDeny` — reject everything (for testing)

---

### 4.1 RBAC (Role-Based Access Control)

The standard authorization mode for production clusters. Covered in detail in [04-rbac.md](./04-rbac.md).

**Quick summary:**
- Define **Roles** (namespace-scoped) or **ClusterRoles** (cluster-wide)
- Bind them to users/groups/service accounts via **RoleBindings** or **ClusterRoleBindings**
- Permissions are additive — no deny rules

---

### 4.2 ABAC (Attribute-Based Access Control)

Policy-based access using a JSON policy file. Very powerful but hard to manage — mostly replaced by RBAC.

```json
// /etc/kubernetes/abac-policy.json
{"apiVersion": "abac.authorization.kubernetes.io/v1beta1", "kind": "Policy",
 "spec": {"user": "john", "namespace": "production", "resource": "pods", "readonly": true}}
```

> Requires API server restart to update policies — rarely used in modern clusters.

---

### 4.3 Node Authorization

Special authorizer only for **kubelets**. Grants each kubelet permission to access only resources for Pods scheduled on that node.

```
  kubelet on node-01:
  - Can read Secrets/ConfigMaps for Pods on node-01  ✓
  - Cannot read Secrets for Pods on node-02          ✗
```

This prevents a compromised node from reading secrets for other nodes. Works in combination with RBAC.

---

### 4.4 Webhook Authorization

Like webhook authentication, but for authorization decisions. API server sends a `SubjectAccessReview` request to an external service.

```
  Request: Can "john" GET pods in "production"?
          │
          ▼
  API Server → POST SubjectAccessReview to webhook
                    │
              External auth system
              (OPA, custom policy engine)
                    │
              Returns: allowed=true/false
```

```bash
kube-apiserver --authorization-webhook-config-file=/etc/kubernetes/webhook-authz.yaml
```

---

## 5. Admission Controllers

After authentication and authorization pass, **admission controllers** are the final gate. They can:
- **Validate** requests (reject non-compliant resources)
- **Mutate** requests (add default values, inject sidecars)

```
  Examples of admission controllers:
  
  NamespaceLifecycle    → reject resources in deleted/non-existent namespaces
  ResourceQuota         → enforce namespace resource limits
  LimitRanger           → enforce default resource requests/limits on pods
  ServiceAccount        → auto-assign default service account to pods
  PodSecurity           → enforce pod security standards (replaced PodSecurityPolicy)
  MutatingWebhook       → call external webhooks to mutate resources
  ValidatingWebhook     → call external webhooks to validate resources
```

```bash
# View enabled admission plugins
kube-apiserver --enable-admission-plugins=NamespaceLifecycle,LimitRanger,ServiceAccount,ResourceQuota
```

---

## 6. API Server Security Flags

Key flags that control security on the API server:

```bash
kube-apiserver \
  # --- Authentication ---
  --client-ca-file=/etc/kubernetes/pki/ca.crt \           # X.509 cert auth
  --token-auth-file=/etc/kubernetes/tokens.csv \           # Static tokens
  --oidc-issuer-url=https://auth.example.com \             # OIDC
  --anonymous-auth=false \                                  # Disable anonymous
  
  # --- Authorization ---
  --authorization-mode=Node,RBAC \                          # Enable RBAC
  
  # --- Admission ---
  --enable-admission-plugins=NamespaceLifecycle,LimitRanger,ServiceAccount,ResourceQuota,NodeRestriction \
  
  # --- TLS ---
  --tls-cert-file=/etc/kubernetes/pki/apiserver.crt \
  --tls-private-key-file=/etc/kubernetes/pki/apiserver.key
```

---

## 7. Checking Your Permissions

### Check What You Can Do

```bash
# Can I create pods in default namespace?
kubectl auth can-i create pods

# Can I delete deployments in production namespace?
kubectl auth can-i delete deployments -n production

# Can I get secrets?
kubectl auth can-i get secrets

# Output: yes / no
```

### Check Another User's Permissions (admin only)

```bash
# Can user "john" create pods in default namespace?
kubectl auth can-i create pods --as=john

# Can service account "my-sa" list deployments?
kubectl auth can-i list deployments \
  --as=system:serviceaccount:default:my-sa

# Can group "developers" access production?
kubectl auth can-i get pods -n production \
  --as-group=developers --as=dummy-user
```

### List All Permissions for Current User

```bash
# List what current user can do in all namespaces
kubectl auth can-i --list

# In a specific namespace
kubectl auth can-i --list -n production
```

---

## 8. Common Interview Questions

**Q: What is the difference between authentication and authorization?**
> Authentication verifies **who** you are (identity). Authorization checks **what** you're allowed to do (permissions). In Kubernetes, both are handled by the API server as separate pluggable modules.

**Q: How does Kubernetes create users?**
> Kubernetes has no user store. Users exist only as identities derived from authentication (e.g., the CN of a certificate or the claims in an OIDC token). You can't `kubectl create user`.

**Q: What authentication method is used for cluster components like kube-scheduler?**
> X.509 client certificates. The scheduler uses a cert with `CN=system:kube-scheduler` which maps to its identity.

**Q: What is `system:masters` group?**
> A special group that bypasses all RBAC checks — any user in this group has unrestricted cluster admin access. The initial kubeadm admin user is placed in this group.

**Q: What authorization mode is enabled by default in kubeadm clusters?**
> `Node,RBAC` — Node authorization for kubelets + RBAC for everyone else.

**Q: What is the difference between RBAC and ABAC?**
> RBAC is role-based — you grant roles to users. ABAC is attribute-based — you write fine-grained policies. RBAC is easier to manage and is the standard. ABAC requires a policy file and API server restart to update.

**Q: What happens if all authorization modules deny a request?**
> The API server returns `403 Forbidden`.

---

## 9. Exam Practice Questions

```
1. Check if the current user can create deployments in namespace "staging".
   Answer: kubectl auth can-i create deployments -n staging

2. Check if user "bob" can delete pods in namespace "default".
   Answer: kubectl auth can-i delete pods --as=bob

3. What API server flag enables RBAC authorization?
   Answer: --authorization-mode=RBAC (or Node,RBAC)

4. What is the username and group assigned to the kube-scheduler?
   Answer: Username: system:kube-scheduler, Group: system:component-credentials

5. List all permissions for the current user in namespace "kube-system".
   Answer: kubectl auth can-i --list -n kube-system

6. What CN and O should a certificate have for an admin with full cluster access?
   Answer: CN=admin, O=system:masters

7. How do you disable anonymous authentication on the API server?
   Answer: --anonymous-auth=false in kube-apiserver flags

8. What group do all authenticated users belong to?
   Answer: system:authenticated
```

---

*Previous: [01-tls-ssl-management.md](./01-tls-ssl-management.md)*  
*Next: [03-kubeconfig.md](./03-kubeconfig.md) — Understanding and managing kubeconfig files*

# Kubernetes Service Accounts — Complete Guide

> A Service Account is an identity for a Pod — it controls what the Pod is allowed to do inside the cluster.

---

## Table of Contents

1. [What is a Service Account?](#1-what-is-a-service-account)
2. [Service Account vs User Account](#2-service-account-vs-user-account)
3. [The Default Service Account](#3-the-default-service-account)
4. [How Pods Use Service Accounts](#4-how-pods-use-service-accounts)
5. [Tokens — How Service Accounts Authenticate](#5-tokens--how-service-accounts-authenticate)
6. [Creating and Assigning Service Accounts](#6-creating-and-assigning-service-accounts)
7. [RBAC — Giving Permissions to a Service Account](#7-rbac--giving-permissions-to-a-service-account)
8. [Automounting — Enable and Disable Token](#8-automounting--enable-and-disable-token)
9. [ImagePullSecrets with Service Accounts](#9-imagepullsecrets-with-service-accounts)
10. [Cloud IAM Integration](#10-cloud-iam-integration)
    - [10.1 AWS — IRSA (IAM Roles for Service Accounts)](#101-aws--irsa-iam-roles-for-service-accounts)
    - [10.2 GCP — Workload Identity](#102-gcp--workload-identity)
11. [Practical Demo](#11-practical-demo)
12. [Common Interview Questions](#12-common-interview-questions)
13. [Exam Practice Questions](#13-exam-practice-questions)

---

## 1. What is a Service Account?

A **Service Account** is a Kubernetes identity for **processes running inside Pods**. When a Pod needs to interact with the Kubernetes API server (e.g., list Pods, read Secrets, create Jobs), it uses a Service Account to authenticate.

```
  Without Service Account:             With Service Account:

  Pod: "I want to list all pods"        Pod → ServiceAccount token
  API Server: "Who are you?"     →      API Server verifies token → RBAC check
  Pod: "I don't know..."                API Server: "Allowed — here are the pods"
  Result: 403 Forbidden
```

**Key facts:**
- Every Pod is assigned exactly **one Service Account**
- If you don't specify one, the **default** service account in the Pod's namespace is used
- Service Accounts are **namespace-scoped**
- Permissions are granted via **RBAC** (Roles and RoleBindings)

---

## 2. Service Account vs User Account

| Feature | User Account | Service Account |
|---------|-------------|----------------|
| **Intended for** | Humans (kubectl users, admins) | Pods and processes |
| **Scope** | Cluster-wide | Namespace-scoped |
| **Managed by** | External IdP, certificates, kubeconfig | Kubernetes natively |
| **Created automatically** | No | Yes (`default` per namespace) |
| **Token stored in** | kubeconfig / browser | Kubernetes Secret / projected volume |

---

## 3. The Default Service Account

Every namespace automatically gets a `default` Service Account. Any Pod that doesn't specify a service account gets this one.

```bash
# List service accounts in default namespace
kubectl get serviceaccounts
# or
kubectl get sa

# Output:
# NAME      SECRETS   AGE
# default   0         10d

# Describe it
kubectl describe sa default

# Check default SA in kube-system (has more permissions)
kubectl describe sa default -n kube-system
```

> **Security note**: The `default` service account has minimal permissions, but it still has an automounted token. Best practice is to set `automountServiceAccountToken: false` on the default SA and explicitly assign service accounts only to Pods that need API access.

---

## 4. How Pods Use Service Accounts

When a Pod is created, Kubernetes automatically:

1. Mounts the service account token as a **projected volume** inside the Pod
2. The token is available at: `/var/run/secrets/kubernetes.io/serviceaccount/token`
3. The CA cert is at: `/var/run/secrets/kubernetes.io/serviceaccount/ca.crt`
4. The namespace is at: `/var/run/secrets/kubernetes.io/serviceaccount/namespace`

```
  Pod (nginx-pod)
  ┌──────────────────────────────────────────────────────────┐
  │                                                          │
  │  Projected Volume (auto-mounted):                        │
  │  /var/run/secrets/kubernetes.io/serviceaccount/          │
  │  ├── token         ← JWT token for API auth              │
  │  ├── ca.crt        ← cluster CA certificate              │
  │  └── namespace     ← current namespace name              │
  │                                                          │
  │  Container uses token to call:                           │
  │  https://kubernetes.default.svc/api/v1/pods              │
  └──────────────────────────────────────────────────────────┘
```

```bash
# Inspect the token from inside a pod
kubectl exec -it nginx-pod -- cat /var/run/secrets/kubernetes.io/serviceaccount/token

# Decode the JWT (shows expiry, audience, namespace, SA name)
kubectl exec -it nginx-pod -- cat /var/run/secrets/kubernetes.io/serviceaccount/token | \
  cut -d. -f2 | base64 -d 2>/dev/null | python3 -m json.tool
```

---

## 5. Tokens — How Service Accounts Authenticate

### Token Types

| Token Type | Kubernetes Version | Characteristics |
|-----------|-------------------|----------------|
| **Long-lived Secret token** | < 1.24 | Never expires, stored in Secret, risky |
| **Bound Service Account Token** | ≥ 1.22 (default ≥ 1.24) | Expires (1hr default), audience-bound, projected volume |

### Modern Token (Kubernetes ≥ 1.24)

Since 1.24, Kubernetes does **not** automatically create a Secret for service accounts. Tokens are generated on-demand and mounted as projected volumes with an expiry.

```bash
# Check SA — no secret listed (modern k8s)
kubectl describe sa my-sa
# Name:         my-sa
# Tokens:       <none>   ← no long-lived secret

# Create a short-lived token manually (valid 1 hour by default)
kubectl create token my-sa

# Create token with custom expiry (in seconds)
kubectl create token my-sa --duration=86400s   # 24 hours
```

### Create a Long-Lived Token (Legacy / for CI-CD pipelines)

```yaml
# long-lived-token.yaml
apiVersion: v1
kind: Secret
metadata:
  name: my-sa-token
  namespace: default
  annotations:
    kubernetes.io/service-account.name: my-sa   # link to SA
type: kubernetes.io/service-account-token
```

```bash
kubectl apply -f long-lived-token.yaml

# Get the token value
kubectl get secret my-sa-token -o jsonpath='{.data.token}' | base64 -d
```

---

## 6. Creating and Assigning Service Accounts

### Create a Service Account

```bash
# Imperative
kubectl create serviceaccount my-app-sa
kubectl create sa my-app-sa -n dev   # in specific namespace
```

```yaml
# serviceaccount.yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app-sa
  namespace: default
  labels:
    app: my-app
automountServiceAccountToken: true    # default is true
```

### Assign to a Pod

```yaml
# pod-with-sa.yaml
apiVersion: v1
kind: Pod
metadata:
  name: my-app-pod
spec:
  serviceAccountName: my-app-sa     # ← assign the SA here
  containers:
  - name: app
    image: nginx
```

### Assign to a Deployment

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: my-app
spec:
  replicas: 2
  selector:
    matchLabels:
      app: my-app
  template:
    metadata:
      labels:
        app: my-app
    spec:
      serviceAccountName: my-app-sa   # ← in the pod template spec
      containers:
      - name: app
        image: nginx:1.21
```

---

## 7. RBAC — Giving Permissions to a Service Account

Creating a Service Account does nothing by itself. You must grant permissions using **Roles** and **RoleBindings**.

```
  ServiceAccount
       │
       │ referenced by
       ▼
  RoleBinding  ──links──►  Role (or ClusterRole)
                               │
                               │ defines
                               ▼
                          Rules: verbs + resources
                          (get, list, watch, create, delete)
```

### Step 1: Create a Role (permissions)

```yaml
# pod-reader-role.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader
  namespace: default
rules:
- apiGroups: [""]              # "" = core API group
  resources: ["pods"]
  verbs: ["get", "watch", "list"]

- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list"]
```

### Step 2: Bind the Role to the Service Account

```yaml
# pod-reader-rolebinding.yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: read-pods-binding
  namespace: default
subjects:
- kind: ServiceAccount
  name: my-app-sa            # ← the SA getting permissions
  namespace: default
roleRef:
  kind: Role
  name: pod-reader           # ← the Role being granted
  apiGroup: rbac.authorization.k8s.io
```

```bash
kubectl apply -f pod-reader-role.yaml
kubectl apply -f pod-reader-rolebinding.yaml

# Verify: check what a SA can do
kubectl auth can-i list pods --as=system:serviceaccount:default:my-app-sa
# Output: yes

kubectl auth can-i delete pods --as=system:serviceaccount:default:my-app-sa
# Output: no
```

### Cluster-Wide Permissions (ClusterRole + ClusterRoleBinding)

```yaml
# Give SA read access to pods across ALL namespaces
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: my-app-cluster-reader
subjects:
- kind: ServiceAccount
  name: my-app-sa
  namespace: default
roleRef:
  kind: ClusterRole
  name: view               # built-in ClusterRole: read-only access
  apiGroup: rbac.authorization.k8s.io
```

### Built-in ClusterRoles

| ClusterRole | Permissions |
|-------------|------------|
| `view` | Read-only on most resources |
| `edit` | Read + write on most resources (no RBAC) |
| `admin` | Full access including RBAC in namespace |
| `cluster-admin` | Full access on entire cluster |

```bash
# Bind SA to built-in view role
kubectl create clusterrolebinding my-sa-view \
  --clusterrole=view \
  --serviceaccount=default:my-app-sa
```

---

## 8. Automounting — Enable and Disable Token

By default, every Pod gets the token auto-mounted. **Disable it** for Pods that don't need API access (improves security).

### Disable at ServiceAccount level

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: no-api-access-sa
automountServiceAccountToken: false    # ← all pods using this SA skip token
```

### Disable at Pod level

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: static-web
spec:
  automountServiceAccountToken: false  # ← overrides SA-level setting
  containers:
  - name: nginx
    image: nginx
```

### Re-enable for specific pod (SA has it disabled)

```yaml
spec:
  automountServiceAccountToken: true   # ← overrides SA-level false
```

> **Best practice**: Disable automounting by default on the `default` service account in every namespace, then only enable it for SAs that genuinely need API access.

---

## 9. ImagePullSecrets with Service Accounts

Attach imagePullSecrets to a ServiceAccount so all Pods using that SA automatically get access to private registries.

```bash
# Create a registry secret
kubectl create secret docker-registry my-registry-secret \
  --docker-server=myregistry.example.com \
  --docker-username=myuser \
  --docker-password=mypassword \
  --docker-email=admin@example.com
```

```yaml
# Attach to ServiceAccount
apiVersion: v1
kind: ServiceAccount
metadata:
  name: my-app-sa
imagePullSecrets:
- name: my-registry-secret   # ← all pods using this SA inherit this
```

Now any Pod that uses `serviceAccountName: my-app-sa` automatically pulls from the private registry without specifying `imagePullSecrets` in the Pod spec.

---

## 10. Cloud IAM Integration

### 10.1 AWS — IRSA (IAM Roles for Service Accounts)

IRSA lets Pods assume an **AWS IAM Role** without storing credentials. The Kubernetes SA token is exchanged for temporary AWS credentials via OIDC.

```
  Pod
   │ uses SA token
   ▼
  OIDC Provider (EKS)
   │ validates token
   ▼
  AWS STS (AssumeRoleWithWebIdentity)
   │ issues temporary credentials
   ▼
  Pod gets: AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_SESSION_TOKEN
```

```bash
# Step 1: Create IAM role with trust policy for the SA
eksctl create iamserviceaccount \
  --cluster=my-cluster \
  --namespace=default \
  --name=s3-reader-sa \
  --attach-policy-arn=arn:aws:iam::aws:policy/AmazonS3ReadOnlyAccess \
  --approve

# Step 2: Use this SA in your Pod
```

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: s3-app
spec:
  serviceAccountName: s3-reader-sa   # SA annotated with IAM role ARN
  containers:
  - name: app
    image: amazon/aws-cli
    command: ["aws", "s3", "ls"]     # works without any credentials in Pod!
```

```bash
# Verify the SA has the IRSA annotation
kubectl describe sa s3-reader-sa
# Annotations: eks.amazonaws.com/role-arn: arn:aws:iam::123456789012:role/...
```

### 10.2 GCP — Workload Identity

Similar to IRSA but for GKE — Kubernetes SA is linked to a Google Service Account (GSA).

```bash
# Step 1: Create GCP service account
gcloud iam service-accounts create my-ksa \
  --project=my-project

# Step 2: Grant GCS permissions to GSA
gcloud projects add-iam-policy-binding my-project \
  --member="serviceAccount:my-ksa@my-project.iam.gserviceaccount.com" \
  --role="roles/storage.objectViewer"

# Step 3: Allow K8s SA to impersonate GSA
gcloud iam service-accounts add-iam-policy-binding \
  my-ksa@my-project.iam.gserviceaccount.com \
  --role roles/iam.workloadIdentityUser \
  --member "serviceAccount:my-project.svc.id.goog[default/my-k8s-sa]"

# Step 4: Annotate K8s SA
kubectl annotate serviceaccount my-k8s-sa \
  iam.gke.io/gcp-service-account=my-ksa@my-project.iam.gserviceaccount.com
```

---

## 11. Practical Demo

```bash
# === CREATE SA AND TEST RBAC ===

# 1. Create namespace and SA
kubectl create ns rbac-demo
kubectl create sa api-reader -n rbac-demo

# 2. Create Role: list pods only
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-lister
  namespace: rbac-demo
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
EOF

# 3. Bind Role to SA
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: api-reader-binding
  namespace: rbac-demo
subjects:
- kind: ServiceAccount
  name: api-reader
  namespace: rbac-demo
roleRef:
  kind: Role
  name: pod-lister
  apiGroup: rbac.authorization.k8s.io
EOF

# 4. Test permissions
kubectl auth can-i list pods \
  --as=system:serviceaccount:rbac-demo:api-reader -n rbac-demo
# yes

kubectl auth can-i delete pods \
  --as=system:serviceaccount:rbac-demo:api-reader -n rbac-demo
# no

# 5. Deploy pod using the SA
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Pod
metadata:
  name: api-client
  namespace: rbac-demo
spec:
  serviceAccountName: api-reader
  containers:
  - name: kubectl
    image: bitnami/kubectl
    command: ["sleep", "3600"]
EOF

# 6. Exec into pod and call Kubernetes API
kubectl exec -it api-client -n rbac-demo -- kubectl get pods -n rbac-demo
# Works! Uses mounted token automatically

kubectl exec -it api-client -n rbac-demo -- kubectl get nodes
# Error from server (Forbidden) — only has pod list permission

# 7. Generate a token for the SA
kubectl create token api-reader -n rbac-demo

# === CLEANUP ===
kubectl delete ns rbac-demo
```

---

## 12. Common Interview Questions

**Q: What is a Service Account in Kubernetes?**
> A Service Account is a namespace-scoped identity for processes running inside Pods. When a Pod needs to interact with the Kubernetes API, it authenticates using a JWT token associated with its Service Account. Permissions are controlled via RBAC Role/ClusterRole bindings.

---

**Q: What is the difference between a User Account and a Service Account?**
> User Accounts are for humans accessing the cluster (via kubectl, dashboards). Service Accounts are for machine processes inside Pods. SAs are namespace-scoped and Kubernetes-managed; user accounts are cluster-wide and managed externally (certificates, OIDC, etc.).

---

**Q: Where is the Service Account token mounted inside a Pod?**
> At `/var/run/secrets/kubernetes.io/serviceaccount/`. It contains: `token` (JWT), `ca.crt` (cluster CA), and `namespace` (current namespace). In Kubernetes ≥ 1.24, this is a time-limited projected volume token, not a Secret-backed token.

---

**Q: If you don't specify a Service Account in a Pod spec, what happens?**
> The Pod automatically uses the `default` Service Account in its namespace. The default SA has minimal permissions but still gets a token mounted, which is a security risk. Best practice: explicitly set `automountServiceAccountToken: false` on the default SA.

---

**Q: How do you give a Pod permission to list all Pods in the cluster?**
> Create a ClusterRole with `get/list/watch` on `pods`, then create a ClusterRoleBinding linking it to the Pod's ServiceAccount. A regular Role/RoleBinding would only grant access within one namespace.

---

**Q: What is IRSA?**
> IRSA (IAM Roles for Service Accounts) is an AWS EKS feature that allows Pods to assume AWS IAM roles without storing credentials. The Kubernetes SA token is validated by an OIDC provider, then exchanged for temporary AWS credentials via STS `AssumeRoleWithWebIdentity`. This eliminates the need for hardcoded AWS keys in Pods.

---

## 13. Exam Practice Questions

**1.** Create a Service Account named `deploy-sa` in namespace `dev`.
```bash
kubectl create sa deploy-sa -n dev
```

**2.** Create a Role that allows listing and getting ConfigMaps in namespace `dev`, then bind it to `deploy-sa`.
```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: configmap-reader
  namespace: dev
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: deploy-sa-binding
  namespace: dev
subjects:
- kind: ServiceAccount
  name: deploy-sa
  namespace: dev
roleRef:
  kind: Role
  name: configmap-reader
  apiGroup: rbac.authorization.k8s.io
```

**3.** Check if `deploy-sa` in `dev` can delete Secrets.
```bash
kubectl auth can-i delete secrets \
  --as=system:serviceaccount:dev:deploy-sa -n dev
```

**4.** Create a Pod named `checker` in `dev` using `deploy-sa`, with token automounting disabled.
```yaml
apiVersion: v1
kind: Pod
metadata:
  name: checker
  namespace: dev
spec:
  serviceAccountName: deploy-sa
  automountServiceAccountToken: false
  containers:
  - name: app
    image: nginx
```

**5.** Generate a 2-hour token for `deploy-sa` in `dev`.
```bash
kubectl create token deploy-sa -n dev --duration=7200s
```

---

> **CKA Exam Tips**:
> - Format for `--as` flag: `system:serviceaccount:<namespace>:<sa-name>`
> - `kubectl auth can-i` is your best debugging tool for RBAC
> - SA + Role + RoleBinding = the minimum 3 objects for giving a Pod API access
> - `kubectl create token <sa-name>` generates tokens (added in k8s 1.24)

---

*Notes by ITkannadigaru | CKA 2026 Certification*

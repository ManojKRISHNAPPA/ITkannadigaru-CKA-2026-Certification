# KubeConfig — Complete Guide

> KubeConfig is the key to your cluster. It tells kubectl WHERE the cluster is, WHO you are, and WHICH context to use.

---

## Table of Contents

1. [What is KubeConfig?](#1-what-is-kubeconfig)
2. [KubeConfig File Structure](#2-kubeconfig-file-structure)
3. [The Three Sections — Clusters, Users, Contexts](#3-the-three-sections--clusters-users-contexts)
4. [Default Location and KUBECONFIG Variable](#4-default-location-and-kubeconfig-variable)
5. [kubectl config Commands](#5-kubectl-config-commands)
6. [Working with Multiple Clusters](#6-working-with-multiple-clusters)
7. [Merging Multiple KubeConfigs](#7-merging-multiple-kubeconfigs)
8. [Authentication Methods in KubeConfig](#8-authentication-methods-in-kubeconfig)
9. [Namespaces in Contexts](#9-namespaces-in-contexts)
10. [Creating a KubeConfig for a New User](#10-creating-a-kubeconfig-for-a-new-user)
11. [Service Account KubeConfig](#11-service-account-kubeconfig)
12. [Security Best Practices](#12-security-best-practices)
13. [Common Interview Questions](#13-common-interview-questions)
14. [Exam Practice Questions](#14-exam-practice-questions)

---

## 1. What is KubeConfig?

KubeConfig is a YAML file that stores all the information `kubectl` needs to connect to and authenticate against one or more Kubernetes clusters.

```
  Without kubeconfig:
  
  kubectl get pods \
    --server=https://192.168.1.100:6443 \
    --certificate-authority=/path/to/ca.crt \
    --client-certificate=/path/to/user.crt \
    --client-key=/path/to/user.key \
    --namespace=production
  
  ← You'd type this every single command!


  With kubeconfig:
  
  kubectl get pods
  
  ← kubectl reads all connection details from ~/.kube/config automatically
```

---

## 2. KubeConfig File Structure

```yaml
apiVersion: v1
kind: Config

# ── SECTION 1: The clusters you can connect to ──────────────────
clusters:
- name: dev-cluster                   # ← nickname for this cluster
  cluster:
    server: https://192.168.1.100:6443  # ← API server URL
    certificate-authority: /path/to/ca.crt  # ← CA to trust
    # OR inline (base64 encoded):
    # certificate-authority-data: LS0tLS1CRUdJTi...

- name: prod-cluster
  cluster:
    server: https://10.0.0.1:6443
    certificate-authority-data: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0t...

# ── SECTION 2: The users (credentials) ────────────────────────────
users:
- name: john-dev                      # ← nickname for these credentials
  user:
    client-certificate: /path/to/john.crt
    client-key: /path/to/john.key
    # OR inline:
    # client-certificate-data: LS0tLS1CRUdJTi...
    # client-key-data: LS0tLS1CRUdJTi...

- name: admin-prod
  user:
    token: eyJhbGciOiJSUzI1NiIsInR5...   # ← bearer token

# ── SECTION 3: Contexts (cluster + user + namespace combos) ───────
contexts:
- name: dev                           # ← nickname for this context
  context:
    cluster: dev-cluster              # ← which cluster
    user: john-dev                    # ← which credentials
    namespace: development            # ← default namespace (optional)

- name: prod
  context:
    cluster: prod-cluster
    user: admin-prod
    namespace: production

# ── ACTIVE CONTEXT ───────────────────────────────────────────────
current-context: dev                  # ← which context kubectl uses now
```

---

## 3. The Three Sections — Clusters, Users, Contexts

```
  CLUSTERS section:                  USERS section:
  "Where do I connect?"              "How do I prove who I am?"
  
  ┌─────────────────────┐            ┌───────────────────────┐
  │ dev-cluster         │            │ john-dev              │
  │  server: 192.168... │            │  cert: john.crt       │
  │  ca: ca.crt         │            │  key:  john.key       │
  ├─────────────────────┤            ├───────────────────────┤
  │ prod-cluster        │            │ admin-prod            │
  │  server: 10.0.0.1   │            │  token: eyJhbGci...   │
  └─────────────────────┘            └───────────────────────┘
            │                                  │
            └──────────────┬───────────────────┘
                           │
                  CONTEXTS section:
                  "Which cluster + which credentials + which namespace"
                  
                  ┌────────────────────────────────────┐
                  │ dev                                 │
                  │  cluster: dev-cluster               │
                  │  user:    john-dev                  │
                  │  namespace: development             │
                  ├────────────────────────────────────┤
                  │ prod                                │
                  │  cluster: prod-cluster              │
                  │  user:    admin-prod                │
                  │  namespace: production              │
                  └────────────────────────────────────┘
                           │
                  current-context: dev   ← kubectl uses "dev" context
```

> **Key insight**: Clusters, users, and contexts are all independent lists. The same user can be used with different clusters, and the same cluster can have different users.

---

## 4. Default Location and KUBECONFIG Variable

### Default Location

```bash
~/.kube/config          # Linux/macOS default
%USERPROFILE%\.kube\config   # Windows default
```

### Override with KUBECONFIG Environment Variable

```bash
# Use a specific kubeconfig file
export KUBECONFIG=/path/to/my-kubeconfig.yaml
kubectl get pods

# Use it for just one command
KUBECONFIG=/path/to/config kubectl get nodes

# Merge multiple files (colon-separated on Linux/macOS)
export KUBECONFIG=~/.kube/config:~/.kube/dev-config:~/.kube/prod-config
```

### Override with --kubeconfig flag

```bash
# Use a specific file for one command
kubectl get pods --kubeconfig=/path/to/special-config.yaml
```

### Priority Order

```
  --kubeconfig flag  >  KUBECONFIG env var  >  ~/.kube/config
```

---

## 5. kubectl config Commands

### View the current kubeconfig

```bash
# Display the full kubeconfig
kubectl config view

# Display with secrets shown (tokens, keys)
kubectl config view --raw

# Display only a specific field
kubectl config view -o jsonpath='{.current-context}'
```

### Manage Contexts

```bash
# List all contexts
kubectl config get-contexts

# Output:
# CURRENT   NAME    CLUSTER       AUTHINFO     NAMESPACE
# *         dev     dev-cluster   john-dev     development
#           prod    prod-cluster  admin-prod   production

# Show current context
kubectl config current-context

# Switch to a different context
kubectl config use-context prod

# Delete a context
kubectl config delete-context old-context
```

### Manage Clusters

```bash
# List all clusters
kubectl config get-clusters

# Add/update a cluster
kubectl config set-cluster my-cluster \
  --server=https://192.168.1.100:6443 \
  --certificate-authority=/path/to/ca.crt

# Delete a cluster
kubectl config delete-cluster my-cluster
```

### Manage Users (Credentials)

```bash
# List all users
kubectl config get-users

# Add a user with client cert
kubectl config set-credentials john \
  --client-certificate=john.crt \
  --client-key=john.key

# Add a user with token
kubectl config set-credentials jane \
  --token=eyJhbGciOiJSUzI1NiIsInR5...

# Delete a user
kubectl config delete-user old-user
```

### Manage Contexts

```bash
# Create/update a context
kubectl config set-context dev \
  --cluster=dev-cluster \
  --user=john-dev \
  --namespace=development

# Rename a context
kubectl config rename-context old-name new-name

# Set default namespace for current context
kubectl config set-context --current --namespace=production
```

---

## 6. Working with Multiple Clusters

### Daily Workflow

```bash
# What context am I in?
kubectl config current-context

# Switch to production
kubectl config use-context prod

# Quick temporary override (don't switch context)
kubectl get pods --context=dev
kubectl get nodes -n kube-system --context=prod

# Override namespace for one command
kubectl get pods -n staging
```

### Useful Shell Aliases

```bash
# In ~/.zshrc or ~/.bashrc

alias kdev='kubectl config use-context dev'
alias kprod='kubectl config use-context prod'

# Show current context in shell prompt
PS1='[$(kubectl config current-context)] $ '
```

---

## 7. Merging Multiple KubeConfigs

When you have separate kubeconfig files (e.g., from cloud providers):

```bash
# Merge dev and prod configs into one
KUBECONFIG=~/.kube/dev-config:~/.kube/prod-config \
  kubectl config view --flatten > ~/.kube/config

# Now ~/.kube/config contains both clusters/users/contexts
kubectl config get-contexts
# dev    dev-cluster    john-dev    development
# prod   prod-cluster   admin-prod  production
```

### Get KubeConfig from Cloud Providers

```bash
# AWS EKS
aws eks update-kubeconfig --region us-east-1 --name my-cluster

# GKE
gcloud container clusters get-credentials my-cluster --zone us-central1-a

# Azure AKS
az aks get-credentials --resource-group myRG --name my-cluster
```

---

## 8. Authentication Methods in KubeConfig

### Method 1: Client Certificate

```yaml
users:
- name: alice
  user:
    client-certificate: /home/alice/.certs/alice.crt
    client-key: /home/alice/.certs/alice.key
    # Or embed directly (base64 encoded file contents):
    # client-certificate-data: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0t...
    # client-key-data: LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVkt...
```

### Method 2: Bearer Token

```yaml
users:
- name: service-account-user
  user:
    token: eyJhbGciOiJSUzI1NiIsImtpZCI6IiJ9.eyJpc3MiOiJrdW...
```

### Method 3: Exec Plugin (OIDC, AWS, GCP)

Used by cloud providers and OIDC integrations — runs an external command to get a token:

```yaml
users:
- name: aws-user
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: aws
      args:
      - eks
      - get-token
      - --cluster-name
      - my-cluster
      env:
      - name: AWS_PROFILE
        value: production
```

```yaml
users:
- name: gke-user
  user:
    exec:
      apiVersion: client.authentication.k8s.io/v1beta1
      command: gke-gcloud-auth-plugin
```

### Method 4: Username + Password (deprecated)

```yaml
users:
- name: basic-user
  user:
    username: admin
    password: s3cur3p@ss
```

> **Avoid this** — passwords are stored in plaintext in the kubeconfig file.

---

## 9. Namespaces in Contexts

If no namespace is set in a context, `kubectl` defaults to the `default` namespace.

```bash
# Set a default namespace for the current context
kubectl config set-context --current --namespace=production

# Now all kubectl commands in this context use "production" namespace:
kubectl get pods           # ← lists pods in production
kubectl get services       # ← lists services in production

# Override for a specific command
kubectl get pods -n kube-system
```

### Checking current namespace

```bash
# See which namespace the current context defaults to
kubectl config view --minify | grep namespace

# Or
kubectl config view -o jsonpath='{.contexts[?(@.name=="'$(kubectl config current-context)'")].context.namespace}'
```

---

## 10. Creating a KubeConfig for a New User

Complete workflow to give a new user access to the cluster:

```bash
# Step 1: Create the user's certificates (covered in TLS guide)
openssl genrsa -out alice.key 2048
openssl req -new -key alice.key -subj "/CN=alice/O=developers" -out alice.csr
openssl x509 -req -in alice.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial -out alice.crt -days 365

# Step 2: Build the kubeconfig file for Alice
kubectl config set-cluster my-cluster \
  --server=https://192.168.1.100:6443 \
  --certificate-authority=/etc/kubernetes/pki/ca.crt \
  --kubeconfig=alice.kubeconfig

kubectl config set-credentials alice \
  --client-certificate=alice.crt \
  --client-key=alice.key \
  --kubeconfig=alice.kubeconfig

kubectl config set-context alice-context \
  --cluster=my-cluster \
  --user=alice \
  --namespace=development \
  --kubeconfig=alice.kubeconfig

kubectl config use-context alice-context \
  --kubeconfig=alice.kubeconfig

# Step 3: Share alice.kubeconfig with Alice
# She places it at ~/.kube/config

# Step 4: Create RBAC permissions for Alice (covered in RBAC guide)
kubectl create rolebinding alice-binding \
  --clusterrole=view \
  --user=alice \
  --namespace=development
```

---

## 11. Service Account KubeConfig

Sometimes you need a kubeconfig for a service account (e.g., for CI/CD pipelines):

```bash
# Step 1: Create the service account
kubectl create sa cicd-bot -n default

# Step 2: Create a long-lived token Secret (K8s v1.24+)
cat <<EOF | kubectl apply -f -
apiVersion: v1
kind: Secret
metadata:
  name: cicd-bot-token
  namespace: default
  annotations:
    kubernetes.io/service-account.name: cicd-bot
type: kubernetes.io/service-account-token
EOF

# Step 3: Get the token
TOKEN=$(kubectl get secret cicd-bot-token -o jsonpath='{.data.token}' | base64 -d)
CA_CERT=$(kubectl get secret cicd-bot-token -o jsonpath='{.data.ca\.crt}')
SERVER=$(kubectl config view --minify -o jsonpath='{.clusters[0].cluster.server}')

# Step 4: Build the kubeconfig
cat > cicd.kubeconfig <<EOF
apiVersion: v1
kind: Config
clusters:
- name: my-cluster
  cluster:
    server: ${SERVER}
    certificate-authority-data: ${CA_CERT}
users:
- name: cicd-bot
  user:
    token: ${TOKEN}
contexts:
- name: cicd
  context:
    cluster: my-cluster
    user: cicd-bot
    namespace: default
current-context: cicd
EOF
```

---

## 12. Security Best Practices

```
  ✓ DO:
  - Store kubeconfig in ~/.kube/config with permissions 600
  - Use separate kubeconfig files per cluster/environment
  - Prefer exec-based auth (OIDC) for human users — tokens expire
  - Use certificates for service accounts in CI/CD
  - Rotate tokens regularly
  - Use kubectl config use-context to avoid accidental prod operations

  ✗ DON'T:
  - Commit kubeconfig to Git (contains sensitive credentials)
  - Use cluster-admin credentials in CI/CD — use least-privilege SA
  - Share kubeconfigs between multiple people
  - Store kubeconfig in environment variables in plain text
  - Use username/password auth (deprecated, insecure)
```

```bash
# Lock down kubeconfig file permissions
chmod 600 ~/.kube/config

# Verify permissions
ls -la ~/.kube/config
# -rw------- 1 user user 5432 Jan 01 10:00 /home/user/.kube/config
```

---

## 13. Common Interview Questions

**Q: What are the three main sections of a kubeconfig file?**
> Clusters (server endpoint + CA cert), Users (credentials), and Contexts (cluster + user + namespace combinations). `current-context` sets the active context.

**Q: What is the default location of the kubeconfig file?**
> `~/.kube/config`. Can be overridden with `--kubeconfig` flag or `KUBECONFIG` environment variable.

**Q: How do you switch between clusters in kubectl?**
> `kubectl config use-context <context-name>`. List available contexts with `kubectl config get-contexts`.

**Q: Can one kubeconfig file have multiple clusters?**
> Yes. It maintains lists of clusters, users, and contexts. You switch between them using `kubectl config use-context`.

**Q: How do you set a default namespace in a context?**
> `kubectl config set-context --current --namespace=<namespace>` — subsequent commands in that context default to that namespace.

**Q: How do you merge two kubeconfig files?**
> `KUBECONFIG=file1:file2 kubectl config view --flatten > merged.yaml` — this produces a merged file.

**Q: Where does `kubectl` look for the kubeconfig, and in what priority?**
> 1. `--kubeconfig` flag, 2. `KUBECONFIG` environment variable, 3. `~/.kube/config`

---

## 14. Exam Practice Questions

```
1. View the current context.
   Answer: kubectl config current-context

2. Switch to context named "production".
   Answer: kubectl config use-context production

3. List all available contexts.
   Answer: kubectl config get-contexts

4. Set the default namespace to "kube-system" for the current context.
   Answer: kubectl config set-context --current --namespace=kube-system

5. View kubeconfig but hide sensitive data (default behavior).
   Answer: kubectl config view

6. View kubeconfig including raw certificate data.
   Answer: kubectl config view --raw

7. Add a new cluster entry to kubeconfig.
   Answer: kubectl config set-cluster my-cluster --server=https://ip:6443 --certificate-authority=ca.crt

8. Add credentials for user "bob" using a token.
   Answer: kubectl config set-credentials bob --token=<token>

9. Create a context called "staging" using cluster "stage-cluster" and user "bob".
   Answer: kubectl config set-context staging --cluster=stage-cluster --user=bob

10. Use a specific kubeconfig file for one command without changing defaults.
    Answer: kubectl get pods --kubeconfig=/path/to/config
```

---

*Previous: [02-authentication-and-authorization.md](./02-authentication-and-authorization.md)*  
*Next: [04-rbac.md](./04-rbac.md) — Role-Based Access Control in depth*

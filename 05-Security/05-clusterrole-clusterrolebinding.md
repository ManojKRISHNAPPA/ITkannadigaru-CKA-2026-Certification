# ClusterRole & ClusterRoleBinding — RBAC Deep Dive

> ClusterRoles are the power tools of RBAC. They grant permissions cluster-wide, across namespaces, and to resources that don't belong to any namespace at all.

---

## Table of Contents

1. [Why ClusterRoles Exist](#1-why-clusterroles-exist)
2. [ClusterRole vs Role — The Key Differences](#2-clusterrole-vs-role--the-key-differences)
3. [Cluster-Scoped Resources](#3-cluster-scoped-resources)
4. [ClusterRole — Structure and Examples](#4-clusterrole--structure-and-examples)
5. [ClusterRoleBinding — Cluster-Wide Assignment](#5-clusterrolebinding--cluster-wide-assignment)
6. [Using ClusterRole with RoleBinding (Namespace Scope)](#6-using-clusterrole-with-rolebinding-namespace-scope)
7. [Binding Matrix — When to Use What](#7-binding-matrix--when-to-use-what)
8. [Aggregated ClusterRoles](#8-aggregated-clusterroles)
9. [Built-in ClusterRoles — Deep Dive](#9-built-in-clusterroles--deep-dive)
10. [Common Real-World Patterns](#10-common-real-world-patterns)
11. [Node Authorization & System Components](#11-node-authorization--system-components)
12. [Inspecting ClusterRoles and Bindings](#12-inspecting-clusterroles-and-bindings)
13. [Security Considerations](#13-security-considerations)
14. [Common Interview Questions](#14-common-interview-questions)
15. [Exam Practice Questions](#15-exam-practice-questions)

---

## 1. Why ClusterRoles Exist

Roles are namespace-scoped. But Kubernetes has resources that **don't belong to any namespace** — and some users need access **across all namespaces**. ClusterRoles handle both cases.

```
  Problems that ClusterRoles solve:

  1. Non-namespaced resources:
     Nodes, PersistentVolumes, StorageClasses, Namespaces, ClusterRoles...
     → These can't be controlled by a Role (no namespace to scope to)
     → Must use ClusterRole

  2. Cross-namespace access:
     monitoring tool needs to read pods in ALL namespaces
     → Creating one Role per namespace is impractical
     → Use ClusterRoleBinding + ClusterRole

  3. Reusable permission sets:
     "view" permissions are the same in every namespace
     → Define once as ClusterRole, bind per-namespace via RoleBinding
```

---

## 2. ClusterRole vs Role — The Key Differences

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                  ROLE                                            │
  │  Scope:     Single namespace                                     │
  │  Resources: Only namespaced resources (pods, services, etc.)     │
  │  Bound via: RoleBinding only                                     │
  │  Use when:  Access needed in ONE namespace                       │
  └──────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────┐
  │                  CLUSTERROLE                                     │
  │  Scope:     Entire cluster                                       │
  │  Resources: Namespaced AND non-namespaced resources              │
  │  Bound via: ClusterRoleBinding (cluster-wide)                    │
  │             OR RoleBinding (scoped to one namespace)             │
  │  Use when:  Access needed cluster-wide, or to non-namespaced     │
  │             resources, or when reusing role definition           │
  └──────────────────────────────────────────────────────────────────┘
```

| Feature | Role | ClusterRole |
|---------|------|-------------|
| **Namespace** | Required | Not set (cluster-wide) |
| **Non-namespaced resources** | No | Yes |
| **Use with RoleBinding** | Yes | Yes (scoped to binding's namespace) |
| **Use with ClusterRoleBinding** | No | Yes (cluster-wide) |

---

## 3. Cluster-Scoped Resources

These resources **don't belong to any namespace** — Roles cannot control them:

```bash
# See all non-namespaced resources
kubectl api-resources --namespaced=false

# Common non-namespaced resources:
# nodes
# persistentvolumes (pv)
# storageclasses
# namespaces
# clusterroles
# clusterrolebindings
# certificatesigningrequests (csr)
# priorityclasses
# ingressclasses
# runtimeclasses
```

---

## 4. ClusterRole — Structure and Examples

### Basic ClusterRole

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: node-reader                   # ← no namespace field!
rules:
- apiGroups: [""]
  resources: ["nodes"]                # ← non-namespaced resource
  verbs: ["get", "list", "watch"]
```

### ClusterRole for Non-Namespaced Resources

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: storage-admin
rules:
# Manage persistent volumes (cluster-scoped)
- apiGroups: [""]
  resources: ["persistentvolumes"]
  verbs: ["*"]

# Manage storage classes
- apiGroups: ["storage.k8s.io"]
  resources: ["storageclasses"]
  verbs: ["*"]

# Read PVC in all namespaces
- apiGroups: [""]
  resources: ["persistentvolumeclaims"]
  verbs: ["get", "list", "watch"]
```

### ClusterRole for Cross-Namespace Access

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: namespace-viewer
rules:
- apiGroups: [""]
  resources: ["namespaces"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list", "watch"]
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "watch"]
```

### Create ClusterRole Imperatively

```bash
# Read-only on nodes
kubectl create clusterrole node-reader \
  --verb=get,list,watch \
  --resource=nodes

# Full control of PersistentVolumes
kubectl create clusterrole pv-manager \
  --verb=get,list,watch,create,update,patch,delete \
  --resource=persistentvolumes

# Manage deployments and pods across all namespaces
kubectl create clusterrole app-manager \
  --verb=get,list,watch,create,update,patch,delete \
  --resource=pods,deployments.apps
```

---

## 5. ClusterRoleBinding — Cluster-Wide Assignment

A ClusterRoleBinding grants the ClusterRole's permissions **across the entire cluster**.

### Structure

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: alice-cluster-admin           # ← no namespace field!
subjects:
- kind: User
  name: alice
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole                   # ← must be ClusterRole
  name: cluster-admin                 # ← which ClusterRole
  apiGroup: rbac.authorization.k8s.io
```

### ClusterRoleBinding Examples

```yaml
# Give monitoring system read-only access to everything
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: prometheus-viewer
subjects:
- kind: ServiceAccount
  name: prometheus
  namespace: monitoring               # ← SA still has a namespace
roleRef:
  kind: ClusterRole
  name: view
  apiGroup: rbac.authorization.k8s.io
```

```bash
# Imperative: bind cluster-admin to user "ops-admin"
kubectl create clusterrolebinding ops-admin \
  --clusterrole=cluster-admin \
  --user=ops-admin

# Bind node-reader ClusterRole to group "sre-team"
kubectl create clusterrolebinding sre-node-access \
  --clusterrole=node-reader \
  --group=sre-team

# Bind view ClusterRole to service account "prometheus" in "monitoring" namespace
kubectl create clusterrolebinding prometheus-view \
  --clusterrole=view \
  --serviceaccount=monitoring:prometheus
```

> **Warning**: ClusterRoleBinding to `cluster-admin` gives **full unrestricted access to everything**. Assign carefully.

---

## 6. Using ClusterRole with RoleBinding (Namespace Scope)

This is a powerful pattern: define permissions **once** as a ClusterRole, then bind them **per-namespace** using RoleBindings.

```
  ClusterRole "pod-reader" exists cluster-wide (no namespace)
           │
           ├── RoleBinding in namespace "dev"    → alice can read pods in dev
           ├── RoleBinding in namespace "staging" → bob can read pods in staging
           └── RoleBinding in namespace "prod"   → charlie can read pods in prod

  Only ONE ClusterRole definition needed, reused multiple times!
```

```yaml
# ClusterRole defined once
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: pod-reader
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list", "watch"]
---
# RoleBinding in dev namespace
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: alice-pod-reader
  namespace: dev                      # ← scoped to dev only
subjects:
- kind: User
  name: alice
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole                   # ← references ClusterRole
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
---
# RoleBinding in staging namespace
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: bob-pod-reader
  namespace: staging                  # ← scoped to staging only
subjects:
- kind: User
  name: bob
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole
  name: pod-reader
  apiGroup: rbac.authorization.k8s.io
```

---

## 7. Binding Matrix — When to Use What

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │  Role Type         + Binding Type         = Access Scope            │
  ├─────────────────────────────────────────────────────────────────────┤
  │                                                                     │
  │  Role              + RoleBinding           = One namespace           │
  │  (namespace A)       (namespace A)                                  │
  │                                                                     │
  │  ClusterRole       + RoleBinding           = One namespace           │
  │                      (namespace A)           (scoped by binding)    │
  │                                                                     │
  │  ClusterRole       + ClusterRoleBinding    = All namespaces          │
  │                                              + cluster-scoped        │
  │                                              resources               │
  └─────────────────────────────────────────────────────────────────────┘

  ✗ INVALID:
  Role + ClusterRoleBinding → NOT ALLOWED
  (A Role is namespace-scoped, can't be bound cluster-wide)
```

### Decision Tree

```
  Need to access cluster-scoped resources (nodes, PVs)?
  └── YES → ClusterRole + ClusterRoleBinding

  Need access across ALL namespaces?
  └── YES → ClusterRole + ClusterRoleBinding

  Need access in ONE namespace, and this role is reused across namespaces?
  └── YES → ClusterRole + RoleBinding (in that namespace)

  Need access in ONE namespace, role is unique to that namespace?
  └── YES → Role + RoleBinding (simpler, more isolated)
```

---

## 8. Aggregated ClusterRoles

Aggregated ClusterRoles automatically **merge rules from multiple ClusterRoles** using label selectors. When you add a new ClusterRole with the matching label, its rules are automatically included.

```
  ClusterRole "monitoring"
  ├── aggregationRule selects ClusterRoles with label "rbac.example.com/aggregate-to-monitoring: true"
  └── automatically inherits rules from all matched ClusterRoles

  If I create a new ClusterRole with that label → it's automatically merged in!
```

### Example: Aggregated Role

```yaml
# The aggregate role itself (no rules — they come from sub-roles)
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: monitoring
aggregationRule:
  clusterRoleSelectors:
  - matchLabels:
      rbac.example.com/aggregate-to-monitoring: "true"
rules: []   # ← empty! aggregated from sub-roles below
---
# Sub-role 1: Pod monitoring
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: monitoring-pods
  labels:
    rbac.example.com/aggregate-to-monitoring: "true"  # ← magic label
rules:
- apiGroups: [""]
  resources: ["pods", "pods/log"]
  verbs: ["get", "list", "watch"]
---
# Sub-role 2: Node monitoring (added later, auto-merged)
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: monitoring-nodes
  labels:
    rbac.example.com/aggregate-to-monitoring: "true"  # ← same label
rules:
- apiGroups: [""]
  resources: ["nodes"]
  verbs: ["get", "list", "watch"]
```

### Kubernetes Built-in Aggregation

The built-in `admin`, `edit`, and `view` ClusterRoles use aggregation. CRD operators add a labeled ClusterRole to automatically extend these:

```yaml
# A CRD operator adds this to extend the "view" ClusterRole:
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: my-operator-viewer
  labels:
    rbac.authorization.k8s.io/aggregate-to-view: "true"   # ← extends "view"
    rbac.authorization.k8s.io/aggregate-to-edit: "true"   # ← extends "edit"
    rbac.authorization.k8s.io/aggregate-to-admin: "true"  # ← extends "admin"
rules:
- apiGroups: ["myoperator.io"]
  resources: ["myresources"]
  verbs: ["get", "list", "watch"]
```

---

## 9. Built-in ClusterRoles — Deep Dive

```bash
# List all built-in ClusterRoles
kubectl get clusterroles

# Describe a specific one
kubectl describe clusterrole view
kubectl describe clusterrole edit
kubectl describe clusterrole admin
kubectl describe clusterrole cluster-admin
```

### The Four Standard ClusterRoles

```
  cluster-admin
  └── Full control of EVERYTHING in the cluster
      rules: [{apiGroups:["*"], resources:["*"], verbs:["*"]}]
      Binding: ClusterRoleBinding → affects entire cluster
               RoleBinding → affects only that namespace

  admin
  └── Full control within a namespace
      Can create/update roles and rolebindings
      Cannot manage namespace itself or resource quotas
      Binding: RoleBinding → namespace admin

  edit
  └── Read/write most resources in a namespace
      Cannot read/write roles, rolebindings, secrets (by default in older versions)
      Binding: RoleBinding → developer access

  view
  └── Read-only on most resources in a namespace
      Cannot read secrets (prevents credential leakage)
      Binding: RoleBinding → read-only observer
```

### System ClusterRoles (for cluster components)

```bash
system:kube-scheduler              # scheduler permissions
system:kube-controller-manager     # controller manager permissions
system:node                        # kubelet node permissions
system:node-proxier                # kube-proxy permissions
system:persistent-volume-provisioner  # PV provisioner
system:aggregate-to-admin          # aggregation for admin role
system:aggregate-to-edit           # aggregation for edit role
system:aggregate-to-view           # aggregation for view role
```

---

## 10. Common Real-World Patterns

### Pattern 1: Namespace Admin

```bash
# Alice is admin of just her team's namespace
kubectl create clusterrolebinding alice-ns-admin \
  --clusterrole=admin \
  --user=alice \
  --namespace=team-alice
# ← Uses RoleBinding, not ClusterRoleBinding, to scope to one namespace
```

Wait — `kubectl create clusterrolebinding` always creates a ClusterRoleBinding. For namespace scope, use:
```bash
kubectl create rolebinding alice-ns-admin \
  -n team-alice \
  --clusterrole=admin \
  --user=alice
```

### Pattern 2: Monitoring Service Account

```bash
# Prometheus needs to read everything across all namespaces
kubectl create clusterrolebinding prometheus-monitoring \
  --clusterrole=view \
  --serviceaccount=monitoring:prometheus
```

### Pattern 3: Node Management

```bash
# SRE team can manage nodes
kubectl create clusterrole node-manager \
  --verb=get,list,watch,patch,update \
  --resource=nodes

kubectl create clusterrolebinding sre-node-manager \
  --clusterrole=node-manager \
  --group=sre-team
```

### Pattern 4: Cluster-Admin for Initial Setup (Temporary)

```bash
# Give temporary cluster-admin (revoke after setup)
kubectl create clusterrolebinding temp-admin \
  --clusterrole=cluster-admin \
  --user=setup-user

# Revoke when done
kubectl delete clusterrolebinding temp-admin
```

### Pattern 5: Read Secrets in Specific Namespace Only

```yaml
# Note: Use Role (not ClusterRole) to avoid accidentally granting cross-NS access
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: secret-reader
  namespace: production
rules:
- apiGroups: [""]
  resources: ["secrets"]
  verbs: ["get", "list"]
```

---

## 11. Node Authorization & System Components

Kubelets use a special **Node Authorizer** (not RBAC) to get permissions scoped to their own node:

```
  kubelet on node-01:
  - Identity: system:node:node-01 (in group system:nodes)
  - Can access secrets/configmaps ONLY for pods on node-01
  - Can update the status of node-01 only
  - Cannot access secrets for pods on node-02

  This is enforced by the Node authorizer, not RBAC.
  Both Node + RBAC modes run together: --authorization-mode=Node,RBAC
```

### NodeRestriction Admission Controller

The `NodeRestriction` admission controller further limits kubelet permissions:

```bash
kube-apiserver \
  --enable-admission-plugins=...,NodeRestriction,...
```

With NodeRestriction enabled, a kubelet can only:
- Modify its own Node object
- Modify Pods bound to its own node
- Cannot modify other nodes or pods on other nodes

---

## 12. Inspecting ClusterRoles and Bindings

```bash
# List all ClusterRoles
kubectl get clusterroles

# List all ClusterRoleBindings
kubectl get clusterrolebindings

# Describe a ClusterRole (see all rules)
kubectl describe clusterrole cluster-admin

# Describe a ClusterRoleBinding (see who is bound)
kubectl describe clusterrolebinding cluster-admin

# Find who has cluster-admin access
kubectl get clusterrolebindings -o json | \
  jq '.items[] | select(.roleRef.name=="cluster-admin") | .subjects'

# Find all bindings for a specific user
kubectl get rolebindings,clusterrolebindings \
  --all-namespaces \
  -o json | \
  jq '.items[] | select(.subjects[]?.name=="alice")'

# Export a ClusterRole to YAML
kubectl get clusterrole view -o yaml
```

---

## 13. Security Considerations

### Principle of Least Privilege

```
  ✓ Grant the minimum permissions needed
  ✓ Prefer namespace-scoped Roles over ClusterRoles when possible
  ✓ Use Groups for team-level access (easier to manage than per-user bindings)
  ✓ Audit ClusterRoleBindings regularly — they grant cluster-wide access
  ✓ Never give ClusterRoleBinding to cluster-admin unless absolutely necessary

  ✗ Don't use wildcards (*) in production roles unless unavoidable
  ✗ Don't give application pods cluster-admin access
  ✗ Don't give access to secrets unless required
  ✗ Don't bind cluster-admin to service accounts
```

### Privilege Escalation Prevention

Kubernetes prevents privilege escalation — you cannot create a Role or ClusterRole granting more permissions than you have:

```
  If I have: permission to get/list pods
  I cannot create a role that: allows creating/deleting pods
  → API server returns: 403 Forbidden (cannot escalate privileges)
```

To grant a role, you need either:
1. The same permissions the role grants, OR
2. The `escalate` verb on roles

### Impersonation

Special RBAC verb that allows one user to act as another:

```yaml
# Allow cicd-controller to impersonate deployment service accounts
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: impersonation-role
rules:
- apiGroups: [""]
  resources: ["users", "groups", "serviceaccounts"]
  verbs: ["impersonate"]
```

```bash
# Use impersonation
kubectl get pods --as=other-user
kubectl get pods --as=system:serviceaccount:default:my-sa
```

> Impersonation is powerful — guard the `impersonate` verb tightly.

---

## 14. Common Interview Questions

**Q: What is the difference between ClusterRole + ClusterRoleBinding vs ClusterRole + RoleBinding?**
> ClusterRole + ClusterRoleBinding grants cluster-wide access (all namespaces + cluster-scoped resources). ClusterRole + RoleBinding grants access only within the binding's namespace — useful for reusing a ClusterRole definition while scoping it to one namespace.

**Q: Can you bind a Role with a ClusterRoleBinding?**
> No. A Role is namespace-scoped; ClusterRoleBinding is cluster-wide. You cannot bind them together. Only ClusterRoles can be used with ClusterRoleBindings.

**Q: How do you give a user admin access to one namespace without cluster-wide access?**
> Create a RoleBinding (not ClusterRoleBinding) referencing the built-in `admin` ClusterRole:  
> `kubectl create rolebinding alice-admin --clusterrole=admin --user=alice --namespace=team-alice`

**Q: What are aggregated ClusterRoles?**
> ClusterRoles that automatically merge rules from other ClusterRoles via label selectors. The built-in `view`, `edit`, `admin` roles use aggregation, allowing CRD operators to extend them without modifying the originals.

**Q: A user needs to list nodes in the cluster. Do you use Role or ClusterRole?**
> ClusterRole — nodes are cluster-scoped resources and can't be accessed via a namespace-scoped Role.

**Q: What is the `system:masters` group and why is it special?**
> Members of `system:masters` bypass all RBAC checks and always have cluster-admin access. It cannot be revoked via RBAC because it's checked before RBAC evaluation.

**Q: How do you find which users have cluster-admin access?**
> `kubectl get clusterrolebindings -o yaml | grep -A5 "cluster-admin"` or describe the `cluster-admin` ClusterRoleBinding.

---

## 15. Exam Practice Questions

```
1. Create a ClusterRole called "node-reader" that allows get, list, watch on nodes.
   Answer:
   kubectl create clusterrole node-reader --verb=get,list,watch --resource=nodes

2. Create a ClusterRoleBinding that binds "node-reader" to user "sre".
   Answer:
   kubectl create clusterrolebinding sre-node-reader --clusterrole=node-reader --user=sre

3. Give service account "prometheus" in namespace "monitoring" view access 
   to all pods in all namespaces.
   Answer:
   kubectl create clusterrolebinding prometheus-view \
     --clusterrole=view \
     --serviceaccount=monitoring:prometheus

4. Give user "alice" admin access ONLY in namespace "team-alice".
   Answer:
   kubectl create rolebinding alice-admin -n team-alice \
     --clusterrole=admin --user=alice

5. List all ClusterRoleBindings in the cluster.
   Answer:
   kubectl get clusterrolebindings

6. Describe the built-in "view" ClusterRole to see what it allows.
   Answer:
   kubectl describe clusterrole view

7. Check if service account "my-sa" in default namespace can list nodes.
   Answer:
   kubectl auth can-i list nodes \
     --as=system:serviceaccount:default:my-sa

8. Create a ClusterRole "pv-manager" with full control over PersistentVolumes.
   Answer:
   kubectl create clusterrole pv-manager --verb="*" --resource=persistentvolumes

9. Find out who has cluster-admin access in this cluster.
   Answer:
   kubectl describe clusterrolebinding cluster-admin

10. Delete the ClusterRoleBinding "temp-admin".
    Answer:
    kubectl delete clusterrolebinding temp-admin
```

---

*Previous: [04-rbac.md](./04-rbac.md)*  
*Module: [05-Security/](./)*

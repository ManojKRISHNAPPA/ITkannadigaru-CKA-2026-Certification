# RBAC — Role-Based Access Control in Kubernetes

> RBAC is the primary authorization system in Kubernetes. It answers: "Can this user/pod perform this action on this resource?"

---

## Table of Contents

1. [What is RBAC?](#1-what-is-rbac)
2. [RBAC Building Blocks](#2-rbac-building-blocks)
3. [API Groups and Resources](#3-api-groups-and-resources)
4. [Verbs — What Actions Can Be Taken?](#4-verbs--what-actions-can-be-taken)
5. [Role — Namespace-Scoped Permissions](#5-role--namespace-scoped-permissions)
6. [RoleBinding — Assigning a Role](#6-rolebinding--assigning-a-role)
7. [Subjects — Who Gets the Role?](#7-subjects--who-gets-the-role)
8. [Practical Examples](#8-practical-examples)
9. [Checking and Debugging Permissions](#9-checking-and-debugging-permissions)
10. [Default Roles in Kubernetes](#10-default-roles-in-kubernetes)
11. [RBAC for Service Accounts](#11-rbac-for-service-accounts)
12. [Common Patterns](#12-common-patterns)
13. [Common Interview Questions](#13-common-interview-questions)
14. [Exam Practice Questions](#14-exam-practice-questions)

---

## 1. What is RBAC?

RBAC controls **who** can do **what** on **which resources** in Kubernetes.

```
  The RBAC question:
  
  Can [SUBJECT] perform [VERB] on [RESOURCE] in [NAMESPACE]?
  
  Example:
  Can [user: alice] [get/list/watch] [pods] in [namespace: production]?
                │              │          │              │
             Subject          Verb     Resource       Scope
```

RBAC is **additive** — there are no explicit deny rules. If a permission is not granted, it is denied.

```
  RBAC is always: "allow this, allow that..."
  NOT:            "deny this" (no deny rules exist!)
  
  Result: if no role grants access → access is denied by default
```

---

## 2. RBAC Building Blocks

```
  ┌─────────────────────────────────────────────────────────────────┐
  │                     RBAC Objects                                │
  │                                                                 │
  │  ┌──────────────────┐       ┌──────────────────┐               │
  │  │  Role             │       │  ClusterRole      │               │
  │  │  (namespace-scoped)│       │  (cluster-wide)   │               │
  │  │  Defines: what    │       │  Defines: what    │               │
  │  │  actions allowed  │       │  actions allowed  │               │
  │  └────────┬─────────┘       └────────┬──────────┘               │
  │           │                          │                          │
  │           │ bound via                │ bound via                │
  │           ▼                          ▼                          │
  │  ┌──────────────────┐       ┌──────────────────────────┐        │
  │  │  RoleBinding      │       │  ClusterRoleBinding       │        │
  │  │  (namespace-scoped)│       │  (cluster-wide)           │        │
  │  │  Links: role →    │       │  Links: clusterrole →     │        │
  │  │  subject in 1 NS  │       │  subject everywhere       │        │
  │  └──────────────────┘       └──────────────────────────┘        │
  └─────────────────────────────────────────────────────────────────┘
```

| Object | Scope | Purpose |
|--------|-------|---------|
| **Role** | Namespace | Defines permissions within one namespace |
| **ClusterRole** | Cluster-wide | Defines permissions cluster-wide or for non-namespaced resources |
| **RoleBinding** | Namespace | Binds a Role or ClusterRole to a subject in one namespace |
| **ClusterRoleBinding** | Cluster-wide | Binds a ClusterRole to a subject cluster-wide |

---

## 3. API Groups and Resources

In Kubernetes, resources are organized into **API groups**.

```
  Core group (apiVersion: v1):
  pods, services, endpoints, namespaces, configmaps, secrets,
  persistentvolumes, persistentvolumeclaims, serviceaccounts,
  nodes, events, resourcequotas

  Named groups:
  apps/v1:        deployments, replicasets, daemonsets, statefulsets
  batch/v1:       jobs, cronjobs
  networking.k8s.io/v1:  ingresses, networkpolicies
  rbac.authorization.k8s.io/v1: roles, rolebindings, clusterroles, clusterrolebindings
  autoscaling/v2: horizontalpodautoscalers
  storage.k8s.io/v1: storageclasses, persistentvolumes
```

### In RBAC Rules

```yaml
# Core group resources (use empty string "")
rules:
- apiGroups: [""]
  resources: ["pods", "services"]
  verbs: ["get", "list"]

# Named group resources
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "create", "update"]
```

### Sub-resources

Some resources have sub-resources that can be targeted separately:

```yaml
rules:
# Allow exec into pods but not create/delete pods
- apiGroups: [""]
  resources: ["pods/exec"]           # ← sub-resource
  verbs: ["create"]

# Allow reading pod logs
- apiGroups: [""]
  resources: ["pods/log"]            # ← sub-resource
  verbs: ["get"]

# Allow port-forwarding
- apiGroups: [""]
  resources: ["pods/portforward"]    # ← sub-resource
  verbs: ["create"]
```

---

## 4. Verbs — What Actions Can Be Taken?

| Verb | HTTP Method | Description |
|------|-------------|-------------|
| `get` | GET | Read a single resource |
| `list` | GET (collection) | List multiple resources |
| `watch` | GET + watch | Watch for changes (streaming) |
| `create` | POST | Create a resource |
| `update` | PUT | Full replace of a resource |
| `patch` | PATCH | Partial update of a resource |
| `delete` | DELETE | Delete a single resource |
| `deletecollection` | DELETE (collection) | Delete multiple resources |
| `use` | — | Special verb for PodSecurityPolicies |
| `bind` | — | Special verb for binding roles |
| `impersonate` | — | Act as another user |
| `escalate` | — | Grant permissions you have |
| `*` | ALL | Wildcard — all verbs |

```yaml
# Common patterns:
verbs: ["get", "list", "watch"]          # read-only
verbs: ["create", "update", "patch"]     # write
verbs: ["delete", "deletecollection"]    # delete
verbs: ["get", "list", "watch", "create", "update", "patch", "delete"]  # full control
verbs: ["*"]                             # wildcard (same as full)
```

---

## 5. Role — Namespace-Scoped Permissions

A Role defines **what can be done** within a **single namespace**.

### Basic Role Structure

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-reader                    # ← role name
  namespace: production               # ← scope: only this namespace
rules:
- apiGroups: [""]                     # ← "" = core API group
  resources: ["pods"]                 # ← which resources
  verbs: ["get", "list", "watch"]     # ← what can be done
```

### Role with Multiple Rules

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: developer-role
  namespace: development
rules:
# Full control over pods
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["*"]

# Read-only on configmaps
- apiGroups: [""]
  resources: ["configmaps"]
  verbs: ["get", "list"]

# Manage deployments
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "create", "update", "patch"]

# Read pod logs
- apiGroups: [""]
  resources: ["pods/log"]
  verbs: ["get"]
```

### Restrict to Specific Resource Names

```yaml
rules:
- apiGroups: [""]
  resources: ["configmaps"]
  resourceNames: ["app-config", "db-config"]  # ← only these specific configmaps
  verbs: ["get"]
```

### Create a Role Imperatively

```bash
# Create role to read pods
kubectl create role pod-reader \
  --verb=get,list,watch \
  --resource=pods \
  --namespace=production

# Create role to manage deployments
kubectl create role deploy-manager \
  --verb=get,list,create,update,patch,delete \
  --resource=deployments \
  --namespace=staging
```

---

## 6. RoleBinding — Assigning a Role

A RoleBinding **connects a Role to a Subject** within a namespace.

### Basic RoleBinding Structure

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: alice-pod-reader              # ← binding name
  namespace: production               # ← applies in this namespace
subjects:                             # ← who gets the role
- kind: User
  name: alice                         # ← the username (from cert CN)
  apiGroup: rbac.authorization.k8s.io
roleRef:                              # ← which role to assign
  kind: Role
  name: pod-reader                    # ← must exist in same namespace
  apiGroup: rbac.authorization.k8s.io
```

### Bind a ClusterRole with a RoleBinding (scoped to namespace)

```yaml
# You can bind a ClusterRole using a RoleBinding
# Result: ClusterRole permissions apply ONLY in this namespace
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: view-in-production
  namespace: production
subjects:
- kind: User
  name: bob
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: ClusterRole              # ← ClusterRole, not Role
  name: view                     # ← built-in cluster role
  apiGroup: rbac.authorization.k8s.io
```

### Create a RoleBinding Imperatively

```bash
# Bind role "pod-reader" to user "alice" in namespace "production"
kubectl create rolebinding alice-pod-reader \
  --role=pod-reader \
  --user=alice \
  --namespace=production

# Bind built-in ClusterRole "view" to user "bob" in namespace "production"
kubectl create rolebinding bob-viewer \
  --clusterrole=view \
  --user=bob \
  --namespace=production

# Bind role to a group
kubectl create rolebinding dev-team-binding \
  --role=developer-role \
  --group=developers \
  --namespace=development

# Bind role to a service account
kubectl create rolebinding sa-binding \
  --role=pod-reader \
  --serviceaccount=default:my-sa \
  --namespace=production
```

---

## 7. Subjects — Who Gets the Role?

A subject is the entity receiving the permissions. Three types:

```yaml
subjects:
# Type 1: User (human, cert-based)
- kind: User
  name: alice
  apiGroup: rbac.authorization.k8s.io

# Type 2: Group
- kind: Group
  name: developers
  apiGroup: rbac.authorization.k8s.io

# Type 3: ServiceAccount
- kind: ServiceAccount
  name: my-service-account
  namespace: default                  # ← SA must specify namespace
```

### Binding to Multiple Subjects

```yaml
subjects:
- kind: User
  name: alice
  apiGroup: rbac.authorization.k8s.io
- kind: User
  name: bob
  apiGroup: rbac.authorization.k8s.io
- kind: Group
  name: ops-team
  apiGroup: rbac.authorization.k8s.io
- kind: ServiceAccount
  name: cicd-sa
  namespace: cicd
```

---

## 8. Practical Examples

### Example 1: Read-Only Access to a Namespace

```yaml
# Role: read pods, services, configmaps
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: readonly
  namespace: production
rules:
- apiGroups: ["", "apps"]
  resources: ["pods", "services", "deployments", "replicasets"]
  verbs: ["get", "list", "watch"]
---
# Bind to user alice
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: alice-readonly
  namespace: production
subjects:
- kind: User
  name: alice
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: readonly
  apiGroup: rbac.authorization.k8s.io
```

### Example 2: CI/CD Bot Can Deploy

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: deployer
  namespace: staging
rules:
- apiGroups: ["apps"]
  resources: ["deployments"]
  verbs: ["get", "list", "create", "update", "patch"]
- apiGroups: [""]
  resources: ["services", "configmaps"]
  verbs: ["get", "list", "create", "update"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: cicd-deploy
  namespace: staging
subjects:
- kind: ServiceAccount
  name: cicd-bot
  namespace: cicd
roleRef:
  kind: Role
  name: deployer
  apiGroup: rbac.authorization.k8s.io
```

### Example 3: Allow Pod Exec for Debugging Team

```yaml
apiVersion: rbac.authorization.k8s.io/v1
kind: Role
metadata:
  name: pod-exec
  namespace: development
rules:
- apiGroups: [""]
  resources: ["pods"]
  verbs: ["get", "list"]
- apiGroups: [""]
  resources: ["pods/exec"]
  verbs: ["create"]
- apiGroups: [""]
  resources: ["pods/log"]
  verbs: ["get"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: debug-team-exec
  namespace: development
subjects:
- kind: Group
  name: debug-team
  apiGroup: rbac.authorization.k8s.io
roleRef:
  kind: Role
  name: pod-exec
  apiGroup: rbac.authorization.k8s.io
```

---

## 9. Checking and Debugging Permissions

```bash
# Check what the current user can do
kubectl auth can-i --list

# Check specific permission
kubectl auth can-i create pods -n production
# Output: yes / no

# Check as another user
kubectl auth can-i get secrets --as=alice

# Check as a service account
kubectl auth can-i list pods \
  --as=system:serviceaccount:default:my-sa

# Check as a group member
kubectl auth can-i create deployments \
  --as=dummy --as-group=developers -n production

# Describe a role to see what it grants
kubectl describe role pod-reader -n production

# Describe a rolebinding to see who it applies to
kubectl describe rolebinding alice-pod-reader -n production

# List all roles in a namespace
kubectl get roles -n production

# List all rolebindings in a namespace
kubectl get rolebindings -n production
```

---

## 10. Default Roles in Kubernetes

Kubernetes ships with several built-in ClusterRoles:

| ClusterRole | Description |
|-------------|-------------|
| `cluster-admin` | Full control of everything in the cluster |
| `admin` | Full control in a namespace (can manage roles too) |
| `edit` | Read/write most resources in namespace, no role management |
| `view` | Read-only access to most resources in namespace |

```bash
# Use built-in roles quickly:

# Give alice view access to production namespace
kubectl create rolebinding alice-view \
  --clusterrole=view \
  --user=alice \
  --namespace=production

# Give bob edit access to staging namespace
kubectl create rolebinding bob-edit \
  --clusterrole=edit \
  --user=bob \
  --namespace=staging
```

---

## 11. RBAC for Service Accounts

Service accounts need RBAC to access the Kubernetes API from within Pods.

```bash
# Create service account
kubectl create serviceaccount app-sa -n default

# Create role
kubectl create role app-role \
  --verb=get,list,watch \
  --resource=pods,configmaps \
  --namespace=default

# Bind role to service account
kubectl create rolebinding app-sa-binding \
  --role=app-role \
  --serviceaccount=default:app-sa \
  --namespace=default
```

```yaml
# Use SA in a Pod
apiVersion: v1
kind: Pod
metadata:
  name: my-app
spec:
  serviceAccountName: app-sa          # ← use the SA with permissions
  containers:
  - name: app
    image: my-app:latest
```

---

## 12. Common Patterns

### Pattern: Namespace Admin

```bash
# Give full admin access to one namespace only
kubectl create rolebinding ns-admin \
  --clusterrole=admin \
  --user=alice \
  --namespace=team-alice
```

### Pattern: Read-Only Across All Namespaces

```bash
# Use ClusterRoleBinding + view ClusterRole
kubectl create clusterrolebinding readonly-all \
  --clusterrole=view \
  --user=monitor-user
```

### Pattern: Multiple Users Same Role

```yaml
# Bind to a group instead of individual users
kubectl create rolebinding dev-team \
  --clusterrole=edit \
  --group=developers \
  --namespace=development
```

---

## 13. Common Interview Questions

**Q: What is the difference between a Role and a ClusterRole?**
> Role is namespace-scoped — it only grants access within one namespace. ClusterRole is cluster-wide — it can grant access across all namespaces or to cluster-scoped resources like Nodes and PersistentVolumes.

**Q: What is the difference between a RoleBinding and a ClusterRoleBinding?**
> RoleBinding grants access within a single namespace. ClusterRoleBinding grants access cluster-wide. A RoleBinding can reference a ClusterRole, but scopes it to one namespace.

**Q: Can RBAC deny access?**
> No. RBAC is purely additive — you can only grant permissions, not explicitly deny them. Access not explicitly granted is denied by default.

**Q: What does `kubectl auth can-i` do?**
> It checks if the current user has permission to perform a specific action. With `--as=username` it checks for a different user. Used heavily in CKA exams.

**Q: How do you give a service account permissions?**
> Create a Role/ClusterRole defining the permissions, then create a RoleBinding/ClusterRoleBinding that binds that role to the service account using `kind: ServiceAccount` in the subjects field.

**Q: What does the built-in `cluster-admin` ClusterRole grant?**
> Complete unrestricted access to all resources in the entire cluster — equivalent to root.

---

## 14. Exam Practice Questions

```
1. Create a Role called "pod-reader" in namespace "production" that allows
   get, list, watch on pods.
   Answer:
   kubectl create role pod-reader --verb=get,list,watch --resource=pods -n production

2. Bind the role "pod-reader" to user "alice" in namespace "production".
   Answer:
   kubectl create rolebinding alice-pod-reader --role=pod-reader --user=alice -n production

3. Check if user "alice" can list pods in namespace "production".
   Answer:
   kubectl auth can-i list pods -n production --as=alice

4. Create a RoleBinding that gives service account "my-sa" in namespace "default"
   the built-in "edit" ClusterRole in namespace "staging".
   Answer:
   kubectl create rolebinding sa-edit -n staging --clusterrole=edit \
     --serviceaccount=default:my-sa

5. List all roles in namespace "development".
   Answer:
   kubectl get roles -n development

6. Describe the rolebinding "alice-pod-reader" in namespace "production".
   Answer:
   kubectl describe rolebinding alice-pod-reader -n production

7. Create a role "deploy-reader" in namespace "default" allowing
   get and list on deployments (apps group).
   Answer:
   kubectl create role deploy-reader --verb=get,list --resource=deployments.apps -n default

8. Check all permissions available to the current user in namespace "staging".
   Answer:
   kubectl auth can-i --list -n staging
```

---

*Previous: [03-kubeconfig.md](./03-kubeconfig.md)*  
*Next: [05-clusterrole-clusterrolebinding.md](./05-clusterrole-clusterrolebinding.md) — RBAC deep dive*

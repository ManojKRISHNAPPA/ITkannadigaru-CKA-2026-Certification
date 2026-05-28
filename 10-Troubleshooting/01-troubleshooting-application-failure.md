# Troubleshooting Application Failure in Kubernetes — Complete Guide

> Domain: Troubleshooting — Application Failure  
> CKA 2026 Course — [YouTube Playlist](https://www.youtube.com/playlist?list=PLaZfMOMvbDOZas6hEZ4_G-JH8FhpzmYQA)

---

## Video-Document Mapper

| Sr No | Topic |
|-------|-------|
| 1 | [Troubleshooting Application Failure](#troubleshooting-methodology) |
| 2 | [Solution - Troubleshooting Application Failure](#hands-on-scenarios) |

---

## Table of Contents

1. [Troubleshooting Methodology](#1-troubleshooting-methodology)
2. [Pod Not Starting — Diagnosis Tree](#2-pod-not-starting--diagnosis-tree)
3. [Common Failure States and Fixes](#3-common-failure-states-and-fixes)
4. [Service Connectivity Issues](#4-service-connectivity-issues)
5. [Deployment Rollout Issues](#5-deployment-rollout-issues)
6. [Node-Level Problems](#6-node-level-problems)
7. [Control Plane Troubleshooting](#7-control-plane-troubleshooting)
8. [Persistent Volume Issues](#8-persistent-volume-issues)
9. [ConfigMap and Secret Issues](#9-configmap-and-secret-issues)
10. [RBAC Permission Errors](#10-rbac-permission-errors)
11. [Hands-On Scenarios](#11-hands-on-scenarios)
12. [Quick Reference — Troubleshooting Cheat Sheet](#12-quick-reference--troubleshooting-cheat-sheet)
13. [Exam Practice Questions](#13-exam-practice-questions)

---

## 1. Troubleshooting Methodology

Always follow a **top-down** approach: start at the highest level and drill down.

```
  Application not working?
  
  Level 1: Is the Pod running?
  └── kubectl get pods
  
  Level 2: Why is the Pod not running?
  └── kubectl describe pod <name>
  └── kubectl logs <pod> [--previous]
  
  Level 3: Can the Pod be accessed via Service?
  └── kubectl get svc
  └── kubectl get endpoints
  
  Level 4: Is the Node healthy?
  └── kubectl get nodes
  └── kubectl describe node <name>
  
  Level 5: Are control plane components healthy?
  └── kubectl get componentstatuses
  └── kubectl get pods -n kube-system
```

### Essential Troubleshooting Commands

```bash
# Cluster-wide health overview
kubectl get nodes
kubectl get pods -A
kubectl get events -A --sort-by='.lastTimestamp' | tail -20

# Pod-specific
kubectl get pod <name> -o wide
kubectl describe pod <name>
kubectl logs <pod> [-c <container>] [--previous]

# Service/networking
kubectl get svc
kubectl get endpoints <svc-name>
kubectl exec -it <pod> -- curl http://<service>:<port>

# Resource usage
kubectl top nodes
kubectl top pods
```

---

## 2. Pod Not Starting — Diagnosis Tree

```
  kubectl get pods shows non-Running status
              │
  ┌───────────┼───────────────────────────────────┐
  │           │                                   │
  ▼           ▼                                   ▼
Pending   CrashLoopBackOff              Error / OOMKilled
  │           │                                   │
  ▼           ▼                                   ▼
kubectl     kubectl logs                   kubectl describe
describe    --previous                     check memory limits
  │
  ▼
Check Events:
- FailedScheduling → Insufficient resources? Taints? NodeSelector?
- FailedMount      → PVC not found? Wrong volume name?
- ImagePullBackOff → Wrong image name? No registry access?
```

---

## 3. Common Failure States and Fixes

### Pending — Not Scheduled

```bash
kubectl describe pod my-pod | grep -A20 "Events:"
```

**FailedScheduling: Insufficient cpu**
```bash
# Check node resources
kubectl top nodes
kubectl describe node node1 | grep -A10 "Allocated resources"

# Fix: reduce pod resource requests
kubectl edit deployment my-app
# change resources.requests.cpu

# OR scale up the cluster (add nodes)
```

**FailedScheduling: 0/3 nodes are available: 3 node(s) had taint**
```bash
# Check taints on nodes
kubectl describe nodes | grep Taints

# Fix option A: add toleration to pod
# Fix option B: remove taint from node
kubectl taint node node1 key=value:NoSchedule-
```

**FailedScheduling: 0/3 nodes match nodeSelector**
```bash
# Check pod nodeSelector
kubectl get pod my-pod -o yaml | grep -A5 nodeSelector

# Check node labels
kubectl get nodes --show-labels

# Fix: add label to node or fix selector
kubectl label node node1 disktype=ssd
```

---

### ImagePullBackOff / ErrImagePull

```bash
kubectl describe pod my-pod | grep -A5 "Warning"
```

**Image name wrong:**
```bash
# Check events for exact error
kubectl describe pod my-pod | grep "Failed to pull image"

# Fix: correct the image name
kubectl set image deployment/my-app app=nginx:1.26   # correct version
kubectl edit deployment my-app                        # edit directly
```

**Private registry — no credentials:**
```bash
# Create imagePullSecret
kubectl create secret docker-registry my-registry-secret \
  --docker-server=registry.example.com \
  --docker-username=user \
  --docker-password=password \
  --docker-email=user@example.com

# Add to pod spec
kubectl patch deployment my-app \
  -p '{"spec":{"template":{"spec":{"imagePullSecrets":[{"name":"my-registry-secret"}]}}}}'
```

---

### CrashLoopBackOff

```bash
# Step 1: See what the container is printing before crashing
kubectl logs my-pod --previous

# Step 2: Check container exit code
kubectl describe pod my-pod | grep "Exit Code"
# Exit Code 1  → application error
# Exit Code 137 → OOMKilled
# Exit Code 143 → SIGTERM (graceful shutdown request)

# Step 3: Debug by running an interactive shell
# If main container crashes immediately, override the command:
kubectl run debug --image=nginx --command -- sleep 3600
kubectl exec -it debug -- /bin/sh
```

**Common causes:**
```bash
# Missing environment variable
kubectl logs my-pod --previous
# Error: DB_HOST environment variable not set
# Fix: add env var to deployment

kubectl set env deployment/my-app DB_HOST=postgres-service

# Wrong command/entrypoint
kubectl get pod my-pod -o yaml | grep -A5 "command"
# Fix: correct the command in pod spec

# Config file missing
kubectl logs my-pod --previous
# Error: /etc/app/config.yaml not found
# Fix: mount ConfigMap as volume or ensure file exists in image
```

---

### OOMKilled (Exit Code 137)

```bash
kubectl describe pod my-pod | grep -i "oom\|memory\|killed"

# Fix: increase memory limit
kubectl edit deployment my-app
# spec.containers[0].resources.limits.memory: 512Mi → 1Gi

# OR investigate memory leak in application
```

---

## 4. Service Connectivity Issues

### Service Not Reaching Pods

```bash
# Step 1: Check if service exists
kubectl get svc my-service

# Step 2: Check if endpoints exist (this is the key check!)
kubectl get endpoints my-service
# NAME         ENDPOINTS          AGE
# my-service   <none>             5m  ← NO ENDPOINTS! pods not matched

# Step 3: Compare service selector with pod labels
kubectl describe svc my-service | grep Selector
kubectl get pods --show-labels

# The selector must match pod labels EXACTLY
```

**Fix: Labels don't match selector**
```bash
# Service selector:
kubectl describe svc my-service
# Selector: app=my-app,version=v2

# Pod labels:
kubectl get pods --show-labels
# my-pod    app=my-app   ← missing version=v2!

# Fix option A: add label to pod
kubectl label pod my-pod version=v2

# Fix option B: fix the service selector
kubectl patch svc my-service \
  -p '{"spec":{"selector":{"app":"my-app"}}}'
```

### Service Port vs Container Port Mismatch

```bash
kubectl describe svc my-service
# Port: 80/TCP
# TargetPort: 3000/TCP  ← must match containerPort in pod spec

kubectl describe pod my-pod | grep "Port:"
# Port: 8080/TCP  ← MISMATCH! service targets 3000, pod listens on 8080

# Fix:
kubectl patch svc my-service \
  -p '{"spec":{"ports":[{"port":80,"targetPort":8080}]}}'
```

### DNS Resolution Issues

```bash
# Test DNS from inside a pod
kubectl run dns-test --image=busybox --rm -it -- \
  nslookup my-service

# Full service DNS format:
# <service>.<namespace>.svc.cluster.local
kubectl run dns-test --image=busybox --rm -it -- \
  nslookup my-service.default.svc.cluster.local

# Check if CoreDNS is running
kubectl get pods -n kube-system | grep coredns
kubectl logs -n kube-system -l k8s-app=kube-dns
```

---

## 5. Deployment Rollout Issues

### Rollout Stuck

```bash
# Check rollout status
kubectl rollout status deployment/my-app
# Waiting for deployment "my-app" rollout to finish: 1 out of 3 new replicas have been updated...

# Check why new pods aren't starting
kubectl get pods
kubectl describe pod <new-pod-name>

# Roll back to previous version
kubectl rollout undo deployment/my-app

# Roll back to specific revision
kubectl rollout history deployment/my-app
kubectl rollout undo deployment/my-app --to-revision=2
```

### Pod Template Wrong After Edit

```bash
# View current deployment spec
kubectl describe deployment my-app

# Check rollout history
kubectl rollout history deployment/my-app

# Check what changed
kubectl rollout history deployment/my-app --revision=3
```

---

## 6. Node-Level Problems

### Node NotReady

```bash
# Check node status
kubectl get nodes
# NAME    STATUS     ROLES     AGE
# node1   NotReady   worker    5d    ← PROBLEM

# Get details
kubectl describe node node1

# Check events on the node
kubectl get events --field-selector involvedObject.name=node1

# SSH to the node and check kubelet
ssh node1
sudo systemctl status kubelet
sudo journalctl -u kubelet --since "10 minutes ago"

# Common causes:
# kubelet service stopped
sudo systemctl restart kubelet

# Disk pressure
df -h     # check disk usage
du -sh /var/lib/containerd    # check container storage

# Memory pressure
free -h   # check memory

# Network plugin not running
kubectl get pods -n kube-system   # check CNI plugin pods
```

### Pods Evicted from Node

```bash
# See evicted pods
kubectl get pods | grep Evicted

# Why evicted?
kubectl describe pod <evicted-pod> | grep "Reason\|Message"
# Common: Evicted: The node was low on resource: memory

# Clean up evicted pods
kubectl delete pods --field-selector status.phase=Failed
```

---

## 7. Control Plane Troubleshooting

### Check Control Plane Components

```bash
# Static pod status (kubeadm clusters)
kubectl get pods -n kube-system

# Check component health
kubectl get componentstatuses
# NAME                 STATUS      MESSAGE
# controller-manager   Healthy     ok
# scheduler            Healthy     ok
# etcd-0               Healthy     ok

# If a component is unhealthy, check its pod
kubectl describe pod kube-apiserver-master -n kube-system
kubectl logs kube-apiserver-master -n kube-system

# For static pods, check manifest files
ls /etc/kubernetes/manifests/
# kube-apiserver.yaml
# kube-controller-manager.yaml
# kube-scheduler.yaml
# etcd.yaml
```

### API Server Not Responding

```bash
# Check if API server pod is running
sudo crictl pods | grep kube-apiserver

# Check for certificate issues
sudo openssl x509 -in /etc/kubernetes/pki/apiserver.crt -text -noout | grep "Not After"

# Tail API server logs
sudo journalctl -u kubelet | grep apiserver
```

---

## 8. Persistent Volume Issues

### PVC Stuck in Pending

```bash
kubectl describe pvc my-pvc

# Events:
# no persistent volumes available for this claim

# Check available PVs
kubectl get pv
# If no PVs available:
# - Create a PV manually (static provisioning)
# - Check StorageClass for dynamic provisioning

# Check if storageClass matches
kubectl get pvc my-pvc -o yaml | grep storageClassName
kubectl get pv | grep storageClassName

# Check access mode compatibility
kubectl describe pvc my-pvc | grep "Access Modes"
kubectl describe pv my-pv | grep "Access Modes"
```

### Pod Can't Mount Volume

```bash
kubectl describe pod my-pod | grep -A10 "Warning.*FailedMount"

# Common: wrong PVC name
kubectl get pvc                        # check actual PVC names
kubectl get pod my-pod -o yaml | grep -A3 "persistentVolumeClaim"

# Fix: correct PVC name in pod spec
```

---

## 9. ConfigMap and Secret Issues

### Application Can't Read Config

```bash
# Check ConfigMap exists
kubectl get configmap my-config

# Describe it to see keys
kubectl describe configmap my-config

# Check pod is mounting it correctly
kubectl describe pod my-pod | grep -A10 "Volumes:"
kubectl describe pod my-pod | grep -A10 "Mounts:"

# Exec into pod to verify mount
kubectl exec -it my-pod -- ls /etc/config
kubectl exec -it my-pod -- cat /etc/config/app.conf

# Check env var from ConfigMap
kubectl exec -it my-pod -- env | grep MY_ENV_VAR
```

### Secret Not Found

```bash
kubectl get secrets
kubectl describe pod my-pod | grep -A5 "secret"

# Error: secret "db-credentials" not found
# Fix: create the secret
kubectl create secret generic db-credentials \
  --from-literal=username=admin \
  --from-literal=password=s3cret
```

---

## 10. RBAC Permission Errors

```bash
# Symptom: 403 Forbidden when accessing API
# Check in pod logs:
# Error from server (Forbidden): pods is forbidden: User "my-sa" cannot list pods

# Diagnose:
kubectl auth can-i list pods \
  --as=system:serviceaccount:default:my-sa

# Fix: create RBAC permissions
kubectl create role pod-reader \
  --verb=get,list,watch \
  --resource=pods

kubectl create rolebinding sa-pod-reader \
  --role=pod-reader \
  --serviceaccount=default:my-sa
```

---

## 11. Hands-On Scenarios

### Scenario 1: App returns 502 Bad Gateway

```bash
# Hypothesis: backend pods not reachable from ingress/service

# Step 1: Check pods
kubectl get pods -l app=backend

# Step 2: Check service endpoints
kubectl get endpoints backend-svc
# If empty → label selector mismatch

# Step 3: Fix label mismatch
kubectl get pods -l app=backend --show-labels
kubectl describe svc backend-svc | grep Selector

# Step 4: Correct the selector or pod labels
kubectl patch svc backend-svc \
  -p '{"spec":{"selector":{"app":"backend"}}}'
```

### Scenario 2: Pod in CrashLoopBackOff

```bash
# Step 1: Check logs
kubectl logs my-pod --previous
# Output: "Error: cannot open /config/app.yaml: no such file"

# Step 2: Check if ConfigMap exists and is mounted
kubectl get configmap app-config
kubectl describe pod my-pod | grep -A10 "Volumes:"

# Step 3: The ConfigMap key is wrong
kubectl describe configmap app-config
# Data: application.yaml  ← but pod expects "app.yaml"

# Fix: update ConfigMap mount with correct key or rename key
```

### Scenario 3: Deployment not scaling

```bash
# Step 1: Check HPA
kubectl get hpa

# Step 2: Check metrics
kubectl top pods

# Step 3: Is metrics-server running?
kubectl get pods -n kube-system | grep metrics

# Step 4: Check HPA events
kubectl describe hpa my-hpa
# Events: unable to get metrics... (metrics server issue)

# Fix: reinstall/fix metrics server
```

---

## 12. Quick Reference — Troubleshooting Cheat Sheet

```
  SYMPTOM                    COMMAND                           LOOK FOR
  ─────────────────────────────────────────────────────────────────────────────
  Pod not running            kubectl describe pod <name>       Events section
  Pod crashing               kubectl logs <pod> --previous     Error output
  No endpoints               kubectl get endpoints <svc>       <none> = label mismatch
  Node NotReady              kubectl describe node <name>      Conditions, Events
  Image not pulling          kubectl describe pod <name>       Failed to pull image
  Permission denied in pod   kubectl auth can-i ...            yes/no
  PVC not binding            kubectl describe pvc <name>       No matching PV
  Service unreachable        kubectl exec -- curl <svc>        Connection refused
  CPU/Memory issues          kubectl top pods/nodes            High usage
  Cert expired               kubeadm certs check-expiration   Expiry dates
```

---

## 13. Exam Practice Questions

```
1. A pod is in CrashLoopBackOff. How do you read its crash logs?
   Answer: kubectl logs <pod-name> --previous

2. A service has no endpoints. What is the most likely cause?
   Answer: Label selector mismatch — service selector doesn't match pod labels.
   Check: kubectl describe svc <name> | grep Selector
          kubectl get pods --show-labels

3. How do you check if a pod has permission to list pods in its namespace?
   Answer: kubectl auth can-i list pods \
             --as=system:serviceaccount:<namespace>:<sa-name>

4. A pod is Pending with "FailedScheduling" event. List 3 possible causes.
   Answer:
   - Insufficient CPU or memory on all nodes
   - Node taint without matching pod toleration
   - NodeSelector/affinity doesn't match any node labels

5. How do you roll back a deployment to the previous version?
   Answer: kubectl rollout undo deployment/<name>

6. A PVC is stuck in Pending. How do you diagnose?
   Answer: kubectl describe pvc <name>
   Look for: "no persistent volumes available" or access mode/StorageClass mismatch

7. How do you get the exit code of the last container crash?
   Answer: kubectl describe pod <name> | grep "Exit Code"

8. A container is OOMKilled. How do you fix it?
   Answer: Increase the memory limit in the deployment:
   kubectl edit deployment <name>
   → spec.containers[0].resources.limits.memory: <higher value>

9. How do you debug a service not being accessible from another pod?
   Answer:
   kubectl exec -it <source-pod> -- curl http://<service-name>:<port>
   kubectl get endpoints <service-name>  # check for populated endpoints

10. Check the rollout history of a deployment.
    Answer: kubectl rollout history deployment/<name>
```

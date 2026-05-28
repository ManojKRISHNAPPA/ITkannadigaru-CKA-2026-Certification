# Cluster Architecture, Installation & Configuration — Complete Guide

> Domain: Cluster Architecture, Installation & Configuration  
> CKA 2026 Course — [YouTube Playlist](https://www.youtube.com/playlist?list=PLaZfMOMvbDOZas6hEZ4_G-JH8FhpzmYQA)

---

## Video-Document Mapper

| Sr No | Topic |
|-------|-------|
| 1 | [sysctl](#1-sysctl--kernel-parameters) |
| 2 | [kubeadm - Setting Up Kubernetes Master Node](#2-kubeadm--setting-up-kubernetes-master-node) |
| 3 | [kubeadm - Setting Up Kubernetes Worker Node](#3-kubeadm--setting-up-kubernetes-worker-node) |
| 4 | [sysctl (revisited)](#4-sysctl-revisited) |
| 5 | [Step 1: Kubernetes From Scratch - Download Kubernetes Binaries](#5-step-1-kubernetes-from-scratch--download-kubernetes-binaries) |
| 6 | [Step 2: Kubernetes From Scratch - Setup Certificate Authority](#6-step-2-kubernetes-from-scratch--setup-certificate-authority) |
| 7 | [Step 3: Kubernetes From Scratch - Configure ETCD](#7-step-3-kubernetes-from-scratch--configure-etcd) |
| 8 | [Step 4: Kubernetes From Scratch - Configure API Server](#8-step-4-kubernetes-from-scratch--configure-api-server) |
| 9 | [Step 5: Kubernetes From Scratch - Configure Controller Manager](#9-step-5-kubernetes-from-scratch--configure-controller-manager) |
| 10 | [Step 6: Kubernetes From Scratch - Configure Scheduler](#10-step-6-kubernetes-from-scratch--configure-scheduler) |
| 11 | [Step 7: Kubernetes From Scratch - Validate Cluster Status](#11-step-7-kubernetes-from-scratch--validate-cluster-status) |
| 12 | [Step 8: Kubernetes From Scratch - Worker Node Configuration](#12-step-8-kubernetes-from-scratch--worker-node-configuration) |
| 13 | [Step 9: Kubernetes From Scratch - Configure Networking](#13-step-9-kubernetes-from-scratch--configure-networking) |
| 14 | [Step 10: Kubernetes From Scratch - API to Kubelet RBAC](#14-step-10-kubernetes-from-scratch--api-to-kubelet-rbac) |
| 15 | [Step 11: Kubernetes From Scratch - Configuring DNS](#15-step-11-kubernetes-from-scratch--configuring-dns) |
| 16 | [Step 12: Kubernetes From Scratch - Kubelet Preferred Address Type](#16-step-12-kubernetes-from-scratch--kubelet-preferred-address-type) |
| 17 | [Breakdown Learning](#17-breakdown-learning) |
| 18 | [ETCD Backup and Restore](#18-etcd-backup-and-restore) |
| 19 | [Structure of Network Policy](#19-structure-of-network-policy) |
| 20 | [Practical - Network Policies](#20-practical--network-policies) |
| 21 | [Network Policies - Except, Port and Protocol](#21-network-policies--except-port-and-protocol) |
| 22 | [Taints and Tolerations](#22-taints-and-tolerations) |
| 23 | [Custom Resource Definition](#23-custom-resource-definition) |
| 24 | [Editing Existing Kubernetes Resources](#24-editing-existing-kubernetes-resources) |
| 25 | [Capacity, Allocated, and Allocatable](#25-capacity-allocated-and-allocatable) |
| 26 | [Exercise - Requests and Limits](#26-exercise--requests-and-limits) |
| 27 | [JSONPath](#27-jsonpath) |
| 28 | [Configuring cri-dockerd](#28-configuring-cri-dockerd) |

---

## 1. sysctl — Kernel Parameters

`sysctl` configures kernel parameters at runtime. Kubernetes requires specific kernel settings for networking and container operation.

### Required Kernel Modules

```bash
# Load required kernel modules
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

sudo modprobe overlay
sudo modprobe br_netfilter

# Verify modules are loaded
lsmod | grep br_netfilter
lsmod | grep overlay
```

### Required sysctl Parameters

```bash
# Apply sysctl settings
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
net.ipv4.ip_forward                 = 1
EOF

# Apply without reboot
sudo sysctl --system

# Verify
sysctl net.bridge.bridge-nf-call-iptables
sysctl net.ipv4.ip_forward
```

**Why these settings?**
- `net.ipv4.ip_forward = 1` — allows packets to be forwarded between network interfaces (required for Pod-to-Pod communication)
- `bridge-nf-call-iptables = 1` — ensures iptables rules apply to bridged network traffic (required for kube-proxy/CNI plugins)

---

## 2. kubeadm — Setting Up Kubernetes Master Node

### Pre-requisites

```bash
# Disable swap (Kubernetes requires swap to be off)
sudo swapoff -a

# Disable swap permanently
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

# Verify swap is off
free -h
# Swap: 0B
```

### Install Container Runtime (containerd)

```bash
# Install containerd
sudo apt-get update
sudo apt-get install -y containerd

# Configure containerd
sudo mkdir -p /etc/containerd
sudo containerd config default | sudo tee /etc/containerd/config.toml

# Enable SystemdCgroup (CRITICAL for kubeadm)
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' \
  /etc/containerd/config.toml

# Restart and enable containerd
sudo systemctl restart containerd
sudo systemctl enable containerd
sudo systemctl status containerd
```

### Install kubeadm, kubelet, kubectl

```bash
# Add Kubernetes apt repository
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gpg

# Download signing key
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.32/deb/Release.key | \
  sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

# Add repository
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] https://pkgs.k8s.io/core:/stable:/v1.32/deb/ /' | \
  sudo tee /etc/apt/sources.list.d/kubernetes.list

# Install packages
sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl

# Pin versions to prevent accidental upgrades
sudo apt-mark hold kubelet kubeadm kubectl

# Enable kubelet
sudo systemctl enable --now kubelet
```

### Initialize the Control Plane

```bash
# Initialize with kubeadm
sudo kubeadm init \
  --pod-network-cidr=192.168.0.0/16 \    # ← Calico default; use 10.244.0.0/16 for Flannel
  --apiserver-advertise-address=<MASTER_IP>

# After init, set up kubeconfig for the admin user
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# Or for root:
export KUBECONFIG=/etc/kubernetes/admin.conf
```

### Install CNI Plugin (Calico)

```bash
# Install Calico
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.0/manifests/calico.yaml

# Wait for nodes to be Ready
kubectl get nodes -w
```

### Save the Join Command

```bash
# kubeadm init prints this at the end — SAVE IT:
kubeadm join <MASTER_IP>:6443 \
  --token <token> \
  --discovery-token-ca-cert-hash sha256:<hash>

# If you lose the token, regenerate:
kubeadm token create --print-join-command
```

---

## 3. kubeadm — Setting Up Kubernetes Worker Node

```bash
# On each worker node:

# Step 1: Apply sysctl + kernel modules (same as master)
# Step 2: Disable swap
# Step 3: Install containerd (same as master)
# Step 4: Install kubelet, kubeadm (kubectl optional on workers)

# Step 5: Join the cluster
sudo kubeadm join <MASTER_IP>:6443 \
  --token <token> \
  --discovery-token-ca-cert-hash sha256:<hash>

# Verify from master:
kubectl get nodes
```

---

## 4. sysctl (Revisited)

Advanced sysctl settings for production Kubernetes:

```bash
# Performance tuning for high-traffic clusters
cat <<EOF | sudo tee /etc/sysctl.d/99-kubernetes-perf.conf
# Increase max connections
net.core.somaxconn = 32768
net.ipv4.tcp_max_syn_backlog = 16384

# Increase inotify watches (for kubelet)
fs.inotify.max_user_watches = 524288
fs.inotify.max_user_instances = 512

# Increase file descriptors
fs.file-max = 52706963
fs.nr_open = 52706963

# Network forwarding (already set)
net.ipv4.ip_forward = 1
net.bridge.bridge-nf-call-iptables = 1
EOF

sudo sysctl --system
```

---

## 5. Step 1: Kubernetes From Scratch — Download Kubernetes Binaries

Building Kubernetes without kubeadm — the "hard way." This teaches how each component works.

```bash
# Set Kubernetes version
K8S_VERSION="v1.32.0"

# Download control plane binaries
wget -q --show-progress --https-only --timestamping \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/amd64/kube-apiserver" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/amd64/kube-controller-manager" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/amd64/kube-scheduler" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/amd64/kubectl"

# Download worker node binaries
wget -q --show-progress --https-only --timestamping \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/amd64/kubelet" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/amd64/kube-proxy"

# Make executable
chmod +x kube-apiserver kube-controller-manager kube-scheduler kubectl kubelet kube-proxy

# Move to PATH
sudo mv kube-apiserver kube-controller-manager kube-scheduler kubectl kubelet kube-proxy \
  /usr/local/bin/
```

---

## 6. Step 2: Kubernetes From Scratch — Setup Certificate Authority

```bash
# Create PKI directory
sudo mkdir -p /etc/kubernetes/pki/etcd

# Generate Cluster CA
# Private key
openssl genrsa -out /etc/kubernetes/pki/ca.key 2048
# Self-signed certificate
openssl req -new -x509 -days 3650 \
  -key /etc/kubernetes/pki/ca.key \
  -out /etc/kubernetes/pki/ca.crt \
  -subj "/CN=kubernetes-ca/O=Kubernetes"

# Generate etcd CA
openssl genrsa -out /etc/kubernetes/pki/etcd/ca.key 2048
openssl req -new -x509 -days 3650 \
  -key /etc/kubernetes/pki/etcd/ca.key \
  -out /etc/kubernetes/pki/etcd/ca.crt \
  -subj "/CN=etcd-ca/O=etcd"

# Generate API Server certificate (with SANs for all IPs/hostnames)
cat > /tmp/apiserver-csr.conf <<EOF
[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name
[req_distinguished_name]
[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth
subjectAltName = @alt_names
[alt_names]
DNS.1 = kubernetes
DNS.2 = kubernetes.default
DNS.3 = kubernetes.default.svc
DNS.4 = kubernetes.default.svc.cluster.local
IP.1 = 10.96.0.1          # ClusterIP of kubernetes service
IP.2 = <MASTER_IP>
EOF

openssl genrsa -out /etc/kubernetes/pki/apiserver.key 2048
openssl req -new -key /etc/kubernetes/pki/apiserver.key \
  -out /tmp/apiserver.csr \
  -subj "/CN=kube-apiserver" \
  -config /tmp/apiserver-csr.conf
openssl x509 -req \
  -in /tmp/apiserver.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/apiserver.crt \
  -days 3650 \
  -extensions v3_req \
  -extfile /tmp/apiserver-csr.conf
```

---

## 7. Step 3: Kubernetes From Scratch — Configure ETCD

etcd is the cluster's key-value store — all cluster state lives here.

```bash
# Download etcd
ETCD_VERSION="v3.5.11"
wget -q --show-progress https://github.com/etcd-io/etcd/releases/download/${ETCD_VERSION}/etcd-${ETCD_VERSION}-linux-amd64.tar.gz
tar -xf etcd-${ETCD_VERSION}-linux-amd64.tar.gz
sudo mv etcd-${ETCD_VERSION}-linux-amd64/etcd* /usr/local/bin/

# Create data directory
sudo mkdir -p /var/lib/etcd
sudo chmod 700 /var/lib/etcd

# Create etcd systemd service
cat <<EOF | sudo tee /etc/systemd/system/etcd.service
[Unit]
Description=etcd
Documentation=https://github.com/etcd-io/etcd

[Service]
ExecStart=/usr/local/bin/etcd \\
  --name=master \\
  --cert-file=/etc/kubernetes/pki/etcd/server.crt \\
  --key-file=/etc/kubernetes/pki/etcd/server.key \\
  --peer-cert-file=/etc/kubernetes/pki/etcd/peer.crt \\
  --peer-key-file=/etc/kubernetes/pki/etcd/peer.key \\
  --trusted-ca-file=/etc/kubernetes/pki/etcd/ca.crt \\
  --peer-trusted-ca-file=/etc/kubernetes/pki/etcd/ca.crt \\
  --peer-client-cert-auth \\
  --client-cert-auth \\
  --initial-advertise-peer-urls https://127.0.0.1:2380 \\
  --listen-peer-urls https://127.0.0.1:2380 \\
  --listen-client-urls https://127.0.0.1:2379 \\
  --advertise-client-urls https://127.0.0.1:2379 \\
  --data-dir=/var/lib/etcd
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now etcd
sudo systemctl status etcd
```

---

## 8. Step 4: Kubernetes From Scratch — Configure API Server

```bash
cat <<EOF | sudo tee /etc/systemd/system/kube-apiserver.service
[Unit]
Description=Kubernetes API Server

[Service]
ExecStart=/usr/local/bin/kube-apiserver \\
  --advertise-address=<MASTER_IP> \\
  --allow-privileged=true \\
  --authorization-mode=Node,RBAC \\
  --client-ca-file=/etc/kubernetes/pki/ca.crt \\
  --enable-admission-plugins=NodeRestriction \\
  --etcd-cafile=/etc/kubernetes/pki/etcd/ca.crt \\
  --etcd-certfile=/etc/kubernetes/pki/apiserver-etcd-client.crt \\
  --etcd-keyfile=/etc/kubernetes/pki/apiserver-etcd-client.key \\
  --etcd-servers=https://127.0.0.1:2379 \\
  --kubelet-client-certificate=/etc/kubernetes/pki/apiserver-kubelet-client.crt \\
  --kubelet-client-key=/etc/kubernetes/pki/apiserver-kubelet-client.key \\
  --runtime-config=api/all=true \\
  --service-account-issuer=https://kubernetes.default.svc.cluster.local \\
  --service-account-key-file=/etc/kubernetes/pki/sa.pub \\
  --service-account-signing-key-file=/etc/kubernetes/pki/sa.key \\
  --service-cluster-ip-range=10.96.0.0/12 \\
  --tls-cert-file=/etc/kubernetes/pki/apiserver.crt \\
  --tls-private-key-file=/etc/kubernetes/pki/apiserver.key
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kube-apiserver
```

---

## 9. Step 5: Kubernetes From Scratch — Configure Controller Manager

```bash
cat <<EOF | sudo tee /etc/systemd/system/kube-controller-manager.service
[Unit]
Description=Kubernetes Controller Manager

[Service]
ExecStart=/usr/local/bin/kube-controller-manager \\
  --bind-address=0.0.0.0 \\
  --cluster-cidr=192.168.0.0/16 \\
  --cluster-name=kubernetes \\
  --cluster-signing-cert-file=/etc/kubernetes/pki/ca.crt \\
  --cluster-signing-key-file=/etc/kubernetes/pki/ca.key \\
  --kubeconfig=/etc/kubernetes/controller-manager.conf \\
  --leader-elect=true \\
  --root-ca-file=/etc/kubernetes/pki/ca.crt \\
  --service-account-private-key-file=/etc/kubernetes/pki/sa.key \\
  --service-cluster-ip-range=10.96.0.0/12 \\
  --use-service-account-credentials=true
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kube-controller-manager
```

---

## 10. Step 6: Kubernetes From Scratch — Configure Scheduler

```bash
cat <<EOF | sudo tee /etc/systemd/system/kube-scheduler.service
[Unit]
Description=Kubernetes Scheduler

[Service]
ExecStart=/usr/local/bin/kube-scheduler \\
  --config=/etc/kubernetes/scheduler.conf \\
  --leader-elect=true
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create scheduler config
cat <<EOF | sudo tee /etc/kubernetes/scheduler-config.yaml
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
clientConnection:
  kubeconfig: /etc/kubernetes/scheduler.conf
leaderElection:
  leaderElect: true
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kube-scheduler
```

---

## 11. Step 7: Kubernetes From Scratch — Validate Cluster Status

```bash
# Check all control plane components
kubectl get componentstatuses
# or (newer)
kubectl get --raw='/readyz?verbose'

# Check nodes
kubectl get nodes

# Check system pods (if CNI installed)
kubectl get pods -n kube-system

# Test cluster with a pod
kubectl run nginx --image=nginx
kubectl get pod nginx
kubectl delete pod nginx

# Check etcd health
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  endpoint health
```

---

## 12. Step 8: Kubernetes From Scratch — Worker Node Configuration

```bash
# On each worker node:

# Install containerd and configure (same as section 2)

# Create kubelet config
sudo mkdir -p /etc/kubernetes/manifests /var/lib/kubelet

cat <<EOF | sudo tee /var/lib/kubelet/config.yaml
apiVersion: kubelet.config.k8s.io/v1beta1
kind: KubeletConfiguration
authentication:
  anonymous:
    enabled: false
  webhook:
    enabled: true
  x509:
    clientCAFile: /etc/kubernetes/pki/ca.crt
authorization:
  mode: Webhook
clusterDNS:
- 10.96.0.10
clusterDomain: cluster.local
containerRuntimeEndpoint: unix:///var/run/containerd/containerd.sock
EOF

# Create kubelet systemd service
cat <<EOF | sudo tee /etc/systemd/system/kubelet.service
[Unit]
Description=Kubernetes Kubelet
After=containerd.service

[Service]
ExecStart=/usr/local/bin/kubelet \\
  --config=/var/lib/kubelet/config.yaml \\
  --kubeconfig=/etc/kubernetes/kubelet.conf \\
  --pod-manifest-path=/etc/kubernetes/manifests
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kubelet
```

---

## 13. Step 9: Kubernetes From Scratch — Configure Networking

```bash
# Install Calico CNI
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.26.0/manifests/calico.yaml

# Verify CNI pods are running
kubectl get pods -n kube-system | grep calico

# Test Pod-to-Pod networking
kubectl run pod1 --image=busybox --command -- sleep 3600
kubectl run pod2 --image=busybox --command -- sleep 3600
kubectl get pods -o wide  # note the IPs
kubectl exec pod1 -- ping <pod2-ip>
```

---

## 14. Step 10: Kubernetes From Scratch — API to Kubelet RBAC

The API server connects to each kubelet to execute commands (logs, exec, portforward). This requires RBAC:

```bash
# Create ClusterRole for API server to access kubelets
cat <<EOF | kubectl apply -f -
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRole
metadata:
  name: system:kube-apiserver-to-kubelet
  annotations:
    rbac.authorization.kubernetes.io/autoupdate: "true"
rules:
- apiGroups: [""]
  resources:
  - nodes/proxy
  - nodes/stats
  - nodes/log
  - nodes/spec
  - nodes/metrics
  verbs: ["*"]
---
apiVersion: rbac.authorization.k8s.io/v1
kind: ClusterRoleBinding
metadata:
  name: system:kube-apiserver
subjects:
- apiGroup: rbac.authorization.k8s.io
  kind: User
  name: kube-apiserver
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: system:kube-apiserver-to-kubelet
EOF
```

---

## 15. Step 11: Kubernetes From Scratch — Configuring DNS

CoreDNS provides in-cluster DNS resolution (pod names, service names).

```bash
# Deploy CoreDNS
kubectl apply -f https://raw.githubusercontent.com/coredns/deployment/master/kubernetes/coredns.yaml

# Verify CoreDNS pods
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Test DNS resolution from inside a Pod
kubectl run dns-test --image=busybox --rm -it -- nslookup kubernetes.default
```

---

## 16. Step 12: Kubernetes From Scratch — Kubelet Preferred Address Type

When the API server connects to kubelets, it tries different address types. Configure the preferred type:

```bash
# In kube-apiserver flags:
--kubelet-preferred-address-types=InternalIP,ExternalIP,Hostname

# InternalIP  → use the node's internal IP (preferred in cloud)
# ExternalIP  → use the node's external/public IP
# Hostname    → use the node's hostname (DNS resolution required)
```

---

## 17. Breakdown Learning

### Kubernetes Architecture Summary

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                    CONTROL PLANE                                 │
  │                                                                  │
  │  ┌─────────────┐  ┌──────────────────┐  ┌──────────────────┐    │
  │  │ kube-       │  │ kube-controller- │  │  kube-scheduler  │    │
  │  │ apiserver   │  │ manager          │  │                  │    │
  │  │             │  │                  │  │                  │    │
  │  │ REST API    │  │ ReplicaSet ctrl  │  │ assigns Pods     │    │
  │  │ Auth + RBAC │  │ Deployment ctrl  │  │ to Nodes         │    │
  │  │ Admission   │  │ Node ctrl        │  │                  │    │
  │  └──────┬──────┘  └──────────────────┘  └──────────────────┘    │
  │         │                                                        │
  │  ┌──────▼──────┐                                                 │
  │  │    etcd     │  Key-value store — ALL cluster state            │
  │  └─────────────┘                                                 │
  └──────────────────────────────────────────────────────────────────┘

  ┌──────────────────────────────────────────────────────────────────┐
  │                    WORKER NODES                                  │
  │                                                                  │
  │  ┌─────────────┐  ┌─────────────┐  ┌────────────────────────┐   │
  │  │   kubelet   │  │ kube-proxy  │  │ Container Runtime      │   │
  │  │             │  │             │  │ (containerd / Docker)  │   │
  │  │ Manages Pods│  │ Network     │  │ Runs containers        │   │
  │  │ on this node│  │ rules       │  │                        │   │
  │  └─────────────┘  └─────────────┘  └────────────────────────┘   │
  └──────────────────────────────────────────────────────────────────┘
```

---

## 18. ETCD Backup and Restore

etcd is the only stateful component — back it up regularly.

### Backup

```bash
ETCDCTL_API=3 etcdctl snapshot save /backup/etcd-snapshot.db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# Verify snapshot
ETCDCTL_API=3 etcdctl snapshot status /backup/etcd-snapshot.db --write-out=table
```

### Restore

```bash
# Stop kube-apiserver first (remove from static pod manifests)
sudo mv /etc/kubernetes/manifests/kube-apiserver.yaml /tmp/

# Restore to a new data directory
ETCDCTL_API=3 etcdctl snapshot restore /backup/etcd-snapshot.db \
  --data-dir=/var/lib/etcd-restored \
  --name=master \
  --initial-cluster=master=https://127.0.0.1:2380 \
  --initial-cluster-token=etcd-cluster-new \
  --initial-advertise-peer-urls=https://127.0.0.1:2380

# Update etcd to use new data directory
sudo sed -i 's|/var/lib/etcd|/var/lib/etcd-restored|g' \
  /etc/kubernetes/manifests/etcd.yaml

# Restore kube-apiserver
sudo mv /tmp/kube-apiserver.yaml /etc/kubernetes/manifests/

# Verify cluster is healthy
kubectl get nodes
```

---

## 19. Structure of Network Policy

NetworkPolicy controls **Pod-to-Pod and Pod-to-external traffic**.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: my-policy
  namespace: production
spec:
  podSelector:                        # ← apply to these pods
    matchLabels:
      app: backend

  policyTypes:
  - Ingress                           # ← control incoming traffic
  - Egress                            # ← control outgoing traffic

  ingress:
  - from:
    - podSelector:                    # ← allow from these pods
        matchLabels:
          app: frontend
    - namespaceSelector:              # ← allow from these namespaces
        matchLabels:
          env: production
    ports:
    - protocol: TCP
      port: 8080

  egress:
  - to:
    - podSelector:
        matchLabels:
          app: database
    ports:
    - protocol: TCP
      port: 5432
```

---

## 20. Practical — Network Policies

```bash
# Deny all ingress to a namespace
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: deny-all-ingress
  namespace: production
spec:
  podSelector: {}                     # ← select all pods
  policyTypes:
  - Ingress
  # no ingress rules = deny all
EOF

# Allow ingress only from specific pods
cat <<EOF | kubectl apply -f -
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend
  namespace: production
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          app: frontend
    ports:
    - protocol: TCP
      port: 3000
EOF
```

---

## 21. Network Policies — Except, Port and Protocol

```yaml
# Except: allow all EXCEPT specific pods
ingress:
- from:
  - ipBlock:
      cidr: 10.0.0.0/8
      except:
      - 10.0.0.0/24              # ← exclude this subnet

# Multiple ports
ingress:
- ports:
  - protocol: TCP
    port: 80
  - protocol: TCP
    port: 443
  - protocol: UDP
    port: 53

# Port range (Kubernetes 1.25+)
ingress:
- ports:
  - protocol: TCP
    port: 8000
    endPort: 9000                 # ← allow ports 8000-9000
```

---

## 22. Taints and Tolerations

Taints prevent Pods from being scheduled on nodes unless the Pod has a matching toleration.

```bash
# Add a taint to a node
kubectl taint nodes node1 key=value:NoSchedule
kubectl taint nodes node1 gpu=true:NoSchedule

# Taint effects:
# NoSchedule     → don't schedule new pods here
# PreferNoSchedule → try to avoid, but not guaranteed
# NoExecute      → don't schedule + evict existing pods

# Remove a taint
kubectl taint nodes node1 gpu=true:NoSchedule-     # ← note the trailing -
```

```yaml
# Pod with toleration
apiVersion: v1
kind: Pod
spec:
  tolerations:
  - key: "gpu"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"
  # Or tolerate ANY taint with a key:
  - key: "gpu"
    operator: "Exists"
    effect: "NoSchedule"
```

---

## 23. Custom Resource Definition

CRDs extend the Kubernetes API with custom resources.

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: databases.mycompany.com        # ← <plural>.<group>
spec:
  group: mycompany.com
  versions:
  - name: v1
    served: true
    storage: true
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            properties:
              engine:
                type: string
              size:
                type: string
  scope: Namespaced
  names:
    plural: databases
    singular: database
    kind: Database
    shortNames:
    - db
```

```bash
# After applying the CRD, create instances:
kubectl apply -f database-instance.yaml
kubectl get databases
kubectl get db
```

---

## 24. Editing Existing Kubernetes Resources

```bash
# Edit a resource directly (opens in $EDITOR)
kubectl edit deployment my-app
kubectl edit pod my-pod
kubectl edit configmap my-config

# Patch a resource (non-interactively)
kubectl patch deployment my-app \
  -p '{"spec":{"replicas":3}}'

# Patch with strategic merge
kubectl patch pod my-pod \
  --type=merge \
  -p '{"spec":{"containers":[{"name":"app","image":"nginx:1.26"}]}}'

# Set image directly
kubectl set image deployment/my-app app=nginx:1.26

# Apply changes from file
kubectl apply -f updated-deployment.yaml

# Force-replace (delete and recreate — use carefully)
kubectl replace --force -f pod.yaml
```

---

## 25. Capacity, Allocated, and Allocatable

```bash
# View node capacity and allocatable resources
kubectl describe node node1

# Key sections:
# Capacity:
#   cpu:     4
#   memory:  8Gi
# 
# Allocatable:
#   cpu:     3800m        ← less than Capacity (reserved for OS + kubelet)
#   memory:  7.5Gi
#
# Allocated resources:
#   cpu:     1200m (32%)  ← sum of all pod requests
#   memory:  2Gi  (27%)
```

```
  Capacity     = Total hardware resources on the node
  Allocatable  = Capacity minus reserved for OS and kubelet
  Allocated    = Sum of resource requests of all Pods on node

  A Pod can be scheduled only if:
  Allocatable - Allocated >= Pod's resource requests
```

---

## 26. Exercise — Requests and Limits

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: resource-pod
spec:
  containers:
  - name: app
    image: nginx
    resources:
      requests:
        cpu: "250m"            # ← guaranteed minimum (scheduler uses this)
        memory: "128Mi"
      limits:
        cpu: "500m"            # ← maximum CPU (throttled if exceeded)
        memory: "256Mi"        # ← maximum memory (OOMKilled if exceeded)
```

```
  requests  → what the Pod is guaranteed to get (scheduler decision)
  limits    → what the Pod is capped at (enforced by cgroups)

  CPU exceeded:   throttled (still runs, but slower)
  Memory exceeded: OOMKilled (container is killed and restarted)
```

```bash
# Check resource usage
kubectl top pods
kubectl top nodes

# See resource requests/limits of all pods
kubectl get pods -o custom-columns=\
  'NAME:.metadata.name,CPU-REQ:.spec.containers[0].resources.requests.cpu,MEM-REQ:.spec.containers[0].resources.requests.memory'
```

---

## 27. JSONPath

JSONPath extracts specific fields from kubectl output.

```bash
# Get a single field
kubectl get pod my-pod -o jsonpath='{.status.podIP}'
kubectl get node node1 -o jsonpath='{.status.capacity.cpu}'

# Get from all items in a list
kubectl get pods -o jsonpath='{.items[*].metadata.name}'
kubectl get nodes -o jsonpath='{.items[*].status.addresses[?(@.type=="InternalIP")].address}'

# Multiple fields
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.podIP}{"\n"}{end}'

# Filter: get all containers named "nginx"
kubectl get pods -o jsonpath='{.items[*].spec.containers[?(@.name=="nginx")].image}'

# Sorted output with custom columns
kubectl get pods -o custom-columns=NAME:.metadata.name,STATUS:.status.phase

# Sort by field
kubectl get pods --sort-by=.metadata.creationTimestamp
kubectl get pv --sort-by=.spec.capacity.storage
```

---

## 28. Configuring cri-dockerd

cri-dockerd is an adapter that makes Docker work as a container runtime with Kubernetes (since Docker is no longer directly supported after K8s 1.24).

```bash
# Download cri-dockerd
wget https://github.com/Mirantis/cri-dockerd/releases/download/v0.3.9/cri-dockerd-0.3.9.amd64.tgz
tar -xf cri-dockerd-0.3.9.amd64.tgz
sudo mv cri-dockerd/cri-dockerd /usr/local/bin/

# Create systemd service for cri-dockerd
cat <<EOF | sudo tee /etc/systemd/system/cri-docker.service
[Unit]
Description=CRI Interface for Docker Application Container Engine
After=network-online.target firewalld.service docker.service
Wants=network-online.target

[Service]
Type=notify
ExecStart=/usr/local/bin/cri-dockerd \
  --container-runtime-endpoint fd:// \
  --pod-infra-container-image=registry.k8s.io/pause:3.9
ExecReload=/bin/kill -s HUP $MAINPID
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now cri-docker.service

# Use with kubeadm
sudo kubeadm init \
  --cri-socket unix:///var/run/cri-dockerd.sock \
  --pod-network-cidr=192.168.0.0/16
```

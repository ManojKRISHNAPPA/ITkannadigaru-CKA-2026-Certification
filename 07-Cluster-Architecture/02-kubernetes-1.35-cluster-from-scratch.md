# Kubernetes 1.35 — Complete Cluster Setup From Scratch

> CKA 2026 Course — Cluster Architecture, Installation & Configuration  
> Kubernetes Version: **v1.35.x**  
> Covers: kubeadm method + full manual "hard way" method

---

## Table of Contents

| # | Section |
|---|---------|
| 1 | [What Changed in v1.35 vs v1.32](#1-whats-new--changed-in-v135) |
| 2 | [Infrastructure Requirements](#2-infrastructure-requirements) |
| 3 | [Phase 0 — All Nodes: OS Prep](#3-phase-0--all-nodes-os-preparation) |
| 4 | [Phase 1 — kubeadm Method (Quick Setup)](#4-phase-1--kubeadm-method-quick-cluster-setup) |
| 5 | [Phase 2 — From Scratch: Download Binaries](#5-phase-2--from-scratch-download-v135-binaries) |
| 6 | [Phase 3 — From Scratch: Certificate Authority](#6-phase-3--from-scratch-setup-certificate-authority) |
| 7 | [Phase 4 — From Scratch: Configure etcd](#7-phase-4--from-scratch-configure-etcd) |
| 8 | [Phase 5 — From Scratch: Configure API Server](#8-phase-5--from-scratch-configure-kube-apiserver) |
| 9 | [Phase 6 — From Scratch: Controller Manager](#9-phase-6--from-scratch-configure-controller-manager) |
| 10 | [Phase 7 — From Scratch: Scheduler](#10-phase-7--from-scratch-configure-scheduler) |
| 11 | [Phase 8 — From Scratch: Worker Node](#11-phase-8--from-scratch-configure-worker-node) |
| 12 | [Phase 9 — CNI Networking (Calico v3.29)](#12-phase-9--install-cni-networking-calico-v329) |
| 13 | [Phase 10 — API-to-Kubelet RBAC](#13-phase-10--api-server-to-kubelet-rbac) |
| 14 | [Phase 11 — CoreDNS](#14-phase-11--configure-coredns) |
| 15 | [Validate the Full Cluster](#15-validate-the-full-cluster) |
| 16 | [ETCD Backup & Restore](#16-etcd-backup--restore) |
| 17 | [Upgrading an Existing Cluster to v1.35](#17-upgrading-an-existing-cluster-to-v135) |
| 18 | [Troubleshooting Reference](#18-troubleshooting-reference) |

---

## 1. What's New / Changed in v1.35

Understanding the differences from older versions prevents common setup mistakes.

| Area | Old (v1.32 and earlier) | v1.35 |
|------|-------------------------|-------|
| Package repo | `pkgs.k8s.io/core:/stable:/v1.32/deb/` | `pkgs.k8s.io/core:/stable:/v1.35/deb/` |
| etcd compatibility | v3.5.11–v3.5.13 | v3.5.17+ |
| containerd | v1.7.x (min v1.6) | v2.0.x recommended (min v1.7.13) |
| pause image | `registry.k8s.io/pause:3.9` | `registry.k8s.io/pause:3.10` |
| Calico CNI | v3.26 | v3.29+ |
| `--allow-privileged` flag | Supported on API server | **Deprecated — remove from service file** |
| `KubeletConfiguration` API | `kubelet.config.k8s.io/v1beta1` | `kubelet.config.k8s.io/v1beta1` (unchanged) |
| Scheduler config API | `kubescheduler.config.k8s.io/v1` | `kubescheduler.config.k8s.io/v1` (unchanged) |
| `ServiceAccount` token signing | `--service-account-signing-key-file` required | Same, still required |
| Container runtime socket | `/var/run/containerd/containerd.sock` | Same |
| cgroup driver | `systemd` (recommended) | `systemd` (required for systemd-based OS) |

### Key version pins for this guide

```
Kubernetes:  v1.35.0
etcd:        v3.5.17
containerd:  v2.0.4
Calico:      v3.29.0
pause image: registry.k8s.io/pause:3.10
```

---

## 2. Infrastructure Requirements

### Minimum Node Specs

| Role | CPU | RAM | Disk | Count |
|------|-----|-----|------|-------|
| Control Plane (master) | 2 vCPU | 2 GB | 20 GB | 1 (3 for HA) |
| Worker Node | 1 vCPU | 1 GB | 20 GB | 1+ |

### Network Requirements

```
Each node must have:
  - A static IP address (or stable DHCP reservation)
  - Unique hostname  (hostnamectl set-hostname <name>)
  - Full network connectivity between all nodes
  - Internet access (to pull images and binaries)

Ports to open (firewall rules):

Control Plane:
  TCP 6443      — Kubernetes API server
  TCP 2379-2380 — etcd server client + peer
  TCP 10250     — Kubelet API
  TCP 10257     — kube-controller-manager
  TCP 10259     — kube-scheduler

Worker Nodes:
  TCP 10250     — Kubelet API
  TCP 30000-32767 — NodePort services
```

### Set Hostnames (on each node)

```bash
# On control plane node
sudo hostnamectl set-hostname k8s-master

# On worker node 1
sudo hostnamectl set-hostname k8s-worker-1

# On worker node 2
sudo hostnamectl set-hostname k8s-worker-2

# Add all nodes to /etc/hosts on EVERY node
sudo tee -a /etc/hosts <<EOF
192.168.1.10  k8s-master
192.168.1.11  k8s-worker-1
192.168.1.12  k8s-worker-2
EOF
```

---

## 3. Phase 0 — All Nodes: OS Preparation

Run these steps on **every node** (master + workers) before installing Kubernetes.

### Step 1 — Disable Swap

Kubernetes 1.35 requires swap to be disabled (hard requirement).

```bash
# Disable swap immediately
sudo swapoff -a

# Permanently disable swap (comment out swap entry in fstab)
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

# Verify swap is completely off
free -h
# Expected: Swap: 0B  0B  0B
```

### Step 2 — Load Required Kernel Modules

```bash
# Create module config file
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

# Load modules now (without reboot)
sudo modprobe overlay
sudo modprobe br_netfilter

# Verify they are loaded
lsmod | grep br_netfilter
lsmod | grep overlay
```

### Step 3 — Configure sysctl (Kernel Network Parameters)

```bash
# Apply Kubernetes required sysctl settings
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
# Allow IP forwarding between network interfaces (Pod-to-Pod traffic)
net.ipv4.ip_forward = 1

# Apply iptables rules to bridged traffic (required for kube-proxy / CNI)
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
EOF

# Apply settings immediately (no reboot needed)
sudo sysctl --system

# Verify
sysctl net.ipv4.ip_forward
# Expected: net.ipv4.ip_forward = 1
sysctl net.bridge.bridge-nf-call-iptables
# Expected: net.bridge.bridge-nf-call-iptables = 1
```

### Step 4 — Install containerd v2.0.x (Container Runtime)

Kubernetes 1.35 requires a CRI-compatible container runtime. containerd v2.0 is recommended.

```bash
# Install dependencies
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Add Docker's official GPG key (containerd is distributed via Docker repo)
sudo install -m 0755 -d /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
  sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg
sudo chmod a+r /etc/apt/keyrings/docker.gpg

# Add Docker apt repository
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(. /etc/os-release && echo "$VERSION_CODENAME") stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list

# Install containerd
sudo apt-get update
sudo apt-get install -y containerd.io

# Check version (must be 2.0.x or 1.7.13+)
containerd --version
```

### Step 5 — Configure containerd for Kubernetes

```bash
# Generate default config
sudo mkdir -p /etc/containerd
sudo containerd config default | sudo tee /etc/containerd/config.toml

# CRITICAL: Enable SystemdCgroup driver
# This MUST match the kubelet's cgroupDriver setting
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' \
  /etc/containerd/config.toml

# Update pause image to v3.10 (new for K8s 1.35)
sudo sed -i 's|registry.k8s.io/pause:3.9|registry.k8s.io/pause:3.10|g' \
  /etc/containerd/config.toml

# Verify the changes
grep -E 'SystemdCgroup|sandbox_image' /etc/containerd/config.toml

# Restart and enable containerd
sudo systemctl restart containerd
sudo systemctl enable containerd

# Confirm it's running
sudo systemctl status containerd --no-pager
```

---

## 4. Phase 1 — kubeadm Method (Quick Cluster Setup)

> Use this if you want the fastest path to a working cluster.  
> Skip to [Phase 2](#5-phase-2--from-scratch-download-v135-binaries) for the full manual "hard way" approach.

### Install kubeadm, kubelet, kubectl (v1.35)

```bash
# Add Kubernetes v1.35 signing key
curl -fsSL https://pkgs.k8s.io/core:/stable:/v1.35/deb/Release.key | \
  sudo gpg --dearmor -o /etc/apt/keyrings/kubernetes-apt-keyring.gpg

# Add Kubernetes v1.35 apt repository
echo 'deb [signed-by=/etc/apt/keyrings/kubernetes-apt-keyring.gpg] \
  https://pkgs.k8s.io/core:/stable:/v1.35/deb/ /' | \
  sudo tee /etc/apt/sources.list.d/kubernetes.list

# Install all three tools
sudo apt-get update
sudo apt-get install -y kubelet kubeadm kubectl

# Pin versions — prevents accidental upgrade
sudo apt-mark hold kubelet kubeadm kubectl

# Verify installed versions
kubeadm version
kubectl version --client
kubelet --version
```

### Initialize Control Plane (Master Node Only)

```bash
# Pull required images first (optional but avoids timeout during init)
sudo kubeadm config images pull --kubernetes-version=v1.35.0

# Initialize the control plane
# --pod-network-cidr=192.168.0.0/16 is for Calico CNI
sudo kubeadm init \
  --kubernetes-version=v1.35.0 \
  --pod-network-cidr=192.168.0.0/16 \
  --apiserver-advertise-address=<MASTER_IP> \
  --cri-socket=unix:///var/run/containerd/containerd.sock

# --- SAVE THE JOIN COMMAND OUTPUT ---
# kubeadm init prints something like:
# kubeadm join 192.168.1.10:6443 --token xxxx --discovery-token-ca-cert-hash sha256:yyyy
```

### Configure kubectl Access

```bash
# For a non-root user (recommended)
mkdir -p $HOME/.kube
sudo cp -i /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config

# For root user
export KUBECONFIG=/etc/kubernetes/admin.conf
echo 'export KUBECONFIG=/etc/kubernetes/admin.conf' >> ~/.bashrc
```

### Install Calico CNI (v3.29)

```bash
# Install Calico v3.29 (required for K8s 1.35 support)
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.29.0/manifests/tigera-operator.yaml

# Apply Calico custom resources
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.29.0/manifests/custom-resources.yaml

# Wait for Calico pods to be Running
kubectl get pods -n calico-system -w

# Wait for nodes to become Ready
kubectl get nodes -w
# Expected: k8s-master   Ready   control-plane   2m
```

### Join Worker Nodes

Run this on each worker node (use the join command from kubeadm init output):

```bash
# On each worker node — run the join command saved earlier
sudo kubeadm join 192.168.1.10:6443 \
  --token <token-from-init> \
  --discovery-token-ca-cert-hash sha256:<hash-from-init>

# If token expired (tokens expire after 24h), generate a new one from master:
kubeadm token create --print-join-command
```

### Verify kubeadm Cluster

```bash
# From master node — all nodes should be Ready
kubectl get nodes -o wide

# All system pods should be Running
kubectl get pods -n kube-system

# Test with a simple pod
kubectl run nginx --image=nginx:1.27
kubectl get pod nginx
kubectl delete pod nginx
```

---

## 5. Phase 2 — From Scratch: Download v1.35 Binaries

> This section builds a Kubernetes cluster manually without kubeadm.  
> This is the "Kubernetes The Hard Way" approach — teaches every component.

### Set Version Variables

```bash
# Set these on every terminal session or add to ~/.bashrc
export K8S_VERSION="v1.35.0"
export ETCD_VERSION="v3.5.17"
export ARCH="amd64"

# Verify variables
echo "K8S: $K8S_VERSION | ETCD: $ETCD_VERSION"
```

### Download Kubernetes Control Plane Binaries

```bash
# Create a working directory
mkdir -p ~/k8s-binaries && cd ~/k8s-binaries

# Download all control plane binaries
wget -q --show-progress --timestamping \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kube-apiserver" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kube-controller-manager" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kube-scheduler" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kubectl"

# Download worker node binaries
wget -q --show-progress --timestamping \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kubelet" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kube-proxy"

# Verify checksums (recommended)
wget -q "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kube-apiserver.sha256"
echo "$(cat kube-apiserver.sha256)  kube-apiserver" | sha256sum --check

# Make all binaries executable
chmod +x kube-apiserver kube-controller-manager kube-scheduler \
         kubectl kubelet kube-proxy

# Install to system PATH
sudo mv kube-apiserver kube-controller-manager kube-scheduler \
        kubectl kubelet kube-proxy \
        /usr/local/bin/

# Verify installation
kubectl version --client
kubelet --version
kube-apiserver --version
```

### Download etcd v3.5.17

```bash
cd ~/k8s-binaries

# Download etcd
wget -q --show-progress \
  "https://github.com/etcd-io/etcd/releases/download/${ETCD_VERSION}/etcd-${ETCD_VERSION}-linux-${ARCH}.tar.gz"

# Extract
tar -xf etcd-${ETCD_VERSION}-linux-${ARCH}.tar.gz

# Install etcd and etcdctl
sudo mv etcd-${ETCD_VERSION}-linux-${ARCH}/etcd \
        etcd-${ETCD_VERSION}-linux-${ARCH}/etcdctl \
        /usr/local/bin/

# Verify
etcd --version
etcdctl version
```

---

## 6. Phase 3 — From Scratch: Setup Certificate Authority

All Kubernetes components communicate over TLS. We need to generate:
- Cluster CA (signs all component certs)
- etcd CA (signs etcd peer and client certs)
- API server certificate
- Service Account key pair
- Additional certs for each component

### Create PKI Directory Structure

```bash
sudo mkdir -p /etc/kubernetes/pki/etcd
sudo chmod 700 /etc/kubernetes/pki
```

### Generate Cluster CA

```bash
# Cluster CA — private key
sudo openssl genrsa -out /etc/kubernetes/pki/ca.key 2048

# Cluster CA — self-signed certificate (10-year validity)
sudo openssl req -new -x509 -days 3650 \
  -key /etc/kubernetes/pki/ca.key \
  -out /etc/kubernetes/pki/ca.crt \
  -subj "/CN=kubernetes-ca/O=Kubernetes"

# Verify
sudo openssl x509 -in /etc/kubernetes/pki/ca.crt -text -noout | grep -E 'Subject:|Issuer:|Not'
```

### Generate etcd CA

```bash
# etcd CA — private key
sudo openssl genrsa -out /etc/kubernetes/pki/etcd/ca.key 2048

# etcd CA — self-signed certificate
sudo openssl req -new -x509 -days 3650 \
  -key /etc/kubernetes/pki/etcd/ca.key \
  -out /etc/kubernetes/pki/etcd/ca.crt \
  -subj "/CN=etcd-ca/O=etcd"
```

### Generate etcd Server Certificate

```bash
# etcd server certificate extensions
cat > /tmp/etcd-server-ext.conf <<EOF
[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name
[req_distinguished_name]
[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names
[alt_names]
DNS.1 = localhost
DNS.2 = k8s-master
IP.1 = 127.0.0.1
IP.2 = <MASTER_IP>
EOF

# Generate key and CSR
sudo openssl genrsa -out /etc/kubernetes/pki/etcd/server.key 2048
sudo openssl req -new \
  -key /etc/kubernetes/pki/etcd/server.key \
  -out /tmp/etcd-server.csr \
  -subj "/CN=etcd-server" \
  -config /tmp/etcd-server-ext.conf

# Sign with etcd CA
sudo openssl x509 -req \
  -in /tmp/etcd-server.csr \
  -CA /etc/kubernetes/pki/etcd/ca.crt \
  -CAkey /etc/kubernetes/pki/etcd/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/etcd/server.crt \
  -days 3650 \
  -extensions v3_req \
  -extfile /tmp/etcd-server-ext.conf
```

### Generate etcd Peer Certificate

```bash
cat > /tmp/etcd-peer-ext.conf <<EOF
[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name
[req_distinguished_name]
[v3_req]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
extendedKeyUsage = serverAuth, clientAuth
subjectAltName = @alt_names
[alt_names]
DNS.1 = localhost
DNS.2 = k8s-master
IP.1 = 127.0.0.1
IP.2 = <MASTER_IP>
EOF

sudo openssl genrsa -out /etc/kubernetes/pki/etcd/peer.key 2048
sudo openssl req -new \
  -key /etc/kubernetes/pki/etcd/peer.key \
  -out /tmp/etcd-peer.csr \
  -subj "/CN=etcd-peer" \
  -config /tmp/etcd-peer-ext.conf

sudo openssl x509 -req \
  -in /tmp/etcd-peer.csr \
  -CA /etc/kubernetes/pki/etcd/ca.crt \
  -CAkey /etc/kubernetes/pki/etcd/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/etcd/peer.crt \
  -days 3650 \
  -extensions v3_req \
  -extfile /tmp/etcd-peer-ext.conf
```

### Generate API Server Certificate

```bash
# API server needs SANs for all IPs and DNS names clients use to reach it
cat > /tmp/apiserver-ext.conf <<EOF
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
DNS.5 = k8s-master
IP.1 = 10.96.0.1        # ClusterIP of the "kubernetes" Service
IP.2 = <MASTER_IP>      # Actual node IP — replace this
IP.3 = 127.0.0.1
EOF

sudo openssl genrsa -out /etc/kubernetes/pki/apiserver.key 2048
sudo openssl req -new \
  -key /etc/kubernetes/pki/apiserver.key \
  -out /tmp/apiserver.csr \
  -subj "/CN=kube-apiserver" \
  -config /tmp/apiserver-ext.conf

sudo openssl x509 -req \
  -in /tmp/apiserver.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/apiserver.crt \
  -days 3650 \
  -extensions v3_req \
  -extfile /tmp/apiserver-ext.conf
```

### Generate API Server to etcd Client Certificate

```bash
sudo openssl genrsa -out /etc/kubernetes/pki/apiserver-etcd-client.key 2048
sudo openssl req -new \
  -key /etc/kubernetes/pki/apiserver-etcd-client.key \
  -out /tmp/apiserver-etcd-client.csr \
  -subj "/CN=kube-apiserver-etcd-client/O=system:masters"

sudo openssl x509 -req \
  -in /tmp/apiserver-etcd-client.csr \
  -CA /etc/kubernetes/pki/etcd/ca.crt \
  -CAkey /etc/kubernetes/pki/etcd/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/apiserver-etcd-client.crt \
  -days 3650
```

### Generate API Server to Kubelet Client Certificate

```bash
sudo openssl genrsa -out /etc/kubernetes/pki/apiserver-kubelet-client.key 2048
sudo openssl req -new \
  -key /etc/kubernetes/pki/apiserver-kubelet-client.key \
  -out /tmp/apiserver-kubelet-client.csr \
  -subj "/CN=kube-apiserver-kubelet-client/O=system:masters"

sudo openssl x509 -req \
  -in /tmp/apiserver-kubelet-client.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/apiserver-kubelet-client.crt \
  -days 3650
```

### Generate Service Account Key Pair

```bash
# SA key pair is used for signing/verifying ServiceAccount tokens
sudo openssl genrsa -out /etc/kubernetes/pki/sa.key 2048
sudo openssl rsa -in /etc/kubernetes/pki/sa.key \
  -pubout -out /etc/kubernetes/pki/sa.pub

# Verify
sudo ls -la /etc/kubernetes/pki/
```

### Generate Admin kubeconfig

```bash
# Admin client certificate
sudo openssl genrsa -out /etc/kubernetes/pki/admin.key 2048
sudo openssl req -new \
  -key /etc/kubernetes/pki/admin.key \
  -out /tmp/admin.csr \
  -subj "/CN=kubernetes-admin/O=system:masters"

sudo openssl x509 -req \
  -in /tmp/admin.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/admin.crt \
  -days 3650

# Build the kubeconfig file (replace <MASTER_IP>)
MASTER_IP="<MASTER_IP>"
CA_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/ca.crt)
CERT_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/admin.crt)
KEY_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/admin.key)

sudo tee /etc/kubernetes/admin.conf <<EOF
apiVersion: v1
kind: Config
clusters:
- cluster:
    certificate-authority-data: ${CA_DATA}
    server: https://${MASTER_IP}:6443
  name: kubernetes
contexts:
- context:
    cluster: kubernetes
    user: kubernetes-admin
  name: kubernetes-admin@kubernetes
current-context: kubernetes-admin@kubernetes
users:
- name: kubernetes-admin
  user:
    client-certificate-data: ${CERT_DATA}
    client-key-data: ${KEY_DATA}
EOF

# Set up kubectl access
mkdir -p $HOME/.kube
sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

---

## 7. Phase 4 — From Scratch: Configure etcd

etcd is the distributed key-value store that holds **all** cluster state.

### Verify etcd Installation

```bash
etcd --version
# Expected: etcd Version: 3.5.17

etcdctl version
# Expected: etcdctl version: 3.5.17
```

### Create etcd Data Directory

```bash
sudo mkdir -p /var/lib/etcd
sudo chmod 700 /var/lib/etcd
```

### Create etcd systemd Service

```bash
# Replace <MASTER_IP> with your actual master node IP
MASTER_IP="192.168.1.10"    # ← change this

sudo tee /etc/systemd/system/etcd.service <<EOF
[Unit]
Description=etcd key-value store
Documentation=https://github.com/etcd-io/etcd
After=network.target

[Service]
Type=notify
User=root
ExecStart=/usr/local/bin/etcd \\
  --name=k8s-master \\
  --cert-file=/etc/kubernetes/pki/etcd/server.crt \\
  --key-file=/etc/kubernetes/pki/etcd/server.key \\
  --peer-cert-file=/etc/kubernetes/pki/etcd/peer.crt \\
  --peer-key-file=/etc/kubernetes/pki/etcd/peer.key \\
  --trusted-ca-file=/etc/kubernetes/pki/etcd/ca.crt \\
  --peer-trusted-ca-file=/etc/kubernetes/pki/etcd/ca.crt \\
  --peer-client-cert-auth=true \\
  --client-cert-auth=true \\
  --initial-advertise-peer-urls=https://${MASTER_IP}:2380 \\
  --listen-peer-urls=https://${MASTER_IP}:2380 \\
  --listen-client-urls=https://${MASTER_IP}:2379,https://127.0.0.1:2379 \\
  --advertise-client-urls=https://${MASTER_IP}:2379 \\
  --initial-cluster-token=etcd-cluster-0 \\
  --initial-cluster=k8s-master=https://${MASTER_IP}:2380 \\
  --initial-cluster-state=new \\
  --data-dir=/var/lib/etcd \\
  --logger=zap
Restart=on-failure
RestartSec=5
LimitNOFILE=40000

[Install]
WantedBy=multi-user.target
EOF

# Start etcd
sudo systemctl daemon-reload
sudo systemctl enable --now etcd

# Verify etcd health
sudo systemctl status etcd --no-pager

# Test with etcdctl
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  endpoint health

# Expected: 127.0.0.1:2379 is healthy: successfully committed proposal: took = Xms
```

---

## 8. Phase 5 — From Scratch: Configure kube-apiserver

The API server is the central hub — all components talk through it.

> **v1.35 change:** `--allow-privileged` flag is deprecated. Do NOT include it in the service file.

```bash
MASTER_IP="192.168.1.10"    # ← change this

sudo tee /etc/systemd/system/kube-apiserver.service <<EOF
[Unit]
Description=Kubernetes API Server
Documentation=https://kubernetes.io/docs/
After=etcd.service
Requires=etcd.service

[Service]
ExecStart=/usr/local/bin/kube-apiserver \\
  --advertise-address=${MASTER_IP} \\
  --authorization-mode=Node,RBAC \\
  --bind-address=0.0.0.0 \\
  --client-ca-file=/etc/kubernetes/pki/ca.crt \\
  --enable-admission-plugins=NodeRestriction \\
  --etcd-cafile=/etc/kubernetes/pki/etcd/ca.crt \\
  --etcd-certfile=/etc/kubernetes/pki/apiserver-etcd-client.crt \\
  --etcd-keyfile=/etc/kubernetes/pki/apiserver-etcd-client.key \\
  --etcd-servers=https://127.0.0.1:2379 \\
  --kubelet-client-certificate=/etc/kubernetes/pki/apiserver-kubelet-client.crt \\
  --kubelet-client-key=/etc/kubernetes/pki/apiserver-kubelet-client.key \\
  --kubelet-preferred-address-types=InternalIP,ExternalIP,Hostname \\
  --proxy-client-cert-file=/etc/kubernetes/pki/apiserver.crt \\
  --proxy-client-key-file=/etc/kubernetes/pki/apiserver.key \\
  --runtime-config=api/all=true \\
  --secure-port=6443 \\
  --service-account-issuer=https://kubernetes.default.svc.cluster.local \\
  --service-account-key-file=/etc/kubernetes/pki/sa.pub \\
  --service-account-signing-key-file=/etc/kubernetes/pki/sa.key \\
  --service-cluster-ip-range=10.96.0.0/12 \\
  --tls-cert-file=/etc/kubernetes/pki/apiserver.crt \\
  --tls-private-key-file=/etc/kubernetes/pki/apiserver.key \\
  --v=2
Restart=on-failure
RestartSec=5
LimitNOFILE=65536

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kube-apiserver

# Verify
sudo systemctl status kube-apiserver --no-pager

# Test API server is responding
curl -k https://127.0.0.1:6443/healthz
# Expected: ok
```

---

## 9. Phase 6 — From Scratch: Configure Controller Manager

The controller manager runs all the built-in control loops (ReplicaSet, Deployment, Node, etc.)

### Generate Controller Manager kubeconfig

```bash
MASTER_IP="192.168.1.10"    # ← change this

# Controller manager client certificate
sudo openssl genrsa -out /etc/kubernetes/pki/controller-manager.key 2048
sudo openssl req -new \
  -key /etc/kubernetes/pki/controller-manager.key \
  -out /tmp/controller-manager.csr \
  -subj "/CN=system:kube-controller-manager"

sudo openssl x509 -req \
  -in /tmp/controller-manager.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/controller-manager.crt \
  -days 3650

# Build controller-manager kubeconfig
CA_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/ca.crt)
CERT_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/controller-manager.crt)
KEY_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/controller-manager.key)

sudo tee /etc/kubernetes/controller-manager.conf <<EOF
apiVersion: v1
kind: Config
clusters:
- cluster:
    certificate-authority-data: ${CA_DATA}
    server: https://${MASTER_IP}:6443
  name: kubernetes
contexts:
- context:
    cluster: kubernetes
    user: system:kube-controller-manager
  name: system:kube-controller-manager@kubernetes
current-context: system:kube-controller-manager@kubernetes
users:
- name: system:kube-controller-manager
  user:
    client-certificate-data: ${CERT_DATA}
    client-key-data: ${KEY_DATA}
EOF
```

### Create Controller Manager Service

```bash
sudo tee /etc/systemd/system/kube-controller-manager.service <<EOF
[Unit]
Description=Kubernetes Controller Manager
Documentation=https://kubernetes.io/docs/
After=kube-apiserver.service

[Service]
ExecStart=/usr/local/bin/kube-controller-manager \\
  --bind-address=0.0.0.0 \\
  --cluster-cidr=192.168.0.0/16 \\
  --cluster-name=kubernetes \\
  --cluster-signing-cert-file=/etc/kubernetes/pki/ca.crt \\
  --cluster-signing-key-file=/etc/kubernetes/pki/ca.key \\
  --cluster-signing-duration=87600h \\
  --kubeconfig=/etc/kubernetes/controller-manager.conf \\
  --leader-elect=true \\
  --root-ca-file=/etc/kubernetes/pki/ca.crt \\
  --service-account-private-key-file=/etc/kubernetes/pki/sa.key \\
  --service-cluster-ip-range=10.96.0.0/12 \\
  --use-service-account-credentials=true \\
  --v=2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kube-controller-manager

# Verify
sudo systemctl status kube-controller-manager --no-pager
```

---

## 10. Phase 7 — From Scratch: Configure Scheduler

The scheduler assigns Pods to Nodes based on resource availability and constraints.

### Generate Scheduler kubeconfig

```bash
MASTER_IP="192.168.1.10"    # ← change this

sudo openssl genrsa -out /etc/kubernetes/pki/scheduler.key 2048
sudo openssl req -new \
  -key /etc/kubernetes/pki/scheduler.key \
  -out /tmp/scheduler.csr \
  -subj "/CN=system:kube-scheduler"

sudo openssl x509 -req \
  -in /tmp/scheduler.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/scheduler.crt \
  -days 3650

CA_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/ca.crt)
CERT_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/scheduler.crt)
KEY_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/scheduler.key)

sudo tee /etc/kubernetes/scheduler.conf <<EOF
apiVersion: v1
kind: Config
clusters:
- cluster:
    certificate-authority-data: ${CA_DATA}
    server: https://${MASTER_IP}:6443
  name: kubernetes
contexts:
- context:
    cluster: kubernetes
    user: system:kube-scheduler
  name: system:kube-scheduler@kubernetes
current-context: system:kube-scheduler@kubernetes
users:
- name: system:kube-scheduler
  user:
    client-certificate-data: ${CERT_DATA}
    client-key-data: ${KEY_DATA}
EOF
```

### Create Scheduler Config File

```bash
# KubeSchedulerConfiguration v1 is stable in K8s 1.35
sudo tee /etc/kubernetes/scheduler-config.yaml <<EOF
apiVersion: kubescheduler.config.k8s.io/v1
kind: KubeSchedulerConfiguration
clientConnection:
  kubeconfig: /etc/kubernetes/scheduler.conf
leaderElection:
  leaderElect: true
EOF
```

### Create Scheduler Service

```bash
sudo tee /etc/systemd/system/kube-scheduler.service <<EOF
[Unit]
Description=Kubernetes Scheduler
Documentation=https://kubernetes.io/docs/
After=kube-apiserver.service

[Service]
ExecStart=/usr/local/bin/kube-scheduler \\
  --config=/etc/kubernetes/scheduler-config.yaml \\
  --v=2
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kube-scheduler

# Verify all control plane services
sudo systemctl status kube-apiserver kube-controller-manager kube-scheduler --no-pager
```

### Quick Control Plane Health Check

```bash
# Check API server health endpoints
curl -k https://127.0.0.1:6443/healthz
curl -k https://127.0.0.1:6443/readyz
curl -k https://127.0.0.1:6443/livez

# Check component statuses (deprecated but still works in v1.35)
kubectl get componentstatuses

# Preferred way — check readyz verbose
kubectl get --raw='/readyz?verbose'
```

---

## 11. Phase 8 — From Scratch: Configure Worker Node

Run these steps on each worker node.

### Copy Required Certificates to Worker Node

```bash
# On master node — copy certs to worker
# (In production, use SSH or a secrets manager)
WORKER_IP="192.168.1.11"    # ← worker node IP

scp /etc/kubernetes/pki/ca.crt ubuntu@${WORKER_IP}:/tmp/ca.crt

# On worker node — put certs in place
sudo mkdir -p /etc/kubernetes/pki
sudo mv /tmp/ca.crt /etc/kubernetes/pki/ca.crt
```

### Generate Kubelet Client Certificate (per worker node)

Do this on the **master node** for each worker, then copy the certs over.

```bash
NODE_NAME="k8s-worker-1"    # ← must match worker's hostname
NODE_IP="192.168.1.11"

# Generate key and CSR
sudo openssl genrsa -out /etc/kubernetes/pki/${NODE_NAME}.key 2048
sudo openssl req -new \
  -key /etc/kubernetes/pki/${NODE_NAME}.key \
  -out /tmp/${NODE_NAME}.csr \
  -subj "/CN=system:node:${NODE_NAME}/O=system:nodes"

# Sign with cluster CA
sudo openssl x509 -req \
  -in /tmp/${NODE_NAME}.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/${NODE_NAME}.crt \
  -days 3650

# Copy to worker node
scp /etc/kubernetes/pki/${NODE_NAME}.crt \
    /etc/kubernetes/pki/${NODE_NAME}.key \
    ubuntu@${NODE_IP}:/tmp/
```

### Create Kubelet kubeconfig (on each worker)

```bash
# On worker node
NODE_NAME=$(hostname)   # must match what was used for the cert CN
MASTER_IP="192.168.1.10"

sudo mkdir -p /etc/kubernetes/pki
sudo mv /tmp/${NODE_NAME}.crt /etc/kubernetes/pki/kubelet.crt
sudo mv /tmp/${NODE_NAME}.key /etc/kubernetes/pki/kubelet.key

CA_DATA=$(base64 -w0 /etc/kubernetes/pki/ca.crt)
CERT_DATA=$(base64 -w0 /etc/kubernetes/pki/kubelet.crt)
KEY_DATA=$(base64 -w0 /etc/kubernetes/pki/kubelet.key)

sudo tee /etc/kubernetes/kubelet.conf <<EOF
apiVersion: v1
kind: Config
clusters:
- cluster:
    certificate-authority-data: ${CA_DATA}
    server: https://${MASTER_IP}:6443
  name: kubernetes
contexts:
- context:
    cluster: kubernetes
    user: system:node:${NODE_NAME}
  name: system:node:${NODE_NAME}@kubernetes
current-context: system:node:${NODE_NAME}@kubernetes
users:
- name: system:node:${NODE_NAME}
  user:
    client-certificate-data: ${CERT_DATA}
    client-key-data: ${KEY_DATA}
EOF
```

### Create Kubelet Configuration

```bash
sudo mkdir -p /var/lib/kubelet /etc/kubernetes/manifests

sudo tee /var/lib/kubelet/config.yaml <<EOF
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
cgroupDriver: systemd
clusterDNS:
- 10.96.0.10
clusterDomain: cluster.local
containerRuntimeEndpoint: unix:///var/run/containerd/containerd.sock
eventRecordQPS: 5
maxPods: 110
podManifestPath: /etc/kubernetes/manifests
resolvConf: /run/systemd/resolve/resolv.conf
rotateCertificates: true
serializeImagePulls: false
staticPodPath: /etc/kubernetes/manifests
EOF
```

### Create Kubelet systemd Service

```bash
sudo tee /etc/systemd/system/kubelet.service <<EOF
[Unit]
Description=Kubernetes Kubelet
Documentation=https://kubernetes.io/docs/
After=containerd.service
Requires=containerd.service

[Service]
ExecStart=/usr/local/bin/kubelet \\
  --config=/var/lib/kubelet/config.yaml \\
  --kubeconfig=/etc/kubernetes/kubelet.conf \\
  --node-ip=$(hostname -I | awk '{print $1}') \\
  --v=2
Restart=always
RestartSec=5
StartLimitInterval=0

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kubelet

# Check kubelet status
sudo systemctl status kubelet --no-pager
sudo journalctl -u kubelet -n 50 --no-pager
```

### Create kube-proxy Configuration

```bash
# On master: create kube-proxy kubeconfig
MASTER_IP="192.168.1.10"

sudo openssl genrsa -out /etc/kubernetes/pki/kube-proxy.key 2048
sudo openssl req -new \
  -key /etc/kubernetes/pki/kube-proxy.key \
  -out /tmp/kube-proxy.csr \
  -subj "/CN=system:kube-proxy"

sudo openssl x509 -req \
  -in /tmp/kube-proxy.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/kube-proxy.crt \
  -days 3650

CA_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/ca.crt)
CERT_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/kube-proxy.crt)
KEY_DATA=$(sudo base64 -w0 /etc/kubernetes/pki/kube-proxy.key)

sudo tee /etc/kubernetes/kube-proxy.conf <<EOF
apiVersion: v1
kind: Config
clusters:
- cluster:
    certificate-authority-data: ${CA_DATA}
    server: https://${MASTER_IP}:6443
  name: kubernetes
contexts:
- context:
    cluster: kubernetes
    user: system:kube-proxy
  name: system:kube-proxy@kubernetes
current-context: system:kube-proxy@kubernetes
users:
- name: system:kube-proxy
  user:
    client-certificate-data: ${CERT_DATA}
    client-key-data: ${KEY_DATA}
EOF

# Copy to worker, then on worker:
sudo tee /etc/systemd/system/kube-proxy.service <<EOF
[Unit]
Description=Kubernetes Kube Proxy
After=network.target

[Service]
ExecStart=/usr/local/bin/kube-proxy \\
  --config=/var/lib/kube-proxy/config.yaml
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo mkdir -p /var/lib/kube-proxy
sudo tee /var/lib/kube-proxy/config.yaml <<EOF
apiVersion: kubeproxy.config.k8s.io/v1alpha1
kind: KubeProxyConfiguration
clientConnection:
  kubeconfig: /etc/kubernetes/kube-proxy.conf
mode: iptables
clusterCIDR: 192.168.0.0/16
EOF

sudo systemctl daemon-reload
sudo systemctl enable --now kube-proxy
```

---

## 12. Phase 9 — Install CNI Networking (Calico v3.29)

Without a CNI plugin, Pods cannot communicate with each other.

### Install Calico v3.29 Operator Method

```bash
# Install Tigera Calico operator
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.29.0/manifests/tigera-operator.yaml

# Check operator is running
kubectl get pods -n tigera-operator -w

# Create Calico Installation resource
kubectl create -f - <<EOF
apiVersion: operator.tigera.io/v1
kind: Installation
metadata:
  name: default
spec:
  calicoNetwork:
    ipPools:
    - blockSize: 26
      cidr: 192.168.0.0/16
      encapsulation: VXLANCrossSubnet
      natOutgoing: Enabled
      nodeSelector: all()
EOF

# Watch Calico pods come up
kubectl get pods -n calico-system -w

# All nodes should become Ready once CNI is installed
kubectl get nodes -w
```

### Alternative: Calico v3.29 Manifest Method (simpler)

```bash
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.29.0/manifests/calico.yaml

# Wait for all calico pods to be Running
kubectl rollout status daemonset/calico-node -n kube-system
```

### Verify Pod-to-Pod Networking

```bash
# Test networking with two pods
kubectl run pod1 --image=busybox --command -- sleep 3600
kubectl run pod2 --image=busybox --command -- sleep 3600

# Get pod IPs
kubectl get pods -o wide

# Test connectivity between pods
POD2_IP=$(kubectl get pod pod2 -o jsonpath='{.status.podIP}')
kubectl exec pod1 -- ping -c 3 ${POD2_IP}

# Cleanup
kubectl delete pod pod1 pod2
```

---

## 13. Phase 10 — API Server to Kubelet RBAC

The API server needs RBAC permissions to execute commands on kubelets (`exec`, `logs`, `port-forward`).

```bash
kubectl apply -f - <<EOF
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

# Verify RBAC is applied
kubectl get clusterrolebinding system:kube-apiserver
```

---

## 14. Phase 11 — Configure CoreDNS

CoreDNS provides in-cluster DNS — allows pods to resolve `service-name.namespace.svc.cluster.local`.

### Deploy CoreDNS

```bash
# CoreDNS 1.12.x is compatible with Kubernetes 1.35
kubectl apply -f https://raw.githubusercontent.com/coredns/deployment/master/kubernetes/coredns.yaml.sed | \
  CLUSTER_DNS_IP=10.96.0.10 \
  CLUSTER_DOMAIN=cluster.local \
  envsubst | kubectl apply -f -

# Or use the ConfigMap approach:
kubectl apply -f - <<EOF
apiVersion: v1
kind: ConfigMap
metadata:
  name: coredns
  namespace: kube-system
data:
  Corefile: |
    .:53 {
        errors
        health {
           lameduck 5s
        }
        ready
        kubernetes cluster.local in-addr.arpa ip6.arpa {
           pods insecure
           fallthrough in-addr.arpa ip6.arpa
           ttl 30
        }
        prometheus :9153
        forward . /etc/resolv.conf {
           max_concurrent 1000
        }
        cache 30
        loop
        reload
        loadbalance
    }
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: coredns
  namespace: kube-system
  labels:
    k8s-app: kube-dns
spec:
  replicas: 2
  selector:
    matchLabels:
      k8s-app: kube-dns
  template:
    metadata:
      labels:
        k8s-app: kube-dns
    spec:
      containers:
      - name: coredns
        image: registry.k8s.io/coredns/coredns:v1.12.0
        args: [ "-conf", "/etc/coredns/Corefile" ]
        ports:
        - containerPort: 53
          name: dns
          protocol: UDP
        - containerPort: 53
          name: dns-tcp
          protocol: TCP
        - containerPort: 9153
          name: metrics
          protocol: TCP
        volumeMounts:
        - mountPath: /etc/coredns
          name: config-volume
          readOnly: true
      volumes:
      - name: config-volume
        configMap:
          items:
          - key: Corefile
            path: Corefile
          name: coredns
---
apiVersion: v1
kind: Service
metadata:
  name: kube-dns
  namespace: kube-system
  labels:
    k8s-app: kube-dns
spec:
  selector:
    k8s-app: kube-dns
  clusterIP: 10.96.0.10
  ports:
  - name: dns
    port: 53
    protocol: UDP
  - name: dns-tcp
    port: 53
    protocol: TCP
EOF

# Verify CoreDNS is running
kubectl get pods -n kube-system -l k8s-app=kube-dns
```

### Test DNS Resolution

```bash
# Run a test pod with nslookup
kubectl run dns-test --image=busybox:1.36 --rm -it --restart=Never -- \
  nslookup kubernetes.default

# Expected output:
# Server:     10.96.0.10
# Address:    10.96.0.10:53
# Name:  kubernetes.default.svc.cluster.local
# Address: 10.96.0.1

# Test cross-namespace resolution
kubectl create namespace test-ns
kubectl run dns-test2 --image=busybox:1.36 --rm -it --restart=Never -n test-ns -- \
  nslookup kube-dns.kube-system.svc.cluster.local
kubectl delete namespace test-ns
```

---

## 15. Validate the Full Cluster

### Complete Health Check

```bash
# 1. Node status
kubectl get nodes -o wide
# All nodes should show: Ready

# 2. System pod status
kubectl get pods -n kube-system
# All pods should be: Running or Completed

# 3. API server health
curl -k https://127.0.0.1:6443/healthz    # ok
curl -k https://127.0.0.1:6443/livez      # ok
curl -k https://127.0.0.1:6443/readyz     # ok

# 4. etcd health
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  endpoint health

# 5. Component status
kubectl get componentstatuses
kubectl get --raw='/readyz?verbose'

# 6. Full lifecycle test
kubectl create deployment web --image=nginx:1.27 --replicas=2
kubectl expose deployment web --port=80 --type=ClusterIP
kubectl get pods,svc

# Test DNS → service name resolution
kubectl run curl-test --image=curlimages/curl --rm -it --restart=Never -- \
  curl http://web.default.svc.cluster.local

# Cleanup
kubectl delete deployment web
kubectl delete service web
```

### Version Verification

```bash
# All components should report v1.35.x
kubectl version
kubelet --version
kube-apiserver --version
kube-controller-manager --version
kube-scheduler --version
etcd --version
```

---

## 16. ETCD Backup & Restore

etcd is the only **stateful** component in Kubernetes. Regular backups are critical.

### Backup etcd

```bash
# Create backup directory
sudo mkdir -p /backup/etcd

# Take snapshot
ETCDCTL_API=3 etcdctl snapshot save /backup/etcd/snapshot-$(date +%Y%m%d-%H%M%S).db \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# Verify the snapshot is not corrupted
ETCDCTL_API=3 etcdctl snapshot status /backup/etcd/snapshot-*.db \
  --write-out=table

# Example output:
# +----------+----------+------------+------------+
# |   HASH   | REVISION | TOTAL KEYS | TOTAL SIZE |
# +----------+----------+------------+------------+
# | 3d4a4e11 |    14391 |        881 |    4.2 MB  |
# +----------+----------+------------+------------+
```

### Restore etcd from Snapshot

```bash
SNAPSHOT="/backup/etcd/snapshot-20260101-120000.db"   # ← your snapshot file

# Stop API server first
# (If using kubeadm — move static pod manifests out)
sudo mv /etc/kubernetes/manifests/kube-apiserver.yaml /tmp/
sudo mv /etc/kubernetes/manifests/kube-controller-manager.yaml /tmp/
sudo mv /etc/kubernetes/manifests/kube-scheduler.yaml /tmp/

# Stop etcd service
sudo systemctl stop etcd

# Restore to new data directory
ETCDCTL_API=3 etcdctl snapshot restore ${SNAPSHOT} \
  --data-dir=/var/lib/etcd-restored \
  --name=k8s-master \
  --initial-cluster=k8s-master=https://127.0.0.1:2380 \
  --initial-cluster-token=etcd-cluster-restored \
  --initial-advertise-peer-urls=https://127.0.0.1:2380

# Back up original data dir and point etcd to restored data
sudo mv /var/lib/etcd /var/lib/etcd-backup-$(date +%Y%m%d)
sudo mv /var/lib/etcd-restored /var/lib/etcd

# For kubeadm — also update etcd static pod
sudo sed -i 's|/var/lib/etcd|/var/lib/etcd|g' /etc/kubernetes/manifests/etcd.yaml
# (path already correct if you moved the dir; update if different)

# Start etcd
sudo systemctl start etcd

# Restore control plane components (kubeadm only)
sudo mv /tmp/kube-apiserver.yaml /etc/kubernetes/manifests/
sudo mv /tmp/kube-controller-manager.yaml /etc/kubernetes/manifests/
sudo mv /tmp/kube-scheduler.yaml /etc/kubernetes/manifests/

# Wait for API server to come back
kubectl get nodes
```

---

## 17. Upgrading an Existing Cluster to v1.35

If you have a cluster running v1.32/1.33/1.34 and want to upgrade to v1.35.

> Only upgrade **one minor version at a time**: 1.32 → 1.33 → 1.34 → 1.35.  
> Never skip a minor version.

### Step 1 — Upgrade Control Plane

```bash
# On master node

# Update the apt repository to v1.35
sudo sed -i 's/v1.34/v1.35/g' /etc/apt/sources.list.d/kubernetes.list

# Unhold, upgrade, rehold
sudo apt-mark unhold kubeadm
sudo apt-get update
sudo apt-get install -y kubeadm=1.35.0-*
sudo apt-mark hold kubeadm

# Verify kubeadm version
kubeadm version

# Check upgrade plan
sudo kubeadm upgrade plan v1.35.0

# Apply the upgrade (interactive — review before confirming)
sudo kubeadm upgrade apply v1.35.0

# Upgrade kubelet and kubectl on master
sudo apt-mark unhold kubelet kubectl
sudo apt-get install -y kubelet=1.35.0-* kubectl=1.35.0-*
sudo apt-mark hold kubelet kubectl

# Restart kubelet
sudo systemctl daemon-reload
sudo systemctl restart kubelet

# Verify master node version
kubectl get nodes
```

### Step 2 — Upgrade Worker Nodes (one at a time)

```bash
# On MASTER — drain the worker node (evict all pods)
kubectl drain k8s-worker-1 --ignore-daemonsets --delete-emptydir-data

# On WORKER NODE k8s-worker-1:
sudo sed -i 's/v1.34/v1.35/g' /etc/apt/sources.list.d/kubernetes.list
sudo apt-mark unhold kubeadm kubelet kubectl
sudo apt-get update
sudo apt-get install -y kubeadm=1.35.0-* kubelet=1.35.0-* kubectl=1.35.0-*
sudo apt-mark hold kubeadm kubelet kubectl

# Upgrade node configuration
sudo kubeadm upgrade node

# Restart kubelet
sudo systemctl daemon-reload
sudo systemctl restart kubelet

# On MASTER — uncordon the worker (allow scheduling again)
kubectl uncordon k8s-worker-1

# Verify all nodes show v1.35
kubectl get nodes

# Repeat for each worker node
```

---

## 18. Troubleshooting Reference

### Checklist: Node stuck in NotReady

```bash
# 1. Check kubelet logs
sudo journalctl -u kubelet -n 100 --no-pager

# 2. Check containerd is running
sudo systemctl status containerd

# 3. Check kernel modules are loaded
lsmod | grep br_netfilter
lsmod | grep overlay

# 4. Check sysctl settings
sysctl net.ipv4.ip_forward
sysctl net.bridge.bridge-nf-call-iptables

# 5. Check CNI is installed
ls /etc/cni/net.d/
ls /opt/cni/bin/

# 6. Check if swap is disabled
free -h

# 7. Describe the node for events
kubectl describe node <node-name>
```

### Checklist: API Server Not Starting

```bash
# Check service log
sudo journalctl -u kube-apiserver -n 100 --no-pager

# Common v1.35 issues:
# - "--allow-privileged" flag → Remove it from service file
# - Wrong etcd endpoint → Check etcd is running on correct port
# - Certificate SAN mismatch → Regenerate API server cert with correct IPs
# - etcd not started yet → Verify etcd service is active

# Verify etcd is accessible
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  endpoint health
```

### Checklist: Pods Stuck in Pending

```bash
# Check scheduler is running
sudo systemctl status kube-scheduler

# Check events on the pod
kubectl describe pod <pod-name>

# Check if all nodes have taints blocking scheduling
kubectl get nodes -o json | jq '.items[].spec.taints'

# For single-node cluster — remove control-plane taint
kubectl taint nodes --all node-role.kubernetes.io/control-plane-
```

### Checklist: DNS Not Working

```bash
# Check CoreDNS pods
kubectl get pods -n kube-system -l k8s-app=kube-dns

# Check CoreDNS ConfigMap
kubectl get configmap coredns -n kube-system -o yaml

# Check kube-dns Service has ClusterIP 10.96.0.10
kubectl get svc kube-dns -n kube-system

# Test from a pod
kubectl run debug --image=busybox --rm -it --restart=Never -- \
  nslookup kubernetes.default
```

### Checklist: Certificate Issues

```bash
# Check certificate expiry
sudo openssl x509 -in /etc/kubernetes/pki/apiserver.crt -noout -dates

# Check SANs on API server cert
sudo openssl x509 -in /etc/kubernetes/pki/apiserver.crt -text -noout | grep -A5 "Subject Alternative"

# For kubeadm clusters — renew all certs
sudo kubeadm certs renew all
sudo kubeadm certs check-expiration
```

### Useful Debug Commands

```bash
# Get all events in a namespace sorted by time
kubectl get events --sort-by=.lastTimestamp

# Get pod logs for a crashed container (previous run)
kubectl logs <pod-name> --previous

# Get container runtime info from a node
kubectl get node <node-name> -o jsonpath='{.status.nodeInfo.containerRuntimeVersion}'

# Force-restart a static pod (kubeadm only)
sudo mv /etc/kubernetes/manifests/kube-apiserver.yaml /tmp/
sleep 5
sudo mv /tmp/kube-apiserver.yaml /etc/kubernetes/manifests/

# Check if kubelet can reach the API server
curl -k https://<MASTER_IP>:6443/healthz --cacert /etc/kubernetes/pki/ca.crt
```

---

## Summary: Component Version Matrix for K8s v1.35 Cluster

```
┌──────────────────────────────────────────────────────┐
│         Kubernetes v1.35 Component Versions          │
├──────────────────────────┬───────────────────────────┤
│ kube-apiserver           │ v1.35.0                   │
│ kube-controller-manager  │ v1.35.0                   │
│ kube-scheduler           │ v1.35.0                   │
│ kubelet                  │ v1.35.0                   │
│ kube-proxy               │ v1.35.0                   │
│ kubectl                  │ v1.35.0                   │
├──────────────────────────┼───────────────────────────┤
│ etcd                     │ v3.5.17                   │
│ containerd               │ v2.0.x (min v1.7.13)      │
│ pause image              │ registry.k8s.io/pause:3.10│
├──────────────────────────┼───────────────────────────┤
│ Calico CNI               │ v3.29.0                   │
│ CoreDNS                  │ v1.12.0                   │
└──────────────────────────┴───────────────────────────┘

Service CIDRs:
  --service-cluster-ip-range = 10.96.0.0/12
  --cluster-cidr             = 192.168.0.0/16 (Calico)
  DNS ClusterIP              = 10.96.0.10

Deprecated in v1.35 (remove from configs):
  --allow-privileged (kube-apiserver)
```

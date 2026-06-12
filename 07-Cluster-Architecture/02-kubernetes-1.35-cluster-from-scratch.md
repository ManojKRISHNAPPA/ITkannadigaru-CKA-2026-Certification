# Kubernetes 1.35 — Cluster From Scratch (The Hard Way)

> CKA 2026 Course — Cluster Architecture, Installation & Configuration
> Kubernetes Version: **v1.35.x** | Method: **100% Manual — No kubeadm**

---

## Table of Contents

| # | Topic |
|---|-------|
| 0 | [OS Preparation — sysctl, Modules, Container Runtime](#0-os-preparation) |
| 1 | [Download Kubernetes Binaries](#step-1-download-kubernetes-binaries) |
| 2 | [Setup Certificate Authority](#step-2-setup-certificate-authority) |
| 3 | [Configure ETCD](#step-3-configure-etcd) |
| 4 | [Configure API Server](#step-4-configure-api-server) |
| 5 | [Configure Controller Manager](#step-5-configure-controller-manager) |
| 6 | [Configure Scheduler](#step-6-configure-scheduler) |
| 7 | [Validate Cluster Status](#step-7-validate-cluster-status) |
| 8 | [Worker Node Configuration](#step-8-worker-node-configuration) |
| 9 | [Configure Networking (CNI)](#step-9-configure-networking) |
| 10 | [API to Kubelet RBAC](#step-10-api-to-kubelet-rbac) |
| 11 | [Configuring DNS (CoreDNS)](#step-11-configuring-dns) |
| 12 | [Kubelet Preferred Address Type](#step-12-kubelet-preferred-address-type) |
| 13 | [Breakdown Learning](#breakdown-learning) |
| 14 | [ETCD Backup and Restore](#etcd-backup-and-restore) |
| 15 | [Structure of Network Policy](#structure-of-network-policy) |
| 16 | [Practical — Network Policies](#practical--network-policies) |
| 17 | [Network Policies — Except, Port and Protocol](#network-policies--except-port-and-protocol) |
| 18 | [Taints and Tolerations](#taints-and-tolerations) |
| 19 | [Custom Resource Definition](#custom-resource-definition) |
| 20 | [Editing Existing Kubernetes Resources](#editing-existing-kubernetes-resources) |
| 21 | [Capacity, Allocated, and Allocatable](#capacity-allocated-and-allocatable) |
| 22 | [Exercise — Requests and Limits](#exercise--requests-and-limits) |
| 23 | [JSONPath](#jsonpath) |
| 24 | [Configuring cri-dockerd](#configuring-cri-dockerd) |

---

## Version Pins — This Guide

```
Kubernetes:  v1.35.0
etcd:        v3.5.17
containerd:  v2.0.4
Calico CNI:  v3.29.0
CoreDNS:     v1.12.0
pause image: registry.k8s.io/pause:3.10
```

---

## Lab Topology

```
192.168.1.10  k8s-master    (Control Plane: API, etcd, CM, Scheduler)
192.168.1.11  k8s-worker-1  (Worker: kubelet, kube-proxy, containerd)
192.168.1.12  k8s-worker-2  (Worker: kubelet, kube-proxy, containerd)

Pod CIDR:     192.168.0.0/16   (Calico)
Service CIDR: 10.96.0.0/12
DNS IP:       10.96.0.10
```

---

## 0. OS Preparation

Run **every command in this section on ALL nodes** (master + all workers) before touching Kubernetes.

### Set Hostnames

```bash
# On master
sudo hostnamectl set-hostname k8s-master

# On worker-1
sudo hostnamectl set-hostname k8s-worker-1

# On worker-2
sudo hostnamectl set-hostname k8s-worker-2

# On EVERY node — add all hosts to /etc/hosts
sudo tee -a /etc/hosts <<EOF
192.168.1.10  k8s-master
192.168.1.11  k8s-worker-1
192.168.1.12  k8s-worker-2
EOF
```

### Disable Swap

Kubernetes requires swap to be completely off. Kubelet will refuse to start if swap is active.

```bash
# Turn off swap immediately
sudo swapoff -a

# Permanently disable by commenting out the swap line in fstab
sudo sed -i '/ swap / s/^\(.*\)$/#\1/g' /etc/fstab

# Verify — all three swap columns must show 0
free -h
# Expected output:
#               total   used   free   shared  buff/cache  available
# Swap:           0B      0B     0B
```

### Load Required Kernel Modules

```bash
# Create persistent module loading config
cat <<EOF | sudo tee /etc/modules-load.d/k8s.conf
overlay
br_netfilter
EOF

# Load immediately without reboot
sudo modprobe overlay
sudo modprobe br_netfilter

# Verify both are loaded
lsmod | grep br_netfilter
lsmod | grep overlay
# Both must return output — empty output means the module failed to load
```

### Configure sysctl — Kernel Network Parameters

This is a critical step. Without these settings, Pod-to-Pod traffic and iptables-based routing will not work.

```bash
# Write Kubernetes required sysctl settings
cat <<EOF | sudo tee /etc/sysctl.d/k8s.conf
# Allow the Linux kernel to forward packets between network interfaces
# Required for Pod-to-Pod traffic across nodes
net.ipv4.ip_forward = 1

# Apply iptables rules to bridged network traffic
# Required so kube-proxy and CNI plugins can intercept container traffic
net.bridge.bridge-nf-call-iptables  = 1
net.bridge.bridge-nf-call-ip6tables = 1
EOF

# Apply all sysctl settings from /etc/sysctl.d/ immediately
sudo sysctl --system

# Verify the three values were applied
sysctl net.ipv4.ip_forward
sysctl net.bridge.bridge-nf-call-iptables
sysctl net.bridge.bridge-nf-call-ip6tables
# All three must return = 1
```

**Why these three settings matter:**

| Parameter | What it does |
|-----------|-------------|
| `net.ipv4.ip_forward` | Allows the OS to route packets between network interfaces — without this, packets from pods die at the host NIC |
| `net.bridge.bridge-nf-call-iptables` | Routes traffic from the container bridge through iptables — kube-proxy depends on this |
| `net.bridge.bridge-nf-call-ip6tables` | Same as above for IPv6 — required even if you only use IPv4 |

### Install containerd v2.0 (Container Runtime)

```bash
# Install build dependencies
sudo apt-get update
sudo apt-get install -y apt-transport-https ca-certificates curl gnupg lsb-release

# Add Docker's GPG key (containerd packages come from Docker's repo)
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

# Confirm version is 2.0.x
containerd --version
```

### Configure containerd for Kubernetes

```bash
# Generate default config
sudo mkdir -p /etc/containerd
sudo containerd config default | sudo tee /etc/containerd/config.toml

# Enable systemd cgroup driver — MUST match kubelet cgroupDriver setting
sudo sed -i 's/SystemdCgroup = false/SystemdCgroup = true/g' \
  /etc/containerd/config.toml

# Update pause image to v3.10 (new requirement for K8s 1.35)
sudo sed -i 's|registry.k8s.io/pause:3.9|registry.k8s.io/pause:3.10|g' \
  /etc/containerd/config.toml

# Verify both changes took effect
grep -E 'SystemdCgroup|sandbox_image' /etc/containerd/config.toml
# Expected:
#   sandbox_image = "registry.k8s.io/pause:3.10"
#   SystemdCgroup = true

# Restart and enable containerd
sudo systemctl restart containerd
sudo systemctl enable containerd

sudo systemctl status containerd --no-pager
```

---

## Step 1: Download Kubernetes Binaries

> Run on: **Master node** (control plane binaries + worker binaries)

### Set Version Variables

```bash
export K8S_VERSION="v1.35.0"
export ETCD_VERSION="v3.5.17"
export ARCH="amd64"

# Add to ~/.bashrc so these persist across sessions
echo "export K8S_VERSION=v1.35.0" >> ~/.bashrc
echo "export ETCD_VERSION=v3.5.17" >> ~/.bashrc
echo "export ARCH=amd64" >> ~/.bashrc
```

### Download Control Plane Binaries

```bash
mkdir -p ~/k8s-binaries && cd ~/k8s-binaries

# All control plane components
wget -q --show-progress --timestamping \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kube-apiserver" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kube-controller-manager" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kube-scheduler" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kubectl"

# Worker node binaries
wget -q --show-progress --timestamping \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kubelet" \
  "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kube-proxy"

# Verify checksum on at least the API server
wget -q "https://dl.k8s.io/${K8S_VERSION}/bin/linux/${ARCH}/kube-apiserver.sha256"
echo "$(cat kube-apiserver.sha256)  kube-apiserver" | sha256sum --check
# Expected: kube-apiserver: OK

# Make all binaries executable and install to PATH
chmod +x kube-apiserver kube-controller-manager kube-scheduler \
         kubectl kubelet kube-proxy

sudo mv kube-apiserver kube-controller-manager kube-scheduler \
        kubectl kubelet kube-proxy \
        /usr/local/bin/

# Verify
kubectl version --client
kubelet --version
kube-apiserver --version
```

### Download etcd v3.5.17

```bash
cd ~/k8s-binaries

wget -q --show-progress \
  "https://github.com/etcd-io/etcd/releases/download/${ETCD_VERSION}/etcd-${ETCD_VERSION}-linux-${ARCH}.tar.gz"

tar -xf etcd-${ETCD_VERSION}-linux-${ARCH}.tar.gz

sudo mv etcd-${ETCD_VERSION}-linux-${ARCH}/etcd \
        etcd-${ETCD_VERSION}-linux-${ARCH}/etcdctl \
        /usr/local/bin/

# Verify
etcd --version
etcdctl version
```

### What Each Binary Does

| Binary | Role | Runs On |
|--------|------|---------|
| `kube-apiserver` | All REST API requests — the single front door to the cluster | Master |
| `kube-controller-manager` | Runs all control loops: ReplicaSet, Deployment, Node, etc. | Master |
| `kube-scheduler` | Decides which node gets each new pod | Master |
| `etcd` | Distributed KV store — holds all cluster state | Master |
| `kubelet` | Node agent — starts/stops containers via CRI | Worker |
| `kube-proxy` | Sets up iptables/ipvs rules for Service routing | Worker |
| `kubectl` | CLI client — talks to kube-apiserver | Master/Local |

---

## Step 2: Setup Certificate Authority

Every Kubernetes component communicates over mutual TLS. You need to generate a chain of trust before any service can start.

### PKI Architecture Overview

```
Root CA (ca.key + ca.crt)
  ├── API Server cert        (apiserver.crt)
  ├── Controller Manager     (controller-manager.crt)
  ├── Scheduler              (scheduler.crt)
  ├── Admin kubeconfig       (admin.crt)
  ├── kubelet (per node)     (system:node:<name>.crt)
  ├── kube-proxy             (kube-proxy.crt)
  └── Service Account pair   (sa.key + sa.pub)

etcd CA (etcd/ca.key + etcd/ca.crt)
  ├── etcd server cert       (etcd/server.crt)
  ├── etcd peer cert         (etcd/peer.crt)
  └── API→etcd client cert   (apiserver-etcd-client.crt)
```

### Create PKI Directory Structure

```bash
sudo mkdir -p /etc/kubernetes/pki/etcd
sudo chmod 700 /etc/kubernetes/pki
```

### Generate Cluster CA

```bash
# Cluster CA private key
sudo openssl genrsa -out /etc/kubernetes/pki/ca.key 2048

# Cluster CA self-signed certificate — 10-year validity
sudo openssl req -new -x509 -days 3650 \
  -key /etc/kubernetes/pki/ca.key \
  -out /etc/kubernetes/pki/ca.crt \
  -subj "/CN=kubernetes-ca/O=Kubernetes"

# Verify
sudo openssl x509 -in /etc/kubernetes/pki/ca.crt -text -noout \
  | grep -E 'Subject:|Issuer:|Not After'
```

### Generate etcd CA

```bash
sudo openssl genrsa -out /etc/kubernetes/pki/etcd/ca.key 2048

sudo openssl req -new -x509 -days 3650 \
  -key /etc/kubernetes/pki/etcd/ca.key \
  -out /etc/kubernetes/pki/etcd/ca.crt \
  -subj "/CN=etcd-ca/O=etcd"
```

### Generate etcd Server Certificate

```bash
MASTER_IP="192.168.1.10"   # change to your actual IP

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
IP.2 = ${MASTER_IP}
EOF

sudo openssl genrsa -out /etc/kubernetes/pki/etcd/server.key 2048

sudo openssl req -new \
  -key /etc/kubernetes/pki/etcd/server.key \
  -out /tmp/etcd-server.csr \
  -subj "/CN=etcd-server" \
  -config /tmp/etcd-server-ext.conf

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
IP.2 = ${MASTER_IP}
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

The API server cert needs SANs for every DNS name and IP that clients (kubectl, kubelet, ingress) use to reach it.

```bash
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
IP.1 = 10.96.0.1
IP.2 = ${MASTER_IP}
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

# Verify SANs are correct
sudo openssl x509 -in /etc/kubernetes/pki/apiserver.crt \
  -text -noout | grep -A5 "Subject Alternative Name"
```

### Generate API Server → etcd Client Certificate

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

### Generate API Server → kubelet Client Certificate

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
# Used by controller-manager to sign ServiceAccount tokens
# and by API server to verify them
sudo openssl genrsa -out /etc/kubernetes/pki/sa.key 2048
sudo openssl rsa -in /etc/kubernetes/pki/sa.key \
  -pubout -out /etc/kubernetes/pki/sa.pub
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

# Build kubeconfig
MASTER_IP="192.168.1.10"
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

# Enable kubectl for the current user
mkdir -p $HOME/.kube
sudo cp /etc/kubernetes/admin.conf $HOME/.kube/config
sudo chown $(id -u):$(id -g) $HOME/.kube/config
```

### Verify PKI Directory

```bash
sudo find /etc/kubernetes/pki -type f | sort
# Expected files:
# /etc/kubernetes/pki/admin.crt
# /etc/kubernetes/pki/admin.key
# /etc/kubernetes/pki/apiserver.crt
# /etc/kubernetes/pki/apiserver.key
# /etc/kubernetes/pki/apiserver-etcd-client.crt
# /etc/kubernetes/pki/apiserver-etcd-client.key
# /etc/kubernetes/pki/apiserver-kubelet-client.crt
# /etc/kubernetes/pki/apiserver-kubelet-client.key
# /etc/kubernetes/pki/ca.crt
# /etc/kubernetes/pki/ca.key
# /etc/kubernetes/pki/ca.srl
# /etc/kubernetes/pki/sa.key
# /etc/kubernetes/pki/sa.pub
# /etc/kubernetes/pki/etcd/ca.crt
# /etc/kubernetes/pki/etcd/ca.key
# /etc/kubernetes/pki/etcd/peer.crt
# /etc/kubernetes/pki/etcd/peer.key
# /etc/kubernetes/pki/etcd/server.crt
# /etc/kubernetes/pki/etcd/server.key
```

---

## Step 3: Configure ETCD

> Reference: https://etcd.io/docs/v3.5/op-guide/configuration/

etcd is the **single source of truth** for all cluster state — every object you create is stored here. If etcd dies without a backup, the cluster is unrecoverable.

### Pre-Requisite — Set SERVER_IP Variable

```bash
# Set this variable first — it is used in every command below
SERVER_IP=139.59.28.67        # ← change to your actual server/master IP
echo $SERVER_IP
```

### Sub-Step 1: Generate etcd Certificates

Certificates are generated in `/root/certificates/` where your CA key and cert already live from Step 2.

```bash
cd /root/certificates/

# Generate etcd private key
openssl genrsa -out etcd.key 2048

# Create the OpenSSL config with SAN entries for the server IP and localhost
cat > etcd.cnf <<EOF
[req]
req_extensions = v3_req
distinguished_name = req_distinguished_name
[req_distinguished_name]
[ v3_req ]
basicConstraints = CA:FALSE
keyUsage = nonRepudiation, digitalSignature, keyEncipherment
subjectAltName = @alt_names
[alt_names]
IP.1 = ${SERVER_IP}
IP.2 = 127.0.0.1
EOF

# Generate CSR and sign it with the cluster CA in a single block
{
  openssl req -new -key etcd.key \
    -subj "/CN=etcd" \
    -out etcd.csr \
    -config etcd.cnf

  openssl x509 -req \
    -in etcd.csr \
    -CA ca.crt \
    -CAkey ca.key \
    -CAcreateserial \
    -out etcd.crt \
    -extensions v3_req \
    -extfile etcd.cnf \
    -days 1000
}

# Verify the cert was issued with the correct SANs
openssl x509 -in etcd.crt -text -noout | grep -A4 "Subject Alternative Name"
# Expected: IP Address:139.59.28.67, IP Address:127.0.0.1
```

### Sub-Step 2: Copy Certificates to /etc/etcd

```bash
mkdir -p /etc/etcd
cp etcd.crt etcd.key ca.crt /etc/etcd/

# Verify all three files are in place
ls -la /etc/etcd/
# etcd.crt  etcd.key  ca.crt
```

### Sub-Step 3: Copy etcd Binaries to PATH

```bash
cd /root/binaries/etcd-v3.5.18-linux-amd64/
cp etcd etcdctl /usr/local/bin/

# Verify versions
etcd --version
etcdctl version
```

### Sub-Step 4: Create etcd systemd Service File

```bash
cat <<EOF | sudo tee /etc/systemd/system/etcd.service
[Unit]
Description=etcd
Documentation=https://github.com/coreos

[Service]
ExecStart=/usr/local/bin/etcd \\
  --name master-1 \\
  --cert-file=/etc/etcd/etcd.crt \\
  --key-file=/etc/etcd/etcd.key \\
  --peer-cert-file=/etc/etcd/etcd.crt \\
  --peer-key-file=/etc/etcd/etcd.key \\
  --trusted-ca-file=/etc/etcd/ca.crt \\
  --peer-trusted-ca-file=/etc/etcd/ca.crt \\
  --peer-client-cert-auth \\
  --client-cert-auth \\
  --initial-advertise-peer-urls https://${SERVER_IP}:2380 \\
  --listen-peer-urls https://${SERVER_IP}:2380 \\
  --listen-client-urls https://${SERVER_IP}:2379,https://127.0.0.1:2379 \\
  --advertise-client-urls https://${SERVER_IP}:2379 \\
  --initial-cluster-token etcd-cluster-0 \\
  --initial-cluster master-1=https://${SERVER_IP}:2380 \\
  --initial-cluster-state new \\
  --data-dir=/var/lib/etcd
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

# Create data directory
sudo mkdir -p /var/lib/etcd
sudo chmod 700 /var/lib/etcd

# Start etcd
systemctl daemon-reload
systemctl start etcd
systemctl enable etcd

# Check status
systemctl status etcd --no-pager
```

### Verification Commands

```bash
# Write a test key to etcd
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/etcd/ca.crt \
  --cert=/etc/etcd/etcd.crt \
  --key=/etc/etcd/etcd.key \
  put course "kplabs cka course is awesome"

# Read it back — should return "kplabs cka course is awesome"
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/etcd/ca.crt \
  --cert=/etc/etcd/etcd.crt \
  --key=/etc/etcd/etcd.key \
  get course

# Check etcd cluster health
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/etcd/ca.crt \
  --cert=/etc/etcd/etcd.crt \
  --key=/etc/etcd/etcd.key \
  endpoint health

# List all members
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/etcd/ca.crt \
  --cert=/etc/etcd/etcd.crt \
  --key=/etc/etcd/etcd.key \
  member list
```

### Key etcd Flags Explained

| Flag | Purpose |
|------|---------|
| `--name` | Human-readable member name — must match `--initial-cluster` entry |
| `--cert-file` / `--key-file` | TLS cert/key for client-facing port 2379 |
| `--peer-cert-file` | TLS cert for peer-to-peer port 2380 (cluster replication) |
| `--peer-client-cert-auth` | Require peer members to present a valid cert |
| `--client-cert-auth` | Require clients (API server) to present a valid cert — no anonymous access |
| `--initial-advertise-peer-urls` | URL this member announces to other members for replication |
| `--listen-client-urls` | Ports this member listens on for client requests |
| `--advertise-client-urls` | URL that clients (API server) use to reach this etcd member |
| `--initial-cluster-token` | Unique token to prevent cross-cluster contamination |
| `--initial-cluster-state=new` | First-time startup; change to `existing` when adding members to a running cluster |
| `--data-dir` | Where etcd writes its WAL (Write-Ahead Log) and snapshots |

---

## Step 4: Configure API Server

The API server is the **only** Kubernetes component that directly reads and writes to etcd. All other components (kubelet, controller-manager, scheduler) communicate through the API server.

> **v1.35 change:** `--allow-privileged` is deprecated. Do NOT add it to the service file — it will cause a startup warning/failure.

```bash
MASTER_IP="192.168.1.10"   # change to your actual IP

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

sudo systemctl status kube-apiserver --no-pager
```

### Verify API Server

```bash
# Health check endpoints (no auth required)
curl -k https://127.0.0.1:6443/healthz
curl -k https://127.0.0.1:6443/readyz
curl -k https://127.0.0.1:6443/livez
# All three should return: ok

# Test that kubectl can reach the API server
kubectl get nodes
# Expected: No resources found (no nodes have joined yet)
```

### Key API Server Flags Explained

| Flag | Purpose |
|------|---------|
| `--advertise-address` | IP the API server announces to other components |
| `--authorization-mode=Node,RBAC` | Node auth for kubelets, RBAC for all other requests |
| `--enable-admission-plugins=NodeRestriction` | Prevents kubelets from modifying objects outside their own node |
| `--service-account-issuer` | JWT issuer claim in SA tokens — must match kubelets' expected value |
| `--service-account-signing-key-file` | Private key for signing SA tokens |
| `--service-account-key-file` | Public key for verifying SA tokens |
| `--service-cluster-ip-range` | CIDR block for ClusterIP Services — must not overlap Pod CIDR |

---

## Step 5: Configure Controller Manager

The controller manager runs dozens of control loops in a single process. Each loop watches a specific resource type and reconciles actual state toward desired state.

### Generate Controller Manager kubeconfig

```bash
MASTER_IP="192.168.1.10"

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

sudo systemctl status kube-controller-manager --no-pager
```

### Key Controller Manager Flags Explained

| Flag | Purpose |
|------|---------|
| `--cluster-cidr` | Pod IP range — controller allocates node subnets from this |
| `--cluster-signing-cert-file` | CA used to sign kubelet CSR bootstrapping requests |
| `--cluster-signing-duration` | How long auto-signed certs are valid (87600h = 10y) |
| `--leader-elect` | In HA setups, only one CM instance is active at a time |
| `--use-service-account-credentials` | Each built-in controller gets its own ServiceAccount — best practice for least privilege |

---

## Step 6: Configure Scheduler

The scheduler watches for unscheduled pods (`spec.nodeName` is empty) and picks the best node based on resource availability, affinity rules, taints, and tolerations.

### Generate Scheduler kubeconfig

```bash
MASTER_IP="192.168.1.10"

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

sudo systemctl status kube-scheduler --no-pager
```

---

## Step 7: Validate Cluster Status

Before adding workers, verify the control plane is fully healthy.

```bash
# All four services must be active (running)
sudo systemctl status etcd kube-apiserver kube-controller-manager kube-scheduler \
  --no-pager

# API server health endpoints
curl -k https://127.0.0.1:6443/healthz   # ok
curl -k https://127.0.0.1:6443/readyz    # ok
curl -k https://127.0.0.1:6443/livez     # ok

# Component status (verbose readyz check)
kubectl get --raw='/readyz?verbose'

# etcd health
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  endpoint health

# Check what kubectl sees
kubectl get nodes          # no nodes yet — that's expected
kubectl get pods -A        # no pods yet — that's expected
```

### Expected State at This Point

```
etcd              active (running)
kube-apiserver    active (running)
kube-controller-manager  active (running)
kube-scheduler    active (running)

curl /healthz     → ok
kubectl get nodes → No resources found  ← correct, workers not joined yet
```

---

## Step 8: Worker Node Configuration

Run steps in this section on **each worker node**.

### Copy CA Certificate to Worker

```bash
# On master — copy CA cert to each worker
WORKER_IP="192.168.1.11"
scp /etc/kubernetes/pki/ca.crt ubuntu@${WORKER_IP}:/tmp/ca.crt

# On worker — install it
sudo mkdir -p /etc/kubernetes/pki
sudo mv /tmp/ca.crt /etc/kubernetes/pki/ca.crt
```

### Generate Kubelet Certificate (on master, once per worker)

The CN must follow the pattern `system:node:<hostname>` and the O must be `system:nodes`. This is how the NodeAuthorizer knows which node is authenticating.

```bash
# Run on MASTER for each worker
NODE_NAME="k8s-worker-1"
NODE_IP="192.168.1.11"

sudo openssl genrsa -out /etc/kubernetes/pki/${NODE_NAME}.key 2048

sudo openssl req -new \
  -key /etc/kubernetes/pki/${NODE_NAME}.key \
  -out /tmp/${NODE_NAME}.csr \
  -subj "/CN=system:node:${NODE_NAME}/O=system:nodes"

sudo openssl x509 -req \
  -in /tmp/${NODE_NAME}.csr \
  -CA /etc/kubernetes/pki/ca.crt \
  -CAkey /etc/kubernetes/pki/ca.key \
  -CAcreateserial \
  -out /etc/kubernetes/pki/${NODE_NAME}.crt \
  -days 3650

# Copy the cert and key to the worker
scp /etc/kubernetes/pki/${NODE_NAME}.crt \
    /etc/kubernetes/pki/${NODE_NAME}.key \
    ubuntu@${NODE_IP}:/tmp/
```

### Build Kubelet kubeconfig (on worker)

```bash
# Run on WORKER
NODE_NAME=$(hostname)
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

sudo systemctl status kubelet --no-pager
sudo journalctl -u kubelet -n 30 --no-pager
```

### Create kube-proxy Configuration (on master → copy to workers)

```bash
# On master — generate kube-proxy cert + kubeconfig
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

# Copy kube-proxy.conf to each worker
scp /etc/kubernetes/kube-proxy.conf ubuntu@192.168.1.11:/tmp/
```

```bash
# On WORKER — install kube-proxy
sudo mkdir -p /var/lib/kube-proxy
sudo mv /tmp/kube-proxy.conf /etc/kubernetes/kube-proxy.conf

sudo tee /var/lib/kube-proxy/config.yaml <<EOF
apiVersion: kubeproxy.config.k8s.io/v1alpha1
kind: KubeProxyConfiguration
clientConnection:
  kubeconfig: /etc/kubernetes/kube-proxy.conf
mode: iptables
clusterCIDR: 192.168.0.0/16
EOF

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

sudo systemctl daemon-reload
sudo systemctl enable --now kube-proxy

sudo systemctl status kube-proxy --no-pager
```

### Verify Workers Joined

```bash
# On master
kubectl get nodes -o wide
# Expected: both workers appear with STATUS = NotReady
# NotReady is correct at this point — CNI not installed yet
```

---

## Step 9: Configure Networking

Without a CNI (Container Network Interface) plugin, pods cannot reach each other. The node will stay `NotReady` until CNI is installed.

### Install Calico v3.29 (Operator Method)

```bash
# Install the Tigera Calico operator
kubectl create -f https://raw.githubusercontent.com/projectcalico/calico/v3.29.0/manifests/tigera-operator.yaml

# Wait for the operator pod to be running
kubectl get pods -n tigera-operator -w

# Apply the Calico Installation resource
kubectl apply -f - <<EOF
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

# Watch calico system pods come up (takes 1-2 minutes)
kubectl get pods -n calico-system -w

# Nodes should now become Ready
kubectl get nodes -w
```

### Alternative: Calico Manifest Method (simpler for single-node)

```bash
kubectl apply -f https://raw.githubusercontent.com/projectcalico/calico/v3.29.0/manifests/calico.yaml

kubectl rollout status daemonset/calico-node -n kube-system
```

### Verify Pod-to-Pod Networking

```bash
# Deploy two pods on different nodes
kubectl run pod1 --image=busybox:1.36 --overrides='{"spec":{"nodeName":"k8s-worker-1"}}' \
  --command -- sleep 3600

kubectl run pod2 --image=busybox:1.36 --overrides='{"spec":{"nodeName":"k8s-worker-2"}}' \
  --command -- sleep 3600

kubectl get pods -o wide

# Test cross-node connectivity
POD2_IP=$(kubectl get pod pod2 -o jsonpath='{.status.podIP}')
kubectl exec pod1 -- ping -c 3 ${POD2_IP}
# Expect 0% packet loss

kubectl delete pod pod1 pod2
```

### CNI Plugin Directory

When Calico installs, it places its config and binaries here:

```bash
ls /etc/cni/net.d/     # Calico config file
ls /opt/cni/bin/       # CNI binary plugins
```

---

## Step 10: API to Kubelet RBAC

The API server needs explicit RBAC permission to proxy requests to kubelet endpoints. Without this, `kubectl exec`, `kubectl logs`, and `kubectl port-forward` will fail with a 403 Forbidden error.

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

# Verify
kubectl get clusterrolebinding system:kube-apiserver -o yaml

# Test that exec and logs work
kubectl run test-rbac --image=nginx:1.27
kubectl wait pod test-rbac --for=condition=Ready --timeout=60s
kubectl exec test-rbac -- nginx -v
kubectl logs test-rbac
kubectl delete pod test-rbac
```

---

## Step 11: Configuring DNS

CoreDNS runs as a Deployment inside the cluster and provides in-cluster DNS so pods can resolve service names like `nginx.default.svc.cluster.local`.

### Deploy CoreDNS

```bash
kubectl apply -f - <<EOF
---
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
  strategy:
    type: RollingUpdate
    rollingUpdate:
      maxUnavailable: 1
  template:
    metadata:
      labels:
        k8s-app: kube-dns
    spec:
      priorityClassName: system-cluster-critical
      tolerations:
      - key: CriticalAddonsOnly
        operator: Exists
      - key: node-role.kubernetes.io/control-plane
        effect: NoSchedule
      nodeSelector:
        kubernetes.io/os: linux
      affinity:
        podAntiAffinity:
          preferredDuringSchedulingIgnoredDuringExecution:
          - weight: 100
            podAffinityTerm:
              labelSelector:
                matchExpressions:
                - key: k8s-app
                  operator: In
                  values: [kube-dns]
              topologyKey: kubernetes.io/hostname
      containers:
      - name: coredns
        image: registry.k8s.io/coredns/coredns:v1.12.0
        imagePullPolicy: IfNotPresent
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
        livenessProbe:
          httpGet:
            path: /health
            port: 8080
          initialDelaySeconds: 60
          timeoutSeconds: 5
        readinessProbe:
          httpGet:
            path: /ready
            port: 8181
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
    kubernetes.io/cluster-service: "true"
    kubernetes.io/name: "CoreDNS"
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

# Wait for CoreDNS pods
kubectl rollout status deployment/coredns -n kube-system
kubectl get pods -n kube-system -l k8s-app=kube-dns
```

### Test DNS Resolution

```bash
# Test resolution of the kubernetes service
kubectl run dns-test --image=busybox:1.36 --rm -it --restart=Never -- \
  nslookup kubernetes.default

# Expected:
# Server:     10.96.0.10
# Address:    10.96.0.10:53
# Name:       kubernetes.default.svc.cluster.local
# Address:    10.96.0.1

# Test cross-namespace DNS
kubectl create namespace test-dns
kubectl run dns-test2 --image=busybox:1.36 --rm -it --restart=Never -n test-dns -- \
  nslookup kube-dns.kube-system.svc.cluster.local
kubectl delete namespace test-dns
```

### CoreDNS Corefile Plugins Explained

| Plugin | Function |
|--------|----------|
| `errors` | Logs DNS errors |
| `health` | Exposes /health endpoint for liveness probe |
| `ready` | Exposes /ready endpoint for readiness probe |
| `kubernetes` | Resolves in-cluster service/pod DNS names |
| `forward` | Forwards external queries to upstream DNS (/etc/resolv.conf) |
| `cache` | Caches responses for 30s to reduce upstream load |
| `loop` | Detects and stops infinite forwarding loops |
| `loadbalance` | Round-robin across multiple A records |

---

## Step 12: Kubelet Preferred Address Type

When the API server connects to a kubelet (for exec/logs/port-forward), it must choose which address to use. This is controlled by `--kubelet-preferred-address-types` on the API server.

### Understanding Address Types

```
InternalIP   → Node's primary network IP (e.g., 192.168.1.11)
ExternalIP   → Public/external IP assigned to the node
Hostname     → Node's hostname (k8s-worker-1)
InternalDNS  → Internal DNS name of the node
ExternalDNS  → External DNS name of the node
```

### Configuration

In the API server service file, the flag is already set:

```
--kubelet-preferred-address-types=InternalIP,ExternalIP,Hostname
```

This means: try `InternalIP` first, then `ExternalIP`, then `Hostname`. For a typical bare-metal or on-prem cluster, `InternalIP` is always correct.

### Why This Matters

```bash
# If preferred address is wrong, these commands fail with:
# error: unable to upgrade connection: ... connection refused

kubectl exec pod-name -- bash
kubectl logs pod-name
kubectl port-forward pod-name 8080:80
```

### Checking Node Addresses

```bash
# View all registered addresses for each node
kubectl get nodes -o json | jq '.items[].status.addresses'

# Example output:
# [
#   { "address": "192.168.1.11", "type": "InternalIP" },
#   { "address": "k8s-worker-1", "type": "Hostname" }
# ]

# If InternalIP is missing, the kubelet was started without --node-ip
# Fix: add --node-ip=<actual-ip> to kubelet.service ExecStart line
```

### Fix: Worker Node Has Wrong Address

```bash
# On worker — add --node-ip flag to kubelet service
sudo sed -i '/ExecStart=\/usr\/local\/bin\/kubelet/a \  --node-ip=192.168.1.11 \\' \
  /etc/systemd/system/kubelet.service

sudo systemctl daemon-reload
sudo systemctl restart kubelet

# Verify the address appears
kubectl get node k8s-worker-1 -o jsonpath='{.status.addresses}'
```

---

## Breakdown Learning

This section consolidates concepts from all the above steps into a mental model.

### The Flow: What Happens When You Run `kubectl apply`

```
kubectl apply -f pod.yaml
      │
      ▼
kube-apiserver  ──► validates YAML, authenticates user, checks RBAC
      │
      ▼
etcd            ──► stores the Pod object (status: Pending)
      │
      ▼
kube-scheduler  ──► watches for unscheduled pods, picks a node
      │              writes node name back to API server
      ▼
kubelet         ──► watches for pods assigned to its node
      │              calls containerd CRI to pull image and start container
      ▼
containerd      ──► pulls image from registry, creates container
      │
      ▼
kubelet         ──► reports pod status back to API server
      │
      ▼
etcd            ──► stores updated pod status (Running)
```

### Component Dependency Order

```
containerd  →  kubelet  →  kube-proxy
etcd  →  kube-apiserver  →  kube-controller-manager
                          →  kube-scheduler
```

### Certificate Trust Chain Summary

```
Cluster CA
├── Signs: apiserver.crt       (presented by API server to clients)
├── Signs: admin.crt           (presented by kubectl as admin user)
├── Signs: controller-mgr.crt  (CM identifies itself to API server)
├── Signs: scheduler.crt       (scheduler identifies itself to API server)
├── Signs: kubelet.crt         (kubelet identifies as system:node:<name>)
├── Signs: kube-proxy.crt      (proxy identifies as system:kube-proxy)
└── Signs: apiserver-kubelet-client.crt (API server → kubelet direction)

etcd CA (separate trust chain)
├── Signs: etcd/server.crt     (etcd server TLS)
├── Signs: etcd/peer.crt       (etcd inter-member replication)
└── Signs: apiserver-etcd-client.crt (API server authenticates to etcd)
```

### RBAC Identity Mapping

| Component | Certificate CN | Group | Role |
|-----------|---------------|-------|------|
| kubelet | `system:node:k8s-worker-1` | `system:nodes` | Node authorizer manages this |
| controller-manager | `system:kube-controller-manager` | — | Built-in ClusterRole |
| scheduler | `system:kube-scheduler` | — | Built-in ClusterRole |
| kube-proxy | `system:kube-proxy` | — | Built-in ClusterRole |
| admin | `kubernetes-admin` | `system:masters` | cluster-admin (unrestricted) |

### Common Startup Failures and Root Causes

| Symptom | Root Cause |
|---------|------------|
| etcd fails to start | Cert SAN doesn't include `MASTER_IP`, or data dir permissions wrong |
| API server refuses to start | `--allow-privileged` still in service file (v1.35 deprecated), etcd not running |
| Node stays `NotReady` | CNI not installed, or kubelet can't reach API server |
| `kubectl exec` fails 403 | API→Kubelet RBAC not applied (Step 10) |
| DNS resolution fails in pods | CoreDNS not deployed, or `clusterDNS` in kubelet config doesn't match service ClusterIP |
| Pods fail to schedule | Scheduler not running, or control-plane has NoSchedule taint |

---

## ETCD Backup and Restore

etcd is the **only stateful component** in Kubernetes. Losing etcd without a backup means losing the entire cluster state — every deployment, configmap, secret, RBAC rule.

### Backup etcd (Snapshot)

```bash
# Create backup directory
sudo mkdir -p /backup/etcd

# Take a snapshot — this is an atomic, consistent backup
SNAPSHOT_FILE="/backup/etcd/snapshot-$(date +%Y%m%d-%H%M%S).db"

ETCDCTL_API=3 etcdctl snapshot save ${SNAPSHOT_FILE} \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

echo "Snapshot saved to: ${SNAPSHOT_FILE}"
```

### Verify Snapshot Integrity

```bash
ETCDCTL_API=3 etcdctl snapshot status ${SNAPSHOT_FILE} --write-out=table

# Example output:
# +----------+----------+------------+------------+
# |   HASH   | REVISION | TOTAL KEYS | TOTAL SIZE |
# +----------+----------+------------+------------+
# | 3d4a4e11 |    14391 |        881 |    4.2 MB  |
# +----------+----------+------------+------------+
```

### Automate Daily Backups (cron)

```bash
# Create a backup script
sudo tee /usr/local/bin/etcd-backup.sh <<'EOF'
#!/bin/bash
set -e
BACKUP_DIR="/backup/etcd"
SNAPSHOT="${BACKUP_DIR}/snapshot-$(date +%Y%m%d-%H%M%S).db"
mkdir -p ${BACKUP_DIR}

ETCDCTL_API=3 etcdctl snapshot save ${SNAPSHOT} \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key

# Keep only last 7 days of backups
find ${BACKUP_DIR} -name "snapshot-*.db" -mtime +7 -delete

echo "Backup complete: ${SNAPSHOT}"
EOF

sudo chmod +x /usr/local/bin/etcd-backup.sh

# Schedule daily at 2am
echo "0 2 * * * root /usr/local/bin/etcd-backup.sh >> /var/log/etcd-backup.log 2>&1" \
  | sudo tee /etc/cron.d/etcd-backup
```

### Restore etcd from Snapshot

```bash
SNAPSHOT="/backup/etcd/snapshot-20260101-120000.db"

# Step 1: Stop the API server (prevents writes during restore)
sudo systemctl stop kube-apiserver kube-controller-manager kube-scheduler

# Step 2: Stop etcd
sudo systemctl stop etcd

# Step 3: Restore snapshot to a NEW directory
ETCDCTL_API=3 etcdctl snapshot restore ${SNAPSHOT} \
  --data-dir=/var/lib/etcd-restored \
  --name=k8s-master \
  --initial-cluster=k8s-master=https://127.0.0.1:2380 \
  --initial-cluster-token=etcd-cluster-restored \
  --initial-advertise-peer-urls=https://127.0.0.1:2380

# Step 4: Replace the corrupted data directory
sudo mv /var/lib/etcd /var/lib/etcd-old-$(date +%Y%m%d)
sudo mv /var/lib/etcd-restored /var/lib/etcd

# Step 5: Start etcd
sudo systemctl start etcd

# Verify etcd is healthy
ETCDCTL_API=3 etcdctl \
  --endpoints=https://127.0.0.1:2379 \
  --cacert=/etc/kubernetes/pki/etcd/ca.crt \
  --cert=/etc/kubernetes/pki/etcd/server.crt \
  --key=/etc/kubernetes/pki/etcd/server.key \
  endpoint health

# Step 6: Start control plane
sudo systemctl start kube-apiserver kube-controller-manager kube-scheduler

# Verify cluster recovered
kubectl get nodes
kubectl get pods -A
```

### Backup vs Restore — Decision Table

| Scenario | Action |
|----------|--------|
| etcd data dir corrupted | Restore from latest snapshot |
| Accidentally deleted a namespace | Restore snapshot to a test cluster first, extract the objects |
| etcd disk full | Expand volume, then compact: `etcdctl defrag` |
| etcd member failed in 3-node HA cluster | Remove failed member, add new member (no restore needed) |

---

## Structure of Network Policy

By default, all pods in a Kubernetes cluster can communicate with all other pods across all namespaces. **NetworkPolicies** are firewall rules that restrict this traffic.

### Key Concepts

```
NetworkPolicy works at Layer 3/4 (IP + port).
It is enforced by the CNI plugin (Calico, Cilium, etc.) — NOT by kube-proxy.
If your CNI does not support NetworkPolicy, the policy objects exist but have NO effect.
```

### NetworkPolicy Anatomy

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: my-policy
  namespace: default       # policy applies to pods in THIS namespace
spec:
  podSelector:             # which pods THIS policy applies to
    matchLabels:
      app: backend

  policyTypes:             # what types of traffic to control
  - Ingress                # incoming traffic to selected pods
  - Egress                 # outgoing traffic from selected pods

  ingress:
  - from:                  # allow traffic FROM these sources
    - podSelector:
        matchLabels:
          app: frontend    # only pods with this label in SAME namespace
    - namespaceSelector:
        matchLabels:
          env: production  # OR pods in namespaces with this label
    ports:
    - protocol: TCP
      port: 8080           # only on this port

  egress:
  - to:
    - ipBlock:
        cidr: 10.0.0.0/24  # allow outbound to this CIDR
        except:
        - 10.0.0.5/32      # but not this specific IP
    ports:
    - protocol: TCP
      port: 5432           # only on this port
```

### Default Behaviors

| Situation | Result |
|-----------|--------|
| No NetworkPolicy exists for a pod | Pod accepts all ingress and sends all egress |
| NetworkPolicy with `podSelector: {}` (empty) | Applies to ALL pods in namespace |
| NetworkPolicy exists but has no `ingress:` rules and `Ingress` is in `policyTypes` | All ingress is DENIED |
| NetworkPolicy exists but has no `egress:` rules and `Egress` is in `policyTypes` | All egress is DENIED |

### Default-Deny All Policy (Best Practice)

```yaml
# Apply this first, then add allow rules
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: default
spec:
  podSelector: {}       # matches ALL pods in namespace
  policyTypes:
  - Ingress
  - Egress
```

---

## Practical — Network Policies

### Scenario: Frontend → Backend → Database

```
[ frontend pods ] --:8080--> [ backend pods ] --:5432--> [ postgres pods ]
```

```bash
# Label the namespaces and pods
kubectl create namespace app

kubectl run frontend --image=nginx:1.27 -n app --labels="tier=frontend"
kubectl run backend  --image=nginx:1.27 -n app --labels="tier=backend"
kubectl run postgres --image=postgres:16 -n app --labels="tier=database" \
  --env="POSTGRES_PASSWORD=secret"
```

```yaml
# 1. Default deny all in the app namespace
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny
  namespace: app
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
---
# 2. Allow frontend to reach backend on port 8080
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-frontend-to-backend
  namespace: app
spec:
  podSelector:
    matchLabels:
      tier: backend
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          tier: frontend
    ports:
    - protocol: TCP
      port: 8080
---
# 3. Allow backend to reach postgres on port 5432
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-backend-to-db
  namespace: app
spec:
  podSelector:
    matchLabels:
      tier: database
  policyTypes:
  - Ingress
  ingress:
  - from:
    - podSelector:
        matchLabels:
          tier: backend
    ports:
    - protocol: TCP
      port: 5432
---
# 4. Allow all pods DNS egress (without this, pods can't resolve service names)
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-dns-egress
  namespace: app
spec:
  podSelector: {}
  policyTypes:
  - Egress
  egress:
  - to:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: kube-system
    ports:
    - protocol: UDP
      port: 53
    - protocol: TCP
      port: 53
```

```bash
kubectl apply -f the-above-policies.yaml

# Test: frontend can reach backend
kubectl exec frontend -n app -- wget -qO- http://backend:8080

# Test: frontend CANNOT reach postgres
kubectl exec frontend -n app -- nc -zv postgres 5432
# Expected: connection refused / timed out
```

---

## Network Policies — Except, Port and Protocol

### `ipBlock` with `except`

Use `ipBlock` to control traffic to/from external IP ranges, and `except` to carve out specific IPs within that range.

```yaml
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-external-except-sensitive
  namespace: default
spec:
  podSelector:
    matchLabels:
      app: api
  policyTypes:
  - Egress
  egress:
  - to:
    - ipBlock:
        cidr: 0.0.0.0/0       # allow all external traffic
        except:
        - 169.254.0.0/16      # block AWS/GCP metadata server
        - 10.0.0.0/8          # block internal RFC-1918
        - 172.16.0.0/12
        - 192.168.0.0/16
```

### Multiple Ports in a Single Rule

```yaml
ingress:
- from:
  - podSelector:
      matchLabels:
        app: monitoring
  ports:
  - protocol: TCP
    port: 9090        # prometheus metrics
  - protocol: TCP
    port: 9091        # push gateway
  - protocol: TCP
    port: 8080        # health endpoint
```

### Port Range (Kubernetes v1.25+)

```yaml
ports:
- protocol: TCP
  port: 30000
  endPort: 32767      # allows ports 30000 through 32767 (NodePort range)
```

### Protocol Options

```yaml
ports:
- protocol: TCP    # HTTP, HTTPS, gRPC, Postgres, MySQL
- protocol: UDP    # DNS (port 53), NTP, statsd
- protocol: SCTP   # telecom/SIP protocols
```

### Combined Selector Logic

```yaml
# AND logic — source must match BOTH selectors simultaneously
ingress:
- from:
  - podSelector:
      matchLabels:
        role: frontend
    namespaceSelector:           # same list item = AND
      matchLabels:
        env: production

# OR logic — source can match EITHER selector
ingress:
- from:
  - podSelector:                 # separate list items = OR
      matchLabels:
        role: frontend
  - namespaceSelector:
      matchLabels:
        env: staging
```

---

## Taints and Tolerations

Taints and Tolerations control which pods can be scheduled on which nodes. A taint on a node **repels** pods — unless the pod has a matching toleration.

### Concept

```
Node taint:        key=value:effect
Pod toleration:    key=value:effect  (must match to "tolerate" the taint)
```

### Taint Effects

| Effect | Behavior |
|--------|----------|
| `NoSchedule` | New pods without the toleration will NOT be scheduled on this node |
| `PreferNoSchedule` | Scheduler will try to avoid this node but won't hard-block it |
| `NoExecute` | New pods are blocked AND existing pods without toleration are EVICTED |

### Adding and Removing Taints

```bash
# Add a taint to a node
kubectl taint nodes k8s-worker-1 gpu=true:NoSchedule

# Add multiple taints
kubectl taint nodes k8s-worker-1 env=prod:NoSchedule
kubectl taint nodes k8s-worker-1 dedicated=ml:NoExecute

# View taints on all nodes
kubectl get nodes -o json | jq '.items[] | {name: .metadata.name, taints: .spec.taints}'

# Remove a taint (append a minus sign)
kubectl taint nodes k8s-worker-1 gpu=true:NoSchedule-

# Remove all taints with a key
kubectl taint nodes k8s-worker-1 gpu-
```

### Adding Tolerations to a Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: gpu-workload
spec:
  tolerations:
  # Exact match — key, value, and effect must all match
  - key: "gpu"
    operator: "Equal"
    value: "true"
    effect: "NoSchedule"

  # Exists match — only the key needs to match (any value)
  - key: "dedicated"
    operator: "Exists"
    effect: "NoExecute"
    tolerationSeconds: 300    # pod is evicted after 300s if still running

  # Empty key — tolerates ALL taints with the given effect
  - operator: "Exists"
    effect: "NoSchedule"

  containers:
  - name: gpu-app
    image: nvidia/cuda:12.0-base
```

### Real-World Use Cases

```bash
# 1. Reserve a node for monitoring only
kubectl taint nodes monitoring-node dedicated=monitoring:NoSchedule
# Add toleration only to prometheus/grafana pods

# 2. Mark a node as not ready for maintenance
kubectl taint nodes k8s-worker-2 maintenance=true:NoExecute
# All pods without toleration are evicted immediately

# 3. Control-plane isolation (default in kubeadm clusters)
# This taint prevents user pods from landing on the master
kubectl taint nodes k8s-master node-role.kubernetes.io/control-plane:NoSchedule
# To allow user pods on master (single-node dev cluster):
kubectl taint nodes k8s-master node-role.kubernetes.io/control-plane:NoSchedule-

# 4. Node-specific dedicated GPU node
kubectl taint nodes gpu-node01 nvidia.com/gpu=present:NoSchedule
```

### Taint vs NodeSelector vs NodeAffinity

| Mechanism | Direction | Use When |
|-----------|-----------|----------|
| `taint + toleration` | Node repels pods | You want to PROTECT a node from most pods |
| `nodeSelector` | Pod attracts to nodes | Simple label-based placement |
| `nodeAffinity` | Pod attracts to nodes | Complex rules with required/preferred |
| `podAffinity` | Pod attracts to other pods | Co-locate pods on same node |
| `podAntiAffinity` | Pod repels other pods | Spread replicas across nodes |

---

## Custom Resource Definition

CRDs let you extend the Kubernetes API with your own resource types. Once a CRD is registered, you can `kubectl apply`, `kubectl get`, `kubectl describe` your custom objects just like built-in resources.

### Anatomy of a CRD

```yaml
apiVersion: apiextensions.k8s.io/v1
kind: CustomResourceDefinition
metadata:
  name: backuppolicies.storage.example.com   # must be: <plural>.<group>
spec:
  group: storage.example.com                 # API group (like "apps" in Deployment)
  versions:
  - name: v1
    served: true      # this version is served by the API
    storage: true     # this version is used for storage in etcd
    schema:
      openAPIV3Schema:
        type: object
        properties:
          spec:
            type: object
            required: ["schedule", "targetPVC"]
            properties:
              schedule:
                type: string
                description: "Cron expression for backup schedule"
              targetPVC:
                type: string
                description: "Name of PVC to back up"
              retainDays:
                type: integer
                minimum: 1
                maximum: 365
                default: 7
          status:
            type: object
            properties:
              lastBackup:
                type: string
              phase:
                type: string
                enum: [Pending, Running, Succeeded, Failed]
    subresources:
      status: {}              # enables /status subresource
    additionalPrinterColumns:
    - name: Schedule
      type: string
      jsonPath: .spec.schedule
    - name: Last-Backup
      type: string
      jsonPath: .status.lastBackup
    - name: Age
      type: date
      jsonPath: .metadata.creationTimestamp
  scope: Namespaced           # or Cluster
  names:
    plural: backuppolicies
    singular: backuppolicy
    kind: BackupPolicy
    shortNames:
    - bp
```

### Register and Use the CRD

```bash
kubectl apply -f backuppolicy-crd.yaml

# Verify the CRD is registered
kubectl get crd backuppolicies.storage.example.com
kubectl describe crd backuppolicies.storage.example.com

# Discover the new API endpoints
kubectl api-resources | grep storage.example.com
kubectl api-versions | grep storage.example.com
```

### Create a Custom Resource (CR) Instance

```yaml
apiVersion: storage.example.com/v1
kind: BackupPolicy
metadata:
  name: postgres-backup
  namespace: default
spec:
  schedule: "0 2 * * *"     # daily at 2am
  targetPVC: postgres-data
  retainDays: 14
```

```bash
kubectl apply -f postgres-backup-cr.yaml

# Use like any other resource
kubectl get backuppolicies
kubectl get bp                              # shortname works
kubectl describe bp postgres-backup
kubectl get bp postgres-backup -o yaml

# Delete
kubectl delete bp postgres-backup
```

### CRD with Validation

```yaml
# Validation rules with CEL (Common Expression Language) — K8s 1.25+
x-kubernetes-validations:
- rule: "self.retainDays >= 1 && self.retainDays <= 365"
  message: "retainDays must be between 1 and 365"
- rule: "self.schedule.matches('^[0-9*/ ]+$')"
  message: "schedule must be a valid cron expression"
```

---

## Editing Existing Kubernetes Resources

### `kubectl edit` — In-Place Interactive Edit

Opens the object in your `$EDITOR` (usually vim). Save and quit to apply.

```bash
# Edit a deployment — changes are applied on save
kubectl edit deployment nginx

# Edit with a specific editor
KUBE_EDITOR=nano kubectl edit configmap app-config

# Edit a resource in a specific namespace
kubectl edit service webapp -n production
```

### `kubectl patch` — Programmatic Partial Update

Use when you need to change one field without opening an editor — great for automation and scripts.

```bash
# Strategic Merge Patch — merges the JSON with the existing object
kubectl patch deployment nginx -p '{"spec":{"replicas":5}}'

# JSON Merge Patch — full replacement of the patched section
kubectl patch deployment nginx --type=merge \
  -p '{"spec":{"template":{"spec":{"containers":[{"name":"nginx","image":"nginx:1.27"}]}}}}'

# JSON Patch — RFC 6902, explicit path operations (add/remove/replace/move/copy/test)
kubectl patch deployment nginx --type=json \
  -p '[{"op":"replace","path":"/spec/replicas","value":3}]'

# Add a new label
kubectl patch node k8s-worker-1 --type=json \
  -p '[{"op":"add","path":"/metadata/labels/gpu","value":"true"}]'

# Remove a field
kubectl patch deployment nginx --type=json \
  -p '[{"op":"remove","path":"/spec/template/spec/containers/0/resources"}]'
```

### `kubectl replace` — Full Object Replacement

Replaces the entire object. The resource must already exist.

```bash
# Export, modify, replace
kubectl get deployment nginx -o yaml > nginx-deploy.yaml
# Edit nginx-deploy.yaml ...
kubectl replace -f nginx-deploy.yaml

# Force replace — deletes and recreates (use for immutable fields)
kubectl replace --force -f nginx-deploy.yaml
```

### `kubectl apply` — Declarative (Recommended)

```bash
# Apply changes from a file or directory
kubectl apply -f my-app/

# Apply and record the change for rollback
kubectl apply -f deployment.yaml

# Dry run — see what would change without applying
kubectl apply -f deployment.yaml --dry-run=client
kubectl apply -f deployment.yaml --dry-run=server
```

### Editing Immutable Fields

Some fields cannot be changed on a running resource:

```bash
# These fields are immutable on a running Pod:
# - spec.containers[*].name
# - spec.nodeName
# - spec.serviceAccountName

# For Deployments, you CAN change container image:
kubectl set image deployment/nginx nginx=nginx:1.27
kubectl rollout status deployment/nginx
kubectl rollout history deployment/nginx

# For Jobs: selector is immutable — you must delete and recreate
kubectl delete job my-job
kubectl apply -f my-job.yaml
```

---

## Capacity, Allocated, and Allocatable

### Concepts

```
Node Capacity       = Total physical resources on the node (CPU cores, RAM)
Node Allocatable    = Capacity minus reserved resources for OS + system daemons
Pod Requests        = What a pod ASKS for (used for scheduling decisions)
Pod Limits          = Maximum a pod can USE before being throttled/OOM-killed
Allocated           = Sum of all requests from pods currently on the node
```

### Visualizing Node Resources

```bash
# See capacity vs allocatable for all nodes
kubectl describe node k8s-worker-1

# Look for this section in the output:
# Capacity:
#   cpu:                4
#   memory:             8157952Ki
#   pods:               110
# Allocatable:
#   cpu:                3800m          ← 200m reserved for system
#   memory:             7655552Ki      ← 502400Ki reserved for system
#   pods:               110
# Allocated resources:
#   (Total limits may be over 100 percent, i.e., overcommitted.)
#   Resource           Requests     Limits
#   --------           --------     ------
#   cpu                1150m (30%)  2200m (57%)
#   memory             840Mi (11%)  1540Mi (20%)
```

### System Resource Reservations

When setting up kubelet, you should reserve resources for OS processes so pods don't starve the system:

```yaml
# In /var/lib/kubelet/config.yaml
systemReserved:
  cpu: "200m"
  memory: "200Mi"
kubeReserved:
  cpu: "100m"
  memory: "100Mi"
evictionHard:
  memory.available: "200Mi"    # evict pods before node runs out of RAM
  nodefs.available: "10%"      # evict when disk drops below 10%
  nodefs.inodesFree: "5%"
```

### Checking Resource Utilization

```bash
# Node resource usage (requires metrics-server)
kubectl top nodes

# Pod resource usage
kubectl top pods
kubectl top pods --sort-by=cpu
kubectl top pods --sort-by=memory

# All pods in a namespace
kubectl top pods -n kube-system

# Check if a pod is being throttled (CPU) or OOM-killed (Memory)
kubectl describe pod <pod-name> | grep -A5 "Last State"

# Useful: see resource requests vs actual across all namespaces
kubectl get pods -A -o json | jq '
  .items[] |
  {
    ns: .metadata.namespace,
    name: .metadata.name,
    cpu_req: (.spec.containers[0].resources.requests.cpu // "none"),
    mem_req: (.spec.containers[0].resources.requests.memory // "none")
  }
'
```

---

## Exercise — Requests and Limits

### Scenario 1: Set Requests Only

```yaml
# Pod will be scheduled on a node with 500m CPU and 256Mi RAM available
# No limits set — the pod can burst as high as it wants
apiVersion: v1
kind: Pod
metadata:
  name: burst-pod
spec:
  containers:
  - name: app
    image: nginx:1.27
    resources:
      requests:
        cpu: "500m"       # 0.5 CPU core
        memory: "256Mi"   # 256 mebibytes
```

### Scenario 2: Set Both Requests and Limits

```yaml
# Scheduler uses requests to find a node
# Runtime enforces limits — container is throttled/killed if it exceeds
apiVersion: v1
kind: Pod
metadata:
  name: bounded-pod
spec:
  containers:
  - name: app
    image: nginx:1.27
    resources:
      requests:
        cpu: "250m"
        memory: "128Mi"
      limits:
        cpu: "1000m"      # max 1 full CPU core
        memory: "512Mi"   # OOM-killed if it goes over 512Mi
```

### Scenario 3: LimitRange — Default for a Namespace

```yaml
apiVersion: v1
kind: LimitRange
metadata:
  name: default-limits
  namespace: default
spec:
  limits:
  - type: Container
    default:              # applied if container sets no limits
      cpu: "500m"
      memory: "256Mi"
    defaultRequest:       # applied if container sets no requests
      cpu: "100m"
      memory: "64Mi"
    max:                  # no container in this namespace can exceed
      cpu: "4"
      memory: "4Gi"
    min:                  # no container can request less than
      cpu: "50m"
      memory: "32Mi"
```

### Scenario 4: ResourceQuota — Namespace Budget

```yaml
apiVersion: v1
kind: ResourceQuota
metadata:
  name: team-quota
  namespace: team-a
spec:
  hard:
    requests.cpu: "10"        # total CPU requests across all pods in namespace
    requests.memory: "20Gi"
    limits.cpu: "20"
    limits.memory: "40Gi"
    pods: "50"                # max 50 pods in this namespace
    services: "10"
    persistentvolumeclaims: "20"
```

```bash
kubectl apply -f limitrange.yaml
kubectl apply -f resourcequota.yaml

# View quota usage
kubectl describe resourcequota team-quota -n team-a

# Output:
# Name:            team-quota
# Namespace:       team-a
# Resource         Used    Hard
# --------         ----    ----
# limits.cpu       3500m   20
# limits.memory    7Gi     40Gi
# pods             7       50
# requests.cpu     1750m   10
# requests.memory  3584Mi  20Gi
```

### CPU Units Reference

```
1 CPU     = 1 vCPU = 1 AWS vCPU = 1 GCP Core = 1 Azure vCore
1000m     = 1 CPU  (m = millicores)
500m      = 0.5 CPU
100m      = 0.1 CPU (1/10th of a core)
```

### Memory Units Reference

```
1Ki  = 1024 bytes     (kibibyte)
1Mi  = 1024 Ki        (mebibyte)  ← use this for memory
1Gi  = 1024 Mi        (gibibyte)
1K   = 1000 bytes     (kilobyte)  ← different from Ki!
1M   = 1000 K         (megabyte)
1G   = 1000 M         (gigabyte)
```

---

## JSONPath

JSONPath is a query language for extracting values from JSON. `kubectl` uses JSONPath in `-o jsonpath=` and `--sort-by=` flags.

### Syntax Reference

| Expression | Meaning |
|-----------|---------|
| `.field` | Access a field |
| `.field.nested` | Access nested field |
| `['field-with-dash']` | Access field with special characters |
| `.items[0]` | First element of an array |
| `.items[-1]` | Last element of an array |
| `.items[*]` | All elements of an array |
| `.items[0:2]` | Elements 0 and 1 (slice) |
| `.items[*].metadata.name` | Extract name from every item |
| `{range .items[*]}{.metadata.name}{"\n"}{end}` | Loop over items |

### Common kubectl JSONPath Examples

```bash
# Get a single value
kubectl get node k8s-master -o jsonpath='{.metadata.name}'

# Get multiple values with space
kubectl get pod nginx -o jsonpath='{.metadata.name} {.status.podIP}'

# Get all pod names
kubectl get pods -o jsonpath='{.items[*].metadata.name}'

# Get all pod names, one per line using range
kubectl get pods -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}'

# Get all container images in all pods
kubectl get pods -A -o jsonpath='{range .items[*]}{.metadata.namespace}{"/"}{.metadata.name}{"\t"}{.spec.containers[0].image}{"\n"}{end}'

# Get node internal IP
kubectl get node k8s-worker-1 \
  -o jsonpath='{.status.addresses[?(@.type=="InternalIP")].address}'

# Conditional filter — only InternalIP type
kubectl get nodes \
  -o jsonpath='{.items[*].status.addresses[?(@.type=="InternalIP")].address}'

# Get all PVC names and their storage class
kubectl get pvc -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.spec.storageClassName}{"\n"}{end}'

# Sort pods by creation time
kubectl get pods --sort-by='.metadata.creationTimestamp'

# Sort pods by CPU requests
kubectl get pods --sort-by='.spec.containers[0].resources.requests.cpu'
```

### Custom Columns (often cleaner than JSONPath)

```bash
# Custom output with column headers
kubectl get pods -o custom-columns=\
"NAME:.metadata.name,\
STATUS:.status.phase,\
NODE:.spec.nodeName,\
IP:.status.podIP"

# Node CPU allocatable
kubectl get nodes -o custom-columns=\
"NAME:.metadata.name,\
CPU:.status.allocatable.cpu,\
MEMORY:.status.allocatable.memory"
```

### JSONPath with Filters

```bash
# Get pods NOT in Running state
kubectl get pods -A \
  -o jsonpath='{range .items[?(@.status.phase!="Running")]}{.metadata.namespace}{"/"}{.metadata.name}{"\t"}{.status.phase}{"\n"}{end}'

# Get all images used in a namespace
kubectl get pods -n kube-system \
  -o jsonpath='{range .items[*]}{range .spec.containers[*]}{.image}{"\n"}{end}{end}' | sort -u

# Get environment variables from a specific container
kubectl get pod nginx \
  -o jsonpath='{.spec.containers[?(@.name=="nginx")].env}'
```

---

## Configuring cri-dockerd

`cri-dockerd` is a shim that lets Kubernetes use Docker Engine as its container runtime via the CRI (Container Runtime Interface). This is required if you need to continue using Docker instead of containerd or CRI-O.

> **Background:** Docker support was removed from Kubernetes (via dockershim) in v1.24. If you have legacy workloads that depend on Docker specifically, install `cri-dockerd` as the bridge.

### When to Use cri-dockerd

```
Use cri-dockerd if:
  - You have existing Docker-based workflows or CI/CD pipelines
  - You need docker-in-docker patterns
  - Your team is not ready to migrate to containerd

Use containerd directly if:
  - This is a new cluster (recommended for K8s 1.35)
  - You want better performance and fewer moving parts
```

### Install Docker Engine

```bash
# Install Docker (if not already installed)
sudo apt-get update
sudo apt-get install -y docker-ce docker-ce-cli containerd.io

# Verify Docker is running
sudo docker version
sudo systemctl status docker
```

### Install cri-dockerd

```bash
# Get the latest release version
CRI_DOCKERD_VERSION="0.3.15"
ARCH="amd64"

# Download the binary
wget -q https://github.com/Mirantis/cri-dockerd/releases/download/v${CRI_DOCKERD_VERSION}/cri-dockerd-${CRI_DOCKERD_VERSION}.amd64.tgz

# Extract and install
tar -xf cri-dockerd-${CRI_DOCKERD_VERSION}.amd64.tgz
sudo mv cri-dockerd/cri-dockerd /usr/local/bin/
chmod +x /usr/local/bin/cri-dockerd

# Verify
cri-dockerd --version
```

### Create cri-dockerd systemd Service

```bash
# Download the official systemd unit files from the repo
wget https://raw.githubusercontent.com/Mirantis/cri-dockerd/master/packaging/systemd/cri-docker.service
wget https://raw.githubusercontent.com/Mirantis/cri-dockerd/master/packaging/systemd/cri-docker.socket

sudo mv cri-docker.service /etc/systemd/system/
sudo mv cri-docker.socket  /etc/systemd/system/

# Fix the binary path in the service file
sudo sed -i 's|/usr/bin/cri-dockerd|/usr/local/bin/cri-dockerd|g' \
  /etc/systemd/system/cri-docker.service

# Start and enable
sudo systemctl daemon-reload
sudo systemctl enable --now cri-docker.socket
sudo systemctl enable --now cri-docker.service

sudo systemctl status cri-docker --no-pager

# Verify the socket exists
ls -la /var/run/cri-dockerd.sock
```

### Configure kubelet to Use cri-dockerd

```bash
# In the kubelet service file, change the runtime socket:
# From: unix:///var/run/containerd/containerd.sock
# To:   unix:///var/run/cri-dockerd.sock

sudo sed -i 's|unix:///var/run/containerd/containerd.sock|unix:///var/run/cri-dockerd.sock|g' \
  /var/lib/kubelet/config.yaml

# Also update the ExecStart line in kubelet.service if --container-runtime-endpoint is set there
sudo systemctl daemon-reload
sudo systemctl restart kubelet

# Verify kubelet is using cri-dockerd
sudo journalctl -u kubelet -n 20 --no-pager | grep -i cri
```

### Using cri-dockerd with kubeadm

```bash
# When initializing with kubeadm, specify the cri-dockerd socket
sudo kubeadm init \
  --kubernetes-version=v1.35.0 \
  --pod-network-cidr=192.168.0.0/16 \
  --cri-socket=unix:///var/run/cri-dockerd.sock

# When joining workers
sudo kubeadm join <master-ip>:6443 \
  --token <token> \
  --discovery-token-ca-cert-hash sha256:<hash> \
  --cri-socket=unix:///var/run/cri-dockerd.sock
```

### Verify Runtime in Use

```bash
# Check what runtime each node reports
kubectl get nodes -o wide
# CONTAINER-RUNTIME column should show: docker://XX.X.X

# Or via jsonpath
kubectl get nodes -o jsonpath='{range .items[*]}{.metadata.name}{"\t"}{.status.nodeInfo.containerRuntimeVersion}{"\n"}{end}'

# Check via crictl (CRI debug tool)
sudo crictl --runtime-endpoint unix:///var/run/cri-dockerd.sock ps
sudo crictl --runtime-endpoint unix:///var/run/cri-dockerd.sock images
```

### cri-dockerd vs containerd Comparison

| Feature | cri-dockerd + Docker | containerd (native) |
|---------|---------------------|---------------------|
| Docker CLI works | Yes | No |
| `docker build` works on node | Yes | No (use buildkit) |
| Performance overhead | Higher (two daemons) | Lower (single daemon) |
| Memory usage | Higher | Lower |
| K8s 1.35 recommended | No — legacy path | Yes |
| Image format | OCI + Docker | OCI only |
| Troubleshooting tool | `docker ps` | `crictl ps` |

---

## Summary: Control Plane Startup Order

```
1. containerd / cri-dockerd  ← must be running before kubelet
2. etcd                       ← must be running before kube-apiserver
3. kube-apiserver             ← must be running before CM + Scheduler
4. kube-controller-manager    ← starts after API server
5. kube-scheduler             ← starts after API server
6. kubelet (workers)          ← connects to API server
7. kube-proxy (workers)       ← connects to API server
8. Calico CNI                 ← deployed via kubectl after API server is up
9. CoreDNS                    ← deployed via kubectl after CNI is up
```

## Component Version Matrix — K8s v1.35

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
│ containerd               │ v2.0.4                    │
│ pause image              │ registry.k8s.io/pause:3.10│
├──────────────────────────┼───────────────────────────┤
│ Calico CNI               │ v3.29.0                   │
│ CoreDNS                  │ v1.12.0                   │
└──────────────────────────┴───────────────────────────┘

Service CIDR:  10.96.0.0/12
Pod CIDR:      192.168.0.0/16   (Calico)
DNS ClusterIP: 10.96.0.10

Removed in v1.35:
  --allow-privileged on kube-apiserver  ← remove from service files
```

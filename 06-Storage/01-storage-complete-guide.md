# Kubernetes Storage — Complete Guide

> Storage in Kubernetes bridges stateful applications with persistent data. Pods are ephemeral — storage must not be.

---

## Table of Contents

1. [Why Storage Matters in Kubernetes](#1-why-storage-matters-in-kubernetes)
2. [Volumes — Ephemeral Pod Storage](#2-volumes--ephemeral-pod-storage)
3. [PersistentVolume (PV)](#3-persistentvolume-pv)
4. [PersistentVolumeClaim (PVC)](#4-persistentvolumeclaim-pvc)
5. [StorageClass — Dynamic Provisioning](#5-storageclass--dynamic-provisioning)
6. [Access Modes](#6-access-modes)
7. [Reclaim Policies](#7-reclaim-policies)
8. [Volume Binding and Lifecycle](#8-volume-binding-and-lifecycle)
9. [Common Volume Types](#9-common-volume-types)
10. [ConfigMap and Secret as Volumes](#10-configmap-and-secret-as-volumes)
11. [StatefulSet Storage](#11-statefulset-storage)
12. [CSI — Container Storage Interface](#12-csi--container-storage-interface)
13. [Volume Snapshots](#13-volume-snapshots)
14. [Common Interview Questions](#14-common-interview-questions)
15. [Exam Practice Questions](#15-exam-practice-questions)

---

## 1. Why Storage Matters in Kubernetes

```
  Problem: Pods are ephemeral
  
  Pod gets deleted → all data inside is lost
  Pod gets restarted → all data inside is lost
  Pod moves to another node → data doesn't follow it
  
  
  Solution: Decouple storage from the Pod lifecycle
  
  Pod  ──────────┐
  (ephemeral)    │ mounts
                 ▼
           PersistentVolume  ──── actual storage (disk, NFS, cloud)
           (independent of Pod)
  
  Pod dies → PV remains → new Pod mounts same PV → data intact
```

---

## 2. Volumes — Ephemeral Pod Storage

A Volume is storage attached to a Pod. It **lives as long as the Pod lives** (unlike containers, which restart independently).

### emptyDir — Temporary Shared Storage Between Containers

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: shared-storage-pod
spec:
  containers:
  - name: writer
    image: busybox
    command: ["/bin/sh", "-c", "echo hello > /data/file.txt; sleep 3600"]
    volumeMounts:
    - name: shared-data
      mountPath: /data

  - name: reader
    image: busybox
    command: ["/bin/sh", "-c", "cat /data/file.txt; sleep 3600"]
    volumeMounts:
    - name: shared-data
      mountPath: /data

  volumes:
  - name: shared-data
    emptyDir: {}                      # ← created fresh when Pod starts, deleted when Pod dies
```

> Use cases: cache, temporary processing, sharing files between init-container and main container.

### hostPath — Mount from Node Filesystem

```yaml
volumes:
- name: host-logs
  hostPath:
    path: /var/log/app                # ← path on the NODE filesystem
    type: DirectoryOrCreate           # create if doesn't exist
```

```
  hostPath types:
  ""                 → no type check
  DirectoryOrCreate  → create directory if missing
  Directory          → directory must exist
  FileOrCreate       → create file if missing
  File               → file must exist
  Socket             → Unix socket must exist
  CharDevice         → character device must exist
  BlockDevice        → block device must exist
```

> **Security risk**: hostPath can expose the node filesystem to the Pod. Avoid in production unless necessary (e.g., DaemonSets collecting logs).

---

## 3. PersistentVolume (PV)

A PV is a piece of storage in the cluster, **provisioned independently from any Pod**. It represents an actual storage backend: an EBS volume, NFS share, GCE disk, etc.

```yaml
apiVersion: v1
kind: PersistentVolume
metadata:
  name: my-pv
spec:
  capacity:
    storage: 10Gi                     # ← size of this storage
  accessModes:
  - ReadWriteOnce                     # ← who can mount and how
  persistentVolumeReclaimPolicy: Retain  # ← what happens when PVC is deleted
  storageClassName: standard          # ← storage class name (or "" for no class)
  
  # Backend-specific configuration (pick one):
  
  # Option A: Local storage (for testing)
  hostPath:
    path: /mnt/data

  # Option B: NFS
  nfs:
    server: nfs-server.example.com
    path: /exports/data

  # Option C: AWS EBS (static provisioning)
  awsElasticBlockStore:
    volumeID: vol-0abcdef1234567890
    fsType: ext4
```

### PV Status

```
  Available  → PV exists, not yet claimed by any PVC
  Bound      → PV is claimed by a PVC
  Released   → PVC was deleted, but PV not yet reclaimed
  Failed     → Automatic reclamation failed
```

---

## 4. PersistentVolumeClaim (PVC)

A PVC is a **request for storage** from a user/Pod. It says "I need 5Gi of ReadWriteOnce storage." Kubernetes finds a matching PV and binds them together.

```yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: my-pvc
  namespace: default
spec:
  accessModes:
  - ReadWriteOnce                     # ← must match PV's accessModes
  resources:
    requests:
      storage: 5Gi                    # ← request at least 5Gi
  storageClassName: standard          # ← must match PV's storageClassName
  
  # Optional: bind to a specific PV
  # volumeName: my-pv
```

### Use PVC in a Pod

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: app-pod
spec:
  containers:
  - name: app
    image: nginx
    volumeMounts:
    - name: data-volume
      mountPath: /usr/share/nginx/html
  volumes:
  - name: data-volume
    persistentVolumeClaim:
      claimName: my-pvc               # ← reference to the PVC
```

### PVC Binding Logic

```
  PVC requests: 5Gi, ReadWriteOnce, storageClass=standard
  
  Kubernetes searches for PV that:
  1. Has storageClassName: standard
  2. Supports ReadWriteOnce access mode
  3. Has capacity >= 5Gi
  4. Is in Available state
  
  Found PV with 10Gi → bound! (PVC gets 10Gi capacity, not just 5Gi)
```

---

## 5. StorageClass — Dynamic Provisioning

StorageClass enables **automatic PV creation** when a PVC is created. No need to manually create PVs.

```yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: fast-ssd
  annotations:
    storageclass.kubernetes.io/is-default-class: "true"   # ← default SC
provisioner: ebs.csi.aws.com                               # ← which CSI driver to use
parameters:
  type: gp3                                                # ← driver-specific params
  iops: "3000"
  throughput: "125"
reclaimPolicy: Delete                                      # ← delete PV when PVC deleted
volumeBindingMode: WaitForFirstConsumer                    # ← wait until Pod is scheduled
allowVolumeExpansion: true                                 # ← allow PVC resize
```

### Common Provisioners

| Cloud | Provisioner |
|-------|-------------|
| AWS EBS | `ebs.csi.aws.com` |
| GCE PD | `pd.csi.storage.gke.io` |
| Azure Disk | `disk.csi.azure.com` |
| NFS | `nfs.csi.k8s.io` |
| Local | `kubernetes.io/no-provisioner` |

### Dynamic Provisioning Flow

```
  User creates PVC
        │
        ▼
  PVC references StorageClass "fast-ssd"
        │
        ▼
  StorageClass provisioner (ebs.csi.aws.com) called
        │
        ▼
  AWS creates new EBS volume
        │
        ▼
  PV is auto-created and bound to PVC
        │
        ▼
  Pod can mount the PVC
```

### Default StorageClass

If a PVC doesn't specify a storageClassName, the **default StorageClass** is used:

```bash
# View StorageClasses
kubectl get storageclass

# Output:
# NAME              PROVISIONER             RECLAIMPOLICY   VOLUMEBINDINGMODE
# standard (default) kubernetes.io/gce-pd  Delete          Immediate
# fast-ssd           ebs.csi.aws.com       Delete          WaitForFirstConsumer
```

```bash
# Set a StorageClass as default
kubectl patch storageclass standard \
  -p '{"metadata": {"annotations":{"storageclass.kubernetes.io/is-default-class":"true"}}}'
```

---

## 6. Access Modes

Access modes define **how a volume can be mounted** across nodes and pods.

| Access Mode | Short | Description |
|-------------|-------|-------------|
| `ReadWriteOnce` | RWO | Read/write by a single node at a time |
| `ReadOnlyMany` | ROX | Read-only by many nodes simultaneously |
| `ReadWriteMany` | RWX | Read/write by many nodes simultaneously |
| `ReadWriteOncePod` | RWOP | Read/write by a single Pod (K8s 1.22+) |

```
  ReadWriteOnce (RWO):      ReadWriteMany (RWX):
  
  Node A (Pod A) ← RW       Node A (Pod A) ← RW
  Node B         ✗           Node B (Pod B) ← RW
  Node C         ✗           Node C (Pod C) ← RW
  
  Most block storage (EBS, GCE PD) = RWO
  NFS, Ceph, EFS = can support RWX
```

> **CKA Tip**: Most exam questions use `ReadWriteOnce`. Know that NFS/CephFS support `ReadWriteMany`.

---

## 7. Reclaim Policies

What happens to the PV after its PVC is deleted?

| Policy | Description |
|--------|-------------|
| `Retain` | PV data is preserved. Manual cleanup required. PV goes to `Released` state. |
| `Delete` | PV and underlying storage are deleted automatically. |
| `Recycle` (deprecated) | Basic scrub (`rm -rf /volume/*`) — deprecated, use dynamic provisioning. |

```
  RETAIN (safe for production data):
  
  PVC deleted → PV status: Released (not Available!)
              → Data still on disk
              → Admin manually verifies data, then deletes PV
              → New PVC cannot bind to this PV (Released ≠ Available)

  DELETE (default for dynamic provisioning):
  
  PVC deleted → PV deleted → underlying EBS/GCE disk deleted
              → Data is gone permanently
```

```bash
# Change reclaim policy on existing PV
kubectl patch pv my-pv \
  -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'
```

---

## 8. Volume Binding and Lifecycle

```
  Full lifecycle of PV + PVC:

  1. PROVISIONING
     Static: Admin creates PV manually
     Dynamic: PVC created → StorageClass auto-creates PV

  2. BINDING
     PVC found matching PV → both get status "Bound"
     One PVC ←→ One PV (1-to-1 exclusive binding)

  3. USING
     Pod mounts PVC → accesses the storage

  4. RELEASING
     Pod deleted
     PVC deleted → PV status becomes "Released"

  5. RECLAIMING
     Delete policy: PV + underlying storage deleted
     Retain policy: PV stays as "Released", data preserved
```

---

## 9. Common Volume Types

### nfs — Network File System

```yaml
volumes:
- name: nfs-vol
  nfs:
    server: 192.168.1.50
    path: /exported/data
    readOnly: false
```

### configMap — Mount ConfigMap as Files

```yaml
volumes:
- name: config
  configMap:
    name: app-config
```

### secret — Mount Secrets as Files

```yaml
volumes:
- name: creds
  secret:
    secretName: db-credentials
    defaultMode: 0400               # ← read-only for owner
```

### projected — Combine Multiple Volume Sources

```yaml
volumes:
- name: combined
  projected:
    sources:
    - configMap:
        name: app-config
    - secret:
        name: app-secrets
    - serviceAccountToken:
        path: token
        expirationSeconds: 3600
```

---

## 10. ConfigMap and Secret as Volumes

```yaml
apiVersion: v1
kind: Pod
metadata:
  name: config-demo
spec:
  containers:
  - name: app
    image: nginx
    volumeMounts:
    - name: config-vol
      mountPath: /etc/config           # ← each key becomes a file
    - name: secret-vol
      mountPath: /etc/secrets
      readOnly: true
  volumes:
  - name: config-vol
    configMap:
      name: my-config
      items:                           # ← optional: select specific keys
      - key: app.properties
        path: app.properties
  - name: secret-vol
    secret:
      secretName: my-secret
```

Result:
```
  /etc/config/app.properties   ← content from ConfigMap key "app.properties"
  /etc/secrets/username        ← content from Secret key "username"
  /etc/secrets/password        ← content from Secret key "password"
```

---

## 11. StatefulSet Storage

StatefulSets use `volumeClaimTemplates` to create a **dedicated PVC per Pod replica**:

```yaml
apiVersion: apps/v1
kind: StatefulSet
metadata:
  name: postgres
spec:
  replicas: 3
  selector:
    matchLabels:
      app: postgres
  serviceName: postgres
  template:
    metadata:
      labels:
        app: postgres
    spec:
      containers:
      - name: postgres
        image: postgres:15
        volumeMounts:
        - name: data
          mountPath: /var/lib/postgresql/data
  
  volumeClaimTemplates:               # ← PVC template per Pod
  - metadata:
      name: data
    spec:
      accessModes: ["ReadWriteOnce"]
      storageClassName: fast-ssd
      resources:
        requests:
          storage: 20Gi
```

Result:
```
  postgres-0 → data-postgres-0 (PVC) → 20Gi PV
  postgres-1 → data-postgres-1 (PVC) → 20Gi PV
  postgres-2 → data-postgres-2 (PVC) → 20Gi PV

  Each Pod has its OWN dedicated storage!
  If postgres-1 is deleted → data-postgres-1 PVC remains
  When postgres-1 is recreated → it mounts the SAME PVC (data intact)
```

---

## 12. CSI — Container Storage Interface

CSI is the standardized interface for storage providers to integrate with Kubernetes.

```
  Old way (in-tree drivers): Storage code baked into Kubernetes core
  - Required Kubernetes upgrade to update storage driver
  - Limited to drivers merged into k8s codebase

  New way (CSI): Out-of-tree storage plugins as DaemonSets/Deployments
  - Storage vendors ship their own CSI driver
  - Update driver independently of Kubernetes
  - Supports more features: snapshots, cloning, resize

  CSI Architecture:
  
  Kubernetes core  ←→  CSI Interface  ←→  CSI Driver (e.g., aws-ebs-csi-driver)
                                                │
                                         Cloud Provider API
                                         (actually creates/deletes volumes)
```

```bash
# List installed CSI drivers
kubectl get csidrivers

# Common CSI drivers:
# ebs.csi.aws.com          AWS EBS
# pd.csi.storage.gke.io    Google Persistent Disk
# disk.csi.azure.com       Azure Disk
# blob.csi.azure.com       Azure Blob
# efs.csi.aws.com          AWS EFS (ReadWriteMany)
```

---

## 13. Volume Snapshots

CSI enables **volume snapshots** — point-in-time backups of PVs.

```yaml
# Create a snapshot
apiVersion: snapshot.storage.k8s.io/v1
kind: VolumeSnapshot
metadata:
  name: my-snapshot
spec:
  volumeSnapshotClassName: csi-aws-vsc
  source:
    persistentVolumeClaimName: my-pvc   # ← snapshot this PVC

---
# Restore from snapshot (create new PVC)
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: restored-pvc
spec:
  accessModes: ["ReadWriteOnce"]
  resources:
    requests:
      storage: 10Gi
  dataSource:
    name: my-snapshot
    kind: VolumeSnapshot
    apiGroup: snapshot.storage.k8s.io
```

---

## 14. Common Interview Questions

**Q: What is the difference between a PV and a PVC?**
> A PV is the actual storage resource (an EBS volume, NFS share, etc.) provisioned by an admin or dynamically. A PVC is a request for storage by a user/Pod. Kubernetes matches PVCs to available PVs.

**Q: What is a StorageClass and why is it important?**
> StorageClass enables dynamic provisioning — when a PVC is created, the StorageClass automatically creates the PV. Without it, admins must manually create PVs before PVCs can bind.

**Q: What happens to data when a PVC is deleted?**
> Depends on the reclaim policy: `Delete` removes the PV and data; `Retain` keeps the PV (in Released state) with data intact for manual recovery.

**Q: What is ReadWriteMany and when do you need it?**
> RWX allows multiple Pods on different nodes to read/write simultaneously. Needed for shared storage in horizontally scaled apps. Requires NFS, CephFS, or cloud-equivalent (AWS EFS). Standard block storage (EBS, GCE PD) only supports RWO.

**Q: How does StatefulSet differ from Deployment regarding storage?**
> Deployments share a single PVC across all replicas (or each Pod has no persistent storage). StatefulSets use `volumeClaimTemplates` to create a dedicated PVC per Pod — each replica gets its own persistent storage that survives Pod restarts.

**Q: What is CSI?**
> Container Storage Interface — a standardized API that allows storage vendors to write drivers that work with Kubernetes without modifying the Kubernetes codebase. Replaced in-tree storage drivers.

---

## 15. Exam Practice Questions

```
1. Create a PersistentVolume "my-pv" of 1Gi with hostPath /mnt/data, RWO, Retain policy.
   Answer:
   apiVersion: v1
   kind: PersistentVolume
   metadata:
     name: my-pv
   spec:
     capacity:
       storage: 1Gi
     accessModes: [ReadWriteOnce]
     persistentVolumeReclaimPolicy: Retain
     hostPath:
       path: /mnt/data

2. Create a PVC "my-pvc" requesting 500Mi, RWO.
   Answer:
   apiVersion: v1
   kind: PersistentVolumeClaim
   metadata:
     name: my-pvc
   spec:
     accessModes: [ReadWriteOnce]
     resources:
       requests:
         storage: 500Mi

3. Mount PVC "my-pvc" into a Pod at /data.
   Answer:
   volumes:
   - name: data
     persistentVolumeClaim:
       claimName: my-pvc
   # plus volumeMounts with mountPath: /data

4. List all PersistentVolumes and their status.
   Answer:
   kubectl get pv

5. Check which PVC is bound to a specific PV.
   Answer:
   kubectl describe pv my-pv | grep "Claim:"

6. Change reclaim policy of PV "old-pv" to Retain.
   Answer:
   kubectl patch pv old-pv -p '{"spec":{"persistentVolumeReclaimPolicy":"Retain"}}'

7. List all StorageClasses in the cluster.
   Answer:
   kubectl get storageclass

8. Delete a PVC and check what happens to the bound PV (Retain policy).
   Answer:
   kubectl delete pvc my-pvc
   kubectl get pv  # PV should show status: Released
```

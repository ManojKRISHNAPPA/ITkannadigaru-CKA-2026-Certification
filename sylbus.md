# Kubernetes Syllabus – Objects, Services, and Volumes

---

## 1. Kubernetes Objects

1. **Pods**
   * Single-container Pods
   * Multi-container Pods
   * Init Containers
   * Lifecycle Hooks
2. **ReplicaSets**

   * Ensures specified number of pod replicas
   * Scaling Pods
3. **Deployments**

   * Rolling updates
   * Rollback strategies
4. **DaemonSets**

   * Ensures all nodes run a copy of a Pod
5. **StatefulSets**

   * Pods with stable identities and storage
6. **Jobs & CronJobs**

   * One-time tasks (Job)
   * Scheduled tasks (CronJob)
7. **ConfigMaps**

   * Configuration data in key-value pairs
   * Mounting into Pods
   * Immutable ConfigMaps
8. **Secrets**

   * Sensitive data storage
   * Types: Opaque, TLS, Docker-registry, etc.
9. **Namespaces**

   * Logical cluster partitioning
10. **Custom Resource Definitions (CRDs)**

* Extending Kubernetes with custom objects

---

## 2. Kubernetes Services

1. **ClusterIP**

   * Default service type
   * Accessible within the cluster
2. **NodePort**

   * Exposes service on each Node’s IP
3. **LoadBalancer**

   * Cloud provider integration
   * External access with a load balancer
4. **ExternalName**

   * Maps service to an external DNS name
5. **Headless Services**

   * No ClusterIP, used for StatefulSets
6. **Ingress**

   * HTTP/HTTPS routing
   * Rules, Hosts, Paths
   * TLS Termination
7. **Gateway API**

   * Advanced routing & traffic management

---

## 3. Volumes and Storage

1. **emptyDir**

   * Temporary storage for Pod lifecycle
2. **hostPath**

   * Pod storage on host node
3. **PersistentVolume (PV)**

   * Storage resource in cluster
   * Types: NFS, iSCSI, AWS EBS, GCE PD, etc.
4. **PersistentVolumeClaim (PVC)**

   * Requests storage from PV
   * Access modes: ReadWriteOnce, ReadOnlyMany, ReadWriteMany
5. **StorageClass**

   * Dynamic provisioning of PVs
   * Defines provisioner, reclaim policy, and parameters
6. **local Path Provisioner**

   * Dynamic local storage provisioning
7. **ConfigMaps & Secrets as Volumes**

   * Mounting configurations and secrets into Pods
8. **Security Contexts**

   * Permissions and access controls for volumes

---

# AWS EBS CSI Driver — Setup Notes
**Cluster:** `itkannadigaru`
**Region:** `ap-northeast-1`
**OIDC ID:** `3AC8691E0EF5472516FD7A4DDCAD7A8B`
**OIDC URL:** `https://oidc.eks.ap-northeast-1.amazonaws.com/id/3AC8691E0EF5472516FD7A4DDCAD7A8B`

---

## Prerequisites — What was already present

| Component | Status |
|---|---|
| `efs.csi.aws.com` CSI driver | ✅ Already installed |
| `gp2` StorageClass (in-tree driver) | ✅ Already existed |
| `ebs.csi.aws.com` CSI driver | ❌ Needed installation |
| `ebs-sc` StorageClass (gp3) | ❌ Needed creation |
| IAM OIDC + EBS role | ❌ Needed creation |

---

## Step 1 — Verify / Associate IAM OIDC Provider

```bash
# Check if OIDC is already associated
aws iam list-open-id-connect-providers | grep 3AC8691E0EF5472516FD7A4DDCAD7A8B

# If empty, associate it
eksctl utils associate-iam-oidc-provider \
  --region ap-northeast-1 \
  --cluster itkannadigaru \
  --approve
```

---

## Step 2 — Create IAM Service Account with EBS Policy

```bash
eksctl create iamserviceaccount \
  --name ebs-csi-controller-sa \
  --namespace kube-system \
  --cluster itkannadigaru \
  --region ap-northeast-1 \
  --attach-policy-arn arn:aws:iam::aws:policy/service-role/AmazonEBSCSIDriverPolicy \
  --approve \
  --role-only \
  --role-name AmazonEKS_EBS_CSI_DriverRole
```

Verify the trust policy references the correct OIDC ID:

```bash
aws iam get-role \
  --role-name AmazonEKS_EBS_CSI_DriverRole \
  --query 'Role.AssumeRolePolicyDocument' \
  --output json
```

> The trust policy should reference `3AC8691E0EF5472516FD7A4DDCAD7A8B`.

---

## Step 3 — Install EBS CSI Addon

```bash
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

eksctl create addon \
  --name aws-ebs-csi-driver \
  --cluster itkannadigaru \
  --region ap-northeast-1 \
  --service-account-role-arn arn:aws:iam::${ACCOUNT_ID}:role/AmazonEKS_EBS_CSI_DriverRole \
  --force
```

Verify pods are running:

```bash
kubectl get pods -n kube-system | grep ebs
```

Expected output:
```
ebs-csi-controller-xxxxxxxxx-xxxxx   6/6   Running
ebs-csi-node-xxxxx                   3/3   Running   # one per node
ebs-csi-node-xxxxx                   3/3   Running
```

Verify CSI driver registered:

```bash
kubectl get csidrivers
# Should show ebs.csi.aws.com alongside efs.csi.aws.com
```

---

## Step 4 — Create StorageClass

```yaml
# ebs-storageclass.yaml
apiVersion: storage.k8s.io/v1
kind: StorageClass
metadata:
  name: ebs-sc
provisioner: ebs.csi.aws.com
volumeBindingMode: WaitForFirstConsumer
reclaimPolicy: Delete
parameters:
  type: gp3
```

```bash
kubectl apply -f ebs-storageclass.yaml
kubectl get sc
```

> **Note:** `WaitForFirstConsumer` is required because EBS volumes are AZ-scoped.
> The volume is created in the same AZ as the scheduled Pod.

---

## Step 5 — Create PersistentVolumeClaim

```yaml
# ebs-pvc.yaml
apiVersion: v1
kind: PersistentVolumeClaim
metadata:
  name: ebs-pvc
spec:
  accessModes:
    - ReadWriteOnce        # EBS only supports RWO
  storageClassName: ebs-sc
  resources:
    requests:
      storage: 5Gi
```

```bash
kubectl apply -f ebs-pvc.yaml
kubectl get pvc ebs-pvc
# STATUS = Pending is normal here until a Pod consumes it
```

---

## Step 6 — Deploy Pod to Consume PVC

```yaml
# ebs-pod.yaml
apiVersion: v1
kind: Pod
metadata:
  name: ebs-test-pod
spec:
  containers:
    - name: app
      image: nginx
      volumeMounts:
        - mountPath: /data
          name: ebs-storage
  volumes:
    - name: ebs-storage
      persistentVolumeClaim:
        claimName: ebs-pvc
```

```bash
kubectl apply -f ebs-pod.yaml
```

---

## Step 7 — Verify End to End

```bash
# PVC should be Bound once pod is scheduled
kubectl get pvc ebs-pvc

# Pod should be Running
kubectl get pod ebs-test-pod

# Confirm EBS volume is mounted inside the container
kubectl exec ebs-test-pod -- df -h /data

# Full details
kubectl describe pvc ebs-pvc
kubectl describe pod ebs-test-pod
```

Expected final state:

```
NAME      STATUS   VOLUME                                     CAPACITY   ACCESS MODES   STORAGECLASS
ebs-pvc   Bound    pvc-xxxxxxxx-xxxx-xxxx-xxxx-xxxxxxxxxxxx   5Gi        RWO            ebs-sc
```

---

## Key Concepts

| Concept | Detail |
|---|---|
| Provisioner | `ebs.csi.aws.com` (new CSI driver, not legacy `kubernetes.io/aws-ebs`) |
| Access Mode | `ReadWriteOnce` — EBS can only attach to one node at a time |
| Volume Binding | `WaitForFirstConsumer` — EBS volume created in same AZ as Pod |
| Volume Type | `gp3` — latest gen, better performance and cost than gp2 |
| Reclaim Policy | `Delete` — EBS volume deleted when PVC is deleted |

---

## Status: ✅ Working
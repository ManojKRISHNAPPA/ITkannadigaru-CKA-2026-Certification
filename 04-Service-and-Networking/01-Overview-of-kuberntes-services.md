# Overview of Service
1. The Pods that get created in the Worker node have a private IP associated with them.
2. Pods in the same cluster can communicate with each other using Private IPs.
![alt text](IMAGES/image.png)

## Use-Case: Frontend to Backend

If the IP address of the backend pod is hardcoded in the front-end pod, it will create issues since Pods can be ephemeral.

# demo:

```
root@admin-server:~/.kube# kubectl run front-end --image=nginx
pod/front-end created
root@admin-server:~/.kube# kubectl run backend --image=httpd
pod/backend created
root@admin-server:~/.kube#
root@admin-server:~/.kube# kubectl get pods
NAME        READY   STATUS    RESTARTS   AGE
backend     1/1     Running   0          4s
front-end   1/1     Running   0          21s
```

## we can see pod ip using below command:
```
root@admin-server:~# kubectl get pods -o wide
NAME        READY   STATUS    RESTARTS   AGE   IP           NODE           NOMINATED NODE   READINESS GATES
backend     1/1     Running   0          73s   10.1.87.68   admin-server   <none>           <none>
front-end   1/1     Running   0          90s   10.1.87.67   admin-server   <none>           <none>

```

## Since both frontend and backend pods are in the same cluster and having the private IP they can communicate well each other

### Lets test connectivity between frontend to backend pods

```
root@admin-server:~# kubectl get pods -o wide
NAME        READY   STATUS    RESTARTS   AGE   IP           NODE           NOMINATED NODE   READINESS GATES
backend     1/1     Running   0          73s   10.1.87.68   admin-server   <none>           <none>
front-end   1/1     Running   0          90s   10.1.87.67   admin-server   <none>           <none>
root@admin-server:~# kubectl exec -it front-end -- bash
root@front-end:/#
root@front-end:/#
root@front-end:/# curl 10.1.87.68
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<title>It works! Apache httpd</title>
</head>
<body>
<p>It works!</p>
</body>
</html>

```

# Use-Case: Frontend to Backend
- If the IP address of the backend pod is hardcoded in the front-end pod, it will create issues since Pods can be ephemeral.

![alt text](<IMAGES/image copy.png>)

- If backend pods are running as deployment, it is challenging to hardcode the IPs of each backend pod.
- You would also like to distribute the traffic across all the backend pods.

![alt text](<IMAGES/image copy 2.png>)


## now in order to overcome this fetaure we required to use a service.

Service acts as a gateway that distributes incoming traffic between its endpoints.

![alt text](<IMAGES/image copy 3.png>)

```
root@admin-server:~# kubectl get pods -o wide
NAME        READY   STATUS    RESTARTS   AGE   IP           NODE           NOMINATED NODE   READINESS GATES
backend     1/1     Running   0          13m   10.1.87.68   admin-server   <none>           <none>
backend-2   1/1     Running   0          15s   10.1.87.69   admin-server   <none>           <none>
front-end   1/1     Running   0          14m   10.1.87.67   admin-server   <none>           <none>
```

```
root@front-end:/# curl 10.1.87.68

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<title>It works! Apache httpd</title>
</head>
<body>
<p>It works!</p>
</body>
</html>


root@front-end:/# curl 10.1.87.69

<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<title>It works! Apache httpd</title>
</head>
<body>
<p>It works!</p>
</body>
</html>
root@front-end:/#
```

## Now lets try to understand will create one Service for the pods and lets try to curl the request

If you use a Deployment to run your app, that Deployment can create and destroy Pods dynamically.
Service can find the latest set of pods and route the traffic accordingly.

![alt text](<IMAGES/image copy 4.png>)

# Points to Note

- Using Service, users outside of Kubernetes cluster can also connect to the Pods internal to the cluster.
![alt text](<IMAGES/image copy 5.png>)


# Benefits of Service
- Pods are ephemeral, and their IPs change frequently. Services provide a stable endpoint.
- Services distribute traffic across multiple Pod replicas.
- Service enables exposing applications to external traffic like from the Internet

![alt text](<IMAGES/image copy 6.png>)


```
Frontend Pod
      |
      |  curl backend-service
      ↓
Kubernetes Service (ClusterIP)
      ↓
  -------------------------
  |                       |
Backend Pod 1        Backend Pod 2

```

```
kubectl run backend-1 \
  --image=nginx \
  --restart=Never \
  --labels=app=backend \
  -n test
```

```
kubectl run backend-2 \
  --image=nginx \
  --restart=Never \
  --labels=app=backend \
  -n test
```

```
kubectl get pods -n test -o wide
backend-1   1/1   Running
backend-2   1/1   Running
frontend    1/1   Running
```

Step 2: Modify Backend Pods
Exec into backend-1
```
kubectl exec -it backend-1 -n test -- /bin/bash
echo "Hello from Backend-1" > /usr/share/nginx/html/index.html
```
```
kubectl exec -it backend-2 -n test -- /bin/bash
echo "Hello from Backend-2" > /usr/share/nginx/html/index.html
```

Step 3: Create Service

```
kubectl expose pod backend-1 \
  --name=backend-service \
  --port=80 \
  --target-port=80 \
  --type=ClusterIP \
  --selector=app=backend \
  -n test
```

```
kubectl get svc -n test
NAME              TYPE        CLUSTER-IP     PORT(S)
backend-service   ClusterIP   10.96.120.45   80/TCP
```

Step 4: Verify Endpoints
```
kubectl get endpoints backend-service -n test
```
```
backend-service   10.244.0.5:80,10.244.0.6:80
```

Step 5: Test Load Balancing from Frontend Pod
```
curl backend-service
curl backend-service
curl backend-service
curl backend-service


Hello from Backend-1
Hello from Backend-2
Hello from Backend-1
Hello from Backend-2

```




# Types of Services

There are four main types of services in Kubernetes. You can specify a `type` in the Service specification.

1.  **ClusterIP**
2.  **NodePort**
3.  **LoadBalancer**
4.  **ExternalName**

---

## 1. ClusterIP
![alt text](<IMAGES/image copy 7.png>)
This is the **default** type of service. It exposes the service on a cluster-internal IP. This means the service is only reachable from within the cluster.

### Use-Case:
Internal communication between different parts of your application, like a web frontend talking to a backend API.

### Demo:

Let's expose a deployment named `backend` on port 80.

```
# First, create a deployment
kubectl create deployment backend --image=httpd --replicas=2

# Expose the deployment as a ClusterIP service
# This is the default, so you don't have to specify --type=ClusterIP
kubectl expose deployment backend --port=80 --target-port=80
```

Now, let's see the service that was created.

```
# kubectl get service backend
NAME      TYPE        CLUSTER-IP      EXTERNAL-IP   PORT(S)   AGE
backend   ClusterIP   10.108.144.22   <none>        80/TCP    5s
```

You can see the `TYPE` is `ClusterIP` and it has a `CLUSTER-IP`. This IP is only reachable from within the cluster. A pod inside the cluster can now access the backend pods via `curl http://backend` or `curl http://10.108.144.22`.

---

## 2. NodePort

This exposes the service on each Node's IP at a static port (the `NodePort`). A `ClusterIP` service, to which the `NodePort` service routes, is automatically created. You'll be able to contact the `NodePort` service from outside the cluster by requesting `<NodeIP>:<NodePort>`.
![alt text](<IMAGES/image copy 8.png>)

### Use-Case:
When you want to expose a service for development purposes or when you don't have a cloud load balancer.

### Demo:

Let's expose the `backend` deployment as a `NodePort` service.

```
# Expose the deployment as a NodePort service
kubectl expose deployment backend --port=80 --target-port=80 --type=NodePort --name=backend-nodeport-svc
```

Let's inspect the created service.

```
# kubectl get service backend-nodeport-svc
NAME                   TYPE       CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
backend-nodeport-svc   NodePort   10.102.51.203   <none>        80:31569/TCP   8s
```

- A `ClusterIP` (`10.102.51.203`) is created.
- The service is exposed on port `31569` on each node in the cluster. The port is chosen from a range (default: 30000-32767).
- You can now access the service from outside the cluster using `http://<any-node-ip>:31569`.
![alt text](<IMAGES/image copy 9.png>)
---

## 3. LoadBalancer

This exposes the service externally using a cloud provider's load balancer. `NodePort` and `ClusterIP` services, to which the external load balancer routes, are automatically created.

### Use-Case:
Exposing a production application to the internet. This is the standard way to expose a service to the outside world on cloud platforms like AWS, GCP, and Azure.

### Demo:

This command will only work if you are running your cluster on a cloud provider that supports external load balancers.

```
# Expose the deployment as a LoadBalancer service
kubectl expose deployment backend --port=80 --target-port=80 --type=LoadBalancer --name=backend-lb-svc
```

Let's see the service.

```
# kubectl get service backend-lb-svc
NAME             TYPE           CLUSTER-IP      EXTERNAL-IP   PORT(S)        AGE
backend-lb-svc   LoadBalancer   10.101.24.108   <pending>     80:32037/TCP   12s
```

- The `EXTERNAL-IP` is initially `<pending>`. It can take a few minutes for the cloud provider to create the load balancer and assign an external IP address.
- Once created, you will see an external IP address, and you can use that to access your service from the internet.

```
# kubectl get service backend-lb-svc
NAME             TYPE           CLUSTER-IP      EXTERNAL-IP      PORT(S)        AGE
backend-lb-svc   LoadBalancer   10.101.24.108   203.0.113.32     80:32037/TCP   2m
```

---

## 4. ExternalName

This type of service maps a service to a DNS name, not to a selector like other services. It returns a `CNAME` record with the value of the `externalName` parameter.
![alt text](<IMAGES/image copy 10.png>)

### Use-Case:
To create a service inside your cluster that represents an external service. For example, you can have a service named `my-database` that points to a managed database service running outside your cluster. Your internal applications can just connect to `my-database`.

### Demo:

This type of service cannot be created with `kubectl expose`. You need to use a YAML file.

Here is an example YAML:
```
apiVersion: apps/v1
kind: Deployment
metadata:
  name: nginx-deployment
spec:
  replicas: 2
  selector:
    matchLabels:
      app: nginx-demo
  template:
    metadata:
      labels:
        app: nginx-demo
    spec:
      containers:
      - name: nginx
        image: nginx
        ports:
        - containerPort: 80
```
```
kubectl apply -f deployment.yaml
```



```yaml
# external-name-svc.yaml
apiVersion: v1
kind: Service
metadata:
  name: google-service
spec:
  type: ExternalName
  externalName: www.google.com
  selector:
    app: nginx-demo
```

You would apply this with `kubectl apply -f external-name-svc.yaml`.

When a pod in your cluster tries to access `my-external-service`, the cluster's DNS service will return a `CNAME` record for `my.database.example.com`. No proxying or port forwarding is involved.

Expected Output:
```
NAME             TYPE           CLUSTER-IP   EXTERNAL-IP      PORT(S)
google-service   ExternalName   <none>       www.google.com   <none>
```

Step 3 — Test ExternalName Service

Start Test Pod
```
kubectl run test-pod --image=busybox --restart=Never -it -- sh

```
Inside Pod Run
```
nslookup google-service

```
Where ExternalName Is Used (Real Time)
1. Connecting External Database
```
externalName: mysql.company.com

```
2. Connecting SaaS / External APIs
```
Stripe
Payment gateways
Google APIs
Third-party logging tools
```
3. Migration Scenarios
Suppose:

Old service running outside Kubernetes

You create:
```
Service inside cluster → pointing to external system
```
4. Multi Cloud / Hybrid Setup
```
EKS → Connect → On-Prem DB
```


# Ingress

- When we use a LoadBalancer Service Type, the Load balancer forwards traffic to a NodePort associated with a single service
![alt text](<IMAGES/image copy 11.png>)


## Multiple Service Scenario
In a scenario where you have multiple services for different websites, you might have to create multiple sets of load balancers for each service. 
This is expensive.
![alt text](<IMAGES/image copy 12.png>)

## Ideal Approach

In an ideal approach, you want a single load balancer to handle requests for multiple services and a logic that can route traffic accordingly
![alt text](<IMAGES/image copy 13.png>)

## Introducing Ingress
Ingress acts as an entry point that routes traffic to specific services based on rules you define.
![alt text](<IMAGES/image copy 14.png>)

![alt text](<IMAGES/image copy 15.png>)

## Components of Ingress
- There are two sub-components of Ingress:
1. Ingress Controller
2. Ingress Resource


![alt text](<IMAGES/image copy 16.png>)

## Components of Ingress

An Ingress Controller is a component that implements the rules defined in Ingress resources.
Ingress Controller is a running application within your cluster.
![alt text](<IMAGES/image copy 18.png>)


# DEMO:
```
root@admin-server:~# kubectl create ingress --help
Create an ingress with the specified name.

Aliases:
ingress, ing

Examples:
  # Create a single ingress called 'simple' that directs requests to foo.com/bar to svc
  # svc1:8080 with a TLS secret "my-cert"
  kubectl create ingress simple --rule="foo.com/bar=svc1:8080,tls=my-cert"

  # Create a catch all ingress of "/path" pointing to service svc:port and Ingress Class as "otheringress"
  kubectl create ingress catch-all --class=otheringress --rule="/path=svc:port"

  # Create an ingress with two annotations: ingress.annotation1 and ingress.annotations2
  kubectl create ingress annotated --class=default --rule="foo.com/bar=svc:port" \
  --annotation ingress.annotation1=foo \
  --annotation ingress.annotation2=bla
```

```
Usage:
  kubectl create ingress NAME --rule=host/path=service:port[,tls[=secret]]  [options]
```

```
root@admin-server:~# kubectl  create ingress first-ingress --rule="example.internal/*=example-service:80"
ingress.networking.k8s.io/first-ingress created
```

### Wheather service present or not no need to worry 
```
root@admin-server:~# kubectl get svc
NAME         TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
kubernetes   ClusterIP   10.152.183.1   <none>        443/TCP   2d17h
root@admin-server:~# kubectl describe ingress first-ingress
Name:             first-ingress
Labels:           <none>
Namespace:        default
Address:
Ingress Class:    <none>
Default backend:  <default>
Rules:
  Host              Path  Backends
  ----              ----  --------
  example.internal
                    /   example-service:80 (<error: services "example-service" not found>)
Annotations:        <none>
Events:             <none>

```

Example 2 - Ingress with 2 Rules
Create Ingress with two rules where traffic for kplabs.internal domain be routed to kplabs-service, and traffic for example.internal domain be routed to example-service.

```
root@admin-server:~# kubectl  create ingress second-ingress --rule="example.internal/*=example-service:80" --rule="kplabs.internal/*=example-service:80"
ingress.networking.k8s.io/second-ingress created
root@admin-server:~# kubectl get svc
NAME         TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
kubernetes   ClusterIP   10.152.183.1   <none>        443/TCP   2d17h
root@admin-server:~# kubectl get svc
NAME         TYPE        CLUSTER-IP     EXTERNAL-IP   PORT(S)   AGE
kubernetes   ClusterIP   10.152.183.1   <none>        443/TCP   2d17h
root@admin-server:~# kubectl get ingress
NAME             CLASS    HOSTS                              ADDRESS   PORTS   AGE
first-ingress    <none>   example.internal                             80      3m45s
second-ingress   <none>   example.internal,kplabs.internal             80      21s
root@admin-server:~# kubectl describe ingress second-ingress
Name:             second-ingress
Labels:           <none>
Namespace:        default
Address:
Ingress Class:    <none>
Default backend:  <default>
Rules:
  Host              Path  Backends
  ----              ----  --------
  example.internal
                    /   example-service:80 (<error: services "example-service" not found>)
  kplabs.internal
                    /   example-service:80 (<error: services "example-service" not found>)
Annotations:        <none>
Events:             <none>

``` 

# INGRESS RULES WITH ROUTING PATTERNS


## 1. NAME BASED VIRTUAL HOSTING
- Traffic is routed to the service based on the host header in the HTTP request

```
root@admin-server:~# kubectl create ingress path-based-igress --rule=*/=example-service:80 --dry-run=client -o yaml
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: path-based-igress
spec:
  rules:
  - host: '*'
    http:
      paths:
      - backend:
          service:
            name: example-service
            port:
              number: 80
        path: /
        pathType: Exact
status:
  loadBalancer: {}

```

lets change in the manifestfie:

```
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: path-based-igress
spec:
  rules:
  - host: '*'
    http:
      paths:
      - backend:
          service:
            name: app-1-service
            port:
              number: 80
        path: /app-1
        pathType: Exact
      - backend:
          service:
            name: app-2-service
            port:
              number: 80
        path: /app-2
        pathType: Exact

```

Remove -host as * it wont allow :

```
apiVersion: networking.k8s.io/v1
kind: Ingress
metadata:
  name: path-based-ingress
spec:
  ingressClassName: nginx
  rules:
  - http:
      paths:
      - path: /app-1
        pathType: Prefix
        backend:
          service:
            name: app-1-service
            port:
              number: 80

      - path: /app-2
        pathType: Prefix
        backend:
          service:
            name: app-2-service
            port:
              number: 80
```

```
root@admin-server:~# vi pathbased.yaml
root@admin-server:~# kubectl apply -f pathbased.yaml
ingress.networking.k8s.io/path-based-ingress created
root@admin-server:~# kubectl get ingress
NAME                 CLASS    HOSTS                              ADDRESS   PORTS   AGE
first-ingress        <none>   example.internal                             80      54m
path-based-ingress   nginx    *                                            80      5s
second-ingress       <none>   example.internal,kplabs.internal             80      51m
root@admin-server:~# kubectl describe ingress path-based-ingress
Name:             path-based-ingress
Labels:           <none>
Namespace:        default
Address:
Ingress Class:    nginx
Default backend:  <default>
Rules:
  Host        Path  Backends
  ----        ----  --------
  *
              /app-1   app-1-service:80 (<error: services "app-1-service" not found>)
              /app-2   app-2-service:80 (<error: services "app-2-service" not found>)
Annotations:  <none>
Events:
  Type    Reason  Age   From                      Message
  ----    ------  ----  ----                      -------
  Normal  Sync    21s   nginx-ingress-controller  Scheduled for sync

```

# Ingress-Controller:

![alt text](<IMAGES/image copy 19.png>)

```
root@admin-server:~# kubectl run example-pod --image=nginx
pod/example-pod created
root@admin-server:~# kubectl run kplabs-pod --image=httpd
pod/kplabs-pod created
root@admin-server:~# kubectl expose pod example-pod --name example-service --port=80 --target-port=80
service/example-service exposed
root@admin-server:~# kubectl expose pod kplabs-pod --name kplabs-service --port=80 --target-port=80
service/kplabs-service exposed
root@admin-server:~# kubectl get svc
NAME              TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)   AGE
example-service   ClusterIP   10.152.183.157   <none>        80/TCP    9s
kplabs-service    ClusterIP   10.152.183.165   <none>        80/TCP    4s
kubernetes        ClusterIP   10.152.183.1     <none>        443/TCP   2d18h
root@admin-server:~# kubectl create ingress main-ingress --class=nginx --rule="example.internal/*=example-service:80" --rule="kplabs.internal/*=kplabs-service:80"
ingress.networking.k8s.io/main-ingress created
root@admin-server:~# kubectl describe ingress main-ingress
Name:             main-ingress
Labels:           <none>
Namespace:        default
Address:
Ingress Class:    nginx
Default backend:  <default>
Rules:
  Host              Path  Backends
  ----              ----  --------
  example.internal
                    /   example-service:80 (10.1.87.84:80)
  kplabs.internal
                    /   kplabs-service:80 (10.1.87.85:80)
Annotations:        <none>
Events:
  Type    Reason  Age   From                      Message
  ----    ------  ----  ----                      -------
  Normal  Sync    5s    nginx-ingress-controller  Scheduled for sync
root@admin-server:~# kubectl apply -f https://raw.githubusercontent.com/kubernetes/ingress-nginx/controller-v1.12.0/deploy/static/provider/cloud/deploy.yaml
namespace/ingress-nginx unchanged
serviceaccount/ingress-nginx unchanged
serviceaccount/ingress-nginx-admission unchanged
role.rbac.authorization.k8s.io/ingress-nginx unchanged
role.rbac.authorization.k8s.io/ingress-nginx-admission unchanged
clusterrole.rbac.authorization.k8s.io/ingress-nginx unchanged
clusterrole.rbac.authorization.k8s.io/ingress-nginx-admission unchanged
rolebinding.rbac.authorization.k8s.io/ingress-nginx unchanged
rolebinding.rbac.authorization.k8s.io/ingress-nginx-admission unchanged
clusterrolebinding.rbac.authorization.k8s.io/ingress-nginx unchanged
clusterrolebinding.rbac.authorization.k8s.io/ingress-nginx-admission unchanged
configmap/ingress-nginx-controller configured
service/ingress-nginx-controller configured
service/ingress-nginx-controller-admission unchanged
deployment.apps/ingress-nginx-controller configured
job.batch/ingress-nginx-admission-create unchanged
job.batch/ingress-nginx-admission-patch unchanged
ingressclass.networking.k8s.io/nginx unchanged
validatingwebhookconfiguration.admissionregistration.k8s.io/ingress-nginx-admission configured
root@admin-server:~# kubectl get svc
NAME              TYPE        CLUSTER-IP       EXTERNAL-IP   PORT(S)   AGE
example-service   ClusterIP   10.152.183.157   <none>        80/TCP    46s
kplabs-service    ClusterIP   10.152.183.165   <none>        80/TCP    41s
kubernetes        ClusterIP   10.152.183.1     <none>        443/TCP   2d18h
root@admin-server:~# kubectl get ingress
NAME                 CLASS    HOSTS                              ADDRESS   PORTS   AGE
first-ingress        <none>   example.internal                             80      62m
main-ingress         nginx    example.internal,kplabs.internal             80      28s
path-based-ingress   nginx    *                                            80      7m35s
second-ingress       <none>   example.internal,kplabs.internal             80      58m
root@admin-server:~# kubectl get pods -n ingress-nginx
kubectl get service -n ingress-nginx
NAME                                        READY   STATUS      RESTARTS   AGE
ingress-nginx-admission-create-c8klk        0/1     Completed   0          89m
ingress-nginx-admission-patch-rzb86         0/1     Completed   1          89m
ingress-nginx-controller-847c65586c-25w9x   1/1     Running     0          89m
NAME                                 TYPE           CLUSTER-IP       EXTERNAL-IP   PORT(S)                      AGE
ingress-nginx-controller             LoadBalancer   10.152.183.177   <pending>     80:31292/TCP,443:32751/TCP   89m
ingress-nginx-controller-admission   ClusterIP      10.152.183.186   <none>        443/TCP                      89m
root@admin-server:~# kubectl get service -n ingress-nginx
NAME                                 TYPE           CLUSTER-IP       EXTERNAL-IP   PORT(S)                      AGE
ingress-nginx-controller             LoadBalancer   10.152.183.177   <pending>     80:31292/TCP,443:32751/TCP   89m
ingress-nginx-controller-admission   ClusterIP      10.152.183.186   <none>        443/TCP                      89m

root@admin-server:~# curl -H "Host: example.internal" 10.152.183.177
<!DOCTYPE html>
<html>
<head>
<title>Welcome to nginx!</title>
<style>
html { color-scheme: light dark; }
body { width: 35em; margin: 0 auto;
font-family: Tahoma, Verdana, Arial, sans-serif; }
</style>
</head>
<body>
<h1>Welcome to nginx!</h1>
<p>If you see this page, the nginx web server is successfully installed and
working. Further configuration is required.</p>

<p>For online documentation and support please refer to
<a href="http://nginx.org/">nginx.org</a>.<br/>
Commercial support is available at
<a href="http://nginx.com/">nginx.com</a>.</p>

<p><em>Thank you for using nginx.</em></p>
</body>
</html>
root@admin-server:~# curl -H "Host: kplabs.internal" 10.152.183.177
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<title>It works! Apache httpd</title>
</head>
<body>
<p>It works!</p>
</body>
</html>

```

Documentaion:
-------------

https://kubernetes.io/docs/concepts/services-networking/ingress-controllers/

https://kubernetes.github.io/ingress-nginx/deploy/


UNDERSTADING OF HELM:
---------------------
https://github.com/ManojKRISHNAPPA/ITkannadigaru-HelmCharts-beginer-to-advance/blob/main/Notes.md


# Namespaces
In Kubernetes, namespaces provide a mechanism for isolating groups of resources within a single cluster
![alt text](<IMAGES/image copy 20.png>)

- Multiple teams or projects can share the same cluster without interfering with each other.
- Separate different environments like, development, QA, staging

![alt text](<IMAGES/image copy 21.png>)

# Service Accounts

## Understanding the basics
Kubernetes Clusters have two categories of accounts:
● User Accounts (For Humans).
● Service Accounts (For Applications)

## Importance of Credentials
To connect to Kubernetes cluster, an entity needs to have some kind of authentication credentials.

HOW IT WILL CONNECT:
```
root@admin-server:~# kubectl get pods
NAME                               READY   STATUS    RESTARTS   AGE
naruto-flask-app-8f9645487-d2rgd   1/1     Running   0          99m
naruto-flask-app-8f9645487-lq57n   1/1     Running   0          99m
root@admin-server:~# cd .kube/
root@admin-server:~/.kube# ls
cache  config
root@admin-server:~/.kube# cat config
apiVersion: v1
clusters:
- cluster:
    certificate-authority-data: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUREekNDQWZlZ0F3SUJBZ0lVUHZmeU5Fb1U5WVZUYjFtbnJ4VlpWWmZRWi9nd0RRWUpLb1pJaHZjTkFRRUwKQlFBd0Z6RVZNQk1HQTFVRUF3d01NVEF1TVRVeUxqRTRNeTR4TUI0WERUSTJNREl3T1RFNU1ETXdNbG9YRFRNMgpNREl3TnpFNU1ETXdNbG93RnpFVk1CTUdBMVVFQXd3TU1UQXVNVFV5TGpFNE15NHhNSUlCSWpBTkJna3Foa2lHCjl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUF0NzJTUUZTa3VzY0I5V3NaNWFhR1p1bXJLejlrQThqOTlhNm8KL0RGelZuTkZuL1dVN1gzQTdlS2l6NXMrb2Qvd0Z0aDZ1WXY3MGVCcThEeGM0dGdCTTNrWVh2NVZlNXBWSjBOcQpvOWZvZ3pUTXloZVp6RWxScnhuWDZucVJJSzNsdDFnUFZ2emRzWWRNMjVCaEpIQlNTbTlzNitwS3UrbW5YUUtnCkZKQXdBK3RVUkxhbmJ1U2NJd1lMY0plSDhwVG9wNTlGV2tzV00xQmN4a3JRaEgvY3NwKzZqQjZEemZvVTB1dDcKU1NJSXNDTGdtNERwdHJIU1FuV3FpQ2kvM0oyWEVLQXFXSVdvRGV1T2pzTk9yODVmR1FPcXA2VFhxVDB0Um5MUApIbC8vOGFXVlFITzhQclllNXJBM2t6ejdjUVpudnZtS21uUGNSUmZhNFhQbDFqNGtuUUlEQVFBQm8xTXdVVEFkCkJnTlZIUTRFRmdRVThQa2lXaVVxQjNXZkdWaldNZzNWcVNYcWNYMHdId1lEVlIwakJCZ3dGb0FVOFBraVdpVXEKQjNXZkdWaldNZzNWcVNYcWNYMHdEd1lEVlIwVEFRSC9CQVV3QXdFQi96QU5CZ2txaGtpRzl3MEJBUXNGQUFPQwpBUUVBcERzZTRMTHhtQzFmVzRxK2NZeEVjYTFEN0lxZXhMdG8ySDZvZ0tKbG5wSzBuWFBybFRST2JSZitnYnpjCk9OVnF1c2lHTlM0NjlhNFlkYkVTd1h0L3pnWTNPdndhMzAvZTQ4bFN5b0tTTmFjbERzRGZrQ0JFamxrYWMxZlIKZ2VhWFpxd2RPei9kSkZ2NGovL1hCUGlVOEZFd016NjJPeGpyV1lqY3JJZ1hzYkhtRlFnU2xITzY4VHhUSjZveQpvWFBEZXZDWklmSXJsZnd5cU1ZSDBjdEJmUFNKVk9HbHVDa1RiME1UV29WQU1PejJlUitzZWwwYW5SOW02YUZsCm9BL2srZjNKRElMejRDU1B5VGpXbm8ycWFCaUxtdG1lVVlXWlJkUkxVMExXenhNZEZKUk9kNkpocHd5Qm04bzEKdm4wQXc0Wm52bUEwanJjazFOT1JQczRGakE9PQotLS0tLUVORCBDRVJUSUZJQ0FURS0tLS0tCg==
    server: https://172.31.34.182:16443
  name: microk8s-cluster
contexts:
- context:
    cluster: microk8s-cluster
    user: admin
  name: microk8s
current-context: microk8s
kind: Config
preferences: {}
users:
- name: admin
  user:
    client-certificate-data: LS0tLS1CRUdJTiBDRVJUSUZJQ0FURS0tLS0tCk1JSUN6RENDQWJTZ0F3SUJBZ0lVWXlzbHBDeHlsRlZFNHh0cTJoNHJQQ2xVSlVBd0RRWUpLb1pJaHZjTkFRRUwKQlFBd0Z6RVZNQk1HQTFVRUF3d01NVEF1TVRVeUxqRTRNeTR4TUI0WERUSTJNREl3T1RFNU1ETXdNMW9YRFRNMgpNREl3TnpFNU1ETXdNMW93S1RFT01Bd0dBMVVFQXd3RllXUnRhVzR4RnpBVkJnTlZCQW9NRG5ONWMzUmxiVHB0CllYTjBaWEp6TUlJQklqQU5CZ2txaGtpRzl3MEJBUUVGQUFPQ0FROEFNSUlCQ2dLQ0FRRUF6QktFeVVNaHZ3bkQKVjFvYjVmV2gwaXRUaHVCdTBmNDBGOUpVUC9rcFlhRVQwUFhHOGkwRWF1WDFyaUdpSzdvVU5sOTRtUlkvNzZzUApORlkwelorUFJsTUp3OHdCQW5YWEtGMGFFR2JMZUVWK3dNcFdhSDIrRzZJZ3J4UHdicUhUMVVMcUkvQm9leElVCnN5Uk44UHFLMC9TUzBhcmE2NVN3QUlSQ0M1Zmxxa05hMFJpZjFCSDgxL3V2cWdkWFRhb3B2amNuOUhCcjhpYnMKQzFPV3FnbWlHY0JMdVYzMkFBNUg0S0VQdy9zbXBkY2g2VS9ZUzB4ZllURmsrUC9yYU93bXNJSFB3M3RxdzRtaAoxZHFUV1NVR1ZBcjRXRVhVNWtldFUvSTJOenBqY0REcC94NFE3MXJoc0VoOVFHdjJPL0Z3Ly9pQzl3WW9GY1NtCm1kdUQ0Z1VYeXdJREFRQUJNQTBHQ1NxR1NJYjNEUUVCQ3dVQUE0SUJBUUFHWGxSb1p0N2lMVytMazhOb0JtWjMKTDZlbHQ1aGsrcnNNZ3daeUFiWFVrRWpCUFpoQkZHZUt1NmhicmFTTjl4VHFnalJOYVl4ZXJqQTl4Q0lZOFZVQQp5ZGdRRkQ1dE1YSlJoWXY5V2EwT1lHL0pCaVJvajd0QnI3clh0UHBSRzQzazdDUEdiQkQwYzltK0pndlRHUDYxClpWOXVQUWZ0cWZndGJRYlZ0WXVNUXVXMnM0QVlMT3owdzNheXVOdC9sOVQ0eEZSTDE0U0YwSkxQVHlLUXFvZEkKSXRkQ2VkODFNcUFEVEIydE9Rdy9qa2dzWktucXRGNXlsU2ZxS3ZDL1lwcHZ0cDB4bmtEblZCdjhkaEVjS0xWaQpaejNBaVo1MVNvNXFpSmU4TldGOGMzRjZHTXlPQVZIbVpCMEI5cldQdnRqUmZENlN6UEZjOFBZSE02NFptWWZoCi0tLS0tRU5EIENFUlRJRklDQVRFLS0tLS0K
    client-key-data: LS0tLS1CRUdJTiBSU0EgUFJJVkFURSBLRVktLS0tLQpNSUlFcFFJQkFBS0NBUUVBekJLRXlVTWh2d25EVjFvYjVmV2gwaXRUaHVCdTBmNDBGOUpVUC9rcFlhRVQwUFhHCjhpMEVhdVgxcmlHaUs3b1VObDk0bVJZLzc2c1BORlkwelorUFJsTUp3OHdCQW5YWEtGMGFFR2JMZUVWK3dNcFcKYUgyK0c2SWdyeFB3YnFIVDFVTHFJL0JvZXhJVXN5Uk44UHFLMC9TUzBhcmE2NVN3QUlSQ0M1Zmxxa05hMFJpZgoxQkg4MS91dnFnZFhUYW9wdmpjbjlIQnI4aWJzQzFPV3FnbWlHY0JMdVYzMkFBNUg0S0VQdy9zbXBkY2g2VS9ZClMweGZZVEZrK1AvcmFPd21zSUhQdzN0cXc0bWgxZHFUV1NVR1ZBcjRXRVhVNWtldFUvSTJOenBqY0REcC94NFEKNzFyaHNFaDlRR3YyTy9Gdy8vaUM5d1lvRmNTbW1kdUQ0Z1VYeXdJREFRQUJBb0lCQVFESFE3bm5NQ2J1ZkdFQwpsWmt5TldRYWJYWDArSWNkZzJOb2MxY1MxSC9FdGQwOHFCRG4vbThXMW83THhrbXMrdGlyc3hOMklCUzBPTXJ5CjVzNU9qZVAvM2l0bHhYaWk1MS85S05PL2VqQnBzeW91cENRMWlicXREdVZ0TDBJUk5QRThoMGRMYW44SzFUL2oKSUtyK2lCWXhHdHFWNG9nN2lvZEZLZCszcEUxOHJ1TFA2WEI3QkxyWXpsMjJPdFNFc0tESjc5ZTBYY1o0UWswQQpxM09IV0JJdkZETThjcHIwQkd5b1dFVndsRFN0Y05ldWpudm5Id0JMUllTUE51a3RkZnRVZDUyVS9uNjVNUkl0CjUva3VFdlNxakxXUjhrTkVNQ0ZDc2JiZW50ZThhM1dPb1ZHSmNHWUZhL1A0Z2d5eGZaaEorMm8zYWpqNVFVV0YKOW02Qk9Ed2hBb0dCQVBROFc1UkFhK1o0Q1FoZzN2K1dSZndMMUNoTXhqWmpoZVNZSlJMQjBnRjFubEpBUm0zYgpJM0hJUFdIQ1pycUdWSitxNVNtYSs3UXRKMk5IS2N4cXRnQm9acXR6aE02RWNWRy82RElhOWhuUE9GY3lEck5uClBJemFmdDhOajJmdjkvemFVcEc4ZzNZZWNTL2VoemJjRmRSMDZZWEp0cFdOQUZkQUZ2V2FnMGZiQW9HQkFOWG0KNlJLTk96STlYUHl0UGd2SU1FWmdsRWtWQnVSYUpPb2JXYXZUQkQ1bjRuUk13NEpQSDlyOEZ5OG9LbGlCb0Y4ZApSOHJ2K1hZcER3TUlLZm9IQ1MxdHUvN0lKT2VQV1R3RkJqck1heFpueURkRFdPSzhVQVZGcTBLbHJibXROdW9KCi9oTGdMMGl4MFE1WGR0M2lOUHR1WjVQdkpYSThueHhjTWp6bllLclJBb0dCQUlaOUZoQzB5TFhJTTNFaHBxb24KSGJLRThQYWdFQ1d5OSsvQXQrbDBRU2Y4bEluR1N3SURRYWxPRWo3YXhhYkFnYWpLZWhaRytZTmx1ZUs1TlJNVApUOVU1cUErUk5QaGpoZUwyUWU0VldwOHJ0R0tQZGZqa1NEdG50YVV0Mm1IcGlpejZLNjJFbVA5YUZBbkFCOFQxCnZDK1prVjNTalhBY2pLdCs1eVduUjlNeEFvR0FaVzFNNzRNUW9zMytIY0o0UFZYN3JpTjFyUUhQZHRCWDJMcUgKVnJhRXVLTEIrcXU3dVRxVHZGNzFEMk5ZVVFlR2FCT1dTMkJuUmVSS1BnSE5CY1g0VUJaTW9vOTlFR0FrekJVRgowelBEUTZpS2c4bm5oL3dMWmJTWGRNN2pCYnhnNGJGRFRPZ0pBOHR0ZWdOM1ZkZEJrRWZWell3RWtacTFSOWxmCjZRaytDVUVDZ1lFQW0yZDNha0pjTzk1L0VYQWhFQi9CZTdoV29BRlJaeW9wc1pIdy9UZWxYSDFqYWh3UVZFTTAKVGxLM09HU1RYNzVPMk9sNDlSOFFOREVyNjlnQW4wb01DVDNVQlZBZkw0YVRXVzNoNm5qTHAvS1JxVnd6Mk45eQo0aU5obWFtMmFnekxneFJrUzZ0NDFrd0hJRzBJWjNPdVIwSFpsVlBhenVjMkpBZVdTNnF3UDJFPQotLS0tLUVORCBSU0EgUFJJVkFURSBLRVktLS0tLQo=

root@admin-se

```


```
root@admin-server:~/.kube# kubectl get sa -A
NAMESPACE         NAME                                          SECRETS   AGE
default           default                                       0         2d18h
kube-node-lease   default                                       0         2d18h
kube-public       default                                       0         2d18h
kube-system       attachdetach-controller                       0         2d18h
kube-system       calico-cni-plugin                             0         2d18h
kube-system       calico-kube-controllers                       0         2d18h
kube-system       calico-node                                   0         2d18h
kube-system       certificate-controller                        0         2d18h
kube-system       clusterrole-aggregation-controller            0         2d18h
kube-system       coredns                                       0         2d18h
kube-system       cronjob-controller                            0         2d18h
kube-system       daemon-set-controller                         0         2d18h
kube-system       default                                       0         2d18h
kube-system       deployment-controller                         0         2d18h
kube-system       disruption-controller                         0         2d18h
kube-system       endpoint-controller                           0         2d18h
kube-system       endpointslice-controller                      0         2d18h
kube-system       endpointslicemirroring-controller             0         2d18h
kube-system       ephemeral-volume-controller                   0         2d18h
kube-system       expand-controller                             0         2d18h
kube-system       generic-garbage-collector                     0         2d18h
kube-system       horizontal-pod-autoscaler                     0         2d18h
kube-system       job-controller                                0         2d18h
kube-system       legacy-service-account-token-cleaner          0         2d18h
kube-system       namespace-controller                          0         2d18h
kube-system       node-controller                               0         2d18h
kube-system       persistent-volume-binder                      0         2d18h
kube-system       pod-garbage-collector                         0         2d18h
kube-system       pv-protection-controller                      0         2d18h
kube-system       pvc-protection-controller                     0         2d18h
kube-system       replicaset-controller                         0         2d18h
kube-system       replication-controller                        0         2d18h
kube-system       resourcequota-controller                      0         2d18h
kube-system       root-ca-cert-publisher                        0         2d18h
kube-system       service-account-controller                    0         2d18h
kube-system       service-cidrs-controller                      0         2d18h
kube-system       statefulset-controller                        0         2d18h
kube-system       ttl-after-finished-controller                 0         2d18h
kube-system       ttl-controller                                0         2d18h
kube-system       validatingadmissionpolicy-status-controller   0         2d18h
service           default                                       0         46h
test              default                                       0         46h
```

```
root@admin-server:~/.kube# kubectl run test-pod --image=nginx
pod/test-pod created
root@admin-server:~/.kube# kubectl get pods
NAME                               READY   STATUS        RESTARTS   AGE
naruto-flask-app-8f9645487-d2rgd   1/1     Terminating   0          107m
naruto-flask-app-8f9645487-lq57n   1/1     Terminating   0          107m
test-pod                           1/1     Running       0          5s
root@admin-server:~/.kube# kubectl get sa
NAME      SECRETS   AGE
default   0         2d18h
root@admin-server:~/.kube#
root@admin-server:~/.kube# kubectl exec -it test-pod -- bash
root@test-pod:/#
root@test-pod:/#
root@test-pod:/# cd /var/run/secrets/kubernetes.io/serviceaccount/
root@test-pod:/var/run/secrets/kubernetes.io/serviceaccount# ls
ca.crt	namespace  token
root@test-pod:/var/run/secrets/kubernetes.io/serviceaccount# cat token
eyJhbGciOiJSUzI1NiIsImtpZCI6IksyM1JMbU9kRlFVemVfaDFWN1hWVTJtbEVPeXRobmRlcm5ZXzdUQVFIMWsifQ.eyJhdWQiOlsiaHR0cHM6Ly9rdWJlcm5ldGVzLmRlZmF1bHQuc3ZjIl0sImV4cCI6MTgwMjQzOTc5MSwiaWF0IjoxNzcwOTAzNzkxLCJpc3MiOiJodHRwczovL2t1YmVybmV0ZXMuZGVmYXVsdC5zdmMiLCJqdGkiOiI4MGFjMThiZi0zYmUyLTRjYmItYTlkMS1lMTA4ZjVkNjgxMDgiLCJrdWJlcm5ldGVzLmlvIjp7Im5hbWVzcGFjZSI6ImRlZmF1bHQiLCJub2RlIjp7Im5hbWUiOiJhZG1pbi1zZXJ2ZXIiLCJ1aWQiOiI5YTRkNjg1YS0zMTU1LTRiMjItOGJiOC1jZTRlZTc1MWY0MTYifSwicG9kIjp7Im5hbWUiOiJ0ZXN0LXBvZCIsInVpZCI6IjgzYzdjMTFhLWRkYTYtNGVmNi05NTI2LWFkYjU1NjcyMjhjMCJ9LCJzZXJ2aWNlYWNjb3VudCI6eyJuYW1lIjoiZGVmYXVsdCIsInVpZCI6ImVlZjA5OTc2LWZjYjYtNDUzYS05OTM4LTFlNzYyMDI5NzM5ZSJ9LCJ3YXJuYWZ0ZXIiOjE3NzA5MDczOTh9LCJuYmYiOjE3NzA5MDM3OTEsInN1YiI6InN5c3RlbTpzZXJ2aWNlYWNjb3VudDpkZWZhdWx0OmRlZmF1bHQifQ.diYChAtNQR-nfeS7jgc7flprhrAP66mvcCflVSHHPzNmTbP2gFjVenBR4ug5nZeQROhoo6SsXR2cdhYmAUXt_v2t7mOVDaxbtW1EAMRRaAfw9-mNdNH2GoVtKPMQzxiRM8hzRf1K0PFDx_Zxvg6R3Z8lWocmf_NmweI_zzo-0tqFrEmf2a31YNkN65ebvOmEHiP9HSr4L7kVbdszHRngUeiSiVyP-QtWeZwBMtFvNITcWV4JU2hUhuy7qk32teYMiHSOzxSYOAgCoeWkVuDqV0r853dB7WYTFJEg-kFp1Kvqoq9UhLsqmgI_ZrGZ355J9egk6tRBkanFVQVKc2TU7wroot@test-pod:/var/run/secrets/kubernetes.io/serviceaccount#

```

## Now will try to curl this with  clsuer info

```
root@admin-server:~/.kube# kubectl cluster-info
Kubernetes control plane is running at https://172.31.34.182:16443
CoreDNS is running at https://172.31.34.182:16443/api/v1/namespaces/kube-system/services/kube-dns:dns/proxy

To further debug and diagnose cluster problems, use 'kubectl cluster-info dump'.
root@admin-server:~/.kube#
root@admin-server:~/.kube# kubectl exec -it test-pod -- bash
root@test-pod:/# cd /var/run/secrets/kubernetes.io/serviceaccount/
root@test-pod:/var/run/secrets/kubernetes.io/serviceaccount# token=$(cat token)
root@test-pod:/var/run/secrets/kubernetes.io/serviceaccount#
root@test-pod:/var/run/secrets/kubernetes.io/serviceaccount# curl -k -H "Authorization: Bearer $token $token "https://172.31.34.182:16443"
> "
curl: (2) no URL specified
curl: try 'curl --help' or 'curl --manual' for more information
root@test-pod:/var/run/secrets/kubernetes.io/serviceaccount# curl -k -H "Authorization: Bearer $token $token 'https://172.31.34.182:16443'"
curl: (2) no URL specified
curl: try 'curl --help' or 'curl --manual' for more information
root@test-pod:/var/run/secrets/kubernetes.io/serviceaccount# curl -k -H "Authorization: Bearer $token" https://172.31.34.182:16443
{
  "paths": [
    "/.well-known/openid-configuration",
    "/api",
    "/api/v1",
    "/apis",
    "/apis/",
    "/apis/admissionregistration.k8s.io",
    "/apis/admissionregistration.k8s.io/v1",
    "/apis/apiextensions.k8s.io",
    "/apis/apiextensions.k8s

```

![alt text](<IMAGES/image copy 22.png>)

![alt text](<IMAGES/image copy 23.png>)


## Point to Note
The default service accounts in each namespace get no permissions by default other than the default API discovery permissions that Kubernetes grants to all
authenticated principals if role-based access control (RBAC) is enabled



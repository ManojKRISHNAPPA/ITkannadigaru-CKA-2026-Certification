# Docker Core — Complete Notes (Day 1, 2 & 3)

---

## Table of Contents

### Day 1: Docker Fundamentals
1. [What is Docker?](#1-what-is-docker)
2. [Docker vs Virtual Machines](#2-docker-vs-virtual-machines)
3. [Docker Architecture](#3-docker-architecture)
4. [Docker Flow](#4-docker-flow)
5. [Essential Docker Commands](#5-essential-docker-commands)

### Day 2: Dockerize an Application
6. [What is a Dockerfile?](#6-what-is-a-dockerfile)
7. [Dockerfile Instructions Reference](#7-dockerfile-instructions-reference)
8. [Writing a Dockerfile — Step by Step](#8-writing-a-dockerfile--step-by-step)
9. [docker pull, push, tag & Registry Commands](#9-docker-pull-push-tag--registry-commands)

### Day 3: Multi-Stage Builds & Best Practices
10. [What is a Multi-Stage Build?](#10-what-is-a-multi-stage-build)
11. [Why Multi-Stage Builds?](#11-why-multi-stage-builds)
12. [How to Write a Multi-Stage Dockerfile](#12-how-to-write-a-multi-stage-dockerfile)
13. [Real-World Examples](#13-real-world-examples)
14. [Benefits of Multi-Stage Builds](#14-benefits-of-multi-stage-builds)
15. [Docker Best Practices](#15-docker-best-practices)
16. [Quick Reference Cheat Sheet](#16-quick-reference-cheat-sheet)

---

# Day 1: Docker Fundamentals

---

## 1. What is Docker?

Docker is an **open-source platform** that lets you **package, ship, and run applications in containers**.

A **container** is a lightweight, standalone, executable unit that includes:
- Application code
- Runtime (e.g., Node.js, Python, JVM)
- Libraries and dependencies
- Configuration files

### The Core Problem Docker Solves

> "It works on my machine!" — every developer ever

Without Docker:
- App works on dev laptop but fails on the server
- Different OS, different library versions, different configs
- Onboarding new developers takes hours

With Docker:
- The container carries its own environment
- Runs identically on any machine that has Docker installed
- "Build once, run anywhere"

### Key Concepts

| Term | Description |
|------|-------------|
| **Image** | A read-only blueprint/template to create containers |
| **Container** | A running instance of an image |
| **Dockerfile** | A text file with instructions to build an image |
| **Registry** | A storage server for images (e.g., Docker Hub) |
| **Volume** | Persistent storage that lives outside the container |
| **Network** | Virtual network connecting containers |

---

## 2. Docker vs Virtual Machines

### Architecture Comparison

```
+---------------------------+       +---------------------------+
|      Virtual Machines     |       |         Docker            |
+---------------------------+       +---------------------------+
|   App A  |   App B        |       |  App A  |  App B         |
+----------+----------------+       +---------+----------------+
| Guest OS | Guest OS       |       | Libs    | Libs           |
+----------+----------------+       +---------+----------------+
|       Hypervisor          |       |      Docker Engine        |
+---------------------------+       +---------------------------+
|       Host OS             |       |       Host OS             |
+---------------------------+       +---------------------------+
|       Hardware            |       |       Hardware            |
+---------------------------+       +---------------------------+
```

### Key Differences

| Feature | Virtual Machine | Docker Container |
|---------|----------------|------------------|
| **OS** | Full Guest OS per VM | Shares Host OS kernel |
| **Size** | GBs | MBs |
| **Startup Time** | Minutes | Seconds (or milliseconds) |
| **Isolation** | Full hardware-level isolation | Process-level isolation |
| **Portability** | Limited (tied to hypervisor) | Highly portable |
| **Resource Usage** | Heavy (dedicated CPU/RAM) | Lightweight (shared) |
| **Use Case** | Full OS isolation needed | App packaging & microservices |

### When to Use What

- **VM:** When you need full OS isolation, different kernels, or legacy OS support
- **Docker:** When you need fast, portable, consistent app deployments

---

## 3. Docker Architecture

Docker uses a **client-server architecture**.

```
+----------------+          +-----------------------------------+
|  Docker Client |          |         Docker Host (Server)      |
|                |          |                                   |
|  docker build  | <------> |  +----------+   +-----------+     |
|  docker pull   |   REST   |  |  Docker  |   | Containers|     |
|  docker run    |   API    |  |  Daemon  |   |  c1 c2 c3 |     |
|                |          |  |(dockerd) |   +-----------+     |
+----------------+          |  +----------+   +-----------+     |
                            |                 |  Images   |     |
                            |                 |  i1 i2 i3 |     |
                            |                 +-----------+     |
                            +-----------------------------------+
                                         |
                                         v
                            +-----------------------------------+
                            |         Docker Registry           |
                            |   (Docker Hub / ECR / GCR etc.)  |
                            +-----------------------------------+
```

### Components

| Component | Role |
|-----------|------|
| **Docker Client** | CLI tool (`docker`) that sends commands to the daemon |
| **Docker Daemon (`dockerd`)** | Background service that manages images, containers, networks, volumes |
| **Docker REST API** | Interface between client and daemon |
| **Docker Registry** | Remote storage for Docker images |
| **containerd** | Low-level container runtime used by the daemon |
| **runc** | OCI-compliant container runtime that actually runs containers |

### How they connect

```
docker CLI  -->  Docker Daemon (dockerd)  -->  containerd  -->  runc  -->  Container
```

---

## 4. Docker Flow

### Image Lifecycle

```
Dockerfile
    |
    | docker build
    v
Local Image  ----docker tag---->  Tagged Image
    |                                  |
    | docker run                       | docker push
    v                                  v
Container                         Docker Registry
                                       |
                                       | docker pull
                                       v
                                  Local Image (another machine)
                                       |
                                       | docker run
                                       v
                                  Container
```

### Container Lifecycle

```
         docker create
Image -----------------> Created
                            |
                    docker start
                            |
                            v
                         Running  <----+
                            |          | docker restart
                    docker stop        |
                            |          |
                            v          |
                         Stopped ------+
                            |
                    docker rm
                            |
                            v
                         Deleted
```

### What Happens When You Run `docker run nginx`

1. Docker client sends the command to Docker daemon
2. Daemon checks if `nginx` image exists locally
3. If not found — pulls it from Docker Hub
4. Creates a new container from the image
5. Allocates a filesystem, network interface, and IP
6. Starts the container process
7. Container runs until the process exits (or you stop it)

---

## 5. Essential Docker Commands

### Container Commands

```bash
# Run a container
docker run nginx                          # run in foreground
docker run -d nginx                       # run in background (detached)
docker run -d -p 8080:80 nginx            # map host:container port
docker run -d --name myapp nginx          # give it a name
docker run -it ubuntu bash                # interactive terminal
docker run --rm nginx                     # auto-remove on exit

# List containers
docker ps                                 # running containers
docker ps -a                              # all containers (including stopped)

# Start / Stop / Restart
docker start <container>
docker stop <container>
docker restart <container>

# Remove containers
docker rm <container>                     # remove stopped container
docker rm -f <container>                  # force remove running container
docker container prune                    # remove all stopped containers

# Inspect / Logs / Exec
docker logs <container>                   # view logs
docker logs -f <container>                # follow logs (live)
docker exec -it <container> bash          # shell into running container
docker inspect <container>                # detailed JSON info
docker stats                              # live resource usage
docker top <container>                    # running processes inside container
```

### Image Commands

```bash
# List / Remove images
docker images                             # list all local images
docker rmi <image>                        # remove an image
docker image prune                        # remove unused images
docker image prune -a                     # remove all unused images

# Build image
docker build -t myapp:1.0 .               # build from Dockerfile in current dir
docker build -f MyDockerfile -t myapp .   # use a specific Dockerfile

# Inspect image layers
docker history myapp:latest
docker inspect myapp:latest
```

### Volume Commands

```bash
# Create and manage volumes
docker volume create mydata
docker volume ls
docker volume inspect mydata
docker volume rm mydata

# Mount volume to container
docker run -d -v mydata:/app/data nginx           # named volume
docker run -d -v /host/path:/container/path nginx # bind mount
docker run -d --mount source=mydata,target=/data nginx
```

### Network Commands

```bash
# List / Create networks
docker network ls
docker network create mynetwork
docker network inspect mynetwork

# Connect container to network
docker run -d --network mynetwork --name app1 nginx
docker network connect mynetwork <container>
docker network disconnect mynetwork <container>
```

### System Commands

```bash
docker info                               # system-wide Docker info
docker version                            # client and daemon version
docker system df                          # disk usage
docker system prune                       # remove all unused resources
docker system prune -a --volumes          # aggressive cleanup
```

---

# Day 2: Dockerize an Application

---

## 6. What is a Dockerfile?

A **Dockerfile** is a plain text file named `Dockerfile` (no extension) that contains a set of **instructions** to build a Docker image layer by layer.

### How Dockerfile Becomes a Container

```
Dockerfile
    |
    | docker build -t myapp .
    v
Docker Image  (stack of read-only layers)
    |
    | docker run myapp
    v
Container  (image layers + writable layer on top)
```

### Image Layers

Every instruction in a Dockerfile creates a **new layer**:

```
Layer 5: CMD ["node", "server.js"]         <-- writable at run time
Layer 4: COPY . .
Layer 3: RUN npm install
Layer 2: COPY package.json .
Layer 1: FROM node:20-alpine               <-- base layer
```

Layers are **cached** — if nothing changes, Docker reuses cached layers, making rebuilds fast.

---

## 7. Dockerfile Instructions Reference

| Instruction | Syntax | Purpose |
|-------------|--------|---------|
| `FROM` | `FROM image:tag` | Base image to build from (must be first) |
| `WORKDIR` | `WORKDIR /app` | Set working directory for subsequent instructions |
| `COPY` | `COPY src dest` | Copy files from host into the image |
| `ADD` | `ADD src dest` | Like COPY but also extracts tarballs and fetches URLs |
| `RUN` | `RUN command` | Execute a command at **build time** |
| `CMD` | `CMD ["exec", "arg"]` | Default command to run when container starts (overridable) |
| `ENTRYPOINT` | `ENTRYPOINT ["exec"]` | Fixed command; CMD provides default arguments |
| `ENV` | `ENV KEY=value` | Set environment variables (available at build and run time) |
| `ARG` | `ARG NAME=default` | Build-time variables (not available at run time) |
| `EXPOSE` | `EXPOSE 8080` | Document which port the app listens on |
| `VOLUME` | `VOLUME ["/data"]` | Declare a mount point for persistent data |
| `USER` | `USER appuser` | Switch to a non-root user |
| `LABEL` | `LABEL key=value` | Add metadata to the image |
| `HEALTHCHECK` | `HEALTHCHECK CMD ...` | Define a health check command |
| `SHELL` | `SHELL ["/bin/sh"]` | Change the default shell for RUN instructions |

### CMD vs ENTRYPOINT

```dockerfile
# CMD only — fully overridable
CMD ["node", "server.js"]
# docker run myapp            -> runs: node server.js
# docker run myapp python app -> runs: python app   (CMD replaced)

# ENTRYPOINT only
ENTRYPOINT ["node"]
# docker run myapp            -> runs: node
# docker run myapp server.js  -> runs: node server.js

# ENTRYPOINT + CMD (best practice)
ENTRYPOINT ["node"]
CMD ["server.js"]
# docker run myapp            -> runs: node server.js  (default)
# docker run myapp app.js     -> runs: node app.js     (CMD overridden)
```

### RUN vs CMD vs ENTRYPOINT

| | `RUN` | `CMD` | `ENTRYPOINT` |
|---|---|---|---|
| **When** | Build time | Runtime (default) | Runtime (fixed) |
| **Purpose** | Install packages, set up environment | Default command/args | The main process |
| **Overridable** | N/A | Yes, by `docker run` args | Only with `--entrypoint` flag |

---

## 8. Writing a Dockerfile — Step by Step

### Example 1: Simple Node.js App

```
project/
├── Dockerfile
├── package.json
├── package-lock.json
└── src/
    └── index.js
```

```dockerfile
# Step 1: Choose a base image
FROM node:20-alpine

# Step 2: Set working directory inside the container
WORKDIR /app

# Step 3: Copy dependency files first (for layer caching)
COPY package*.json ./

# Step 4: Install dependencies
RUN npm install

# Step 5: Copy the rest of the source code
COPY . .

# Step 6: Expose the port the app runs on
EXPOSE 3000

# Step 7: Define the command to start the app
CMD ["node", "src/index.js"]
```

Build and run:
```bash
docker build -t my-node-app:1.0 .
docker run -d -p 3000:3000 --name nodeapp my-node-app:1.0
```

---

### Example 2: Python Flask App

```dockerfile
FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 5000

CMD ["python", "app.py"]
```

---

### Example 3: Nginx Serving Static Files

```dockerfile
FROM nginx:alpine

# Remove default nginx page
RUN rm -rf /usr/share/nginx/html/*

# Copy your static files
COPY ./dist /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
```

---

### Example 4: Java Spring Boot App

```dockerfile
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app

COPY target/myapp.jar app.jar

EXPOSE 8080

ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

## 9. docker pull, push, tag & Registry Commands

### Docker Hub Workflow

```
Local Machine                     Docker Hub (Registry)
     |                                    |
     |---docker pull nginx:alpine-------->|
     |<--image downloaded-----------------|
     |                                    |
     |---docker build -t myapp:1.0 .      |
     |---docker tag myapp:1.0 user/myapp:1.0
     |---docker push user/myapp:1.0------>|
     |                                    |
  Another Machine                         |
     |---docker pull user/myapp:1.0------>|
     |<--image downloaded-----------------|
     |---docker run user/myapp:1.0        |
```

### docker pull

```bash
# Pull an image from Docker Hub
docker pull nginx                         # pulls 'latest' tag
docker pull nginx:1.25-alpine             # pulls specific version
docker pull ubuntu:22.04

# Pull from a private registry
docker pull myregistry.example.com/myapp:1.0
```

### docker tag

```bash
# Syntax: docker tag SOURCE_IMAGE[:TAG] TARGET_IMAGE[:TAG]

docker tag myapp:latest myapp:1.0.0                          # add version tag
docker tag myapp:latest username/myapp:latest                # add Docker Hub username
docker tag myapp:latest myregistry.io/team/myapp:1.0         # tag for private registry

# Multiple tags for the same image
docker tag myapp:latest myapp:stable
docker tag myapp:latest myapp:production
```

### docker push

```bash
# Login first
docker login                              # Docker Hub
docker login myregistry.example.com       # Private registry

# Push to Docker Hub
docker push username/myapp:1.0
docker push username/myapp:latest

# Push to private registry
docker push myregistry.example.com/team/myapp:1.0
```

### docker pull with Authentication

```bash
# Login
docker login -u myusername -p mypassword

# Logout
docker logout

# Login to AWS ECR
aws ecr get-login-password --region us-east-1 | \
  docker login --username AWS --password-stdin 123456789.dkr.ecr.us-east-1.amazonaws.com
```

### Tagging Strategy Best Practices

```bash
# Semantic versioning (recommended)
myapp:1.0.0          # specific version
myapp:1.0            # minor version alias
myapp:1              # major version alias
myapp:latest         # always points to newest stable

# Git-based tags
myapp:abc1234        # short git commit SHA
myapp:main-20240315  # branch + date

# Environment tags
myapp:staging
myapp:production
```

### Saving and Loading Images (without registry)

```bash
# Save image to a tar file
docker save -o myapp.tar myapp:1.0

# Load image from tar file
docker load -i myapp.tar

# Export a container filesystem (not the full image)
docker export mycontainer -o container.tar

# Import as a new image
docker import container.tar myapp:imported
```

---

# Day 3: Multi-Stage Builds & Best Practices

---

## 10. What is a Multi-Stage Build?

A **multi-stage build** uses **multiple `FROM` statements** in a single Dockerfile. Each `FROM` starts a new **stage** with its own base image. You can selectively **copy artifacts** from one stage into another, leaving behind everything you don't need in the final image.

### Before Multi-Stage (the old problem)

```
Developer code  -->  Builder image (with compilers, SDKs, dev tools)
                          |
                          v
                  Final image (also contains compilers, SDKs — bloated!)
```

### After Multi-Stage (the solution)

```
Developer code  -->  Stage 1: Builder (compile/build)
                          |
                          | COPY only the binary/artifact
                          v
                     Stage 2: Runner (tiny, production image)
```

---

## 11. Why Multi-Stage Builds?

| Problem (Without Multi-Stage)         | Solution (With Multi-Stage)               |
|---------------------------------------|-------------------------------------------|
| Final image contains build tools      | Build tools stay in the builder stage only |
| Large image size (GBs)                | Small final image (MBs)                   |
| Sensitive build secrets may leak      | Secrets never reach the final image       |
| Slow pulls in CI/CD and production    | Fast pulls with minimal images            |
| Complex shell scripts to clean up     | Clean separation via stages               |

---

## 12. How to Write a Multi-Stage Dockerfile

### Basic Syntax

```dockerfile
# Stage 1 — Builder
FROM <build-image> AS builder
# ... build steps ...

# Stage 2 — Final / Runner
FROM <runtime-image>
COPY --from=builder /path/to/artifact /app/artifact
CMD ["/app/artifact"]
```

### Key Keywords

| Keyword | Purpose |
|---------|---------|
| `FROM <image> AS <name>` | Start a new stage and give it a name |
| `COPY --from=<stage>` | Copy files from a previous stage |
| `COPY --from=<image>` | Copy files directly from any Docker image |
| `RUN --mount=type=cache` | Mount a cache during build (BuildKit) |

### Building a Specific Stage (partial build)

```bash
# Build only up to the "builder" stage (useful for debugging)
docker build --target builder -t myapp:builder .

# Build the full final image
docker build -t myapp:latest .
```

---

## 13. Real-World Examples

### 13.1 Go Application

```dockerfile
# Stage 1: Build
FROM golang:1.22-alpine AS builder

WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download

COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o server ./cmd/server

# Stage 2: Run
FROM scratch
# 'scratch' is an empty image — absolute minimum size

COPY --from=builder /app/server /server
EXPOSE 8080
ENTRYPOINT ["/server"]
```

> **Result:** A Go binary running in a ~5 MB image instead of ~300 MB.

---

### 13.2 Node.js Application

```dockerfile
# Stage 1: Install dependencies and build
FROM node:20-alpine AS builder

WORKDIR /app
COPY package*.json ./
RUN npm ci --only=production

COPY . .
RUN npm run build

# Stage 2: Production runner
FROM node:20-alpine AS runner

WORKDIR /app

# Create non-root user
RUN addgroup -S appgroup && adduser -S appuser -G appgroup

COPY --from=builder /app/dist ./dist
COPY --from=builder /app/node_modules ./node_modules
COPY --from=builder /app/package.json ./

USER appuser
EXPOSE 3000
CMD ["node", "dist/index.js"]
```

---

### 13.3 Java (Maven) Application

```dockerfile
# Stage 1: Build with Maven
FROM maven:3.9-eclipse-temurin-21 AS builder

WORKDIR /app
COPY pom.xml .
# Download dependencies first (cached layer)
RUN mvn dependency:go-offline -B

COPY src ./src
RUN mvn package -DskipTests

# Stage 2: Run with lightweight JRE
FROM eclipse-temurin:21-jre-alpine

WORKDIR /app
COPY --from=builder /app/target/*.jar app.jar

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]
```

---

## 14. Benefits of Multi-Stage Builds

### Smaller Image Size
- Only the compiled artifact/binary is copied to the final image
- No compilers, package managers, or source code in production

### Better Security
- Reduced attack surface — fewer tools = fewer vulnerabilities
- Build-time secrets (API keys, tokens) never end up in the final image

### Cleaner Dockerfiles
- Single file replaces the old pattern of multiple Dockerfiles + shell scripts
- Each stage has a clear, single responsibility

### Faster CI/CD Pipelines
- Smaller images = faster push/pull from registries
- Layer caching still works per stage

### Separation of Concerns
- Build environment is completely separate from runtime environment
- Easier to update base images independently

---

## 15. Docker Best Practices

### 15.1 Image Size Optimization

**Use minimal base images:**

```dockerfile
# Avoid (large)
FROM ubuntu:22.04

# Better (~7 MB)
FROM alpine:3.19

# Best for compiled binaries (0 MB base)
FROM scratch

# Good balance — no shell, no package manager
FROM gcr.io/distroless/base-debian12
```

**Image size comparison:**

| Base Image | Approx. Size |
|------------|------|
| `ubuntu:22.04` | ~77 MB |
| `debian:slim` | ~74 MB |
| `alpine:3.19` | ~7 MB |
| `distroless/base` | ~20 MB |
| `scratch` | 0 MB |

---

### 15.2 Layer Caching

Docker caches each layer. **Order instructions from least to most frequently changed.**

```dockerfile
# WRONG — any code change invalidates the npm install cache
FROM node:20-alpine
COPY . .
RUN npm install

# CORRECT — dependencies cached independently from source code
FROM node:20-alpine
COPY package*.json ./      # changes rarely  -> cached
RUN npm install            # cached unless package.json changes
COPY . .                   # changes often   -> not cached, but that's fine
```

**Combine RUN commands to reduce layers:**

```bash
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        curl \
        git && \
    rm -rf /var/lib/apt/lists/*
```

---

### 15.3 Security Best Practices

**Never run as root:**

```dockerfile
RUN groupadd -r appgroup && useradd -r -g appgroup appuser
USER appuser
```

**Don't store secrets in the image:**

```dockerfile
# WRONG — secret baked into the image layer forever
RUN curl -H "Authorization: Bearer mysecret" https://api.example.com

# CORRECT — BuildKit secret (never stored in any layer)
RUN --mount=type=secret,id=api_token \
    curl -H "Authorization: Bearer $(cat /run/secrets/api_token)" https://api.example.com
```

```bash
docker build --secret id=api_token,src=./token.txt .
```

**Pin image versions:**

```dockerfile
# WRONG — unpredictable
FROM node:latest

# CORRECT — reproducible
FROM node:20.11.1-alpine3.19
```

**Scan for vulnerabilities:**

```bash
docker scout cves myapp:latest
trivy image myapp:latest
```

---

### 15.4 Dockerfile Writing Tips

**Use ENTRYPOINT + CMD together:**

```dockerfile
ENTRYPOINT ["java", "-jar"]
CMD ["app.jar"]
# Override: docker run myapp other.jar
```

**Prefer COPY over ADD:**

```dockerfile
COPY app.tar.gz /app/      # predictable: copies as-is
ADD  app.tar.gz /app/      # unpacks automatically (surprising!)
# Only use ADD when you need tar auto-extraction
```

**Set WORKDIR explicitly:**

```dockerfile
WORKDIR /app               # correct
# NOT: RUN mkdir /app && cd /app
```

**Use HEALTHCHECK:**

```dockerfile
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
  CMD curl -f http://localhost:8080/health || exit 1
```

**Use ARG + LABEL for metadata:**

```dockerfile
ARG APP_VERSION=1.0.0
LABEL version="${APP_VERSION}" \
      maintainer="team@example.com"
```

---

### 15.5 .dockerignore

Always create `.dockerignore` to exclude unnecessary files from the build context:

```
# .dockerignore
.git
.gitignore
.env
*.log
node_modules
__pycache__
*.pyc
dist
coverage
.DS_Store
README.md
Dockerfile*
docker-compose*
```

Benefits:
- Faster builds (smaller build context sent to daemon)
- Prevents secrets (`.env`) from leaking into the image
- Prevents large directories (`node_modules`) from being unnecessarily copied

---

### 15.6 Resource & Runtime Best Practices

**Use tini or dumb-init as PID 1:**

```dockerfile
FROM node:20-alpine
RUN apk add --no-cache tini
ENTRYPOINT ["/sbin/tini", "--"]
CMD ["node", "server.js"]
```

**One process per container** — use orchestration (Kubernetes, Compose) to link multiple containers.

**Make containers stateless** — store state in external volumes or databases, not the container filesystem.

**Set resource limits:**

```yaml
# docker-compose.yml
services:
  app:
    image: myapp:latest
    deploy:
      resources:
        limits:
          cpus: '0.5'
          memory: 256M
```

---

## 16. Quick Reference Cheat Sheet

### Container Commands

```bash
docker run -d -p 8080:80 --name myapp nginx    # run detached with port mapping
docker ps                                       # list running containers
docker ps -a                                    # list all containers
docker logs -f myapp                            # follow logs
docker exec -it myapp bash                      # shell into container
docker stop myapp && docker rm myapp            # stop and remove
docker stats                                    # live resource usage
```

### Image Commands

```bash
docker build -t myapp:1.0 .                    # build image
docker images                                   # list images
docker pull nginx:alpine                        # pull from registry
docker tag myapp:1.0 user/myapp:1.0             # tag image
docker push user/myapp:1.0                      # push to registry
docker rmi myapp:1.0                            # remove image
docker history myapp:latest                     # show layers
docker inspect myapp:latest                     # full details
```

### Multi-Stage & BuildKit

```bash
docker build --target builder -t myapp:builder .    # build specific stage
DOCKER_BUILDKIT=1 docker build -t myapp:latest .    # enable BuildKit
docker build --secret id=mysecret,src=./secret.txt . # use build secret
docker build --build-arg VERSION=2.0.0 -t myapp .   # pass build arg
```

### Cleanup

```bash
docker container prune          # remove all stopped containers
docker image prune -a           # remove all unused images
docker volume prune             # remove unused volumes
docker system prune -a          # remove everything unused
docker system df                # check disk usage
```

### Dockerfile Instruction Summary

| Instruction | Build/Run | Purpose |
|-------------|-----------|---------|
| `FROM` | Build | Set base image / start new stage |
| `WORKDIR` | Build | Set working directory |
| `COPY` | Build | Copy files from host or another stage |
| `ADD` | Build | Like COPY but with tar extraction |
| `RUN` | Build | Execute commands at build time |
| `ENV` | Both | Set environment variables |
| `ARG` | Build | Build-time variables only |
| `EXPOSE` | Build | Document the listening port |
| `CMD` | Run | Default command (overridable) |
| `ENTRYPOINT` | Run | Fixed command, CMD provides args |
| `USER` | Build | Switch to non-root user |
| `HEALTHCHECK` | Run | Container health check command |
| `LABEL` | Build | Add metadata to the image |
| `VOLUME` | Run | Declare a persistent mount point |

---

> **Key Takeaways:**
> - Day 1: Containers are lightweight, portable, and share the host OS kernel — unlike VMs.
> - Day 2: A Dockerfile is the recipe for your image. Order instructions to leverage layer caching.
> - Day 3: Multi-stage builds produce small, secure, production-ready images. Combine with best practices (non-root user, pinned versions, `.dockerignore`) for robust deployments.

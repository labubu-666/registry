# Open Container Initiative

Implemented as [Open Container Initiative](https://github.com/opencontainers/distribution-spec/blob/v1.1.1/spec.md) with [Docker Registry v2 Token Authentication](https://docs.docker.com/registry/spec/auth/token/).

# Quick Start 🏃

# Local Development

Run the registry directly with Python:

```bash
uv run python main.py
```

# Docker

```bash
docker build . --tag registry:latest && docker run --publish 5000:5000 --rm registry:latest
```

# Docker Compose

```bash
docker compose up --build
```

The registry will start on http://localhost:5000

# 1. Configure Docker for Insecure Registry

The registry runs on HTTP by default. 

Configure Docker to allow insecure registries. 

The steps depend on your platform -

## GNU/Linux

Edit `/etc/docker/daemon.json`.

```json
{
  "insecure-registries": ["localhost:5000"]
}
```

```bash
sudo systemctl restart docker
```

## macOS with Colima (Registry Running on Host)

When running the registry on your Mac host with `uv run python main.py`, use `host.docker.internal:5000` because the Colima VM is isolated from your Mac's localhost.

Edit `~/.colima/default/daemon.json`.

```json
{
  "insecure-registries": ["host.docker.internal:5000"]
}
```

Restart Colima to apply changes

```bash
colima stop
colima start
```

## Windows

For Docker Desktop, use localhost:5000

```json
{
  "insecure-registries": ["localhost:5000"]
}
```

**Steps:**
- Open Docker Desktop → Settings → Docker Engine
- Paste the configuration above (use `localhost:5000` for Docker Desktop)
- Click "Apply & Restart"

# 2. Test 

# For macOS with Colima (Host Registry)

```bash
# Tag an Alpine image for host.docker.internal
docker tag alpine:3.22.4 host.docker.internal:5000/alpine:3.22.4

# Push to your local registry
docker push host.docker.internal:5000/alpine:3.22.4

# Verify it worked (from host)
curl http://localhost:5000/v2/_catalog
```

# For Docker Desktop or GNU/Linux

```bash
# Tag an Alpine image
docker tag alpine:3.22.4 localhost:5000/alpine:3.22.4

# Push to your local registry
docker push localhost:5000/alpine:3.22.4

# Verify it worked
curl http://localhost:5000/v2/_catalog
```

# API Endpoints 📡

## Authentication

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/auth/token` | Obtain a JWT (anonymous or via HTTP Basic Auth) |

**Query parameters for `/auth/token`:**

| Parameter | Description |
|-----------|-------------|
| `service` | Registry service name (sent automatically by Docker) |
| `scope` | Resource scope, e.g. `repository:alpine:pull,push` |
| `account` | Username hint for anonymous tokens |


## Core API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Root endpoint |
| `GET` | `/api/v1/docs` | Docs |
| `GET` | `/api/v1/repositories` | Paginated list of repositories |
| `DELETE` | `/api/v1/repositories/{repo}` | Delete repository. Recursively deletes manifests and blobs not referenced elsewhere |

## Docker Registry v2 API

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/v2/` | API version check |
| `GET` | `/v2/_catalog` | List all repositories |
| `GET` | `/v2/{repo}/tags/list` | List tags for a repository |
| `GET` | `/v2/{repo}/manifests/{ref}` | Get manifest |
| `PUT` | `/v2/{repo}/manifests/{ref}` | Upload manifest |
| `HEAD` | `/v2/{repo}/manifests/{ref}` | Check manifest exists |
| `GET` | `/v2/{repo}/blobs/{digest}` | Download blob |
| `HEAD` | `/v2/{repo}/blobs/{digest}` | Check blob exists |
| `POST` | `/v2/{repo}/blobs/uploads/` | Initiate blob upload |
| `PUT` | `/v2/{repo}/blobs/uploads/{uuid}` | Complete blob upload |
| `DELETE` | `/v2/{repo}/manifests/{ref}` | Delete manifest |

# Example Usage 💡

## Check registry version

```bash
curl http://localhost:5000/v2/
```

## List repositories

```bash
curl http://localhost:5000/v2/_catalog
```

Read more on [authentication](./authentication.md).

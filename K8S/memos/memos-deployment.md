# Memos + PostgreSQL 17 on Kubernetes

A self-hosted [Memos](https://github.com/usememos/memos) app backed by PostgreSQL 17. It runs on a two-node k3s cluster (`golahmar-ha1` control-plane, `golahmar-ha2` worker). It has its own namespace, separate Secret/ConfigMap, and external access via Ingress.

**Live at:** `http://golahmar.osdl.ir`

---

## Table of Contents

- [What I Did](#what-i-did)
- [Problems Encountered](#problems-encountered)
- [Design Decisions](#design-decisions)
- [Manifest Files](#manifest-files)

---

## What I Did

### 1. Namespace Isolation

Created a `memos` namespace. This keeps all app resources separate from the `default` namespace.

### 2. Secret & ConfigMap Separation

Split config into two objects:

- **`memos-db-secret`** — sensitive values: `POSTGRES_PASSWORD` and `MEMOS_DSN`.
- **`memos-config`** — non-sensitive values: `POSTGRES_DB`, `POSTGRES_USER`, `MEMOS_DRIVER`, `MEMOS_PORT`.

Both pods load non-sensitive values in bulk via `envFrom`. Each sensitive value is injected one at a time via `env` + `secretKeyRef`, so it's clear which secret goes to which pod.

### 3. PostgreSQL 17 (StatefulSet)

Deployed as a `StatefulSet`, not a `Deployment`, because a database needs stable identity and storage across restarts. `volumeClaimTemplates` gives each pod its own sticky PVC, so it always reattaches to the same disk. Paired with a headless Service (`clusterIP: None`), so DNS resolves straight to the pod's IP instead of a load-balanced virtual IP.

`pg_isready` probes make sure Kubernetes only sends traffic once Postgres is ready.

Two separate storage volumes, one per pod, never touch each other:

| Pod | PVC | Mount path | Holds |
|---|---|---|---|
| Memos | `memos-data` (plain PVC) | `/var/opt/memos` | Uploaded attachments |
| Postgres | `pgdata` (via `volumeClaimTemplates`) | `/var/lib/postgresql/data` | Table rows (notes, users, etc.) |

The two pods only connect over the network. Neither mounts the other's disk.

### 4. Memos (Deployment)

Deployed as a plain `Deployment`, since Memos doesn't need per-replica identity — its state lives in Postgres and in its own PVC. It connects to Postgres via the `MEMOS_DSN` env variable. Exposed internally through a normal `ClusterIP` Service, since Memos replicas are interchangeable and can be load-balanced.

`httpGet` probes on `/healthz` confirm the app is actually serving HTTP, not just that the process started.

### 5. External Access (Ingress)

Created an `Ingress` that routes `golahmar.osdl.ir` to the Memos Service, on port 80 only (no TLS, per the task requirement), using Traefik (already running as part of k3s).

---

## Problems Encountered

### `ImagePullBackOff` on the Postgres pod

The `memos-postgres-0` pod kept cycling through `ImagePullBackOff` / `ErrImagePull`.

**Diagnosis:** `kubectl describe pod memos-postgres-0 -n memos` showed a `403 Forbidden` on signed CloudFront URLs — not a Docker Hub rate limit. Pulling the same image separately worked fine.

**Fix:** Deleted the deployment and reapplied it. That fixed it.

---

## Design Decisions

- **StatefulSet for Postgres, Deployment for Memos** — only Postgres needs stable identity and storage.
- **Headless Service for Postgres, normal Service for Memos** — Postgres traffic needs a specific instance; Memos traffic can go to any replica.
- **`volumeClaimTemplates` for Postgres, standalone PVC for Memos** — StatefulSets auto-generate per-replica storage; Deployments don't.
- **Sensitive values always via `env` + `secretKeyRef`, never bulk `envFrom: secretRef`** — keeps it clear which secret data each pod gets.

## Manifest Files

```
manifests/
├── 00-namespace.yaml     # memos namespace
├── 01-secret.yaml        # POSTGRES_PASSWORD, MEMOS_DSN
├── 02-configmap.yaml     # POSTGRES_DB, POSTGRES_USER, MEMOS_DRIVER, MEMOS_PORT
├── 03-postgres.yaml      # headless Service + StatefulSet + volumeClaimTemplates
├── 04-memos.yaml         # PVC + Deployment + Service
└── 05-ingress.yaml       # Ingress for golahmar.osdl.ir, port 80
```

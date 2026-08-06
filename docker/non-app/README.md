# Docker Compose Task: Non-App PID 1 + Resource Limits

A minimal FastAPI service demonstrating two Docker requirements:
1. **PID 1 is not the application** — `tini` is used as the init process.
2. **CPU and RAM are limited**, with endpoints to demonstrate both limits under load.

## Project structure

```
.
├── Dockerfile
├── docker-compose.yml
├── README.md
└── app/
    ├── main.py
    └── requirements.txt
```

## Run

```bash
docker compose up --build -d
docker compose ps
```

API available at `http://localhost:8000`.

---

## Demonstration 1: PID 1 is not the app

```bash
docker exec -it pid1-resource-demo ps aux
```

`tini` shows up as PID 1; `uvicorn` (the actual app) runs as its child (PID 2+).
`tini` is set as the Dockerfile's `ENTRYPOINT`, so it always wraps whatever `CMD` runs — it forwards signals (e.g. `SIGTERM` from `docker stop`) to the app and reaps any zombie child processes, jobs the app itself would otherwise have to handle.

---

## Demonstration 2: CPU limit (0.5 core)

```bash
curl "http://localhost:8000/burn-cpu?seconds=10"
```

Watched via `docker stats` in a second terminal, CPU% stays capped around **50%** — the Linux CFS scheduler enforces `cpu.cfs_quota_us` (50ms allowed per 100ms period), throttling the process rather than killing it. The request still completes, just slower.

---

## Demonstration 3: Memory limit (256M) — actual run

```bash
curl "http://localhost:8000/memory-test?size_mb=10000"
```

Requesting a 10,000MB allocation against a 256M cgroup limit triggers the kernel OOM killer. Captured via `docker events` during the test:

```
container die     ... exitCode=137, service=api, name=pid1-resource-demo
container start    ... service=api, name=pid1-resource-demo
```

What this confirms:
- **`exitCode=137`** = `128 + 9` (SIGKILL) — the standard signature of an OOM kill, not a normal app crash.
- The **`die`** event fires the instant the container's memory cgroup is exceeded and the kernel kills the process — no graceful shutdown is possible with SIGKILL.
- The **`start`** event right after shows `restart: unless-stopped` (in `docker-compose.yml`) immediately bringing the same container back up with a fresh process and empty memory state.

Additional verification commands:
```bash
docker inspect pid1-resource-demo --format '{{.State.OOMKilled}}'   # true
docker inspect pid1-resource-demo --format '{{.State.ExitCode}}'    # 137
```

---

## Key config (`docker-compose.yml`)

```yaml
init: false            # tini (in the Dockerfile) already handles PID 1, so Docker's built-in --init is unnecessary
deploy:
  resources:
    limits:
      cpus: "0.50"      # hard ceiling
      memory: 256M      # hard ceiling
    reservations:
      cpus: "0.25"      # soft guarantee
      memory: 128M
restart: unless-stopped  # auto-recovers after an OOM kill or crash
```

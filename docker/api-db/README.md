# Transaction API

A minimal FastAPI service that writes/reads transaction records to PostgreSQL, orchestrated with Docker Compose.

## Stack

- **API**: FastAPI + SQLAlchemy (ORM) + psycopg2
- **DB**: PostgreSQL 16 (alpine)
- **Orchestration**: Docker Compose (single-stage, hardened Dockerfile)

## Project layout

```
.
├── app/
│   ├── main.py 
│   └── requirements.txt
│
├── scripts/
│   ├── backup.sh         # runs inside the "backup" service, loops pg_dump daily
│   └── restore.sh        # run from host: restores a dump into the running db
├── backups/               # created at runtime — dump files land here
├── Dockerfile
├── docker-compose.yml
├── .env
└── .dockerignore
```

## Run

```bash
docker compose up --build -d
```

- API: http://localhost:8080
- Interactive docs: http://localhost:8080/docs
- The `transactions` table is created automatically on first API startup.
- The database persists in the `pgdata` named volume across restarts.

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/health` | API + DB connectivity check |
| POST | `/transactions` | create a transaction (`sender`, `receiver`, `amount`) |
| GET | `/transactions` | list all transactions, newest first |
| GET | `/transactions/{id}` | get one transaction |

Example:
```bash
curl -X POST http://localhost:8080/transactions \
  -H "Content-Type: application/json" \
  -d '{"sender": "alice", "receiver": "bob", "amount": 42.50}'
```

## Key design points

- **API ↔ DB connection uses the Compose service name (`db`)** as the hostname. Docker's embedded DNS resolves it inside the `backend` network — no hardcoded IPs.
- **Persistence**: `pgdata` named volume mounted at Postgres's data directory. Survives `docker compose down`; only removed with `docker compose down -v`.
- **Hardened**: non-root container user, no DB port exposed to host, read-only API filesystem, `no-new-privileges`, resource limits, pinned dependency versions.

## Backups

A `backup` service (in `docker-compose.yml`) runs alongside `api` and `db`. It uses `pg_dump` to write a compressed dump of the database to `./backups/` once every 24 hours, and automatically deletes dumps older than `BACKUP_RETENTION_DAYS` (default: 7, set in `docker-compose.yml`).

Backups land in a **host-mounted folder**, not a Docker volume — so they're safe even if the `pgdata` volume itself is deleted, and directly copyable off the machine.

**Manual backup (anytime, on demand):**
```bash
docker compose exec db pg_dump -U "$POSTGRES_USER" -d "$POSTGRES_DB" -F c -f /tmp/manual.dump
docker compose cp db:/tmp/manual.dump ./backups/manual_$(date +%Y%m%d_%H%M%S).dump
```

**Restore from a dump:**
```bash
./scripts/restore.sh ./backups/transactions_db_20260806_120000.dump
```
This drops and recreates existing objects (`--clean --if-exists`) before restoring — confirm you're targeting the right dump file before continuing.

**View backup logs:**
```bash
docker logs -f transaction_db_backup
```
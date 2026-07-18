# Deployment — SafeCycle Backend

This document describes how the `safecycle-backend` service is deployed to
**Railway** today, and how to migrate it to AWS / GCP / any container platform
later with minimal effort.

The guiding principle: **the container is portable, the platform is disposable.**
The app reads *everything* it needs from environment variables
([`app/config.py`](app/config.py)), and ships as a plain
[`Dockerfile`](Dockerfile) that runs identically on Railway, ECS, Cloud Run,
Fly, or `docker run`. Migrating platforms means repointing connection strings —
not rewriting the app.

---

## 1. Architecture

Three services, mirroring [`docker-compose.yml`](docker-compose.yml) (which
stays the source of truth for local dev):

| Local (`docker-compose`)        | Railway service           | Cloud equivalent (later)                     |
| ------------------------------- | ------------------------- | -------------------------------------------- |
| `api` (this Dockerfile)         | **safecycle-backend**     | ECS/Fargate task · Cloud Run · Fly Machine   |
| `db` (`postgis/postgis:15-3.3`) | **Postgres** (see §5 ⚠️)  | AWS RDS Postgres · GCP Cloud SQL (+PostGIS)  |
| `redis` (`redis:7-alpine`)      | **Redis**                 | AWS ElastiCache · GCP Memorystore            |

The `api` service talks to the other two **only** through `DATABASE_URL` and
`REDIS_URL`. There is no hardcoded host, no reliance on Railway's private
networking DNS inside application code.

---

## 2. Required environment variables

Set these on the **safecycle-backend** service. Names and defaults come straight
from [`app/config.py`](app/config.py) (pydantic-settings, `case_sensitive=True`).

### Required

| Variable        | Example / Required value                                             | Notes                                                                 |
| --------------- | ------------------------------------------------------------------- | --------------------------------------------------------------------- |
| `DATABASE_URL`  | `postgresql+asyncpg://user:pass@host:5432/dbname`                   | ⚠️ **Must use the `postgresql+asyncpg://` scheme** — see §4.          |
| `REDIS_URL`     | `redis://host:6379/0`                                               | Railway Redis provides this; format is already correct.               |
| `ENVIRONMENT`   | `production`                                                        | Anything other than `development`.                                    |
| `DEBUG`         | `false`                                                            | Leave off / false in prod (true enables SQL echo).                    |

### Firebase (push notifications only — not hosting)

| Variable                    | Value                          | Notes                                                                                 |
| --------------------------- | ------------------------------ | -------------------------------------------------------------------------------------- |
| `FIREBASE_ENABLED`          | `true` / `false`               | Set `false` to disable FCM entirely (app degrades gracefully).                       |
| `FIREBASE_CREDENTIALS_JSON` | *(full service account JSON)*  | **Use this on Railway/cloud** — the JSON file's contents as one string. Takes priority over the path below. See §7. |
| `FIREBASE_CREDENTIALS_PATH` | `firebase-credentials.json`    | File-path fallback, used only when `FIREBASE_CREDENTIALS_JSON` is unset (local dev). |

### Optional / tunable (safe defaults exist)

| Variable                | Default | Purpose                                    |
| ----------------------- | ------- | ------------------------------------------ |
| `PORT`                  | `8000`  | See §3 — Railway routing target port.      |
| `ALLOWED_ORIGINS`       | `["*"]` | CORS origins (JSON list).                  |
| `GOOGLE_MAPS_API_KEY`   | `""`    | Google Roads/Maps features.               |
| `DATABASE_POOL_SIZE`    | `10`    | SQLAlchemy pool.                           |
| `DATABASE_MAX_OVERFLOW` | `20`    | SQLAlchemy overflow.                       |

> A full list of tunables (hazard TTLs, graph bbox, VeloBG refresh, WebSocket
> limits, safety thresholds) lives in [`app/config.py`](app/config.py). All have
> production-safe defaults; override only when you need to.

---

## 3. Port / listening

The container **always listens on `8000`** (`EXPOSE 8000`, and uvicorn binds
`--port 8000` in the Dockerfile CMD). This is deliberately fixed so the image
behaves identically everywhere.

- **Railway:** set the service's target port to `8000` (Settings → Networking,
  or set a `PORT=8000` service variable). Railway's edge proxy will route to it.
- **Cloud Run:** set the container port to `8000` (Cloud Run defaults to `8080`).
- **ECS / ALB:** target group port `8000`.

The app does **not** read `PORT` to choose its bind port — it's listed above only
because Railway uses that variable to decide where to route. If you ever want the
bind port itself to be dynamic, that's a Dockerfile CMD change; flag it before
doing so.

---

## 4. Wiring the three Railway services together

1. **Create the project** and add three services: the app (from this repo),
   a **Postgres**, and a **Redis** (Railway → New → Database).
2. **Point the app service at this subfolder.** In the app service Settings, set
   the **Root Directory** to `safecycle-backend` so Railway builds
   `safecycle-backend/Dockerfile` (a Dockerfile is present, so Railway uses it —
   nixpacks is *not* used).
3. **Reference the databases via variables.** In the **safecycle-backend**
   service variables:
   - `REDIS_URL` → reference the Redis service's connection URL
     (e.g. `${{Redis.REDIS_URL}}` in Railway's variable-reference syntax).
   - `DATABASE_URL` → **do not** reference Postgres's raw URL directly, because
     Railway hands out `postgresql://…` and the app needs `postgresql+asyncpg://…`.
     Set it explicitly with the driver, e.g.:
     ```
     postgresql+asyncpg://${{Postgres.PGUSER}}:${{Postgres.PGPASSWORD}}@${{Postgres.PGHOST}}:${{Postgres.PGPORT}}/${{Postgres.PGDATABASE}}
     ```
     > The `${{Service.VAR}}` reference syntax lives **only in Railway's
     > dashboard config**, never in application code — so it doesn't create
     > lock-in. On AWS/GCP you'd just paste a plain connection string here.
4. **Set the remaining variables** from §2 (`ENVIRONMENT`, `DEBUG`,
   `FIREBASE_*`, etc.).
5. **Run the database migrations** — see §5.

---

## 5. ⚠️ Database requires PostGIS + manual migrations

Two things about the database that differ from a stock Railway Postgres:

**(a) PostGIS is required.** The schema uses the PostGIS extension and spatial
types/functions — see [`app/db/migrations/001_initial.sql`](app/db/migrations/001_initial.sql)
(`CREATE EXTENSION postgis`, `GEOMETRY(Point,4326)`, `GIST` indexes, `ST_*`).
Railway's managed Postgres plugin is **vanilla Postgres and may not include the
PostGIS binaries**, so `CREATE EXTENSION postgis` can fail. Options:

- Try `CREATE EXTENSION IF NOT EXISTS postgis;` against the Railway Postgres — if
  the extension is available, you're done.
- If it isn't, deploy Postgres as a **custom Railway service from the
  `postgis/postgis:15-3.3-alpine` image** (the same image `docker-compose.yml`
  uses locally) instead of the managed plugin, and point `DATABASE_URL` at it.

**(b) Migrations do not auto-run on Railway.** Locally, `docker-compose` mounts
`001_initial.sql` into the Postgres container's `docker-entrypoint-initdb.d`.
Railway's database has no such hook, so apply the migrations yourself once the DB
is up, in order:

```bash
# from a machine with psql and the Railway DB URL (plain postgresql:// form):
psql "$RAILWAY_PLAIN_DATABASE_URL" -f app/db/migrations/001_initial.sql
psql "$RAILWAY_PLAIN_DATABASE_URL" -f app/db/migrations/006_velobg_paths.sql
psql "$RAILWAY_PLAIN_DATABASE_URL" -f app/db/migrations/007_notification_log.sql
```

(Use the plain `postgresql://` URL for `psql`; the `+asyncpg` variant is only for
the app.) The `/health/ready` endpoint returns `503` until Postgres, Redis, and
the routing graph are all reachable — use it to confirm the wiring.

---

## 6. ⚠️ Cold start takes ~3–4 minutes — configure Railway's health check timeout

On a **fresh container** (no graph cache, no VeloBG cache — i.e. every first
deploy, and every deploy after a filesystem reset), startup does real work
before the process can answer requests:

- Downloads and caches the Sofia OSMnx graph (~10–60s depending on cache state).
- Enriches the graph with the local GeoJSON bike-alley dataset — measured
  **~145s** on a clean build (unindexed nearest-edge matching over ~36k graph
  nodes for 486 features).
- Fetches and enriches VeloBG path data from a live Google My Maps KML export
  — measured **~62s**.

Verified end-to-end: total cold start was **~215s** (app process up to
`/health/ready` returning `200`). The Dockerfile's `HEALTHCHECK
--start-period` and `docker-compose.yml`'s `start_period` have been bumped
from `90s` to `240s` to match — the old value under-counted the real startup
window and caused the container to report `unhealthy` for roughly two minutes
while it was, in fact, still legitimately starting.

**Action needed on Railway:** its deploy health check (Settings → Deploy →
Healthcheck Path `/health/ready` + Healthcheck Timeout) must be set to
tolerate this same ~3–4 minute window, or Railway may mark the deploy failed
and roll back before the app finishes booting. Increase the timeout there to
match (e.g. 300s) with some margin.

If subsequent deploys reuse a persisted volume with a warm graph/VeloBG cache,
cold start is much faster (~15–20s, per the `graph_cache_hit` log line) — but
don't assume that; Railway's default filesystem is ephemeral between deploys
unless a volume is explicitly attached.

---

## 7. Firebase credentials — env var, no file required

[`app/services/notification_service.py`](app/services/notification_service.py)
now accepts the service account **JSON directly via an env var**:

```python
if settings.FIREBASE_CREDENTIALS_JSON:
    cred = credentials.Certificate(json.loads(settings.FIREBASE_CREDENTIALS_JSON))
else:
    cred = credentials.Certificate(settings.FIREBASE_CREDENTIALS_PATH)
```

Set **`FIREBASE_CREDENTIALS_JSON`** on Railway (and any other platform) to the
full contents of the Firebase service account JSON file, as a single-line
string. No filesystem access, no volume mount, no Railway-specific handling —
it's a plain secret like `DATABASE_URL`. `FIREBASE_CREDENTIALS_PATH` (the old
file-path variable) still works as a fallback for local dev, where mounting a
JSON file is easy. Set `FIREBASE_ENABLED=false` to disable push entirely — the
notification layer degrades gracefully either way.

---

## 8. CI/CD pipeline

[`.github/workflows/deploy.yml`](../.github/workflows/deploy.yml) runs on every
push to `main`:

1. **Build** the Docker image from `safecycle-backend/Dockerfile` (proves it
   compiles).
2. **Test** — runs `pytest` **inside that image**, so the tested environment is
   byte-identical to what deploys. The suite (`safecycle-backend/tests/`) is
   fully mocked (no live DB/Redis). A test failure fails the job and **blocks the
   deploy**.
3. **Deploy** — installs the Railway CLI and runs
   `railway up --service safecycle-backend --detach`, authenticated by the
   `RAILWAY_TOKEN` repo secret (a Railway **project token**).

> **Note on the test suite:** the deploy gate runs `safecycle-backend`'s own
> `tests/` directory — the self-contained suite for the service being deployed.
> The root-level `test_api.py` / `test_notifications.py` belong to the separate
> top-level app (they import the root `notifications` package, and `test_api.py`
> is a manual smoke script that needs a live server), so they are **not** part of
> this service's gate.

**Setup required (one-time):** create a Railway **Project Token** (scoped to the
project + environment you deploy to) and add it as a repository secret named
`RAILWAY_TOKEN` under *Settings → Secrets and variables → Actions*.

---

## 9. How to migrate off Railway

Because all config is environment-driven and the image is a standard Dockerfile,
migration is mostly "run the same container somewhere else, hand it new
connection strings."

1. **Provision managed backing services** on the target cloud:
   - Postgres **with PostGIS**: AWS RDS for PostgreSQL (enable the `postgis`
     extension) or GCP Cloud SQL for PostgreSQL (add the PostGIS extension).
   - Redis: AWS ElastiCache or GCP Memorystore.
2. **Run the migrations** (§5) against the new database once.
3. **Deploy the same image** to your compute:
   - **AWS ECS/Fargate:** push the image to ECR, run it as a task, target
     port `8000`, health check `GET /health/ready`.
   - **GCP Cloud Run:** push to Artifact Registry, deploy, set container port
     `8000`, health check `/health/ready`.
4. **Set the same environment variables** (§2) — the only values that change are:
   - `DATABASE_URL` → your RDS/Cloud SQL endpoint (keep the
     `postgresql+asyncpg://` scheme).
   - `REDIS_URL` → your ElastiCache/Memorystore endpoint.
   - Firebase creds per §7.
5. **Repoint CI.** Swap the "Deploy to Railway" step in
   `.github/workflows/deploy.yml` for your target's deploy action (e.g.
   `aws ecs update-service` or `gcloud run deploy`). The build-and-test job is
   unchanged — it's platform-agnostic.

Nothing above touches application code. The Railway-specific surface area is
confined to: the `railway up` step in the workflow, the `${{Service.VAR}}`
references in the dashboard, and the `RAILWAY_TOKEN` secret.

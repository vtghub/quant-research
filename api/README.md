# quant-research-api

A multi-user FastAPI service wrapping the `quant_research` engine: account
signup/login (JWT), saved pipeline configs, and async research/backtest runs
executed by Celery workers, with a React frontend (`../frontend`) on top.

## Architecture

```
FastAPI (uvicorn)  <-- HTTP -->  React/Vite SPA
     |
     | SQLAlchemy
     v
PostgreSQL (users, saved_configs, runs)
     |
     | Celery .delay()
     v
Redis (broker + result backend)
     |
     v
Celery worker --> quant_research.pipeline.orchestrator.Pipeline
                   (the exact same engine the CLI uses)
```

- **Registry endpoint reuses the engine's registries directly** (`core/registries.py`)
  -- the same data sources/signals/strategies the CLI's `list-registry` shows
  are what the frontend's config-builder dropdowns list.
- **Config validation reuses `PipelineConfig`** -- a saved config is rejected
  at save time with the exact same pydantic errors `quant-research
  validate-config` would give, not discovered later inside a worker.
- **Every run stores a config snapshot**, not just a foreign key to the saved
  config -- editing or deleting a saved config never changes historical run
  results.
- **Per-run artifact isolation**: the Celery task overrides
  `report.output_dir` to `<artifacts_root>/<run_id>` regardless of what the
  config says, so two runs (even of the same saved config) never overwrite
  each other's tearsheet files.

## Local development (no Docker)

Requires PostgreSQL and Redis running locally, plus the core engine installed.

```bash
# from the repo root
python3 -m venv .venv && source .venv/bin/activate
pip install -e .                    # the core engine
pip install -e ./api -e "./api[dev]"  # this service + test deps

# start postgres & redis however your system does (services, brew, etc.)
createuser qra --pwprompt   # password: qra (or set QRA_DATABASE_URL yourself)
createdb qra -O qra
createdb qra_test -O qra    # only if you'll run the test suite against real postgres

cd api
alembic upgrade head         # creates users / saved_configs / runs tables

# terminal 1
uvicorn quant_research_api.main:app --reload --port 8000
# terminal 2
celery -A quant_research_api.celery_app worker --loglevel=info
# terminal 3 (frontend)
cd ../frontend && npm install && npm run dev
```

Then open http://localhost:5173 -- the Vite dev server proxies `/api/*` to
`http://127.0.0.1:8000` (see `frontend/vite.config.ts`), so the SPA never
needs to know the backend's host/port and there's no CORS to configure for
local dev.

## Configuration

All settings are environment variables prefixed `QRA_` (see
`quant_research_api/settings.py`), or a `.env` file in `api/`:

| Variable | Default | Purpose |
|---|---|---|
| `QRA_DATABASE_URL` | `postgresql+psycopg://qra:qra@localhost:5432/qra` | SQLAlchemy connection string |
| `QRA_REDIS_URL` | `redis://localhost:6379/0` | Celery broker + result backend |
| `QRA_JWT_SECRET` | dev placeholder | **override this in any real deployment** |
| `QRA_ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | JWT lifetime |
| `QRA_CORS_ORIGINS` | `["http://localhost:5173"]` | JSON list of allowed frontend origins |
| `QRA_ARTIFACTS_ROOT` | `api_data/reports` | Where per-run tearsheet files are written |

## Docker Compose

`docker-compose.yml` at the repo root wires up Postgres, Redis, the API,
a Celery worker, and an nginx-served frontend build:

```bash
docker compose up --build
```

API on `:8000`, frontend on `:8080`. **Note**: this was written following
standard patterns but could not be built/run inside the session that
authored it -- that session's network policy blocks Docker Hub image pulls
the same way it blocks live data vendors (confirmed with a real `docker
pull`, not assumed). Verify it once in an environment with normal registry
access before relying on it.

## Testing

```bash
cd api
pytest
```

Runs fully offline: an in-memory SQLite database (via a `StaticPool`-backed
engine so independent sessions still share data) stands in for Postgres, and
Celery's `task_always_eager` setting runs tasks synchronously in-process --
no real Redis or worker process needed. A registered fake `DataSource` (same
pattern the core engine's own tests use) exercises the run lifecycle without
hitting any live vendor.

## API surface

| Method | Path | Auth | Purpose |
|---|---|---|---|
| POST | `/auth/register` | - | Create an account |
| POST | `/auth/login` | - | OAuth2 password flow, returns a JWT |
| GET | `/auth/me` | required | Current user |
| GET | `/registry` | - | Every registered data source/signal/strategy/etc. |
| POST/GET/PUT/DELETE | `/configs[/{id}]` | required | Saved pipeline configs, owner-scoped |
| POST | `/runs` | required | Trigger a research or backtest run (`config_id` or inline `config_json`) |
| GET | `/runs` / `/runs/{id}` | required | List / poll run status and results |
| GET | `/runs/{id}/artifacts/{filename}` | required | Download a tearsheet file, owner-scoped |

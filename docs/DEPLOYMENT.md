# Deployment

## Local

```bash
pip install -r requirements.txt
cp .env.example .env     # edit
python main.py
```

Defaults bind `127.0.0.1:8000` with the fake LLM and fake catalog. Nothing leaves the machine.

## Docker

```bash
docker build -t ai-shopping-bot .
docker run --rm -p 8000:8000 --env-file .env ai-shopping-bot
```

The image runs as a non-root user, binds `0.0.0.0:8000`, and has a `/health` healthcheck. Pass secrets with `--env-file` or your orchestrator's secret store. Never bake them into the image.

## Environment

Every setting has a `SHOPBOT_` prefix except provider keys, which keep their conventional names so the same `.env` works across your projects.

| Variable | Default | Purpose |
|---|---|---|
| `SHOPBOT_LLM` | `fake` | `fake` or `live` |
| `SHOPBOT_MODELS__UNDERSTANDING` | `openai/gpt-4o-mini` | Model for the understanding role |
| `SHOPBOT_MODELS__PLANNING` | same | Planner fallback |
| `SHOPBOT_MODELS__RESPONSE` | same | Reply writer |
| `SHOPBOT_MODELS__ENRICH` | same | Comparison, checklist, rationale, review and research tools |
| `OPENAI_API_KEY`, `SILICONFLOW_API_KEY`, `OPENROUTER_API_KEY` | unset | Set the ones your models use |
| `SILICONFLOW_BASE_URL` | `https://api.siliconflow.com/v1` | Override for regional endpoints |
| `SHOPBOT_CATALOG` | `fake` | `fake` or `unwrangle` |
| `UNWRANGLE_APIKEY` | unset | Required when catalog is `unwrangle` |
| `SHOPBOT_SESSION_STORE` | `memory` | `memory` or `sqlite` |
| `SHOPBOT_SQLITE_PATH` | `shopbot.db` | Mount a volume here in Docker |
| `SHOPBOT_CACHE_TTL_S` | `86400` | Search result cache TTL |
| `SHOPBOT_LLM_MAX_CALLS_PER_REQUEST` | `4` | Hard budget per chat turn |
| `SHOPBOT_TRACKING` | `memory` | `off`, `memory`, or `sqlite`. Price and availability history for every product seen |
| `SHOPBOT_TRACKING_SQLITE_PATH` | unset | Defaults to `SHOPBOT_SQLITE_PATH`. Separate tables from sessions |
| `SHOPBOT_TRACKING_MONITOR_INTERVAL_S` | `0` | Re-check watched products every N seconds in a background thread. `0` disables |
| `SHOPBOT_TRACKING_HISTORY_LIMIT` | `100` | Default observations returned by the history endpoint |
| `SHOPBOT_API_KEY` | unset | When set, clients must send `X-API-Key` |
| `SHOPBOT_RATE_LIMIT_PER_MINUTE` | `60` | Per API key, or per client IP when no key |
| `SHOPBOT_OTEL_ENDPOINT` | unset | OTLP HTTP endpoint for per-stage spans. Needs `pip install ".[otel]"` |

## Multi-replica

The in-memory session store and cache are per process. For more than one replica use `SHOPBOT_SESSION_STORE=sqlite` on a shared volume (small deployments) or add a Redis cache backend (`pip install ".[redis]"` and wire `RedisBackend` in `ai_shopping_bot/api/wiring.py`). A Postgres `SessionStore` is a straightforward addition behind the same protocol.

## Observability

Logs are structured: event name plus a `fields` dict on each record. Point your log handler's formatter at `record.fields`. With `SHOPBOT_OTEL_ENDPOINT` set, each chat turn becomes a root span with one child span per pipeline stage, carrying `ms`, plus `llm_calls`, `from_cache`, and `data_count` on the root.

## Checklist before exposing publicly

- `SHOPBOT_API_KEY` set
- `SHOPBOT_LLM_MAX_CALLS_PER_REQUEST` reviewed against your provider budget
- Rate limit tuned
- TLS terminated in front (nginx, a cloud load balancer, or your platform's ingress)
- `.env` not in the image or the repo

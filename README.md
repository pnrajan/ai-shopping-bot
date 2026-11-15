# AI Shopping Bot

[![CI](https://github.com/pnrajan/ai-shopping-bot/actions/workflows/ci.yml/badge.svg)](https://github.com/pnrajan/ai-shopping-bot/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Ruff](https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json)](https://github.com/astral-sh/ruff)

A conversational shopping assistant API. Send a message, get back a reply plus structured product data. Follow-up turns that narrow results are filtered in memory with no new search. Comparisons return a side-by-side table.

Runs fully offline by default with a deterministic fake LLM and fake catalog. No keys needed to try it.

## Features

- **One LLM call to understand a turn.** Canonical query, filters, intent, and specialized intents (gift, essentials checklist, rationale) in a single structured response.
- **Refinement without re-searching.** "Which of these are under $300?" filters the products already shown.
- **Comparisons.** "X vs Y" fetches each product and returns a comparison table.
- **Multi-provider LLM routing.** OpenAI, SiliconFlow, and OpenRouter behind one client. Pick a model per role.
- **Per-request LLM budget.** Default 4 calls. The happy path uses 2. Overruns raise instead of silently continuing.
- **Pluggable state.** In-memory or SQLite sessions. In-memory or Redis cache with 24-hour TTL.
- **Price and availability tracking.** Every product seen becomes an observation. Watch an item, get alerts on price drops, target price, and stock changes, with a history endpoint per product.
- **Production basics.** API key auth, rate limiting, optional OpenTelemetry traces, Dockerfile.

## Quick start

Requires Python 3.11 or newer.

```bash
git clone https://github.com/pnrajan/ai-shopping-bot.git
cd ai-shopping-bot
bash scripts/setup.sh        # creates .venv, installs deps, copies .env.example to .env
bash scripts/run.sh          # serves on http://127.0.0.1:8000
```

In another terminal:

```bash
curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' -d '{
  "recent_turn": "gaming laptop under $1200",
  "history": [],
  "conversation_id": "demo"
}'
```

Refine in the same conversation:

```bash
curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' -d '{
  "recent_turn": "which of these are under $600?",
  "history": [],
  "conversation_id": "demo"
}'
```

Interactive docs at `http://localhost:8000/docs`. More examples in [`examples/`](examples/).

### Scripts

| Script | Purpose |
|---|---|
| `scripts/setup.sh [--dev]` | Create virtualenv, install dependencies, create `.env` if missing. Idempotent. |
| `scripts/run.sh [--dev] [--workers N]` | Launch the API. `--dev` enables auto-reload. Reads `.env`, environment wins. |
| `scripts/check.sh` | Run every CI check locally in the same order. |

## Configuration

All settings come from environment variables or `.env`. See [`.env.example`](.env.example) for the full list with defaults.

### Going live

Set `SHOPBOT_LLM=live` and choose a model per role. Model ids are `provider/model`.

| Provider | Example model id | Key variable |
|---|---|---|
| OpenAI | `openai/gpt-4o-mini` | `OPENAI_API_KEY` |
| SiliconFlow | `siliconflow/Qwen/Qwen3-8B` | `SILICONFLOW_API_KEY` |
| OpenRouter | `openrouter/anthropic/claude-haiku-5-5` | `OPENROUTER_API_KEY` |

Roles are `understanding`, `planning`, `response`, `enrich`. Mix providers freely:

```bash
SHOPBOT_LLM=live
SHOPBOT_MODELS__UNDERSTANDING=siliconflow/Qwen/Qwen3-8B
SHOPBOT_MODELS__RESPONSE=openrouter/anthropic/claude-haiku-5-5
```

For a real catalog set `SHOPBOT_CATALOG=unwrangle` and `UNWRANGLE_APIKEY`.

Keys are read from the environment only, held as secrets, and never logged. `.env` is gitignored.

### Auth and limits

Set `SHOPBOT_API_KEY` to require an `X-API-Key` header. `SHOPBOT_RATE_LIMIT_PER_MINUTE` applies per key, or per client IP when no key is set.

## API

### `POST /chat`

Request:

| Field | Type | Required | Notes |
|---|---|---|---|
| `recent_turn` | string | yes | Latest user message |
| `history` | array of `{role, content}` | no | Prior turns, oldest first |
| `conversation_id` | string | yes | Stable per conversation. Drives refinement and memory |

Response:

| Field | Type | Notes |
|---|---|---|
| `response` | string | Reply text |
| `data` | array | Products with `title`, `price`, `rating`, `brand`, `url`, `provider`, and more |
| `data_type` | string | `products`, `general`, or `clarification` |
| `data_count` | int | |
| `clarification_questions` | array or null | Set when `data_type` is `clarification` |
| `metadata` | object | `processing_time_ms`, `llm_calls`, `from_cache`, `plan`, per-stage timings |

### `GET /products/search?q=…&limit=10`

Direct catalog search with no LLM. Useful for checking a provider.

### Tracking: the availability DB

Every product returned by a provider is recorded as an observation (provider, id, price, stock, URL, originating query, time) and folded into a current-state table of tracked items. Enabled by default in memory; set `SHOPBOT_TRACKING=sqlite` to persist.

Three things use that table:

- **Enrichment.** Cached search results can be up to the cache TTL old. When a newer sighting exists for a cached product, its price, stock, and URL are overlaid before the result is returned. Metadata reports `enriched`. Turn off with `SHOPBOT_TRACKING_ENRICH_CACHED=false`.
- **Refresh.** `POST /tracking/refresh` re-checks tracked items not seen for `SHOPBOT_TRACKING_STALE_AFTER_S`, oldest first, up to `SHOPBOT_TRACKING_REFRESH_LIMIT` per pass. Watched items are always re-checked by `POST /watches/check`. Both run on a background loop when `SHOPBOT_TRACKING_MONITOR_INTERVAL_S` is set.
- **Alerts.** Consecutive observations are diffed: `price_drop`, `price_rise`, `back_in_stock`, `out_of_stock`, and `target_reached` for a watch with a target price.

| Endpoint | Purpose |
|---|---|
| `GET /tracking/status` | Item counts by availability, stale count, price range, watches, alerts, last update |
| `GET /tracking/items` | Current state, filterable by `in_stock`, `price_min`, `price_max`, `stale_after_s` |
| `GET /tracking/items/{provider}/{id}` | Current state of one product |
| `POST /tracking/items/bulk` | Current state for many ids or URLs in one call. URLs are normalized |
| `POST /tracking/refresh` | Re-check stale items now. Returns checked, updated, changed, alerts |
| `GET /products/{provider}/{id}/history` | Stats (current, min, max, avg price, availability ratio) plus observations and alerts |
| `POST /watches` · `GET /watches` · `DELETE /watches/{id}` | Watch a product with an optional `target_price` |
| `POST /watches/check` | Re-check every watch now. Returns new alerts |
| `GET /alerts` | Recent alerts |

### `GET /health`

Returns status and version.

## How it works

```
understand → refine → compare → plan → execute → respond → enrich → persist
```

Each stage is one class. A request context flows through them; any stage can mark the request done and the rest are skipped, except persist, which always runs.

| Stage | What it does |
|---|---|
| understand | One structured LLM call for query, filters, intent |
| refine | Filter products from the previous turn. Regex first, LLM only if regex misses |
| compare | For "X vs Y", search each and keep the best match |
| plan | Pattern table by intent. LLM planner only for unknown intents |
| execute | Run tool steps: `product_search`, `review_summarizer`, `research_product` |
| respond | One LLM call for the reply, or a template when budget is spent |
| enrich | Comparison table, essentials checklist, rationale |
| persist | Save turns and shown products |

Full design in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md).

## Project layout

```
ai_shopping_bot/
├── contracts/   # pure data models
├── llm/         # LLMClient (OpenAI-compatible, budgeted), FakeLLM, prompts
├── providers/   # CatalogProvider protocol, FakeProvider, UnWrangleProvider
├── search/      # handler, relevance, filters
├── tools/       # registry and tools
├── stages/      # one class per pipeline stage
├── session/     # SessionStore: in-memory and SQLite
├── cache/       # TTL cache: in-memory or Redis
├── tracking/    # price history, watches, alerts, availability monitor
├── api/         # app factory, wiring, auth, rate limit, tracing
├── pipeline.py
└── settings.py  # the only place model names and keys live
```

Layers import downward only, enforced by `import-linter`.

## Development

```bash
bash scripts/setup.sh --dev
source .venv/bin/activate
bash scripts/check.sh      # ruff, import-linter, vulture, repo checks, pytest with coverage
```

CI runs the same checks on Python 3.11, 3.12, and 3.13. See [CONTRIBUTING.md](CONTRIBUTING.md) for the code rules.

## Deployment

```bash
docker build -t ai-shopping-bot .
docker run --rm -p 8000:8000 --env-file .env ai-shopping-bot
```

[docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) covers the environment reference, multi-replica setup, and OpenTelemetry export. Call counts and latency baselines live in [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

## Roadmap

Each lands behind an optional extra with a before/after row in the benchmarks.

- [ ] Indexed hybrid search in front of the live provider
- [ ] Cross-encoder reranker
- [ ] Query expansion
- [ ] Second catalog provider

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). Participants are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE) © Pankaj Rajan

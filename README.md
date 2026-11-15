# Personal Shopper API

[![CI](https://github.com/pnrajan/personal-shopper/actions/workflows/ci.yml/badge.svg)](https://github.com/pnrajan/personal-shopper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)

A FastAPI shopping assistant. One `/chat` endpoint takes a user turn, understands it with a single LLM call, searches a product catalog, and replies with text plus structured product data. Follow-up turns that narrow the results ("which of these are under $300?") are filtered in memory without a new search. Comparisons ("X vs Y") fetch each product and return a table.

Runs fully offline by default with a deterministic fake LLM and fake catalog, so you can try it with no keys.

## Quick start

```bash
git clone https://github.com/pnrajan/personal-shopper.git
cd personal-shopper
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
python main.py
```

```bash
curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' -d '{
  "recent_turn": "gaming laptop under $1200",
  "history": [],
  "conversation_id": "demo"
}'
```

Then refine in the same conversation:

```bash
curl -s -X POST localhost:8000/chat -H 'Content-Type: application/json' -d '{
  "recent_turn": "which of these are under $600?",
  "history": [],
  "conversation_id": "demo"
}'
```

Interactive docs at `http://localhost:8000/docs`.

## Going live

Copy `.env.example` to `.env`. Set `SHOPPER_LLM=live` and pick models per role. Each model id is `provider/model`.

| Provider | Model id example | Key variable |
|---|---|---|
| OpenAI | `openai/gpt-4o-mini` | `OPENAI_API_KEY` |
| SiliconFlow | `siliconflow/Qwen/Qwen3-8B` | `SILICONFLOW_API_KEY` |
| OpenRouter | `openrouter/anthropic/claude-haiku-5-5` | `OPENROUTER_API_KEY` |

Roles are `understanding`, `planning`, `response`, `enrich`. Mix providers freely, for example a cheap SiliconFlow model for understanding and a stronger OpenRouter model for the reply:

```bash
SHOPPER_LLM=live
SHOPPER_MODELS__UNDERSTANDING=siliconflow/Qwen/Qwen3-8B
SHOPPER_MODELS__RESPONSE=openrouter/anthropic/claude-haiku-5-5
```

SiliconFlow calls disable hidden reasoning (`enable_thinking=false`). OpenRouter calls send `reasoning.enabled=false` and retry without it if the model insists on reasoning.

For a real catalog set `SHOPPER_CATALOG=unwrangle` and `UNWRANGLE_APIKEY`. Keys are read from the environment only and never logged.

## API

### `POST /chat`

| Field | Type | Required | Notes |
|---|---|---|---|
| `recent_turn` | string | yes | Latest user message |
| `history` | array of `{role, content}` | no | Prior turns, oldest first. `role` is `user` or `assistant` |
| `conversation_id` | string | yes | Stable per conversation. Drives refinement and session memory |

Response:

| Field | Type | Notes |
|---|---|---|
| `response` | string | Reply text |
| `data` | array | Products, each with `title`, `price`, `rating`, `brand`, `url`, `provider`, and more |
| `data_type` | string | `products`, `general`, or `clarification` |
| `data_count` | int | |
| `clarification_questions` | array or null | Set when `data_type` is `clarification` |
| `metadata` | object | `processing_time_ms`, `llm_calls`, `from_cache`, `plan`, per-stage timings |

### `GET /products/search?q=…&limit=10`

Direct catalog search without the LLM. Useful for checking a provider.

### `GET /health`

### Auth and limits

Set `SHOPPER_API_KEY` to require an `X-API-Key` header. `SHOPPER_RATE_LIMIT_PER_MINUTE` applies per key, or per client IP when no key is set.

## How a turn flows

```
understand → refine → compare → plan → execute → respond → enrich → persist
```

- **understand**: one structured LLM call. Canonical query, attributes, search queries, intent, and specialized intents (gift, essentials checklist, rationale). Asks a clarifying question only when nothing is searchable, and at most once per conversation.
- **refine**: if the session holds products and the turn narrows them, filter and return. Regex first, LLM only when regex misses.
- **compare**: for comparison intent, search each named product and keep the best match of each.
- **plan**: pattern table by intent. LLM planner only for unknown intents.
- **execute**: run tool steps. Tools: `product_search`, `review_summarizer`, `research_product`.
- **respond**: one LLM call to write the reply, or a template when budget is spent.
- **enrich**: comparison table, essentials checklist, rationale, each toggleable.
- **persist**: save turns and shown products for the next turn.

Every request has an LLM budget (default 4 calls). The happy path uses 2. Exceeding the budget raises instead of silently continuing.

Design rationale and the rules the code follows are in [docs/ENGINEERING_PLAN.md](docs/ENGINEERING_PLAN.md). Target architecture is in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md). [docs/PORTING_PLAN.md](docs/PORTING_PLAN.md) records what was carried over from the author's larger Search Hub codebase.

## Development

```bash
pip install -e ".[dev]"
ruff check . && ruff format --check .
lint-imports                      # layer contract
vulture shopper --min-confidence 80
bash scripts/check_root_clutter.sh
bash scripts/check_model_names.sh
pytest --cov=shopper --cov-fail-under=80
```

CI runs all of the above on Python 3.11, 3.12, and 3.13.

### Layout

```
shopper/
├── contracts/   # pure data: chat, product, understanding, plan, tools, context
├── llm/         # LLMClient (OpenAI-compatible, budgeted), FakeLLM, prompts
├── providers/   # CatalogProvider protocol, FakeProvider, UnWrangleProvider
├── search/      # handler, relevance, filters
├── tools/       # registry and three tools
├── stages/      # one class per pipeline stage
├── session/     # SessionStore: in-memory and SQLite
├── cache/       # normalized-key TTL cache, in-memory or Redis
├── api/         # app factory, wiring, auth and rate limit
├── pipeline.py
└── settings.py  # the only place model names and keys live
```

Layers import downward only, checked by `import-linter`.

## Deploy

```bash
docker build -t personal-shopper . && docker run --rm -p 8000:8000 --env-file .env personal-shopper
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for environment reference, multi-replica notes, and the OpenTelemetry export (`pip install ".[otel]"`, set `SHOPPER_OTEL_ENDPOINT`). Measurements live in [docs/BENCHMARKS.md](docs/BENCHMARKS.md).

## Roadmap

Behind optional extras, each landing only with a before/after measurement:

- [ ] Indexed hybrid search in front of the live provider
- [ ] Cross-encoder reranker
- [ ] Query expansion
- [ ] Second catalog provider

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All participants are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE) © Pankaj Rajan

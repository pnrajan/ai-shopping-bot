# Personal Shopper API

[![CI](https://github.com/pankajrajan/personal-shopper/actions/workflows/ci.yml/badge.svg)](https://github.com/pankajrajan/personal-shopper/actions/workflows/ci.yml)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.10+](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/)

A FastAPI service that exposes a chat endpoint for a personal shopping assistant. Clients send the user's latest message, the conversation history, and a session ID. The service validates the payload and returns a structured response.

> **Status: early skeleton.** The `/chat` endpoint currently validates and echoes requests. AI responses, product search, and storage are not implemented yet. See [Roadmap](#roadmap).

## Features

- `POST /chat` endpoint with Pydantic request validation
- Stateless design: all context travels in the request, so instances scale horizontally
- Auto-generated OpenAPI docs at `/docs` and `/redoc`
- Test suite, linting, and CI configured out of the box

## Requirements

- Python 3.10 or newer
- pip

## Quick Start

```bash
git clone https://github.com/pankajrajan/personal-shopper.git
cd personal-shopper

python -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate

pip install -r requirements.txt
python main.py
```

The server listens on `http://localhost:8000`. Interactive docs are at `http://localhost:8000/docs`.

For hot reload during development:

```bash
uvicorn main:app --reload
```

## API

### `POST /chat`

Request body:

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| `recent_turn` | string | Yes | The user's latest message |
| `history` | array of objects | Yes | Prior turns. Each object is free-form, typically `{"role": ..., "message": ...}` |
| `conversation_id` | string | Yes | Stable identifier for the session |

Response body:

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | Acknowledgement text |
| `conversation_id` | string | Echo of the request's session ID |
| `recent_turn` | string | Echo of the user's message |
| `history_length` | integer | Number of prior turns received |

Validation failures return `422 Unprocessable Entity` with FastAPI's standard error body.

### Example

```bash
curl -X POST http://localhost:8000/chat \
  -H "Content-Type: application/json" \
  -d '{
    "recent_turn": "I need a laptop for video editing under $1500",
    "history": [
      {"role": "user", "message": "Hello"},
      {"role": "assistant", "message": "Hi! How can I help you shop today?"}
    ],
    "conversation_id": "session-123"
  }'
```

```json
{
  "message": "Chat request received",
  "conversation_id": "session-123",
  "recent_turn": "I need a laptop for video editing under $1500",
  "history_length": 2
}
```

More examples live in [`examples/`](./examples/):

- [`curl_examples.sh`](./examples/curl_examples.sh) - shell script with curl requests
- [`python_client.py`](./examples/python_client.py) - Python client with multi-turn history

## Development

```bash
pip install -r requirements-dev.txt
ruff check .
pytest
```

CI runs the same two commands on Python 3.10, 3.12, and 3.13 for every push and pull request.

### Project layout

```
personal-shopper/
├── .github/workflows/ci.yml   # Lint + tests
├── docs/                      # Architecture and porting plan
├── examples/                  # Runnable client examples
├── tests/                     # pytest suite
├── main.py                    # FastAPI application
├── pyproject.toml             # Metadata, ruff and pytest config
├── requirements.txt           # Runtime dependencies
└── requirements-dev.txt       # Dev dependencies
```

### Dependencies

| Package | Minimum | Purpose |
|---------|---------|---------|
| fastapi | 0.163 | Web framework |
| uvicorn | 0.54 | ASGI server |
| pydantic | 2.14 | Request validation |
| pytest | 9.2 | Tests (dev) |
| httpx2 | 2.16 | Test client transport (dev) |
| ruff | 0.17 | Lint and import sorting (dev) |

## Troubleshooting

**Port 8000 in use.** Pick another port:

```bash
uvicorn main:app --port 8001
```

**`ModuleNotFoundError`.** Activate the virtual environment and reinstall dependencies.

**`python` not found.** Use `python3` on systems where `python` is not aliased.

## Design

The target architecture is written up in [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md), [docs/PORTING_PLAN.md](docs/PORTING_PLAN.md) lists what comes over from the author's larger Search Hub codebase, in what order, and what stays behind. [docs/ENGINEERING_PLAN.md](docs/ENGINEERING_PLAN.md) sets the package layout, core interfaces, phased milestones, and the CI guardrails that keep the codebase from growing the problems the reference did. In short: one query-understanding call, a refinement filter over products already shown, a small planner and executor over shopping tools, and a 24-hour semantic cache in front of catalog providers. The guiding rule is to show results fast and let the user refine, asking a clarifying question only when there is nothing to search for.

## Roadmap

Ordered to match the architecture doc. Discussion and progress tracking happen in GitHub Issues.

- [ ] Query understanding: one structured LLM call producing canonical query, attributes, search queries, and specialized intents (gift, essentials checklist, rationale)
- [ ] Response model with `data`, `data_type`, `data_count`, and `clarification_questions`
- [ ] `product_search` tool against a first catalog provider
- [ ] Planner pattern table (shopping, comparison, browse) with LLM planner fallback
- [ ] Sequential executor with per-step results and stop-on-error
- [ ] Session storage keyed by `conversation_id`, holding turns and last shown products
- [ ] Refinement filter: narrow stored products on price or feature instead of re-searching
- [ ] 24-hour semantic cache (Redis when available, in-memory otherwise)
- [ ] Comparison table, essentials checklist, and product rationale enrichments
- [ ] `review_summarizer` and `research_product` tools
- [ ] Authentication, rate limiting, and observability

## Contributing

See [CONTRIBUTING.md](CONTRIBUTING.md). All participants are expected to follow the [Code of Conduct](CODE_OF_CONDUCT.md).

## License

[MIT](LICENSE) © Pankaj Rajan

---
layout: default
title: AI Shopping Bot
---

A conversational shopping assistant API. Send a message, get back a reply plus structured product data. Follow-up turns that narrow results are filtered in memory with no new search. Comparisons return a side-by-side table.

Runs fully offline by default with a deterministic fake LLM and fake catalog. No keys needed to try it.

## Features

- **One LLM call to understand a turn.** Canonical query, filters, intent, and specialized intents (gift, essentials checklist, rationale) in a single structured response.
- **Refinement without re-searching.** "Which of these are under $300?" filters the products already shown.
- **Comparisons.** "X vs Y" fetches each product and returns a comparison table.
- **Multi-provider LLM routing.** OpenAI, SiliconFlow, and OpenRouter behind one client. Pick a model per role.
- **Per-request LLM budget.** Default 4 calls. The happy path uses 2. Overruns raise instead of silently continuing.
- **Pluggable state.** In-memory or SQLite sessions. In-memory or Redis cache with 24-hour TTL.
- **Production basics.** API key auth, rate limiting, optional OpenTelemetry traces, Dockerfile.

## Quick start

Requires Python 3.11 or newer.

```bash
git clone https://github.com/pnrajan/ai-shopping-bot.git
cd ai-shopping-bot
bash scripts/setup.sh        # creates .venv, installs deps, copies .env.example to .env
bash scripts/run.sh          # serves on http://127.0.0.1:8000
```

Ask for something:

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

Interactive OpenAPI docs are served at `http://localhost:8000/docs` once the server is running.

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

## Documentation

- [Architecture](ARCHITECTURE.md). Pipeline design, stages, layering rules.
- [Deployment](DEPLOYMENT.md). Environment reference, multi-replica setup, OpenTelemetry export.
- [Benchmarks](BENCHMARKS.md). LLM call counts and latency baselines.
- [Contributing](https://github.com/pnrajan/ai-shopping-bot/blob/main/CONTRIBUTING.md). Code rules and workflow.

## Links

- [Source on GitHub](https://github.com/pnrajan/ai-shopping-bot)
- [CI status](https://github.com/pnrajan/ai-shopping-bot/actions/workflows/ci.yml)
- [License: MIT](https://github.com/pnrajan/ai-shopping-bot/blob/main/LICENSE)

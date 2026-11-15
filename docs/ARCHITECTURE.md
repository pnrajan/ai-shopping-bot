# Architecture

This document describes the design of Personal Shopper Agent. As of commit `38cbbbe` the pipeline below is implemented under `shopper/`; the indexed catalog, reranker, and query expansion remain roadmap items behind optional extras.

## Guiding principle

**Show results fast, refine later.** Users prefer browsing to interrogation. If a query names a product type plus any one attribute (budget, color, brand, use case), search immediately and let the user narrow results in the next turn. Ask a clarifying question only when there is literally nothing to search for, and never more than once per conversation.

## Request lifecycle

```
POST /chat
   │
   ▼
1. Validate (Pydantic)                 recent_turn, history, conversation_id
   │
   ▼
2. Query Understanding (1 LLM call)    canonical query, category, attributes,
   │                                   search queries, specialized intents,
   │                                   should-ask-followup flag
   ▼
3. Refinement check                    If the session already holds products and
   │                                   the turn narrows them ("under $50",
   │                                   "which of these has USB-C"), filter the
   │                                   stored list and return. No new search.
   ▼
4. Comparison check                    "X vs Y" → search each product name
   │                                   separately, take the best match of each.
   ▼
5. Plan                                Pick a tool sequence for the intent
   │                                   (pattern table first, LLM planner as
   │                                   fallback).
   ▼
6. Execute                             Run each tool step in order. Stop on a
   │                                   failed required step.
   ▼
7. Generate response                   Turn tool output into a conversational
   │                                   reply plus structured product data.
   ▼
8. Enrich                              Comparison table, essentials checklist,
   │                                   or "why these match" rationale, driven by
   │                                   the specialized intents from step 2.
   ▼
9. Store products in session           Enables step 3 on the next turn.
   │
   ▼
Response
```

## Components

### Query Understanding

A single structured LLM call that produces every signal downstream steps need. One call, not several, keeps latency predictable.

| Field | Purpose |
|-------|---------|
| `CanonicalQuery` | Cleaned, spelling-corrected form of the user's ask |
| `Category`, `SubCategory` | Product taxonomy hint for providers |
| `Attributes` | Key/value filters: budget, color, brand, size, rating minimum |
| `SearchQueries` | One or more provider-ready query strings |
| `ShouldIAskFollowup` | True only when nothing is searchable |
| `IsContinuation` | Whether this turn depends on prior turns |
| `SpecializedIntents` | See below |

Specialized intents detected in the same call:

- **gift_shopping**. Extracts recipient. Needs clarification only if neither the query nor history reveals the recipient's interests. Clarifying question templates: "What does your {recipient} like or enjoy?"
- **essentials_checklist**. Fires for "what do I need for X" where X is a known topic (camping, travel, home office, baby, college, moving, kitchen, workout, pet care). Generates a prioritized must-have / nice-to-have list.
- **product_rationale**. Fires when the user asks why or asks for recommendations with criteria. Appends a short explanation of how results match the stated criteria.

### Refinement filter

Runs before any search when the session holds products from a previous turn. Hybrid detection:

1. Regex runs first and catches the common patterns with no LLM call:
   - price: `under|less than|below|cheaper than|no more than $N`, `over|at least|above $N`
   - pointer words: `from those`, `which one`, `show me the ...`
   - filter words: `narrow down`, `filter by`, `only the`, `just the ones`
2. LLM extracts `price_max`, `price_min`, `features` only when regex misses, the
   understanding call marked the turn as a continuation, and budget remains.

Filtered results return with a one-line explanation of the filter applied. A filter that matches nothing says so rather than running a new search.

### Planner

Maps intent to an ordered list of tool steps. A static pattern table covers the common cases without an LLM call:

| Intent | Steps |
|--------|-------|
| shopping | `product_search(limit=10)` → `review_summarizer` |
| comparison | `product_search(limit=5)` → `review_summarizer(query="comparison")` |
| browse | `product_search(limit=15)` |
| fallback | `product_search` |

An LLM planner with a strict JSON schema (`persona`, `steps[tool, inputs]`, `needs_clarification`, `questions`) handles anything the table misses.

### Executor

Runs plan steps sequentially. Each step receives the query understanding result and recent turns. A failed required step halts the plan. Output is an `ExecutionResponse` with per-step results, timing, and the plan's reasoning.

### Tools

Each tool takes a `ToolInput` (query understanding result, recent turns, tool params) and returns a `ToolOutput` (success, data, metadata, error).

| Tool | What it does |
|------|--------------|
| `product_search` | Thin wrapper over the search handler. Passes search queries, category, attributes, and limit. |
| `review_summarizer` | LLM summary of reviews for a named product: summary, key points, sentiment, confidence. |
| `research_product` | LLM research brief: key features, pros and cons, recommendation. |

### Product search handler

Shared by the chat tool and any direct REST endpoint, so business logic lives in one place.

Implemented today:

1. Run each search query against the catalog provider in parallel (thread pool).
2. Dedupe by product id, falling back to URL, then lowercased title.
3. Score lexical relevance of each result against the canonical query.
4. Apply price, rating, and brand filters from attributes. A filter that would
   empty the list is skipped and the previous list kept.
5. Sort by relevance, truncate to the requested limit.

Results are cached under a normalized key (lowercased query, sorted attributes,
limit) for 24 hours, in Redis when `[redis]` is installed and configured, in
memory otherwise.

Roadmap, each gated on a row in `docs/BENCHMARKS.md`: indexed hybrid search in
front of the live provider, cross-encoder reranker, query expansion.

### Product schema

The structured item returned alongside the conversational reply.

| Field | Type | Notes |
|-------|------|-------|
| `id` | string | Provider's product ID |
| `title` | string | Required |
| `price` | string | Formatted with currency |
| `currency`, `currency_symbol` | string | Default USD, `$` |
| `rating` | float, optional | |
| `total_ratings` | int, optional | |
| `brand` | string | |
| `url` | string | Product page |
| `provider` | string | Which catalog it came from |
| `description` | string | |
| `category` | string | |
| `thumbnail` | string, optional | Image URL |
| `in_stock` | bool, optional | |
| `model_no` | string | |

### Session storage

Per `conversation_id`, keep the last turns, the last product list shown, and a count of clarifications asked. The product list powers refinement; the counter enforces at most one clarification per conversation. `SessionStore` is a small protocol with two backends: in-memory (default) and SQLite (`SHOPPER_SESSION_STORE=sqlite`). Multi-replica deployments need a shared backend; see `docs/DEPLOYMENT.md`.

### Response shape (target)

```json
{
  "success": true,
  "response": "Here are five laptops for video editing under $1500...",
  "conversation_id": "session-123",
  "data": [ { "title": "...", "price": "$1,299.00", "...": "..." } ],
  "data_type": "products",
  "data_count": 5,
  "clarification_questions": null,
  "metadata": {
    "processing_time_ms": 1840,
    "from_cache": false,
    "plan": ["product_search", "review_summarizer"]
  }
}
```

This is the shape `/chat` returns today. `data_type` tells a client how to render `data`: product cards for `products`, plain text for `general`.

## Scope

Personal Shopper Agent is a single persona. There is no routing between assistants, no UI, and no scraping provider in the default install. If a second persona ever appears it is a second pipeline, not a router.

## Implementation status

Items 1 through 9 of the original order are implemented (commit `38cbbbe`):
query understanding, `product_search` against UnWrangle, planner table and
executor, response generation, session storage and refinement, 24-hour cache,
enrichments, review and research tools, auth, rate limiting, and tracing.

Remaining roadmap items live in the README and `docs/BENCHMARKS.md`.

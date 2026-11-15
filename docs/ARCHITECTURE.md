# Architecture

This document describes the design of Personal Shopper, distilled from the shopper persona in the author's larger Search Hub platform (`pi-user-personas`) and reduced to the pieces a standalone shopping assistant needs. As of commit `38cbbbe` the pipeline below is implemented under `shopper/`; the indexed catalog, reranker, and query expansion remain roadmap items behind optional extras.

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

1. LLM extracts `price_max`, `price_min`, `features` from the query.
2. Regex fallback catches the common patterns if the LLM is unavailable:
   - price: `under|less than|below|cheaper than|no more than $N`
   - pointer words: `from those`, `which one`, `show me the ...`
   - filter words: `narrow down`, `filter by`, `only the`, `just the ones`

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

1. Expand the query lightly (synonyms, spelling).
2. Query the indexed catalog first (hybrid BM25 + vector, target under 50 ms).
3. Score relevance of results against the query and attributes.
4. If average relevance is low, fall back to a live catalog API (2 to 3 s).
5. Rerank with a cross-encoder.
6. Apply price, rating, category, and product-type filters from attributes.
7. Enrich prices from an availability store where present.

Results are cached with a semantic key (similarity threshold 0.98) for 24 hours, in Redis when available and in memory otherwise.

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

Per `conversation_id`, keep the last turns and the last product list shown. The product list powers refinement. Storage is a key-value abstraction with pluggable backends: on-disk for local development, a shared document store for multi-replica deployments.

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

## What the reference does that this project leaves out

The reference platform routes between many personas (shopper, researcher, reminders, tasks, news, events, weather) with a persona router, multi-persona synthesis, a Streamlit UI, nginx, Docker, Redis, MongoDB, and a separate knowledge base service. Personal Shopper keeps only the shopper path. Anything that exists to arbitrate between personas or to serve non-shopping intents is out of scope.

## Implementation order

Matches the README roadmap.

1. Query understanding call and request/response models
2. `product_search` tool against one catalog provider
3. Planner pattern table and sequential executor
4. Response generator producing `data` + `response`
5. Session storage and refinement filter
6. 24-hour semantic cache
7. Comparison, essentials, and rationale enrichments
8. Review summarizer and product research tools
9. Auth, rate limiting, observability

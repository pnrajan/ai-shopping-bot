# Benchmarks

Every change that adds latency, an LLM call, or a dependency gets a row here. Numbers without a
method are not numbers.

## Method

Local machine, fake LLM and fake catalog unless stated. `processing_time_ms` from the response
metadata, median of 20 requests. LLM call counts from `metadata.llm_calls`, asserted in tests.

## Baseline, 2026-11-14, commit `4d92d4e`

| Scenario | LLM calls | Provider calls | p50 ms (fake) |
|---|---:|---:|---:|
| Search: "gaming laptop under $1200" | 2 | 1 | < 1 |
| Refinement: "which of these are under $600?" | 1 | 0 | < 1 |
| Repeat search (cache hit) | 2 | 0 | < 1 |
| Comparison: "sony wh-1000xm5 vs bose qc45" | 3 | 2 | < 1 |
| Clarification: "I want to buy something" | 1 | 0 | < 1 |
| Essentials + rationale | 4 | 1 | < 1 |

## Tracking, 2026-11-15

`AvailabilityStore.record` runs once per cache miss on the 10 products a search returns. Median
of 20 calls, same machine and method as above.

| Store | Added per search (ms) | Notes |
|---|---:|---|
| `memory` (default) | < 0.1 | Bounded list per product |
| `sqlite` | 6 | One insert per product plus a lookup of the previous row; shares the session DB file |

Cache hits add nothing. The monitor runs off the request path.

Pipeline overhead is negligible. Live latency is dominated by provider and model round trips.
Record live numbers per provider here when a key is available, with model ids and region.

## Pending

| Change | Expected cost | Expected benefit | Status |
|---|---|---|---|
| Indexed hybrid search | +1 dependency group, index build | Sub-50 ms search on indexed catalog | Not started |
| Cross-encoder reranker | +200 to 500 ms CPU | Better top-3 relevance | Not started |
| Query expansion | +0 or +1 LLM call | Higher recall on vague queries | Not started |

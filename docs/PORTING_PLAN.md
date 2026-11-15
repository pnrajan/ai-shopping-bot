# Porting Plan

What to bring over from the Search Hub platform (`pi-user-personas`) to turn this skeleton into a working shopping assistant. Scope is the shopper path only. Anything that exists to route between personas or serve non-shopping intents stays behind.

Line counts and dependency notes are from the reference repo as of 2026-11-14.

## Summary

| Tier | What | Lines | Effort | Port as-is or rewrite |
|------|------|------:|--------|-----------------------|
| 1 | Contracts and pure logic | ~1,500 | Days | Copy, trim imports |
| 2 | Planner, executor, tools | ~1,400 | Days | Copy, remove persona abstraction |
| 3 | Query understanding and LLM layer | ~1,400 | 1 week | Copy, swap LLM client |
| 4 | Product search handler and providers | ~6,000 | 2 to 3 weeks | Rewrite smaller |
| 5 | Session state and cache | ~1,600 | 1 week | Copy, simplify backends |
| 6 | Response generation and enrichments | ~2,800 | 1 to 2 weeks | Rewrite smaller |

Not ported: persona router, orchestrator, multi-persona synthesis, Streamlit UI, nginx, Docker, KBService, MongoDB layer, safety guard, news/events/weather/time providers, task and reminder personas.

## Tier 1. Contracts and pure logic

Zero or near-zero internal coupling. Copy first, build everything else on top.

| Source file | Lines | Internal imports | Third-party | Action |
|-------------|------:|-----------------:|-------------|--------|
| `core/schemas/products.py` | 152 | 1 | pydantic | Copy. This is the `Product` model. |
| `core/tools/tools_io.py` | 232 | 2 | none | Copy. `ToolInput` / `ToolOutput` contract. |
| `core/tools/tool_registry.py` | 192 | 0 | none | Copy. `@register_tool` decorator and `ToolSpec`. |
| `core/personas/shopper_config.py` | 15 | 0 | none | Copy. Two thresholds and planner rules string. |
| `core/personas/configs/shopper_config.yaml` | 186 | 0 | none | Copy. Gift, essentials, rationale intent config and prompt fragments. |
| `core/planner/persona_plans.json` | 133 | 0 | none | Copy only the `shopper` block. |
| `core/classifier/comparison_classifier.py` | 119 | 0 | none | Copy. Regex comparison detection and product name extraction. |
| `core/personas/shopper_product_filter.py` | 389 | 2 | none | Copy. Refinement detection, price and feature filters. Swap `call_llm` import. |
| `core/caching/decorators.py` | 350 | 0 | none | Copy. Semantic cache decorator with in-memory backend. |
| `core/schemas/conversation.py` | 343 | low | none | Copy. `Turn` and history helpers. |

## Tier 2. Planner, executor, tools

Clean modules whose internal imports are mostly Tier 1 or each other.

| Source file | Lines | Internal imports | Third-party | Action |
|-------------|------:|-----------------:|-------------|--------|
| `core/executor/executor.py` | 297 | 6 | none | Copy. Sequential step runner with stop-on-error. |
| `core/planner/planner.py` | 427 | 7 | none | Copy. Pattern table lookup plus LLM fallback. Drop multi-persona scoring. |
| `core/planner/llm_planner.py` | 148 | 3 | none | Copy. Strict JSON schema planner. |
| `core/planner/heuristic_planner.py` | 264 | 6 | none | Optional. Rule-based fast path. |
| `core/tools/shopping_tools.py` | 392 | 4 | none | Copy. `product_search`, `review_summarizer`, `research_product`. |
| `core/personas/persona_planner_executor.py` | 373 | 11 | none | Collapse into a single `ShoppingPipeline` class. The persona wrapper layer is not needed here. |
| `core/personas/shopper_persona.py` | 607 | 13 | none | Do not copy wholesale. Extract `handle_request` body into the pipeline: refinement check, comparison branch, product storage, enrichment hooks. Drop `can_handle` and persona registration. |

## Tier 3. Query understanding and LLM layer

One structured LLM call that feeds everything else. Heavier third-party surface.

| Source file | Lines | Internal imports | Third-party | Action |
|-------------|------:|-----------------:|-------------|--------|
| `core/utils/llm/query_understanding/query_understanding.py` | 852 | 8 | yaml, retrying | Copy dataclass and prompt. Remove `SuggestedPersonas` and `PersonaConfidence`. Keep `SpecializedIntents`. |
| `core/utils/llm/llm_utils.py` | 503 | 5 | litellm, openai, tiktoken, tenacity, cachetools | Copy `call_llm` and `LLMProxyAdaptor`. Decide one client: `litellm` keeps provider flexibility, direct `openai` is lighter. |
| `core/utils/llm/prompt_templates.py` | 378 | low | none | Copy. Role definition and section helpers used by shopper prompts. |
| `core/utils/message_template_manager.py` | 282 | low | yaml | Copy. User-facing message strings for filter results. |
| `core/personas/shopper_helpers.py` | 271 | 2 | litellm, yaml | Copy. Essentials checklist and rationale generators. |

## Tier 4. Product search handler and providers

Largest and most coupled part. The reference handler is 4,036 lines and pulls in spaCy, NLTK, WordNet, a spell checker, and a reranker. Rewrite a smaller version, then add pieces back as measurements justify.

| Source file | Lines | Third-party | Action |
|-------------|------:|-------------|--------|
| `core/handlers/product_search_handler.py` | 4,036 | cachetools, nltk, spellchecker, yaml, spacy (via utils) | Rewrite at roughly 400 lines: expand query, call provider, score relevance, apply attribute filters, return `Product` list. Skip WordNet synonym expansion, gender filtering, and spaCy noun extraction in v1. |
| `core/providers/provider_response.py` | 510 | none | Copy. `ProductInfo` dataclass and `ProviderResults`. |
| `core/providers/product_providers.py` | 881 | requests, dataclasses_json | Copy `BaseProductCatalogProvider` and `UnWrangleCatalogProvider`. Drop commerce-partner routing. Needs `UNWRANGLE_APIKEY`. |
| `core/providers/serp_provider.py` | 594 | requests | Optional second provider. Google Shopping via SerpAPI. Needs `SERPAPI_KEY`. |
| `core/providers/searchdb_provider.py` + `infrastructure/storage/searchdb.py` | 2,084 | lancedb, pyarrow, numpy, sentence_transformers, model2vec, openai | Defer. Indexed hybrid search is a latency optimization that needs a populated index. Add after a live provider works. |
| `core/providers/reranker.py` | 403 | flashrank, sentence_transformers | Defer. Cross-encoder reranking. Measure relevance first. |
| `core/services/price_filter.py` | 875 | none | Copy price and rating filter functions only. |
| `core/services/lightweight_query_expander.py` | 879 | cachetools, nltk, litellm | Defer. Start with no expansion. |
| `core/utils/category_mapping.py` | 676 | yaml | Copy if UnWrangle category mapping is needed. Otherwise defer. |
| `core/utils/product_filters.py` | 736 | ftfy, spacy, yaml | Defer. |
| `core/utils/nlp_enhancements.py` | 1,040 | spacy, nltk, model2vec, ftfy | Defer. |
| `core/providers/amz_scraper.py`, `merchant_scraper.py`, `google_shopping_scraper.py` | 1,897 | requests, Oxylabs creds | Do not port. Scraping has terms-of-service and maintenance costs an open-source repo should not carry by default. |

## Tier 5. Session state and cache

| Source file | Lines | Third-party | Action |
|-------------|------:|-------------|--------|
| `core/conversation/conversation_state_manager.py` | 856 | none | Copy `get_entities` / `update_entities` and turn storage. Back with an in-memory dict first, then SQLite. Drop MongoDB and Mongita backends. |
| `infrastructure/cache/cache_decorator.py` | 387 | none | Copy. Unified cache decorator with TTL. |
| `core/caching/backends/` | varies | redis | Copy in-memory semantic backend. Add Redis as optional extra. |

## Tier 6. Response generation and enrichments

| Source file | Lines | Action |
|-------------|------:|--------|
| `core/response/response_generator.py` | 2,593 | Rewrite at roughly 200 lines. Only the shopping branch is needed: turn `ExecutionResponse` into reply text plus `data` list. |
| `core/response/comparison_helper.py` | 127 | Copy. Structured product comparison table. |
| `core/personas/persona_response.py` | 140 | Copy `RichDataItem`. Rename `PersonaResponse` to `ShoppingResponse` or merge into the API response model. |
| `core/api/models.py` | 524 | Copy `ChatResponse` fields: `response`, `data`, `data_type`, `data_count`, `clarification_questions`, `metadata`. Drop `persona_id` and `safety`. |

## Order of work

Each step leaves the test suite green and the endpoint callable.

1. **Contracts.** Tier 1 files into `shopper/` package. Update `/chat` response model to the Tier 6 `ChatResponse` shape, still echoing.
2. **One provider.** `ProductInfo`, `ProviderResults`, `UnWrangleCatalogProvider`. Direct `POST /products/search` endpoint for testing providers in isolation.
3. **Minimal handler.** 400-line `ProductSearchHandler`: provider call, relevance score, price and rating filter.
4. **LLM layer.** `call_llm`, prompt templates, `QueryUnderstanding`. `/chat` now runs query understanding and calls the handler.
5. **Planner and executor.** Pattern table, executor, three shopping tools. `/chat` goes through the pipeline.
6. **Response generator.** Reply text plus structured `data`.
7. **Session and refinement.** State manager, product storage per conversation, `shopper_product_filter`.
8. **Cache.** Semantic cache decorator on the handler, 24-hour TTL.
9. **Enrichments.** Comparison detection and table, essentials checklist, rationale.
10. **Optional depth.** SearchDB index, reranker, query expansion, SerpAPI, each behind a setting and measured.

## Dependencies this adds

Core path after step 9:

```
litellm or openai      LLM calls
pyyaml                 intent config and message templates
requests               provider HTTP
cachetools             LRU for cache decorator
tenacity               LLM retry
```

Deferred extras, each as an optional dependency group:

```
[index]    lancedb, pyarrow, sentence-transformers, model2vec
[rerank]   flashrank
[nlp]      spacy, nltk, pyspellchecker, ftfy
[redis]    redis
```

## Cleanups to do while porting

- Strip emoji and `🔍🔍🔍` debug logging from `shopper_persona.py` and `persona_planner_executor.py`. Use structured log fields.
- Remove dead code: `_detect_ambiguous_query_llm` in the persona is superseded by query understanding's `ShouldIAskFollowup`.
- Replace `'resp' not in locals()` control flow in the comparison branch with an explicit `Optional` variable.
- Move module-level Redis connection probing out of import time and into app startup.
- Make `conversation_id` required in the request, matching this repo's existing contract, instead of auto-generating session IDs.
- Every ported file gets a test before the next tier starts. The reference repo's `tests/unit` has coverage for `shopper_product_filter`, `comparison_classifier`, and `executor` that can come along.

## Licensing note

The reference repository has no LICENSE file. It is the same author's private code, so relicensing the ported parts under this repo's MIT license is the author's call to make. Record that decision in the first porting commit message.

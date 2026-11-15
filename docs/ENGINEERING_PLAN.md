# Engineering Plan

How Personal Shopper gets built so it does not grow the problems the reference codebase grew. Each rule below traces to a specific lesson from `pi-user-personas`. The rules are enforced by structure, lint, and CI, not by memory.

Companion documents: [ARCHITECTURE.md](ARCHITECTURE.md) says what the system does. [PORTING_PLAN.md](PORTING_PLAN.md) says which reference files inform which modules. This document says how the work is organized and what "done" means at each stage.

## Part 1. Lessons and the rules they produce

| Lesson from reference | Rule here | Enforced by |
|---|---|---|
| `handle_request` reached 361 lines doing six jobs | A request is a sequence of stages. Each stage is one class with one `run(ctx)` method under 80 lines. | ruff `PLR0915` (max statements), `C901` (complexity 10) |
| Search handler reached 4,036 lines with duplicated NLP helpers | One module per concern. Hard cap 500 lines per file. Duplicate logic is a review blocker. | ruff per-file line budget via CI script |
| 40 `except Exception` in one file | Catch specific exceptions where recovery is specific. One broad handler lives at the HTTP boundary and nowhere else. | ruff `BLE001` (blind except) |
| Control flow via `'resp' not in locals()` | No dynamic scope tricks. Initialize every variable before its branch. | ruff `F821`, code review |
| Clarification detected by substring-matching prior assistant text | State lives in the session record, never inferred from rendered text. | `SessionState` has typed fields: `clarifications_asked: int` |
| 16 lazy imports inside one file to dodge cycles | Layers import downward only. `api` → `pipeline` → `stages` → `tools` → `providers` → `contracts`. | `import-linter` contract in `pyproject.toml` |
| Emoji and `🔍🔍🔍` in log messages | Structured logging. Event name plus key/value fields. No f-strings in log calls. | ruff `G004` (f-string in logging) |
| Up to 11 LLM call sites per turn, no budget | Every LLM call goes through one `LLMClient` with a per-request budget. Exceeding budget raises, not silently continues. | `LLMClient.call()` checks `ctx.llm_budget` |
| 24 hardcoded `gpt-4o` strings | Model names live in `settings.py` only. Code refers to roles: `settings.models.understanding`, `settings.models.planning`. | grep in CI: `gpt-|claude-` outside `settings.py` fails build |
| Redis pinged at import time | Nothing touches network or disk at import. Clients are built in `lifespan()` and injected. | FastAPI dependency injection, no module globals holding clients |
| Dead `_detect_ambiguous_query_llm` kept after being superseded | Delete code when its replacement ships. Same PR. | `vulture` in CI at 80% confidence |
| 26 loose scripts and 9 build artifacts tracked at root | Root holds config and entrypoint only. Scripts in `scripts/`. `.gitignore` covers coverage and reports. | CI fails if root gains a `.py` other than `main.py` |
| 82-line requirements with heavy ML deps for everyone | Core deps stay under 10. Everything heavy is an optional extra. | `pyproject.toml` extras, CI installs core only |
| Shopper covered by e2e tests only | Pure functions get unit tests first. E2E tests are a smoke layer, not the coverage. | Coverage gate 80% on `shopper/` package |
| Reference has no LICENSE, scrapers with ToS exposure | MIT from day one. No scraping providers in the default install. | Already done. Provider interface documents the requirement. |

## Part 2. Package layout

```
personal-shopper/
├── main.py                      # uvicorn entry only
├── shopper/
│   ├── __init__.py
│   ├── settings.py              # pydantic-settings; the only place model names and keys live
│   ├── contracts/               # pure data, zero imports from other shopper packages
│   │   ├── chat.py              # ChatRequest, ChatResponse, Turn, Role
│   │   ├── product.py           # Product, ProductInfo, ProviderResults
│   │   ├── understanding.py     # QueryUnderstanding, SpecializedIntents
│   │   ├── plan.py              # ExecutionPlan, ExecutionStep, ExecutionResponse
│   │   └── tools.py             # ToolInput, ToolOutput, ToolSpec
│   ├── llm/
│   │   ├── client.py            # LLMClient: single entry point, budget, retries, tracing
│   │   └── prompts.py           # prompt templates; no logic
│   ├── providers/               # one file per external catalog
│   │   ├── base.py              # CatalogProvider protocol
│   │   ├── unwrangle.py
│   │   └── fake.py              # deterministic provider for tests
│   ├── tools/
│   │   ├── registry.py          # @tool decorator, lookup by name
│   │   ├── product_search.py
│   │   ├── review_summarizer.py
│   │   └── research_product.py
│   ├── search/
│   │   ├── handler.py           # orchestrates provider call + filters, < 300 lines
│   │   ├── relevance.py         # scoring
│   │   └── filters.py           # price, rating, category
│   ├── stages/                  # each a class with run(ctx) -> ctx
│   │   ├── understand.py
│   │   ├── refine.py
│   │   ├── compare.py
│   │   ├── plan.py
│   │   ├── execute.py
│   │   ├── respond.py
│   │   ├── enrich.py
│   │   └── persist.py
│   ├── pipeline.py              # ShoppingPipeline: ordered list of stages, one run() loop
│   ├── session/
│   │   ├── state.py             # SessionState dataclass
│   │   └── store.py             # SessionStore protocol + InMemory, SQLite
│   ├── cache/
│   │   └── semantic.py          # decorator, in-memory backend; Redis under extra
│   └── api/
│       ├── app.py               # create_app(), lifespan, DI wiring
│       ├── routes_chat.py
│       ├── routes_products.py   # direct search for debugging providers
│       └── routes_health.py
├── tests/
│   ├── unit/                    # mirrors shopper/, no network, no LLM
│   ├── contract/                # provider contract tests against recorded fixtures
│   └── e2e/                     # full pipeline with FakeProvider and FakeLLM
├── scripts/
└── docs/
```

### Layer rule

```
api → pipeline → stages → {tools, search, session, cache} → {providers, llm} → contracts
```

Arrows point to allowed imports. `contracts` imports nothing from `shopper`. Enforced with `import-linter`:

```toml
[tool.importlinter]
root_package = "shopper"

[[tool.importlinter.contracts]]
name = "layers"
type = "layers"
layers = [
  "shopper.api",
  "shopper.pipeline",
  "shopper.stages",
  "shopper.tools | shopper.search | shopper.session | shopper.cache",
  "shopper.providers | shopper.llm",
  "shopper.contracts",
]
```

## Part 3. Core abstractions

Five interfaces. Everything else is an implementation of one of them.

### `RequestContext`

Carried through every stage. Replaces kwargs threading and `locals()` tricks.

```python
@dataclass
class RequestContext:
    request: ChatRequest
    session: SessionState
    understanding: QueryUnderstanding | None = None
    plan: ExecutionPlan | None = None
    execution: ExecutionResponse | None = None
    response: ChatResponse | None = None
    llm_budget: LLMBudget = field(default_factory=lambda: LLMBudget(max_calls=4))
    trace: list[StageEvent] = field(default_factory=list)
    done: bool = False          # a stage sets this to short-circuit (e.g. refinement hit)
```

### `Stage`

```python
class Stage(Protocol):
    name: str
    def run(self, ctx: RequestContext) -> RequestContext: ...
```

Pipeline loop is ten lines: for each stage, if `ctx.done` break, else time it, run it, append a `StageEvent`. Stages do not know about each other.

### `CatalogProvider`

```python
class CatalogProvider(Protocol):
    name: str
    def search(self, queries: list[str], *, category: str | None, limit: int, timeout_s: float) -> ProviderResults: ...
```

Contract test suite in `tests/contract/` runs the same assertions against every provider using recorded responses. A new provider is a file plus a fixture.

### `SessionStore`

```python
class SessionStore(Protocol):
    def get(self, conversation_id: str) -> SessionState: ...
    def put(self, state: SessionState) -> None: ...
```

`SessionState` is typed: `turns`, `last_products`, `clarifications_asked`, `updated_at`. No free-form entity dict.

### `LLMClient`

```python
class LLMClient:
    def call(self, *, role: ModelRole, messages: list[Message], schema: type[BaseModel] | None, budget: LLMBudget) -> LLMResult: ...
```

`role` maps to a model name in settings. `schema` forces structured output. `budget.consume()` raises `LLMBudgetExceeded` on the fifth call. Every call emits one structured log event with role, latency, tokens, and cache hit.

## Part 4. Phases

Each phase ends with the test suite green, CI green, and the endpoint callable. No phase starts until the previous phase's exit criteria are met.

### Phase 0. Foundations (current state → scaffolding)

Build: package layout, `contracts/`, `settings.py`, `RequestContext`, `Stage`, `ShoppingPipeline` with one `EchoStage`, `create_app()` with lifespan, `/health`, `ChatResponse` model, `Turn` with `Role` enum. Add `import-linter`, `vulture`, ruff rule set, coverage gate, root-clutter check to CI.

Exit: `/chat` returns the target response shape with `data=[]`. `import-linter` passes. Coverage of `shopper/` at 90% (it is all contracts, so this is cheap).

### Phase 1. One provider, direct search

Build: `CatalogProvider` protocol, `FakeProvider`, `UnWrangleProvider`, `ProviderResults`, `search/handler.py` with relevance scoring and price/rating filters, `POST /products/search`.

Exit: contract tests pass against recorded UnWrangle fixture and `FakeProvider`. Handler under 300 lines. p50 latency under 3 s against live provider, measured and recorded in `docs/BENCHMARKS.md`.

### Phase 2. Understanding and planning

Build: `LLMClient` with budget and structured output, `UnderstandStage`, `PlanStage` with pattern table and LLM fallback, `ExecuteStage`, `product_search` tool, `RespondStage` producing reply text and `data`.

Exit: `/chat` returns real products for "laptop under $1500". Happy path uses exactly 2 LLM calls (understanding, response), asserted by a test on `ctx.llm_budget.used`. FakeLLM makes the e2e suite deterministic and network-free.

### Phase 3. Memory and refinement

Build: `SessionStore` with InMemory and SQLite, `PersistStage`, `RefineStage` with LLM detection and regex fallback, `clarifications_asked` counter replacing text matching.

Exit: two-turn test: search, then "which of these is under $1000" returns a filtered subset with zero provider calls and at most 1 LLM call. Session survives process restart with SQLite.

### Phase 4. Cache

Build: semantic cache decorator on the search handler, 24 h TTL, in-memory backend. Redis backend under `[redis]` extra.

Exit: repeated query hits cache, `from_cache=true` in metadata, provider call count asserted zero. Cache key excludes `conversation_id`.

### Phase 5. Enrichments and remaining tools

Build: `CompareStage`, `EnrichStage` (comparison table, essentials checklist, rationale) driven by `SpecializedIntents`, `review_summarizer` and `research_product` tools.

Exit: comparison query returns two products and a table. LLM budget still holds: worst case 4 calls, asserted. Each enrichment is independently disableable in settings.

### Phase 6. Hardening

Build: API key auth dependency, rate limit middleware, OpenTelemetry tracing export for `ctx.trace`, Dockerfile, deployment doc.

Exit: 401 on missing key, 429 on burst, trace visible in a local collector. Docker image builds in CI.

### Deferred, each behind an extra and a benchmark

Indexed hybrid search, cross-encoder reranker, query expansion, second provider. Each lands only with a before/after number in `docs/BENCHMARKS.md`. The reference added these without measurements and ended up with 4,000 lines of filters nobody could remove.

## Part 5. Guardrails in CI

Run on every PR. All must pass.

```yaml
- ruff check .                     # includes BLE001, G004, C901, PLR0915, I, UP, B
- ruff format --check .
- lint-imports                     # layer contract
- vulture shopper --min-confidence 80
- pytest --cov=shopper --cov-fail-under=80
- scripts/check_root_clutter.sh    # fails if root has .py beyond main.py or tracked coverage/report files
- scripts/check_model_names.sh     # fails if model name literals appear outside shopper/settings.py
```

Ruff config additions over the current one:

```toml
[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "BLE", "G", "C90", "PLR0915", "SIM", "RET"]

[tool.ruff.lint.mccabe]
max-complexity = 10

[tool.ruff.lint.pylint]
max-statements = 40
```

## Part 6. Definition of done for any PR

- Changed stage or module under its line cap.
- New behavior has a unit test that runs without network.
- No new `except Exception` outside `api/`.
- No new LLM call outside `LLMClient`.
- No new model-name literal outside `settings.py`.
- If a feature replaces another, the old one is deleted in the same PR.
- Log calls use event names and fields, not f-strings.
- If it adds latency or a dependency, `docs/BENCHMARKS.md` gets a row.

## Part 7. Decisions recorded

| Decision | Choice | Reason |
|---|---|---|
| LLM client library | `openai` SDK direct, behind `LLMClient` | One dependency, structured outputs native. `litellm` can be swapped in behind the same interface if multi-provider becomes a need. |
| Session store default | SQLite | Zero infra for contributors. Survives restart. Protocol allows Postgres later. |
| Cache default | In-memory semantic | Same reason. Redis is an extra. |
| First provider | UnWrangle | Already proven in reference. Documented API, no scraping. |
| Scrapers | Not included | Terms-of-service exposure. An open-source default install should not ship them. |
| Multi-persona routing | Not included | This is a shopper. If a second persona ever appears, it is a second pipeline, not a router. |
| Python floor | 3.10 | `X | Y` unions and `match`. Nothing in the plan needs newer. |

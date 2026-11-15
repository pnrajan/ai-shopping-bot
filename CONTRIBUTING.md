# Contributing

Thanks for your interest. Issues and pull requests are welcome.

## Setup

```bash
git clone https://github.com/<your-username>/ai-shopping-bot.git
cd ai-shopping-bot
bash scripts/setup.sh --dev
source .venv/bin/activate
```

## Workflow

1. Open an issue before large changes so the approach can be agreed first.
2. Branch from `main`. Keep one concern per pull request.
3. Run `bash scripts/check.sh` before pushing. It runs exactly what CI runs.
4. Open a pull request describing what changed and why.

## Code rules

These are enforced by CI, not just convention.

| Rule | Enforced by |
|---|---|
| A request is a sequence of stages. One class per stage, one `run(ctx)` method, under 40 statements. | ruff `PLR0915`, `C901` |
| Catch specific exceptions. The only broad handler lives at the HTTP boundary in `ai_shopping_bot/api/`. | ruff `BLE001` |
| Layers import downward only: `api` → `pipeline` → `stages` → `tools` → `search` → `session`/`cache` → `providers`/`llm` → `contracts`. | `import-linter` |
| Every LLM call goes through `LLMClient` and spends from the per-request budget. | code review, `LLMBudget` |
| Model names live in `ai_shopping_bot/settings.py` only. Code refers to roles. | `scripts/check_model_names.sh` |
| Nothing touches network or disk at import time. Clients are built in the app lifespan and injected. | code review |
| Delete superseded code in the same PR that replaces it. | `vulture` |
| Repo root holds config and `main.py` only. Scripts go in `scripts/`. | `scripts/check_root_clutter.sh` |
| Core dependencies stay small. Anything heavy is an optional extra. | `pyproject.toml` extras |
| Log with event names and fields, not f-strings. | ruff `G004` |
| Pure functions get unit tests that run without network. Coverage gate is 80%. | `pytest-cov` |

## Definition of done

- New behavior has a unit test that runs offline.
- No new model literal, blind except, or LLM call outside the places above.
- If the change adds latency, an LLM call, or a dependency, `docs/BENCHMARKS.md` gets a row.
- Docs updated where behavior changed.

## Style

- Python 3.11+. Type hints on public functions. Docstrings proportional to the code.
- Formatting and linting via `ruff`.

## License

By contributing you agree your contributions are licensed under the MIT License.

# Contributing

Thanks for your interest in contributing.

## Setup

```bash
git clone https://github.com/<your-username>/personal-shopper.git
cd personal-shopper
python -m venv venv && source venv/bin/activate
pip install -r requirements-dev.txt
```

## Workflow

1. Open an issue describing the change before large work.
2. Fork and create a branch from `main`.
3. Keep changes focused. One concern per pull request.
4. Run checks before pushing:

   ```bash
   ruff check .
   pytest
   ```

5. Open a pull request. Describe what changed and why.

## Style

- Python 3.9+ compatible.
- Type hints on public functions.
- Docstrings on public classes and functions. Keep them proportional to the code.
- Formatting and linting via `ruff`.

## License

By contributing you agree your contributions are licensed under the MIT License.

This is a lightweight software distribution implementation supporting different technologies.

- Follow the "Easier to Ask Forgiveness than Permission" pattern.
- Lint using `uv run ty check` and format using `uv run ruff format`.
- Run using `uv run python cli.py`.
    - Dont try (re)starting the server, ill handle it myself.
# Testing
- Run tests using `uv run pytest`.
    - Measure coverage (opt-in) using `uv run pytest --cov`; HTML report via `--cov-report=html`.
    - Parametrise tests whenever possible.
    - Prefer `monkeypatch` for mocks.
    - Tests should follow Arrange-Act-Assert pattern.
    - Tests should be reasonable.
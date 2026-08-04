# Contributing

## Before you start

- Search existing issues and pull requests before proposing duplicate work.
- Keep changes focused on the problem being addressed.
- Do not commit secrets, `.env` files, Chroma databases, local traces, caches,
  virtual environments, `node_modules`, or generated reports.
- Use fictional or synthetic data in examples and tests.
- Do not add private workflow files or machine-specific paths.

## Development setup

Set up the Python and API dependencies from the repository root:

```bash
uv sync --group dev --group api
```

Set up the frontend from `frontend/`:

```bash
cd frontend
npm ci
```

See the [README](README.md), [engineering onboarding guide](docs/engineering/onboarding.md),
and [testing strategy](docs/engineering/testing-strategy.md) for the current
requirements and workflows.

## Validation

Run the keys-free checks relevant to your changes from the repository root:

```bash
uv run pytest -v
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

`mypy` takes no path arguments: its scope is the `files` list in
`pyproject.toml`, which is the single source of truth shared with CI. Passing
paths explicitly overrides that list and reports on modules that are outside the
type-checked surface by design.

For frontend changes, run these commands from `frontend/`:

```bash
npm run build
npm test
npm run test:responsive
```

Report the checks you ran and any checks you could not run.

## Provider-backed tests

Normal validation is keys-free. Real-model tests run only when
`RUN_REAL_MODEL_TESTS=1` is explicitly set and the required credentials are
deliberately provided. `OFFLINE_MODE` prevents provider execution. Do not enable
paid or provider-backed tests unintentionally, and never include credentials in
output or committed files.

Provider-backed ingestion and evaluation runs are not required for ordinary
contributions unless a change specifically affects those paths.

## Pull requests

Include:

- the problem and approach;
- affected modules;
- tests and checks run;
- documentation changes;
- compatibility implications; and
- whether external or provider behavior changed.

Avoid unrelated formatting changes and dependency churn.

## Documentation and architecture

Preserve the primary architecture boundary:

```text
frontend/
  -> api/
     -> office_agent.engine.answer_office_request()
        -> deterministic Office tools or the Enterprise RAG adapter
```

The `api/` package must remain a thin adapter. Frontend code must not derive
authoritative effective Run Settings. Keep historical ADRs and release notes as
point-in-time records, update current-state documentation when behavior changes,
and keep synthetic mock data fictional.

## Security reports

Follow [SECURITY.md](SECURITY.md). Do not disclose vulnerabilities in ordinary
public issue or pull-request discussions.

## License

By contributing, you agree that your contributions will be licensed under the
[MIT License](LICENSE).

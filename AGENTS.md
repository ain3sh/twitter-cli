<coding_guidelines>
# AGENTS.md - twitter-cli developer guide

## Project

- Python 3.10+
- Click CLI
- uv package manager
- Repository: https://github.com/ain3sh/twitter-cli
- Upstream: https://github.com/public-clis/twitter-cli

## Checks

```bash
uv sync --extra dev
uv run ruff check .
uv run mypy twitter_cli
uv run pytest -q
uv run pytest -m smoke -v
```

## Style

- Line length: 100
- Add `from __future__ import annotations` to Python modules.
- Use snake_case for Python names and PascalCase for classes.
- Dataclasses live in `models.py`.
- Custom exceptions derive from `TwitterError` in `exceptions.py`.

## Canonical runtime contracts

- YAML is the default; commands expose one `--format` selector.
- Structured output uses the envelope in `SCHEMA.md` with `schemaVersion: "1"`.
- Rich results go to stdout; progress and diagnostics go to stderr.
- Save output with shell redirection. Do not add an output-file option.
- `Timeline` is the only internal tweet-list result and owns `next_cursor`.
- Nested quoted tweets use the full recursive Tweet shape.
- The model and public contract use `username`; `screen_name` exists only as an upstream API key.
- `user [username] [relation]` owns profiles and user relations.
- `post` owns posts, replies, and quotes.
- `filter` owns local timeline transformation and never creates a client.
- Search accepts Twitter's native query grammar; do not add operator flags or a query builder.
- All tweet-targeting commands accept the same numeric ID or x.com/twitter.com URL grammar.
- Write results contain only the affected `id`.
- Browser discovery is owned by `auth.py`; do not add subprocess or filesystem shims.
- Read paths must not initialize write-only transaction-ID machinery.
- Config lives under XDG config; caches live under XDG cache.
- Config parsing is strict and uses only the shape documented in README.md.
- Keep `twitter_cli.__version__` and `project.version` synchronized.

## Modules

```text
twitter_cli/
  main.py           process entrypoint and fast version path
  cli.py            canonical Click command graph
  client.py         Twitter HTTP client
  auth.py           browser cookie discovery
  parser.py         upstream response parsing
  models.py         dataclass models
  serialization.py canonical wire conversion
  output.py         envelopes and output selection
  formatter.py      Rich terminal rendering
  config.py         strict XDG configuration
  filter.py         tweet scoring and filtering
  graphql.py        query IDs and feature flags
  constants.py      browser request constants
  exceptions.py     error hierarchy
  paths.py          XDG paths
  timeutil.py       terminal time formatting
```
</coding_guidelines>

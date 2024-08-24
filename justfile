@lint:
  echo mypy
  just --justfile {{justfile()}} mypy
  echo ruff
  just --justfile {{justfile()}} ruff
  echo ruff-format
  just --justfile {{justfile()}} ruff-format

@mypy:
  uv run mypy meilisearch_python_sdk tests

@ruff:
  uv run ruff check .

@ruff-format:
  uv run ruff format meilisearch_python_sdk tests

@test:
  -uv run pytest -x

@test-parallel:
  -uv run pytest -n auto -x -m "not no_parallel"

@test-no-parallel:
  -uv run pytest -x -m "no_parallel"

@test-ci: start-meilisearch-detached && stop-meilisearch
  uv run pytest --cov=meilisearch_python_sdk --cov-report=xml

@test-parallel-ci: start-meilisearch-detached && stop-meilisearch
  uv run pytest --cov=meilisearch_python_sdk --cov-report=xml -n auto -m "not no_parallel"

@test-no-parallel-ci: start-meilisearch-detached && stop-meilisearch
  uv run pytest --cov=meilisearch_python_sdk --cov-report=xml -m "no_parallel"

@start-meilisearch:
  docker compose up

@start-meilisearch-detached:
  docker compose up -d

@stop-meilisearch:
  docker compose down

@build-docs:
  uv run mkdocs build --strict

@serve-docs:
  mkdocs serve

@install:
  uv sync --frozen --all-extras

@benchmark: start-meilisearch-detached && stop-meilisearch
  -uv run benchmark/run_benchmark.py

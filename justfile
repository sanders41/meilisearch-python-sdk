@_default:
  just --list

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
  uv run ruff format meilisearch_python_sdk tests examples

@test *args="":
  -uv run pytest {{args}}

@test-http2 *args="":
  -uv run pytest --http2 {{args}}

@test-parallel *args="":
  -uv run pytest -n auto -m "not no_parallel" {{args}}

@test-no-parallel *args="":
  -uv run pytest -m "no_parallel" {{args}}

@test-parallel-http2 *args="":
  -uv run pytest -n auto -m "not no_parallel" --http2 {{args}}

@test-no-parallel-http2 *args="":
  -uv run pytest -m "no_parallel" --http2 {{args}}

@test-ci: start-meilisearch-detached && stop-meilisearch
  uv run pytest --cov=meilisearch_python_sdk --cov-report=xml

@test-parallel-ci: start-meilisearch-detached && stop-meilisearch
  uv run pytest --cov=meilisearch_python_sdk --cov-report=xml -n auto -m "not no_parallel"

@test-no-parallel-ci: start-meilisearch-detached && stop-meilisearch
  uv run pytest --cov=meilisearch_python_sdk --cov-report=xml -m "no_parallel"

@test-parallel-ci-http2: start-meilisearch-detached-http2 && stop-meilisearch-http2
  uv run pytest --cov=meilisearch_python_sdk --cov-report=xml -n auto -m "not no_parallel" --http2

@test-no-parallel-ci-http2: start-meilisearch-detached-http2 && stop-meilisearch-http2
  uv run pytest --cov=meilisearch_python_sdk --cov-report=xml -m "no_parallel" --http2

@test-examples-ci: start-meilisearch-detached
  cd examples && \
  pip install -r requirements.txt && \
  pytest

@start-meilisearch:
  docker compose up

@start-meilisearch-detached:
  docker compose up -d

@stop-meilisearch:
  docker compose down

@start-meilisearch-http2:
  docker compose -f docker-compose.https.yml up

@start-meilisearch-detached-http2:
  docker compose -f docker-compose.https.yml up -d

@stop-meilisearch-http2:
  docker compose -f docker-compose.https.yml down

@build-docs:
  uv run mkdocs build --strict

@serve-docs:
  mkdocs serve

@install:
  uv sync --frozen --all-extras

@lock:
  uv lock

@lock-upgrade:
  uv lock --upgrade

@benchmark: start-meilisearch-detached && stop-meilisearch
  -uv run benchmark/run_benchmark.py

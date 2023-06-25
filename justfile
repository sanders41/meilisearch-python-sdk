@lint:
  echo black
  just --justfile {{justfile()}} black
  echo mypy
  just --justfile {{justfile()}} mypy
  echo ruff
  just --justfile {{justfile()}} ruff

@black:
  poetry run black meilisearch_python_async tests

@mypy:
  poetry run mypy .

@ruff:
  poetry run ruff check .

@test: start-meilisearch-detached && stop-meilisearch
  -poetry run pytest

@test-ci: start-meilisearch-detached && stop-meilisearch
    poetry run pytest --cov=meilisearch_python_async --cov-report=xml

@start-meilisearch:
  docker compose up

@start-meilisearch-detached:
  docker compose up -d

@stop-meilisearch:
  docker compose down

@build-docs:
  poetry run mkdocs build --strict

@serve-docs:
  mkdocs serve

@install:
  poetry install

@benchmark: start-meilisearch-detached && stop-meilisearch
  -poetry run python benchmark/run_benchmark.py

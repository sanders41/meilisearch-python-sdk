@lint:
  echo mypy
  just --justfile {{justfile()}} mypy
  echo ruff
  just --justfile {{justfile()}} ruff
  echo ruff-format
  just --justfile {{justfile()}} ruff-format

@mypy:
  poetry run mypy meilisearch_python_sdk tests

@ruff:
  poetry run ruff check .

@ruff-format:
  poetry run ruff format meilisearch_python_sdk tests

@test: start-meilisearch-detached && stop-meilisearch
  -poetry run pytest -x

@test-ci: start-meilisearch-detached && stop-meilisearch
  poetry run pytest --cov=meilisearch_python_sdk --cov-report=xml

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

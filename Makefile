CONTAINER_NAME = meilisearch_test

.PHONY: test
test:
	@docker run --rm -d -p 7700:7700 --name $(CONTAINER_NAME) getmeili/meilisearch:latest ./meilisearch --master-key=masterKey --no-analytics
	@poetry run pytest
	@docker stop $(CONTAINER_NAME)

.PHONY: clean
clean:
	@docker stop $(CONTAINER_NAME)
	@echo "$(CONTAINER_NAME) stopped"

.PHONY: dev lint test

dev:
	uvicorn backend.manager_api.app:create_app --factory --reload

lint:
	python -m ruff check backend

test:
	pytest

.PHONY: dev lint test worker

dev:
	uvicorn backend.manager_api.app:create_app --factory --reload

lint:
	python -m ruff check backend

test:
	pytest

worker:
	python -m backend.manager_worker

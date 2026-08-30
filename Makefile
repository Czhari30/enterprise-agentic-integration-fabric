.PHONY: test evaluate lint run container

test:
	python -m unittest discover -s tests -v

evaluate:
	python evaluation/run.py

lint:
	ruff check enterprise_fabric tests evaluation

run:
	uvicorn enterprise_fabric.api:app --reload --port 8080

container:
	docker compose up --build

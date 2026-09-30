.PHONY: install test lint run dry-run eval build

install:
	pip install -r requirements-dev.txt

test:
	pytest tests/unit -q

lint:
	ruff check src scripts tests

run:
	python scripts/run_local.py

dry-run:
	python scripts/run_local.py --dry-run

eval:
	python scripts/evaluate.py eligibility
	python scripts/evaluate.py role

build:
	docker build -t rjp .

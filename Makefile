install:
	pip install -r test_requirements.txt

test:
	pytest --create-db --nomigrations

coverage:
	pytest --create-db --nomigrations --cov=briefme_subscription tests

report:
	pytest --create-db --nomigrations --cov=briefme_subscription --cov-report=html tests
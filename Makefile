.PHONY: install lock upload-models download-models check-secrets

install:
	python -m pip install -r requirements-locked.txt || python -m pip install -r requirements.txt
	python -m pip install -e .

lock:
	python -m pip install pip-tools
	pip-compile requirements.in --output-file=requirements-locked.txt

upload-models:
	python scripts/upload_models.py

download-models:
	python scripts/download_models.py

check-secrets:
	python scripts/check_secrets.py

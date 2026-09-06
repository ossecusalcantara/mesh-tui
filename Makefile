PYTHON := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: help venv install run run-serial run-tcp test check clean

help: ## Show available targets
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

venv: ## Create the virtual environment
	python3 -m venv .venv

install: venv ## Install dependencies into the venv
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

run: ## Launch the TUI (pick port/host with F2)
	$(PYTHON) main.py

run-serial: ## Launch connected via serial (PORT=/dev/ttyUSB0)
	$(PYTHON) main.py --port $(or $(PORT),/dev/ttyUSB0)

run-tcp: ## Launch connected via TCP (HOST=192.168.1.50)
	$(PYTHON) main.py --host $(or $(HOST),192.168.1.50)

test: ## Run headless tests (no hardware needed)
	$(PYTHON) tests/test_app.py

check: test ## Verify imports and CLI
	$(PYTHON) -c "import mesh_tui.app; print('import OK')"

clean: ## Remove caches and build artifacts
	rm -rf __pycache__ .pytest_cache mesh_tui/__pycache__ tests/__pycache__ \
		mesh_tui.egg-info build dist *.egg-info

PYTHON := .venv/bin/python
PIP := .venv/bin/pip

.PHONY: help venv install run run-serial run-tcp test check clean

help: ## Mostra os alvos disponíveis
	@grep -E '^[a-zA-Z_-]+:.*?## ' $(MAKEFILE_LIST) | awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-12s\033[0m %s\n", $$1, $$2}'

venv: ## Cria o ambiente virtual
	python3 -m venv .venv

install: venv ## Instala dependências no venv
	$(PIP) install -r requirements.txt
	$(PIP) install -e .

run: ## Abre a TUI (escolhe porta/host com F2)
	$(PYTHON) main.py

run-serial: ## Abre a TUI conectando via serial (PORT=/dev/ttyUSB0)
	$(PYTHON) main.py --port $(or $(PORT),/dev/ttyUSB0)

run-tcp: ## Abre a TUI conectando via TCP (HOST=192.168.1.50)
	$(PYTHON) main.py --host $(or $(HOST),192.168.1.50)

test: ## Roda os testes headless (sem hardware)
	$(PYTHON) tests/test_app.py

check: test ## Verifica imports e CLI
	$(PYTHON) -c "import mesh_tui.app; print('import OK')"

clean: ## Remove caches e arquivos de build
	rm -rf __pycache__ .pytest_cache mesh_tui/__pycache__ tests/__pycache__ \
		mesh_tui.egg-info build dist *.egg-info

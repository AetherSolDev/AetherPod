# Created: 2026-07-26
# Last Edited: 2026-07-26 11:07 CT (America/Chicago)
# Path: Makefile
# Purpose: Convenience targets for installing and managing AetherPod.

PIP ?= pip3

.PHONY: install install-user install-venv uninstall clean

install:
	$(PIP) install .

install-user:
	$(PIP) install --user .

install-venv:
	python3 -m venv --prompt aetherpod .venv && \
	. .venv/bin/activate && \
	$(PIP) install -e .

uninstall:
	$(PIP) uninstall -y aetherpod

clean:
	rm -rf build/ dist/ *.egg-info/ src/*.egg-info/
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true

.PHONY: help run serve ip integration lint

help: ## Targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F'[:#]+' '{printf "  %-12s %s\n", $$1, $$NF}'

run: ## Verdict on sample photos: make run F="samples/*.jpg"
	uv run python cli/main.py $(or $(F),samples/*.jpg)

serve: ## HTTP endpoint for the iPhone Shortcut on :8787
	uv run uvicorn app.server:app --host 0.0.0.0 --port 8787

ip: ## LAN URL to paste into the Shortcut
	@echo "http://$$(ipconfig getifaddr en0):8787/decide"

integration: ## One sample through the full pipeline, must print a decision
	uv run python cli/main.py --json samples/*.jpg | head -1 | grep -E '"decision": "(APPROVE|NOPE|REVIEW)"'

lint: ## Ruff
	uvx ruff check app cli

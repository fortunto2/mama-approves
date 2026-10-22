ENV := set -a; [ -f .env ] && . ./.env; set +a;

.PHONY: help run serve ip tunnel integration lint snap cams

help: ## Targets
	@grep -E '^[a-z-]+:.*##' $(MAKEFILE_LIST) | awk -F'[:#]+' '{printf "  %-12s %s\n", $$1, $$NF}'

run: ## Verdict on sample photos: make run F="samples/*.jpg"
	$(ENV) uv run python cli/main.py $(or $(F),samples/*.jpg)

serve: ## HTTP endpoint on :8787 (PUBLIC_URL drives the QR)
	$(ENV) PUBLIC_URL=$(or $(PUBLIC_URL),https://bro.rustman.org) uv run uvicorn app.server:app --host 0.0.0.0 --port 8787

tunnel: ## bro.rustman.org via the named Cloudflare tunnel (config ~/.cloudflared/brocheck.yml)
	cloudflared tunnel --config ~/.cloudflared/brocheck.yml run brocheck

quick-tunnel: ## Throwaway public URL when the named tunnel is not set up
	cloudflared tunnel --url http://127.0.0.1:8787 --no-autoupdate

ip: ## LAN URL to paste into the Shortcut
	@echo "http://$$(ipconfig getifaddr en0):8787/decide"

integration: ## One sample through the full pipeline, must print a decision
	$(ENV) uv run python cli/main.py --json samples/*.jpg | head -1 | grep -E '"decision": "(APPROVE|NOPE|REVIEW)"'

lint: ## Ruff
	uvx ruff check app cli

snap: ## Grab a frame from the Mac camera and judge it: make snap [CAM=0]
	ffmpeg -hide_banner -loglevel error -y -f avfoundation -framerate 30 -i "$(or $(CAM),0)" -frames:v 1 -update 1 samples/snap.jpg && $(ENV) uv run python cli/main.py samples/snap.jpg

cams: ## List cameras (0 = MacBook, 2 = iPhone Continuity)
	ffmpeg -hide_banner -f avfoundation -list_devices true -i "" 2>&1 | grep -E '^\[AVFoundation.*\] \[[0-9]\]'

# Variables
SERVICE_NAME ?= math-madness
REGION ?= us-central1
PROJECT_ID ?= $(shell gcloud config get-value project)

# Default target
.PHONY: all
all: help

# Help target
.PHONY: help
help:
	@echo "Usage:"
	@echo "  make run          Run locally with uvicorn (port 8080)"
	@echo "  make deploy       Deploy the application to Cloud Run"
	@echo "  make build-local  Build the Docker image locally"
	@echo "  make run-docker   Run the Docker container locally (port 8080)"

# Run locally (no Docker)
.PHONY: run
run:
	uv run python server.py

# Deploy target
.PHONY: deploy
deploy:
	@echo "Deploying $(SERVICE_NAME) to Cloud Run in region $(REGION)..."
	gcloud run deploy $(SERVICE_NAME) \
		--source . \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--allow-unauthenticated \
		--port 8080 \
		--min-instances 1 \
		--max-instances 1

# Local build target
.PHONY: build-local
build-local:
	docker build -t $(SERVICE_NAME) .

# Local Docker run target
.PHONY: run-docker
run-docker:
	docker run -p 8080:8080 $(SERVICE_NAME)

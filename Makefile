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
	@echo "  make deploy       Deploy the application to Cloud Run"
	@echo "  make build-local  Build the Docker image locally"
	@echo "  make run-local    Run the Docker container locally (port 8080)"

# Deploy target
.PHONY: deploy
deploy:
	@echo "Deploying $(SERVICE_NAME) to Cloud Run in region $(REGION)..."
	gcloud run deploy $(SERVICE_NAME) \
		--source . \
		--region $(REGION) \
		--project $(PROJECT_ID) \
		--allow-unauthenticated \
		--port 80

# Local build target
.PHONY: build-local
build-local:
	docker build -t $(SERVICE_NAME) .

# Local run target
.PHONY: run-local
run-local:
	docker run -p 8080:80 $(SERVICE_NAME)

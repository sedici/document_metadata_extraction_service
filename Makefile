# Makefile for the Sedici metadata extraction project
# ----------------------------------------------------------
# Provides shortcuts to manage core API services and the MCP layer
# using Docker Compose. The definition assumes the root of the
# repository is the working directory.

DC = docker compose
# Include the core compose file and the MCP compose file
DC_FILES = -f api/app/docker-compose.yml
# Load environment variables from the parent .env file
ENV_FILE = --env-file api/app/.env

.PHONY: up build stop down logs

up: ## Start all services (APIs + MCPs) in detached mode
	$(DC) $(DC_FILES) $(ENV_FILE) up -d

build: ## Build all images for APIs and MCPs
	$(DC) $(DC_FILES) $(ENV_FILE) build

stop: ## Stop containers without removing them
	$(DC) $(DC_FILES) $(ENV_FILE) stop

down: ## Stop and remove containers, networks, volumes, and images
	$(DC) $(DC_FILES) $(ENV_FILE) down --remove-orphans

logs: ## Follow logs for all containers
	$(DC) $(DC_FILES) $(ENV_FILE) logs -f

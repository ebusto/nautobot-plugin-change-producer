# -------------------------------------------------------------------------------------------
# VARIABLES: Variable declarations to be used within make to generate commands.
# -------------------------------------------------------------------------------------------
PROJECT_NAME ?= nautobot-change-producer

# These variables should be the same across all projects
COMPOSE = docker-compose --project-name $(PROJECT_NAME) --project-directory "develop" -f "develop/docker-compose.yml"
VERSION = $(shell grep -m 1 version pyproject.toml | tr -s ' ' | tr -d '"' | tr -d "'" | cut -d' ' -f3)

default: help

# -------------------------------------------------------------------------------------------
# DEVELOPMENT ENVIRONMENT: Commands used to interface with the development environment.
# -------------------------------------------------------------------------------------------
cli: .env ## Launch a bash shell inside the running Nautobot container.
ifeq (,$(findstring nautobot,$($COMPOSE ps --services --filter status=running)))
	@make start
endif
	@$(COMPOSE) exec nautobot bash
.PHONY: cli

sub:  ## Runs a small subscriber to test the change producer.
	@python3 develop/subscriber.py

debug: .env ## Start Nautobot and its dependencies with this plugin in debug mode.
	@$(COMPOSE) up
.PHONY: debug

logs: .env ## Attach to the running containers and tail the logs.
	@$(COMPOSE) logs -f --tail=500
.PHONY: logs

start: .env ## Start Nautobot and its dependencies in detached mode.
	@ENV=local $(COMPOSE) up -d
.PHONY: start

stop: .env ## Stop Nautobot and its dependencies.
	@$(COMPOSE) down
.PHONY: stop

restart: .env ## Restart Nautobot and its dependencies.
	@ENV=local $(COMPOSE) restart
.PHONY: restart

destroy: .env ## Destroy all containers and volumes.
	@$(COMPOSE) down --volumes
.PHONY: destroy

build: .env ## Build all docker images.
	@$(COMPOSE) build --no-cache
.PHONY: build

shell: .env ## Launch a Django Shell session.
ifeq (,$(findstring nautobot,$($COMPOSE ps --services --filter status=running)))
	@make start
endif
	@$(COMPOSE) exec nautobot nautobot-server shell_plus
.PHONY: shell

# -------------------------------------------------------------------------------------------
# LINT/TEST: Linting, integrations and unit tests.
# -------------------------------------------------------------------------------------------
unittest: .env ## Runs unit tests in the dev container.
	@$(COMPOSE) run --rm --entrypoint 'make _unittest' nautobot
.PHONY: unittest

_unittest:
	@echo "🧪 Running Python Unittest... 🧪"
	@poetry run coverage run --rcfile=pyproject.toml --module nautobot.core.cli test nautobot_change_producer --buffer
	@poetry run coverage combine || true
	@poetry run coverage report --rcfile=pyproject.toml --fail-under=50
	@poetry run coverage html --rcfile=pyproject.toml
.PHONY: _unittest

# -------------------------------------------------------------------------------------------
# BUILD: Build Python package.
# -------------------------------------------------------------------------------------------
package: ## Build the python package for this repo.
	@poetry build --format=wheel
.PHONY: package

minor: ## Bumps the poetry version of this package.
	@poetry version minor
.PHONY: minor

pypi-minor: _poetry_setup minor package _env-ARTIFACTORY_USERNAME _env-ARTIFACTORY_SECRET ## Bump poetry version, build and publish the package to Artifactory.
	@poetry publish --repository=nv-shared -u "${ARTIFACTORY_USERNAME}" -p "${ARTIFACTORY_SECRET}"
.PHONY: pypi-minor

pypi: _poetry_setup package _env-ARTIFACTORY_USERNAME _env-ARTIFACTORY_SECRET ## Build and publish the package to Artifactory.
	@poetry publish --repository=nv-shared -u "${ARTIFACTORY_USERNAME}" -p "${ARTIFACTORY_SECRET}"
.PHONY: pypi

# -------------------------------------------------------------------------------------------
# HELPERS: Internal Make Commands
# -------------------------------------------------------------------------------------------
_poetry_setup:
	@poetry config repositories.nv-shared https://urm.nvidia.com/artifactory/api/pypi/nv-shared-pypi-local
.PHONY: _poetry_setup

.env:
	@if [ ! -f "${PWD}/develop/.env" ]; then \
	   echo "Creating environment file..."; \
	   cp ${PWD}/develop/env.example ${PWD}/develop/.env; \
	fi
.PHONY: .env

_env-%:
	@ if [ "${${*}}" = "" ]; then \
		echo "Environment variable $* not set"; \
		echo "Please check README.md or Makefile for variables required."; \
		echo "(╯°□°）╯︵ ┻━┻"; \
		exit 1; \
	fi
.PHONY: _env-%

help:
	@echo "\033[1m\033[01;32m\
	$(shell echo $(PROJECT_NAME) | tr  '[:lower:]' '[:upper:]') $(VERSION) \
	\033[00m\n"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' \
	$(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; \
	{printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}'
.PHONY: help
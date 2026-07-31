# Thin convenience wrapper. Windows contributors can invoke WORKSPACE_CLI directly.

include stack.mk

.DEFAULT_GOAL := help
.PHONY: help setup dev fmt fmt-check lint typecheck test check build ship
.PHONY: migrate migrate-down coverage contract contract-check demo smoke
.PHONY: audit review journal doctor hooks compose-config compose-build compose-up compose-down
.PHONY: check-backend check-frontend

help:
	@$(WORKSPACE_CLI) --help

setup:
	@$(WORKSPACE_CLI) setup

dev:
	@$(WORKSPACE_CLI) dev

fmt:
	@$(WORKSPACE_CLI) fmt

fmt-check:
	@$(WORKSPACE_CLI) fmt-check

lint:
	@$(WORKSPACE_CLI) lint

typecheck:
	@$(WORKSPACE_CLI) typecheck

test:
	@$(WORKSPACE_CLI) test

check:
	@$(WORKSPACE_CLI) check

check-backend:
	@$(WORKSPACE_CLI) check backend

check-frontend:
	@$(WORKSPACE_CLI) check frontend

build:
	@$(WORKSPACE_CLI) build

ship:
	@$(WORKSPACE_CLI) ship

migrate:
	@$(WORKSPACE_CLI) migrate

migrate-down:
	@$(WORKSPACE_CLI) migrate-down

coverage:
	@$(WORKSPACE_CLI) coverage

contract:
	@$(WORKSPACE_CLI) contract sync

contract-check:
	@$(WORKSPACE_CLI) contract check

demo:
	@$(WORKSPACE_CLI) demo

smoke:
	@$(WORKSPACE_CLI) smoke

audit:
	@$(WORKSPACE_CLI) audit

review:
	@$(WORKSPACE_CLI) review

journal:
	@$(WORKSPACE_CLI) journal

doctor:
	@$(WORKSPACE_CLI) doctor

hooks:
	@$(WORKSPACE_CLI) hooks

compose-config:
	@$(WORKSPACE_CLI) compose config

compose-build:
	@$(WORKSPACE_CLI) compose build

compose-up:
	@$(WORKSPACE_CLI) compose up

compose-down:
	@$(WORKSPACE_CLI) compose down

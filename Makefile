# Info      : Microelectronic System test system (FuseSoC-based)
# File      : Makefile
# Author    : Christian Conti
# Contact   : christian.conti@polito.it

SHELL := /bin/bash

# Directory of this Makefile (robust even if make is invoked from elsewhere)
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

## @section Config

## @config Target DUT directory
## @param TARGET Path to the exercise directory
TARGET ?= 

## Removed TB argument; tests discover simulation folders automatically

# Script path for conda environment setup
CONDA_ENV_SCRIPT ?= $(MAKEFILE_DIR)/utils/MakeConda

# FuseSoC configuration
FUSESOC           := fusesoc
FUSESOC_CORE_FILE := fusesoc.core

# ── Targets ─────────────────────────────────────────────────────────────────────
.PHONY: help env test clean

## @section Help
## Show this guide
help:
	@set -e; \
	HELP_SCRIPT="$(MAKEFILE_DIR)/utils/MakeHelp"; \
	if [ ! -f "$$HELP_SCRIPT" ]; then \
		echo "[ERROR] $$HELP_SCRIPT not found."; \
		exit 1; \
	fi; \
	FILE_FOR_HELP="$(firstword $(MAKEFILE_LIST))" bash "$$HELP_SCRIPT"

## @section Environment
## Download miniconda (if needed) and create the conda environment with FuseSoC
## After the environment is created, install pre-built GHDL
env:
	@bash "$(CONDA_ENV_SCRIPT)"
	@echo "[INFO] Installing pre-built GHDL (utils/MakeGHDL)..."
	@bash "$(MAKEFILE_DIR)/utils/MakeGHDL"

## Execute the test flow: scan TARGET for "sim" dirs and run Python runner
## @param TARGET Path to the exercise directory
test:
	@python3 "$(MAKEFILE_DIR)/utils/run_tests.py" "$(TARGET)"

## @section Clean
## Remove all build artifacts
clean:
	rm -rf build/
	rm -f $(FUSESOC_CORE_FILE)
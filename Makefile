# Info      : Microelectronic System test system (FuseSoC-based)
# File      : Makefile
# Author    : Christian Conti
# Contact   : christian.conti@polito.it

SHELL := /bin/bash

# Directory of this Makefile (robust even if make is invoked from elsewhere)
MAKEFILE_DIR := $(dir $(abspath $(lastword $(MAKEFILE_LIST))))

## @section Config

## @config Target DUT directory
## @param TARGET Path to the DUT directory
TARGET ?= src/cap1/dut

## @config Testbench name
## @param TB Testbench name (e.g., capX-name)
TB ?= cap1-name

# Script path for conda environment setup
CONDA_ENV_SCRIPT ?= $(MAKEFILE_DIR)/utils/MakeConda

# FuseSoC configuration
FUSESOC           := fusesoc
FUSESOC_CORE_FILE := fusesoc.core

# ── Targets ─────────────────────────────────────────────────────────────────────
.PHONY: help conda-env core sim clean

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
## Download miniconda (if needed) and create the 'amaretto' conda environment with FuseSoC
conda-env:
	@bash "$(CONDA_ENV_SCRIPT)";

## @section Core & Simulation

## Generate the fusesoc core file from the target directory and testbench
## @param TARGET Path to the DUT directory
## @param TB Testbench name (e.g., capX-name)
core:
	@python3 "$(MAKEFILE_DIR)/utils/generate_core.py" "$(TARGET)" "$(TB)" -o "$(FUSESOC_CORE_FILE)"

## Execute the simulation flow: builds the core first, then runs fusesoc sim target
## @param TARGET Path to the DUT directory
## @param TB Testbench name (e.g., capX-name)
sim: core
	@CORE_VLNV=$$(grep -m 1 '^name *:' $(FUSESOC_CORE_FILE) | awk '{print $$2}'); \
	if [ -z "$$CORE_VLNV" ]; then \
		echo "[ERROR] Could not find 'name:' field inside $(FUSESOC_CORE_FILE)."; \
		exit 1; \
	fi; \
	$(FUSESOC) --cores-root=. run --target=sim $$CORE_VLNV

## @section Clean
## Remove all build artifacts
clean:
	rm -rf build/
	rm -f $(FUSESOC_CORE_FILE)

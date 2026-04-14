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

## @config ASIC standard cell library
## @param LIB Path to the .lib file for synthesis
LIB ?= $(abspath $(MAKEFILE_DIR)/../../../repository/do/libnandgate/NangateOpenCellLibrary_typical_ecsm.lib)

# ── Targets ─────────────────────────────────────────────────────────────────────
.PHONY: help env test

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
## After the environment is created, install pNVC
env:
	@bash "$(MAKEFILE_DIR)/utils/MakeConda"
	@bash "$(MAKEFILE_DIR)/utils/MakeYosys"

## Execute the test flow: scan TARGET for "sim" dirs and run Python runner
## @param TARGET Path to the exercise directory
## @param LIB Path to the .lib file
test:
	@ASIC_LIB="$(LIB)" python3 "$(MAKEFILE_DIR)/src/run_tests.py" "$(TARGET)"
	echo $(MAKEFILE_DIR)
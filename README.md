
# VHDL-FastCheck

VHDL-FastCheck is a toolkit for quickly running VHDL checks and test flows using only open source tools:

- [GHDL](https://ghdl.github.io/ghdl/) for simulation
- [Yosys](https://yosyshq.net/yosys/) for synthesis

It provides lightweight Python runners and Makefile helpers to automate simulation and synthesis checks for VHDL projects.


## Features

- Automates VHDL simulation with GHDL
- Automates synthesis checks with Yosys
- Simple Python scripts and Makefile helpers
- 100% open source dependencies



## Installation

Clone this repository:

```sh
git clone https://github.com/yourusername/vhdl-fastcheck.git
cd vhdl-fastcheck
```



## Usage

### Makefile-based workflow

- **Show help:**
	```sh
	make help
	```
	Prints a summary of available Makefile targets and usage instructions.

- **Set up the environment:**
	```sh
	make env
	```
	Downloads and installs open source tools (Yosys & GHDL) and sets up your shell environment.  
	**Note:** You may need to restart your terminal or source your shell rc file to update your PATH.

- **Run all tests:**
	```sh
	make test TARGET=<path-to-your-vhdl-project>
	```
	- `TARGET` is the path to the directory containing your VHDL project or exercises.
	- Optionally, set `LIB` to specify a custom standard cell library for synthesis.


## Output

- **make test** (or `run_tests.py`):
	- For each subdirectory named `sim` or `syn` under your target, runs simulation (GHDL) or synthesis (Yosys).
	- **Simulation output**: Console output from GHDL, including compile logs, testbench results, and pass/fail status for each test. Errors are clearly marked.
	- **Synthesis output**: Console output from Yosys, including synthesis logs, resource usage, and any warnings or errors. If a standard cell library is used, timing and area reports may be included.
	- At the end, a summary of all test results is printed. Errors are reported with details for debugging.
	- A file named `test_results.json` is written in the target directory, containing a summary of all results.

- **Python runners**: Each runner prints detailed logs to the console, including which files are being processed, any dependency analysis, and the results of each simulation or synthesis step. Errors and warnings are clearly indicated.

All outputs are printed to the terminal. For more details, check the logs and error messages printed by each tool.

### Example output JSON (`test_results.json`)

```json
{
	"dir": "~/myproject",
	"tasks": {
		"ex1/sim": {
			"compile": { "ok": true },
			"run": { "ok": true, "result": "PASS" }
		},
		"ex1/syn": {
			"compile": { "ok": true },
			"synth": { "ok": true, "area": 123, "timing": "OK" }
		},
		"ex2/sim": {
			"compile": { "ok": false, "error": "Syntax error" }
		}
	}
}
```

Each key in `tasks` is a subdirectory tested. Each value contains the results for that directory, including compile status, run/synth results, and any errors.


## Repository layout

- `src/` — Python runners and helpers
- `utils/` — Make helpers for Yosys and other tooling

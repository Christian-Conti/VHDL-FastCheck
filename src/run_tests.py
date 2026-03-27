#!/usr/bin/env python3
import argparse
import json
import subprocess
import sys
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed

# ANSI color codes for terminal output
GREEN = '\033[92m'
RED = '\033[91m'
RESET = '\033[0m'

# Log prefix
TAG = '[run_tests]'
def info(msg: str) -> None:
    print(f"{TAG} {msg}")
def error(msg: str) -> None:
    print(f"{TAG} [ERROR] {msg}", file=sys.stderr)


def find_work_dirs(target: Path):
    work_dirs = []
    for p in target.rglob('*'):
        if p.is_dir() and ('sim' in p.name.lower() or 'syn' in p.name.lower()):
            work_dirs.append(p)
    # also consider immediate children (likely already included by rglob)
    for p in target.iterdir():
        if p.is_dir() and ('sim' in p.name.lower() or 'syn' in p.name.lower()) and p not in work_dirs:
            work_dirs.append(p)
    return sorted(work_dirs)


def run_runner(work_dir: Path, base_path: Path):
    # Determine the correct runner script based on directory name
    if 'sim' in work_dir.name.lower():
        runner_script = base_path / 'ghdl_runner.py'
    else:
        runner_script = base_path / 'yosys_runner.py'

    # Open a subprocess for the simulation or synthesis
    cmd = [sys.executable, str(runner_script), str(work_dir)]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # Runners print JSON to standard output
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            data = {"error": "Invalid JSON output", "stdout": r.stdout, "stderr": r.stderr}
        return work_dir, data, r.returncode
    except Exception as e:
        return work_dir, {"error": str(e)}, 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument('target_dir')
    args = p.parse_args()

    target = Path(args.target_dir).resolve()
    if not target.exists() or not target.is_dir():
        error(f"target not found: {target}")
        sys.exit(2)

    base_path = Path(__file__).parent
    work_dirs = find_work_dirs(target)

    results = {"dir": _display_path(str(target)), "tasks": {}}

    total = len(work_dirs)
    passed = 0
    failed_tasks = []

    # Run processes concurrently
    futures = []
    with ThreadPoolExecutor() as executor:
        for w in work_dirs:
            futures.append(executor.submit(run_runner, w, base_path))

        for future in as_completed(futures):
            w, data, rc = future.result()
            
            try:
                rel = str(w.relative_to(target))
            except Exception:
                rel = str(w)

            is_ok = False
            if isinstance(data, dict):
                data.pop("elaborate", None)
                data.pop("sim_dir", None)
                data.pop("syn_dir", None)
                
                compile_info = data.get("compile", {})
                is_ok = compile_info.get("ok", False)

            if is_ok and rc == 0:
                passed += 1
            else:
                failed_tasks.append(rel)

            results["tasks"][rel] = data

    # Determine color based on pass rate
    if total > 0 and passed == total:
        color = GREEN
    else:
        color = RED

    # Print requested output
    info(f"{color}[RESULT] {_display_path(str(target))} ({passed}/{total}){RESET}")
    
    if failed_tasks:
        for f in sorted(failed_tasks):
            error(f"- {f} failed")

    out_file = target / 'test_results.json'
    out_file.write_text(json.dumps(results, indent=2))


def _display_path(path_str: str) -> str:
    # Replace home prefix with ~ for readability
    try:
        home = str(Path.home())
        if path_str.startswith(home):
            return path_str.replace(home, '~', 1)
    except Exception:
        pass
    return path_str


if __name__ == '__main__':
    main()

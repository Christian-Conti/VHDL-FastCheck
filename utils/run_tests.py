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


def find_sim_dirs(target: Path):
    sims = []
    for p in target.rglob('*'):
        if p.is_dir() and 'sim' in p.name.lower():
            sims.append(p)
    # also consider immediate children (likely already included by rglob)
    for p in target.iterdir():
        if p.is_dir() and 'sim' in p.name.lower() and p not in sims:
            sims.append(p)
    return sorted(sims)


def run_runner(sim_dir: Path, runner_script: Path):
    # Open a subprocess for the simulation
    cmd = [sys.executable, str(runner_script), str(sim_dir)]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
        # nvc_runner prints JSON to standard output
        try:
            data = json.loads(r.stdout)
        except json.JSONDecodeError:
            data = {"error": "Invalid JSON output", "stdout": r.stdout, "stderr": r.stderr}
        return sim_dir, data, r.returncode
    except Exception as e:
        return sim_dir, {"error": str(e)}, 1


def main():
    p = argparse.ArgumentParser()
    p.add_argument('target_dir')
    args = p.parse_args()

    target = Path(args.target_dir).resolve()
    if not target.exists() or not target.is_dir():
        print(f"{RED}[ERROR] target not found: {target}{RESET}")
        sys.exit(2)

    runner_script = Path(__file__).parent / 'nvc_runner.py'
    sims = find_sim_dirs(target)

    results = {"dir": _display_path(str(target)), "sims": {}}

    total = len(sims)
    passed = 0
    failed_sims = []

    # Run processes concurrently
    futures = []
    with ThreadPoolExecutor() as executor:
        for s in sims:
            futures.append(executor.submit(run_runner, s, runner_script))

        for future in as_completed(futures):
            s, data, rc = future.result()
            
            try:
                rel = str(s.relative_to(target))
            except Exception:
                rel = str(s)

            is_ok = False
            if isinstance(data, dict):
                data.pop("elaborate", None)
                data.pop("sim_dir", None)
                
                compile_info = data.get("compile", {})
                is_ok = compile_info.get("ok", False)

            if is_ok and rc == 0:
                passed += 1
            else:
                failed_sims.append(rel)

            results["sims"][rel] = data

    # Determine color based on pass rate
    if total > 0 and passed == total:
        color = GREEN
    else:
        color = RED

    # Print requested output
    print(f"{color}[RESULT] {_display_path(str(target))} ({passed}/{total}){RESET}")
    
    if failed_sims:
        for f in sorted(failed_sims):
            print(f"{RED}  - {f} failed{RESET}")

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

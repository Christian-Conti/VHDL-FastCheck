#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import subprocess
import sys
from pathlib import Path


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


def run_runner(sim_dir: Path, runner_script: Path, progress_cb=None):
    # Import ghdl_runner as a module from file so we can call process_sim directly and get progress
    import importlib.util
    spec = importlib.util.spec_from_file_location("ghdl_runner", str(runner_script))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    # mod.process_sim(sim_dir, progress_callback)
    data, rc = mod.process_sim(sim_dir, progress_callback=progress_cb)
    return data, rc


def main():
    p = argparse.ArgumentParser()
    p.add_argument('target_dir')
    args = p.parse_args()

    target = Path(args.target_dir).resolve()
    if not target.exists() or not target.is_dir():
        print(f"[ERROR] target not found: {target}")
        sys.exit(2)

    runner_script = Path(__file__).parent / 'ghdl_runner.py'
    sims = find_sim_dirs(target)

    results = {"dir": _display_path(str(target)), "sims": {}}

    total = len(sims)
    for idx, s in enumerate(sims, start=1):
        # use path relative to target as key
        try:
            rel = str(s.relative_to(target))
        except Exception:
            rel = str(s)
        print(f"[{idx}/{total}] Processing {rel}")

        def progress_cb(percent, message):
            bar_len = 40
            filled = int(percent * bar_len / 100)
            bar = '=' * filled + ' ' * (bar_len - filled)
            print(f"\r  [{bar}] {percent:3d}% - {message}", end='', flush=True)

        data, rc = run_runner(s, runner_script, progress_cb)
        print()  # newline after progress bar

        # Normalize returned data: drop elaborate if present (ghdl_runner already sets top/files/compile)
        try:
            if isinstance(data, dict):
                data.pop("elaborate", None)
                data.pop("sim_dir", None)
        except Exception:
            pass

        # Use relative-to-target path as key to avoid duplicate 'sim' names
        results["sims"][rel] = data

    out_file = target / 'test_results.json'
    out_file.write_text(json.dumps(results, indent=2))
    print(f"Wrote results to {out_file}")


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

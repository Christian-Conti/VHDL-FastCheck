#!/usr/bin/env python3
from __future__ import annotations
import argparse
import json
import os
import re
import subprocess
import tempfile
import sys
from pathlib import Path

# Ensure local utils can be imported when script is run directly
sys.path.insert(0, str(Path(__file__).parent))
try:
    import generate_core
except Exception:
    # If import fails, we still try to use local resolver fallback
    generate_core = None


def find_entities(file_list: list[str]) -> list[str]:
    ents = []
    re_ent = re.compile(r'entity\s+(\w+)', re.IGNORECASE)
    for f in file_list:
        try:
            txt = Path(f).read_text(encoding='utf-8', errors='ignore')
            # strip comments
            txt = re.sub(r'--.*', '', txt)
            for m in re_ent.findall(txt):
                en = m.strip()
                if en and en not in ents:
                    ents.append(en)
        except Exception:
            continue
    return ents


def run_ghdl_analyze(files: list[str]):
    logs = []
    for f in files:
        cmd = ["ghdl", "-a", "--std=08", f]
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except FileNotFoundError:
            return False, "ghdl not found in PATH", '\n'.join(logs)
        logs.append(f"$ {' '.join(cmd)}\n{r.stdout}")
        if r.returncode != 0:
            return False, f"analysis failed for {f}", '\n'.join(logs)
    return True, "analysis OK", '\n'.join(logs)


def run_ghdl_elaborate(top: str):
    cmd = ["ghdl", "-e", "--std=08", top]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError:
        return False, "ghdl not found in PATH", ''
    return (r.returncode == 0), r.stdout, ' '.join(cmd)


def process_sim(sim_path: Path, progress_callback=None):
    """Process a simulation directory. Calls progress_callback(percent:int, message:str) if provided.
    Returns (result_dict, returncode).
    """
    sim_path = Path(sim_path).resolve()
    if not sim_path.exists() or not sim_path.is_dir():
        return {"error": f"sim dir not found: {sim_path}"}, 2

    # find VHDL files in order using generate_core resolver if available
    if generate_core is not None:
        try:
            files = generate_core.find_hdl_files(sim_path)
        except Exception:
            files = [str(p) for p in sim_path.rglob('*.vhd') if p.is_file()]
    else:
        files = [str(p) for p in sim_path.rglob('*.vhd') if p.is_file()]

    files = [str(Path(f).resolve()) for f in files]

    # Create hierarchical-sorted file list (relative to sim_path) and present only basenames
    rel_paths = [Path(f).relative_to(sim_path) for f in files]
    rel_sorted = sorted(rel_paths, key=lambda p: p.parts)
    basenames = []
    for p in rel_sorted:
        name = p.name
        if name not in basenames:
            basenames.append(name)

    result = {"sim_dir": str(sim_path), "files": basenames, "top": None, "compile": {}}

    if not files:
        result["compile"]["ok"] = False
        result["compile"]["error"] = "no .vhd files found"
        if progress_callback:
            progress_callback(100, "no .vhd files found")
        return result, 0

    entities = find_entities(files)

    # Heuristic for top:
    # 1) prefer an entity whose name contains 'tb' (testbench),
    # 2) else prefer entity matching folder name,
    # 3) else prefer first entity not containing 'tb',
    # 4) else first available entity.
    top = None
    # 1) tb-containing entity
    tb_entities = [e for e in entities if 'tb' in e.lower()]
    if tb_entities:
        top = tb_entities[0]
    else:
        # 2) folder match
        folder_name = sim_path.name.lower()
        for e in entities:
            if e.lower() == folder_name:
                top = e
                break
        # 3) first non-tb
        if top is None:
            non_tb = [e for e in entities if 'tb' not in e.lower()]
            if non_tb:
                top = non_tb[0]
            elif entities:
                top = entities[0]

    result["top"] = top

    # Analyze files with progress callback
    logs = []
    total = len(files)
    # Use filenames relative to sim_path for ghdl invocation
    local_files = [str(Path(f).relative_to(sim_path)) for f in files]

    # Create temporary HOME to avoid using user's ~/.config
    with tempfile.TemporaryDirectory() as tmp_home:
        cfg_dir = Path(tmp_home) / '.config' / 'ghdl'
        cfg_dir.mkdir(parents=True, exist_ok=True)
        cfg_file = cfg_dir / 'config'
        if not cfg_file.exists():
            cfg_file.write_text('')

        env = os.environ.copy()
        env['HOME'] = tmp_home

        for i, local_f in enumerate(local_files, start=1):
            if progress_callback:
                pct = int((i - 1) / total * 100)
                progress_callback(pct, f"Analyzing {Path(local_f).name} ({i}/{total})")
            cmd = ["ghdl", "-a", "--std=08", local_f]
            try:
                r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(sim_path), env=env)
            except FileNotFoundError:
                result["compile"]["ok"] = False
                result["compile"]["error"] = "ghdl not found in PATH"
                result["compile"]["log"] = '\n'.join(logs)
                if progress_callback:
                    progress_callback(100, "ghdl not found in PATH")
                return result, 1
            logs.append(f"$ {' '.join(cmd)}\n{r.stdout}")
            if r.returncode != 0:
                result["compile"]["ok"] = False
                result["compile"]["message"] = f"analysis failed for {str(sim_path / local_f)}"
                result["compile"]["log"] = '\n'.join(logs)
                if progress_callback:
                    progress_callback(100, f"analysis failed for {Path(local_f).name}")
                return result, 1

    result["compile"]["ok"] = True
    result["compile"]["message"] = "analysis OK"
    result["compile"]["log"] = '\n'.join(logs)

    if progress_callback:
        progress_callback(100, "done")

    return result, 0


def main():
    p = argparse.ArgumentParser()
    p.add_argument('sim_dir')
    args = p.parse_args()

    sim_path = Path(args.sim_dir).resolve()
    if not sim_path.exists() or not sim_path.is_dir():
        print(json.dumps({"error": f"sim dir not found: {sim_path}"}))
        sys.exit(2)

    res, rc = process_sim(sim_path)
    print(json.dumps(res))
    sys.exit(rc)


if __name__ == '__main__':
    main()

#!/usr/bin/env python3
import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Ensure local utils can be imported when script is run directly
sys.path.insert(0, str(Path(__file__).parent))
try:
    import generate_core
except Exception:
    # If import fails, we still try to use local resolver fallback
    generate_core = None


def find_top_entity(file_list: list[str]) -> str | None:
    """
    Builds a dependency graph by finding all defined entities and all instantiated
    entities across the files
    
    Returns the top entity (a root node in the hierarchy that is never instantiated)
    """
    # Regex to find entity definitions
    re_entity = re.compile(r'^\s*entity\s+(\w+)', re.IGNORECASE | re.MULTILINE)
    
    # Regex to find component/entity instantiations
    # Matches: label : [entity work.]name [generic map | port map]
    re_inst = re.compile(r':\s*(?:entity\s+(?:\w+\.)?)?(\w+)\s+(?:generic\s+map|port\s+map)', re.IGNORECASE)

    defined_entities = {}
    instantiated_entities = set()

    for f in file_list:
        try:
            txt = Path(f).read_text(encoding='utf-8', errors='ignore')
            # Strip comments to avoid false positives
            txt = re.sub(r'--.*', '', txt)
            
            # Register defined entities
            for match in re_entity.findall(txt):
                defined_entities[match.lower()] = match
                
            # Register instantiated components/entities
            for match in re_inst.findall(txt):
                instantiated_entities.add(match.lower())
        except Exception:
            continue

    # The top candidates are entities that are defined but never instantiated
    top_candidates = []
    for lower_name, original_name in defined_entities.items():
        if lower_name not in instantiated_entities:
            top_candidates.append(original_name)

    # Fallback if the graph is somehow empty or circular
    if not top_candidates:
        if defined_entities:
            return list(defined_entities.values())[0]
        return None

    # Sort alphabetically to guarantee a deterministic selection if multiple 
    # uninstantiated entities exist in the same test directory
    top_candidates.sort()
    return top_candidates[0]


def run_nvc_analyze(files: list[str]):
    logs = []
    for f in files:
        cmd = ["nvc", "-a", f]
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        except FileNotFoundError:
            return False, "nvc not found in PATH", '\n'.join(logs)
        logs.append(f"$ {' '.join(cmd)}\n{r.stdout}")
        if r.returncode != 0:
            return False, f"analysis failed for {f}", '\n'.join(logs)
    return True, "analysis OK", '\n'.join(logs)


def run_nvc_elaborate(top: str):
    cmd = ["nvc", "-e", top]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError:
        return False, "nvc not found in PATH", ''
    return (r.returncode == 0), r.stdout, ' '.join(cmd)


def process_sim(sim_path: Path, progress_callback=None):
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

    # Retrieve the top entity mathematically instead of using a heuristic
    top = find_top_entity(files)
    result["top"] = top

    # Analyze files with progress callback
    logs = []
    total = len(files)
    # Use filenames relative to sim_path for nvc invocation
    local_files = [str(Path(f).relative_to(sim_path)) for f in files]

    env = os.environ.copy()

    for i, local_f in enumerate(local_files, start=1):
        if progress_callback:
            pct = int((i - 1) / total * 100)
            progress_callback(pct, f"Analyzing {Path(local_f).name} ({i}/{total})")
        
        cmd = ["nvc", "-a", local_f]
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(sim_path), env=env)
        except FileNotFoundError:
            result["compile"]["ok"] = False
            result["compile"]["error"] = "nvc not found in PATH"
            result["compile"]["log"] = '\n'.join(logs)
            if progress_callback:
                progress_callback(100, "nvc not found in PATH")
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
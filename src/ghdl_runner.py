#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

# Runner: GHDL
sys.path.insert(0, str(Path(__file__).parent))
try:
    import generate_core
except Exception:
    generate_core = None

# Log helpers
TAG = '[ghdl_runner]'
def info(msg: str) -> None:
    print(f"{TAG} {msg}", file=sys.stderr)
def error(msg: str) -> None:
    print(f"{TAG} [ERROR] {msg}", file=sys.stderr)


def get_dependencies(file_list: list[str]):
    re_prov_entity = re.compile(r'^\s*entity\s+(\w+)', re.IGNORECASE | re.MULTILINE)
    re_prov_pkg = re.compile(r'^\s*package\s+(?!body\b)(\w+)', re.IGNORECASE | re.MULTILINE)

    # Use DOTALL to match newlines between component name and generic/port map
    re_req_inst = re.compile(r':\s*(?:entity\s+(?:\w+\.)?)?(\w+)\s+(?:generic|port)\s+map', re.IGNORECASE | re.DOTALL)
    re_req_use = re.compile(r'^\s*use\s+(?:\w+\.)?(\w+)', re.IGNORECASE | re.MULTILINE)
    re_req_arch = re.compile(r'^\s*architecture\s+\w+\s+of\s+(\w+)', re.IGNORECASE | re.MULTILINE)
    re_req_pkg_body = re.compile(r'^\s*package\s+body\s+(\w+)', re.IGNORECASE | re.MULTILINE)

    provides = {}
    requires = {}

    for f in file_list:
        try:
            txt = Path(f).read_text(encoding='utf-8', errors='ignore')
            txt = re.sub(r'--.*', '', txt)

            prov = set(m.lower() for m in re_prov_entity.findall(txt))
            prov.update(m.lower() for m in re_prov_pkg.findall(txt))

            req = set(m.lower() for m in re_req_inst.findall(txt))
            req.update(m.lower() for m in re_req_use.findall(txt))
            req.update(m.lower() for m in re_req_arch.findall(txt))
            req.update(m.lower() for m in re_req_pkg_body.findall(txt))
            req = req - prov

            provides[f] = prov
            requires[f] = req
        except Exception:
            provides[f] = set()
            requires[f] = set()

    dependencies = {f: set() for f in file_list}
    for f, reqs in requires.items():
        for f_dep, provs in provides.items():
            if f != f_dep and reqs.intersection(provs):
                dependencies[f].add(f_dep)

    return provides, dependencies


def find_top_entity(file_list: list[str], provides: dict, dependencies: dict) -> str | None:
    is_dependency_of = set()
    for deps in dependencies.values():
        is_dependency_of.update(deps)

    potential_top_files = set(file_list) - is_dependency_of

    if not potential_top_files:
        if file_list:
            return None
        return None

    # Sort candidates, giving priority to files containing 'tb' to guarantee deterministic results
    sorted_tops = sorted(list(potential_top_files), key=lambda x: (0 if 'tb' in Path(x).name.lower() else 1, x.lower()))
    top_file = sorted_tops[0]

    entities_in_top = sorted(list(provides[top_file]))
    if entities_in_top:
        txt = Path(top_file).read_text(encoding='utf-8', errors='ignore')
        # Try to extract the original case formatting of the entity
        for ent in entities_in_top:
            match = re.search(rf'entity\s+({ent})', txt, re.IGNORECASE)
            if match:
                return match.group(1)
        return entities_in_top[0]

    return None


def sort_files_by_dependency(file_list: list[str], dependencies: dict) -> list[str]:
    sorted_files = []
    visited = set()
    temp_mark = set()

    def visit(n):
        if n in temp_mark:
            return
        if n not in visited:
            temp_mark.add(n)
            for dep in sorted(dependencies.get(n, set())):
                visit(dep)
            temp_mark.remove(n)
            visited.add(n)
            sorted_files.append(n)

    for f in sorted(file_list):
        if f not in visited:
            visit(f)

    return sorted_files


def run_ghdl_elaborate(top: str):
    cmd = ["ghdl", "-e", "--std=08", "-fsynopsys", top]
    try:
        r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    except FileNotFoundError:
        return False, "ghdl not found in PATH", ''
    return (r.returncode == 0), r.stdout, ' '.join(cmd)


def process_sim(sim_path: Path, progress_callback=None):
    sim_path = Path(sim_path).resolve()
    if not sim_path.exists() or not sim_path.is_dir():
        return {"error": f"sim dir not found: {sim_path}"}, 2

    if generate_core is not None:
        try:
            files = generate_core.find_hdl_files(sim_path)
        except Exception:
            files = [str(p) for p in sim_path.rglob('*.vhd') if p.is_file()]
    else:
        files = [str(p) for p in sim_path.rglob('*.vhd') if p.is_file()]

    files = [str(Path(f).resolve()) for f in files]

    if not files:
        result = {"sim_dir": str(sim_path), "files": [], "top": None, "compile": {}}
        result["compile"]["ok"] = False
        result["compile"]["error"] = "no .vhd files found"
        if progress_callback:
            progress_callback(100, "no .vhd files found")
        return result, 0

    provides, dependencies = get_dependencies(files)
    top = find_top_entity(files, provides, dependencies)
    files = sort_files_by_dependency(files, dependencies)

    rel_paths = [Path(f).relative_to(sim_path) for f in files]
    basenames = []
    for p in rel_paths:
        name = p.name
        if name not in basenames:
            basenames.append(name)

    result = {"sim_dir": str(sim_path), "files": basenames, "top": top, "compile": {}}

    total = len(files)
    local_files = [str(Path(f).relative_to(sim_path)) for f in files]

    env = os.environ.copy()


    for i, local_f in enumerate(local_files, start=1):
        if progress_callback:
            pct = int((i - 1) / total * 100)
            progress_callback(pct, f"Analyzing {Path(local_f).name} ({i}/{total})")

        cmd = ["ghdl", "-a", "--std=08", "-fsynopsys", local_f]
        try:
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(sim_path), env=env)
        except FileNotFoundError:
            result["compile"]["ok"] = False
            result["compile"]["error"] = "ghdl not found in PATH"
            result["compile"]["log"] = "ghdl not found in PATH"
            if progress_callback:
                progress_callback(100, "ghdl not found in PATH")
            return result, 1

        if r.returncode != 0:
            result["compile"]["ok"] = False
            result["compile"]["message"] = f"analysis failed for {str(sim_path / local_f)}"
            result["compile"]["log"] = r.stdout
            if progress_callback:
                progress_callback(100, f"analysis failed for {Path(local_f).name}")
            return result, 1

    result["compile"]["ok"] = True
    result["compile"]["message"] = "analysis OK"

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
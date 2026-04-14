#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path

def find_top_entity(file_list: list[str]) -> str | None:
    re_entity = re.compile(r'^\s*entity\s+(\w+)', re.IGNORECASE | re.MULTILINE)
    re_inst = re.compile(r':\s*(?:entity\s+(?:\w+\.)?)?(\w+)\s+(?:generic\s+map|port\s+map)', re.IGNORECASE)
    defined_entities = {}
    instantiated_entities = set()
    
    for f in file_list:
        try:
            txt = Path(f).read_text(encoding='utf-8', errors='ignore')
            txt = re.sub(r'--.*', '', txt)
            for match in re_entity.findall(txt):
                defined_entities[match.lower()] = match
            for match in re_inst.findall(txt):
                instantiated_entities.add(match.lower())
        except Exception: 
            continue
            
    top_candidates = [orig for low, orig in defined_entities.items() if low not in instantiated_entities]
    if not top_candidates: 
        return list(defined_entities.values())[0] if defined_entities else None
    
    top_candidates.sort()
    return top_candidates[0]

def sort_files_by_dependency(file_list: list[str]) -> list[str]:
    re_provides = re.compile(r'^\s*(?:entity|package)\s+(?!body\b)(\w+)', re.IGNORECASE | re.MULTILINE)
    re_requires = re.compile(r'(?:package\s+body\s+|:\s*(?:entity\s+(?:\w+\.)?)?|use\s+(?:\w+\.)?|architecture\s+\w+\s+of\s+)(\w+)', re.IGNORECASE | re.MULTILINE)
    provides, requires = {}, {}
    
    for f in file_list:
        try:
            txt = Path(f).read_text(encoding='utf-8', errors='ignore')
            txt = re.sub(r'--.*', '', txt)
            prov = set(m.lower() for m in re_provides.findall(txt))
            req = set(m.lower() for m in re_requires.findall(txt)) - prov
            provides[f], requires[f] = prov, req
        except Exception: 
            provides[f], requires[f] = set(), set()
            
    dependencies = {f: set() for f in file_list}
    for f, reqs in requires.items():
        for f_dep, provs in provides.items():
            if f != f_dep and reqs.intersection(provs): 
                dependencies[f].add(f_dep)
                
    sorted_files, visited, temp = [], set(), set()
    
    def visit(n):
        if n in temp or n in visited: return
        temp.add(n)
        for d in sorted(dependencies.get(n, set())): 
            visit(d)
        temp.remove(n)
        visited.add(n)
        sorted_files.append(n)
        
    for f in sorted(file_list): 
        visit(f)
    return sorted_files

def process_syn(syn_path: Path):
    syn_path = syn_path.resolve()
    files = [str(p.resolve()) for p in syn_path.rglob('*.vhd') if p.is_file()]
    top = find_top_entity(files)
    files = sort_files_by_dependency(files)
    local_files = [str(Path(f).relative_to(syn_path)) for f in files]
    
    lib_str = os.environ.get("ASIC_LIB", "").strip()
    tmp_unmapped_blif = "__unmapped_netlist.blif"
    
    res = {
        "syn_dir": str(syn_path),
        "top": top,
        "compile": {"ok": True, "message": "Synthesis OK"},
        "metrics": {"area_um2": float('nan'), "cp_ns": float('nan')}
    }

    # Step 1: Yosys logic mapping and area extraction
    yosys_cmds = [
        f"ghdl --std=08 -fsynopsys {' '.join(local_files)} -e {top}",
        f"synth -top {top}",
        "flatten",
        "design -save pre_map",
        "techmap -map +/adff2dff.v",
        "dffunmap",
        "opt_clean -purge",
        f"write_blif {tmp_unmapped_blif}",
        "design -load pre_map",
        f"dfflibmap -liberty {lib_str}", 
        f"abc -liberty {lib_str}", 
        "opt_clean -purge",
        f"stat -liberty {lib_str}" 
    ]

    r_yosys = subprocess.run(
        ["yosys", "-m", "ghdl", "-p", "; ".join(yosys_cmds)], 
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(syn_path)
    )
    (syn_path / "yosys_synth.log").write_text(r_yosys.stdout, encoding='utf-8')
    final_stdout = r_yosys.stdout

    # Step 2: ABC standalone timing extraction
    abc_cmds = f"read_lib -w {lib_str}; read_blif {tmp_unmapped_blif}; strash; map; topo; stime"
    r_abc = subprocess.run(
        ["yosys-abc", "-c", abc_cmds], 
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, cwd=str(syn_path)
    )
    (syn_path / "abc_timing.log").write_text(r_abc.stdout, encoding='utf-8')
    final_stdout += "\n" + r_abc.stdout
    
    # Cleanup temp file
    if (syn_path / tmp_unmapped_blif).exists():
        (syn_path / tmp_unmapped_blif).unlink()

    # Metrics Extraction
    am = re.search(r"Chip area for module.*?:\s*([0-9.]+)", final_stdout)
    if am and float(am.group(1)) > 0: 
        res["metrics"]["area_um2"] = float(am.group(1))
    
    abcm = re.search(r"Delay\s*=\s*([0-9.]+)", final_stdout, re.IGNORECASE)
    if abcm and float(abcm.group(1)) > 0:
        res["metrics"]["cp_ns"] = round(float(abcm.group(1)) / 1000.0, 3)

    return res, 0

def main():
    p = argparse.ArgumentParser()
    p.add_argument('syn_dir')
    args = p.parse_args()
    
    res, rc = process_syn(Path(args.syn_dir))
    print(json.dumps(res, indent=2))
    sys.exit(rc)

if __name__ == '__main__':
    main()
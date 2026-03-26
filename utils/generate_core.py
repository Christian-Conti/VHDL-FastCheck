#!/usr/bin/env python3
from __future__ import annotations
import argparse
import os
import sys
import re
from pathlib import Path
from collections import defaultdict

HDL_EXTS = {'.v', '.sv', '.vh', '.svh', '.vhd', '.vhdl'}

def get_file_type(filepath: str) -> str:
    ext = os.path.splitext(filepath)[1].lower()
    if ext in ['.vhd', '.vhdl']:
        return 'vhdlSource-2008'
    if ext in ['.sv', '.svh']:
        return 'systemVerilogSource'
    return 'verilogSource'

class VHDLDependencyResolver:
    """Parses VHDL files to determine compilation order including Configurations."""
    
    def __init__(self):
        self.provides = {} # unit name -> file path
        self.requires = defaultdict(set) # file path -> set of unit names
        
        # Improved Regex: Catch definitions anywhere (not just start of line)
        self.re_provide = re.compile(r'(?:entity|package|configuration)\s+(\w+)', re.IGNORECASE)
        # Catch any 'work.name' usage
        self.re_use_work = re.compile(r'work\.(\w+)', re.IGNORECASE)

    def scan_file(self, filepath: str):
        try:
            with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Strip comments to prevent false dependencies
                content = re.sub(r'--.*', '', content)
                
                # Find what this file provides
                provides = self.re_provide.findall(content)
                for unit in provides:
                    self.provides[unit.lower()] = filepath
                
                # Find what this file requires from 'work'
                requires = self.re_use_work.findall(content)
                for unit in requires:
                    self.requires[filepath].add(unit.lower())
        except Exception as e:
            print(f"[WARN] Could not parse {filepath}: {e}")

    def resolve_order(self, file_list: list[str]) -> list[str]:
        for f in file_list:
            if get_file_type(f).startswith('vhdl'):
                self.scan_file(f)

        graph = defaultdict(set)
        for requester_file, units in self.requires.items():
            for unit in units:
                if unit in self.provides:
                    provider_file = self.provides[unit]
                    if provider_file != requester_file:
                        graph[requester_file].add(provider_file)

        sorted_files = []
        visited = set()
        temp_stack = set()

        def visit(f):
            if f in temp_stack: return
            if f not in visited:
                temp_stack.add(f)
                for dep in sorted(list(graph[f])):
                    visit(dep)
                temp_stack.remove(f)
                visited.add(f)
                sorted_files.append(f)

        for f in sorted(file_list):
            visit(f)

        return sorted_files

def find_hdl_files(root: Path):
    raw_list = [str(p) for p in root.rglob('*') if p.suffix.lower() in HDL_EXTS and p.is_file()]
    resolver = VHDLDependencyResolver()
    return resolver.resolve_order(raw_list)

def find_tb_files(tb_name: str, workspace: Path):
    candidates = []
    src_root = workspace / 'src'
    if '-' in tb_name:
        dir_part, file_part = tb_name.split('-', 1)
        file_stem = 'tb_' + file_part.replace('-', '_')
        search_dir = src_root / dir_part.lower()
        if search_dir.exists():
            for p in sorted(search_dir.rglob('*')):
                if p.is_file() and p.suffix.lower() in HDL_EXTS and (p.stem == file_stem or p.stem.startswith(file_stem)):
                    candidates.append(str(p))
    
    if not candidates:
        src_dir = src_root / tb_name
        if src_dir.exists():
            candidates = [str(p) for p in src_dir.rglob('*') if p.suffix.lower() in HDL_EXTS]

    resolver = VHDLDependencyResolver()
    return resolver.resolve_order(candidates)

def render_template(template_path: Path, core_name: str, entity_name: str, dut_files: list, tb_files: list):
    try:
        from mako.template import Template
    except ImportError:
        print('[ERROR] Mako is required.', file=sys.stderr)
        sys.exit(1)

    dut_data = [(f, get_file_type(f)) for f in dut_files]
    tb_data = [(f, get_file_type(f)) for f in tb_files]

    tpl = Template(template_path.read_text())
    return tpl.render(core_name=core_name, entity_name=entity_name, dut_files=dut_data, tb_files=tb_data)

def main():
    p = argparse.ArgumentParser()
    p.add_argument('target_dir')
    p.add_argument('tb_name')
    p.add_argument('--template', '-t', default='fusesoc.core.tpl')
    p.add_argument('--out', '-o', default='fusesoc.core')
    args = p.parse_args()

    workspace = Path.cwd()
    target = Path(args.target_dir)

    dut_files_abs = find_hdl_files(target)
    tb_files_abs = find_tb_files(args.tb_name, workspace)

    dut_files = [os.path.relpath(p, workspace) for p in dut_files_abs]
    tb_files = [os.path.relpath(p, workspace) for p in tb_files_abs]

    if '-' in args.tb_name:
        entity_name = f"TB_{args.tb_name.split('-', 1)[1].replace('-', '_').upper()}"
    else:
        entity_name = args.tb_name

    core_name = target.name.replace('.', '_')
    rendered = render_template(workspace / args.template, core_name, entity_name, dut_files, tb_files)
    Path(args.out).write_text(rendered)
    
    print(f'[INFO] Core generated with order:')
    for i, f in enumerate(dut_files):
        print(f"  {i+1}: {os.path.basename(f)}")

if __name__ == '__main__':
    main()

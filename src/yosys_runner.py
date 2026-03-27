#!/usr/bin/env python3
import os
import sys
import subprocess
from mako.template import Template

def run_yosys_flow(entity_name, vhd_files, core_name="design_core"):
    print("[yosys_runner] Starting Yosys synthesis preparation...")

    dut_files = []
    for f in vhd_files:
        dut_files.append((f, "vhdlSource-2008"))

    tb_files = []

    tpl_path = "fusesoc.core.tpl"
    out_core_path = f"{core_name}.core"

    if not os.path.exists(tpl_path):
        print(f"[yosys_runner] Error: Template file '{tpl_path}' not found.")
        sys.exit(1)

    print(f"[yosys_runner] Rendering template {tpl_path} into {out_core_path}...")
    try:
        template = Template(filename=tpl_path)
        rendered_core = template.render(
            core_name=core_name,
            entity_name=entity_name,
            dut_files=dut_files,
            tb_files=tb_files
        )
    except Exception as e:
        print(f"[yosys_runner] Template rendering failed: {e}")
        sys.exit(1)

    with open(out_core_path, "w") as f:
        f.write(rendered_core)

    print("[yosys_runner] Executing FuseSoC for Yosys synthesis...")
    cmd = [
        "fusesoc",
        "--cores-root", ".",
        "run",
        "--target=syn",
        f"vlsi_lab:ms:{core_name}"
    ]

    print(f"[yosys_runner] Running command: {' '.join(cmd)}")
    try:
        subprocess.run(cmd, check=True)
        print("[yosys_runner] Yosys synthesis completed successfully.")
    except subprocess.CalledProcessError as e:
        print(f"[yosys_runner] FuseSoC execution failed with return code {e.returncode}.")
        sys.exit(e.returncode)


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("[yosys_runner] Usage: python yosys_runner.py <entity_name> <file1.vhd> <file2.vhd> ...")
        sys.exit(1)

    top_entity = sys.argv[1]
    input_files = sys.argv[2:]
    run_yosys_flow(top_entity, input_files)

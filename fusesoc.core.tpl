CAPI=2:
<%!
# Helper to normalize paths
def q(p):
    return p.replace('\\', '/')
%>
name: vlsi_lab:ms:${core_name}
description: Generated FuseSoC core for simulation and synthesis

filesets:
  rtl:
    files:
% for f, ftype in dut_files:
      - ${q(f)}: {file_type: ${ftype}}
% endfor

  sim:
    files:
% for f, ftype in tb_files:
      - ${q(f)}: {file_type: ${ftype}}
% endfor

targets:
  sim:
    default_tool: modelsim
    filesets: [rtl, sim]
    toplevel: ${entity_name}
    tools:
      modelsim:
        vlog_options: [-quiet, -timescale=1ns/1ps]
        vsim_options: [-voptargs="+acc"]

  syn:
    default_tool: yosys
    filesets: [rtl]
    toplevel: ${entity_name}
    tools:
      yosys:
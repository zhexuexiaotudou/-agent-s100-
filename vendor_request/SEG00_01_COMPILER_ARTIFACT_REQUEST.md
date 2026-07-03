# SEG00_01 Compiler Artifact Request

Please provide the exact artifacts required to close Dream7B seq128 B=1 `seg00_01` correctness:

- source ONNX/HBIR/HBO for `seg00_01` used to build the tested HBM
- quant scales and zero points for GatherND output and final add output
- constants and dynamic ranges used by `hbir.mul_id_63`
- separate tensors or formulas for `hbir.add_id_137` input-0 and input-1
- exact op list, shapes, layout, and split metadata
- calibration dataset, calibration command, and dynamic range tables
- compiler/HBDK/HBRT versions and export command
- mapping from HF source functions/layers to each exported segment

Current limitation: HRT dump shows View, GatherND, BPU hbir.mul, and BPU hbir.add, but does not expose `mul_output` or `add_input_position`.

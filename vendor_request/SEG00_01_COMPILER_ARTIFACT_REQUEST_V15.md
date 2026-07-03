# SEG00_01 Compiler Artifact Request V15

Required for Dream7B seq128 B=1 tested `seg00_01` HBM closure:

- source ONNX/HBIR/HBO matching `/mnt/nas/openclaw/models/dream7b-hbm/seq128-b1-lmheadq16-lasttoken/seg00_01/dream7b_segment_0_1_seq128_q8.hbm`
- HBDK/HBRT compiler metadata, export command, compiler version, and split metadata
- quantization table: GatherND output scale/zero point/layout, add output scale/zero point/layout
- calibration dataset and dynamic ranges for embedding table, `hbir.mul_id_63`, and `hbir.add_id_137`
- constants/formulas for `hbir.mul_id_63`, `hbir.add_id_137` input-0/input-1, and qnt.const_fake_quant nodes
- exact op list with tensor names, dtypes, shapes, scales, zero points, and layouts

# Paper Evidence Dossier v14

The paper-safe result is negative for the tested full-BPU and hybrid BPU-island paths, not a general impossibility claim for Dream7B on S100P. BF16 full-truth arrays are packaged as standalone v14 evidence. The strongest root-cause locus remains `seg00_01`; HRT-visible intermediate dumps show the embedding-like GatherND path and position-sensitive BPU add output, while missing compiler source graph prevents final operator-level closure. No generation quality and no 18888/18889 product route tests were run.

# Candidate Deployment Routes v14

No route is deployable on logits evidence yet. Candidate A is a corrected `seg00_01` re-export/recompile using vendor/compiler source graph and verified quant scales. Candidate B is a CPU/HF prefix plus BPU island plus HF suffix route only if a deployable no-fit or known-scale island correction passes strict logits validity. Candidate C is GGUF F16/logits reference, currently blocked by missing F16 artifact and logits-only runner. Generation remains locked.

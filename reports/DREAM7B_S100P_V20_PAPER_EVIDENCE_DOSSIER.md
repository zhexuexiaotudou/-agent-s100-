# Dream7B S100P V20 Paper Evidence Dossier

v20 does not repeat full-chain falsification. It localizes the remaining semantic HF truth blocker: the model loads all safetensors weights, embedding is fast, SDPA fallback is fast, and the decoder-layer dense/MLP path is the runtime bottleneck on S100P torch1.8 CPU. The reproducible next step is the included x86/GPU torch2 export bundle. Generation quality and product routes were not run.
